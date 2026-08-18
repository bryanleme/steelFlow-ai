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
        "docs/IMPLEMENTATION_PLAN.md",
        "docs/DECISION_LOG.md",
        "docs/REQUIREMENTS_TRACEABILITY.md",
        "docs/RISK_REGISTER.md",
        "docs/DATA_CARD.md",
        "docs/03_DATA_DICTIONARY_V0.md",
        "docs/GENERATOR_DESIGN.md",
        "artifacts/samples/phase_2_run_summaries.json",
        "src/steelflow/config.py",
        "src/steelflow/cli.py",
        "src/steelflow/generation/generator.py",
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
