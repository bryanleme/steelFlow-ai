"""Post-training validation for temporal model artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from steelflow.models.contracts import ModelingConfig


def validate_model_evaluation(
    modeling: ModelingConfig,
    *,
    training_manifest: dict[str, Any],
    model_root: Path,
    evaluation_root: Path,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "PASS" if passed else "FAIL",
                "observed": observed,
                "expected": expected,
            }
        )

    add(
        "training.final_test_isolation",
        training_manifest.get("final_test_labels_used") is False,
        training_manifest.get("final_test_labels_used"),
        False,
    )
    add(
        "contract.modeling_hash",
        training_manifest.get("modeling_config_sha256") == modeling.stable_hash(),
        training_manifest.get("modeling_config_sha256"),
        modeling.stable_hash(),
    )
    for snapshot, split_record in training_manifest["splits"].items():
        assignments = pd.read_parquet(model_root / split_record["path"])
        required = {"train", "tuning", "calibration", "final_test"}
        observed_splits = set(assignments["split"])
        add(
            f"splits.{snapshot}.required",
            required <= observed_splits,
            sorted(observed_splits),
            sorted(required),
        )
        maxima = assignments[assignments["split"].isin(required)].groupby("split")[
            "snapshot_ts"
        ].max()
        minima = assignments[assignments["split"].isin(required)].groupby("split")[
            "snapshot_ts"
        ].min()
        ordered = (
            maxima["train"] < minima["tuning"]
            and maxima["tuning"] < minima["calibration"]
            and maxima["calibration"] < minima["final_test"]
        )
        add(f"splits.{snapshot}.chronological", bool(ordered), bool(ordered), True)
        embargo_ok = assignments.loc[
            assignments["split"].isin(["train", "tuning", "calibration"]),
            "label_available_before_next_window",
        ].all()
        add(f"splits.{snapshot}.label_embargo", bool(embargo_ok), bool(embargo_ok), True)

    metrics = pd.read_parquet(evaluation_root / "metrics" / "final_test.parquet")
    add(
        "metrics.all_tasks",
        set(metrics["task"]) == {task.name for task in modeling.tasks},
        sorted(set(metrics["task"])),
        sorted(task.name for task in modeling.tasks),
    )
    for task in modeling.tasks:
        task_metrics = metrics[metrics["task"] == task.name]
        required_columns = (
            {"mae", "rmse", "r2"}
            if task.problem_type == "regression"
            else {
                "pr_auc",
                "roc_auc",
                "log_loss",
                "brier",
                "ece_10",
                "precision_at_0_5",
                "recall_at_0_5",
                "tn",
                "fp",
                "fn",
                "tp",
            }
        )
        add(
            f"metrics.{task.name}.required",
            required_columns <= set(task_metrics.columns),
            sorted(required_columns & set(task_metrics.columns)),
            sorted(required_columns),
        )
        main_name = (
            "catboost" if task.problem_type == "regression" else "catboost_calibrated_sigmoid"
        )
        add(
            f"metrics.{task.name}.main_model",
            main_name in set(task_metrics["model"]),
            sorted(set(task_metrics["model"])),
            main_name,
        )
        if task.quantiles:
            add(
                f"metrics.{task.name}.quantiles",
                "catboost_multiquantile" in set(task_metrics["model"]),
                sorted(set(task_metrics["model"])),
                "catboost_multiquantile",
            )
        explanation_root = evaluation_root / "explanations" / task.name
        required_explanations = {
            "global.parquet",
            "segments.parquet",
            "scenarios.parquet",
        }
        observed_explanations = {
            path.name for path in explanation_root.glob("*.parquet") if path.is_file()
        }
        add(
            f"shap.{task.name}",
            observed_explanations == required_explanations,
            sorted(observed_explanations),
            sorted(required_explanations),
        )

    evaluation_manifest = __import__("json").loads(
        (evaluation_root / "evaluation_manifest.json").read_text(encoding="utf-8")
    )
    add(
        "evaluation.single_final_test",
        evaluation_manifest.get("evaluation_count") == 1,
        evaluation_manifest.get("evaluation_count"),
        1,
    )
    recovered = int(evaluation_manifest.get("causal_audit", {}).get("recovered", 0))
    add("causal_audit.minimum_recovery", recovered >= 4, recovered, ">=4")
    failed = sum(check["status"] == "FAIL" for check in checks)
    return {
        "schema_version": "1.0",
        "status": "PASS" if failed == 0 else "FAIL",
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - failed,
            "failed": failed,
        },
        "checks": checks,
    }
