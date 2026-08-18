from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from steelflow.config import (
    ConfigError,
    OutputConfig,
    SimulationConfig,
    SimulationProfile,
    available_profiles,
    load_config_bundle,
    load_simulation_config,
    resolve_project_root,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("profile", "days", "orders", "tubes"),
    [
        ("test", 2, 24, 480),
        ("dev", 30, 500, 10_500),
        ("mvp", 731, 12_000, 250_000),
    ],
)
def test_profiles_load_with_expected_contract(
    profile: str, days: int, orders: int, tubes: int
) -> None:
    config = load_simulation_config(profile, ROOT)

    assert config.profile is SimulationProfile(profile)
    assert config.period.duration_days == days
    assert config.volume_targets.orders == orders
    assert config.volume_targets.tubes == tubes
    assert len(config.plant.lines) == 3
    assert len(config.plant.shifts) == 3
    assert len(config.plant.grade_families) == 4
    assert len(config.plant.product_codes) == 12


def test_complete_bundle_has_deterministic_hash() -> None:
    first = load_config_bundle("dev", ROOT)
    second = load_config_bundle("dev", ROOT)

    assert first == second
    assert first.stable_hash() == second.stable_hash()
    assert len(first.stable_hash()) == 64
    assert first.stable_hash() != load_config_bundle("test", ROOT).stable_hash()


def test_available_profiles_follow_declared_order() -> None:
    assert available_profiles() == ("test", "dev", "mvp")


def test_project_root_is_discovered_from_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)

    assert resolve_project_root() == ROOT


def test_unknown_keys_are_rejected() -> None:
    raw = yaml.safe_load((ROOT / "configs" / "simulation_test.yaml").read_text("utf-8"))
    raw["unreviewed_option"] = True

    with pytest.raises(ValidationError, match="unreviewed_option"):
        SimulationConfig.model_validate(raw)


@pytest.mark.parametrize("unsafe_path", [Path("../outside"), Path("C:/outside")])
def test_output_paths_must_remain_inside_project(unsafe_path: Path) -> None:
    with pytest.raises(ValidationError, match="safe path relative"):
        OutputConfig(
            base_path=unsafe_path,
            partition_frequency="day",
            batch_size=1000,
        )


def test_requested_profile_must_match_file_content(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='temporary'\n", encoding="utf-8")
    raw = (ROOT / "configs" / "simulation_test.yaml").read_text(encoding="utf-8")
    (tmp_path / "configs" / "simulation_dev.yaml").write_text(raw, encoding="utf-8")

    with pytest.raises(ConfigError, match="profile mismatch"):
        load_simulation_config("dev", tmp_path)


def test_missing_project_marker_fails_early(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="pyproject.toml"):
        load_simulation_config("test", tmp_path)
