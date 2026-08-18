from __future__ import annotations

import json
import logging

import pytest

from steelflow.observability import JsonFormatter, configure_logging


def test_json_formatter_includes_context() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="steelflow.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="simulation_started",
        args=(),
        exc_info=None,
    )
    record.profile = "test"
    record.simulation_run_id = "run-001"

    parsed = json.loads(formatter.format(record))

    assert parsed["event"] == "simulation_started"
    assert parsed["profile"] == "test"
    assert parsed["simulation_run_id"] == "run-001"
    assert parsed["level"] == "INFO"


def test_invalid_log_level_fails_early() -> None:
    with pytest.raises(ValueError, match="invalid log level"):
        configure_logging("not-a-level")
