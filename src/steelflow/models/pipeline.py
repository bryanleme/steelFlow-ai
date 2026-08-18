"""Chronological baseline, CatBoost, calibration, uncertainty and SHAP pipeline."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor, Pool
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

from steelflow.config import ProjectConfigBundle
from steelflow.features.contracts import FeatureContract, load_feature_contract
from steelflow.generation.manifest import dependency_versions, utc_now, write_manifest
from steelflow.generation.writer import sha256_file
from steelflow.models.baselines import (
    classification_baselines,
    positive_probability,
    regression_baselines,
)
from steelflow.models.contracts import ModelingConfig, ModelTask, load_modeling_config
from steelflow.models.data import (
    SnapshotData,
    build_temporal_assignments,
    expanding_backtest_positions,
    load_snapshot,
    resolve_feature_root,
    split_positions,
)
from steelflow.models.metrics import (
    classification_metrics,
    quantile_metrics,
    regression_metrics,
    segment_records,
)


class ModelPipelineError(RuntimeError):
    """Raised when temporal model training or evaluation cannot complete safely."""


@dataclass(frozen=True)
class TrainingResult:
    simulation_run_id: str
    model_root: Path
    manifest_path: Path
    task_count: int
    elapsed_seconds: float


@dataclass(frozen=True)
class EvaluationResult:
    simulation_run_id: str
    model_root: Path
    evaluation_path: Path
    task_count: int
    engineering_goal_met: bool
    recovered_mechanisms: int
    reused: bool
    elapsed_seconds: float


def _safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise ModelPipelineError(f"refusing to remove path outside model parent: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _ml_dependencies() -> dict[str, str]:
    versions = dependency_versions()
    for package in ("catboost", "joblib", "scikit-learn", "shap"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _model_directory_name(
    simulation_run_id: str,
    modeling: ModelingConfig,
) -> str:
    return f"{simulation_run_id}-models-v{modeling.model_version}-{modeling.stable_hash()[:12]}"


def resolve_model_root(
    bundle: ProjectConfigBundle,
    project_root: Path,
    modeling: ModelingConfig,
    feature_contract: FeatureContract,
) -> tuple[Path, Path]:
    feature_root = resolve_feature_root(bundle, feature_contract, project_root)
    feature_manifest = json.loads(
        (feature_root / "feature_manifest.json").read_text(encoding="utf-8")
    )
    simulation_run_id = str(feature_manifest["simulation_run_id"])
    model_root = (
        project_root
        / "data"
        / "model_outputs"
        / bundle.simulation.profile.value
        / _model_directory_name(simulation_run_id, modeling)
    )
    return feature_root, model_root


def _prepare_catboost(X: pd.DataFrame, categorical: tuple[str, ...]) -> pd.DataFrame:
    prepared = X.copy()
    for column in categorical:
        if column in prepared:
            prepared[column] = prepared[column].fillna("__MISSING__").astype(str)
    return prepared


def _task_positions(
    data: SnapshotData,
    assignments: pd.DataFrame,
    task: ModelTask,
    split_name: str,
) -> np.ndarray:
    positions = split_positions(assignments, split_name)
    target_observed = data.y.iloc[positions][task.target].notna().to_numpy()
    positions = positions[target_observed]
    if task.positive_filter:
        positive = data.y.iloc[positions][task.positive_filter].astype(bool).to_numpy()
        positions = positions[positive]
    return positions


def _task_xy(
    data: SnapshotData,
    positions: np.ndarray,
    task: ModelTask,
) -> tuple[pd.DataFrame, pd.Series]:
    X = data.X.iloc[positions].reset_index(drop=True)
    y = data.y.iloc[positions][task.target].reset_index(drop=True)
    if task.invert_target:
        y = ~y.astype(bool)
    y = y.astype(int) if task.problem_type == "classification" else y.astype(float)
    return X, y


def _catboost_regressor(
    modeling: ModelingConfig,
    *,
    iterations: int | None = None,
    loss_function: str = "RMSE",
    depth: int | None = None,
    learning_rate: float | None = None,
) -> CatBoostRegressor:
    training = modeling.training
    return CatBoostRegressor(
        iterations=iterations or training.iterations,
        depth=depth or training.depth,
        learning_rate=learning_rate or training.learning_rate,
        loss_function=loss_function,
        eval_metric="MAE" if loss_function == "RMSE" else loss_function,
        random_seed=modeling.random_seed,
        allow_writing_files=False,
        verbose=False,
        thread_count=-1,
    )


def _catboost_classifier(
    modeling: ModelingConfig,
    *,
    iterations: int | None = None,
) -> CatBoostClassifier:
    training = modeling.training
    return CatBoostClassifier(
        iterations=iterations or training.iterations,
        depth=training.depth,
        learning_rate=training.learning_rate,
        loss_function="Logloss",
        eval_metric="AUC",
        auto_class_weights="Balanced",
        random_seed=modeling.random_seed,
        allow_writing_files=False,
        verbose=False,
        thread_count=-1,
    )


def _fit_catboost(
    task: ModelTask,
    modeling: ModelingConfig,
    data: SnapshotData,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_tuning: pd.DataFrame,
    y_tuning: pd.Series,
    *,
    iterations: int | None = None,
) -> Any:
    categorical = [column for column in data.categorical_features if column in X_train.columns]
    train_frame = _prepare_catboost(X_train, data.categorical_features)
    tuning_frame = _prepare_catboost(X_tuning, data.categorical_features)
    model = (
        _catboost_regressor(
            modeling,
            iterations=iterations or task.iterations_override,
            loss_function=task.point_loss,
            depth=task.depth_override,
            learning_rate=task.learning_rate_override,
        )
        if task.problem_type == "regression"
        else _catboost_classifier(modeling, iterations=iterations)
    )
    model.fit(
        train_frame,
        y_train,
        cat_features=categorical,
        eval_set=(tuning_frame, y_tuning),
        early_stopping_rounds=modeling.training.early_stopping_rounds,
        use_best_model=True,
    )
    return model


def _fit_quantile_model(
    modeling: ModelingConfig,
    data: SnapshotData,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_tuning: pd.DataFrame,
    y_tuning: pd.Series,
) -> CatBoostRegressor:
    categorical = [column for column in data.categorical_features if column in X_train.columns]
    model = _catboost_regressor(
        modeling,
        loss_function="MultiQuantile:alpha=0.1,0.5,0.9",
    )
    model.fit(
        _prepare_catboost(X_train, data.categorical_features),
        y_train,
        cat_features=categorical,
        eval_set=(_prepare_catboost(X_tuning, data.categorical_features), y_tuning),
        early_stopping_rounds=modeling.training.early_stopping_rounds,
        use_best_model=True,
    )
    return model


def _metric_record(
    task: ModelTask,
    model_name: str,
    split_name: str,
    rows: int,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": task.name,
        "snapshot": task.snapshot,
        "problem_type": task.problem_type,
        "model": model_name,
        "split": split_name,
        "rows": int(rows),
        **metrics,
    }


def _write_training_card(
    path: Path,
    task: ModelTask,
    tuning_records: list[dict[str, Any]],
    *,
    calibrated: bool,
) -> None:
    main = next(record for record in tuning_records if record["model"] == "catboost")
    calibration_text = (
        "Platt em `calibration`" if calibrated else "calibração reservada sem ajuste do ponto"
    )
    uncertainty_text = (
        'Probabilidade calibrada por `CalibratedClassifierCV(method="sigmoid")`.'
        if calibrated
        else "P10/P50/P90 por CatBoost MultiQuantile quando contratado."
    )
    primary = (
        f"MAE={main['mae']:.6f}; RMSE={main['rmse']:.6f}; R²={main['r2']:.6f}"
        if task.problem_type == "regression"
        else (
            f"PR-AUC={main['pr_auc']:.6f}; ROC-AUC={main['roc_auc']:.6f}; "
            f"Brier={main['brier']:.6f}"
        )
    )
    content = f"""# Model card — {task.name}

