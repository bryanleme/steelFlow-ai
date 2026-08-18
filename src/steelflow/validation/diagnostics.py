"""Validation of retrospective synthetic diagnostic packages."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.generation.writer import sha256_file
from steelflow.reporting.diagnostics import DIAGNOSTIC_EXPORTS
from steelflow.validation.raw_data import ValidationReport


def _scalar(connection: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def validate_diagnostic_package(
    bundle: ProjectConfigBundle,
    *,
    database_path: Path,
    diagnostic_root: Path,
    report_path: Path,
) -> ValidationReport:
    manifest = json.loads(
        (diagnostic_root / "diagnostic_manifest.json").read_text(encoding="utf-8")
    )
    report = ValidationReport(
        simulation_run_id=str(manifest["simulation_run_id"]),
        profile=bundle.simulation.profile.value,
        checked_at_utc=datetime.now(tz=UTC).isoformat(),
    )
    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("SET TimeZone='UTC'")
    try:
        report.add(
            "tables.required",
            passed=set(manifest["tables"]) == set(DIAGNOSTIC_EXPORTS),
            observed=sorted(manifest["tables"]),
            expected=sorted(DIAGNOSTIC_EXPORTS),
            detail=(
                "The package must cover trends, mix, SPC, interactions, associations and Pareto."
            ),
        )
        export_failures = []
        for name, source in DIAGNOSTIC_EXPORTS.items():
            record = manifest["tables"][name]
            source_count = int(_scalar(connection, f"SELECT count(*) FROM {source}"))
            if source_count <= 0 or source_count != int(record["rows"]):
                export_failures.append(f"{name}:rows")
            for file_type in ("parquet", "csv"):
                file_record = record["files"][file_type]
                file_path = diagnostic_root / file_record["path"]
                if not file_path.is_file() or sha256_file(file_path) != file_record["sha256"]:
                    export_failures.append(f"{name}:{file_type}")
        report.add(
            "exports.reconciled",
            passed=not export_failures,
            observed=export_failures,
            expected=[],
            detail="Every non-empty diagnostic export must reconcile and match its checksum.",
        )

        mix_violations = int(
            _scalar(
                connection,
                "SELECT count(*) FROM analytics.diagnostic_mix_adjustment WHERE "
                "abs(mix_adjusted_tbh_gap - (actual_tbh - mix_expected_tbh)) > 1e-10",
            )
        )
        report.add(
            "formula.mix_adjustment",
            passed=mix_violations == 0,
            observed=mix_violations,
            expected=0,
            detail="Mix-adjusted gap must reconcile to actual minus expected segment TBH.",
        )
        pareto_violations = int(
            _scalar(
                connection,
                "SELECT count(*) FROM analytics.mart_loss_pareto WHERE "
                "loss_share NOT BETWEEN 0 AND 1 OR cumulative_loss_share NOT BETWEEN 0 AND 1",
            )
        )
        report.add(
            "range.loss_pareto",
            passed=pareto_violations == 0,
            observed=pareto_violations,
            expected=0,
            detail="Loss shares and cumulative shares must remain within [0, 1].",
        )
        spc_violations = int(
            _scalar(
                connection,
                "SELECT count(*) FROM analytics.diagnostic_spc_tbh WHERE "
                "lower_control_tbh > upper_control_tbh OR "
                "(control_signal AND NOT limits_reliable)",
            )
        )
        quality_spc_violations = int(
            _scalar(
                connection,
                "SELECT count(*) FROM analytics.diagnostic_spc_quality WHERE "
                "lower_control_value > upper_control_value OR "
                "(control_signal AND NOT limits_reliable)",
            )
        )
        report.add(
            "spc.guardrails",
            passed=spc_violations == 0 and quality_spc_violations == 0,
            observed={"tbh": spc_violations, "quality": quality_spc_violations},
            expected={"tbh": 0, "quality": 0},
            detail="Control signals require ordered limits and sufficient baseline support.",
        )
        small_interaction_cells = int(
            _scalar(
                connection,
                "SELECT count(*) FROM analytics.diagnostic_process_interactions "
                "WHERE tube_count <= 0",
            )
        )
        report.add(
            "interactions.support",
            passed=small_interaction_cells == 0,
            observed=small_interaction_cells,
            expected=0,
            detail="Every exported interaction cell must contain observations.",
        )
        summary_text = json.dumps(manifest.get("summary", {})).lower()
        guard_present = "not demonstrated industrial causality" in summary_text
        report.add(
            "language.non_causal",
            passed=guard_present,
            observed=guard_present,
            expected=True,
            detail="Diagnostic summary must explicitly deny demonstrated industrial causality.",
        )
        report.add(
            "architecture.no_causal_truth",
            passed="ground_truth" not in json.dumps(manifest).lower(),
            observed="ground_truth" in json.dumps(manifest).lower(),
            expected=False,
            detail="Diagnostic artifacts must not reference isolated generator truth.",
        )
        report.statistics = {
            "tables": len(DIAGNOSTIC_EXPORTS),
            "rows": {name: int(record["rows"]) for name, record in manifest["tables"].items()},
            "summary": manifest["summary"],
        }
    finally:
        connection.close()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
