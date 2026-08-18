"""End-to-end constrained optimization demo over frozen synthetic models."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from steelflow.config import ProjectConfigBundle
from steelflow.features.contracts import load_feature_contract
from steelflow.generation.manifest import dependency_versions, utc_now
from steelflow.models.contracts import load_modeling_config
from steelflow.models.data import load_snapshot
from steelflow.models.pipeline import resolve_model_root
from steelflow.optimization.contracts import OptimizationConfig, load_optimization_config
from steelflow.optimization.envelope import (
    EnvelopeError,
    HistoricalEnvelope,
    build_historical_envelope,
    wear_band,
)
from steelflow.optimization.predictor import (
    AssetEstimate,
    ScenarioPredictor,
    save_throughput_surrogate,
    train_throughput_surrogate,
)
from steelflow.optimization.problem import optimize_context, select_alternatives
from steelflow.validation.optimization import validate_optimization_package


class OptimizationPipelineError(RuntimeError):
    """Raised when the package cannot safely publish scenarios."""


@dataclass(frozen=True)
class OptimizationResult:
    simulation_run_id: str
    optimization_root: Path
    manifest_path: Path
    context_count: int
    scenario_count: int
    logical_sha256: str
    reused: bool
    elapsed_seconds: float


def _native(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(item) for item in value]
    if isinstance(value, set):
        return sorted(_native(item) for item in value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _canonical_hash(value: Any) -> str:
    content = json.dumps(
        _native(value),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_native(value), ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _safe_remove(path: Path, parent: Path) -> None:
    resolved = path.resolve()
    safe_parent = parent.resolve()
    if resolved == safe_parent or safe_parent not in resolved.parents:
        raise OptimizationPipelineError(f"refusing to remove unsafe path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _optimization_root(model_root: Path, config: OptimizationConfig) -> Path:
    return (
        model_root
        / "optimization"
        / f"optimization-v{config.optimization_version}-{config.stable_hash()[:12]}"
    )


def _asset_estimate(
    *,
    line_id: str,
    asset_data: Any,
    assignments: pd.DataFrame,
    predictor: ScenarioPredictor,
    config: OptimizationConfig,
) -> AssetEstimate:
    positions = assignments.loc[assignments["split"] == "train", "row_position"].to_numpy()
    X = asset_data.X.iloc[positions]
    selected = X["line_id"].astype(str) == line_id
    X_line = X.loc[selected]
    if X_line.empty:
        raise OptimizationPipelineError(f"no asset training context for {line_id}")
    estimates = predictor.estimate_asset_rows(
        X_line,
        asset_data.index.loc[X_line.index, "sample_key"],
    )
    limits = config.constraints
    feasible = estimates[
        (estimates["downtime_probability"] <= limits.max_downtime_probability)
        & (
            estimates["expected_downtime_minutes"]
            <= limits.max_expected_downtime_minutes
        )
    ]
    if feasible.empty:
        raise OptimizationPipelineError(f"no safe asset context for {line_id}")
    probability_median = float(feasible["downtime_probability"].median())
    duration_median = float(feasible["duration_p50"].median())
    score = (
        np.abs(feasible["downtime_probability"] - probability_median)
        / max(limits.max_downtime_probability, 1e-12)
        + np.abs(feasible["duration_p50"] - duration_median)
        / max(limits.max_expected_downtime_minutes, 1e-12)
    )
    selected_index = score.sort_values(kind="stable").index[0]
    row = feasible.loc[selected_index]
    context = _native(X_line.loc[selected_index].to_dict())
    return AssetEstimate(
        sample_key=str(row["sample_key"]),
        context=context,
        downtime_probability=float(row["downtime_probability"]),
        duration_p10=float(row["duration_p10"]),
        duration_p50=float(row["duration_p50"]),
        duration_p90=float(row["duration_p90"]),
    )


def _candidate_indices(
    training: pd.DataFrame,
    *,
    line_id: str,
    config: OptimizationConfig,
) -> list[int]:
    enriched = training.copy()
    enriched["wear_band"] = wear_band(
        enriched["tool_wear_index"], config.envelope.wear_band_edges
    )
    line = enriched[enriched["line_id"].astype(str) == line_id]
    groups = (
        line.groupby(
            ["product_code", "grade_family", "line_id", "wear_band"],
            observed=True,
        )
        .size()
        .sort_values(ascending=False, kind="stable")
    )
    controls = list(config.controllables)
    ordered: list[int] = []
    for group_values, count in groups.items():
        if int(count) < config.envelope.minimum_support:
            continue
        mask = pd.Series(True, index=line.index)
        for column, value in zip(groups.index.names, group_values, strict=True):
            mask &= line[column].astype(str) == str(value)
        group = line.loc[mask]
        center = group[controls].median().to_numpy(dtype=float)
        scale = np.maximum(group[controls].std(ddof=0).to_numpy(dtype=float), 1e-12)
        distance = np.square((group[controls].to_numpy(dtype=float) - center) / scale).mean(axis=1)
        ordered.extend(
            int(index)
            for index in group.index[np.argsort(distance, kind="stable")[:100]]
            if int(index) not in ordered
        )
    return ordered


def _select_process_context(
    *,
    line_id: str,
    rolling_data: Any,
    training: pd.DataFrame,
    predictor: ScenarioPredictor,
    asset: AssetEstimate,
    config: OptimizationConfig,
) -> tuple[pd.Series, pd.Series, HistoricalEnvelope]:
    errors: list[str] = []
    for row_index in _candidate_indices(training, line_id=line_id, config=config):
        current = rolling_data.X.loc[row_index]
        try:
            envelope = build_historical_envelope(training, current, config)
        except EnvelopeError as exc:
            errors.append(str(exc))
            continue
        evaluation = predictor.evaluate(
            envelope.current,
            current=current,
            envelope=envelope,
            asset=asset,
        ).iloc[0]
        if bool(evaluation["hard_constraints_pass"]):
            return current, rolling_data.index.loc[row_index], envelope
        errors.append("medoid failed model/uncertainty hard constraints")
    detail = errors[-1] if errors else "no supported conditional group"
    raise OptimizationPipelineError(f"no safe process context for {line_id}: {detail}")


def _constraint_records(row: pd.Series, config: OptimizationConfig) -> list[dict[str, Any]]:
    limits = config.constraints
    observed = {
        "historical_distance": float(row["distance_ratio"]),
        "quality_failure_probability": float(row["quality_failure_probability"]),
        "downtime_probability": float(row["downtime_probability"]),
        "expected_downtime_minutes": float(row["expected_downtime_minutes"]),
        "throughput_interval_width": float(row["throughput_interval_width"]),
        "energy_interval_width": float(row["energy_interval_width"]),
        "outer_diameter_deviation": float(
            max(
                abs(row["outer_diameter_deviation_p10"]),
                abs(row["outer_diameter_deviation_p90"]),
            )
        ),
        "wall_eccentricity": float(row["wall_eccentricity_p90"]),
        "ovality": float(row["ovality_p90"]),
    }
    thresholds = {
        "historical_distance": 1.0,
        "quality_failure_probability": limits.max_quality_failure_probability,
        "downtime_probability": limits.max_downtime_probability,
        "expected_downtime_minutes": limits.max_expected_downtime_minutes,
        "throughput_interval_width": limits.max_throughput_interval_width,
        "energy_interval_width": limits.max_energy_interval_width,
        "outer_diameter_deviation": limits.max_abs_outer_diameter_deviation_mm,
        "wall_eccentricity": limits.max_wall_eccentricity_pct,
        "ovality": limits.max_ovality_pct,
    }
    return [
        {
            "name": name,
            "observed": value,
            "maximum": float(thresholds[name]),
            "margin": float(thresholds[name] - value),
            "status": "PASS" if value <= thresholds[name] + 1e-9 else "FAIL",
        }
        for name, value in observed.items()
    ]


def _scenario_payload(
    *,
    label: str,
    context_id: str,
    current: pd.Series,
    process_index: pd.Series,
    envelope: HistoricalEnvelope,
    asset: AssetEstimate,
    row: pd.Series,
    config: OptimizationConfig,
) -> dict[str, Any]:
    parameters = {
        name: {
            "value": float(row[name]),
            "current_value": float(current[name]),
            "unit": config.controllables[name].unit,
        }
        for name in envelope.controllables
    }
    factors = sorted(
        (
            {
                "parameter": bound.name,
                "current_value": bound.current_value,
                "scenario_value": float(row[bound.name]),
                "normalized_change": float(
                    abs(float(row[bound.name]) - bound.current_value)
                    / max(bound.max_absolute_change, 1e-12)
                ),
                "interpretation": "alteração controlável; associação preditiva, não causal",
            }
            for bound in envelope.bounds
        ),
        key=lambda item: (-item["normalized_change"], item["parameter"]),
    )[:3]
    constraints = _constraint_records(row, config)
    active = [
        item["name"]
        for item in sorted(constraints, key=lambda item: (item["margin"], item["name"]))[:3]
    ]
    fixed_features = {
        name: _native(value)
        for name, value in current.items()
        if name not in envelope.controllables
    }
    return {
        "schema_version": "1.0",
        "scenario_id": f"{context_id}-{label}",
        "context_id": context_id,
        "label": label,
        "status": "reference" if label == "current" else "eligible_for_human_review",
        "recommendation_issued": label != "current",
        "human_approval_required": True,
        "interpretation": "cenário estimado em backtest sintético",
        "causal_claim": False,
        "synthetic_scope": "protótipo offline; sem controle de máquina",
        "process_sample_key": str(process_index["sample_key"]),
        "asset_sample_key": asset.sample_key,
        "fixed_context": fixed_features,
        "fixed_context_sha256": _canonical_hash(fixed_features),
        "parameters": parameters,
        "predictions": {
            "actual_tph_surrogate": {
                "p10": float(row["throughput_p10"]),
                "p50": float(row["throughput_p50"]),
                "p90": float(row["throughput_p90"]),
                "unit": "t/h",
                "role": "auxiliary controllable surrogate",
            },
            "estimated_tbh_proxy": {
                "p50": float(row["estimated_tbh_proxy"]),
                "definition": "actual_tph P50 × (1 − calibrated quality failure probability)",
                "unit": "t boa/h",
            },
            "quality": {
                "failure_probability": float(row["quality_failure_probability"]),
                "estimated_fpy": float(row["estimated_fpy"]),
            },
            "energy_per_good_tonne_kwh_t": {
                "p10": float(row["energy_p10"]),
                "p50": float(row["energy_p50"]),
                "p90": float(row["energy_p90"]),
            },
            "outer_diameter_deviation_mm": {
                "p10": float(row["outer_diameter_deviation_p10"]),
                "p50": float(row["outer_diameter_deviation_p50"]),
                "p90": float(row["outer_diameter_deviation_p90"]),
            },
            "wall_eccentricity_pct": {
                "p10": float(row["wall_eccentricity_p10"]),
                "p50": float(row["wall_eccentricity_p50"]),
                "p90": float(row["wall_eccentricity_p90"]),
            },
            "ovality_pct": {
                "p10": float(row["ovality_p10"]),
                "p50": float(row["ovality_p50"]),
                "p90": float(row["ovality_p90"]),
            },
            "downtime": {
                "probability": asset.downtime_probability,
                "duration_p10_minutes": asset.duration_p10,
                "duration_p50_minutes": asset.duration_p50,
                "duration_p90_minutes": asset.duration_p90,
                "expected_minutes": asset.expected_downtime_minutes,
                "scenario_invariant": True,
                "reason": "frozen asset model has no rolling controllables",
            },
        },
        "uncertainty": {
            "throughput_p90_minus_p10": float(row["throughput_interval_width"]),
            "energy_p90_minus_p10": float(row["energy_interval_width"]),
        },
        "ood_assessment": {
            "within_conditional_bounds": bool(row["within_conditional_bounds"]),
            "historical_distance": float(row["historical_distance"]),
            "distance_threshold": float(row["distance_threshold"]),
            "distance_ratio": float(row["distance_ratio"]),
            "in_distribution": bool(row["in_distribution"]),
        },
        "hard_constraints_pass": (
            all(item["status"] == "PASS" for item in constraints)
            and bool(row["within_conditional_bounds"])
            and bool(row["in_distribution"])
        ),
        "constraints": constraints,
        "active_constraints": active,
        "main_factors": factors,
    }


def _refusal_payload(
    context_id: str,
    envelope: HistoricalEnvelope,
) -> dict[str, Any]:
    probe = envelope.current.copy()
    span = envelope.upper_bounds[0] - envelope.lower_bounds[0]
    probe[0] = envelope.upper_bounds[0] + max(span * 0.05, 1e-6)
    assessment = envelope.assess(probe).iloc[0]
    return {
        "schema_version": "1.0",
        "context_id": context_id,
        "status": "REFUSED_OOD",
        "recommendation_issued": False,
        "engineering_validation_required": True,
        "warning": (
            "Cenário fora do envelope histórico condicional; nenhuma recomendação foi emitida. "
            "Solicite validação de engenharia e novos dados representativos."
        ),
        "violated_parameter": envelope.controllables[0],
        "ood_assessment": {
            "within_conditional_bounds": bool(assessment["within_conditional_bounds"]),
            "historical_distance": float(assessment["historical_distance"]),
            "distance_threshold": float(assessment["distance_threshold"]),
            "distance_ratio": float(assessment["distance_ratio"]),
            "in_distribution": bool(assessment["in_distribution"]),
        },
    }


def run_optimization_demo(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    overwrite: bool = False,
) -> OptimizationResult:
    timer = time.perf_counter()
    root = project_root.resolve()
    config = load_optimization_config(root)
    feature_contract = load_feature_contract(root)
    recommendable = {
        feature.name
        for feature in feature_contract.snapshot(config.snapshot).features
        if feature.recommendable
    }
    if set(config.controllables) != recommendable:
        raise OptimizationPipelineError(
            "optimization controls must exactly match frozen recommendable features"
        )
    modeling = load_modeling_config(root)
    feature_root, model_root = resolve_model_root(bundle, root, modeling, feature_contract)
    training_manifest_path = model_root / "training_manifest.json"
    evaluation_manifest_path = model_root / "evaluation" / "evaluation_manifest.json"
    if not training_manifest_path.is_file() or not evaluation_manifest_path.is_file():
        raise OptimizationPipelineError("frozen Phase 5 training and evaluation are required")
    training_manifest = json.loads(training_manifest_path.read_text(encoding="utf-8"))
    evaluation_manifest = json.loads(evaluation_manifest_path.read_text(encoding="utf-8"))
    if training_manifest.get("final_test_labels_used") is not False:
        raise OptimizationPipelineError("upstream training did not preserve final-test isolation")
    if evaluation_manifest.get("evaluation_count") != 1:
        raise OptimizationPipelineError("upstream final evaluation is not frozen exactly once")
    final_root = _optimization_root(model_root, config)
    parent = final_root.parent
    staging = parent / f".{final_root.name}.staging"
    manifest_path = final_root / "optimization_manifest.json"
    if final_root.exists() and not overwrite:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return OptimizationResult(
            simulation_run_id=str(training_manifest["simulation_run_id"]),
            optimization_root=final_root,
            manifest_path=manifest_path,
            context_count=int(manifest["context_count"]),
            scenario_count=int(manifest["scenario_count"]),
            logical_sha256=str(manifest["logical_sha256"]),
            reused=True,
            elapsed_seconds=time.perf_counter() - timer,
        )
    parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        _safe_remove(final_root, parent)
    _safe_remove(staging, parent)
    staging.mkdir(parents=True, exist_ok=False)
    try:
        rolling_data = load_snapshot(feature_root, feature_contract, "in_process_rolling")
        asset_data = load_snapshot(feature_root, feature_contract, "asset_window")
        rolling_assignments = pd.read_parquet(model_root / "splits/in_process_rolling.parquet")
        asset_assignments = pd.read_parquet(model_root / "splits/asset_window.parquet")
        surrogate = train_throughput_surrogate(rolling_data, rolling_assignments, config)
        save_throughput_surrogate(surrogate, staging / "surrogate")
        predictor = ScenarioPredictor(
            model_root=model_root,
            feature_contract=feature_contract,
            surrogate=surrogate,
            config=config,
        )
        training_positions = rolling_assignments.loc[
            rolling_assignments["split"] == "train", "row_position"
        ].to_numpy()
        training = rolling_data.X.iloc[training_positions]
        lines = sorted(training["line_id"].astype(str).unique())
        if len(lines) != config.demo.contexts:
            raise OptimizationPipelineError(
                f"expected {config.demo.contexts} lines, found {len(lines)}"
            )
        scenarios: list[dict[str, Any]] = []
        refusals: list[dict[str, Any]] = []
        pareto_frames: list[pd.DataFrame] = []
        context_records: list[dict[str, Any]] = []
        for ordinal, line_id in enumerate(lines, start=1):
            asset = _asset_estimate(
                line_id=line_id,
                asset_data=asset_data,
                assignments=asset_assignments,
                predictor=predictor,
                config=config,
            )
            current, process_index, envelope = _select_process_context(
                line_id=line_id,
                rolling_data=rolling_data,
                training=training,
                predictor=predictor,
                asset=asset,
                config=config,
            )
            context_id = f"context-{ordinal:02d}-{line_id.lower()}"
            outcome = optimize_context(
                predictor=predictor,
                current=current,
                envelope=envelope,
                asset=asset,
                config=config,
                seed_offset=ordinal,
            )
            selected = select_alternatives(outcome.pareto, envelope=envelope)
            current_evaluation = predictor.evaluate(
                envelope.current,
                current=current,
                envelope=envelope,
                asset=asset,
            ).iloc[0]
            current_row = pd.concat(
                [
                    pd.Series(
                        dict(zip(envelope.controllables, envelope.current, strict=True))
                    ),
                    current_evaluation,
                ]
            )
            context_scenarios = {"current": current_row, **selected}
            for label, row in context_scenarios.items():
                payload = _scenario_payload(
                    label=label,
                    context_id=context_id,
                    current=current,
                    process_index=process_index,
                    envelope=envelope,
                    asset=asset,
                    row=row,
                    config=config,
                )
                scenarios.append(payload)
                _write_json(staging / "scenarios" / f"{payload['scenario_id']}.json", payload)
            refusal = _refusal_payload(context_id, envelope)
            refusals.append(refusal)
            _write_json(staging / "refusals" / f"{context_id}-ood.json", refusal)
            pareto = outcome.pareto.copy()
            pareto.insert(0, "context_id", context_id)
            (staging / "pareto").mkdir(parents=True, exist_ok=True)
            pareto.to_parquet(staging / "pareto" / f"{context_id}.parquet", index=False)
            pareto_frames.append(pareto)
            envelope_record = envelope.to_dict()
            _write_json(staging / "envelopes" / f"{context_id}.json", envelope_record)
            context_records.append(
                {
                    "context_id": context_id,
                    "line_id": line_id,
                    "process_sample_key": str(process_index["sample_key"]),
                    "asset_sample_key": asset.sample_key,
                    "conditional_support_rows": envelope.support_rows,
                    "conditioning_columns": list(envelope.conditioning_columns),
                    "pareto_scenarios": len(pareto),
                    "nsga2_evaluations": outcome.evaluations,
                    "nsga2_generations": outcome.generations,
                }
            )
        logical_payload = {
            "optimization_config_sha256": config.stable_hash(),
            "upstream_modeling_config_sha256": modeling.stable_hash(),
            "surrogate_metrics": surrogate.metrics,
            "contexts": context_records,
            "scenarios": scenarios,
            "refusals": refusals,
            "pareto": [
                frame[
                    [
                        *config.controllables,
                        "objective_negative_tbh_proxy",
                        "objective_quality_risk",
                        "objective_energy",
                        "objective_downtime_risk",
                        "objective_expected_downtime",
                        "objective_intervention_magnitude",
                    ]
                ].to_dict(orient="records")
                for frame in pareto_frames
            ],
        }
        logical_sha256 = _canonical_hash(logical_payload)
        dependencies = dependency_versions()
        for package in ("pymoo", "catboost", "scikit-learn", "joblib"):
            dependencies[package] = importlib.metadata.version(package)
        manifest = {
            "schema_version": "1.0",
            "status": "success",
            "simulation_run_id": training_manifest["simulation_run_id"],
            "profile": bundle.simulation.profile.value,
            "optimization_version": config.optimization_version,
            "optimization_config_sha256": config.stable_hash(),
            "feature_contract_sha256": feature_contract.stable_hash(),
            "modeling_config_sha256": modeling.stable_hash(),
            "upstream_training_manifest": str(training_manifest_path.relative_to(root)),
            "upstream_evaluation_manifest": str(evaluation_manifest_path.relative_to(root)),
            "final_test_labels_used": False,
            "context_count": len(context_records),
            "scenario_count": len(scenarios),
            "published_hard_constraint_pass_rate": 1.0,
            "ood_probe_count": len(refusals),
            "ood_recommendations_issued": 0,
            "optimizer": {
                "algorithm": "NSGA-II",
                "implementation": "pymoo",
                "population_size": config.nsga2.population_size,
                "offspring": config.nsga2.offspring,
                "generations": config.nsga2.generations,
                "random_seed": config.random_seed,
                "objectives": [
                    "maximize estimated TBH proxy",
                    "minimize calibrated quality failure probability",
                    "minimize energy per good tonne",
                    "minimize downtime probability",
                    "minimize expected downtime duration",
                    "minimize normalized intervention magnitude",
                ],
            },
            "decision_scope": {
                "controllables": list(config.controllables),
                "fixed_mediators_and_context": True,
                "heat_treatment_controls_available": False,
                "downtime_objectives_scenario_invariant": True,
            },
            "throughput_proxy": {
                "definition": "actual_tph P50 × (1 − calibrated quality failure probability)",
                "surrogate_fit": "train with tuning early stopping",
                "surrogate_assessment": "calibration only",
                "final_test_performance_claimed": False,
            },
            "human_approval_required": True,
            "interpretation": (
                "cenários estimados em backtest sintético; não contrafactuais causais"
            ),
            "contexts": context_records,
            "logical_sha256": logical_sha256,
            "dependencies": dependencies,
            "completed_at_utc": utc_now().isoformat(),
            "synthetic_scope": "protótipo offline; sem controle de máquina",
        }
        validation = validate_optimization_package(
            config,
            feature_contract,
            manifest=manifest,
            scenarios=scenarios,
            refusals=refusals,
            pareto_frames=pareto_frames,
        )
        _write_json(staging / "validation.json", validation)
        if validation["status"] != "PASS":
            raise OptimizationPipelineError(
                f"optimization validation failed: {validation['summary']['failed']} checks"
            )
        _write_json(staging / "optimization_manifest.json", manifest)
        staging.replace(final_root)
        return OptimizationResult(
            simulation_run_id=str(training_manifest["simulation_run_id"]),
            optimization_root=final_root,
            manifest_path=final_root / "optimization_manifest.json",
            context_count=len(context_records),
            scenario_count=len(scenarios),
            logical_sha256=logical_sha256,
            reused=False,
            elapsed_seconds=time.perf_counter() - timer,
        )
    except Exception as exc:
        _safe_remove(staging, parent)
        if isinstance(exc, OptimizationPipelineError):
            raise
        raise OptimizationPipelineError(f"optimization demo failed: {exc}") from exc
