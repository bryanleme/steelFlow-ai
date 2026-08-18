"""Evaluation metrics for regression, uncertainty and rare-event classification."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    mean_absolute_error,
    mean_pinball_loss,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


def expected_calibration_error(
    y_true: np.ndarray,
    probability: np.ndarray,
    *,
    bins: int = 10,
) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    bucket = np.clip(np.digitize(probability, edges[1:-1], right=False), 0, bins - 1)
    error = 0.0
    for index in range(bins):
        mask = bucket == index
        if mask.any():
            error += float(mask.mean()) * abs(
                float(np.mean(y_true[mask])) - float(np.mean(probability[mask]))
            )
    return float(error)


def regression_metrics(y_true: Any, prediction: Any) -> dict[str, float]:
    observed = np.asarray(y_true, dtype=float)
    predicted = np.asarray(prediction, dtype=float)
    residual = observed - predicted
    return {
        "mae": float(mean_absolute_error(observed, predicted)),
        "rmse": float(math.sqrt(np.mean(np.square(residual)))),
        "r2": float(r2_score(observed, predicted)),
    }


def quantile_metrics(y_true: Any, quantiles: Any) -> dict[str, float]:
    observed = np.asarray(y_true, dtype=float)
    predicted = np.asarray(quantiles, dtype=float)
    if predicted.ndim != 2 or predicted.shape[1] != 3:
        raise ValueError("quantile predictions must have columns P10, P50 and P90")
    p10, p50, p90 = predicted.T
    return {
        "pinball_p10": float(mean_pinball_loss(observed, p10, alpha=0.1)),
        "pinball_p50": float(mean_pinball_loss(observed, p50, alpha=0.5)),
        "pinball_p90": float(mean_pinball_loss(observed, p90, alpha=0.9)),
        "empirical_coverage_80": float(np.mean((observed >= p10) & (observed <= p90))),
        "coverage_error_abs": float(abs(np.mean((observed >= p10) & (observed <= p90)) - 0.8)),
        "mean_interval_width": float(np.mean(p90 - p10)),
        "p50_mae": float(mean_absolute_error(observed, p50)),
    }


def classification_metrics(
    y_true: Any,
    probability: Any,
    *,
    alert_budgets: tuple[float, ...],
) -> dict[str, float | int]:
    observed = np.asarray(y_true, dtype=int)
    probability_array = np.clip(np.asarray(probability, dtype=float), 1e-12, 1 - 1e-12)
    predicted = (probability_array >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(observed, predicted, labels=[0, 1]).ravel()
    metrics: dict[str, float | int] = {
        "prevalence": float(observed.mean()),
        "pr_auc": float(average_precision_score(observed, probability_array)),
        "log_loss": float(log_loss(observed, probability_array, labels=[0, 1])),
        "brier": float(brier_score_loss(observed, probability_array)),
        "ece_10": expected_calibration_error(observed, probability_array),
        "precision_at_0_5": float(precision_score(observed, predicted, zero_division=0)),
        "recall_at_0_5": float(recall_score(observed, predicted, zero_division=0)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }
    try:
        metrics["roc_auc"] = float(roc_auc_score(observed, probability_array))
    except ValueError:
        metrics["roc_auc"] = float("nan")
    order = np.argsort(-probability_array, kind="stable")
    positive_total = max(1, int(observed.sum()))
    for budget in alert_budgets:
        count = max(1, math.ceil(len(observed) * budget))
        selected = observed[order[:count]]
        suffix = str(int(round(budget * 100))).zfill(2)
        metrics[f"recall_at_alert_budget_{suffix}pct"] = float(selected.sum() / positive_total)
        metrics[f"precision_at_alert_budget_{suffix}pct"] = float(selected.mean())
    return metrics


def segment_records(
    *,
    task_name: str,
    model_name: str,
    problem_type: str,
    y_true: pd.Series,
    prediction: np.ndarray,
    X: pd.DataFrame,
    snapshot_ts: pd.Series,
    min_rows: int,
    alert_budgets: tuple[float, ...],
) -> list[dict[str, Any]]:
    segments = pd.DataFrame(index=np.arange(len(X)))
    for column in ("product_code", "grade_family", "line_id"):
        if column in X.columns:
            segments[column] = X[column].astype(str).to_numpy()
    segments["month"] = pd.to_datetime(snapshot_ts, utc=True).dt.strftime("%Y-%m").to_numpy()
    wear_column = next(
        (column for column in ("tool_wear_index", "prior_mean_tool_wear") if column in X.columns),
        None,
    )
    if wear_column:
        segments["wear_band"] = pd.cut(
            X[wear_column].astype(float),
            bins=[-np.inf, 0.25, 0.50, 0.75, np.inf],
            labels=["low", "moderate", "high", "very_high"],
        ).astype(str)

    records: list[dict[str, Any]] = []
    observed = pd.Series(np.asarray(y_true), index=segments.index)
    predicted = np.asarray(prediction)
    for segment_name in segments.columns:
        for segment_value, positions in segments.groupby(segment_name, dropna=False).groups.items():
            indices = np.asarray(list(positions), dtype=int)
            if len(indices) < min_rows:
                continue
            if problem_type == "classification" and observed.iloc[indices].nunique() < 2:
                continue
            metric_values = (
                regression_metrics(observed.iloc[indices], predicted[indices])
                if problem_type == "regression"
                else classification_metrics(
                    observed.iloc[indices], predicted[indices], alert_budgets=alert_budgets
                )
            )
            records.append(
                {
                    "task": task_name,
                    "model": model_name,
                    "segment": segment_name,
                    "segment_value": str(segment_value),
                    "rows": int(len(indices)),
                    **metric_values,
                }
            )
    return records
