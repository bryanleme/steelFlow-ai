-- Point-in-time snapshots. No target or post-process field is selected.

CREATE TABLE features.pre_order_snapshot AS
WITH base AS (
    SELECT
        o.order_id,
        greatest(o.release_ts, b.received_ts) AS snapshot_ts,
        o.product_code,
        o.grade_family,
        o.line_id,
        o.shift_id,
        o.quantity_tubes,
        o.target_tonnes,
        o.priority_code,
        o.committed_sequence,
        o.ambient_temperature_c,
        b.carbon_pct,
        b.manganese_pct,
        b.chromium_pct,
        b.molybdenum_pct,
        b.billet_diameter_mm,
        b.billet_mass_kg,
        b.received_ts,
        (
            SELECT max(m.actual_end_ts)
            FROM curated.maintenance_events m
            WHERE m.line_id = o.line_id
              AND m.actual_end_ts <= greatest(o.release_ts, b.received_ts)
        ) AS last_maintenance_ts,
        o.simulation_run_id
    FROM curated.production_orders o
    JOIN curated.billet_batches b USING (order_id)
)
SELECT
    *,
    date_diff('hour', last_maintenance_ts, snapshot_ts) AS hours_since_last_maintenance,
    greatest(received_ts, coalesce(last_maintenance_ts, received_ts)) AS feature_max_source_ts
FROM base;

CREATE TABLE features.in_process_rolling_snapshot AS
WITH rolling_stage AS (
    SELECT tube_id, max(event_end_ts) AS snapshot_ts
    FROM curated.stage_events
    WHERE stage_name = 'ROLLING_SIZING'
    GROUP BY tube_id
),
sensor_state AS (
    SELECT
        s.tube_id,
        max(s.feature_available_at_ts) AS sensor_max_source_ts,
        avg(s.mean_value) FILTER (WHERE s.sensor_type = 'furnace_zone_temperature')
            AS observed_furnace_temperature,
        avg(s.mean_value) FILTER (WHERE s.sensor_type = 'reheat_exit_temperature')
            AS observed_reheat_exit_temperature,
        avg(s.mean_value) FILTER (WHERE s.sensor_type = 'roll_speed')
            AS observed_roll_speed,
        avg(s.mean_value) FILTER (WHERE s.sensor_type = 'rolling_load')
            AS observed_rolling_load,
        avg(s.mean_value) FILTER (WHERE s.sensor_type = 'lubrication_flow')
            AS observed_lubrication_flow,
        avg(s.mean_value) FILTER (WHERE s.sensor_type = 'mill_vibration')
            AS observed_mill_vibration,
        avg(s.out_of_range_pct) AS mean_sensor_out_of_range_pct,
        avg((s.data_quality_status = 'VALID')::INTEGER) AS valid_sensor_window_rate
    FROM curated.sensor_windows s
    JOIN rolling_stage r USING (tube_id)
    WHERE s.feature_available_at_ts <= r.snapshot_ts
    GROUP BY s.tube_id
)
SELECT
    p.tube_id,
    p.order_id,
    r.snapshot_ts,
    p.product_code,
    p.grade_family,
    p.line_id,
    p.shift_id,
    p.ambient_temperature_c,
    p.tool_wear_index,
    p.hours_since_maintenance,
    p.maintenance_deferred,
    p.sensor_degradation_index,
    p.reheat_zone_1_temp_c,
    p.reheat_zone_2_temp_c,
    p.reheat_zone_3_temp_c,
    p.soak_time_min,
    p.reheat_exit_temp_c,
    p.thermal_uniformity_index,
    p.roll_speed_rpm,
    p.roll_gap_mm,
    p.mandrel_position_mm,
    p.reduction_rate_pct,
    p.exit_speed_m_s,
    p.lubrication_flow_l_min,
    p.rolling_load_index,
    s.observed_furnace_temperature,
    s.observed_reheat_exit_temperature,
    s.observed_roll_speed,
    s.observed_rolling_load,
    s.observed_lubrication_flow,
    s.observed_mill_vibration,
    s.mean_sensor_out_of_range_pct,
    s.valid_sensor_window_rate,
    greatest(p.process_start_ts, coalesce(s.sensor_max_source_ts, p.process_start_ts))
        AS feature_max_source_ts,
    p.simulation_run_id
FROM curated.process_parameters p
JOIN rolling_stage r USING (tube_id)
LEFT JOIN sensor_state s USING (tube_id);

CREATE TABLE model_outputs.predictions (
    prediction_id VARCHAR PRIMARY KEY,
    entity_id VARCHAR NOT NULL,
    prediction_time_ts TIMESTAMPTZ NOT NULL,
    target_name VARCHAR NOT NULL,
    p10 DOUBLE,
    p50 DOUBLE,
    p90 DOUBLE,
    calibrated_probability DOUBLE,
    model_version VARCHAR NOT NULL,
    simulation_run_id VARCHAR NOT NULL
);

CREATE TABLE model_outputs.scenario_recommendations (
    scenario_id VARCHAR PRIMARY KEY,
    context_id VARCHAR NOT NULL,
    scenario_label VARCHAR NOT NULL,
    in_distribution BOOLEAN NOT NULL,
    requires_human_approval BOOLEAN NOT NULL DEFAULT TRUE,
    payload_json JSON NOT NULL,
    model_version VARCHAR NOT NULL,
    simulation_run_id VARCHAR NOT NULL
);
