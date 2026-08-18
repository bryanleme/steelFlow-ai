"""Versioned causal truth used only by synthetic generation and later audit.

This module is intentionally private to ``steelflow.generation``. Feature,
model and optimization packages must never import it or read its outputs.
All numeric limits are internal simulation choices, not API 5CT values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

TRUTH_VERSION = "0.1.0"


@dataclass(frozen=True)
class ProductTruth:
    product_code: str
    product_family: str
    outer_diameter_mm: float
    wall_thickness_mm: float
    nominal_length_m: float
    nominal_mass_kg: float
    complexity_latent: float


@dataclass(frozen=True)
class TubeSynthesis:
    process: dict[str, Any]
    outcomes: dict[str, Any]
    truth: dict[str, Any]


def product_catalog(product_codes: tuple[str, ...]) -> tuple[ProductTruth, ...]:
    diameters = (60.3, 73.0, 88.9, 101.6, 114.3, 127.0)
    walls = (5.5, 6.5, 7.5, 8.5, 10.0, 12.0)
    products: list[ProductTruth] = []
    for index, product_code in enumerate(product_codes):
        diameter = diameters[index % len(diameters)]
        wall = walls[(index * 2 + index // 6) % len(walls)]
        length = 9.5 + 0.5 * (index % 4)
        section_area_mm2 = math.pi * (diameter * wall - wall**2)
        mass = section_area_mm2 * length * 0.00785
        complexity = min(0.95, 0.16 + 0.055 * index + 0.018 * wall)
        products.append(
            ProductTruth(
                product_code=product_code,
                product_family="CASING" if index < 6 else "TUBING",
                outer_diameter_mm=diameter,
                wall_thickness_mm=wall,
                nominal_length_m=length,
                nominal_mass_kg=round(mass, 3),
                complexity_latent=round(complexity, 6),
            )
        )
    return tuple(products)


def public_product_rows(products: tuple[ProductTruth, ...]) -> list[dict[str, Any]]:
    """Expose product geometry without leaking the latent complexity score."""

    return [
        {
            "product_code": product.product_code,
            "product_family": product.product_family,
            "outer_diameter_mm": product.outer_diameter_mm,
            "wall_thickness_mm": product.wall_thickness_mm,
            "nominal_length_m": product.nominal_length_m,
            "nominal_mass_kg": product.nominal_mass_kg,
            "internal_simulated_spec": True,
        }
        for product in products
    ]


def line_rows(lines: tuple[str, ...]) -> list[dict[str, Any]]:
    capabilities = (
        (48.0, 120.0, 0.96),
        (60.0, 140.0, 1.03),
        (73.0, 160.0, 1.00),
    )
    return [
        {
            "line_id": line_id,
            "minimum_outer_diameter_mm": minimum,
            "nominal_roll_speed_rpm": speed,
            "energy_efficiency_index": efficiency,
            "internal_simulated_limits": True,
        }
        for line_id, (minimum, speed, efficiency) in zip(lines, capabilities, strict=True)
    ]


def _clip(value: float, lower: float, upper: float) -> float:
    return float(np.clip(value, lower, upper))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def synthesize_tube(
    *,
    rng: np.random.Generator,
    product: ProductTruth,
    grade_family: str,
    line_id: str,
    shift_id: str,
    day_fraction: float,
    global_tube_index: int,
    heat_treatment_applied: bool,
    ambient_temperature_c: float,
) -> TubeSynthesis:
    """Apply nonlinear versioned mechanisms to one synthetic tube."""

    grade_index = {"J55": 0, "N80": 1, "L80": 2, "P110": 3}[grade_family]
    line_index = int(line_id[-2:]) - 1
    shift_index = {"SHIFT_A": 0, "SHIFT_B": 1, "SHIFT_C": 2}[shift_id]
    complexity = product.complexity_latent

    calibration_drift = (
        0.16 * day_fraction
        + 0.045 * math.sin(day_fraction * 8.0 * math.pi + line_index)
        + float(rng.normal(0.0, 0.012))
    )
    wear_cycle = (global_tube_index % (420 + line_index * 35)) / (420 + line_index * 35)
    tool_wear = _clip(wear_cycle + 0.06 * line_index + rng.normal(0.0, 0.025), 0.0, 1.0)
    hours_since_maintenance = _clip(18.0 + tool_wear * 510.0 + rng.normal(0.0, 8.0), 0, 560)
    maintenance_deferred = hours_since_maintenance > 430.0
    sensor_degradation = _clip(
        0.04
        + 0.58 * tool_wear
        + 0.20 * max(calibration_drift, 0.0)
        + 0.04 * shift_index
        + rng.normal(0.0, 0.025),
        0.0,
        1.0,
    )

    target_exit_temp = 1110.0 + grade_index * 13.0 + product.wall_thickness_mm * 1.15
    zone_1 = target_exit_temp - 58.0 + rng.normal(0.0, 13.0) + calibration_drift * 55.0
    zone_2 = target_exit_temp - 22.0 + rng.normal(0.0, 11.0) + calibration_drift * 48.0
    zone_3 = target_exit_temp + rng.normal(0.0, 10.0) + calibration_drift * 42.0
    soak_time = 42.0 + product.wall_thickness_mm * 2.7 + complexity * 24.0 + rng.normal(0, 5)
    reheat_exit_temp = 0.18 * zone_1 + 0.30 * zone_2 + 0.52 * zone_3 + rng.normal(0.0, 6.0)
    zone_spread = float(np.std((zone_1, zone_2, zone_3)))
    thermal_uniformity = _clip(
        0.98
        - zone_spread / 115.0
        - 0.13 * tool_wear
        - 0.12 * abs(calibration_drift)
        + rng.normal(0.0, 0.025),
        0.20,
        0.99,
    )

    nominal_speed = (120.0, 140.0, 160.0)[line_index] * (1.0 - 0.10 * complexity)
    roll_speed = nominal_speed + rng.normal(0.0, 13.0) + calibration_drift * 18.0
    roll_gap = 8.0 + 0.58 * product.wall_thickness_mm + rng.normal(0.0, 0.45)
    mandrel_position = 2.5 + 0.08 * product.wall_thickness_mm + rng.normal(0.0, 0.22)
    reduction_rate = 18.0 + 8.0 * complexity + grade_index * 1.5 + rng.normal(0.0, 2.0)
    exit_speed = 1.2 + roll_speed / 115.0 + rng.normal(0.0, 0.08)
    lubrication_flow = 31.0 + 9.0 * complexity + 7.0 * tool_wear + rng.normal(0.0, 3.0)
    rolling_load = _clip(
        0.36
        + 0.42 * complexity
        + 0.18 * tool_wear
        + 0.08 * grade_index
        - 0.0018 * (roll_speed - nominal_speed)
        + rng.normal(0.0, 0.035),
        0.15,
        1.35,
    )

    target_austenitizing = 820.0 + grade_index * 23.0 + product.wall_thickness_mm * 1.1
    target_tempering = 655.0 - grade_index * 19.0 + product.wall_thickness_mm * 0.9
    if heat_treatment_applied:
        austenitizing_temp = target_austenitizing + rng.normal(0.0, 13.0)
        austenitizing_time = 24.0 + product.wall_thickness_mm * 1.8 + rng.normal(0.0, 3.0)
        quench_delay = 13.0 + grade_index * 2.0 + rng.normal(0.0, 2.5)
        quench_flow = 118.0 + product.wall_thickness_mm * 5.0 + rng.normal(0.0, 8.0)
        quench_medium_temp = 28.0 + rng.normal(0.0, 3.0)
        tempering_temp = target_tempering + rng.normal(0.0, 11.0)
        tempering_time = 36.0 + product.wall_thickness_mm * 2.1 + rng.normal(0.0, 4.0)
        heat_treatment_mismatch = _clip(
            abs(austenitizing_temp - target_austenitizing) / 55.0
            + abs(tempering_temp - target_tempering) / 65.0
            + max(quench_delay - 18.0, 0.0) / 25.0,
            0.0,
            2.0,
        )
    else:
        austenitizing_temp = None
        austenitizing_time = None
        quench_delay = None
        quench_flow = None
        quench_medium_temp = None
        tempering_temp = None
        tempering_time = None
        heat_treatment_mismatch = 0.16 * max(grade_index - 1, 0) * complexity

    thermal_distance = abs(reheat_exit_temp - target_exit_temp)
    thermal_window_ok = thermal_distance <= 42.0 and thermal_uniformity >= 0.68
    speed_delta = (roll_speed - nominal_speed) / nominal_speed
    speed_window_effect = (
        0.42 * speed_delta
        if thermal_window_ok
        else -0.22 * abs(speed_delta) - 0.14 * max(speed_delta, 0.0)
    )
    thermal_speed_penalty = max(speed_delta, 0.0) * (
        thermal_distance / 55.0 + max(0.72 - thermal_uniformity, 0.0) * 3.0
    )
    eccentricity_interaction = (1.0 - thermal_uniformity) * (0.35 + tool_wear) * 4.8

    od_deviation = (
        calibration_drift * 0.85
        + speed_delta * (0.55 if thermal_window_ok else 1.35)
        + rng.normal(0.0, 0.31)
    )
    wall_eccentricity = 0.55 + eccentricity_interaction + 0.18 * complexity + rng.normal(0.0, 0.18)
    ovality = (
        0.48
        + 0.72 * complexity
        + 0.55 * abs(speed_delta)
        + 0.32 * tool_wear
        + 0.62 * thermal_speed_penalty
        + rng.normal(0.0, 0.16)
    )

    internal_yield_center = (410.0, 545.0, 590.0, 760.0)[grade_index]
    heat_response = (
        (34.0 + 12.0 * grade_index) * (1.0 - heat_treatment_mismatch)
        if heat_treatment_applied
        else -24.0 * max(grade_index - 1, 0)
    )
    yield_strength = internal_yield_center + heat_response + rng.normal(0.0, 20.0)
    tensile_strength = yield_strength + 105.0 + 8.0 * grade_index + rng.normal(0.0, 15.0)
    mechanical_lower = internal_yield_center - 62.0
    mechanical_upper = internal_yield_center + 115.0

    defect_logit = (
        -4.45
        + 1.15 * complexity
        + 1.25 * tool_wear
        + 2.5 * thermal_speed_penalty
        + 1.1 * heat_treatment_mismatch
        + 0.55 * sensor_degradation
    )
    ndt_probability = _clip(_sigmoid(defect_logit), 0.001, 0.55)
    ndt_indication = (
        _clip(0.68 + rng.beta(2.0, 4.0) * 0.45, 0.0, 1.2)
        if rng.random() < ndt_probability
        else _clip(rng.beta(1.0, 18.0) * 0.45, 0.0, 0.65)
    )

    checks = {
        "outer_diameter_deviation_mm": abs(od_deviation) <= 1.20,
        "wall_eccentricity_pct": wall_eccentricity <= 3.50,
        "ovality_pct": ovality <= 2.50,
        "yield_strength_mpa": mechanical_lower <= yield_strength <= mechanical_upper,
        "tensile_strength_mpa": tensile_strength >= internal_yield_center + 55.0,
        "ndt_indication_score": ndt_indication < 0.70,
    }
    approved_first_pass = all(checks.values())
    severe_failure = (
        wall_eccentricity > 4.8
        or ovality > 3.4
        or ndt_indication > 0.94
        or yield_strength < mechanical_lower - 45.0
    )
    disposition = "FIRST_PASS" if approved_first_pass else ("SCRAP" if severe_failure else "REWORK")

    tube_mass_kg = product.nominal_mass_kg * _clip(rng.normal(1.0, 0.012), 0.96, 1.04)
    line_base_tph = (30.0, 34.0, 32.0)[line_index]
    actual_tph = _clip(
        line_base_tph
        * (1.0 - 0.30 * complexity)
        * (1.0 + speed_window_effect - 0.09 * tool_wear - 0.04 * grade_index)
        + rng.normal(0.0, 0.7),
        8.0,
        42.0,
    )
    productive_hours = tube_mass_kg / 1000.0 / actual_tph
    good_mass_t = tube_mass_kg / 1000.0 if approved_first_pass else 0.0
    total_energy_kwh = (
        tube_mass_kg
        / 1000.0
        * (
            420.0
            + 88.0 * complexity
            + 72.0 * (1.0 - thermal_uniformity)
            + 34.0 * heat_treatment_applied
            + 24.0 * rolling_load
            - 8.0 * line_index
        )
    )
    stop_risk = _clip(
        _sigmoid(-5.1 + 3.2 * sensor_degradation + 2.1 * tool_wear + maintenance_deferred),
        0.001,
        0.65,
    )

    process = {
        "tool_wear_index": round(tool_wear, 6),
        "hours_since_maintenance": round(hours_since_maintenance, 3),
        "maintenance_deferred": maintenance_deferred,
        "sensor_degradation_index": round(sensor_degradation, 6),
        "reheat_zone_1_temp_c": round(zone_1, 3),
        "reheat_zone_2_temp_c": round(zone_2, 3),
        "reheat_zone_3_temp_c": round(zone_3, 3),
        "soak_time_min": round(soak_time, 3),
        "reheat_exit_temp_c": round(reheat_exit_temp, 3),
        "thermal_uniformity_index": round(thermal_uniformity, 6),
        "roll_speed_rpm": round(roll_speed, 3),
        "roll_gap_mm": round(roll_gap, 3),
        "mandrel_position_mm": round(mandrel_position, 3),
        "reduction_rate_pct": round(reduction_rate, 3),
        "exit_speed_m_s": round(exit_speed, 4),
        "lubrication_flow_l_min": round(lubrication_flow, 3),
        "rolling_load_index": round(rolling_load, 6),
        "heat_treatment_applied": heat_treatment_applied,
        "austenitizing_temp_c": None
        if austenitizing_temp is None
        else round(austenitizing_temp, 3),
        "austenitizing_time_min": None
        if austenitizing_time is None
        else round(austenitizing_time, 3),
        "quench_delay_s": None if quench_delay is None else round(quench_delay, 3),
        "quench_flow_l_min": None if quench_flow is None else round(quench_flow, 3),
        "quench_medium_temp_c": None
        if quench_medium_temp is None
        else round(quench_medium_temp, 3),
        "tempering_temp_c": None if tempering_temp is None else round(tempering_temp, 3),
        "tempering_time_min": None if tempering_time is None else round(tempering_time, 3),
    }
    outcomes = {
        "outer_diameter_deviation_mm": round(od_deviation, 6),
        "wall_eccentricity_pct": round(wall_eccentricity, 6),
        "ovality_pct": round(ovality, 6),
        "yield_strength_mpa": round(yield_strength, 4),
        "tensile_strength_mpa": round(tensile_strength, 4),
        "ndt_indication_score": round(ndt_indication, 6),
        "quality_passes": checks,
        "approved_first_pass": approved_first_pass,
        "disposition": disposition,
        "tube_mass_kg": round(tube_mass_kg, 4),
        "good_mass_t": round(good_mass_t, 7),
        "productive_hours": round(productive_hours, 8),
        "actual_tph": round(actual_tph, 5),
        "total_energy_kwh": round(total_energy_kwh, 5),
    }
    truth = {
        "truth_version": TRUTH_VERSION,
        "product_complexity_latent": complexity,
        "calibration_drift_latent": round(calibration_drift, 7),
        "target_exit_temperature_latent_c": round(target_exit_temp, 4),
        "thermal_window_ok_latent": thermal_window_ok,
        "speed_window_effect_latent": round(speed_window_effect, 7),
        "thermal_speed_penalty_latent": round(thermal_speed_penalty, 7),
        "eccentricity_interaction_latent": round(eccentricity_interaction, 7),
        "heat_treatment_mismatch_latent": round(heat_treatment_mismatch, 7),
        "sensor_degradation_latent": round(sensor_degradation, 7),
        "stop_risk_latent": round(stop_risk, 7),
        "ndt_probability_latent": round(ndt_probability, 7),
    }
    return TubeSynthesis(process=process, outcomes=outcomes, truth=truth)
