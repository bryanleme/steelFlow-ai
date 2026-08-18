from __future__ import annotations

import ast
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from steelflow.config import load_config_bundle
from steelflow.generation.generator import GenerationError, generate_dataset
from steelflow.validation.raw_data import validate_raw_dataset

ROOT = Path(__file__).resolve().parents[2]


def test_test_profile_is_reproducible_and_valid(tmp_path: Path) -> None:
    bundle = load_config_bundle("test", ROOT)
    first = generate_dataset(
        bundle,
        project_root=ROOT,
        output_base=tmp_path / "first" / "raw",
        ground_truth_base=tmp_path / "first" / "ground_truth",
    )
    second = generate_dataset(
        bundle,
        project_root=ROOT,
        output_base=tmp_path / "second" / "raw",
        ground_truth_base=tmp_path / "second" / "ground_truth",
    )

    assert first.simulation_run_id == second.simulation_run_id
    assert first.dataset_logical_sha256 == second.dataset_logical_sha256
    assert first.table_counts == second.table_counts
    assert first.table_counts["production_orders"] == 24
    assert first.table_counts["tubes"] == 480
    assert first.table_counts["stage_events"] == 3456
    assert first.table_counts["sensor_windows"] == 15_360
    assert first.table_counts["quality_results"] == 2880
    assert first.table_counts["downtime_events"] == 40

    first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    assert first_manifest["dataset_logical_sha256"] == second_manifest["dataset_logical_sha256"]
    assert {name: table["logical_sha256"] for name, table in first_manifest["tables"].items()} == {
        name: table["logical_sha256"] for name, table in second_manifest["tables"].items()
    }
    assert {
        file_record["path"]: file_record["sha256"]
        for table in first_manifest["tables"].values()
        for file_record in table["files"]
    } == {
        file_record["path"]: file_record["sha256"]
        for table in second_manifest["tables"].values()
        for file_record in table["files"]
    }
    assert first_manifest["derived_seeds"] == second_manifest["derived_seeds"]
    assert first_manifest["status"] == "success"
    assert "tube_causal_truth" not in first_manifest["tables"]
    assert (first.ground_truth_path / "tube_causal_truth").is_dir()
    assert not (first.raw_path / "tube_causal_truth").exists()

    report = validate_raw_dataset(
        bundle,
        project_root=ROOT,
        run_path=first.raw_path,
        report_path=tmp_path / "validation.json",
    )
    assert report.passed, [check.check_id for check in report.checks if check.status == "FAIL"]
    assert report.statistics["represented_products"] == 12
    assert report.statistics["represented_grades"] == 4
    assert report.statistics["missingness_counts"]["MCAR"] > 0
    assert report.statistics["missingness_counts"]["MAR"] > 0
    assert report.statistics["missingness_counts"]["BLOCK"] > 0

    with pytest.raises(GenerationError, match="run already exists"):
        generate_dataset(
            bundle,
            project_root=ROOT,
            output_base=tmp_path / "first" / "raw",
            ground_truth_base=tmp_path / "first" / "ground_truth",
        )


def test_ids_and_foreign_keys_are_present_in_parquet(tmp_path: Path) -> None:
    bundle = load_config_bundle("test", ROOT)
    result = generate_dataset(
        bundle,
        project_root=ROOT,
        output_base=tmp_path / "raw",
        ground_truth_base=tmp_path / "ground_truth",
    )
    order_file = next((result.raw_path / "production_orders").rglob("*.parquet"))
    tube_file = next((result.raw_path / "tubes").rglob("*.parquet"))
    orders = pq.read_table(order_file, columns=["order_id", "product_code", "line_id"])
    tubes = pq.read_table(tube_file, columns=["tube_id", "order_id", "billet_batch_id"])

    assert orders.num_rows > 0
    assert tubes.num_rows > 0
    assert all(value.startswith("ORD-") for value in orders.column("order_id").to_pylist())
    assert all(value.startswith("TUB-") for value in tubes.column("tube_id").to_pylist())


def test_forbidden_packages_do_not_import_private_ground_truth() -> None:
    forbidden_roots = (
        ROOT / "src" / "steelflow" / "features",
        ROOT / "src" / "steelflow" / "models",
        ROOT / "src" / "steelflow" / "optimization",
    )
    violations = []
    for package_root in forbidden_roots:
        for source_file in package_root.rglob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                else:
                    continue
                if any("generation._ground_truth" in name for name in imported):
                    violations.append(str(source_file.relative_to(ROOT)))

    assert not violations, f"private causal truth imported by forbidden packages: {violations}"
