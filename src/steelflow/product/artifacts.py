"""Resolve and validate the frozen artifacts consumed by the analytical product."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steelflow.config import ProjectConfigBundle
from steelflow.features.contracts import load_feature_contract
from steelflow.models.contracts import load_modeling_config
from steelflow.models.pipeline import resolve_model_root
from steelflow.optimization.contracts import load_optimization_config
from steelflow.product.powerbi import validate_powerbi_package


class ProductArtifactError(RuntimeError):
    """Raised when a required generated artifact is unavailable or stale."""


@dataclass(frozen=True)
class ProductArtifacts:
    project_root: Path
    profile: str
    simulation_run_id: str
    analytics_database: Path
    feature_root: Path
    model_root: Path
    evaluation_root: Path
    optimization_root: Path
    powerbi_export_root: Path
    powerbi_validation: dict[str, Any]


def _load_success_manifest(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ProductArtifactError(f"{label} não encontrado: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductArtifactError(f"{label} inválido: {path}") from exc
    status = str(manifest.get("status", "")).lower()
    if status not in {"success", "pass"}:
        raise ProductArtifactError(f"{label} não está concluído com sucesso")
    return manifest


def resolve_product_artifacts(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
) -> ProductArtifacts:
    root = project_root.resolve()
    feature_contract = load_feature_contract(root)
    modeling = load_modeling_config(root)
    optimization = load_optimization_config(root)
    feature_root, model_root = resolve_model_root(
        bundle,
        root,
        modeling,
        feature_contract,
    )
    training = _load_success_manifest(model_root / "training_manifest.json", "treinamento")
    run_id = str(training["simulation_run_id"])
    if training.get("final_test_labels_used") is not False:
        raise ProductArtifactError("o treinamento não preservou o isolamento do teste final")
    evaluation_root = model_root / "evaluation"
    evaluation = _load_success_manifest(
        evaluation_root / "evaluation_manifest.json",
        "avaliação final",
    )
    if evaluation.get("evaluation_count") != 1:
        raise ProductArtifactError("a avaliação final não está congelada exatamente uma vez")
    optimization_root = (
        model_root
        / "optimization"
        / (
            f"optimization-v{optimization.optimization_version}-"
            f"{optimization.stable_hash()[:12]}"
        )
    )
    optimization_manifest = _load_success_manifest(
        optimization_root / "optimization_manifest.json",
        "otimização",
    )
    if optimization_manifest.get("published_hard_constraint_pass_rate") != 1.0:
        raise ProductArtifactError("a otimização contém cenários fora das restrições duras")
    analytics_root = root / "data" / "analytics" / bundle.simulation.profile.value / run_id
    _load_success_manifest(analytics_root / "build_manifest.json", "banco analítico")
    analytics_database = analytics_root / "steelflow.duckdb"
    if not analytics_database.is_file():
        raise ProductArtifactError(f"DuckDB não encontrado: {analytics_database}")
    export_root = root / "powerbi" / "exports" / bundle.simulation.profile.value / run_id
    export_manifest = _load_success_manifest(
        export_root / "export_manifest.json",
        "pacote Power BI",
    )
    if len(export_manifest.get("tables", {})) != 13:
        raise ProductArtifactError("o pacote Power BI não contém as 13 tabelas esperadas")
    powerbi_report = validate_powerbi_package(root, export_root)
    if not powerbi_report["ready"]:
        raise ProductArtifactError(
            "o pacote Power BI falhou na validação: "
            + "; ".join(powerbi_report["errors"])
        )
    return ProductArtifacts(
        project_root=root,
        profile=bundle.simulation.profile.value,
        simulation_run_id=run_id,
        analytics_database=analytics_database,
        feature_root=feature_root,
        model_root=model_root,
        evaluation_root=evaluation_root,
        optimization_root=optimization_root,
        powerbi_export_root=export_root,
        powerbi_validation=powerbi_report,
    )


def product_artifact_report(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
) -> dict[str, Any]:
    try:
        artifacts = resolve_product_artifacts(bundle, project_root=project_root)
    except ProductArtifactError as exc:
        return {
            "status": "ERROR",
            "ready": False,
            "profile": bundle.simulation.profile.value,
            "message": str(exc),
            "recovery_commands": [
                f"python -m steelflow generate --profile {bundle.simulation.profile.value}",
                f"python -m steelflow build-db --profile {bundle.simulation.profile.value}",
                f"python -m steelflow build-features --profile {bundle.simulation.profile.value}",
                f"python -m steelflow train --profile {bundle.simulation.profile.value}",
                f"python -m steelflow evaluate --profile {bundle.simulation.profile.value}",
                f"python -m steelflow optimize-demo --profile {bundle.simulation.profile.value}",
            ],
        }
    return {
        "status": "PASS",
        "ready": True,
        "profile": artifacts.profile,
        "simulation_run_id": artifacts.simulation_run_id,
        "analytics_database": str(artifacts.analytics_database),
        "evaluation_root": str(artifacts.evaluation_root),
        "optimization_root": str(artifacts.optimization_root),
        "powerbi_export_root": str(artifacts.powerbi_export_root),
        "powerbi_validation": artifacts.powerbi_validation,
    }
