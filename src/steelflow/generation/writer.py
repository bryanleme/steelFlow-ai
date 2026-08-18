"""Incremental deterministic Parquet writer with logical and physical hashes."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def _json_default(value: Any) -> str | int | float | bool | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"unsupported value for logical hashing: {type(value).__name__}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DatasetWriter:
    """Write one or more deterministic files per table without retaining full data."""

    def __init__(self, root: Path, *, compression: str = "zstd") -> None:
        self.root = root
        self.compression = compression
        self.root.mkdir(parents=True, exist_ok=False)
        self._counts: defaultdict[str, int] = defaultdict(int)
        self._hashers: dict[str, hashlib._Hash] = {}  # type: ignore[attr-defined]
        self._files: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        self._part_counters: defaultdict[tuple[str, str], int] = defaultdict(int)

    def write_rows(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        *,
        partition: str | None = None,
    ) -> Path | None:
        if not rows:
            return None

        partition_key = partition or "unpartitioned"
        file_index = self._part_counters[(table_name, partition_key)]
        self._part_counters[(table_name, partition_key)] += 1

        table_directory = self.root / table_name
        if partition is not None:
            table_directory /= f"partition={partition}"
        table_directory.mkdir(parents=True, exist_ok=True)
        path = table_directory / f"part-{file_index:05d}.parquet"

        table = pa.Table.from_pylist(rows)
        pq.write_table(
            table,
            path,
            compression=self.compression,
            use_dictionary=True,
            write_statistics=True,
            row_group_size=min(len(rows), 100_000),
        )

        hasher = self._hashers.setdefault(table_name, hashlib.sha256())
        for row in rows:
            encoded = json.dumps(
                row,
                default=_json_default,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            hasher.update(encoded)
            hasher.update(b"\n")

        self._counts[table_name] += len(rows)
        relative_path = path.relative_to(self.root).as_posix()
        self._files[table_name].append(
            {
                "path": relative_path,
                "rows": len(rows),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
        return path

    def table_summary(self) -> dict[str, dict[str, Any]]:
        return {
            table_name: {
                "rows": self._counts[table_name],
                "logical_sha256": self._hashers[table_name].hexdigest(),
                "files": self._files[table_name],
            }
            for table_name in sorted(self._counts)
        }

    def dataset_logical_hash(self) -> str:
        digest = hashlib.sha256()
        for table_name, summary in sorted(self.table_summary().items()):
            digest.update(f"{table_name}:{summary['logical_sha256']}\n".encode())
        return digest.hexdigest()
