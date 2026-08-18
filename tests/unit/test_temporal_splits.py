from __future__ import annotations

import numpy as np
import pandas as pd

from steelflow.models.contracts import ModelTask
from steelflow.models.data import (
    SnapshotData,
    build_temporal_assignments,
    expanding_backtest_positions,
)
from steelflow.models.pipeline import _task_positions


def _index(rows: int = 80) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=rows, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "sample_key": [f"sample-{index:03d}" for index in range(rows)],
            "snapshot_ts": timestamps,
        }
    )


def test_temporal_assignments_are_ordered_and_embargo_crossing_labels() -> None:
    index = _index()
    availability = index["snapshot_ts"] + pd.Timedelta(hours=1)
    availability.iloc[43] = index["snapshot_ts"].iloc[70]

    assignments, boundaries = build_temporal_assignments(
        index,
        availability,
        (0.55, 0.20, 0.10, 0.15),
    )

    assert set(assignments["split"]) == {
        "train",
        "tuning",
        "calibration",
        "final_test",
        "embargo",
    }
    assert assignments.loc[43, "split"] == "embargo"
    assert boundaries["tuning_start"] < boundaries["calibration_start"]
    assert boundaries["calibration_start"] < boundaries["final_test_start"]
    ordered = [
        assignments.loc[assignments["split"] == name, "snapshot_ts"]
        for name in ("train", "tuning", "calibration", "final_test")
    ]
    assert all(
        left.max() < right.min()
        for left, right in zip(ordered[:-1], ordered[1:], strict=True)
    )


def test_expanding_backtests_never_reach_calibration_or_final_test() -> None:
    index = _index(120)
    assignments, _ = build_temporal_assignments(
        index,
        index["snapshot_ts"] + pd.Timedelta(minutes=10),
        (0.55, 0.20, 0.10, 0.15),
    )

    folds = expanding_backtest_positions(assignments, 3)

    assert len(folds) == 3
    for train, validation in folds:
        assert len(train) > 0
        assert len(validation) > 0
        assert np.max(train) < np.min(validation)
        used_splits = set(assignments.iloc[np.concatenate([train, validation])]["split"])
        assert used_splits <= {"train", "tuning"}


def test_task_positions_exclude_unobservable_continuous_targets() -> None:
    index = _index(12)
    data = SnapshotData(
        name="pre_order",
        X=pd.DataFrame({"feature": np.arange(12)}),
        index=index,
        y=pd.DataFrame(
            {
                "target": [1.0, float("nan"), *np.arange(10, dtype=float)],
                "target_available_at_ts": index["snapshot_ts"] + pd.Timedelta(minutes=1),
            }
        ),
        categorical_features=(),
    )
    assignments, _ = build_temporal_assignments(
        index,
        data.y["target_available_at_ts"],
        (0.5, 0.25, 1 / 12, 1 / 6),
    )
    task = ModelTask(
        name="observable_target",
        snapshot="pre_order",
        problem_type="regression",
        target="target",
        unit="unit",
    )

    positions = _task_positions(data, assignments, task, "train")

    assert 1 not in positions
