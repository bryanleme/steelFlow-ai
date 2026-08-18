from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_foundation_files_are_present() -> None:
    required = {
        "README.md",
        "pyproject.toml",
        "Makefile",
        ".env.example",
        ".gitignore",
        "configs/simulation_test.yaml",
        "configs/simulation_dev.yaml",
        "configs/simulation_mvp.yaml",
        "configs/internal_specs.yaml",
        "configs/causal_rules.yaml",
        "configs/data_quality.yaml",
        "configs/feature_availability.yaml",
        "configs/feature_contract_v1.yaml",
        "configs/modeling_v1.yaml",
        "docs/IMPLEMENTATION_PLAN.md",
        "docs/DECISION_LOG.md",
        "docs/REQUIREMENTS_TRACEABILITY.md",
        "docs/RISK_REGISTER.md",
        "docs/DATA_CARD.md",
        "docs/03_DATA_DICTIONARY_V0.md",
        "docs/GENERATOR_DESIGN.md",
        "docs/ANALYTICAL_MODEL.md",
        "docs/KPI_CATALOG.md",
        "docs/DIAGNOSTIC_REPORT.md",
        "docs/FEATURE_CONTRACT.md",
        "docs/MODELING_REPORT.md",
        "docs/MODEL_CARDS.md",
        "artifacts/samples/phase_2_run_summaries.json",
        "artifacts/samples/phase_3_build_summaries.json",
        "artifacts/samples/phase_4_analysis_summaries.json",
        "artifacts/samples/phase_5_modeling_summaries.json",
        "powerbi/POWER_QUERY.md",
        "powerbi/RELATIONSHIPS.md",
        "powerbi/load_export_csv.pq",
        "powerbi/measures/steelflow_measures.dax",
        "sql/curated/010_curated_tables.sql",
        "sql/marts/020_dimensions_and_facts.sql",
        "sql/marts/030_kpis_and_marts.sql",
        "sql/marts/040_feature_snapshots.sql",
        "sql/marts/050_powerbi_views.sql",
        "sql/marts/060_diagnostics_and_asset_snapshots.sql",
        "src/steelflow/config.py",
        "src/steelflow/cli.py",
        "src/steelflow/curation/database.py",
        "src/steelflow/curation/exports.py",
        "src/steelflow/curation/lineage.py",
        "src/steelflow/features/builder.py",
        "src/steelflow/features/contracts.py",
        "src/steelflow/generation/generator.py",
        "src/steelflow/models/baselines.py",
        "src/steelflow/models/contracts.py",
        "src/steelflow/models/data.py",
        "src/steelflow/models/metrics.py",
        "src/steelflow/models/pipeline.py",
        "src/steelflow/reporting/diagnostics.py",
        "src/steelflow/validation/analytics.py",
        "src/steelflow/validation/diagnostics.py",
        "src/steelflow/validation/features.py",
        "src/steelflow/validation/ground_truth_audit.py",
        "src/steelflow/validation/models.py",
        "src/steelflow/validation/raw_data.py",
    }

    missing = sorted(path for path in required if not (ROOT / path).is_file())

    assert not missing, f"missing foundation files: {missing}"


def test_generated_data_directories_are_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for generated_path in (
        "data/raw/",
        "data/curated/",
        "data/analytics/",
        "data/features/",
        "data/model_outputs/",
        "data/ground_truth/",
        "*.duckdb",
        "artifacts/*",
    ):
        assert generated_path in gitignore
