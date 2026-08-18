"""Readable deterministic identifiers for synthetic entities."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable


def deterministic_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def deterministic_run_id(
    profile: str,
    generator_version: str,
    master_seed: int,
    config_hash: str,
) -> str:
    digest = hashlib.sha256(
        f"{profile}|{generator_version}|{master_seed}|{config_hash}".encode()
    ).hexdigest()[:12]
    return f"sim-{profile}-v{generator_version}-{digest}"


def assert_unique(values: Iterable[str], *, entity: str) -> None:
    materialized = list(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"deterministic ID collision detected for {entity}")
