"""Typed configuration for constrained multi-objective scenario search."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from steelflow.config import ConfigError, StrictModel


class EnvelopeConfig(StrictModel):
    lower_quantile: float = Field(ge=0, lt=0.5)
    upper_quantile: float = Field(gt=0.5, le=1)
    minimum_support: int = Field(ge=50)
    nearest_neighbors: int = Field(ge=2, le=50)
    distance_quantile: float = Field(gt=0.5, lt=1)
    distance_multiplier: float = Field(ge=0.5, le=3)
    wear_band_edges: tuple[float, ...]

    @model_validator(mode="after")
    def validate_envelope(self) -> EnvelopeConfig:
        if self.upper_quantile <= self.lower_quantile:
            raise ValueError("upper envelope quantile must exceed lower quantile")
        if len(self.wear_band_edges) < 3 or tuple(sorted(self.wear_band_edges)) != (
            self.wear_band_edges
        ):
            raise ValueError("wear band edges must be ascending")
        return self


class SurrogateConfig(StrictModel):
    iterations: int = Field(ge=20, le=1000)
    depth: int = Field(ge=3, le=12)
    learning_rate: float = Field(gt=0, le=1)
    early_stopping_rounds: int = Field(ge=5, le=100)


class Nsga2Config(StrictModel):
    population_size: int = Field(ge=20, le=1000)
    offspring: int = Field(ge=20, le=1000)
    generations: int = Field(ge=10, le=1000)
    alternatives: Literal[4]


class ConstraintConfig(StrictModel):
    max_quality_failure_probability: float = Field(gt=0, lt=1)
    max_downtime_probability: float = Field(gt=0, lt=1)
    max_expected_downtime_minutes: float = Field(gt=0)
    max_throughput_interval_width: float = Field(gt=0)
    max_energy_interval_width: float = Field(gt=0)
    max_abs_outer_diameter_deviation_mm: float = Field(gt=0)
    max_wall_eccentricity_pct: float = Field(gt=0)
    max_ovality_pct: float = Field(gt=0)


class ControllableConfig(StrictModel):
    unit: str = Field(min_length=1)
    internal_min: float
    internal_max: float
    max_change_fraction: float = Field(gt=0, le=0.5)

    @model_validator(mode="after")
    def validate_range(self) -> ControllableConfig:
        if self.internal_max <= self.internal_min:
            raise ValueError("controllable internal_max must exceed internal_min")
        return self


class DemoConfig(StrictModel):
    contexts: int = Field(ge=1, le=10)
    selection: Literal["one_supported_medoid_per_line"]
    require_human_approval: Literal[True]
    scenario_language: Literal["estimated_scenario_in_synthetic_backtest"]


class OptimizationConfig(StrictModel):
    schema_version: Literal["1.0"]
    optimization_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    random_seed: int = Field(ge=0)
    snapshot: Literal["in_process_rolling"]
    context_columns: tuple[str, ...]
    conditioning_hierarchy: tuple[tuple[str, ...], ...]
    envelope: EnvelopeConfig
    surrogate: SurrogateConfig
    nsga2: Nsga2Config
    constraints: ConstraintConfig
    controllables: dict[str, ControllableConfig]
    demo: DemoConfig

    @field_validator("context_columns")
    @classmethod
    def validate_context_columns(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        required = {"product_code", "grade_family", "line_id", "shift_id"}
        if set(values) != required:
            raise ValueError(f"context columns must be exactly {sorted(required)}")
        return values

    @field_validator("conditioning_hierarchy")
    @classmethod
    def validate_hierarchy(cls, values: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
        if not values or any(not level for level in values):
            raise ValueError("conditioning hierarchy must contain non-empty levels")
        allowed = {"product_code", "grade_family", "line_id", "shift_id", "wear_band"}
        invalid = {column for level in values for column in level} - allowed
        if invalid:
            raise ValueError(f"invalid conditioning columns: {sorted(invalid)}")
        return values

    def stable_hash(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_optimization_config(project_root: Path) -> OptimizationConfig:
    path = project_root / "configs" / "optimization_v1.yaml"
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        return OptimizationConfig.model_validate(content)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigError(f"invalid optimization contract {path}: {exc}") from exc
