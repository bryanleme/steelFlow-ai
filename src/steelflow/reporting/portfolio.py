"""Traceable portfolio-claim and publication-language audit."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


class PortfolioAuditError(ValueError):
    """Raised when a public portfolio claim cannot be reproduced."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioAuditError(f"cannot read valid JSON from {path}: {exc}") from exc


def _resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise PortfolioAuditError(f"invalid JSON pointer: {pointer!r}")
    current = document
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(part)] if isinstance(current, list) else current[part]
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise PortfolioAuditError(f"JSON pointer {pointer!r} does not resolve") from exc
    return current


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    return actual == expected


def _safe_path(project_root: Path, relative_path: str) -> Path:
    path = (project_root / relative_path).resolve()
    if not path.is_relative_to(project_root.resolve()):
        raise PortfolioAuditError(f"path escapes project root: {relative_path}")
    return path


def audit_portfolio(project_root: Path) -> dict[str, Any]:
    """Validate numeric claims, source pointers and mandatory publication language."""

    root = project_root.resolve()
    contract_path = root / "configs" / "portfolio_claims.json"
    contract = _load_json(contract_path)
    errors: list[str] = []
    source_cache: dict[Path, Any] = {}
    document_cache: dict[Path, str] = {}
    claim_checks = 0

    for claim in contract.get("claims", []):
        claim_id = claim["id"]
        source_path = _safe_path(root, claim["source"])
        if source_path not in source_cache:
            source_cache[source_path] = _load_json(source_path)
        actual = _resolve_pointer(source_cache[source_path], claim["pointer"])
        claim_checks += 1
        if not _same_value(actual, claim["expected"]):
            errors.append(
                f"{claim_id}: source value {actual!r} differs from expected {claim['expected']!r}"
            )
        marker = f"[claim:{claim_id}]"
        for relative_document in claim.get("documents", []):
            document_path = _safe_path(root, relative_document)
            if document_path not in document_cache:
                try:
                    document_cache[document_path] = document_path.read_text(encoding="utf-8")
                except OSError as exc:
                    errors.append(f"{relative_document}: cannot read publication: {exc}")
                    document_cache[document_path] = ""
            text = document_cache[document_path]
            claim_checks += 2
            if claim["display"] not in text:
                errors.append(
                    f"{claim_id}: display {claim['display']!r} absent from {relative_document}"
                )
            if marker not in text:
                errors.append(f"{claim_id}: marker {marker} absent from {relative_document}")

    language_checks = 0
    for relative_document, required_terms in contract.get("required_disclosures", {}).items():
        document_path = _safe_path(root, relative_document)
        if document_path not in document_cache:
            try:
                document_cache[document_path] = document_path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"{relative_document}: cannot read publication: {exc}")
                document_cache[document_path] = ""
        folded = document_cache[document_path].casefold()
        for term in required_terms:
            language_checks += 1
            if term.casefold() not in folded:
                errors.append(f"{relative_document}: required disclosure absent: {term!r}")

    for document_path, text in document_cache.items():
        relative_document = document_path.relative_to(root).as_posix()
        for pattern in contract.get("forbidden_patterns", []):
            language_checks += 1
            if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                errors.append(f"{relative_document}: forbidden language matched {pattern!r}")

    if errors:
        raise PortfolioAuditError("portfolio audit failed:\n- " + "\n- ".join(errors))

    return {
        "status": "PASS",
        "schema_version": contract["schema_version"],
        "claims": len(contract["claims"]),
        "claim_checks": claim_checks,
        "language_checks": language_checks,
        "documents": len(document_cache),
        "sources": len(source_cache),
    }
