"""Reproducible descriptive and diagnostic analytical package."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.curation.lineage import resolve_current_analytics_build
from steelflow.generation.manifest import dependency_versions, utc_now, write_manifest
from steelflow.generation.writer import sha256_file

DIAGNOSTIC_EXPORTS: dict[str, str] = {
    "daily_trend": "analytics.diagnostic_daily_trend",
    "mix_adjustment": "analytics.diagnostic_mix_adjustment",
    "spc_tbh": "analytics.diagnostic_spc_tbh",
    "spc_quality": "analytics.diagnostic_spc_quality",
    "process_interactions": "analytics.diagnostic_process_interactions",
    "segment_associations": "analytics.diagnostic_segment_associations",
    "loss_pareto": "analytics.mart_loss_pareto",
}


class DiagnosticBuildError(RuntimeError):
    """Raised when the diagnostic package cannot be completed atomically."""


@dataclass(frozen=True)
class DiagnosticBuildResult:
    simulation_run_id: str
    diagnostic_root: Path
    manifest_path: Path
    validation_path: Path
    table_rows: dict[str, int]
    elapsed_seconds: float


def _safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise DiagnosticBuildError(f"refusing to remove path outside diagnostic parent: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _quoted_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _diagnostic_summary(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    global_metrics = connection.execute(
        "SELECT sum(good_mass_t) / NULLIF(sum(productive_hours), 0), "
        "avg(approved_first_pass::INTEGER) FROM analytics.fact_production"
    ).fetchone()
    trend_slope = connection.execute(
        "WITH daily AS (SELECT date_key, sum(good_mass_t) / NULLIF(sum(productive_hours), 0) "
        "AS tbh FROM analytics.fact_production GROUP BY date_key) "
        "SELECT regr_slope(tbh, date_key) FROM daily"
    ).fetchone()[0]
    mix_gap = connection.execute(
        "SELECT avg(mix_adjusted_tbh_gap), max(abs(mix_adjusted_tbh_gap)) "
        "FROM analytics.diagnostic_mix_adjustment"
    ).fetchone()
    top_loss = connection.execute(
        "SELECT loss_type, sum(loss_tonnes_equivalent) AS loss_tonnes "
        "FROM analytics.mart_loss_pareto GROUP BY loss_type "
        "ORDER BY loss_tonnes DESC, loss_type LIMIT 1"
    ).fetchone()
    spc = connection.execute(
        "SELECT sum((limits_reliable AND control_signal)::INTEGER), "
        "sum(limits_reliable::INTEGER) FROM analytics.diagnostic_spc_tbh"
    ).fetchone()
    quality_spc = connection.execute(
        "SELECT sum((limits_reliable AND control_signal)::INTEGER), "
        "sum(limits_reliable::INTEGER) FROM analytics.diagnostic_spc_quality"
    ).fetchone()
    interaction = connection.execute(
        "WITH spreads AS (SELECT product_code, grade_family, line_id, "
        "max(mean_actual_tph) - min(mean_actual_tph) AS tbh_spread "
        "FROM analytics.diagnostic_process_interactions "
        "GROUP BY product_code, grade_family, line_id) "
        "SELECT product_code, grade_family, line_id, tbh_spread FROM spreads "
        "ORDER BY tbh_spread DESC, product_code, grade_family, line_id LIMIT 1"
    ).fetchone()
    return {
        "global_tbh": round(float(global_metrics[0]), 6),
        "global_fpy": round(float(global_metrics[1]), 6),
        "daily_tbh_linear_slope": None if trend_slope is None else round(float(trend_slope), 9),
        "mean_mix_adjusted_tbh_gap": round(float(mix_gap[0]), 6),
        "maximum_absolute_mix_adjusted_tbh_gap": round(float(mix_gap[1]), 6),
        "top_loss_type": str(top_loss[0]),
        "top_loss_tonnes_equivalent": round(float(top_loss[1]), 6),
        "tbh_control_signals": int(spc[0] or 0),
        "tbh_windows_with_reliable_limits": int(spc[1] or 0),
        "quality_control_signals": int(quality_spc[0] or 0),
        "quality_rows_with_reliable_limits": int(quality_spc[1] or 0),
        "largest_interaction_tbh_spread": {
            "product_code": str(interaction[0]),
            "grade_family": str(interaction[1]),
            "line_id": str(interaction[2]),
            "tbh_spread": round(float(interaction[3]), 6),
        },
        "interpretation_guard": (
            "retrospective synthetic associations; not demonstrated industrial causality"
        ),
    }


def build_diagnostic_package(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    analytics_build_dir: Path | None = None,
    output_base: Path | None = None,
    overwrite: bool = False,
) -> DiagnosticBuildResult:
    """Export diagnostic marts with a compact, validated summary."""

    timer_start = time.perf_counter()
    started_at = utc_now()
    root = project_root.resolve()
    analytics = resolve_current_analytics_build(
        bundle,
        project_root=root,
        build_dir_override=analytics_build_dir,
    )
    profile = bundle.simulation.profile.value
    parent = (output_base or root / "artifacts" / "diagnostics" / profile).resolve()
    final_root = parent / analytics.simulation_run_id
    staging_root = parent / f".{analytics.simulation_run_id}.staging"
    parent.mkdir(parents=True, exist_ok=True)
    if final_root.exists() and not overwrite:
        raise DiagnosticBuildError(f"diagnostic package already exists: {final_root}; use --force")
    if overwrite:
        _safe_remove_tree(final_root, parent)
    _safe_remove_tree(staging_root, parent)
    staging_root.mkdir(parents=True, exist_ok=False)

    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(analytics.database_path), read_only=True)
        connection.execute("SET TimeZone='UTC'")
        table_records: dict[str, Any] = {}
        table_rows: dict[str, int] = {}
        for export_name, source in DIAGNOSTIC_EXPORTS.items():
            parquet_path = staging_root / f"{export_name}.parquet"
            csv_path = staging_root / f"{export_name}.csv"
            connection.execute(
                f"COPY (SELECT * FROM {source} ORDER BY ALL) TO '{_quoted_path(parquet_path)}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            connection.execute(
                f"COPY (SELECT * FROM {source} ORDER BY ALL) TO '{_quoted_path(csv_path)}' "
                "(FORMAT CSV, HEADER TRUE)"
            )
            rows = int(connection.execute(f"SELECT count(*) FROM {source}").fetchone()[0])
            table_rows[export_name] = rows
            table_records[export_name] = {
                "source": source,
                "rows": rows,
                "files": {
                    "parquet": {
                        "path": parquet_path.name,
                        "bytes": parquet_path.stat().st_size,
                        "sha256": sha256_file(parquet_path),
                    },
                    "csv": {
                        "path": csv_path.name,
                        "bytes": csv_path.stat().st_size,
                        "sha256": sha256_file(csv_path),
                    },
                },
            }
        summary = _diagnostic_summary(connection)
        connection.close()
        connection = None

        manifest = {
            "schema_version": "1.0",
            "status": "success",
            "simulation_run_id": analytics.simulation_run_id,
            "profile": profile,
            "analytical_database_sha256": analytics.build_manifest["database"]["sha256"],
            "tables": table_records,
            "summary": summary,
            "started_at_utc": started_at.isoformat(),
            "finished_at_utc": utc_now().isoformat(),
            "dependencies": dependency_versions(),
            "synthetic_scope": "offline synthetic prototype; no machine control",
        }
        write_manifest(staging_root / "diagnostic_manifest.json", manifest)

        from steelflow.validation.diagnostics import validate_diagnostic_package

        validation_path = (
            root
            / "artifacts"
            / "validation"
            / f"{analytics.simulation_run_id}-diagnostic-validation.json"
        )
        report = validate_diagnostic_package(
            bundle,
            database_path=analytics.database_path,
            diagnostic_root=staging_root,
            report_path=validation_path,
        )
        if not report.passed:
            failed = report.to_dict()["summary"]["failed"]
            raise DiagnosticBuildError(f"diagnostic validation failed with {failed} failed checks")

        elapsed_seconds = time.perf_counter() - timer_start
        staging_root.replace(final_root)
        return DiagnosticBuildResult(
            simulation_run_id=analytics.simulation_run_id,
            diagnostic_root=final_root,
            manifest_path=final_root / "diagnostic_manifest.json",
            validation_path=validation_path,
            table_rows=table_rows,
            elapsed_seconds=elapsed_seconds,
        )
    except Exception as exc:
        if connection is not None:
            connection.close()
        _safe_remove_tree(staging_root, parent)
        if isinstance(exc, DiagnosticBuildError):
            raise
        raise DiagnosticBuildError(f"diagnostic build failed: {exc}") from exc
