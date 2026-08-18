"""Incremental raw Parquet validation with DuckDB pushdown."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.generation.generator import load_manifest
from steelflow.generation.ids import deterministic_run_id
from steelflow.generation.schemas import EXPECTED_TABLES, TABLE_PRIMARY_KEYS
from steelflow.generation.writer import sha256_file


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    observed: Any
    expected: Any
    detail: str


@dataclass
class ValidationReport:
    simulation_run_id: str
    profile: str
    checked_at_utc: str
    checks: list[CheckResult] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(check.status == "PASS" for check in self.checks)

    def add(
        self,
        check_id: str,
        *,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str,
    ) -> None:
        self.checks.append(
            CheckResult(
                check_id=check_id,
                status="PASS" if passed else "FAIL",
                observed=observed,
                expected=expected,
                detail=detail,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "simulation_run_id": self.simulation_run_id,
            "profile": self.profile,
            "checked_at_utc": self.checked_at_utc,
            "status": "PASS" if self.passed else "FAIL",
            "summary": {
                "checks": len(self.checks),
                "passed": sum(check.status == "PASS" for check in self.checks),
                "failed": sum(check.status == "FAIL" for check in self.checks),
            },
            "statistics": self.statistics,
            "checks": [check.__dict__ for check in self.checks],
        }


def expected_run_path(bundle: ProjectConfigBundle, project_root: Path) -> Path:
    config = bundle.simulation
    run_id = deterministic_run_id(
        config.profile.value,
        config.generator_version,
        config.random_seed,
        bundle.stable_hash(),
    )
    return project_root / config.output.base_path / config.profile.value / run_id


def _parquet_scan(run_path: Path, table_name: str) -> str:
    pattern = (run_path / table_name / "**" / "*.parquet").as_posix().replace("'", "''")
    return f"read_parquet('{pattern}', union_by_name=true, hive_partitioning=false)"


def _scalar(connection: duckdb.DuckDBPyConnection, sql: str) -> Any:
    result = connection.execute(sql).fetchone()
    return None if result is None else result[0]


def _expected_counts(bundle: ProjectConfigBundle) -> dict[str, int]:
    targets = bundle.simulation.volume_targets
    return {
        "dim_products": 12,
        "dim_lines": 3,
        "dim_shifts": 3,
        "dim_assets": 15,
        "feature_availability": len(bundle.feature_availability.features),
        "production_orders": targets.orders,
        "billet_batches": targets.orders,
        "tubes": targets.tubes,
        "process_parameters": targets.tubes,
        "stage_events": targets.stage_events,
        "sensor_windows": targets.sensor_windows,
        "quality_results": targets.quality_results,
        "energy_events": targets.tubes * 3,
        "downtime_events": targets.downtime_events,
    }


def _check_query_zero(
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


def _validate_manifest_files(
    report: ValidationReport,
    run_path: Path,
    manifest: dict[str, Any],
) -> None:
    mismatches: list[str] = []
    missing: list[str] = []
    for summary in manifest["tables"].values():
        for file_record in summary["files"]:
            file_path = run_path / file_record["path"]
            if not file_path.is_file():
                missing.append(file_record["path"])
            elif sha256_file(file_path) != file_record["sha256"]:
                mismatches.append(file_record["path"])
    report.add(
        "physical_file_checksums",
        passed=not missing and not mismatches,
        observed={"missing": missing, "mismatched": mismatches},
        expected={"missing": [], "mismatched": []},
        detail="Every Parquet file must match its manifest SHA-256.",
    )
    manifest_path = run_path / "run_manifest.json"
    sidecar_path = manifest_path.with_suffix(".sha256")
    sidecar_digest = (
        sidecar_path.read_text(encoding="ascii").split()[0] if sidecar_path.is_file() else None
    )
    current_digest = sha256_file(manifest_path)
    report.add(
        "manifest_checksum",
        passed=sidecar_digest == current_digest,
        observed=sidecar_digest,
        expected=current_digest,
        detail="Manifest sidecar must match the manifest content.",
    )


def validate_raw_dataset(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    run_path: Path | None = None,
    report_path: Path | None = None,
) -> ValidationReport:
    """Validate one generated raw run without reading isolated causal truth."""

    config = bundle.simulation
    run_path = (run_path or expected_run_path(bundle, project_root)).resolve()
    manifest_path = run_path / "run_manifest.json"
    manifest = load_manifest(manifest_path)
    report = ValidationReport(
        simulation_run_id=str(manifest.get("simulation_run_id", "unknown")),
        profile=config.profile.value,
        checked_at_utc=datetime.now(tz=UTC).isoformat(),
    )
    expected_run_id = deterministic_run_id(
        config.profile.value,
        config.generator_version,
        config.random_seed,
        bundle.stable_hash(),
    )
    report.add(
        "manifest_status",
        passed=manifest.get("status") == "success",
        observed=manifest.get("status"),
        expected="success",
        detail="Only completed atomic runs are valid.",
    )
    report.add(
        "simulation_run_id",
        passed=manifest.get("simulation_run_id") == expected_run_id,
        observed=manifest.get("simulation_run_id"),
        expected=expected_run_id,
        detail="Run ID must be deterministic from profile, version, seed and configuration.",
    )
    report.add(
        "configuration_sha256",
        passed=manifest.get("configuration_sha256") == bundle.stable_hash(),
        observed=manifest.get("configuration_sha256"),
        expected=bundle.stable_hash(),
        detail="Manifest must refer to the exact validated configuration bundle.",
    )
    manifest_tables = set(manifest.get("tables", {}))
    report.add(
        "expected_tables",
        passed=manifest_tables == set(EXPECTED_TABLES),
        observed=sorted(manifest_tables),
        expected=sorted(EXPECTED_TABLES),
        detail="Raw run must contain every contracted public table and no causal truth table.",
    )
    report.add(
        "causal_truth_isolation",
        passed=not (run_path / "tube_causal_truth").exists()
        and "tube_causal_truth" not in manifest_tables,
        observed="isolated" if "tube_causal_truth" not in manifest_tables else "present_in_raw",
        expected="isolated",
        detail="Causal truth is prohibited from the raw analytical run.",
    )
    _validate_manifest_files(report, run_path, manifest)

    connection = duckdb.connect(":memory:")
    connection.execute("SET threads TO 2")
    expected_counts = _expected_counts(bundle)
    observed_counts: dict[str, int] = {}
    try:
        for table_name in EXPECTED_TABLES:
            scan = _parquet_scan(run_path, table_name)
            count = int(_scalar(connection, f"SELECT count(*) FROM {scan}"))
            observed_counts[table_name] = count
            manifest_count = int(manifest["tables"][table_name]["rows"])
            if table_name == "maintenance_events":
                expected = "> 0"
                count_passed = count > 0
            else:
                expected = expected_counts[table_name]
                count_passed = count == expected
            report.add(
                f"row_count.{table_name}",
                passed=count_passed and count == manifest_count,
                observed={"parquet": count, "manifest": manifest_count},
                expected=expected,
                detail="Physical count, manifest count and configured target must reconcile.",
            )

            primary_key = TABLE_PRIMARY_KEYS[table_name]
            distinct_count, null_count = connection.execute(
                f"SELECT count(DISTINCT {primary_key}), "
                f"count(*) FILTER (WHERE {primary_key} IS NULL) FROM {scan}"
            ).fetchone()
            report.add(
                f"primary_key.{table_name}",
                passed=int(distinct_count) == count and int(null_count) == 0,
                observed={"distinct": int(distinct_count), "null": int(null_count)},
                expected={"distinct": count, "null": 0},
                detail=f"{primary_key} must be unique and non-null.",
            )
            foreign_run_ids = int(
                _scalar(
                    connection,
                    f"SELECT count(*) FROM {scan} WHERE simulation_run_id <> "
                    f"'{expected_run_id}' OR simulation_run_id IS NULL",
                )
            )
            report.add(
                f"lineage.{table_name}",
                passed=foreign_run_ids == 0,
                observed=foreign_run_ids,
                expected=0,
                detail="Every record must carry the current simulation_run_id.",
            )

        orders = _parquet_scan(run_path, "production_orders")
        billets = _parquet_scan(run_path, "billet_batches")
        tubes = _parquet_scan(run_path, "tubes")
        process = _parquet_scan(run_path, "process_parameters")
        stages = _parquet_scan(run_path, "stage_events")
        sensors = _parquet_scan(run_path, "sensor_windows")
        quality = _parquet_scan(run_path, "quality_results")
        energy = _parquet_scan(run_path, "energy_events")
        downtime = _parquet_scan(run_path, "downtime_events")
        maintenance = _parquet_scan(run_path, "maintenance_events")
        products = _parquet_scan(run_path, "dim_products")
        lines = _parquet_scan(run_path, "dim_lines")
        shifts = _parquet_scan(run_path, "dim_shifts")
        assets = _parquet_scan(run_path, "dim_assets")

        foreign_keys = (
            ("orders_product", orders, "product_code", products, "product_code"),
            ("orders_line", orders, "line_id", lines, "line_id"),
            ("orders_shift", orders, "shift_id", shifts, "shift_id"),
            ("billets_order", billets, "order_id", orders, "order_id"),
            ("tubes_order", tubes, "order_id", orders, "order_id"),
            ("tubes_billet", tubes, "billet_batch_id", billets, "billet_batch_id"),
            ("process_tube", process, "tube_id", tubes, "tube_id"),
            ("stages_tube", stages, "tube_id", tubes, "tube_id"),
            ("sensors_tube", sensors, "tube_id", tubes, "tube_id"),
            ("quality_tube", quality, "tube_id", tubes, "tube_id"),
            ("energy_tube", energy, "tube_id", tubes, "tube_id"),
            ("downtime_line", downtime, "line_id", lines, "line_id"),
            ("downtime_asset", downtime, "asset_id", assets, "asset_id"),
            ("maintenance_line", maintenance, "line_id", lines, "line_id"),
            ("maintenance_asset", maintenance, "asset_id", assets, "asset_id"),
        )
        for check_id, child, child_key, parent, parent_key in foreign_keys:
            _check_query_zero(
                report,
                connection,
                f"foreign_key.{check_id}",
                f"SELECT count(*) FROM {child} c LEFT JOIN {parent} p "
                f"ON c.{child_key}=p.{parent_key} WHERE p.{parent_key} IS NULL",
                f"{child_key} must resolve to {parent_key}.",
            )

        temporal_checks = (
            ("orders", f"SELECT count(*) FROM {orders} WHERE release_ts > scheduled_start_ts"),
            ("tubes", f"SELECT count(*) FROM {tubes} WHERE actual_start_ts >= actual_end_ts"),
            ("stages", f"SELECT count(*) FROM {stages} WHERE event_start_ts > event_end_ts"),
            (
                "sensors",
                f"SELECT count(*) FROM {sensors} WHERE window_start_ts >= window_end_ts "
                "OR feature_available_at_ts < window_end_ts",
            ),
            (
                "downtime",
                f"SELECT count(*) FROM {downtime} WHERE event_start_ts >= event_end_ts",
            ),
            (
                "maintenance",
                f"SELECT count(*) FROM {maintenance} WHERE actual_start_ts >= actual_end_ts "
                "OR scheduled_start_ts > actual_start_ts",
            ),
        )
        for name, sql in temporal_checks:
            _check_query_zero(
                report,
                connection,
                f"temporal_order.{name}",
                sql,
                "Start, end and availability timestamps must be point-in-time coherent.",
            )

        domain_checks = (
            (
                "tube_disposition",
                f"SELECT count(*) FROM {tubes} WHERE disposition NOT IN "
                "('FIRST_PASS','REWORK','SCRAP')",
            ),
            (
                "sensor_missingness",
                f"SELECT count(*) FROM {sensors} WHERE missingness_type NOT IN "
                "('NONE','MCAR','MAR','BLOCK','NOT_APPLICABLE')",
            ),
            (
                "quality_characteristic",
                f"SELECT count(*) FROM {quality} WHERE characteristic NOT IN "
                "('outer_diameter_deviation_mm','wall_eccentricity_pct','ovality_pct',"
                "'yield_strength_mpa','tensile_strength_mpa','ndt_indication_score')",
            ),
        )
        for name, sql in domain_checks:
            _check_query_zero(
                report,
                connection,
                f"domain.{name}",
                sql,
                "Categorical values must remain inside the documented domain.",
            )

        _check_query_zero(
            report,
            connection,
            "range.process_parameters",
            f"SELECT count(*) FROM {process} WHERE "
            "reheat_zone_1_temp_c NOT BETWEEN 850 AND 1320 OR "
            "reheat_zone_2_temp_c NOT BETWEEN 850 AND 1320 OR "
            "reheat_zone_3_temp_c NOT BETWEEN 850 AND 1320 OR "
            "soak_time_min NOT BETWEEN 20 AND 180 OR "
            "roll_speed_rpm NOT BETWEEN 40 AND 240 OR "
            "lubrication_flow_l_min NOT BETWEEN 5 AND 80 OR "
            "tool_wear_index NOT BETWEEN 0 AND 1 OR "
            "sensor_degradation_index NOT BETWEEN 0 AND 1",
            "Process values must respect broad internal simulated envelopes.",
        )
        _check_query_zero(
            report,
            connection,
            "completeness.sensor_statistics",
            f"SELECT count(*) FROM {sensors} WHERE "
            "(missingness_type='NONE' AND (mean_value IS NULL OR minimum_value IS NULL "
            "OR maximum_value IS NULL OR standard_deviation IS NULL OR slope IS NULL "
            "OR amplitude IS NULL OR out_of_range_pct IS NULL)) OR "
            "(missingness_type<>'NONE' AND (mean_value IS NOT NULL OR minimum_value IS NOT NULL "
            "OR maximum_value IS NOT NULL))",
            "Valid sensor windows need all summaries; missing windows must not carry values.",
        )

        missingness_rows = connection.execute(
            f"SELECT missingness_type, count(*) FROM {sensors} GROUP BY 1 ORDER BY 1"
        ).fetchall()
        missingness = {str(kind): int(count) for kind, count in missingness_rows}
        for mechanism in ("MCAR", "MAR", "BLOCK"):
            report.add(
                f"missingness_mechanism.{mechanism.lower()}",
                passed=missingness.get(mechanism, 0) > 0,
                observed=missingness.get(mechanism, 0),
                expected="> 0",
                detail=f"The {mechanism} mechanism must be present and auditable.",
            )

        fpy, rework_rate, scrap_rate = connection.execute(
            f"SELECT avg(approved_first_pass::INT), "
            "avg((disposition='REWORK')::INT), avg((disposition='SCRAP')::INT) "
            f"FROM {tubes}"
        ).fetchone()
        report.statistics = {
            "table_counts": observed_counts,
            "first_pass_yield": round(float(fpy), 6),
            "rework_rate": round(float(rework_rate), 6),
            "scrap_rate": round(float(scrap_rate), 6),
            "missingness_counts": missingness,
            "represented_products": int(
                _scalar(connection, f"SELECT count(DISTINCT product_code) FROM {orders}")
            ),
            "represented_grades": int(
                _scalar(connection, f"SELECT count(DISTINCT grade_family) FROM {orders}")
            ),
            "mean_downtime_minutes": round(
                float(_scalar(connection, f"SELECT avg(duration_minutes) FROM {downtime}")), 6
            ),
            "dataset_logical_sha256": manifest["dataset_logical_sha256"],
        }
        report.add(
            "context_coverage.products",
            passed=report.statistics["represented_products"] == 12,
            observed=report.statistics["represented_products"],
            expected=12,
            detail="Every configured product combination must occur in the fact data.",
        )
        report.add(
            "context_coverage.grades",
            passed=report.statistics["represented_grades"] == 4,
            observed=report.statistics["represented_grades"],
            expected=4,
            detail="Every configured grade code must occur in the fact data.",
        )
    finally:
        connection.close()

    report_path = report_path or (
        project_root / "artifacts" / "validation" / f"{expected_run_id}-validation.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
