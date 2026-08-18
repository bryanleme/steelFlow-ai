"""Mandatory transparent and nonlinear model baselines."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class ConditionedMedianRegressor(RegressorMixin, BaseEstimator):
    """Median by available product/grade/line context with global fallback."""

    def __init__(self, group_columns: tuple[str, ...]) -> None:
        self.group_columns = group_columns

    def fit(self, X: pd.DataFrame, y: pd.Series) -> ConditionedMedianRegressor:
        self.global_median_ = float(np.median(np.asarray(y, dtype=float)))
        frame = X.loc[:, self.group_columns].copy()
        frame["__target"] = np.asarray(y, dtype=float)
        grouped = frame.groupby(list(self.group_columns), dropna=False)["__target"].median()
        self.lookup_ = {
            key if isinstance(key, tuple) else (key,): float(value)
            for key, value in grouped.items()
        }
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.group_columns:
            return np.full(len(X), self.global_median_, dtype=float)
        keys = X.loc[:, self.group_columns].itertuples(index=False, name=None)
        return np.fromiter(
            (self.lookup_.get(tuple(key), self.global_median_) for key in keys),
            dtype=float,
            count=len(X),
        )


class ConditionedRateClassifier(ClassifierMixin, BaseEstimator):
    """Smoothed event rate by context with global fallback."""

    def __init__(self, group_columns: tuple[str, ...], smoothing: float = 20.0) -> None:
        self.group_columns = group_columns
        self.smoothing = smoothing

    def fit(self, X: pd.DataFrame, y: pd.Series) -> ConditionedRateClassifier:
        values = np.asarray(y, dtype=int)
        self.classes_ = np.array([0, 1], dtype=int)
        self.global_rate_ = float(values.mean())
        frame = X.loc[:, self.group_columns].copy()
        frame["__target"] = values
        grouped = frame.groupby(list(self.group_columns), dropna=False)["__target"].agg(
            ["sum", "count"]
        )
        rates = (grouped["sum"] + self.smoothing * self.global_rate_) / (
            grouped["count"] + self.smoothing
        )
        self.lookup_ = {
            key if isinstance(key, tuple) else (key,): float(value)
            for key, value in rates.items()
        }
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if not self.group_columns:
            positive = np.full(len(X), self.global_rate_, dtype=float)
        else:
            keys = X.loc[:, self.group_columns].itertuples(index=False, name=None)
            positive = np.fromiter(
                (self.lookup_.get(tuple(key), self.global_rate_) for key in keys),
                dtype=float,
                count=len(X),
            )
        return np.column_stack([1.0 - positive, positive])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _preprocessor(
    columns: list[str],
    categorical_features: tuple[str, ...],
    *,
    scale: bool,
) -> ColumnTransformer:
    categorical = [column for column in categorical_features if column in columns]
    numeric = [column for column in columns if column not in categorical]
    numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        numeric_steps.append(("scaler", StandardScaler()))
    return ColumnTransformer(
        [
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("one_hot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
            ("numeric", Pipeline(numeric_steps), numeric),
        ],
        remainder="drop",
    )


def regression_baselines(
    X: pd.DataFrame,
    categorical_features: tuple[str, ...],
    *,
    random_seed: int,
    forest_estimators: int,
    forest_max_depth: int,
) -> dict[str, Any]:
    groups = tuple(
        column for column in ("product_code", "grade_family", "line_id") if column in X.columns
    )
    return {
        "global_median": DummyRegressor(strategy="median"),
        "conditioned_median": ConditionedMedianRegressor(groups),
        "ridge": Pipeline(
            [
                ("preprocessor", _preprocessor(list(X.columns), categorical_features, scale=True)),
                ("model", Ridge(alpha=10.0)),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocessor", _preprocessor(list(X.columns), categorical_features, scale=False)),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=forest_estimators,
                        max_depth=forest_max_depth,
                        min_samples_leaf=10,
                        n_jobs=-1,
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
    }


def classification_baselines(
    X: pd.DataFrame,
    categorical_features: tuple[str, ...],
    *,
    random_seed: int,
    forest_estimators: int,
    forest_max_depth: int,
) -> dict[str, Any]:
    groups = tuple(
        column for column in ("product_code", "grade_family", "line_id") if column in X.columns
    )
    return {
        "global_prior": DummyClassifier(strategy="prior"),
        "conditioned_rate": ConditionedRateClassifier(groups),
        "logistic_regression": Pipeline(
            [
                ("preprocessor", _preprocessor(list(X.columns), categorical_features, scale=True)),
                (
                    "model",
                    LogisticRegression(
                        C=0.5,
                        max_iter=500,
                        class_weight="balanced",
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocessor", _preprocessor(list(X.columns), categorical_features, scale=False)),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=forest_estimators,
                        max_depth=forest_max_depth,
                        min_samples_leaf=10,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
    }


def positive_probability(model: Any, X: pd.DataFrame) -> np.ndarray:
    probabilities = np.asarray(model.predict_proba(X), dtype=float)
    classes = np.asarray(getattr(model, "classes_", [0, 1]))
    matches = np.flatnonzero(classes == 1)
    if not len(matches):
        return np.zeros(len(X), dtype=float)
    return probabilities[:, int(matches[0])]
