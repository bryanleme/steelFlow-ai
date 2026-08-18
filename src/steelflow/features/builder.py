"""Atomic materialization of frozen point-in-time feature packages."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.curation.lineage import resolve_current_analytics_build
from steelflow.features.contracts import FeatureContract, SnapshotContract, load_feature_contract
from steelflow.generation.manifest import dependency_versions, utc_now, write_manifest
from steelflow.generation.writer import sha256_file


class FeatureBuildError(RuntimeError):
    """Raised when a frozen feature package cannot be built atomically."""


@dataclass(frozen=True)
class FeatureBuildResult:
    simulation_run_id: str
    feature_root: Path
    manifest_path: Path
    validation_path: Path
    snapshot_rows: dict[str, int]
    elapsed_seconds: float


def _safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise FeatureBuildError(f"refusing to remove path outside feature parent: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _quoted_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _copy_query(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"COPY ({query}) TO '{_quoted_path(path)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _target_query(snapshot_name: str, coverage_end: str) -> str:
    if snapshot_name == "pre_order":
        return """
            WITH availability AS (
                SELECT order_id, max(actual_end_ts) AS target_available_at_ts
                FROM analytics.fact_production
                GROUP BY order_id
            )
            SELECT
                s.order_id AS sample_key,
                a.target_available_at_ts,
                t.tbh,
                t.fpy,
                t.energy_per_good_tonne_kwh_t,
                t.rework_rate,
                t.scrap_rate
            FROM features.pre_order_snapshot s
            JOIN analytics.mart_order_performance t USING (order_id)
            JOIN availability a USING (order_id)
            ORDER BY s.order_id
        """
    if snapshot_name == "in_process_rolling":
        return """
            WITH quality AS (
                SELECT
                    tube_id,
                    max(measured_value) FILTER (
                        WHERE characteristic = 'outer_diameter_deviation_mm'
                    ) AS outer_diameter_deviation_mm,
                    max(measured_value) FILTER (
                        WHERE characteristic = 'wall_eccentricity_pct'
                    ) AS wall_eccentricity_pct,
                    max(measured_value) FILTER (
                        WHERE characteristic = 'ovality_pct'
                    ) AS ovality_pct
                FROM analytics.fact_quality
                GROUP BY tube_id
            ),
            energy AS (
                SELECT tube_id, sum(energy_kwh) AS energy_kwh
                FROM analytics.fact_energy
                GROUP BY tube_id
            )
            SELECT
                s.tube_id AS sample_key,
                p.actual_end_ts AS target_available_at_ts,
                p.actual_tph,
                p.approved_first_pass,
                (p.disposition = 'REWORK') AS is_rework,
                (p.disposition = 'SCRAP') AS is_scrap,
                e.energy_kwh / NULLIF(p.good_mass_t, 0) AS energy_per_good_tonne_kwh_t,
                q.outer_diameter_deviation_mm,
                q.wall_eccentricity_pct,
                q.ovality_pct
            FROM features.in_process_rolling_snapshot s
            JOIN analytics.fact_production p USING (tube_id)
            JOIN quality q USING (tube_id)
            JOIN energy e USING (tube_id)
            ORDER BY s.tube_id
        """
    if snapshot_name == "asset_window":
        return f"""
            SELECT
                s.window_id AS sample_key,
                s.snapshot_ts + INTERVAL '2 hours' AS target_available_at_ts,
                count(d.downtime_event_id) > 0 AS next_window_downtime_occurred,
                coalesce(sum(d.duration_minutes), 0.0)
                    AS next_window_downtime_duration_minutes
            FROM features.asset_window_snapshot s
            LEFT JOIN analytics.fact_downtime d
                ON d.asset_id = s.asset_id
               AND d.event_start_ts >= s.snapshot_ts
               AND d.event_start_ts < s.snapshot_ts + INTERVAL '2 hours'
            WHERE s.snapshot_ts + INTERVAL '2 hours' <= TIMESTAMPTZ '{coverage_end}'
            GROUP BY s.window_id, s.snapshot_ts
            ORDER BY s.window_id
        """
    raise FeatureBuildError(f"unsupported snapshot target query: {snapshot_name}")


def _source_filter(snapshot_name: str, coverage_end: str) -> str:
    if snapshot_name == "asset_window":
        return f"WHERE snapshot_ts + INTERVAL '2 hours' <= TIMESTAMPTZ '{coverage_end}'"
    return ""


def _snapshot_queries(
    snapshot: SnapshotContract,
    *,
    coverage_end: str,
) -> tuple[str, str, str]:
    feature_columns = ", ".join(snapshot_feature.name for snapshot_feature in snapshot.features)
    source_filter = _source_filter(snapshot.name, coverage_end)
    x_query = (
        f"SELECT {feature_columns} FROM {snapshot.source_table} "
        f"{source_filter} ORDER BY {snapshot.ordered_by}"
    )
    index_query = (
        f"SELECT {snapshot.entity_id_column} AS sample_key, "
        f"CAST({snapshot.entity_id_column} AS VARCHAR) AS entity_id, "
        f"{snapshot.snapshot_column} AS snapshot_ts, "
        f"{snapshot.max_source_timestamp_column} AS feature_max_source_ts "
        f"FROM {snapshot.source_table} {source_filter} ORDER BY {snapshot.ordered_by}"
    )
    return x_query, index_query, _target_query(snapshot.name, coverage_end)


def _assert_source_columns(
    connection: duckdb.DuckDBPyConnection,
    contract: FeatureContract,
) -> None:
    for snapshot in contract.snapshots:
        available = {
            row[0]
            for row in connection.execute(
                f"DESCRIBE SELECT * FROM {snapshot.source_table}"
            ).fetchall()
        }
        required = {
            snapshot.entity_id_column,
            snapshot.snapshot_column,
            snapshot.max_source_timestamp_column,
            snapshot.ordered_by,
            *(feature.name for feature in snapshot.features),
        }
        missing = required - available
        if missing:
            raise FeatureBuildError(
                f"snapshot {snapshot.name!r} is missing source columns: {sorted(missing)}"
            )


def build_feature_package(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    analytics_build_dir: Path | None = None,
    output_base: Path | None = None,
    overwrite: bool = False,
) -> FeatureBuildResult:
    """Materialize X/index/y Parquets for every frozen point-in-time snapshot."""

    timer_start = time.perf_counter()
    started_at = utc_now()
    root = project_root.resolve()
    analytics = resolve_current_analytics_build(
        bundle,
        project_root=root,
        build_dir_override=analytics_build_dir,
    )
    contract = load_feature_contract(root)
    profile = bundle.simulation.profile.value
    parent = (output_base or root / "data" / "features" / profile).resolve()
    directory_name = f"{analytics.simulation_run_id}-features-v{contract.contract_version}"
    final_root = parent / directory_name
    staging_root = parent / f".{directory_name}.staging"
    parent.mkdir(parents=True, exist_ok=True)
    if final_root.exists() and not overwrite:
        raise FeatureBuildError(f"feature package already exists: {final_root}; use --force")
    if overwrite:
        _safe_remove_tree(final_root, parent)
    _safe_remove_tree(staging_root, parent)
    staging_root.mkdir(parents=True, exist_ok=False)

    coverage_end = (
        bundle.simulation.period.end_date + timedelta(days=1)
    ).isoformat() + "T00:00:00+00:00"
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(analytics.database_path), read_only=True)
        connection.execute("SET TimeZone='UTC'")
        _assert_source_columns(connection, contract)
        snapshots: dict[str, Any] = {}
        snapshot_rows: dict[str, int] = {}
        for snapshot in contract.snapshots:
            x_query, index_query, y_query = _snapshot_queries(
                snapshot,
                coverage_end=coverage_end,
            )
            snapshot_root = staging_root / snapshot.name
            x_path = snapshot_root / "X.parquet"
            index_path = snapshot_root / "index.parquet"
            y_path = snapshot_root / "y.parquet"
            _copy_query(connection, x_query, x_path)
            _copy_query(connection, index_query, index_path)
            _copy_query(connection, y_query, y_path)
            row_count = int(
                connection.execute(f"SELECT count(*) FROM ({index_query})").fetchone()[0]
            )
            snapshot_rows[snapshot.name] = row_count
            snapshots[snapshot.name] = {
                "entity_grain": snapshot.entity_grain,
                "rows": row_count,
                "ordered_by": snapshot.ordered_by,
                "features": [feature.model_dump(mode="json") for feature in snapshot.features],
                "targets": list(snapshot.targets),
                "files": {
                    "X": _file_record(x_path, staging_root),
                    "index": _file_record(index_path, staging_root),
                    "y": _file_record(y_path, staging_root),
                },
            }
        connection.close()
        connection = None

        manifest = {
            "schema_version": "1.0",
            "status": "success",
            "simulation_run_id": analytics.simulation_run_id,
            "profile": profile,
            "feature_contract_version": contract.contract_version,
            "feature_contract_sha256": contract.stable_hash(),
            "feature_contract_source": "configs/feature_contract_v1.yaml",
            "analytical_database_sha256": analytics.build_manifest["database"]["sha256"],
            "preprocessing_fit_scope": contract.preprocessing_fit_scope,
            "snapshots": snapshots,
            "started_at_utc": started_at.isoformat(),
            "finished_at_utc": utc_now().isoformat(),
            "dependencies": dependency_versions(),
            "synthetic_scope": "offline synthetic prototype; no machine control",
        }
        staging_manifest_path = staging_root / "feature_manifest.json"
        write_manifest(staging_manifest_path, manifest)

        from steelflow.validation.features import validate_feature_package

        validation_path = (
            root
            / "artifacts"
            / "validation"
            / f"{analytics.simulation_run_id}-feature-validation.json"
        )
        report = validate_feature_package(
            bundle,
            contract=contract,
            database_path=analytics.database_path,
            feature_root=staging_root,
            report_path=validation_path,
        )
        if not report.passed:
            failed = report.to_dict()["summary"]["failed"]
            raise FeatureBuildError(f"feature validation failed with {failed} failed checks")

        elapsed_seconds = time.perf_counter() - timer_start
        staging_root.replace(final_root)
        return FeatureBuildResult(
            simulation_run_id=analytics.simulation_run_id,
            feature_root=final_root,
            manifest_path=final_root / "feature_manifest.json",
            validation_path=validation_path,
            snapshot_rows=snapshot_rows,
            elapsed_seconds=elapsed_seconds,
        )
    except Exception as exc:
        if connection is not None:
            connection.close()
        _safe_remove_tree(staging_root, parent)
        if isinstance(exc, FeatureBuildError):
            raise
        raise FeatureBuildError(f"feature build failed: {exc}") from exc
