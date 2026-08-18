"""Table contracts shared by generation and raw-data validation."""

from __future__ import annotations

TABLE_PRIMARY_KEYS: dict[str, str] = {
    "dim_products": "product_code",
    "dim_lines": "line_id",
    "dim_shifts": "shift_id",
    "dim_assets": "asset_id",
    "feature_availability": "feature_name",
    "production_orders": "order_id",
    "billet_batches": "billet_batch_id",
    "tubes": "tube_id",
    "process_parameters": "tube_id",
    "stage_events": "stage_event_id",
    "sensor_windows": "sensor_window_id",
    "quality_results": "quality_result_id",
    "energy_events": "energy_event_id",
    "downtime_events": "downtime_event_id",
    "maintenance_events": "maintenance_event_id",
}

FACT_TABLES = (
    "production_orders",
    "billet_batches",
    "tubes",
    "process_parameters",
    "stage_events",
    "sensor_windows",
    "quality_results",
    "energy_events",
    "downtime_events",
    "maintenance_events",
)

DIMENSION_TABLES = (
    "dim_products",
    "dim_lines",
    "dim_shifts",
    "dim_assets",
    "feature_availability",
)

EXPECTED_TABLES = DIMENSION_TABLES + FACT_TABLES

QUALITY_CHARACTERISTICS = (
    "outer_diameter_deviation_mm",
    "wall_eccentricity_pct",
    "ovality_pct",
    "yield_strength_mpa",
    "tensile_strength_mpa",
    "ndt_indication_score",
)

SENSOR_TYPES = (
    "furnace_zone_temperature",
    "reheat_exit_temperature",
    "roll_speed",
    "rolling_load",
    "lubrication_flow",
    "mill_vibration",
    "electrical_power",
    "quench_flow",
)

BASE_STAGES = (
    "ORDER_RELEASE",
    "BILLET_RECEIPT",
    "REHEATING",
    "PIERCING_ELONGATION",
    "ROLLING_SIZING",
    "INSPECTION",
    "DISPOSITION",
)
