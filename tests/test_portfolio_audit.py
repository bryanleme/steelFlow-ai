from __future__ import annotations

import json
from pathlib import Path

import pytest

from steelflow.reporting.portfolio import (
    PortfolioAuditError,
    _resolve_pointer,
    audit_portfolio,
)


def test_json_pointer_supports_escaping_and_lists() -> None:
    document = {"a/b": [{"c~d": 7}]}
    assert _resolve_pointer(document, "/a~1b/0/c~0d") == 7


def test_portfolio_audit_detects_changed_source_value(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "artifacts" / "source.json").write_text(
        json.dumps({"metric": 2}), encoding="utf-8"
    )
    (tmp_path / "docs" / "publication.md").write_text(
        "Valor 1. <!-- [claim:EXAMPLE] -->", encoding="utf-8"
    )
    contract = {
        "schema_version": "1.0",
        "claims": [
            {
                "id": "EXAMPLE",
                "source": "artifacts/source.json",
                "pointer": "/metric",
                "expected": 1,
                "display": "1",
                "documents": ["docs/publication.md"],
            }
        ],
        "required_disclosures": {},
        "forbidden_patterns": [],
    }
    (tmp_path / "configs" / "portfolio_claims.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )

    with pytest.raises(PortfolioAuditError, match="differs from expected"):
        audit_portfolio(tmp_path)


def test_repository_portfolio_contract() -> None:
    project_root = Path(__file__).resolve().parents[1]
    report = audit_portfolio(project_root)
    assert report["status"] == "PASS"
    assert report["claims"] == 12
