from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from steelflow.config import load_config_bundle
from steelflow.curation.database import DatabaseBuildError, build_analytics_database
from steelflow.curation.exports import POWERBI_EXPORTS
from steelflow.generation.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[2]


def test_test_profile_builds_reconciled_database_and_powerbi_package(tmp_path: Path) -> None:
    bundle = load_config_bundle("test", ROOT)
    generated = generate_dataset(
        bundle,
        project_root=ROOT,
        output_base=tmp_path / "source" / "raw",
        ground_truth_base=tmp_path / "source" / "ground_truth",
    )
    first = build_analytics_database(
        bundle,
        project_root=ROOT,
        raw_run_path=generated.raw_path,
        analytics_base=tmp_path / "first" / "analytics",
        export_base=tmp_path / "first" / "exports",
    )

    validation = json.loads(first.validation_path.read_text(encoding="utf-8"))
    build_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    export_manifest = json.loads(
        (first.export_path / "export_manifest.json").read_text(encoding="utf-8")
    )
    assert validation["status"] == "PASS"
    assert validation["summary"]["failed"] == 0
    assert build_manifest["status"] == "success"
    assert build_manifest["raw_dataset_logical_sha256"] == generated.dataset_logical_sha256
    assert set(export_manifest["tables"]) == set(POWERBI_EXPORTS)
    assert all(
        (first.export_path / f"{table_name}.{extension}").is_file()
        for table_name in POWERBI_EXPORTS
        for extension in ("parquet", "csv")
    )

    connection = duckdb.connect(str(first.database_path), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM curated.tubes").fetchone()[0] == 480
        assert (
            connection.execute("SELECT count(*) FROM analytics.mart_order_performance").fetchone()[
                0
            ]
            == 24
        )
        assert (
            connection.execute("SELECT count(*) FROM features.pre_order_snapshot").fetchone()[0]
            == 24
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM features.in_process_rolling_snapshot"
            ).fetchone()[0]
            == 480
        )
        assert (
            connection.execute("SELECT count(*) FROM model_outputs.predictions").fetchone()[0] == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM model_outputs.scenario_recommendations"
            ).fetchone()[0]
            == 0
        )
        formula_violations = connection.execute(
            "SELECT count(*) FROM analytics.mart_order_performance "
            "WHERE abs(tbh - good_tonnes / NULLIF(productive_hours, 0)) > 1e-10"
        ).fetchone()[0]
        assert formula_violations == 0
    finally:
        connection.close()

    with pytest.raises(DatabaseBuildError, match="already exists"):
        build_analytics_database(
            bundle,
            project_root=ROOT,
            raw_run_path=generated.raw_path,
            analytics_base=tmp_path / "first" / "analytics",
            export_base=tmp_path / "first" / "exports",
        )

    second = build_analytics_database(
        bundle,
        project_root=ROOT,
        raw_run_path=generated.raw_path,
        analytics_base=tmp_path / "second" / "analytics",
        export_base=tmp_path / "second" / "exports",
    )
    second_export_manifest = json.loads(
        (second.export_path / "export_manifest.json").read_text(encoding="utf-8")
    )
    first_hashes = {
        table_name: record["files"] for table_name, record in export_manifest["tables"].items()
    }
    second_hashes = {
        table_name: record["files"]
        for table_name, record in second_export_manifest["tables"].items()
    }
    assert first_hashes == second_hashes


def test_sql_contracts_never_reference_private_causal_truth() -> None:
    violations = []
    for sql_path in (ROOT / "sql").rglob("*.sql"):
        if "ground_truth" in sql_path.read_text(encoding="utf-8").lower():
            violations.append(sql_path.relative_to(ROOT).as_posix())

    assert not violations
