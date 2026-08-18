from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from steelflow.config import AvailabilityStage, FeatureClass
from steelflow.features.contracts import ModelFeature, load_feature_contract

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_feature_contract_is_complete_and_safe() -> None:
    contract = load_feature_contract(ROOT)

    assert contract.contract_version == "1.0.0"
    assert contract.preprocessing_fit_scope == "fold_train_only"
    assert {snapshot.name for snapshot in contract.snapshots} == {
        "asset_window",
        "in_process_rolling",
        "pre_order",
    }
    assert len(contract.stable_hash()) == 64
    assert all(
        feature.data_class is FeatureClass.CONTROLLABLE
        for snapshot in contract.snapshots
        for feature in snapshot.features
        if feature.recommendable
    )
    assert all(
        feature.availability_stage
        not in {
            AvailabilityStage.POST_PROCESS,
            AvailabilityStage.DERIVED_POST,
            AvailabilityStage.METADATA,
        }
        for snapshot in contract.snapshots
        for feature in snapshot.features
    )


def test_contract_rejects_post_process_feature() -> None:
    with pytest.raises(ValidationError, match="post-process feature prohibited"):
        ModelFeature(
            name="approved_first_pass",
            dtype="boolean",
            availability_stage=AvailabilityStage.POST_PROCESS,
            data_class=FeatureClass.RESULT,
            recommendable=False,
        )
