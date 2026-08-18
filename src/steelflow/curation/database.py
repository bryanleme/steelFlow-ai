"""Atomic DuckDB build for curated, analytical and feature layers."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.curation.exports import export_powerbi_package
from steelflow.generation.generator import load_manifest
from steelflow.generation.manifest import dependency_versions, utc_now, write_manifest
from steelflow.generation.schemas import EXPECTED_TABLES
from steelflow.generation.writer import sha256_file
from steelflow.validation.analytics import validate_analytics_database
from steelflow.validation.raw_data import expected_run_path, validate_raw_dataset


class DatabaseBuildError(RuntimeError):
    """Raised when an analytical build cannot be completed atomically."""


@dataclass(frozen=True)
class DatabaseBuildResult:
    simulation_run_id: str
    database_path: Path
    export_path: Path
    manifest_path: Path
    validation_path: Path
    object_counts: dict[str, int]
    elapsed_seconds: float


def _safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise DatabaseBuildError(f"refusing to remove path outside build parent: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _atomic_promote(staging: Path, final: Path) -> None:
    if final.exists():
        raise DatabaseBuildError(f"final build directory already exists: {final}")
    staging.replace(final)


def _quoted_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _relative_or_absolute(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _render_sql(path: Path, replacements: dict[str, str]) -> str:
    rendered = path.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        rendered = rendered.replace(f"{{{{{placeholder}}}}}", value.replace("'", "''"))
    if "{{" in rendered or "}}" in rendered:
        raise DatabaseBuildError(f"unresolved SQL placeholder in {path}")
    return rendered


def _object_counts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for schema_name in ("raw", "curated", "analytics", "features", "model_outputs"):
        table_count = int(
            connection.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = ?",
                [schema_name],
            ).fetchone()[0]
        )
        counts[schema_name] = table_count
    return counts


def _execute_sql_contracts(
    connection: duckdb.DuckDBPyConnection,
    *,
    project_root: Path,
    replacements: dict[str, str],
) -> dict[str, dict[str, Any]]:
    sql_paths = tuple(sorted((project_root / "sql" / "curated").glob("*.sql"))) + tuple(
        sorted((project_root / "sql" / "marts").glob("*.sql"))
    )
    if not sql_paths:
        raise DatabaseBuildError("no SQL contracts were found")

    records: dict[str, dict[str, Any]] = {}
    for path in sql_paths:
        connection.execute(_render_sql(path, replacements))
        relative_path = path.relative_to(project_root).as_posix()
        records[relative_path] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return records


def _make_raw_views_portable(
    connection: duckdb.DuckDBPyConnection,
    *,
    raw_path: Path,
    project_root: Path,
) -> None:
    try:
        relative_raw_path = raw_path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return
    for table_name in EXPECTED_TABLES:
        parquet_glob = f"{relative_raw_path}/{table_name}/**/*.parquet".replace("'", "''")
        connection.execute(
            f"CREATE OR REPLACE VIEW raw.{table_name} AS SELECT * FROM "
            f"read_parquet('{parquet_glob}', union_by_name=true, hive_partitioning=false)"
        )


def build_analytics_database(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    raw_run_path: Path | None = None,
    analytics_base: Path | None = None,
    export_base: Path | None = None,
    overwrite: bool = False,
) -> DatabaseBuildResult:
    """Build and validate one analytical database plus Power BI package atomically."""

    started_at = utc_now()
    timer_start = time.perf_counter()
    root = project_root.resolve()
    raw_path = (raw_run_path or expected_run_path(bundle, root)).resolve()
    raw_validation_path = (
        root
        / "artifacts"
        / "validation"
        / (f"{bundle.simulation.profile.value}-raw-for-analytics.json")
    )
    raw_report = validate_raw_dataset(
        bundle,
        project_root=root,
        run_path=raw_path,
        report_path=raw_validation_path,
    )
    if not raw_report.passed:
        raise DatabaseBuildError("raw validation failed; analytical build was not started")

    raw_manifest = load_manifest(raw_path / "run_manifest.json")
    run_id = str(raw_manifest["simulation_run_id"])
    profile = bundle.simulation.profile.value
    analytics_parent = (analytics_base or root / "data" / "analytics" / profile).resolve()
    export_parent = (export_base or root / "powerbi" / "exports" / profile).resolve()
    final_database_dir = analytics_parent / run_id
    final_export_dir = export_parent / run_id
    staging_database_dir = analytics_parent / f".{run_id}.staging"
    staging_export_dir = export_parent / f".{run_id}.staging"
    staging_database_path = staging_database_dir / "steelflow.duckdb"

    analytics_parent.mkdir(parents=True, exist_ok=True)
    export_parent.mkdir(parents=True, exist_ok=True)
    existing = [path for path in (final_database_dir, final_export_dir) if path.exists()]
    if existing and not overwrite:
        paths = ", ".join(str(path) for path in existing)
        raise DatabaseBuildError(f"analytical build already exists: {paths}; use --force")
    if overwrite:
        _safe_remove_tree(final_database_dir, analytics_parent)
        _safe_remove_tree(final_export_dir, export_parent)
    _safe_remove_tree(staging_database_dir, analytics_parent)
    _safe_remove_tree(staging_export_dir, export_parent)
    staging_database_dir.mkdir(parents=True, exist_ok=False)

    validation_path = root / "artifacts" / "validation" / f"{run_id}-analytics-validation.json"
    sql_records: dict[str, dict[str, Any]] = {}
    export_manifest: dict[str, Any] = {}
    object_counts: dict[str, int] = {}
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(staging_database_path))
        connection.execute("SET TimeZone='UTC'")
        # Floating-point aggregates must remain byte-stable across equivalent builds.
        connection.execute("SET threads TO 1")
        for schema_name in (
            "raw",
            "curated",
            "analytics",
            "features",
            "model_outputs",
            "metadata",
        ):
            connection.execute(f"CREATE SCHEMA {schema_name}")

        for table_name in EXPECTED_TABLES:
            parquet_glob = _quoted_path(raw_path / table_name / "**" / "*.parquet")
            connection.execute(
                f"CREATE VIEW raw.{table_name} AS SELECT * FROM "
                f"read_parquet('{parquet_glob}', union_by_name=true, hive_partitioning=false)"
            )

        connection.execute(
            "CREATE TABLE metadata.build_info ("
            "simulation_run_id VARCHAR NOT NULL, profile VARCHAR NOT NULL, "
            "configuration_sha256 VARCHAR NOT NULL, raw_dataset_logical_sha256 VARCHAR NOT NULL, "
            "database_build_version VARCHAR NOT NULL, built_at_utc TIMESTAMPTZ NOT NULL, "
            "raw_run_path VARCHAR NOT NULL, synthetic_scope VARCHAR NOT NULL)"
        )
        connection.execute(
            "INSERT INTO metadata.build_info VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                profile,
                bundle.stable_hash(),
                raw_manifest["dataset_logical_sha256"],
                "0.1.0",
                started_at,
                _relative_or_absolute(raw_path, root),
                "offline synthetic prototype; no machine control",
            ],
        )

        replacements = {
            "PARTITION_FREQUENCY": bundle.simulation.output.partition_frequency,
            "START_DATE": bundle.simulation.period.start_date.isoformat(),
            "END_DATE": bundle.simulation.period.end_date.isoformat(),
            "SIMULATION_RUN_ID": run_id,
        }
        sql_records = _execute_sql_contracts(
            connection,
            project_root=root,
            replacements=replacements,
        )
        _make_raw_views_portable(connection, raw_path=raw_path, project_root=root)
        object_counts = _object_counts(connection)
        export_manifest = export_powerbi_package(
            connection,
            export_root=staging_export_dir,
            simulation_run_id=run_id,
            profile=profile,
        )
        connection.execute("CHECKPOINT")
        connection.close()
        connection = None

        validation_report = validate_analytics_database(
            bundle,
            database_path=staging_database_path,
            raw_run_path=raw_path,
            export_root=staging_export_dir,
            report_path=validation_path,
        )
        if not validation_report.passed:
            failed = validation_report.to_dict()["summary"]["failed"]
            raise DatabaseBuildError(f"analytical validation failed with {failed} failed checks")

        elapsed_seconds = time.perf_counter() - timer_start
        database_bytes = staging_database_path.stat().st_size
        database_sha256 = sha256_file(staging_database_path)
        manifest = {
            "schema_version": "1.0",
            "simulation_run_id": run_id,
            "profile": profile,
            "status": "success",
            "configuration_sha256": bundle.stable_hash(),
            "raw_dataset_logical_sha256": raw_manifest["dataset_logical_sha256"],
            "source_raw_run": _relative_or_absolute(raw_path, root),
            "database": {
                "path": staging_database_path.name,
                "bytes": database_bytes,
                "sha256": database_sha256,
            },
            "sql_contracts": sql_records,
            "object_counts": object_counts,
            "powerbi_exports": {
                "tables": len(export_manifest["tables"]),
                "path": _relative_or_absolute(final_export_dir, root),
            },
            "validation": validation_report.to_dict()["summary"],
            "statistics": validation_report.statistics,
            "started_at_utc": started_at.isoformat(),
            "finished_at_utc": utc_now().isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 6),
            "dependencies": dependency_versions(),
            "synthetic_scope": "offline synthetic prototype; no machine control",
        }
        write_manifest(staging_database_dir / "build_manifest.json", manifest)
        _atomic_promote(staging_database_dir, final_database_dir)
        try:
            _atomic_promote(staging_export_dir, final_export_dir)
        except Exception:
            _safe_remove_tree(final_database_dir, analytics_parent)
            raise

        final_database_path = final_database_dir / "steelflow.duckdb"
        manifest_path = final_database_dir / "build_manifest.json"
        return DatabaseBuildResult(
            simulation_run_id=run_id,
            database_path=final_database_path,
            export_path=final_export_dir,
            manifest_path=manifest_path,
            validation_path=validation_path,
            object_counts=object_counts,
            elapsed_seconds=elapsed_seconds,
        )
    except Exception as exc:
        if connection is not None:
            connection.close()
        _safe_remove_tree(staging_database_dir, analytics_parent)
        _safe_remove_tree(staging_export_dir, export_parent)
        if isinstance(exc, DatabaseBuildError):
            raise
        raise DatabaseBuildError(f"analytical build failed: {exc}") from exc
