"""Lineage checks shared by downstream analytical artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steelflow.config import ProjectConfigBundle
from steelflow.generation.writer import sha256_file
from steelflow.validation.raw_data import expected_run_path


class StaleAnalyticsError(RuntimeError):
    """Raised when a downstream build sees an absent or stale analytical database."""


@dataclass(frozen=True)
class AnalyticsBuildReference:
    simulation_run_id: str
    database_path: Path
    build_manifest_path: Path
    build_manifest: dict[str, Any]


def current_sql_contracts(project_root: Path) -> dict[str, dict[str, Any]]:
    paths = tuple(sorted((project_root / "sql" / "curated").glob("*.sql"))) + tuple(
        sorted((project_root / "sql" / "marts").glob("*.sql"))
    )
    return {
        path.relative_to(project_root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    }


def resolve_current_analytics_build(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    build_dir_override: Path | None = None,
) -> AnalyticsBuildReference:
    """Resolve the deterministic database and reject SQL/configuration drift."""

    run_id = expected_run_path(bundle, project_root).name
    build_dir = (
        build_dir_override.resolve()
        if build_dir_override is not None
        else project_root / "data" / "analytics" / bundle.simulation.profile.value / run_id
    )
    database_path = build_dir / "steelflow.duckdb"
    manifest_path = build_dir / "build_manifest.json"
    if not database_path.is_file() or not manifest_path.is_file():
        raise StaleAnalyticsError(f"analytical database not found for {run_id}; run build-db first")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StaleAnalyticsError(f"could not read analytical build manifest: {exc}") from exc

    if manifest.get("status") != "success":
        raise StaleAnalyticsError("analytical build manifest is not successful")
    if manifest.get("configuration_sha256") != bundle.stable_hash():
        raise StaleAnalyticsError(
            "analytical build configuration does not match the selected profile"
        )
    if manifest.get("sql_contracts") != current_sql_contracts(project_root):
        raise StaleAnalyticsError("analytical SQL changed; rebuild the database before continuing")
    if sha256_file(database_path) != manifest.get("database", {}).get("sha256"):
        raise StaleAnalyticsError("analytical database checksum does not match its build manifest")

    return AnalyticsBuildReference(
        simulation_run_id=run_id,
        database_path=database_path,
        build_manifest_path=manifest_path,
        build_manifest=manifest,
    )
