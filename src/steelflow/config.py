"""Typed, fail-fast configuration loading for SteelFlow AI."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConfigError(RuntimeError):
    """Raised when a configuration file cannot be found, parsed or validated."""


class StrictModel(BaseModel):
    """Base model that rejects unknown keys and cannot be mutated after validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SimulationProfile(StrEnum):
    TEST = "test"
    DEV = "dev"
    MVP = "mvp"


class SimulationPeriod(StrictModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_order(self) -> SimulationPeriod:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    @property
    def duration_days(self) -> int:
        """Inclusive number of simulated calendar days."""

        return (self.end_date - self.start_date).days + 1


class PlantConfig(StrictModel):
    lines: tuple[str, ...]
    shifts: tuple[str, ...]
    grade_families: tuple[str, ...]
    product_codes: tuple[str, ...]

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != 3 or len(set(value)) != 3:
            raise ValueError("exactly three unique production lines are required")
        return value

    @field_validator("shifts")
    @classmethod
    def validate_shifts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != 3 or len(set(value)) != 3:
            raise ValueError("exactly three unique shifts are required")
        return value

    @field_validator("grade_families")
    @classmethod
    def validate_grades(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        expected = {"J55", "N80", "L80", "P110"}
        if set(value) != expected:
            raise ValueError(f"grade_families must contain exactly {sorted(expected)}")
        return value

    @field_validator("product_codes")
    @classmethod
    def validate_products(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != 12 or len(set(value)) != 12:
            raise ValueError("exactly twelve unique product combinations are required")
        return value


class VolumeTargets(StrictModel):
    orders: int = Field(gt=0)
    tubes: int = Field(gt=0)
    stage_events: int = Field(gt=0)
    sensor_windows: int = Field(gt=0)
    quality_results: int = Field(gt=0)
    downtime_events: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_relationships(self) -> VolumeTargets:
        if self.tubes < self.orders:
            raise ValueError("tubes must be greater than or equal to orders")
        if self.stage_events < self.tubes:
            raise ValueError("stage_events must be greater than or equal to tubes")
        if self.sensor_windows < self.stage_events:
            raise ValueError("sensor_windows must be greater than or equal to stage_events")
        if self.quality_results < self.tubes:
            raise ValueError("quality_results must be greater than or equal to tubes")
        return self


class OutputConfig(StrictModel):
    base_path: Path
    partition_frequency: Literal["day", "month"]
    batch_size: int = Field(ge=100, le=1_000_000)
    overwrite: bool = False

    @field_validator("base_path")
    @classmethod
    def validate_relative_path(cls, value: Path) -> Path:
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("base_path must be a safe path relative to the project root")
        return value


class SimulationConfig(StrictModel):
    schema_version: Literal["1.0"]
    profile: SimulationProfile
    generator_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    random_seed: int = Field(ge=0, le=2**32 - 1)
    period: SimulationPeriod
    plant: PlantConfig
    volume_targets: VolumeTargets
    output: OutputConfig

    @model_validator(mode="after")
    def validate_profile_period(self) -> SimulationConfig:
        expected_days = {
            SimulationProfile.TEST: 2,
            SimulationProfile.DEV: 30,
            SimulationProfile.MVP: 731,
        }
        actual = self.period.duration_days
        if actual != expected_days[self.profile]:
            raise ValueError(
                f"profile {self.profile.value!r} requires {expected_days[self.profile]} "
                f"inclusive days, received {actual}"
            )
        if self.profile is SimulationProfile.MVP:
            targets = self.volume_targets
            bounds = {
                "orders": (8_000, 15_000),
                "tubes": (250_000, 250_000),
                "stage_events": (1_500_000, 2_000_000),
                "sensor_windows": (6_000_000, 10_000_000),
                "quality_results": (1_000_000, 2_000_000),
                "downtime_events": (10_000, 30_000),
            }
            for field_name, (lower, upper) in bounds.items():
                value = getattr(targets, field_name)
                if not lower <= value <= upper:
                    raise ValueError(
                        f"mvp {field_name} target must be within "
                        f"[{lower}, {upper}], received {value}"
                    )
        return self

    def stable_hash(self) -> str:
        """Return a stable SHA-256 hash of the logical configuration."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class NumericRange(StrictModel):
    min: float
    max: float

    @model_validator(mode="after")
    def validate_range(self) -> NumericRange:
        if self.max <= self.min:
            raise ValueError("range max must be greater than min")
        return self


class InternalSpecsConfig(StrictModel):
    schema_version: Literal["1.0"]
    disclaimer: str
    units: dict[str, str]
    process_envelopes: dict[str, NumericRange]

    @field_validator("disclaimer")
    @classmethod
    def validate_disclaimer(cls, value: str) -> str:
        normalized = value.lower()
        if "simulated" not in normalized or "not an api 5ct" not in normalized:
            raise ValueError("disclaimer must identify simulated limits and deny API 5CT status")
        return value


class AccessPolicy(StrictModel):
    allowed_packages: tuple[str, ...]
    forbidden_packages: tuple[str, ...]

    @model_validator(mode="after")
    def validate_disjoint(self) -> AccessPolicy:
        overlap = set(self.allowed_packages) & set(self.forbidden_packages)
        if overlap:
            raise ValueError(f"causal access lists overlap: {sorted(overlap)}")
        return self


class CausalMechanism(StrictModel):
    id: str = Field(min_length=3)
    enabled: bool


class CausalRulesConfig(StrictModel):
    schema_version: Literal["1.0"]
    truth_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    access_policy: AccessPolicy
    mechanisms: tuple[CausalMechanism, ...]

    @field_validator("mechanisms")
    @classmethod
    def validate_mechanisms(cls, value: tuple[CausalMechanism, ...]) -> tuple[CausalMechanism, ...]:
        identifiers = [mechanism.id for mechanism in value]
        if len(identifiers) < 8 or len(set(identifiers)) != len(identifiers):
            raise ValueError("at least eight unique causal mechanism identifiers are required")
        return value


class DataQualityCheck(StrictModel):
    id: str = Field(min_length=3)
    severity: Literal["warning", "error"]
    enabled: bool


class DataQualityConfig(StrictModel):
    schema_version: Literal["1.0"]
    fail_fast: bool
    checks: tuple[DataQualityCheck, ...]

    @field_validator("checks")
    @classmethod
    def validate_checks(cls, value: tuple[DataQualityCheck, ...]) -> tuple[DataQualityCheck, ...]:
        identifiers = [check.id for check in value]
        if not identifiers or len(set(identifiers)) != len(identifiers):
            raise ValueError("data-quality check identifiers must be present and unique")
        return value


class ProjectConfigBundle(StrictModel):
    simulation: SimulationConfig
    internal_specs: InternalSpecsConfig
    causal_rules: CausalRulesConfig
    data_quality: DataQualityConfig

    def stable_hash(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_project_root(explicit_root: Path | None = None) -> Path:
    """Resolve the project root without embedding machine-specific absolute paths."""

    candidate = explicit_root
    if candidate is None and (environment_root := os.getenv("STEELFLOW_PROJECT_ROOT")):
        candidate = Path(environment_root)
    if candidate is None:
        working_directory = Path.cwd().resolve()
        search_roots = (working_directory, *working_directory.parents)
        candidate = next(
            (
                path
                for path in search_roots
                if (path / "pyproject.toml").is_file() and (path / "configs").is_dir()
            ),
            Path(__file__).resolve().parents[2],
        )

    resolved = candidate.expanduser().resolve()
    if not (resolved / "pyproject.toml").is_file():
        raise ConfigError(f"project root does not contain pyproject.toml: {resolved}")
    return resolved


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"configuration file not found: {path}")
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not parse configuration file {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(f"configuration root must be a mapping: {path}")
    return parsed


def load_simulation_config(
    profile: SimulationProfile | str,
    project_root: Path | None = None,
) -> SimulationConfig:
    """Load and validate one named simulation profile."""

    try:
        normalized_profile = SimulationProfile(profile)
    except ValueError as exc:
        expected = ", ".join(item.value for item in SimulationProfile)
        raise ConfigError(f"unknown profile {profile!r}; expected one of: {expected}") from exc

    root = resolve_project_root(project_root)
    path = root / "configs" / f"simulation_{normalized_profile.value}.yaml"
    try:
        config = SimulationConfig.model_validate(_load_yaml(path))
    except ValueError as exc:
        raise ConfigError(f"invalid simulation configuration {path}: {exc}") from exc
    if config.profile is not normalized_profile:
        raise ConfigError(
            f"profile mismatch: file requested {normalized_profile.value!r}, "
            f"content declares {config.profile.value!r}"
        )
    return config


def load_config_bundle(
    profile: SimulationProfile | str,
    project_root: Path | None = None,
) -> ProjectConfigBundle:
    """Load all versioned configuration contracts needed by a pipeline run."""

    root = resolve_project_root(project_root)
    model_paths: tuple[tuple[str, type[StrictModel], Path], ...] = (
        ("internal_specs", InternalSpecsConfig, root / "configs" / "internal_specs.yaml"),
        ("causal_rules", CausalRulesConfig, root / "configs" / "causal_rules.yaml"),
        ("data_quality", DataQualityConfig, root / "configs" / "data_quality.yaml"),
    )
    values: dict[str, StrictModel] = {"simulation": load_simulation_config(profile, root)}
    for name, model_type, path in model_paths:
        try:
            values[name] = model_type.model_validate(_load_yaml(path))
        except ValueError as exc:
            raise ConfigError(f"invalid supporting configuration {path}: {exc}") from exc
    return ProjectConfigBundle.model_validate(values)


def available_profiles() -> tuple[str, ...]:
    return tuple(profile.value for profile in SimulationProfile)
