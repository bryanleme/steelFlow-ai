"""Small structured logging layer shared by CLI and future pipelines."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Emit one stable JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _STANDARD_FIELDS and not key.startswith("_")
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)


def configure_logging(level: str | None = None, *, json_output: bool = False) -> None:
    """Configure the process root logger exactly once per CLI invocation."""

    normalized_level = (level or os.getenv("STEELFLOW_LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, normalized_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"invalid log level: {normalized_level}")

    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)
