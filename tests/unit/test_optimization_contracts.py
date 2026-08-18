from __future__ import annotations

from pathlib import Path

from steelflow.features.contracts import load_feature_contract
from steelflow.optimization.contracts import load_optimization_config

ROOT = Path(__file__).resolve().parents[2]


def test_optimization_contract_matches_only_recommendable_features() -> None:
    config = load_optimization_config(ROOT)
    features = load_feature_contract(ROOT).snapshot(config.snapshot)
    recommendable = {feature.name for feature in features.features if feature.recommendable}

    assert config.optimization_version == "1.0.0"
    assert set(config.controllables) == recommendable
    assert len(config.controllables) == 11
    assert config.demo.require_human_approval is True
    assert config.nsga2.alternatives == 4
    assert len(config.stable_hash()) == 64


def test_optimization_code_cannot_import_isolated_ground_truth() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/steelflow/optimization").glob("*.py")
    )

    assert "_ground_truth" not in sources
    assert "data/ground_truth" not in sources
