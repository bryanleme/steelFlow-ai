"""Post-model audit of synthetic causal mechanisms in the isolated truth area.

This module is the only validation boundary allowed to read causal truth. It is
called after models and final-test explanations have been frozen; truth never
enters fitting, model selection, features or optimization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from steelflow.config import ProjectConfigBundle
from steelflow.generation.manifest import utc_now, write_manifest


def _spearman(left: pd.Series, right: pd.Series) -> float:
    valid = left.notna() & right.notna()
    if valid.sum() < 20:
        return float("nan")
    return float(left[valid].rank().corr(right[valid].rank()))


def audit_causal_recovery(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    feature_root: Path,
    model_root: Path,
    evaluation_root: Path,
) -> dict[str, Any]:
    """Compare frozen public evidence with private truth after evaluation."""

    evaluation_manifest = json.loads(
        (evaluation_root / "evaluation_manifest.json").read_text(encoding="utf-8")
    )
    if evaluation_manifest.get("status") != "success":
        raise ValueError("causal audit requires a successful frozen evaluation manifest")
    simulation_run_id = str(evaluation_manifest["simulation_run_id"])
    truth_root = (
        project_root
        / "data"
        / "ground_truth"
        / bundle.simulation.profile.value
        / simulation_run_id
        / "tube_causal_truth"
    )
    if not truth_root.is_dir():
        raise ValueError(f"isolated causal truth not found: {truth_root}")

    assignments = pd.read_parquet(model_root / "splits" / "in_process_rolling.parquet")
    positions = assignments.loc[
        assignments["split"] == "final_test", "row_position"
    ].to_numpy(dtype=int)
    index = pd.read_parquet(feature_root / "in_process_rolling" / "index.parquet").iloc[
        positions
    ]
    X = pd.read_parquet(feature_root / "in_process_rolling" / "X.parquet").iloc[positions]
    y = pd.read_parquet(feature_root / "in_process_rolling" / "y.parquet").iloc[positions]
    public = pd.concat(
        [
            index[["entity_id"]].reset_index(drop=True),
            X.reset_index(drop=True),
            y.drop(columns=["sample_key", "target_available_at_ts"]).reset_index(drop=True),
        ],
        axis=1,
    )
    public["quality_failure"] = (~public["approved_first_pass"].astype(bool)).astype(int)
    truth_columns = [
        "tube_id",
        "product_complexity_latent",
        "calibration_drift_latent",
        "thermal_speed_penalty_latent",
        "eccentricity_interaction_latent",
        "heat_treatment_mismatch_latent",
        "sensor_degradation_latent",
    ]
    truth = pd.read_parquet(truth_root, columns=truth_columns)
    joined = public.merge(truth, left_on="entity_id", right_on="tube_id", validate="one_to_one")

    mechanisms = (
        (
            "product_mix_complexity",
            "product_complexity_latent",
            "actual_tph",
            -1,
            "energy_intensity",
            {"product_code", "grade_family", "rolling_load_index"},
        ),
        (
            "thermal_uniformity_x_mandrel_wear",
            "eccentricity_interaction_latent",
            "wall_eccentricity_pct",
            1,
            "wall_eccentricity",
            {"thermal_uniformity_index", "tool_wear_index"},
        ),
        (
            "speed_x_thermal_window",
            "thermal_speed_penalty_latent",
            "ovality_pct",
            1,
            "ovality",
            {"roll_speed_rpm", "observed_roll_speed", "thermal_uniformity_index"},
        ),
        (
            "heat_treatment_grade_x_thickness",
            "heat_treatment_mismatch_latent",
            "quality_failure",
            1,
            "quality_failure",
            {"grade_family", "product_code", "rolling_load_index"},
        ),
        (
            "accumulated_hours_x_sensor_degradation",
            "sensor_degradation_latent",
            "quality_failure",
            1,
            "quality_failure",
            {"sensor_degradation_index", "hours_since_maintenance", "tool_wear_index"},
        ),
        (
            "temporal_process_drift",
            "calibration_drift_latent",
            "outer_diameter_deviation_mm",
            1,
            "outer_diameter_deviation",
            {
                "reheat_exit_temp_c",
                "observed_reheat_exit_temperature",
                "reheat_zone_3_temp_c",
            },
        ),
    )
    records: list[dict[str, Any]] = []
    for mechanism_id, truth_signal, public_target, direction, task, expected_features in mechanisms:
        correlation = _spearman(joined[truth_signal], joined[public_target])
        shap = pd.read_parquet(evaluation_root / "explanations" / task / "global.parquet")
        top_features = set(shap.sort_values("rank").head(20)["feature"].astype(str))
        recovered_features = sorted(expected_features & top_features)
        association_recovered = (
            np.isfinite(correlation)
            and abs(correlation) >= 0.08
            and np.sign(correlation) == direction
        )
        model_signal_recovered = bool(recovered_features)
        records.append(
            {
                "mechanism_id": mechanism_id,
                "truth_signal": truth_signal,
                "public_target": public_target,
                "spearman": correlation,
                "expected_direction": "positive" if direction > 0 else "negative",
                "shap_task": task,
                "expected_public_features": sorted(expected_features),
                "recovered_public_features_in_top20": recovered_features,
                "association_recovered": bool(association_recovered),
                "model_signal_recovered": model_signal_recovered,
                "recovered": bool(association_recovered and model_signal_recovered),
            }
        )
    recovered = sum(record["recovered"] for record in records)
    result = {
        "status": "PASS" if recovered >= 4 else "FAIL",
        "required": 4,
        "recovered": recovered,
        "tested": len(records),
        "rows": len(joined),
        "executed_after_model_freeze": True,
        "truth_used_for_training": False,
        "method": "directional rank association plus expected public feature in top-20 TreeSHAP",
        "mechanisms": records,
        "audited_at_utc": utc_now().isoformat(),
        "synthetic_scope": "generator recovery audit only; not real-world causal validation",
    }
    audit_path = evaluation_root / "audit" / "causal_recovery.json"
    write_manifest(audit_path, result)
    return result
