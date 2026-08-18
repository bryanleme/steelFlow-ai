from __future__ import annotations

import ast
from pathlib import Path

from steelflow.config import FeatureClass, load_config_bundle
from steelflow.generation.schemas import EXPECTED_TABLES, TABLE_PRIMARY_KEYS

ROOT = Path(__file__).resolve().parents[2]


def test_every_public_table_has_one_primary_key_contract() -> None:
    assert set(TABLE_PRIMARY_KEYS) == set(EXPECTED_TABLES)
    assert all(
        primary_key.endswith("_id")
        or primary_key.endswith("_code")
        or primary_key == "feature_name"
        for primary_key in TABLE_PRIMARY_KEYS.values()
    )


def test_configured_volumes_match_fixed_per_tube_contracts() -> None:
    for profile in ("test", "dev", "mvp"):
        targets = load_config_bundle(profile, ROOT).simulation.volume_targets

        assert targets.sensor_windows == targets.tubes * 32
        assert targets.quality_results == targets.tubes * 6
        assert targets.tubes * 7 <= targets.stage_events <= targets.tubes * 8


def test_only_controllable_features_are_recommendable() -> None:
    registry = load_config_bundle("dev", ROOT).feature_availability.features

    assert all(
        feature.data_class is FeatureClass.CONTROLLABLE
        for feature in registry
        if feature.recommendable
    )
    assert all(
        not feature.recommendable
        for feature in registry
        if feature.data_class in {FeatureClass.CONTEXT, FeatureClass.MEDIATOR, FeatureClass.RESULT}
    )


def test_public_validator_does_not_import_private_causal_truth() -> None:
    source = (ROOT / "src" / "steelflow" / "validation" / "raw_data.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    assert not any("generation._ground_truth" in imported for imported in imports)
