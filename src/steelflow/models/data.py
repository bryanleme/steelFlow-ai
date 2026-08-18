"""Point-in-time dataset loading and leakage-safe temporal partitions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from steelflow.config import ProjectConfigBundle
from steelflow.features.contracts import FeatureContract
from steelflow.generation.generator import load_manifest


class ModelingDataError(RuntimeError):
    """Raised when a feature package cannot support temporal modeling."""


@dataclass(frozen=True)
class SnapshotData:
    name: str
    X: pd.DataFrame
    index: pd.DataFrame
    y: pd.DataFrame
    categorical_features: tuple[str, ...]

    def frame_for_task(
        self,
        target: str,
        *,
        invert_target: bool = False,
        positive_filter: str | None = None,
    ) -> tuple[pd.DataFrame, pd.Series]:
        mask = pd.Series(True, index=self.X.index)
        if positive_filter:
            mask &= self.y[positive_filter].astype(bool)
        target_values = self.y[target]
        if invert_target:
            target_values = ~target_values.astype(bool)
        return (
            self.X.loc[mask].reset_index(drop=True),
            target_values.loc[mask].reset_index(drop=True),
        )


def resolve_feature_root(
    bundle: ProjectConfigBundle,
    contract: FeatureContract,
    project_root: Path,
) -> Path:
    raw_parent = project_root / "data" / "raw" / bundle.simulation.profile.value
    candidates = sorted(raw_parent.glob("*/run_manifest.json"))
    matching: list[tuple[str, Path]] = []
    for manifest_path in candidates:
        manifest = load_manifest(manifest_path)
        if manifest.get("configuration_sha256") == bundle.stable_hash():
            matching.append((str(manifest["simulation_run_id"]), manifest_path.parent))
    if len(matching) != 1:
        raise ModelingDataError(
            "expected exactly one raw run matching the active configuration before modeling"
        )
    run_id = matching[0][0]
    feature_root = (
        project_root
        / "data"
        / "features"
        / bundle.simulation.profile.value
        / f"{run_id}-features-v{contract.contract_version}"
    )
    if not (feature_root / "feature_manifest.json").is_file():
        raise ModelingDataError(f"validated feature package not found: {feature_root}")
    manifest = json.loads((feature_root / "feature_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "success":
        raise ModelingDataError("feature manifest is not successful")
    if manifest.get("feature_contract_sha256") != contract.stable_hash():
        raise ModelingDataError("feature manifest does not match the active feature contract")
    return feature_root


def load_snapshot(feature_root: Path, contract: FeatureContract, name: str) -> SnapshotData:
    snapshot_contract = contract.snapshot(name)
    snapshot_root = feature_root / name
    X = pd.read_parquet(snapshot_root / "X.parquet")
    index = pd.read_parquet(snapshot_root / "index.parquet")
    y = pd.read_parquet(snapshot_root / "y.parquet")
    if not (len(X) == len(index) == len(y)):
        raise ModelingDataError(f"unaligned feature parts for snapshot {name!r}")
    if not index["sample_key"].equals(y["sample_key"]):
        raise ModelingDataError(f"sample keys are not aligned for snapshot {name!r}")
    categorical = tuple(
        feature.name for feature in snapshot_contract.features if feature.dtype == "category"
    )
    return SnapshotData(name, X, index, y, categorical)


def build_temporal_assignments(
    index: pd.DataFrame,
    target_available_at: pd.Series,
    fractions: tuple[float, float, float, float],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Assign four chronological windows and embargo labels crossing a boundary."""

    if len(index) != len(target_available_at) or len(index) == 0:
        raise ModelingDataError("index and target availability must be non-empty and aligned")
    timestamps = pd.to_datetime(index["snapshot_ts"], utc=True)
    availability = pd.to_datetime(target_available_at, utc=True)
    unique_times = np.sort(timestamps.unique())
    if len(unique_times) < 8:
        raise ModelingDataError("at least eight distinct snapshot timestamps are required")

    cumulative = np.cumsum(fractions[:-1])
    positions = [
        min(len(unique_times) - 1, max(1, int(len(unique_times) * value)))
        for value in cumulative
    ]
    if len(set(positions)) != 3:
        raise ModelingDataError("temporal boundaries collapsed; use a larger profile")
    tuning_start, calibration_start, final_test_start = [
        pd.Timestamp(unique_times[position]) for position in positions
    ]

    split = np.select(
        [
            timestamps < tuning_start,
            timestamps < calibration_start,
            timestamps < final_test_start,
        ],
        ["train", "tuning", "calibration"],
        default="final_test",
    ).astype(object)
    next_boundary = {
        "train": tuning_start,
        "tuning": calibration_start,
        "calibration": final_test_start,
    }
    label_available = np.ones(len(index), dtype=bool)
    for split_name, boundary in next_boundary.items():
        positions_in_split = split == split_name
        crosses = positions_in_split & (availability >= boundary).to_numpy()
        label_available[crosses] = False
        split[crosses] = "embargo"

    assignments = pd.DataFrame(
        {
            "row_position": np.arange(len(index), dtype=np.int64),
            "sample_key": index["sample_key"].astype(str),
            "snapshot_ts": timestamps,
            "target_available_at_ts": availability,
            "split": split,
            "label_available_before_next_window": label_available,
        }
    )
    required = {"train", "tuning", "calibration", "final_test"}
    if set(assignments["split"]) & required != required:
        raise ModelingDataError("one or more required temporal windows are empty")
    boundaries = {
        "tuning_start": tuning_start.isoformat(),
        "calibration_start": calibration_start.isoformat(),
        "final_test_start": final_test_start.isoformat(),
    }
    return assignments, boundaries


def split_positions(assignments: pd.DataFrame, split_name: str) -> np.ndarray:
    return assignments.loc[assignments["split"] == split_name, "row_position"].to_numpy()


def expanding_backtest_positions(
    assignments: pd.DataFrame,
    folds: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Build expanding folds wholly before the calibration and final-test windows."""

    eligible = assignments[assignments["split"].isin(["train", "tuning"])].copy()
    unique_times = np.sort(eligible["snapshot_ts"].unique())
    chunks = np.array_split(unique_times, folds + 1)
    if any(len(chunk) == 0 for chunk in chunks):
        raise ModelingDataError("insufficient timestamps for expanding backtests")
    results: list[tuple[np.ndarray, np.ndarray]] = []
    for fold in range(folds):
        train_end = chunks[fold][-1]
        validation_times = chunks[fold + 1]
        validation_start = validation_times[0]
        validation_end = validation_times[-1]
        train_mask = (eligible["snapshot_ts"] <= train_end) & (
            eligible["target_available_at_ts"] < validation_start
        )
        validation_mask = (eligible["snapshot_ts"] >= validation_start) & (
            eligible["snapshot_ts"] <= validation_end
        )
        train_positions = eligible.loc[train_mask, "row_position"].to_numpy()
        validation_positions = eligible.loc[validation_mask, "row_position"].to_numpy()
        if len(train_positions) == 0 or len(validation_positions) == 0:
            raise ModelingDataError(f"empty expanding backtest fold {fold + 1}")
        results.append((train_positions, validation_positions))
    return results
