"""Leakage, temporal and physical checks for frozen feature packages."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from steelflow.config import ProjectConfigBundle
from steelflow.features.contracts import FeatureContract
from steelflow.generation.writer import sha256_file
from steelflow.validation.raw_data import ValidationReport


def _scan(path: Path) -> str:
    quoted = path.resolve().as_posix().replace("'", "''")
    return f"read_parquet('{quoted}')"


def _scalar(connection: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def validate_feature_package(
    bundle: ProjectConfigBundle,
    *,
    contract: FeatureContract,
    database_path: Path,
    feature_root: Path,
    report_path: Path,
) -> ValidationReport:
    """Validate feature matrices without importing private synthetic causal truth."""

    manifest_path = feature_root / "feature_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = str(manifest["simulation_run_id"])
    report = ValidationReport(
        simulation_run_id=run_id,
        profile=bundle.simulation.profile.value,
        checked_at_utc=datetime.now(tz=UTC).isoformat(),
    )
    report.add(
        "contract.hash",
        passed=manifest.get("feature_contract_sha256") == contract.stable_hash(),
        observed=manifest.get("feature_contract_sha256"),
        expected=contract.stable_hash(),
        detail="Feature package must use the exact frozen versioned contract.",
    )
    report.add(
        "contract.fold_train_only",
        passed=manifest.get("preprocessing_fit_scope") == "fold_train_only",
        observed=manifest.get("preprocessing_fit_scope"),
        expected="fold_train_only",
        detail="Future preprocessors may only be fitted inside a training fold.",
    )

    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("SET TimeZone='UTC'")
    statistics: dict[str, Any] = {"snapshots": {}}
    try:
        for snapshot in contract.snapshots:
            record = manifest["snapshots"][snapshot.name]
            x_path = feature_root / record["files"]["X"]["path"]
            index_path = feature_root / record["files"]["index"]["path"]
            y_path = feature_root / record["files"]["y"]["path"]
            x_columns = [
                row[0]
                for row in connection.execute(f"DESCRIBE SELECT * FROM {_scan(x_path)}").fetchall()
            ]
            y_columns = [
                row[0]
                for row in connection.execute(f"DESCRIBE SELECT * FROM {_scan(y_path)}").fetchall()
            ]
            expected_x = [feature.name for feature in snapshot.features]
            expected_y = ["sample_key", "target_available_at_ts", *snapshot.targets]
            report.add(
                f"columns.{snapshot.name}.X",
                passed=x_columns == expected_x,
                observed=x_columns,
                expected=expected_x,
                detail="X must contain only the ordered frozen feature list.",
            )
            report.add(
                f"columns.{snapshot.name}.y",
                passed=y_columns == expected_y,
                observed=y_columns,
                expected=expected_y,
                detail="Targets and availability timestamp must remain outside X.",
            )

            x_count = int(_scalar(connection, f"SELECT count(*) FROM {_scan(x_path)}"))
            index_count = int(_scalar(connection, f"SELECT count(*) FROM {_scan(index_path)}"))
            y_count = int(_scalar(connection, f"SELECT count(*) FROM {_scan(y_path)}"))
            expected_count = int(record["rows"])
            report.add(
                f"rows.{snapshot.name}",
                passed=x_count == index_count == y_count == expected_count,
                observed={"X": x_count, "index": index_count, "y": y_count},
                expected=expected_count,
                detail="X, index and y must preserve one aligned deterministic row order.",
            )
            duplicate_keys = int(
                _scalar(
                    connection,
                    f"SELECT count(*) FROM (SELECT sample_key FROM {_scan(index_path)} "
                    "GROUP BY sample_key HAVING count(*) <> 1)",
                )
            )
            unmatched_keys = int(
                _scalar(
                    connection,
                    f"SELECT count(*) FROM {_scan(index_path)} i FULL JOIN {_scan(y_path)} y "
                    "USING (sample_key) WHERE i.sample_key IS NULL OR y.sample_key IS NULL",
                )
            )
            report.add(
                f"keys.{snapshot.name}",
                passed=duplicate_keys == 0 and unmatched_keys == 0,
                observed={"duplicates": duplicate_keys, "unmatched": unmatched_keys},
                expected={"duplicates": 0, "unmatched": 0},
                detail="Index and targets must share unique sample keys.",
            )

            future_features = int(
                _scalar(
                    connection,
                    f"SELECT count(*) FROM {_scan(index_path)} "
                    "WHERE feature_max_source_ts > snapshot_ts",
                )
            )
            premature_targets = int(
                _scalar(
                    connection,
                    f"SELECT count(*) FROM {_scan(index_path)} i JOIN {_scan(y_path)} y "
                    "USING (sample_key) WHERE y.target_available_at_ts <= i.snapshot_ts",
                )
            )
            report.add(
                f"time.{snapshot.name}.features",
                passed=future_features == 0,
                observed=future_features,
                expected=0,
                detail="No feature source timestamp may exceed the prediction snapshot.",
            )
            report.add(
                f"time.{snapshot.name}.targets",
                passed=premature_targets == 0,
                observed=premature_targets,
                expected=0,
                detail="Targets must become available strictly after the prediction snapshot.",
            )

            forbidden = {
                "actual_tph",
                "approved_first_pass",
                "asset_id",
                "disposition",
                "good_mass_t",
                "order_id",
                "productive_hours",
                "simulation_run_id",
                "tube_id",
                "window_id",
                *snapshot.targets,
            }
            leaked = sorted(forbidden & set(x_columns))
            report.add(
                f"leakage.{snapshot.name}.forbidden_columns",
                passed=not leaked,
                observed=leaked,
                expected=[],
                detail="Entity IDs, lineage, targets and direct proxies are prohibited from X.",
            )

            file_failures = []
            for file_name, file_record in record["files"].items():
                path = feature_root / file_record["path"]
                if not path.is_file() or sha256_file(path) != file_record["sha256"]:
                    file_failures.append(file_name)
            report.add(
                f"physical.{snapshot.name}",
                passed=not file_failures,
                observed=file_failures,
                expected=[],
                detail="Each feature artifact must match its manifest checksum.",
            )

            stats: dict[str, Any] = {
                "rows": expected_count,
                "features": len(expected_x),
                "targets": len(snapshot.targets),
            }
            if "approved_first_pass" in snapshot.targets:
                stats["first_pass_rate"] = round(
                    float(
                        _scalar(
                            connection,
                            f"SELECT avg(approved_first_pass::INTEGER) FROM {_scan(y_path)}",
                        )
                    ),
                    6,
                )
            if "next_window_downtime_occurred" in snapshot.targets:
                stats["next_window_downtime_rate"] = round(
                    float(
                        _scalar(
                            connection,
                            "SELECT avg(next_window_downtime_occurred::INTEGER) "
                            f"FROM {_scan(y_path)}",
                        )
                    ),
                    6,
                )
            statistics["snapshots"][snapshot.name] = stats
    finally:
        connection.close()

    report.add(
        "architecture.no_causal_truth",
        passed="ground_truth" not in json.dumps(manifest).lower(),
        observed="ground_truth" in json.dumps(manifest).lower(),
        expected=False,
        detail="Feature manifests and paths must not reference isolated causal truth.",
    )
    report.statistics = statistics
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
