from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

import pytest

from steelflow.product.scenario import (
    approve_scenario,
    scenario_csv_bytes,
    scenario_json_bytes,
)


def eligible_scenario() -> dict[str, object]:
    return {
        "context_id": "ctx-001",
        "status": "ELIGIBLE_FOR_HUMAN_REVIEW",
        "recommendation_issued": True,
        "human_approved": False,
        "machine_command": False,
        "hard_constraints_pass": True,
        "parameters": {"roll_speed_mpm": 18.5},
        "predictions": {
            "estimated_tbh_proxy": 19.2,
            "actual_tph": {"p10": 18.0, "p50": 19.5, "p90": 20.2},
        },
        "ood_assessment": {"in_distribution": True},
    }


def test_approval_requires_explicit_acknowledgement_and_preserves_no_command() -> None:
    scenario = eligible_scenario()

    with pytest.raises(ValueError, match="confirmação humana"):
        approve_scenario(scenario, acknowledgement=False)

    approved = approve_scenario(
        scenario,
        acknowledgement=True,
        approved_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        approval_id="approval-test",
    )

    assert approved["human_approved"] is True
    assert approved["machine_command"] is False
    assert approved["approval"]["approval_id"] == "approval-test"
    assert scenario["human_approved"] is False


def test_refused_scenario_cannot_be_approved() -> None:
    scenario = eligible_scenario()
    scenario["recommendation_issued"] = False

    with pytest.raises(ValueError, match="recusado"):
        approve_scenario(scenario, acknowledgement=True)


def test_approved_scenario_exports_are_readable() -> None:
    approved = approve_scenario(
        eligible_scenario(),
        acknowledgement=True,
        approval_id="approval-test",
    )

    json_payload = json.loads(scenario_json_bytes(approved).decode("utf-8"))
    csv_payload = next(
        csv.DictReader(io.StringIO(scenario_csv_bytes(approved).decode("utf-8-sig")))
    )

    assert json_payload["approval"]["approval_id"] == "approval-test"
    assert csv_payload["human_approved"] == "True"
    assert csv_payload["parameter__roll_speed_mpm"] == "18.5"
