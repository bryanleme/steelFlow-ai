"""Regression tests for analytical reconciliation tolerances."""

from steelflow.validation.analytics import _add_close_check
from steelflow.validation.raw_data import ValidationReport


def _report() -> ValidationReport:
    return ValidationReport(
        simulation_run_id="sim-test",
        profile="test",
        checked_at_utc="2026-08-18T00:00:00+00:00",
    )


def test_close_check_accepts_negligible_relative_error_at_large_scale() -> None:
    report = _report()

    _add_close_check(
        report,
        "energy",
        observed=24_181_229.776240956,
        expected=24_181_229.776241064,
        detail="Floating aggregates should use scale-aware tolerance.",
    )

    assert report.passed


def test_close_check_rejects_material_reconciliation_error() -> None:
    report = _report()

    _add_close_check(
        report,
        "energy",
        observed=24_181_220.0,
        expected=24_181_229.776241064,
        detail="Material divergence must still fail.",
    )

    assert not report.passed
