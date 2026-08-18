"""Run-manifest assembly and persistence."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from steelflow.generation.writer import sha256_file


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def dependency_versions() -> dict[str, str]:
    packages = (
        "steelflow-ai",
        "duckdb",
        "catboost",
        "joblib",
        "numpy",
        "pandas",
        "polars",
        "pyarrow",
        "pydantic",
        "PyYAML",
        "scikit-learn",
        "shap",
    )
    versions: dict[str, str] = {"python": platform.python_version()}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def write_manifest(path: Path, manifest: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum = sha256_file(path)
    path.with_suffix(".sha256").write_text(f"{checksum}  {path.name}\n", encoding="ascii")
    return checksum


def base_manifest(
    *,
    simulation_run_id: str,
    generator_version: str,
    profile: str,
    master_seed: int,
    derived_seeds: dict[str, int],
    seed_derivation: str,
    config_hash: str,
    period: dict[str, str],
    requested_volumes: dict[str, int],
    started_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "simulation_run_id": simulation_run_id,
        "generator_version": generator_version,
        "profile": profile,
        "master_seed": master_seed,
        "derived_seeds": derived_seeds,
        "seed_derivation": seed_derivation,
        "configuration_sha256": config_hash,
        "period": period,
        "requested_volumes": requested_volumes,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": None,
        "elapsed_seconds": None,
        "status": "running",
        "errors": [],
        "dependencies": dependency_versions(),
        "runtime": {
            "platform": platform.platform(),
            "python_executable": Path(sys.executable).name,
        },
        "tables": {},
        "ground_truth": {},
        "dataset_logical_sha256": None,
    }
