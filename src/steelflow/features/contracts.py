"""Frozen, typed point-in-time feature contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from steelflow.config import AvailabilityStage, ConfigError, FeatureClass, StrictModel

FeatureDtype = Literal["boolean", "category", "float", "integer"]


class ModelFeature(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    dtype: FeatureDtype
    availability_stage: AvailabilityStage
    data_class: FeatureClass
    recommendable: bool

    @model_validator(mode="after")
    def validate_feature_safety(self) -> ModelFeature:
        if self.availability_stage in {
            AvailabilityStage.POST_PROCESS,
            AvailabilityStage.DERIVED_POST,
            AvailabilityStage.METADATA,
        }:
            raise ValueError(f"post-process feature prohibited: {self.name}")
        if self.data_class in {FeatureClass.RESULT, FeatureClass.METADATA}:
            raise ValueError(f"result or metadata feature prohibited: {self.name}")
        if self.recommendable and self.data_class is not FeatureClass.CONTROLLABLE:
            raise ValueError(f"only controllable features may be recommendable: {self.name}")
        return self


class SnapshotContract(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    entity_grain: str = Field(min_length=3)
    source_table: str = Field(pattern=r"^features\.[a-z][a-z0-9_]*$")
    entity_id_column: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    snapshot_column: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    max_source_timestamp_column: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    ordered_by: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    features: tuple[ModelFeature, ...]
    targets: tuple[str, ...]

    @model_validator(mode="after")
    def validate_unique_columns(self) -> SnapshotContract:
        feature_names = [feature.name for feature in self.features]
        if not feature_names or len(feature_names) != len(set(feature_names)):
            raise ValueError(f"snapshot {self.name!r} requires unique features")
        if not self.targets or len(self.targets) != len(set(self.targets)):
            raise ValueError(f"snapshot {self.name!r} requires unique targets")
        overlap = set(feature_names) & set(self.targets)
        if overlap:
            raise ValueError(f"features overlap targets in {self.name!r}: {sorted(overlap)}")
        prohibited_identifiers = {
            "asset_id",
            "order_id",
            "simulation_run_id",
            "tube_id",
            "window_id",
        }
        leaked = prohibited_identifiers & set(feature_names)
        if leaked:
            raise ValueError(f"entity or lineage identifiers prohibited: {sorted(leaked)}")
        allowed_stages = {
            "pre_order": {AvailabilityStage.PLAN, AvailabilityStage.PRE_PROCESS},
            "in_process_rolling": {
                AvailabilityStage.PLAN,
                AvailabilityStage.PRE_PROCESS,
                AvailabilityStage.IN_PROCESS_REHEAT,
                AvailabilityStage.IN_PROCESS_ROLLING,
            },
            "asset_window": {AvailabilityStage.PLAN, AvailabilityStage.PRE_PROCESS},
        }
        invalid_stages = sorted(
            feature.name
            for feature in self.features
            if feature.availability_stage not in allowed_stages.get(self.name, set())
        )
        if invalid_stages:
            raise ValueError(f"features unavailable at snapshot {self.name!r}: {invalid_stages}")
        return self


class FeatureContract(StrictModel):
    schema_version: Literal["1.0"]
    contract_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    preprocessing_fit_scope: Literal["fold_train_only"]
    snapshots: tuple[SnapshotContract, ...]

    @field_validator("snapshots")
    @classmethod
    def validate_snapshots(
        cls, snapshots: tuple[SnapshotContract, ...]
    ) -> tuple[SnapshotContract, ...]:
        names = [snapshot.name for snapshot in snapshots]
        if set(names) != {"pre_order", "in_process_rolling", "asset_window"}:
            raise ValueError("exactly the three frozen Phase 4 snapshots are required")
        return snapshots

    def stable_hash(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def snapshot(self, name: str) -> SnapshotContract:
        try:
            return next(snapshot for snapshot in self.snapshots if snapshot.name == name)
        except StopIteration as exc:
            raise ConfigError(f"unknown feature snapshot contract: {name}") from exc


def load_feature_contract(project_root: Path) -> FeatureContract:
    path = project_root / "configs" / "feature_contract_v1.yaml"
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        return FeatureContract.model_validate(content)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigError(f"invalid feature contract {path}: {exc}") from exc
