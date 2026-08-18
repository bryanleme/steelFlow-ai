"""Compact, reproducible Power BI export package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from steelflow.generation.manifest import write_manifest
from steelflow.generation.writer import sha256_file

POWERBI_EXPORTS: dict[str, str] = {
    "dim_date": "analytics.pbi_dim_date",
    "dim_product": "analytics.pbi_dim_product",
    "dim_line": "analytics.pbi_dim_line",
    "dim_shift": "analytics.pbi_dim_shift",
    "dim_asset": "analytics.pbi_dim_asset",
    "fact_line_shift": "analytics.pbi_fact_line_shift",
    "fact_order": "analytics.pbi_fact_order",
    "fact_quality": "analytics.pbi_fact_quality",
    "fact_energy": "analytics.pbi_fact_energy",
    "fact_downtime": "analytics.pbi_fact_downtime",
    "fact_maintenance": "analytics.pbi_fact_maintenance",
    "fact_losses": "analytics.pbi_fact_losses",
    "fact_asset_condition": "analytics.pbi_fact_asset_condition",
}


def _quoted_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def export_powerbi_package(
    connection: duckdb.DuckDBPyConnection,
    *,
    export_root: Path,
    simulation_run_id: str,
    profile: str,
) -> dict[str, Any]:
    """Export each star-schema object to both Parquet and CSV."""

    export_root.mkdir(parents=True, exist_ok=False)
    tables: dict[str, Any] = {}
    for export_name, source in POWERBI_EXPORTS.items():
        parquet_path = export_root / f"{export_name}.parquet"
        csv_path = export_root / f"{export_name}.csv"
        connection.execute(
            f"COPY (SELECT * FROM {source} ORDER BY ALL) TO '{_quoted_path(parquet_path)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        connection.execute(
            f"COPY (SELECT * FROM {source} ORDER BY ALL) TO '{_quoted_path(csv_path)}' "
            "(FORMAT CSV, HEADER TRUE)"
        )
        row_count = int(connection.execute(f"SELECT count(*) FROM {source}").fetchone()[0])
        tables[export_name] = {
            "source": source,
            "rows": row_count,
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

    manifest = {
        "schema_version": "1.0",
        "simulation_run_id": simulation_run_id,
        "profile": profile,
        "status": "success",
        "synthetic_scope": "offline synthetic prototype; no machine control",
        "tables": tables,
        "relationships_document": "powerbi/RELATIONSHIPS.md",
        "measures_document": "powerbi/measures/steelflow_measures.dax",
    }
    write_manifest(export_root / "export_manifest.json", manifest)
    return manifest


def load_export_manifest(export_root: Path) -> dict[str, Any]:
    return json.loads((export_root / "export_manifest.json").read_text(encoding="utf-8"))
