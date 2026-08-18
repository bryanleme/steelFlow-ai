"""Deterministic seed derivation for independent simulation components."""

from __future__ import annotations

import hashlib

import numpy as np

SEED_DERIVATION = "sha256(master_seed:namespace) first 32 bits"
SEED_NAMESPACES = (
    "dimensions",
    "orders",
    "billets",
    "process",
    "quality",
    "sensors",
    "missingness",
    "downtime",
    "maintenance",
)


class SeedBook:
    """Derive stable, independent NumPy generators from one master seed."""

    def __init__(self, master_seed: int) -> None:
        self.master_seed = master_seed

    def derive(self, namespace: str) -> int:
        payload = f"{self.master_seed}:{namespace}".encode()
        return int.from_bytes(hashlib.sha256(payload).digest()[:4], byteorder="big")

    def rng(self, namespace: str) -> np.random.Generator:
        return np.random.default_rng(self.derive(namespace))

    def partition_rng(self, namespace: str, partition: str) -> np.random.Generator:
        return np.random.default_rng(self.derive(f"{namespace}:{partition}"))

    def manifest_seeds(self) -> dict[str, int]:
        return {namespace: self.derive(namespace) for namespace in SEED_NAMESPACES}
