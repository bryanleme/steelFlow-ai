"""Validation of safe, reproducible optimization scenario packages."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from steelflow.features.contracts import FeatureContract
from steelflow.optimization.contracts import OptimizationConfig


def _is_nondominated(objectives: np.ndarray) -> bool:
    for index, candidate in enumerate(objectives):
        others = np.delete(objectives, index, axis=0)
        dominated = np.any(
            np.all(others <= candidate + 1e-12, axis=1)
            & np.any(others < candidate - 1e-12, axis=1)
        )
        if dominated:
            return False
    return True


def validate_optimization_package(
    config: OptimizationConfig,
    feature_contract: FeatureContract,
    *,
    manifest: dict[str, Any],
    scenarios: list[dict[str, Any]],
    refusals: list[dict[str, Any]],
    pareto_frames: list[pd.DataFrame],
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

    recommendable = {
        feature.name
        for feature in feature_contract.snapshot(config.snapshot).features
        if feature.recommendable
    }
    controls = set(config.controllables)
    add(
        "contract.recommendable_controls",
        controls == recommendable,
        sorted(controls),
        sorted(recommendable),
    )
    add(
        "lineage.final_test_isolation",
        manifest["final_test_labels_used"] is False,
        manifest["final_test_labels_used"],
        False,
    )
    add(
        "engine.nsga2",
        manifest["optimizer"]["algorithm"] == "NSGA-II",
        manifest["optimizer"]["algorithm"],
        "NSGA-II",
    )
    context_ids = {scenario["context_id"] for scenario in scenarios}
    add(
        "demo.context_count",
        len(context_ids) == config.demo.contexts,
        len(context_ids),
        config.demo.contexts,
    )
    expected_labels = {"current", "conservative", "balanced", "productivity"}
    labels_by_context = {
        context_id: {item["label"] for item in scenarios if item["context_id"] == context_id}
        for context_id in context_ids
    }
    add(
        "scenarios.four_labels_per_context",
        all(labels == expected_labels for labels in labels_by_context.values()),
        labels_by_context,
        sorted(expected_labels),
    )
    add(
        "scenarios.controls_only",
        all(set(item["parameters"]) == controls for item in scenarios),
        sorted({parameter for item in scenarios for parameter in item["parameters"]}),
        sorted(controls),
    )
    add(
        "scenarios.hard_constraints",
        all(item["hard_constraints_pass"] for item in scenarios),
        sum(item["hard_constraints_pass"] for item in scenarios),
        len(scenarios),
    )
    add(
        "scenarios.in_distribution",
        all(item["ood_assessment"]["in_distribution"] for item in scenarios),
        sum(item["ood_assessment"]["in_distribution"] for item in scenarios),
        len(scenarios),
    )
    add(
        "scenarios.human_approval",
        all(item["human_approval_required"] for item in scenarios),
        sum(item["human_approval_required"] for item in scenarios),
        len(scenarios),
    )
    add(
        "scenarios.noncausal_language",
        all(
            item["interpretation"] == "cenário estimado em backtest sintético"
            for item in scenarios
        ),
        sorted({item["interpretation"] for item in scenarios}),
        "cenário estimado em backtest sintético",
    )
    add(
        "ood.one_refusal_per_context",
        len(refusals) == config.demo.contexts,
        len(refusals),
        config.demo.contexts,
    )
    add(
        "ood.refusal_blocks_recommendation",
        all(
            not item["recommendation_issued"]
            and item["engineering_validation_required"]
            and not item["ood_assessment"]["in_distribution"]
            for item in refusals
        ),
        sum(not item["recommendation_issued"] for item in refusals),
        len(refusals),
    )
    objective_columns = [
        "objective_negative_tbh_proxy",
        "objective_quality_risk",
        "objective_energy",
        "objective_downtime_risk",
        "objective_expected_downtime",
        "objective_intervention_magnitude",
    ]
    add(
        "pareto.all_feasible",
        all(bool(frame["hard_constraints_pass"].all()) for frame in pareto_frames),
        [int(frame["hard_constraints_pass"].sum()) for frame in pareto_frames],
        [len(frame) for frame in pareto_frames],
    )
    add(
        "pareto.nondominated",
        all(_is_nondominated(frame[objective_columns].to_numpy(float)) for frame in pareto_frames),
        len(pareto_frames),
        len(pareto_frames),
    )
    failed = sum(check["status"] == "FAIL" for check in checks)
    return {
        "schema_version": "1.0",
        "status": "PASS" if failed == 0 else "FAIL",
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - failed,
            "failed": failed,
        },
        "published_scenarios": len(scenarios),
        "hard_constraint_pass_rate": float(
            sum(item["hard_constraints_pass"] for item in scenarios) / max(len(scenarios), 1)
        ),
        "ood_refusal_rate": float(
            sum(not item["recommendation_issued"] for item in refusals)
            / max(len(refusals), 1)
        ),
        "checks": checks,
    }
