"""Frozen-model inference and a leakage-safe controllable throughput surrogate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from steelflow.features.contracts import FeatureContract
from steelflow.models.baselines import positive_probability
from steelflow.models.data import SnapshotData, split_positions
from steelflow.models.metrics import quantile_metrics, regression_metrics
from steelflow.optimization.contracts import OptimizationConfig
from steelflow.optimization.envelope import HistoricalEnvelope

CONSTRAINT_COLUMNS = (
    "historical_distance",
    "quality_failure_probability",
    "downtime_probability",
    "expected_downtime_minutes",
    "throughput_interval_width",
    "energy_interval_width",
    "outer_diameter_deviation",
    "wall_eccentricity",
    "ovality",
)


def prepare_catboost(frame: pd.DataFrame, categorical: tuple[str, ...]) -> pd.DataFrame:
    prepared = frame.copy()
    for column in categorical:
        if column in prepared:
            prepared[column] = prepared[column].fillna("__MISSING__").astype(str)
    return prepared


@dataclass(frozen=True)
class ThroughputSurrogate:
    point_model: Any
    quantile_model: Any
    categorical_features: tuple[str, ...]
    metrics: dict[str, Any]


def train_throughput_surrogate(
    data: SnapshotData,
    assignments: pd.DataFrame,
    config: OptimizationConfig,
) -> ThroughputSurrogate:
    """Fit only on train, tune by early stopping, assess only on calibration."""

    train = split_positions(assignments, "train")
    tuning = split_positions(assignments, "tuning")
    calibration = split_positions(assignments, "calibration")
    X_train = prepare_catboost(data.X.iloc[train], data.categorical_features)
    X_tuning = prepare_catboost(data.X.iloc[tuning], data.categorical_features)
    X_calibration = prepare_catboost(data.X.iloc[calibration], data.categorical_features)
    y_train = data.y.iloc[train]["actual_tph"].astype(float)
    y_tuning = data.y.iloc[tuning]["actual_tph"].astype(float)
    y_calibration = data.y.iloc[calibration]["actual_tph"].astype(float)
    categorical = [column for column in data.categorical_features if column in X_train]
    common = {
        "iterations": config.surrogate.iterations,
        "depth": config.surrogate.depth,
        "learning_rate": config.surrogate.learning_rate,
        "random_seed": config.random_seed,
        "allow_writing_files": False,
        "verbose": False,
        "thread_count": 1,
    }
    point = CatBoostRegressor(loss_function="MAE", eval_metric="MAE", **common)
    point.fit(
        X_train,
        y_train,
        cat_features=categorical,
        eval_set=(X_tuning, y_tuning),
        early_stopping_rounds=config.surrogate.early_stopping_rounds,
        use_best_model=True,
    )
    quantile = CatBoostRegressor(
        loss_function="MultiQuantile:alpha=0.1,0.5,0.9",
        eval_metric="MultiQuantile:alpha=0.1,0.5,0.9",
        **common,
    )
    quantile.fit(
        X_train,
        y_train,
        cat_features=categorical,
        eval_set=(X_tuning, y_tuning),
        early_stopping_rounds=config.surrogate.early_stopping_rounds,
        use_best_model=True,
    )
    point_prediction = np.asarray(point.predict(X_calibration), dtype=float)
    quantile_prediction = np.asarray(quantile.predict(X_calibration), dtype=float)
    metrics = {
        "fit_splits": ["train", "tuning_for_early_stopping"],
        "assessed_split": "calibration",
        "final_test_labels_used": False,
        "train_rows": len(train),
        "tuning_rows": len(tuning),
        "calibration_rows": len(calibration),
        "point": regression_metrics(y_calibration, point_prediction),
        "quantiles": quantile_metrics(y_calibration, quantile_prediction),
        "point_best_iteration": int(point.get_best_iteration()),
        "quantile_best_iteration": int(quantile.get_best_iteration()),
    }
    return ThroughputSurrogate(point, quantile, data.categorical_features, metrics)


def save_throughput_surrogate(surrogate: ThroughputSurrogate, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    joblib.dump(surrogate.point_model, root / "actual_tph_point.joblib", compress=3)
    joblib.dump(surrogate.quantile_model, root / "actual_tph_quantiles.joblib", compress=3)
    (root / "metrics.json").write_text(
        json.dumps(surrogate.metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class AssetEstimate:
    sample_key: str
    context: dict[str, Any]
    downtime_probability: float
    duration_p10: float
    duration_p50: float
    duration_p90: float

    @property
    def expected_downtime_minutes(self) -> float:
        return self.downtime_probability * self.duration_p50


class ScenarioPredictor:
    """Evaluate scenarios without changing their fixed operational context."""

    def __init__(
        self,
        *,
        model_root: Path,
        feature_contract: FeatureContract,
        surrogate: ThroughputSurrogate,
        config: OptimizationConfig,
    ) -> None:
        self.model_root = model_root
        self.config = config
        self.rolling_categorical = tuple(
            feature.name
            for feature in feature_contract.snapshot("in_process_rolling").features
            if feature.dtype == "category"
        )
        self.asset_categorical = tuple(
            feature.name
            for feature in feature_contract.snapshot("asset_window").features
            if feature.dtype == "category"
        )
        self.surrogate = surrogate
        self.models = {
            name: self._load_model(name, quantile=True)
            for name in (
                "energy_intensity",
                "outer_diameter_deviation",
                "wall_eccentricity",
                "ovality",
                "downtime_duration",
            )
        }
        self.models.update(
            {
                name: self._load_model(name, calibrated=True)
                for name in ("quality_failure", "downtime_occurrence")
            }
        )

    def _load_model(
        self,
        name: str,
        *,
        quantile: bool = False,
        calibrated: bool = False,
    ) -> Any:
        task_root = self.model_root / "models" / name
        manifest = json.loads((task_root / "task_manifest.json").read_text(encoding="utf-8"))
        key = "quantile_file" if quantile else "calibrated_file" if calibrated else "catboost_file"
        filename = manifest.get(key)
        if not filename:
            raise ValueError(f"frozen model {name!r} does not provide {key}")
        return joblib.load(task_root / filename)

    @staticmethod
    def _ordered_quantiles(model: Any, frame: pd.DataFrame) -> np.ndarray:
        prediction = np.asarray(model.predict(frame), dtype=float)
        if prediction.ndim != 2 or prediction.shape[1] != 3:
            raise ValueError("expected P10/P50/P90 predictions")
        return np.sort(prediction, axis=1)

    def estimate_asset_rows(
        self,
        X: pd.DataFrame,
        sample_keys: pd.Series,
    ) -> pd.DataFrame:
        prepared = prepare_catboost(X, self.asset_categorical)
        probability = positive_probability(self.models["downtime_occurrence"], prepared)
        duration = self._ordered_quantiles(self.models["downtime_duration"], prepared)
        return pd.DataFrame(
            {
                "sample_key": sample_keys.astype(str).to_numpy(),
                "downtime_probability": probability,
                "duration_p10": duration[:, 0],
                "duration_p50": duration[:, 1],
                "duration_p90": duration[:, 2],
                "expected_downtime_minutes": probability * duration[:, 1],
            },
            index=X.index,
        )

    def evaluate(
        self,
        values: np.ndarray,
        *,
        current: pd.Series,
        envelope: HistoricalEnvelope,
        asset: AssetEstimate,
    ) -> pd.DataFrame:
        matrix = np.atleast_2d(np.asarray(values, dtype=float))
        frame = pd.DataFrame(
            np.repeat(current.to_numpy()[None, :], len(matrix), axis=0),
            columns=current.index,
        )
        frame.loc[:, list(envelope.controllables)] = matrix
        prepared = prepare_catboost(frame, self.rolling_categorical)
        throughput = self._ordered_quantiles(self.surrogate.quantile_model, prepared)
        energy = self._ordered_quantiles(self.models["energy_intensity"], prepared)
        diameter = self._ordered_quantiles(
            self.models["outer_diameter_deviation"], prepared
        )
        eccentricity = self._ordered_quantiles(self.models["wall_eccentricity"], prepared)
        ovality = self._ordered_quantiles(self.models["ovality"], prepared)
        failure_probability = positive_probability(self.models["quality_failure"], prepared)
        ood = envelope.assess(matrix)
        result = pd.DataFrame(
            {
                "throughput_p10": throughput[:, 0],
                "throughput_p50": throughput[:, 1],
                "throughput_p90": throughput[:, 2],
                "quality_failure_probability": failure_probability,
                "estimated_fpy": 1.0 - failure_probability,
                "estimated_tbh_proxy": throughput[:, 1] * (1.0 - failure_probability),
                "energy_p10": energy[:, 0],
                "energy_p50": energy[:, 1],
                "energy_p90": energy[:, 2],
                "outer_diameter_deviation_p10": diameter[:, 0],
                "outer_diameter_deviation_p50": diameter[:, 1],
                "outer_diameter_deviation_p90": diameter[:, 2],
                "wall_eccentricity_p10": eccentricity[:, 0],
                "wall_eccentricity_p50": eccentricity[:, 1],
                "wall_eccentricity_p90": eccentricity[:, 2],
                "ovality_p10": ovality[:, 0],
                "ovality_p50": ovality[:, 1],
                "ovality_p90": ovality[:, 2],
                "downtime_probability": asset.downtime_probability,
                "downtime_duration_p10": asset.duration_p10,
                "downtime_duration_p50": asset.duration_p50,
                "downtime_duration_p90": asset.duration_p90,
                "expected_downtime_minutes": asset.expected_downtime_minutes,
                "throughput_interval_width": throughput[:, 2] - throughput[:, 0],
                "energy_interval_width": energy[:, 2] - energy[:, 0],
                "historical_distance": ood["historical_distance"].to_numpy(),
                "distance_threshold": ood["distance_threshold"].to_numpy(),
                "distance_ratio": ood["distance_ratio"].to_numpy(),
                "within_conditional_bounds": ood["within_conditional_bounds"].to_numpy(),
                "in_distribution": ood["in_distribution"].to_numpy(),
            }
        )
        limits = self.config.constraints
        result["constraint_historical_distance"] = result["distance_ratio"] - 1.0
        result["constraint_quality_failure_probability"] = (
            result["quality_failure_probability"] - limits.max_quality_failure_probability
        )
        result["constraint_downtime_probability"] = (
            result["downtime_probability"] - limits.max_downtime_probability
        )
        result["constraint_expected_downtime_minutes"] = (
            result["expected_downtime_minutes"] - limits.max_expected_downtime_minutes
        )
        result["constraint_throughput_interval_width"] = (
            result["throughput_interval_width"] - limits.max_throughput_interval_width
        )
        result["constraint_energy_interval_width"] = (
            result["energy_interval_width"] - limits.max_energy_interval_width
        )
        max_abs_diameter = np.maximum(
            np.abs(result["outer_diameter_deviation_p10"]),
            np.abs(result["outer_diameter_deviation_p90"]),
        )
        result["constraint_outer_diameter_deviation"] = (
            max_abs_diameter - limits.max_abs_outer_diameter_deviation_mm
        )
        result["constraint_wall_eccentricity"] = (
            result["wall_eccentricity_p90"] - limits.max_wall_eccentricity_pct
        )
        result["constraint_ovality"] = result["ovality_p90"] - limits.max_ovality_pct
        constraint_columns = [f"constraint_{name}" for name in CONSTRAINT_COLUMNS]
        result["hard_constraints_pass"] = (
            result[constraint_columns].max(axis=1) <= 1e-9
        ) & result["within_conditional_bounds"]
        return result

    @staticmethod
    def objectives(evaluation: pd.DataFrame) -> np.ndarray:
        return np.column_stack(
            [
                -evaluation["estimated_tbh_proxy"],
                evaluation["quality_failure_probability"],
                evaluation["energy_p50"],
                evaluation["downtime_probability"],
                evaluation["expected_downtime_minutes"],
            ]
        )

    @staticmethod
    def constraints(evaluation: pd.DataFrame) -> np.ndarray:
        return evaluation[[f"constraint_{name}" for name in CONSTRAINT_COLUMNS]].to_numpy()
