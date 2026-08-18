"""Interactive scenario evaluation and export with explicit human acknowledgement."""

from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd

from steelflow.features.contracts import load_feature_contract
from steelflow.optimization.contracts import load_optimization_config
from steelflow.optimization.envelope import HistoricalEnvelope, build_historical_envelope
from steelflow.optimization.predictor import (
    AssetEstimate,
    ScenarioPredictor,
    ThroughputSurrogate,
)
from steelflow.product.artifacts import ProductArtifacts


@dataclass(frozen=True)
class InteractiveScenarioRuntime:
    context_id: str
    current_payload: dict[str, Any]
    current: pd.Series
    envelope: HistoricalEnvelope
    asset: AssetEstimate
    predictor: ScenarioPredictor


def _scenario_files(artifacts: ProductArtifacts, context_id: str) -> list[Any]:
    payloads = []
    for path in sorted((artifacts.optimization_root / "scenarios").glob(f"{context_id}-*.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def build_interactive_runtime(
    artifacts: ProductArtifacts,
    context_id: str,
) -> InteractiveScenarioRuntime:
    config = load_optimization_config(artifacts.project_root)
    feature_contract = load_feature_contract(artifacts.project_root)
    payloads = _scenario_files(artifacts, context_id)
    try:
        current_payload = next(item for item in payloads if item["label"] == "current")
    except StopIteration as exc:
        raise ValueError(f"cenário atual ausente para {context_id}") from exc
    snapshot_contract = feature_contract.snapshot(config.snapshot)
    values = dict(current_payload["fixed_context"])
    values.update(
        {
            name: specification["current_value"]
            for name, specification in current_payload["parameters"].items()
        }
    )
    feature_order = [feature.name for feature in snapshot_contract.features]
    current = pd.Series(values).reindex(feature_order)
    if current.isna().any():
        missing = current.index[current.isna()].tolist()
        raise ValueError(f"contexto interativo incompleto: {missing}")
    X = pd.read_parquet(artifacts.feature_root / config.snapshot / "X.parquet")
    assignments = pd.read_parquet(artifacts.model_root / "splits/in_process_rolling.parquet")
    positions = assignments.loc[assignments["split"] == "train", "row_position"].to_numpy()
    envelope = build_historical_envelope(X.iloc[positions], current, config)
    surrogate_root = artifacts.optimization_root / "surrogate"
    surrogate = ThroughputSurrogate(
        point_model=joblib.load(surrogate_root / "actual_tph_point.joblib"),
        quantile_model=joblib.load(surrogate_root / "actual_tph_quantiles.joblib"),
        categorical_features=tuple(
            feature.name for feature in snapshot_contract.features if feature.dtype == "category"
        ),
        metrics=json.loads((surrogate_root / "metrics.json").read_text(encoding="utf-8")),
    )
    downtime = current_payload["predictions"]["downtime"]
    asset = AssetEstimate(
        sample_key=str(current_payload["asset_sample_key"]),
        context={},
        downtime_probability=float(downtime["probability"]),
        duration_p10=float(downtime["duration_p10_minutes"]),
        duration_p50=float(downtime["duration_p50_minutes"]),
        duration_p90=float(downtime["duration_p90_minutes"]),
    )
    predictor = ScenarioPredictor(
        model_root=artifacts.model_root,
        feature_contract=feature_contract,
        surrogate=surrogate,
        config=config,
    )
    return InteractiveScenarioRuntime(
        context_id=context_id,
        current_payload=current_payload,
        current=current,
        envelope=envelope,
        asset=asset,
        predictor=predictor,
    )


def evaluate_interactive_scenario(
    runtime: InteractiveScenarioRuntime,
    parameters: dict[str, float],
) -> dict[str, Any]:
    expected = set(runtime.envelope.controllables)
    if set(parameters) != expected:
        raise ValueError("parâmetros interativos não correspondem ao contrato controlável")
    values = np.asarray([parameters[name] for name in runtime.envelope.controllables], dtype=float)
    evaluation = runtime.predictor.evaluate(
        values,
        current=runtime.current,
        envelope=runtime.envelope,
        asset=runtime.asset,
    ).iloc[0]
    constraints = [
        {
            "name": column.removeprefix("constraint_"),
            "normalized_violation": float(evaluation[column]),
            "margin": float(-evaluation[column]),
            "status": "PASS" if evaluation[column] <= 1e-9 else "FAIL",
        }
        for column in evaluation.index
        if column.startswith("constraint_")
    ]
    safe = bool(evaluation["hard_constraints_pass"] and evaluation["in_distribution"])
    return {
        "schema_version": "1.0",
        "context_id": runtime.context_id,
        "status": "ELIGIBLE_FOR_HUMAN_REVIEW" if safe else "REFUSED",
        "recommendation_issued": safe,
        "engineering_validation_required": not safe,
        "human_approval_required": True,
        "human_approved": False,
        "machine_command": False,
        "interpretation": "cenário estimado em backtest sintético",
        "parameters": {name: float(parameters[name]) for name in runtime.envelope.controllables},
        "predictions": {
            "estimated_tbh_proxy": float(evaluation["estimated_tbh_proxy"]),
            "actual_tph": {
                "p10": float(evaluation["throughput_p10"]),
                "p50": float(evaluation["throughput_p50"]),
                "p90": float(evaluation["throughput_p90"]),
            },
            "quality_failure_probability": float(
                evaluation["quality_failure_probability"]
            ),
            "estimated_fpy": float(evaluation["estimated_fpy"]),
            "energy_per_good_tonne": {
                "p10": float(evaluation["energy_p10"]),
                "p50": float(evaluation["energy_p50"]),
                "p90": float(evaluation["energy_p90"]),
            },
            "downtime_probability": float(evaluation["downtime_probability"]),
            "expected_downtime_minutes": float(
                evaluation["expected_downtime_minutes"]
            ),
        },
        "ood_assessment": {
            "within_conditional_bounds": bool(evaluation["within_conditional_bounds"]),
            "historical_distance": float(evaluation["historical_distance"]),
            "distance_threshold": float(evaluation["distance_threshold"]),
            "distance_ratio": float(evaluation["distance_ratio"]),
            "in_distribution": bool(evaluation["in_distribution"]),
        },
        "hard_constraints_pass": bool(evaluation["hard_constraints_pass"]),
        "constraints": constraints,
    }


def approve_scenario(
    scenario: dict[str, Any],
    *,
    acknowledgement: bool,
    approved_at: datetime | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    if not acknowledgement:
        raise ValueError("a confirmação humana explícita é obrigatória")
    if not scenario.get("recommendation_issued") or not scenario.get("hard_constraints_pass"):
        raise ValueError("cenário recusado não pode receber aprovação")
    approved = json.loads(json.dumps(scenario))
    approved["human_approved"] = True
    approved["approval"] = {
        "approval_id": approval_id or str(uuid.uuid4()),
        "approved_at_utc": (approved_at or datetime.now(UTC)).isoformat(),
        "acknowledgement": (
            "Simulação sintética revisada por humano; não constitui comando de máquina."
        ),
    }
    return approved


def scenario_json_bytes(scenario: dict[str, Any]) -> bytes:
    return (
        json.dumps(scenario, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def scenario_csv_bytes(scenario: dict[str, Any]) -> bytes:
    row: dict[str, Any] = {
        "context_id": scenario["context_id"],
        "status": scenario["status"],
        "human_approved": scenario["human_approved"],
        "in_distribution": scenario["ood_assessment"]["in_distribution"],
        "hard_constraints_pass": scenario["hard_constraints_pass"],
    }
    row.update({f"parameter__{key}": value for key, value in scenario["parameters"].items()})
    for key, value in scenario["predictions"].items():
        if isinstance(value, dict):
            row.update({f"prediction__{key}__{inner}": item for inner, item in value.items()})
        else:
            row[f"prediction__{key}"] = value
    buffer = io.StringIO()
    pd.DataFrame([row]).to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8-sig")
