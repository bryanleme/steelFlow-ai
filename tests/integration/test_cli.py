from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(ROOT / "src"), environment.get("PYTHONPATH", "")))
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "steelflow",
            "--project-root",
            str(ROOT),
            *arguments,
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_help_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "steelflow", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "offline synthetic decision-support prototype" in result.stdout


def test_all_configs_validate_from_cli() -> None:
    result = run_cli("validate-config", "--all")

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("OK profile=") == 3
    assert "profile=test" in result.stdout
    assert "profile=dev" in result.stdout
    assert "profile=mvp" in result.stdout


def test_doctor_returns_machine_readable_report() -> None:
    result = run_cli("doctor", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["python_supported"] is True
    assert set(report["profiles"]) == {"test", "dev", "mvp"}
    assert report["packages"]["numpy"] is True
    assert report["packages"]["pyarrow"] is True
    assert report["packages"]["duckdb"] is True
    assert report["prototype_scope"] == "offline synthetic data; no machine control"


def test_config_hash_is_a_sha256_digest() -> None:
    result = run_cli("config-hash", "--profile", "test")

    assert result.returncode == 0, result.stderr
    digest = result.stdout.strip()
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    ("command", "phase"),
    [
        ("build-db", 3),
        ("train", 5),
        ("evaluate", 5),
        ("optimize-demo", 6),
        ("app", 7),
    ],
)
def test_future_commands_fail_explicitly(command: str, phase: int) -> None:
    result = run_cli(command, "--profile", "test")

    assert result.returncode == 2
    assert f"reserved for Phase {phase}" in result.stderr
    assert "not implemented" in result.stderr
