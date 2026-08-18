from __future__ import annotations

import json
from pathlib import Path

import pytest

from steelflow.config import load_config_bundle
from steelflow.product.artifacts import ProductArtifactError, resolve_product_artifacts
from steelflow.product.powerbi import validate_powerbi_package
from steelflow.product.scenario import (
    approve_scenario,
    build_interactive_runtime,
    evaluate_interactive_scenario,
    scenario_csv_bytes,
    scenario_json_bytes,
)

ROOT = Path(__file__).resolve().parents[2]
PAGE_FILES = (
    ROOT / "app" / "Home.py",
    ROOT / "app" / "pages" / "1_Root_Cause_Explainability.py",
    ROOT / "app" / "pages" / "2_Forecast_Risk.py",
    ROOT / "app" / "pages" / "3_Scenario_Lab.py",
    ROOT / "app" / "pages" / "4_Model_Reliability.py",
)


def _mvp_artifacts():
    try:
        return resolve_product_artifacts(load_config_bundle("mvp", ROOT), project_root=ROOT)
    except ProductArtifactError as exc:
        pytest.skip(f"artefatos MVP recriáveis não estão presentes: {exc}")


def test_powerbi_package_and_all_export_checksums() -> None:
    artifacts = _mvp_artifacts()

    report = validate_powerbi_package(ROOT, artifacts.powerbi_export_root)

    assert report["status"] == "PASS", report["errors"]
    assert report["tables"] == 13
    assert report["dimensions"] == 5
    assert report["facts"] == 8
    assert report["files_verified"] == 26
    assert report["pbix_declared"] is False


def test_scenario_lab_runs_frozen_models_and_exports_human_review() -> None:
    artifacts = _mvp_artifacts()
    scenario_path = (
        artifacts.optimization_root
        / "scenarios"
        / "context-01-line_01-balanced.json"
    )
    published = json.loads(scenario_path.read_text(encoding="utf-8"))
    parameters = {
        name: specification["value"]
        for name, specification in published["parameters"].items()
    }

    runtime = build_interactive_runtime(artifacts, published["context_id"])
    evaluated = evaluate_interactive_scenario(runtime, parameters)
    approved = approve_scenario(
        evaluated,
        acknowledgement=True,
        approval_id="e2e-test",
    )

    assert evaluated["recommendation_issued"] is True
    assert evaluated["ood_assessment"]["in_distribution"] is True
    assert all(item["status"] == "PASS" for item in evaluated["constraints"])
    assert approved["human_approved"] is True
    assert approved["machine_command"] is False
    assert json.loads(scenario_json_bytes(approved))["approval"]["approval_id"] == "e2e-test"
    assert b"parameter__roll_speed_rpm" in scenario_csv_bytes(approved)


@pytest.mark.parametrize("page_file", PAGE_FILES, ids=lambda path: path.stem)
def test_streamlit_page_smoke(page_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mvp_artifacts()
    testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.setenv("STEELFLOW_PROFILE", "mvp")

    app = testing.AppTest.from_file(str(page_file), default_timeout=120).run()

    assert not app.exception, [str(exception) for exception in app.exception]
    assert app.title or app.markdown


def test_application_can_start_without_generated_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.setenv("STEELFLOW_PROFILE", "test")

    app = testing.AppTest.from_file(str(ROOT / "app" / "Home.py")).run(timeout=30)

    assert not app.exception
    rendered = " ".join(item.value for item in (*app.markdown, *app.error, *app.code))
    assert "Dados da demonstração ainda não estão disponíveis" in rendered
    assert "generate" in rendered
