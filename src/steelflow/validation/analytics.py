"""Reconciliation and star-schema validation for the Phase 3 DuckDB build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.curation.exports import POWERBI_EXPORTS, load_export_manifest
from steelflow.generation.generator import load_manifest
from steelflow.generation.schemas import EXPECTED_TABLES
from steelflow.generation.writer import sha256_file
from steelflow.validation.raw_data import ValidationReport


def _scalar(connection: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def _add_zero_check(
    report: ValidationReport,
    connection: duckdb.DuckDBPyConnection,
    check_id: str,
    sql: str,
    detail: str,
) -> None:
    violations = int(_scalar(connection, sql))
    report.add(
        check_id,
        passed=violations == 0,
        observed=violations,
        expected=0,
        detail=detail,
    )


def _add_close_check(
    report: ValidationReport,
    check_id: str,
    observed: float,
    expected: float,
    detail: str,
    *,
    tolerance: float = 1e-8,
) -> None:
    report.add(
        check_id,
        passed=abs(observed - expected) <= tolerance,
        observed=observed,
        expected=expected,
        detail=detail,
    )


def validate_analytics_database(
    bundle: ProjectConfigBundle,
    *,
    database_path: Path,
    raw_run_path: Path,
    export_root: Path,
    report_path: Path,
) -> ValidationReport:
    """Validate one database build and its Power BI exports."""

    raw_manifest = load_manifest(raw_run_path / "run_manifest.json")
    run_id = raw_manifest["simulation_run_id"]
    report = ValidationReport(
        simulation_run_id=run_id,
        profile=bundle.simulation.profile.value,
        checked_at_utc=datetime.now(tz=UTC).isoformat(),
    )
    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("SET TimeZone='UTC'")
    try:
        schemas = {
            row[0]
            for row in connection.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        expected_schemas = {"raw", "curated", "analytics", "features", "model_outputs", "metadata"}
        report.add(
            "database.schemas",
            passed=expected_schemas <= schemas,
            observed=sorted(expected_schemas & schemas),
            expected=sorted(expected_schemas),
            detail="All contracted analytical layers must exist.",
        )

        build_info = connection.execute(
            "SELECT simulation_run_id, profile, configuration_sha256 FROM metadata.build_info"
        ).fetchone()
        report.add(
            "database.lineage",
            passed=build_info == (run_id, bundle.simulation.profile.value, bundle.stable_hash()),
            observed=build_info,
            expected=(run_id, bundle.simulation.profile.value, bundle.stable_hash()),
            detail="Database lineage must match the raw run and configuration bundle.",
        )

        required_kpis = {
            "availability",
            "energy_per_good_tonne",
            "fpy",
            "good_tonnes",
            "next_window_downtime_probability",
            "oee",
            "outer_diameter_deviation",
            "ovality",
            "performance",
            "productive_hours",
            "quality",
            "rework_rate",
            "scrap_rate",
            "simulated_mechanical_conformance",
            "tbh",
            "unplanned_downtime",
            "wall_eccentricity",
        }
        observed_kpis = {
            row[0]
            for row in connection.execute("SELECT kpi_name FROM analytics.kpi_catalog").fetchall()
        }
        report.add(
            "kpi_catalog.required_indicators",
            passed=observed_kpis == required_kpis,
            observed=sorted(observed_kpis),
            expected=sorted(required_kpis),
            detail="The catalog must cover every required executive, quality and risk KPI.",
        )
        _add_zero_check(
            report,
            connection,
            "kpi_catalog.complete_contracts",
            "SELECT count(*) FROM analytics.kpi_catalog WHERE "
            "formula = '' OR grain = '' OR unit = '' OR filters = '' OR "
            "source_fields = '' OR zero_division = ''",
            "Each KPI must document formula, grain, unit, filters, source and zero division.",
        )

        for table_name in EXPECTED_TABLES:
            curated_count = int(_scalar(connection, f"SELECT count(*) FROM curated.{table_name}"))
            raw_count = int(raw_manifest["tables"][table_name]["rows"])
            report.add(
                f"curated_count.{table_name}",
                passed=curated_count == raw_count,
                observed=curated_count,
                expected=raw_count,
                detail="Curated materialization must preserve the validated raw row count.",
            )

        _add_zero_check(
            report,
            connection,
            "grain.order_performance",
            "SELECT count(*) FROM (SELECT order_id FROM analytics.mart_order_performance "
            "GROUP BY order_id HAVING count(*) <> 1)",
            "Order mart must contain exactly one row per order.",
        )
        _add_zero_check(
            report,
            connection,
            "grain.line_shift_performance",
            "SELECT count(*) FROM (SELECT date_key, line_key, shift_key "
            "FROM analytics.mart_line_shift_performance GROUP BY ALL HAVING count(*) <> 1)",
            "Executive mart grain must be date x line x shift.",
        )
        _add_zero_check(
            report,
            connection,
            "grain.quality_summary",
            "SELECT count(*) FROM (SELECT date_key, product_key, line_key, grade_family, "
            "characteristic FROM analytics.mart_quality_summary GROUP BY ALL HAVING count(*) <> 1)",
            "Quality mart grain must be unique.",
        )

        production_good = float(
            _scalar(connection, "SELECT sum(good_mass_t) FROM analytics.fact_production")
        )
        production_hours = float(
            _scalar(connection, "SELECT sum(productive_hours) FROM analytics.fact_production")
        )
        order_good, order_hours = connection.execute(
            "SELECT sum(good_tonnes), sum(productive_hours) FROM analytics.mart_order_performance"
        ).fetchone()
        executive_good, executive_hours = connection.execute(
            "SELECT sum(good_tonnes), sum(productive_hours) "
            "FROM analytics.mart_line_shift_performance"
        ).fetchone()
        _add_close_check(
            report,
            "reconciliation.good_tonnes.order",
            float(order_good),
            production_good,
            "Order mart good tonnes must reconcile to the tube fact.",
        )
        _add_close_check(
            report,
            "reconciliation.good_tonnes.executive",
            float(executive_good),
            production_good,
            "Executive mart good tonnes must reconcile to the tube fact.",
        )
        _add_close_check(
            report,
            "reconciliation.productive_hours.order",
            float(order_hours),
            production_hours,
            "Order mart productive hours must reconcile to the tube fact.",
        )
        _add_close_check(
            report,
            "reconciliation.productive_hours.executive",
            float(executive_hours),
            production_hours,
            "Executive mart productive hours must reconcile to the tube fact.",
        )

        fact_energy = float(
            _scalar(connection, "SELECT sum(energy_kwh) FROM analytics.fact_energy")
        )
        mart_energy = float(
            _scalar(connection, "SELECT sum(energy_kwh) FROM analytics.mart_energy_summary")
        )
        _add_close_check(
            report,
            "reconciliation.energy",
            mart_energy,
            fact_energy,
            "Energy mart must reconcile to the atomic energy fact.",
        )
        quality_count = int(_scalar(connection, "SELECT count(*) FROM analytics.fact_quality"))
        quality_summary_count = int(
            _scalar(
                connection,
                "SELECT sum(inspection_count) FROM analytics.mart_quality_summary",
            )
        )
        report.add(
            "reconciliation.quality_results",
            passed=quality_summary_count == quality_count,
            observed=quality_summary_count,
            expected=quality_count,
            detail="Aggregated inspections must reconcile to the quality fact.",
        )
        downtime_fact = float(
            _scalar(connection, "SELECT sum(duration_minutes) FROM analytics.fact_downtime")
        )
        downtime_mart = float(
            _scalar(
                connection,
                "SELECT sum(unplanned_downtime_minutes) FROM analytics.mart_downtime_maintenance",
            )
        )
        _add_close_check(
            report,
            "reconciliation.downtime",
            downtime_mart,
            downtime_fact,
            "Downtime mart must reconcile to atomic events.",
        )

        _add_zero_check(
            report,
            connection,
            "formula.order_tbh",
            "SELECT count(*) FROM analytics.mart_order_performance WHERE "
            "abs(tbh - good_tonnes / NULLIF(productive_hours, 0)) > 1e-10",
            "Order TBH must use aggregated good tonnes divided by productive hours.",
        )
        _add_zero_check(
            report,
            connection,
            "formula.executive_tbh",
            "SELECT count(*) FROM analytics.mart_line_shift_performance WHERE "
            "abs(tbh - good_tonnes / NULLIF(productive_hours, 0)) > 1e-10",
            "Executive TBH must use aggregated good tonnes divided by productive hours.",
        )
        _add_zero_check(
            report,
            connection,
            "range.oee_components",
            "SELECT count(*) FROM analytics.mart_line_shift_performance WHERE "
            "availability NOT BETWEEN 0 AND 1 OR performance NOT BETWEEN 0 AND 1 OR "
            "quality NOT BETWEEN 0 AND 1 OR oee NOT BETWEEN 0 AND 1 OR "
            "fpy NOT BETWEEN 0 AND 1 OR scrap_rate NOT BETWEEN 0 AND 1 OR "
            "rework_rate NOT BETWEEN 0 AND 1",
            "OEE components and rates must remain within [0, 1].",
        )

        _add_zero_check(
            report,
            connection,
            "feature_time.pre_order",
            "SELECT count(*) FROM features.pre_order_snapshot "
            "WHERE feature_max_source_ts > snapshot_ts",
            "Pre-order features must be available no later than the snapshot.",
        )
        _add_zero_check(
            report,
            connection,
            "feature_time.in_process",
            "SELECT count(*) FROM features.in_process_rolling_snapshot "
            "WHERE feature_max_source_ts > snapshot_ts",
            "In-process features must be available no later than the rolling snapshot.",
        )
        _add_zero_check(
            report,
            connection,
            "feature_time.asset_window",
            "SELECT count(*) FROM features.asset_window_snapshot "
            "WHERE feature_max_source_ts > snapshot_ts",
            "Historical asset-window features must stop at the prediction snapshot.",
        )
        forbidden_columns = {
            "approved_first_pass",
            "disposition",
            "good_mass_t",
            "productive_hours",
            "actual_tph",
            "measured_value",
            "passed",
        }
        snapshot_columns = {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='features'"
            ).fetchall()
        }
        leaked_columns = sorted(forbidden_columns & snapshot_columns)
        report.add(
            "feature_contract.no_post_process_columns",
            passed=not leaked_columns,
            observed=leaked_columns,
            expected=[],
            detail="Point-in-time snapshots must not expose targets or post-process fields.",
        )
        report.add(
            "feature_count.pre_order",
            passed=int(_scalar(connection, "SELECT count(*) FROM features.pre_order_snapshot"))
            == int(raw_manifest["tables"]["production_orders"]["rows"]),
            observed=int(_scalar(connection, "SELECT count(*) FROM features.pre_order_snapshot")),
            expected=int(raw_manifest["tables"]["production_orders"]["rows"]),
            detail="There must be one pre-order snapshot per order.",
        )
        report.add(
            "feature_count.in_process",
            passed=int(
                _scalar(connection, "SELECT count(*) FROM features.in_process_rolling_snapshot")
            )
            == int(raw_manifest["tables"]["tubes"]["rows"]),
            observed=int(
                _scalar(connection, "SELECT count(*) FROM features.in_process_rolling_snapshot")
            ),
            expected=int(raw_manifest["tables"]["tubes"]["rows"]),
            detail="There must be one rolling snapshot per tube.",
        )
        expected_asset_windows = bundle.simulation.period.duration_days * 15 * 12
        observed_asset_windows = int(
            _scalar(connection, "SELECT count(*) FROM features.asset_window_snapshot")
        )
        report.add(
            "feature_count.asset_window",
            passed=observed_asset_windows == expected_asset_windows,
            observed=observed_asset_windows,
            expected=expected_asset_windows,
            detail="There must be one asset snapshot per date, synthetic asset and shift.",
        )
        diagnostic_tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='analytics' AND table_name LIKE 'diagnostic_%'"
            ).fetchall()
        }
        expected_diagnostic_tables = {
            "diagnostic_daily_trend",
            "diagnostic_mix_adjustment",
            "diagnostic_process_interactions",
            "diagnostic_segment_associations",
            "diagnostic_spc_quality",
            "diagnostic_spc_tbh",
        }
        report.add(
            "diagnostics.required_tables",
            passed=diagnostic_tables == expected_diagnostic_tables,
            observed=sorted(diagnostic_tables),
            expected=sorted(expected_diagnostic_tables),
            detail="Phase 4 analytical diagnostics must be materialized reproducibly.",
        )

        star_fk_checks = (
            (
                "line_shift_date",
                "analytics.mart_line_shift_performance f LEFT JOIN analytics.dim_date d "
                "USING (date_key) WHERE d.date_key IS NULL",
            ),
            (
                "line_shift_line",
                "analytics.mart_line_shift_performance f LEFT JOIN analytics.dim_line d "
                "USING (line_key) WHERE d.line_key IS NULL",
            ),
            (
                "line_shift_shift",
                "analytics.mart_line_shift_performance f LEFT JOIN analytics.dim_shift d "
                "USING (shift_key) WHERE d.shift_key IS NULL",
            ),
            (
                "order_product",
                "analytics.mart_order_performance f LEFT JOIN analytics.dim_product d "
                "USING (product_key) WHERE d.product_key IS NULL",
            ),
        )
        for name, from_clause in star_fk_checks:
            _add_zero_check(
                report,
                connection,
                f"star_fk.{name}",
                f"SELECT count(*) FROM {from_clause}",
                "Fact foreign keys must resolve to the exported dimensions.",
            )

        view_sql = " ".join(
            str(row[0] or "")
            for row in connection.execute(
                "SELECT sql FROM duckdb_views() WHERE schema_name IN "
                "('raw','curated','analytics','features','model_outputs')"
            ).fetchall()
        ).lower()
        report.add(
            "architecture.no_ground_truth_reference",
            passed="ground_truth" not in view_sql,
            observed="ground_truth" in view_sql,
            expected=False,
            detail="Analytical database views must never reference isolated causal truth.",
        )

        export_manifest = load_export_manifest(export_root)
        export_failures: list[str] = []
        for export_name, source in POWERBI_EXPORTS.items():
            record = export_manifest["tables"][export_name]
            source_count = int(_scalar(connection, f"SELECT count(*) FROM {source}"))
            parquet_path = export_root / record["files"]["parquet"]["path"]
            csv_path = export_root / record["files"]["csv"]["path"]
            parquet_count = int(
                _scalar(
                    connection,
                    f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}')",
                )
            )
            if source_count != int(record["rows"]) or parquet_count != source_count:
                export_failures.append(f"{export_name}:row_count")
            if sha256_file(parquet_path) != record["files"]["parquet"]["sha256"]:
                export_failures.append(f"{export_name}:parquet_hash")
            if sha256_file(csv_path) != record["files"]["csv"]["sha256"]:
                export_failures.append(f"{export_name}:csv_hash")
        report.add(
            "powerbi.exports",
            passed=not export_failures,
            observed=export_failures,
            expected=[],
            detail="Every export must reconcile to its source and checksum manifest.",
        )

        global_metrics = connection.execute(
            "SELECT sum(good_mass_t) / NULLIF(sum(productive_hours), 0), "
            "avg(approved_first_pass::INTEGER), sum(good_mass_t), sum(productive_hours) "
            "FROM analytics.fact_production"
        ).fetchone()
        report.statistics = {
            "database_bytes": database_path.stat().st_size,
            "database_sha256": sha256_file(database_path),
            "global_tbh": round(float(global_metrics[0]), 6),
            "global_fpy": round(float(global_metrics[1]), 6),
            "good_tonnes": round(float(global_metrics[2]), 6),
            "productive_hours": round(float(global_metrics[3]), 6),
            "energy_kwh": round(fact_energy, 6),
            "unplanned_downtime_minutes": round(downtime_fact, 6),
            "executive_rows": int(
                _scalar(connection, "SELECT count(*) FROM analytics.mart_line_shift_performance")
            ),
            "order_rows": int(
                _scalar(connection, "SELECT count(*) FROM analytics.mart_order_performance")
            ),
            "powerbi_export_tables": len(POWERBI_EXPORTS),
        }
    finally:
        connection.close()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