## Uso pretendido

Predição `{task.problem_type}` no snapshot `{task.snapshot}` para o alvo sintético
`{task.target}` ({task.unit}). Apoio educacional offline; não controla equipamentos.

## Dados e temporalidade

Features point-in-time v1.0.0. Ajuste apenas na janela `train`, seleção/early stopping
em `tuning` e {calibration_text}.
O teste final não foi consultado durante o treinamento.

## Resultado de tuning

CatBoost: {primary}.

## Incerteza e explicabilidade

{uncertainty_text}
TreeSHAP é calculado somente após o congelamento do modelo.

## Limitações

Dados exclusivamente sintéticos; associações e desempenho não representam uma usina real.
Requer validação externa, monitoramento de drift e aprovação humana antes de qualquer uso real.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _train_backtests(
    *,
    task: ModelTask,
    modeling: ModelingConfig,
    data: SnapshotData,
    assignments: pd.DataFrame,
) -> list[dict[str, Any]]:
    if not task.backtest:
        return []
    records: list[dict[str, Any]] = []
    for fold_number, (train_positions, validation_positions) in enumerate(
        expanding_backtest_positions(assignments, modeling.splits.backtest_folds),
        start=1,
    ):
        if task.positive_filter:
            train_positions = train_positions[
                data.y.iloc[train_positions][task.positive_filter].astype(bool).to_numpy()
            ]
            validation_positions = validation_positions[
                data.y.iloc[validation_positions][task.positive_filter].astype(bool).to_numpy()
            ]
        X_train, y_train = _task_xy(data, train_positions, task)
        X_validation, y_validation = _task_xy(data, validation_positions, task)
        model = _fit_catboost(
            task,
            modeling,
            data,
            X_train,
            y_train,
            X_validation,
            y_validation,
            iterations=modeling.training.backtest_iterations,
        )
        validation_frame = _prepare_catboost(X_validation, data.categorical_features)
        if task.problem_type == "regression":
            metric_values = regression_metrics(y_validation, model.predict(validation_frame))
        else:
            metric_values = classification_metrics(
                y_validation,
                model.predict_proba(validation_frame)[:, 1],
                alert_budgets=modeling.training.alert_budgets,
            )
        records.append(
            {
                "task": task.name,
                "fold": fold_number,
                "train_rows": len(train_positions),
                "validation_rows": len(validation_positions),
                "train_end": data.index.iloc[train_positions]["snapshot_ts"].max(),
                "validation_start": data.index.iloc[validation_positions]["snapshot_ts"].min(),
                "validation_end": data.index.iloc[validation_positions]["snapshot_ts"].max(),
                **metric_values,
            }
        )
    return records


