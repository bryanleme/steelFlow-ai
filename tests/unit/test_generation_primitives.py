from __future__ import annotations

import numpy as np

from steelflow.generation._ground_truth import product_catalog, synthesize_tube
from steelflow.generation.ids import deterministic_id, deterministic_run_id
from steelflow.generation.seeds import SEED_NAMESPACES, SeedBook

PRODUCT_CODES = tuple(f"OCTG_{index:02d}" for index in range(1, 13))


def test_seed_namespaces_are_stable_and_independent() -> None:
    first = SeedBook(20260818)
    second = SeedBook(20260818)

    assert first.manifest_seeds() == second.manifest_seeds()
    assert set(first.manifest_seeds()) == set(SEED_NAMESPACES)
    assert len(set(first.manifest_seeds().values())) == len(SEED_NAMESPACES)
    assert first.manifest_seeds() != SeedBook(20260819).manifest_seeds()


def test_deterministic_identifiers_are_readable_and_repeatable() -> None:
    first = deterministic_id("TUB", "order-1", 17)
    second = deterministic_id("TUB", "order-1", 17)

    assert first == second
    assert first.startswith("TUB-")
    assert first != deterministic_id("TUB", "order-1", 18)
    assert deterministic_run_id("test", "0.1.0", 7, "abc").startswith("sim-test-v0.1.0-")


def _synthesize(product_index: int, *, grade: str, global_index: int, heat: bool):
    product = product_catalog(PRODUCT_CODES)[product_index]
    return synthesize_tube(
        rng=np.random.default_rng(12345),
        product=product,
        grade_family=grade,
        line_id="LINE_01",
        shift_id="SHIFT_A",
        day_fraction=0.5,
        global_tube_index=global_index,
        heat_treatment_applied=heat,
        ambient_temperature_c=25.0,
    )


def test_product_complexity_reduces_base_throughput() -> None:
    simple = _synthesize(0, grade="J55", global_index=20, heat=False)
    complex_product = _synthesize(11, grade="J55", global_index=20, heat=False)

    assert (
        complex_product.truth["product_complexity_latent"]
        > simple.truth["product_complexity_latent"]
    )
    assert complex_product.outcomes["actual_tph"] < simple.outcomes["actual_tph"]


def test_wear_and_low_uniformity_raise_eccentricity_interaction() -> None:
    fresh = _synthesize(6, grade="N80", global_index=0, heat=False)
    worn = _synthesize(6, grade="N80", global_index=410, heat=False)

    assert worn.process["tool_wear_index"] > fresh.process["tool_wear_index"]
    assert (
        worn.truth["eccentricity_interaction_latent"]
        > fresh.truth["eccentricity_interaction_latent"]
    )
    assert worn.outcomes["wall_eccentricity_pct"] > fresh.outcomes["wall_eccentricity_pct"]


def test_heat_treatment_response_depends_on_grade() -> None:
    low_grade = _synthesize(8, grade="J55", global_index=120, heat=True)
    high_grade = _synthesize(8, grade="P110", global_index=120, heat=True)

    assert high_grade.outcomes["yield_strength_mpa"] > low_grade.outcomes["yield_strength_mpa"]
    assert (
        high_grade.truth["target_exit_temperature_latent_c"]
        > low_grade.truth["target_exit_temperature_latent_c"]
    )


def test_stop_risk_grows_with_degradation_and_accumulated_hours() -> None:
    fresh = _synthesize(4, grade="L80", global_index=0, heat=False)
    worn = _synthesize(4, grade="L80", global_index=410, heat=False)

    assert worn.process["hours_since_maintenance"] > fresh.process["hours_since_maintenance"]
    assert worn.truth["sensor_degradation_latent"] > fresh.truth["sensor_degradation_latent"]
    assert worn.truth["stop_risk_latent"] > fresh.truth["stop_risk_latent"]
