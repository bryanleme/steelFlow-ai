from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from steelflow.models.contracts import ModelTask, load_modeling_config

ROOT = Path(__file__).resolve().parents[2]


def test_modeling_contract_covers_required_tasks_and_windows() -> None:
    contract = load_modeling_config(ROOT)

    assert contract.model_version == "1.0.0"
    assert len(contract.tasks) == 10
    assert sum(
        (
            contract.splits.train_fraction,
            contract.splits.tuning_fraction,
            contract.splits.calibration_fraction,
            contract.splits.final_test_fraction,
        )
    ) == pytest.approx(1.0)
    assert {task.name for task in contract.tasks if task.quantiles} == {
        "tbh",
        "energy_intensity",
        "outer_diameter_deviation",
        "wall_eccentricity",
        "ovality",
        "downtime_duration",
    }
    assert len(contract.stable_hash()) == 64


def test_classification_task_rejects_quantiles() -> None:
    with pytest.raises(ValidationError, match="cannot request quantiles"):
        ModelTask(
            name="invalid",
            snapshot="asset_window",
            problem_type="classification",
            target="event",
            quantiles=True,
            unit="probability",
        )