def train_models(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    overwrite: bool = False,
) -> TrainingResult:
    """Train without evaluating or selecting against the final-test labels."""

    timer_start = time.perf_counter()
    started_at = utc_now()
    root = project_root.resolve()
    feature_contract = load_feature_contract(root)
    modeling = load_modeling_config(root)
    feature_root, final_root = resolve_model_root(bundle, root, modeling, feature_contract)
    feature_manifest = json.loads(
        (feature_root / "feature_manifest.json").read_text(encoding="utf-8")
    )
    simulation_run_id = str(feature_manifest["simulation_run_id"])
    parent = final_root.parent
    staging_root = parent / f".{final_root.name}.staging"
    parent.mkdir(parents=True, exist_ok=True)
    if final_root.exists() and not overwrite:
        raise ModelPipelineError(f"model run already exists: {final_root}; use --force")
    if overwrite:
        _safe_remove_tree(final_root, parent)
    _safe_remove_tree(staging_root, parent)
    staging_root.mkdir(parents=True, exist_ok=False)

    split_config = modeling.splits
    fractions = (
        split_config.train_fraction,
        split_config.tuning_fraction,
        split_config.calibration_fraction,
        split_config.final_test_fraction,
    )
    snapshot_cache: dict[str, SnapshotData] = {}
    assignments_by_snapshot: dict[str, pd.DataFrame] = {}
    split_manifest: dict[str, Any] = {}
    tuning_records: list[dict[str, Any]] = []
    calibration_records: list[dict[str, Any]] = []
    backtest_records: list[dict[str, Any]] = []
    task_manifest: dict[str, Any] = {}
    try:
        for snapshot_name in ("pre_order", "in_process_rolling", "asset_window"):
            data = load_snapshot(feature_root, feature_contract, snapshot_name)
            assignments, boundaries = build_temporal_assignments(
                data.index,
                data.y["target_available_at_ts"],
                fractions,
            )
            snapshot_cache[snapshot_name] = data
            assignments_by_snapshot[snapshot_name] = assignments
            split_path = staging_root / "splits" / f"{snapshot_name}.parquet"
            split_path.parent.mkdir(parents=True, exist_ok=True)
            assignments.to_parquet(split_path, index=False)
            split_manifest[snapshot_name] = {
                "boundaries": boundaries,
                "counts": {
                    str(name): int(count)
                    for name, count in assignments["split"].value_counts().sort_index().items()
                },
                "path": split_path.relative_to(staging_root).as_posix(),
                "sha256": sha256_file(split_path),
            }

        for task in modeling.tasks:
            data = snapshot_cache[task.snapshot]
            assignments = assignments_by_snapshot[task.snapshot]
            train_positions = _task_positions(data, assignments, task, "train")
            tuning_positions = _task_positions(data, assignments, task, "tuning")
            calibration_positions = _task_positions(data, assignments, task, "calibration")
            X_train, y_train = _task_xy(data, train_positions, task)
            X_tuning, y_tuning = _task_xy(data, tuning_positions, task)
            X_calibration, y_calibration = _task_xy(data, calibration_positions, task)
            if task.problem_type == "classification" and (
                y_train.nunique() < 2 or y_tuning.nunique() < 2 or y_calibration.nunique() < 2
            ):
                raise ModelPipelineError(
                    f"task {task.name!r} lacks both classes in a required temporal window"
                )

            task_root = staging_root / "models" / task.name
            task_root.mkdir(parents=True, exist_ok=True)
            if task.problem_type == "regression":
                baselines = regression_baselines(
                    X_train,
                    data.categorical_features,
                    random_seed=modeling.random_seed,
                    forest_estimators=modeling.training.random_forest_estimators,
                    forest_max_depth=modeling.training.random_forest_max_depth,
                )
            else:
                baselines = classification_baselines(
                    X_train,
                    data.categorical_features,
                    random_seed=modeling.random_seed,
                    forest_estimators=modeling.training.random_forest_estimators,
                    forest_max_depth=modeling.training.random_forest_max_depth,
                )
            baseline_names: list[str] = []
            task_records: list[dict[str, Any]] = []
            for name, baseline in baselines.items():
                baseline.fit(X_train, y_train)
                joblib.dump(baseline, task_root / f"baseline_{name}.joblib", compress=3)
                baseline_names.append(name)
                prediction = (
                    baseline.predict(X_tuning)
                    if task.problem_type == "regression"
                    else positive_probability(baseline, X_tuning)
                )
                metric_values = (
                    regression_metrics(y_tuning, prediction)
                    if task.problem_type == "regression"
                    else classification_metrics(
                        y_tuning,
                        prediction,
                        alert_budgets=modeling.training.alert_budgets,
                    )
                )
                record = _metric_record(task, name, "tuning", len(y_tuning), metric_values)
                tuning_records.append(record)
                task_records.append(record)

            main_model = _fit_catboost(
                task,
                modeling,
                data,
                X_train,
                y_train,
                X_tuning,
                y_tuning,
            )
            joblib.dump(main_model, task_root / "catboost.joblib", compress=3)
            tuning_frame = _prepare_catboost(X_tuning, data.categorical_features)
            main_prediction = (
                main_model.predict(tuning_frame)
                if task.problem_type == "regression"
                else main_model.predict_proba(tuning_frame)[:, 1]
            )
            main_metrics = (
                regression_metrics(y_tuning, main_prediction)
                if task.problem_type == "regression"
                else classification_metrics(
                    y_tuning,
                    main_prediction,
                    alert_budgets=modeling.training.alert_budgets,
                )
            )
            main_record = _metric_record(task, "catboost", "tuning", len(y_tuning), main_metrics)
            tuning_records.append(main_record)
            task_records.append(main_record)

            quantile_file: str | None = None
            calibrated_file: str | None = None
            if task.quantiles:
                quantile_model = _fit_quantile_model(
                    modeling,
                    data,
                    X_train,
                    y_train,
                    X_tuning,
                    y_tuning,
                )
                quantile_file = "catboost_quantiles.joblib"
                joblib.dump(quantile_model, task_root / quantile_file, compress=3)
                quantile_prediction = quantile_model.predict(tuning_frame)
                quantile_record = _metric_record(
                    task,
                    "catboost_multiquantile",
                    "tuning",
                    len(y_tuning),
                    quantile_metrics(y_tuning, quantile_prediction),
                )
                tuning_records.append(quantile_record)
                task_records.append(quantile_record)
            if task.problem_type == "classification":
                calibration_frame = _prepare_catboost(
                    X_calibration, data.categorical_features
                )
                uncalibrated = main_model.predict_proba(calibration_frame)[:, 1]
                calibration_records.append(
                    _metric_record(
                        task,
                        "catboost_uncalibrated",
                        "calibration",
                        len(y_calibration),
                        classification_metrics(
                            y_calibration,
                            uncalibrated,
                            alert_budgets=modeling.training.alert_budgets,
                        ),
                    )
                )
                calibrated = CalibratedClassifierCV(
                    FrozenEstimator(main_model),
                    method="sigmoid",
                )
                calibrated.fit(calibration_frame, y_calibration)
                calibrated_file = "catboost_calibrated_sigmoid.joblib"
                joblib.dump(calibrated, task_root / calibrated_file, compress=3)
                calibrated_probability = positive_probability(calibrated, calibration_frame)
                calibration_records.append(
                    _metric_record(
                        task,
                        "catboost_calibrated_sigmoid",
                        "calibration_fit_window",
                        len(y_calibration),
                        classification_metrics(
                            y_calibration,
                            calibrated_probability,
                            alert_budgets=modeling.training.alert_budgets,
                        ),
                    )
                )

            task_backtests = _train_backtests(
                task=task,
                modeling=modeling,
                data=data,
                assignments=assignments,
            )
            backtest_records.extend(task_backtests)
            task_manifest[task.name] = {
                **task.model_dump(mode="json"),
                "train_rows": len(train_positions),
                "tuning_rows": len(tuning_positions),
                "calibration_rows": len(calibration_positions),
                "baseline_models": baseline_names,
                "catboost_file": "catboost.joblib",
                "quantile_file": quantile_file,
                "calibrated_file": calibrated_file,
                "categorical_features": list(data.categorical_features),
                "best_iteration": int(main_model.get_best_iteration()),
                "point_loss": task.point_loss,
            }
            (task_root / "task_manifest.json").write_text(
                json.dumps(task_manifest[task.name], ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            _write_training_card(
                task_root / "MODEL_CARD.md",
                task,
                task_records,
                calibrated=task.problem_type == "classification",
            )

        metrics_root = staging_root / "metrics"
        metrics_root.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(tuning_records).to_parquet(metrics_root / "tuning.parquet", index=False)
        pd.DataFrame(calibration_records).to_parquet(
            metrics_root / "calibration.parquet", index=False
        )
        pd.DataFrame(backtest_records).to_parquet(
            metrics_root / "expanding_backtests.parquet", index=False
        )
        elapsed_seconds = time.perf_counter() - timer_start
        manifest = {
            "schema_version": "1.0",
            "status": "success",
            "simulation_run_id": simulation_run_id,
            "profile": bundle.simulation.profile.value,
            "model_version": modeling.model_version,
            "modeling_config_sha256": modeling.stable_hash(),
            "feature_contract_sha256": feature_contract.stable_hash(),
            "feature_manifest_sha256": sha256_file(feature_root / "feature_manifest.json"),
            "split_strategy": "four chronological windows with next-boundary label embargo",
            "splits": split_manifest,
            "tasks": task_manifest,
            "backtest_strategy": "three expanding folds wholly before calibration/final test",
            "calibration": "CalibratedClassifierCV sigmoid on exclusive calibration window",
            "final_test_labels_used": False,
            "final_evaluation_status": "pending",
            "started_at_utc": started_at.isoformat(),
            "finished_at_utc": utc_now().isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 6),
            "dependencies": _ml_dependencies(),
            "synthetic_scope": "offline synthetic prototype; no machine control",
        }
        write_manifest(staging_root / "training_manifest.json", manifest)
        staging_root.replace(final_root)
        return TrainingResult(
            simulation_run_id=simulation_run_id,
            model_root=final_root,
            manifest_path=final_root / "training_manifest.json",
            task_count=len(modeling.tasks),
            elapsed_seconds=elapsed_seconds,
        )
    except Exception as exc:
        _safe_remove_tree(staging_root, parent)
        if isinstance(exc, ModelPipelineError):
            raise
        raise ModelPipelineError(f"model training failed: {exc}") from exc


def _tree_shap_records(
    *,
    task: ModelTask,
    model: Any,
    data: SnapshotData,
    X: pd.DataFrame,
    y: pd.Series,
    sample_keys: pd.Series,
    prediction: np.ndarray,
    sample_size: int,
    scenario_count: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sample_count = min(sample_size, len(X))
    sample_positions = np.linspace(0, len(X) - 1, sample_count, dtype=int)
    sample = X.iloc[sample_positions].reset_index(drop=True)
    prepared = _prepare_catboost(sample, data.categorical_features)
    categorical = [column for column in data.categorical_features if column in prepared.columns]
    values = np.asarray(
        model.get_feature_importance(
            Pool(prepared, cat_features=categorical),
            type="ShapValues",
        )
    )
    if values.ndim == 3:
        values = values[:, 1, :]
    contributions = values[:, :-1]
    global_frame = pd.DataFrame(
        {
            "task": task.name,
            "feature": sample.columns,
            "mean_abs_shap": np.mean(np.abs(contributions), axis=0),
            "mean_shap": np.mean(contributions, axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False, ignore_index=True)
    global_frame["rank"] = np.arange(1, len(global_frame) + 1)

    segment_frames: list[pd.DataFrame] = []
    for segment in ("line_id", "grade_family", "product_code"):
        if segment not in sample.columns:
            continue
        for value, indices in sample.groupby(segment).groups.items():
            positions = np.asarray(list(indices), dtype=int)
            mean_abs = np.mean(np.abs(contributions[positions]), axis=0)
            order = np.argsort(-mean_abs, kind="stable")[:10]
            segment_frames.append(
                pd.DataFrame(
                    {
                        "task": task.name,
                        "segment": segment,
                        "segment_value": str(value),
                        "feature": sample.columns[order],
                        "mean_abs_shap": mean_abs[order],
                        "rank": np.arange(1, len(order) + 1),
                        "rows": len(positions),
                    }
                )
            )
    segment_frame = (
        pd.concat(segment_frames, ignore_index=True) if segment_frames else pd.DataFrame()
    )

    ranked = np.argsort(np.asarray(prediction), kind="stable")
    scenario_indices = ranked[
        np.linspace(0, len(ranked) - 1, min(scenario_count, len(ranked)), dtype=int)
    ]
    scenario_rows: list[dict[str, Any]] = []
    sampled_lookup = {original: position for position, original in enumerate(sample_positions)}
    for original in scenario_indices:
        if int(original) not in sampled_lookup:
            nearest = int(np.argmin(np.abs(sample_positions - int(original))))
        else:
            nearest = sampled_lookup[int(original)]
        top = np.argsort(-np.abs(contributions[nearest]), kind="stable")[:5]
        scenario_rows.append(
            {
                "task": task.name,
                "sample_key": str(sample_keys.iloc[int(original)]),
                "observed": float(y.iloc[int(original)]),
                "prediction": float(prediction[int(original)]),
                "base_value": float(values[nearest, -1]),
                "top_contributions_json": json.dumps(
                    [
                        {
                            "feature": str(sample.columns[index]),
                            "value": str(sample.iloc[nearest, index]),
                            "shap": float(contributions[nearest, index]),
                        }
                        for index in top
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return global_frame, segment_frame, pd.DataFrame(scenario_rows)


def _evaluation_card(
    path: Path,
    task: ModelTask,
    record: dict[str, Any],
) -> None:
    uncertainty_text = (
        "Classificador calibrado por Platt."
        if task.problem_type == "classification"
        else "Incerteza P10/P50/P90 disponível."
    )
    if task.problem_type == "regression":
        headline = f"MAE {record['mae']:.6f}; RMSE {record['rmse']:.6f}; R² {record['r2']:.6f}."
    else:
        headline = (
            f"PR-AUC {record['pr_auc']:.6f}; ROC-AUC {record['roc_auc']:.6f}; "
            f"log-loss {record['log_loss']:.6f}; Brier {record['brier']:.6f}; "
            f"ECE {record['ece_10']:.6f}."
        )
    content = f"""# Model card final — {task.name}

Modelo CatBoost para `{task.target}` no snapshot `{task.snapshot}`. Resultado no teste
cronológico final, consultado uma única vez: {headline}

Treino, tuning, calibração e teste são janelas distintas; transformações dos baselines
foram ajustadas dentro do treino. {uncertainty_text}
TreeSHAP explica o modelo base congelado; contribuição não implica causalidade.

Uso limitado a demonstração educacional offline com dados sintéticos. Não representa
desempenho industrial real, não é validado por norma e não deve operar máquinas.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _benchmark_frozen_inference(
    *,
    feature_root: Path,
    model_root: Path,
    modeling: ModelingConfig,
    batch_rows: int = 1000,
    repeats: int = 5,
) -> dict[str, Any]:
    """Measure serving prediction only; final-test labels are never loaded."""

    feature_cache: dict[str, pd.DataFrame] = {}
    records: list[dict[str, Any]] = []
    for task in modeling.tasks:
        if task.snapshot not in feature_cache:
            feature_cache[task.snapshot] = pd.read_parquet(
                feature_root / task.snapshot / "X.parquet"
            )
        assignments = pd.read_parquet(model_root / "splits" / f"{task.snapshot}.parquet")
        positions = assignments.loc[
            assignments["split"] == "final_test", "row_position"
        ].to_numpy(dtype=int)[:batch_rows]
        X = feature_cache[task.snapshot].iloc[positions].reset_index(drop=True)
        task_root = model_root / "models" / task.name
        task_manifest = json.loads(
            (task_root / "task_manifest.json").read_text(encoding="utf-8")
        )
        categorical = tuple(task_manifest["categorical_features"])
        prepared = _prepare_catboost(X, categorical)
        if task.problem_type == "classification":
            model = joblib.load(task_root / task_manifest["calibrated_file"])
        else:
            model = joblib.load(task_root / "catboost.joblib")
        if task.problem_type == "classification":
            positive_probability(model, prepared)
        else:
            model.predict(prepared)
        durations: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            if task.problem_type == "classification":
                positive_probability(model, prepared)
            else:
                model.predict(prepared)
            durations.append((time.perf_counter() - started) * 1000.0)
        median_ms = float(np.median(durations))
        records.append(
            {
                "task": task.name,
                "batch_rows": len(X),
                "repeats": repeats,
                "median_batch_ms": median_ms,
                "p95_batch_ms": float(np.percentile(durations, 95)),
                "median_per_row_ms": median_ms / len(X),
            }
        )
    return {
        "scope": "prediction only on final-test X; labels not loaded; warm-up excluded",
        "batch_rows": batch_rows,
        "repeats": repeats,
        "tasks": records,
    }


def evaluate_models(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    causal_auditor: Callable[..., dict[str, Any]],
) -> EvaluationResult:
    """Evaluate the frozen run once on the untouched chronological final test."""

    timer_start = time.perf_counter()
    root = project_root.resolve()
    feature_contract = load_feature_contract(root)
    modeling = load_modeling_config(root)
    feature_root, model_root = resolve_model_root(bundle, root, modeling, feature_contract)
    training_manifest_path = model_root / "training_manifest.json"
    if not training_manifest_path.is_file():
        raise ModelPipelineError("trained model run not found; run `train` first")
    training_manifest = json.loads(training_manifest_path.read_text(encoding="utf-8"))
    if training_manifest.get("final_test_labels_used") is not False:
        raise ModelPipelineError("training manifest does not prove final-test isolation")
    evaluation_root = model_root / "evaluation"
    evaluation_manifest_path = evaluation_root / "evaluation_manifest.json"
    if evaluation_manifest_path.is_file():
        existing = json.loads(evaluation_manifest_path.read_text(encoding="utf-8"))
        if "inference_latency" not in existing:
            existing["inference_latency"] = _benchmark_frozen_inference(
                feature_root=feature_root,
                model_root=model_root,
                modeling=modeling,
            )
            write_manifest(evaluation_manifest_path, existing)
        return EvaluationResult(
            simulation_run_id=str(existing["simulation_run_id"]),
            model_root=model_root,
            evaluation_path=evaluation_manifest_path,
            task_count=int(existing["task_count"]),
            engineering_goal_met=bool(existing["engineering_goal"]["met"]),
            recovered_mechanisms=int(existing["causal_audit"]["recovered"]),
            reused=True,
            elapsed_seconds=time.perf_counter() - timer_start,
        )
    staging_root = model_root / ".evaluation.staging"
    _safe_remove_tree(staging_root, model_root)
    staging_root.mkdir(parents=True, exist_ok=False)

    snapshot_cache: dict[str, SnapshotData] = {}
    assignments_cache: dict[str, pd.DataFrame] = {}
    final_records: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    try:
        for snapshot_name in ("pre_order", "in_process_rolling", "asset_window"):
            snapshot_cache[snapshot_name] = load_snapshot(
                feature_root, feature_contract, snapshot_name
            )
            assignments_cache[snapshot_name] = pd.read_parquet(
                model_root / "splits" / f"{snapshot_name}.parquet"
            )

        for task in modeling.tasks:
            data = snapshot_cache[task.snapshot]
            assignments = assignments_cache[task.snapshot]
            positions = _task_positions(data, assignments, task, "final_test")
            X_test, y_test = _task_xy(data, positions, task)
            index_test = data.index.iloc[positions].reset_index(drop=True)
            task_root = model_root / "models" / task.name
            task_manifest = json.loads(
                (task_root / "task_manifest.json").read_text(encoding="utf-8")
            )
            predictions = pd.DataFrame(
                {
                    "sample_key": index_test["sample_key"].astype(str),
                    "snapshot_ts": index_test["snapshot_ts"],
                    "observed": y_test,
                }
            )
            for baseline_name in task_manifest["baseline_models"]:
                baseline = joblib.load(task_root / f"baseline_{baseline_name}.joblib")
                baseline_prediction = (
                    baseline.predict(X_test)
                    if task.problem_type == "regression"
                    else positive_probability(baseline, X_test)
                )
                metric_values = (
                    regression_metrics(y_test, baseline_prediction)
                    if task.problem_type == "regression"
                    else classification_metrics(
                        y_test,
                        baseline_prediction,
                        alert_budgets=modeling.training.alert_budgets,
                    )
                )
                final_records.append(
                    _metric_record(
                        task, baseline_name, "final_test", len(y_test), metric_values
                    )
                )

            base_model = joblib.load(task_root / "catboost.joblib")
            prepared = _prepare_catboost(X_test, data.categorical_features)
            if task.problem_type == "regression":
                main_prediction = np.asarray(base_model.predict(prepared), dtype=float)
                main_name = "catboost"
                main_metrics = regression_metrics(y_test, main_prediction)
            else:
                calibrated = joblib.load(task_root / task_manifest["calibrated_file"])
                main_prediction = positive_probability(calibrated, prepared)
                main_name = "catboost_calibrated_sigmoid"
                main_metrics = classification_metrics(
                    y_test,
                    main_prediction,
                    alert_budgets=modeling.training.alert_budgets,
                )
            main_record = _metric_record(
                task, main_name, "final_test", len(y_test), main_metrics
            )
            final_records.append(main_record)
            predictions["prediction"] = main_prediction
            segment_rows.extend(
                segment_records(
                    task_name=task.name,
                    model_name=main_name,
                    problem_type=task.problem_type,
                    y_true=y_test,
                    prediction=main_prediction,
                    X=X_test,
                    snapshot_ts=index_test["snapshot_ts"],
                    min_rows=modeling.training.min_segment_rows,
                    alert_budgets=modeling.training.alert_budgets,
                )
            )

            if task.quantiles:
                quantile_model = joblib.load(task_root / task_manifest["quantile_file"])
                quantile_prediction = np.asarray(quantile_model.predict(prepared), dtype=float)
                final_records.append(
                    _metric_record(
                        task,
                        "catboost_multiquantile",
                        "final_test",
                        len(y_test),
                        quantile_metrics(y_test, quantile_prediction),
                    )
                )
                predictions[["p10", "p50", "p90"]] = quantile_prediction

            prediction_path = staging_root / "predictions" / f"{task.name}.parquet"
            prediction_path.parent.mkdir(parents=True, exist_ok=True)
            predictions.to_parquet(prediction_path, index=False)
            global_shap, segment_shap, scenarios = _tree_shap_records(
                task=task,
                model=base_model,
                data=data,
                X=X_test,
                y=y_test,
                sample_keys=index_test["sample_key"],
                prediction=main_prediction,
                sample_size=modeling.training.shap_sample_size,
                scenario_count=modeling.training.scenario_count,
            )
            explanation_root = staging_root / "explanations" / task.name
            explanation_root.mkdir(parents=True, exist_ok=True)
            global_shap.to_parquet(explanation_root / "global.parquet", index=False)
            segment_shap.to_parquet(explanation_root / "segments.parquet", index=False)
            scenarios.to_parquet(explanation_root / "scenarios.parquet", index=False)
            _evaluation_card(staging_root / "model_cards" / f"{task.name}.md", task, main_record)

        final_metrics = pd.DataFrame(final_records)
        metrics_root = staging_root / "metrics"
        metrics_root.mkdir(parents=True, exist_ok=True)
        final_metrics.to_parquet(metrics_root / "final_test.parquet", index=False)
        pd.DataFrame(segment_rows).to_parquet(metrics_root / "segments.parquet", index=False)

        tbh = final_metrics[final_metrics["task"] == "tbh"]
        baseline_tbh = tbh[
            ~tbh["model"].isin(["catboost", "catboost_multiquantile"])
        ].sort_values("mae")
        if baseline_tbh.empty:
            raise ModelPipelineError("TBH baseline comparison is missing")
        strongest = baseline_tbh.iloc[0]
        catboost_row = tbh[tbh["model"] == "catboost"].iloc[0]
        relative_improvement = float(
            (strongest["mae"] - catboost_row["mae"]) / strongest["mae"]
        )
        engineering_goal = {
            "metric": "TBH MAE relative improvement versus strongest baseline",
            "target_fraction": 0.05,
            "strongest_baseline": str(strongest["model"]),
            "baseline_mae": float(strongest["mae"]),
            "catboost_mae": float(catboost_row["mae"]),
            "relative_improvement": relative_improvement,
            "met": relative_improvement >= 0.05,
        }
        inference_latency = _benchmark_frozen_inference(
            feature_root=feature_root,
            model_root=model_root,
            modeling=modeling,
        )

        backtests = pd.read_parquet(model_root / "metrics" / "expanding_backtests.parquet")
        stability: dict[str, Any] = {}
        for task_name, group in backtests.groupby("task"):
            primary = "mae" if group["mae"].notna().any() else "pr_auc"
            values = group[primary].dropna().astype(float)
            stability[str(task_name)] = {
                "metric": primary,
                "folds": len(values),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
                "min": float(values.min()),
                "max": float(values.max()),
            }

        preliminary_manifest = {
            "schema_version": "1.0",
            "status": "success",
            "simulation_run_id": training_manifest["simulation_run_id"],
            "profile": bundle.simulation.profile.value,
            "model_version": modeling.model_version,
            "task_count": len(modeling.tasks),
            "evaluated_split": "final_test",
            "evaluation_count": 1,
            "idempotent_reuse_on_subsequent_calls": True,
            "engineering_goal": engineering_goal,
            "backtest_stability": stability,
            "inference_latency": inference_latency,
            "final_metrics_path": "metrics/final_test.parquet",
            "segment_metrics_path": "metrics/segments.parquet",
            "explainability": {
                "method": "CatBoost exact TreeSHAP on frozen base models",
                "global": True,
                "segments": ["line_id", "grade_family", "product_code"],
                "scenarios_per_task": modeling.training.scenario_count,
            },
            "causal_audit": {"status": "pending", "recovered": 0, "required": 4},
            "evaluated_at_utc": utc_now().isoformat(),
            "dependencies": _ml_dependencies(),
            "synthetic_scope": "offline synthetic prototype; no machine control",
        }
        write_manifest(staging_root / "evaluation_manifest.json", preliminary_manifest)

        audit = causal_auditor(
            bundle,
            project_root=root,
            feature_root=feature_root,
            model_root=model_root,
            evaluation_root=staging_root,
        )
        preliminary_manifest["causal_audit"] = audit
        write_manifest(staging_root / "evaluation_manifest.json", preliminary_manifest)

        from steelflow.validation.models import validate_model_evaluation

        validation = validate_model_evaluation(
            modeling,
            training_manifest=training_manifest,
            model_root=model_root,
            evaluation_root=staging_root,
        )
        validation_path = staging_root / "validation.json"
        validation_path.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if validation["status"] != "PASS":
            raise ModelPipelineError(
                f"model evaluation validation failed with {validation['summary']['failed']} checks"
            )

        staging_root.replace(evaluation_root)
        elapsed = time.perf_counter() - timer_start
        return EvaluationResult(
            simulation_run_id=str(training_manifest["simulation_run_id"]),
            model_root=model_root,
            evaluation_path=evaluation_root / "evaluation_manifest.json",
            task_count=len(modeling.tasks),
            engineering_goal_met=bool(engineering_goal["met"]),
            recovered_mechanisms=int(audit["recovered"]),
            reused=False,
            elapsed_seconds=elapsed,
        )
    except Exception as exc:
        _safe_remove_tree(staging_root, model_root)
        if isinstance(exc, ModelPipelineError):
            raise
        raise ModelPipelineError(f"model evaluation failed: {exc}") from exc
