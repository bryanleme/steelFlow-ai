"""Typed contracts for temporal model training and evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from steelflow.config import ConfigError, StrictModel

ProblemType = Literal["regression", "classification"]


class SplitConfig(StrictModel):
    train_fraction: float = Field(gt=0, lt=1)
    tuning_fraction: float = Field(gt=0, lt=1)
    calibration_fraction: float = Field(gt=0, lt=1)
    final_test_fraction: float = Field(gt=0, lt=1)
    backtest_folds: int = Field(ge=2, le=5)

    @model_validator(mode="after")
    def validate_sum(self) -> SplitConfig:
        total = (
            self.train_fraction
            + self.tuning_fraction
            + self.calibration_fraction
            + self.final_test_fraction
        )
        if abs(total - 1.0) > 1e-12:
            raise ValueError(f"temporal split fractions must sum to 1.0, got {total}")
        return self


class TrainingConfig(StrictModel):
    iterations: int = Field(ge=20, le=2000)
    backtest_iterations: int = Field(ge=10, le=500)
    depth: int = Field(ge=3, le=12)
    learning_rate: float = Field(gt=0, le=1)
    early_stopping_rounds: int = Field(ge=5, le=200)
    random_forest_estimators: int = Field(ge=20, le=1000)
    random_forest_max_depth: int = Field(ge=3, le=40)
    min_segment_rows: int = Field(ge=20)
    shap_sample_size: int = Field(ge=20, le=5000)
    scenario_count: int = Field(ge=1, le=100)
    alert_budgets: tuple[float, ...]

    @field_validator("alert_budgets")
    @classmethod
    def validate_budgets(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        if not values or any(value <= 0 or value > 1 for value in values):
            raise ValueError("alert budgets must be non-empty fractions in (0, 1]")
        if tuple(sorted(set(values))) != values:
            raise ValueError("alert budgets must be unique and ascending")
        return values


class ModelTask(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    snapshot: Literal["pre_order", "in_process_rolling", "asset_window"]
    problem_type: ProblemType
    target: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    positive_filter: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    invert_target: bool = False
    quantiles: bool = False
    backtest: bool = False
    unit: str = Field(min_length=1)
    point_loss: Literal["RMSE", "MAE"] = "RMSE"
    iterations_override: int | None = Field(default=None, ge=20, le=2000)
    depth_override: int | None = Field(default=None, ge=3, le=12)
    learning_rate_override: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def validate_task(self) -> ModelTask:
        if self.problem_type == "classification" and self.quantiles:
            raise ValueError(f"classification task {self.name!r} cannot request quantiles")
        if self.problem_type == "classification" and self.positive_filter:
            raise ValueError(f"classification task {self.name!r} cannot use positive_filter")
        if self.problem_type == "classification" and (
            self.point_loss != "RMSE"
            or self.iterations_override is not None
            or self.depth_override is not None
            or self.learning_rate_override is not None
        ):
            raise ValueError(f"classification task {self.name!r} cannot override regression fit")
        if self.problem_type == "regression" and self.invert_target:
            raise ValueError(f"regression task {self.name!r} cannot invert its target")
        return self


class ModelingConfig(StrictModel):
    schema_version: Literal["1.0"]
    model_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    random_seed: int = Field(ge=0)
    splits: SplitConfig
    training: TrainingConfig
    tasks: tuple[ModelTask, ...]

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, tasks: tuple[ModelTask, ...]) -> tuple[ModelTask, ...]:
        names = [task.name for task in tasks]
        if not names or len(names) != len(set(names)):
            raise ValueError("model task names must be non-empty and unique")
        required = {
            "tbh",
            "energy_intensity",
            "outer_diameter_deviation",
            "wall_eccentricity",
            "ovality",
            "downtime_duration",
            "quality_failure",
            "rework",
            "scrap",
            "downtime_occurrence",
        }
        if set(names) != required:
            raise ValueError(f"modeling contract must contain tasks: {sorted(required)}")
        return tasks

    def stable_hash(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def task(self, name: str) -> ModelTask:
        try:
            return next(task for task in self.tasks if task.name == name)
        except StopIteration as exc:
            raise ConfigError(f"unknown modeling task: {name}") from exc


def load_modeling_config(project_root: Path) -> ModelingConfig:
    path = project_root / "configs" / "modeling_v1.yaml"
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ModelingConfig.model_validate(content)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigError(f"invalid modeling contract {path}: {exc}") from exc
