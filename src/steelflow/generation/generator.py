"""Partitioned synthetic factory generator for SteelFlow AI."""

from __future__ import annotations

import json
import math
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from steelflow.config import ProjectConfigBundle
from steelflow.generation._ground_truth import (
    TRUTH_VERSION,
    ProductTruth,
    line_rows,
    product_catalog,
    public_product_rows,
    synthesize_tube,
)
from steelflow.generation.ids import deterministic_id, deterministic_run_id
from steelflow.generation.manifest import base_manifest, utc_now, write_manifest
from steelflow.generation.schemas import BASE_STAGES, QUALITY_CHARACTERISTICS, SENSOR_TYPES
from steelflow.generation.seeds import SEED_DERIVATION, SeedBook
from steelflow.generation.writer import DatasetWriter


class GenerationError(RuntimeError):
    """Raised when generation cannot complete atomically."""


@dataclass(frozen=True)
class GenerationResult:
    simulation_run_id: str
    raw_path: Path
    ground_truth_path: Path
    manifest_path: Path
    table_counts: dict[str, int]
    dataset_logical_sha256: str
    elapsed_seconds: float


def _partition_key(value: date, frequency: str) -> str:
    return value.isoformat() if frequency == "day" else value.strftime("%Y-%m")


def _safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise GenerationError(f"refusing to remove path outside run parent: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _atomic_promote(staging: Path, final: Path) -> None:
    if final.exists():
        raise GenerationError(f"final run directory already exists: {final}")
    staging.replace(final)


def _distribute_exact(total: int, groups: int) -> list[int]:
    base, remainder = divmod(total, groups)
    return [base + (1 if index < remainder else 0) for index in range(groups)]


def _heat_treatment_selected(global_index: int, total_tubes: int, treatment_count: int) -> bool:
    before = global_index * treatment_count // total_tubes
    after = (global_index + 1) * treatment_count // total_tubes
    return after > before


def _build_dimensions(
    *,
    bundle: ProjectConfigBundle,
    products: tuple[ProductTruth, ...],
    run_id: str,
) -> dict[str, list[dict[str, Any]]]:
    plant = bundle.simulation.plant
    product_rows = public_product_rows(products)
    for row in product_rows:
        row["simulation_run_id"] = run_id

    lines = line_rows(plant.lines)
    for row in lines:
        row["simulation_run_id"] = run_id

    shifts = [
        {
            "shift_id": shift_id,
            "start_hour": index * 8,
            "duration_hours": 8,
            "simulation_run_id": run_id,
        }
        for index, shift_id in enumerate(plant.shifts)
    ]
    assets = []
    for line_id in plant.lines:
        for asset_type in (
            "REHEAT_FURNACE",
            "PIERCING_MILL",
            "ROLLING_MILL",
            "HEAT_TREATMENT",
            "INSPECTION_LINE",
        ):
            assets.append(
                {
                    "asset_id": deterministic_id("AST", line_id, asset_type),
                    "line_id": line_id,
                    "asset_type": asset_type,
                    "criticality": "HIGH"
                    if asset_type in {"ROLLING_MILL", "REHEAT_FURNACE"}
                    else "MEDIUM",
                    "simulation_run_id": run_id,
                }
            )
    feature_rows = [
        {
            **feature.model_dump(mode="json"),
            "simulation_run_id": run_id,
        }
        for feature in bundle.feature_availability.features
    ]
    return {
        "dim_products": product_rows,
        "dim_lines": lines,
        "dim_shifts": shifts,
        "dim_assets": assets,
        "feature_availability": feature_rows,
    }


def _build_orders(
    *,
    bundle: ProjectConfigBundle,
    products: tuple[ProductTruth, ...],
    seed_book: SeedBook,
    run_id: str,
) -> list[dict[str, Any]]:
    config = bundle.simulation
    rng = seed_book.rng("orders")
    quantities = _distribute_exact(config.volume_targets.tubes, config.volume_targets.orders)
    start_date = config.period.start_date
    duration_days = config.period.duration_days
    grade_probabilities = np.array((0.34, 0.29, 0.22, 0.15))
    line_day_sequences: defaultdict[tuple[str, date], int] = defaultdict(int)
    orders: list[dict[str, Any]] = []
    cumulative_tubes = 0

    for order_index, quantity in enumerate(quantities):
        day_offset = min(duration_days - 1, order_index * duration_days // len(quantities))
        planned_date = start_date + timedelta(days=day_offset)
        day_fraction = day_offset / max(duration_days - 1, 1)
        if order_index < len(products):
            product_index = order_index
        else:
            product_beta = rng.beta(1.8 + 2.4 * day_fraction, 2.5 - 0.7 * day_fraction)
            product_index = min(len(products) - 1, int(product_beta * len(products)))
        product = products[product_index]
        grade_family = (
            config.plant.grade_families[order_index]
            if order_index < len(config.plant.grade_families)
            else str(rng.choice(config.plant.grade_families, p=grade_probabilities))
        )
        line_id = config.plant.lines[(order_index * 7 + day_offset) % len(config.plant.lines)]
        shift_index = (order_index + day_offset) % len(config.plant.shifts)
        shift_id = config.plant.shifts[shift_index]
        sequence_key = (line_id, planned_date)
        committed_sequence = line_day_sequences[sequence_key]
        line_day_sequences[sequence_key] += 1
        scheduled_start = datetime.combine(
            planned_date,
            datetime.min.time(),
            tzinfo=UTC,
        ) + timedelta(hours=shift_index * 8, minutes=(committed_sequence * 17) % 420)
        release_ts = scheduled_start - timedelta(hours=12 + int(rng.integers(0, 8)))
        order_id = deterministic_id(
            "ORD", config.generator_version, config.random_seed, order_index
        )
        billet_batch_id = deterministic_id("BLT", order_id)
        ambient = (
            23.0
            + 7.0 * math.sin(2 * math.pi * planned_date.timetuple().tm_yday / 365.25)
            + float(rng.normal(0.0, 2.2))
        )
        orders.append(
            {
                "order_id": order_id,
                "billet_batch_id": billet_batch_id,
                "scheduled_start_ts": scheduled_start,
                "release_ts": release_ts,
                "product_code": product.product_code,
                "grade_family": grade_family,
                "line_id": line_id,
                "shift_id": shift_id,
                "quantity_tubes": quantity,
                "target_tonnes": round(product.nominal_mass_kg * quantity / 1000.0, 5),
                "priority_code": ("STANDARD", "EXPEDITE", "CAMPAIGN")[order_index % 3],
                "committed_sequence": committed_sequence,
                "ambient_temperature_c": round(ambient, 3),
                "prediction_time_ts": release_ts,
                "first_global_tube_index": cumulative_tubes,
                "partition": _partition_key(planned_date, config.output.partition_frequency),
                "simulation_run_id": run_id,
            }
        )
        cumulative_tubes += quantity
    return orders


def _build_billet(
    order: dict[str, Any], product: ProductTruth, rng: np.random.Generator
) -> dict[str, Any]:
    grade_index = {"J55": 0, "N80": 1, "L80": 2, "P110": 3}[order["grade_family"]]
    return {
        "billet_batch_id": order["billet_batch_id"],
        "order_id": order["order_id"],
        "received_ts": order["release_ts"] + timedelta(hours=2),
        "supplier_code": f"SYN_SUPPLIER_{1 + grade_index % 3:02d}",
        "heat_code": deterministic_id("HEAT", order["billet_batch_id"]),
        "carbon_pct": round(0.18 + 0.025 * grade_index + rng.normal(0.0, 0.008), 5),
        "manganese_pct": round(0.82 + 0.12 * grade_index + rng.normal(0.0, 0.025), 5),
        "chromium_pct": round(0.06 + 0.13 * grade_index + rng.normal(0.0, 0.018), 5),
        "molybdenum_pct": round(0.018 + 0.035 * grade_index + rng.normal(0.0, 0.008), 5),
        "billet_diameter_mm": round(product.outer_diameter_mm * 2.15 + rng.normal(0, 1.2), 3),
        "billet_mass_kg": round(product.nominal_mass_kg * 1.18 + rng.normal(0, 3.0), 3),
        "traceability_status": "COMPLETE",
        "simulation_run_id": order["simulation_run_id"],
    }


def _stage_rows(
    *,
    tube_id: str,
    order: dict[str, Any],
    actual_start: datetime,
    actual_end: datetime,
    heat_treatment_applied: bool,
    process: dict[str, Any],
    run_id: str,
) -> list[dict[str, Any]]:
    offsets: dict[str, tuple[float, float]] = {
        "ORDER_RELEASE": (-720.0, -710.0),
        "BILLET_RECEIPT": (-600.0, -585.0),
        "REHEATING": (0.0, 30.0 + process["soak_time_min"] * 0.18),
        "PIERCING_ELONGATION": (36.0, 46.0),
        "ROLLING_SIZING": (46.0, 64.0),
        "HEAT_TREATMENT": (64.0, 118.0),
        "INSPECTION": (
            120.0 if heat_treatment_applied else 66.0,
            132.0 if heat_treatment_applied else 78.0,
        ),
        "DISPOSITION": (
            132.0 if heat_treatment_applied else 78.0,
            135.0 if heat_treatment_applied else 81.0,
        ),
    }
    stage_names = list(BASE_STAGES)
    if heat_treatment_applied:
        stage_names.insert(5, "HEAT_TREATMENT")

    rows = []
    for sequence, stage_name in enumerate(stage_names, start=1):
        start_offset, end_offset = offsets[stage_name]
        event_start = actual_start + timedelta(minutes=start_offset)
        event_end = actual_start + timedelta(minutes=end_offset)
        if stage_name == "DISPOSITION":
            event_end = actual_end
        rows.append(
            {
                "stage_event_id": deterministic_id("STG", tube_id, stage_name),
                "tube_id": tube_id,
                "order_id": order["order_id"],
                "line_id": order["line_id"],
                "stage_sequence": sequence,
                "stage_name": stage_name,
                "event_start_ts": event_start,
                "event_end_ts": event_end,
                "duration_minutes": round((event_end - event_start).total_seconds() / 60.0, 4),
                "event_status": "COMPLETED",
                "simulation_run_id": run_id,
            }
        )
    return rows


def _sensor_rows(
    *,
    tube_id: str,
    order: dict[str, Any],
    actual_start: datetime,
    process: dict[str, Any],
    outcomes: dict[str, Any],
    global_tube_index: int,
    day_index: int,
    rng: np.random.Generator,
    run_id: str,
) -> list[dict[str, Any]]:
    average_furnace = sum(process[f"reheat_zone_{index}_temp_c"] for index in (1, 2, 3)) / 3
    power = outcomes["total_energy_kwh"] / max(outcomes["productive_hours"], 0.0001) * 0.035
    definitions = {
        "furnace_zone_temperature": (average_furnace, "degC", 850.0, 1320.0, 5.0),
        "reheat_exit_temperature": (process["reheat_exit_temp_c"], "degC", 900.0, 1280.0, 25.0),
        "roll_speed": (process["roll_speed_rpm"], "rpm", 40.0, 240.0, 45.0),
        "rolling_load": (process["rolling_load_index"], "ratio", 0.1, 1.35, 48.0),
        "lubrication_flow": (process["lubrication_flow_l_min"], "L_min", 5.0, 80.0, 50.0),
        "mill_vibration": (
            1.8 + 4.4 * process["tool_wear_index"] + 1.3 * process["sensor_degradation_index"],
            "mm_s",
            0.0,
            7.0,
            52.0,
        ),
        "electrical_power": (power, "kW", 120.0, 1600.0, 15.0),
        "quench_flow": (
            process["quench_flow_l_min"] or 0.0,
            "L_min",
            70.0,
            240.0,
            70.0,
        ),
    }
    line_index = int(order["line_id"][-2:]) - 1
    rows: list[dict[str, Any]] = []
    for sensor_index, sensor_type in enumerate(SENSOR_TYPES):
        base_value, unit, lower, upper, minute_offset = definitions[sensor_type]
        for window_index in range(4):
            ordinal = global_tube_index * 32 + sensor_index * 4 + window_index
            missingness = "NONE"
            if sensor_type == "quench_flow" and not process["heat_treatment_applied"]:
                missingness = "NOT_APPLICABLE"
            elif (day_index + line_index * 7 + sensor_index) % 41 == 0 and window_index in {
                1,
                2,
            }:
                missingness = "BLOCK"
            elif ordinal % 211 == 0:
                missingness = "MCAR"
            elif (
                order["shift_id"] == "SHIFT_C"
                and process["sensor_degradation_index"] > 0.42
                and ordinal % 97 == 0
            ):
                missingness = "MAR"

            start_ts = actual_start + timedelta(minutes=minute_offset + window_index * 2)
            end_ts = start_ts + timedelta(minutes=2)
            if missingness == "NONE":
                scale = max(abs(float(base_value)) * 0.008, 0.02)
                mean = float(base_value) + float(rng.normal(0.0, scale))
                standard_deviation = abs(float(rng.normal(scale * 0.58, scale * 0.12)))
                minimum = mean - standard_deviation * (1.6 + float(rng.random()) * 0.5)
                maximum = mean + standard_deviation * (1.6 + float(rng.random()) * 0.5)
                slope = float(rng.normal(0.0, scale * 0.12))
                outside = max(lower - minimum, 0.0) + max(maximum - upper, 0.0)
                out_of_range_pct = _bounded(outside / max(upper - lower, 0.001) * 100, 0, 100)
                stats = {
                    "mean_value": round(mean, 6),
                    "minimum_value": round(minimum, 6),
                    "maximum_value": round(maximum, 6),
                    "standard_deviation": round(standard_deviation, 6),
                    "slope": round(slope, 7),
                    "amplitude": round(maximum - minimum, 6),
                    "out_of_range_pct": round(out_of_range_pct, 6),
                }
                quality_status = "VALID"
            else:
                stats = {
                    "mean_value": None,
                    "minimum_value": None,
                    "maximum_value": None,
                    "standard_deviation": None,
                    "slope": None,
                    "amplitude": None,
                    "out_of_range_pct": None,
                }
                quality_status = "NOT_APPLICABLE" if missingness == "NOT_APPLICABLE" else "MISSING"

            rows.append(
                {
                    "sensor_window_id": deterministic_id("SNS", tube_id, sensor_type, window_index),
                    "tube_id": tube_id,
                    "order_id": order["order_id"],
                    "line_id": order["line_id"],
                    "sensor_type": sensor_type,
                    "window_index": window_index,
                    "window_start_ts": start_ts,
                    "window_end_ts": end_ts,
                    "feature_available_at_ts": end_ts,
                    "unit": unit,
                    **stats,
                    "missingness_type": missingness,
                    "data_quality_status": quality_status,
                    "simulation_run_id": run_id,
                }
            )
    return rows


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _quality_rows(
    *,
    tube_id: str,
    order: dict[str, Any],
    inspection_ts: datetime,
    outcomes: dict[str, Any],
    run_id: str,
) -> list[dict[str, Any]]:
    grade_center = {"J55": 410.0, "N80": 545.0, "L80": 590.0, "P110": 760.0}[order["grade_family"]]
    specs = {
        "outer_diameter_deviation_mm": (-1.20, 1.20, "mm"),
        "wall_eccentricity_pct": (0.0, 3.50, "pct"),
        "ovality_pct": (0.0, 2.50, "pct"),
        "yield_strength_mpa": (grade_center - 62.0, grade_center + 115.0, "MPa"),
        "tensile_strength_mpa": (grade_center + 55.0, grade_center + 360.0, "MPa"),
        "ndt_indication_score": (0.0, 0.70, "score"),
    }
    rows = []
    for characteristic in QUALITY_CHARACTERISTICS:
        lower, upper, unit = specs[characteristic]
        rows.append(
            {
                "quality_result_id": deterministic_id("QLT", tube_id, characteristic),
                "tube_id": tube_id,
                "order_id": order["order_id"],
                "line_id": order["line_id"],
                "characteristic": characteristic,
                "measured_value": outcomes[characteristic],
                "internal_simulated_lower_limit": lower,
                "internal_simulated_upper_limit": upper,
                "unit": unit,
                "passed": outcomes["quality_passes"][characteristic],
                "inspection_ts": inspection_ts,
                "simulation_run_id": run_id,
            }
        )
    return rows


def _energy_rows(
    *,
    tube_id: str,
    order: dict[str, Any],
    event_ts: datetime,
    outcomes: dict[str, Any],
    heat_treatment_applied: bool,
    run_id: str,
) -> list[dict[str, Any]]:
    stages = (
        ("REHEATING", 0.50),
        ("ROLLING_SIZING", 0.35),
        ("HEAT_TREATMENT" if heat_treatment_applied else "FINISHING", 0.15),
    )
    rows = []
    for stage_name, share in stages:
        energy = outcomes["total_energy_kwh"] * share
        good_mass = outcomes["good_mass_t"]
        rows.append(
            {
                "energy_event_id": deterministic_id("ENG", tube_id, stage_name),
                "tube_id": tube_id,
                "order_id": order["order_id"],
                "line_id": order["line_id"],
                "stage_name": stage_name,
                "event_ts": event_ts,
                "energy_kwh": round(energy, 6),
                "good_mass_t": good_mass,
                "energy_per_good_tonne_kwh_t": None
                if good_mass <= 0
                else round(energy / good_mass, 5),
                "simulation_run_id": run_id,
            }
        )
    return rows


def _generate_partition(
    *,
    partition: str,
    orders: list[dict[str, Any]],
    product_map: dict[str, ProductTruth],
    bundle: ProjectConfigBundle,
    seed_book: SeedBook,
    run_id: str,
    raw_writer: DatasetWriter,
    truth_writer: DatasetWriter,
    treatment_count: int,
) -> None:
    config = bundle.simulation
    process_rng = seed_book.partition_rng("process", partition)
    billet_rng = seed_book.partition_rng("billets", partition)
    sensor_rng = seed_book.partition_rng("sensors", partition)
    raw_buffers: dict[str, list[dict[str, Any]]] = {
        "tubes": [],
        "process_parameters": [],
        "stage_events": [],
        "sensor_windows": [],
        "quality_results": [],
        "energy_events": [],
    }
    truth_buffer: list[dict[str, Any]] = []
    batch_size = config.output.batch_size

    order_rows = []
    billet_rows = []
    for order in orders:
        public_order = {
            key: value
            for key, value in order.items()
            if key not in {"partition", "first_global_tube_index"}
        }
        order_rows.append(public_order)
        billet_rows.append(_build_billet(order, product_map[order["product_code"]], billet_rng))
    raw_writer.write_rows("production_orders", order_rows, partition=partition)
    raw_writer.write_rows("billet_batches", billet_rows, partition=partition)

    for order in orders:
        product = product_map[order["product_code"]]
        planned_date = order["scheduled_start_ts"].date()
        day_index = (planned_date - config.period.start_date).days
        day_fraction = day_index / max(config.period.duration_days - 1, 1)
        for tube_sequence in range(order["quantity_tubes"]):
            global_index = order["first_global_tube_index"] + tube_sequence
            heat_treatment_applied = _heat_treatment_selected(
                global_index, config.volume_targets.tubes, treatment_count
            )
            tube_id = deterministic_id("TUB", order["order_id"], tube_sequence)
            actual_start = order["scheduled_start_ts"] + timedelta(minutes=tube_sequence * 3.2)
            synthesis = synthesize_tube(
                rng=process_rng,
                product=product,
                grade_family=order["grade_family"],
                line_id=order["line_id"],
                shift_id=order["shift_id"],
                day_fraction=day_fraction,
                global_tube_index=global_index,
                heat_treatment_applied=heat_treatment_applied,
                ambient_temperature_c=order["ambient_temperature_c"],
            )
            duration_minutes = 135.0 if heat_treatment_applied else 81.0
            actual_end = actual_start + timedelta(minutes=duration_minutes)

            raw_buffers["tubes"].append(
                {
                    "tube_id": tube_id,
                    "order_id": order["order_id"],
                    "billet_batch_id": order["billet_batch_id"],
                    "tube_sequence": tube_sequence,
                    "product_code": order["product_code"],
                    "grade_family": order["grade_family"],
                    "line_id": order["line_id"],
                    "shift_id": order["shift_id"],
                    "actual_start_ts": actual_start,
                    "actual_end_ts": actual_end,
                    "tube_mass_kg": synthesis.outcomes["tube_mass_kg"],
                    "approved_first_pass": synthesis.outcomes["approved_first_pass"],
                    "disposition": synthesis.outcomes["disposition"],
                    "good_mass_t": synthesis.outcomes["good_mass_t"],
                    "productive_hours": synthesis.outcomes["productive_hours"],
                    "actual_tph": synthesis.outcomes["actual_tph"],
                    "simulation_run_id": run_id,
                }
            )
            raw_buffers["process_parameters"].append(
                {
                    "tube_id": tube_id,
                    "order_id": order["order_id"],
                    "product_code": order["product_code"],
                    "grade_family": order["grade_family"],
                    "line_id": order["line_id"],
                    "shift_id": order["shift_id"],
                    "process_start_ts": actual_start,
                    "ambient_temperature_c": order["ambient_temperature_c"],
                    **synthesis.process,
                    "simulation_run_id": run_id,
                }
            )
            raw_buffers["stage_events"].extend(
                _stage_rows(
                    tube_id=tube_id,
                    order=order,
                    actual_start=actual_start,
                    actual_end=actual_end,
                    heat_treatment_applied=heat_treatment_applied,
                    process=synthesis.process,
                    run_id=run_id,
                )
            )
            raw_buffers["sensor_windows"].extend(
                _sensor_rows(
                    tube_id=tube_id,
                    order=order,
                    actual_start=actual_start,
                    process=synthesis.process,
                    outcomes=synthesis.outcomes,
                    global_tube_index=global_index,
                    day_index=day_index,
                    rng=sensor_rng,
                    run_id=run_id,
                )
            )
            raw_buffers["quality_results"].extend(
                _quality_rows(
                    tube_id=tube_id,
                    order=order,
                    inspection_ts=actual_end - timedelta(minutes=5),
                    outcomes=synthesis.outcomes,
                    run_id=run_id,
                )
            )
            raw_buffers["energy_events"].extend(
                _energy_rows(
                    tube_id=tube_id,
                    order=order,
                    event_ts=actual_end,
                    outcomes=synthesis.outcomes,
                    heat_treatment_applied=heat_treatment_applied,
                    run_id=run_id,
                )
            )
            truth_buffer.append(
                {
                    "tube_id": tube_id,
                    "order_id": order["order_id"],
                    "product_code": order["product_code"],
                    "grade_family": order["grade_family"],
                    "line_id": order["line_id"],
                    "event_date": planned_date,
                    **synthesis.truth,
                    "simulation_run_id": run_id,
                }
            )

            for table_name, buffer in raw_buffers.items():
                if len(buffer) >= batch_size:
                    raw_writer.write_rows(table_name, buffer, partition=partition)
                    buffer.clear()
            if len(truth_buffer) >= batch_size:
                truth_writer.write_rows("tube_causal_truth", truth_buffer, partition=partition)
                truth_buffer.clear()

    for table_name, buffer in raw_buffers.items():
        raw_writer.write_rows(table_name, buffer, partition=partition)
    truth_writer.write_rows("tube_causal_truth", truth_buffer, partition=partition)


def _maintenance_rows(
    *,
    bundle: ProjectConfigBundle,
    seed_book: SeedBook,
    run_id: str,
) -> list[dict[str, Any]]:
    config = bundle.simulation
    rng = seed_book.rng("maintenance")
    rows = []
    asset_types = (
        "REHEAT_FURNACE",
        "PIERCING_MILL",
        "ROLLING_MILL",
        "HEAT_TREATMENT",
        "INSPECTION_LINE",
    )
    event_index = 0
    for day_offset in range(0, config.period.duration_days, 5):
        event_date = config.period.start_date + timedelta(days=day_offset)
        for line_index, line_id in enumerate(config.plant.lines):
            asset_type = asset_types[(day_offset // 5 + line_index) % len(asset_types)]
            scheduled = datetime.combine(event_date, datetime.min.time(), tzinfo=UTC) + timedelta(
                hours=6 + line_index
            )
            deferred = (event_index + line_index) % 11 == 0
            actual = scheduled + timedelta(hours=12 if deferred else 0)
            duration = max(25.0, float(rng.normal(78.0, 22.0)))
            rows.append(
                {
                    "maintenance_event_id": deterministic_id("MNT", run_id, event_index),
                    "asset_id": deterministic_id("AST", line_id, asset_type),
                    "line_id": line_id,
                    "maintenance_type": "PREVENTIVE" if event_index % 4 else "CONDITION_BASED",
                    "scheduled_start_ts": scheduled,
                    "actual_start_ts": actual,
                    "actual_end_ts": actual + timedelta(minutes=duration),
                    "duration_minutes": round(duration, 4),
                    "was_deferred": deferred,
                    "work_order_status": "COMPLETED",
                    "partition": _partition_key(event_date, config.output.partition_frequency),
                    "simulation_run_id": run_id,
                }
            )
            event_index += 1
    return rows


def _downtime_rows(
    *,
    bundle: ProjectConfigBundle,
    seed_book: SeedBook,
    run_id: str,
) -> list[dict[str, Any]]:
    config = bundle.simulation
    rng = seed_book.rng("downtime")
    days = config.period.duration_days
    candidates = [(day_index, line_index) for day_index in range(days) for line_index in range(3)]
    weights = np.array(
        [
            0.65
            + 0.75 * day_index / max(days - 1, 1)
            + 0.12 * line_index
            + 0.18 * math.sin(day_index / 9.0 + line_index)
            for day_index, line_index in candidates
        ]
    )
    weights = weights / weights.sum()
    chosen = rng.choice(
        len(candidates), size=config.volume_targets.downtime_events, replace=True, p=weights
    )
    reasons = ("MECHANICAL", "ELECTRICAL", "SENSOR_FAULT", "MATERIAL_JAM")
    asset_by_reason = {
        "MECHANICAL": "ROLLING_MILL",
        "ELECTRICAL": "REHEAT_FURNACE",
        "SENSOR_FAULT": "INSPECTION_LINE",
        "MATERIAL_JAM": "PIERCING_MILL",
    }
    rows = []
    for event_index, candidate_index in enumerate(chosen):
        day_index, line_index = candidates[int(candidate_index)]
        event_date = config.period.start_date + timedelta(days=day_index)
        line_id = config.plant.lines[line_index]
        day_fraction = day_index / max(days - 1, 1)
        hours_since_maintenance = _bounded(
            28 + 470 * ((event_index * 37 + day_index) % 503) / 503 + rng.normal(0, 8),
            0,
            560,
        )
        degradation = _bounded(
            0.08 + 0.62 * hours_since_maintenance / 560 + 0.18 * day_fraction + rng.normal(0, 0.04),
            0,
            1,
        )
        deferred = hours_since_maintenance > 430
        reason_probabilities = np.array((0.38, 0.20, 0.16 + 0.20 * degradation, 0.26), dtype=float)
        reason_probabilities /= reason_probabilities.sum()
        reason = str(rng.choice(reasons, p=reason_probabilities))
        risk_multiplier = 1.0 + 1.3 * degradation + 0.65 * deferred + 0.25 * day_fraction
        duration = _bounded(float(rng.lognormal(2.25, 0.70)) * risk_multiplier, 2.0, 360.0)
        start_ts = datetime.combine(event_date, datetime.min.time(), tzinfo=UTC) + timedelta(
            minutes=int(rng.integers(0, 1440))
        )
        asset_type = asset_by_reason[reason]
        rows.append(
            {
                "downtime_event_id": deterministic_id("DWT", run_id, event_index),
                "line_id": line_id,
                "asset_id": deterministic_id("AST", line_id, asset_type),
                "reason_code": reason,
                "event_start_ts": start_ts,
                "event_end_ts": start_ts + timedelta(minutes=duration),
                "duration_minutes": round(duration, 5),
                "hours_since_maintenance": round(hours_since_maintenance, 4),
                "sensor_degradation_index": round(degradation, 6),
                "maintenance_deferred": deferred,
                "production_impact_t": round(duration / 60.0 * (18 + line_index * 2), 5),
                "unplanned": True,
                "partition": _partition_key(event_date, config.output.partition_frequency),
                "simulation_run_id": run_id,
            }
        )
    return rows


def _write_grouped_rows(
    writer: DatasetWriter,
    table_name: str,
    rows: list[dict[str, Any]],
) -> None:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        partition = row.pop("partition")
        grouped[partition].append(row)
    for partition in sorted(grouped):
        writer.write_rows(table_name, grouped[partition], partition=partition)


def generate_dataset(
    bundle: ProjectConfigBundle,
    *,
    project_root: Path,
    output_base: Path | None = None,
    ground_truth_base: Path | None = None,
    overwrite: bool = False,
) -> GenerationResult:
    """Generate one profile atomically and return its verified lineage metadata."""

    config = bundle.simulation
    config_hash = bundle.stable_hash()
    run_id = deterministic_run_id(
        config.profile.value,
        config.generator_version,
        config.random_seed,
        config_hash,
    )
    output_base = (output_base or project_root / config.output.base_path).resolve()
    ground_truth_base = (ground_truth_base or project_root / "data" / "ground_truth").resolve()
    raw_parent = output_base / config.profile.value
    truth_parent = ground_truth_base / config.profile.value
    raw_final = raw_parent / run_id
    truth_final = truth_parent / run_id
    raw_staging = raw_parent / f".{run_id}.staging"
    truth_staging = truth_parent / f".{run_id}.staging"
    effective_overwrite = overwrite or config.output.overwrite

    for parent in (raw_parent, truth_parent):
        parent.mkdir(parents=True, exist_ok=True)
    if raw_final.exists() or truth_final.exists():
        if not effective_overwrite:
            raise GenerationError(
                f"run already exists for profile {config.profile.value}: {run_id}; "
                "use --force only after confirming replacement"
            )
        _safe_remove_tree(raw_final, raw_parent)
        _safe_remove_tree(truth_final, truth_parent)
    _safe_remove_tree(raw_staging, raw_parent)
    _safe_remove_tree(truth_staging, truth_parent)

    seed_book = SeedBook(config.random_seed)
    started_at = utc_now()
    start_clock = time.perf_counter()
    manifest = base_manifest(
        simulation_run_id=run_id,
        generator_version=config.generator_version,
        profile=config.profile.value,
        master_seed=config.random_seed,
        derived_seeds=seed_book.manifest_seeds(),
        seed_derivation=SEED_DERIVATION,
        config_hash=config_hash,
        period={
            "start_date": config.period.start_date.isoformat(),
            "end_date": config.period.end_date.isoformat(),
        },
        requested_volumes=config.volume_targets.model_dump(),
        started_at=started_at,
    )
    artifacts_dir = project_root / "artifacts" / "runs"

    try:
        raw_writer = DatasetWriter(raw_staging)
        truth_writer = DatasetWriter(truth_staging)
        products = product_catalog(config.plant.product_codes)
        product_map = {product.product_code: product for product in products}
        for table_name, rows in _build_dimensions(
            bundle=bundle,
            products=products,
            run_id=run_id,
        ).items():
            raw_writer.write_rows(table_name, rows)

        orders = _build_orders(
            bundle=bundle,
            products=products,
            seed_book=seed_book,
            run_id=run_id,
        )
        orders_by_partition: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for order in orders:
            orders_by_partition[order["partition"]].append(order)

        treatment_count = (
            config.volume_targets.stage_events - len(BASE_STAGES) * config.volume_targets.tubes
        )
        if not 0 <= treatment_count <= config.volume_targets.tubes:
            raise GenerationError(
                "stage_events target must support seven base stages and at most "
                "one heat-treatment stage per tube"
            )
        if (
            config.volume_targets.sensor_windows
            != len(SENSOR_TYPES) * 4 * config.volume_targets.tubes
        ):
            raise GenerationError("sensor_windows target must equal 32 summarized windows per tube")
        if (
            config.volume_targets.quality_results
            != len(QUALITY_CHARACTERISTICS) * config.volume_targets.tubes
        ):
            raise GenerationError("quality_results target must equal six inspections per tube")

        for partition in sorted(orders_by_partition):
            _generate_partition(
                partition=partition,
                orders=orders_by_partition[partition],
                product_map=product_map,
                bundle=bundle,
                seed_book=seed_book,
                run_id=run_id,
                raw_writer=raw_writer,
                truth_writer=truth_writer,
                treatment_count=treatment_count,
            )

        _write_grouped_rows(
            raw_writer,
            "maintenance_events",
            _maintenance_rows(bundle=bundle, seed_book=seed_book, run_id=run_id),
        )
        _write_grouped_rows(
            raw_writer,
            "downtime_events",
            _downtime_rows(bundle=bundle, seed_book=seed_book, run_id=run_id),
        )

        truth_summary = truth_writer.table_summary()
        truth_manifest = {
            "schema_version": "1.0",
            "simulation_run_id": run_id,
            "truth_version": TRUTH_VERSION,
            "access_policy": bundle.causal_rules.access_policy.model_dump(mode="json"),
            "tables": truth_summary,
            "dataset_logical_sha256": truth_writer.dataset_logical_hash(),
            "warning": (
                "Isolated synthetic truth; prohibited for feature engineering and model training."
            ),
        }
        write_manifest(truth_staging / "ground_truth_manifest.json", truth_manifest)

        finished_at = utc_now()
        elapsed = time.perf_counter() - start_clock
        manifest.update(
            {
                "finished_at_utc": finished_at.isoformat(),
                "elapsed_seconds": round(elapsed, 6),
                "status": "success",
                "tables": raw_writer.table_summary(),
                "ground_truth": {
                    "truth_version": TRUTH_VERSION,
                    "rows": truth_summary["tube_causal_truth"]["rows"],
                    "logical_sha256": truth_summary["tube_causal_truth"]["logical_sha256"],
                    "access": "generation_and_separate_audit_only",
                },
                "dataset_logical_sha256": raw_writer.dataset_logical_hash(),
            }
        )
        write_manifest(raw_staging / "run_manifest.json", manifest)
        _atomic_promote(truth_staging, truth_final)
        _atomic_promote(raw_staging, raw_final)
        write_manifest(artifacts_dir / f"{run_id}-manifest.json", manifest)
        counts = {
            table_name: int(summary["rows"]) for table_name, summary in manifest["tables"].items()
        }
        return GenerationResult(
            simulation_run_id=run_id,
            raw_path=raw_final,
            ground_truth_path=truth_final,
            manifest_path=raw_final / "run_manifest.json",
            table_counts=counts,
            dataset_logical_sha256=manifest["dataset_logical_sha256"],
            elapsed_seconds=elapsed,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start_clock
        manifest.update(
            {
                "finished_at_utc": utc_now().isoformat(),
                "elapsed_seconds": round(elapsed, 6),
                "status": "failed",
                "errors": [{"type": type(exc).__name__, "message": str(exc)}],
            }
        )
        write_manifest(artifacts_dir / f"{run_id}-failed.json", manifest)
        _safe_remove_tree(raw_staging, raw_parent)
        _safe_remove_tree(truth_staging, truth_parent)
        if isinstance(exc, GenerationError):
            raise
        raise GenerationError(f"generation failed for {run_id}: {exc}") from exc


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationError(f"could not read run manifest {path}: {exc}") from exc
