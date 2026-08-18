"""Validation for the reproducible Power BI hand-off package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_TABLES = {
    "dim_asset",
    "dim_date",
    "dim_line",
    "dim_product",
    "dim_shift",
    "fact_asset_condition",
    "fact_downtime",
    "fact_energy",
    "fact_line_shift",
    "fact_losses",
    "fact_maintenance",
    "fact_order",
    "fact_quality",
}

REQUIRED_MEASURES = {
    "Good Tonnes",
    "Productive Hours",
    "TBH",
    "FPY",
    "Availability",
    "Performance",
    "Quality",
    "OEE",
    "Scrap Rate",
    "Rework Rate",
    "Energy kWh",
    "Energy per Good Tonne",
    "Unplanned Downtime Minutes",
    "Quality Characteristic Mean",
    "Simulated Mechanical Conformance",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_powerbi_package(project_root: Path, export_root: Path) -> dict[str, Any]:
    """Validate tracked hand-off assets plus generated exports and their checksums."""
    root = project_root.resolve()
    package_root = root / "powerbi"
    errors: list[str] = []

    tracked_files = {
        "theme": package_root / "theme" / "steelflow-industrial.json",
        "wireframe": package_root / "WIREFRAME.md",
        "checklist": package_root / "PACKAGE_CHECKLIST.md",
        "relationships": package_root / "RELATIONSHIPS.md",
        "power_query": package_root / "load_export_csv.pq",
        "measures": package_root / "measures" / "steelflow_measures.dax",
    }
    for label, path in tracked_files.items():
        if not path.is_file():
            errors.append(f"arquivo {label} ausente: {path}")

    if tracked_files["theme"].is_file():
        try:
            theme = json.loads(tracked_files["theme"].read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"tema JSON inválido: {exc}")
        else:
            if theme.get("name") != "SteelFlow Industrial":
                errors.append("tema Power BI sem o nome contratado")
            if len(theme.get("dataColors", [])) < 6:
                errors.append("tema Power BI precisa de ao menos seis cores de dados")

    if tracked_files["measures"].is_file():
        dax = tracked_files["measures"].read_text(encoding="utf-8")
        missing_measures = sorted(
            measure for measure in REQUIRED_MEASURES if f"{measure} =" not in dax
        )
        if missing_measures:
            errors.append(f"medidas DAX ausentes: {', '.join(missing_measures)}")
        if "DIVIDE (" not in dax:
            errors.append("medidas DAX não usam divisão segura")

    if tracked_files["relationships"].is_file():
        relationships = tracked_files["relationships"].read_text(encoding="utf-8")
        missing_relationship_tables = sorted(
            table for table in EXPECTED_TABLES if f"`{table}`" not in relationships
        )
        if missing_relationship_tables:
            errors.append(
                "tabelas ausentes na documentação de relações: "
                + ", ".join(missing_relationship_tables)
            )
        if "`1:*`" not in relationships:
            errors.append("cardinalidade 1:* não está documentada")

    if tracked_files["power_query"].is_file():
        power_query = tracked_files["power_query"].read_text(encoding="utf-8")
        for token in ("SteelFlowExportRoot", "Csv.Document", "File.Contents", "Encoding = 65001"):
            if token not in power_query:
                errors.append(f"Power Query sem o token contratado: {token}")

    if tracked_files["wireframe"].is_file():
        wireframe = tracked_files["wireframe"].read_text(encoding="utf-8")
        for page in (
            "Executive Overview",
            "Quality & Losses",
            "Energy & Downtime",
            "Reliability & Governance",
        ):
            if page not in wireframe:
                errors.append(f"wireframe sem a página: {page}")

    manifest_path = export_root / "export_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"manifest do Power BI indisponível ou inválido: {exc}")
        manifest = {}

    tables = manifest.get("tables", {})
    if set(tables) != EXPECTED_TABLES:
        errors.append("o manifest não contém exatamente as 5 dimensões e 8 fatos")
    checked_files = 0
    checked_bytes = 0
    for table_name, table in tables.items():
        for file_format in ("csv", "parquet"):
            record = table.get("files", {}).get(file_format, {})
            file_path = export_root / str(record.get("path", ""))
            if not file_path.is_file():
                errors.append(f"export ausente: {table_name}.{file_format}")
                continue
            expected_bytes = record.get("bytes")
            actual_bytes = file_path.stat().st_size
            if expected_bytes != actual_bytes:
                errors.append(f"tamanho divergente: {table_name}.{file_format}")
            if record.get("sha256") != _sha256(file_path):
                errors.append(f"checksum divergente: {table_name}.{file_format}")
            checked_files += 1
            checked_bytes += actual_bytes

    return {
        "status": "PASS" if not errors else "ERROR",
        "ready": not errors,
        "tables": len(tables),
        "dimensions": sum(name.startswith("dim_") for name in tables),
        "facts": sum(name.startswith("fact_") for name in tables),
        "files_verified": checked_files,
        "bytes_verified": checked_bytes,
        "errors": errors,
        "pbix_declared": False,
    }
