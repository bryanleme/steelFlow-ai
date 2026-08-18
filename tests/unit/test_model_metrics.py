from __future__ import annotations

import pytest

from steelflow.models.metrics import (
    classification_metrics,
    quantile_metrics,
    regression_metrics,
)


def test_regression_and_quantile_metrics_are_exact_for_perfect_predictions() -> None:
    observed = [1.0, 2.0, 3.0, 4.0]

    point = regression_metrics(observed, observed)
    intervals = quantile_metrics(
        observed,
        [[0.5, 1.0, 1.5], [1.5, 2.0, 2.5], [2.5, 3.0, 3.5], [3.5, 4.0, 4.5]],
    )

    assert point == {"mae": 0.0, "rmse": 0.0, "r2": 1.0}
    assert intervals["p50_mae"] == 0.0
    assert intervals["empirical_coverage_80"] == 1.0


def test_classification_metrics_include_calibration_confusion_and_alert_budget() -> None:
    metrics = classification_metrics(
        [0, 0, 1, 1],
        [0.01, 0.10, 0.80, 0.99],
        alert_budgets=(0.25, 0.50),
    )

    assert metrics["pr_auc"] == pytest.approx(1.0)
    assert metrics["roc_auc"] == pytest.approx(1.0)
    assert metrics["tn"] == 2
    assert metrics["tp"] == 2
    assert metrics["recall_at_alert_budget_25pct"] == pytest.approx(0.5)
