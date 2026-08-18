-- Phase 4 diagnostic tables and point-in-time asset windows.
-- Diagnostic associations are retrospective and must not be described as industrial causality.

CREATE TABLE features.asset_window_snapshot AS
WITH windows AS (
    SELECT
        concat(
            strftime(d.full_date, '%Y%m%d'), '-', da.asset_id, '-',
            lpad(CAST(h.window_hour AS VARCHAR), 2, '0')
        ) AS window_id,
        CAST(CAST(d.full_date AS TIMESTAMP) + h.window_hour * INTERVAL '1 hour' AS TIMESTAMPTZ)
            AS snapshot_ts,
        d.month_number,
        d.day_of_week,
        d.is_weekend,
        da.asset_id,
        da.asset_type,
        da.criticality AS asset_criticality,
        da.line_id,
        ds.shift_id,
        h.window_hour
    FROM analytics.dim_date d
    CROSS JOIN analytics.dim_asset da
    CROSS JOIN range(0, 24, 2) AS h(window_hour)
    JOIN analytics.dim_shift ds
        ON ds.start_hour = 8 * floor(h.window_hour / 8)
),
history AS (
    SELECT
        w.*,
        (
            SELECT count(*)
            FROM curated.downtime_events de
            WHERE de.asset_id = w.asset_id
              AND de.event_end_ts <= w.snapshot_ts
              AND de.event_end_ts > w.snapshot_ts - INTERVAL '7 days'
        ) AS prior_7d_downtime_events,
        coalesce((
            SELECT sum(de.duration_minutes)
            FROM curated.downtime_events de
            WHERE de.asset_id = w.asset_id
              AND de.event_end_ts <= w.snapshot_ts
              AND de.event_end_ts > w.snapshot_ts - INTERVAL '7 days'
        ), 0.0) AS prior_7d_downtime_minutes,
        (
            SELECT count(*)
            FROM curated.downtime_events de
            WHERE de.asset_id = w.asset_id
              AND de.event_end_ts <= w.snapshot_ts
              AND de.event_end_ts > w.snapshot_ts - INTERVAL '30 days'
        ) AS prior_30d_downtime_events,
        coalesce((
            SELECT sum(de.duration_minutes)
            FROM curated.downtime_events de
            WHERE de.asset_id = w.asset_id
              AND de.event_end_ts <= w.snapshot_ts
              AND de.event_end_ts > w.snapshot_ts - INTERVAL '30 days'
        ), 0.0) AS prior_30d_downtime_minutes,
        (
            SELECT count(*)
            FROM curated.maintenance_events me
            WHERE me.asset_id = w.asset_id
              AND me.actual_end_ts <= w.snapshot_ts
              AND me.actual_end_ts > w.snapshot_ts - INTERVAL '7 days'
        ) AS prior_7d_maintenance_events,
        coalesce((
            SELECT sum(me.duration_minutes)
            FROM curated.maintenance_events me
            WHERE me.asset_id = w.asset_id
              AND me.actual_end_ts <= w.snapshot_ts
              AND me.actual_end_ts > w.snapshot_ts - INTERVAL '7 days'
        ), 0.0) AS prior_7d_maintenance_minutes,
        (
            SELECT avg(pp.sensor_degradation_index)
            FROM curated.process_parameters pp
            WHERE pp.line_id = w.line_id
              AND pp.process_start_ts < w.snapshot_ts
              AND pp.process_start_ts >= w.snapshot_ts - INTERVAL '7 days'
        ) AS prior_mean_sensor_degradation,
        (
            SELECT avg(pp.tool_wear_index)
            FROM curated.process_parameters pp
            WHERE pp.line_id = w.line_id
              AND pp.process_start_ts < w.snapshot_ts
              AND pp.process_start_ts >= w.snapshot_ts - INTERVAL '7 days'
        ) AS prior_mean_tool_wear,
        (
            SELECT max(de.event_end_ts)
            FROM curated.downtime_events de
            WHERE de.asset_id = w.asset_id AND de.event_end_ts <= w.snapshot_ts
        ) AS last_downtime_source_ts,
        (
            SELECT max(me.actual_end_ts)
            FROM curated.maintenance_events me
            WHERE me.asset_id = w.asset_id AND me.actual_end_ts <= w.snapshot_ts
        ) AS last_maintenance_source_ts,
        (
            SELECT max(pp.process_start_ts)
            FROM curated.process_parameters pp
            WHERE pp.line_id = w.line_id AND pp.process_start_ts < w.snapshot_ts
        ) AS last_process_source_ts
    FROM windows w
)
SELECT
    window_id,
    snapshot_ts,
    asset_id,
    asset_type,
    asset_criticality,
    line_id,
    shift_id,
    window_hour,
    month_number,
    day_of_week,
    is_weekend,
    prior_7d_downtime_events,
    prior_7d_downtime_minutes,
    prior_30d_downtime_events,
    prior_30d_downtime_minutes,
    prior_7d_maintenance_events,
    prior_7d_maintenance_minutes,
    prior_mean_sensor_degradation,
    prior_mean_tool_wear,
    date_diff('hour', last_maintenance_source_ts, snapshot_ts)
        AS hours_since_last_maintenance,
    greatest(last_downtime_source_ts, last_maintenance_source_ts, last_process_source_ts)
        AS feature_max_source_ts,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM history;

CREATE UNIQUE INDEX idx_asset_window_snapshot_pk
    ON features.asset_window_snapshot(window_id);

CREATE TABLE analytics.diagnostic_daily_trend AS
SELECT
    d.full_date,
    f.*,
    f.tbh - lag(f.tbh) OVER (PARTITION BY f.line_key, f.shift_key ORDER BY f.date_key)
        AS tbh_change_from_previous_window,
    f.fpy - lag(f.fpy) OVER (PARTITION BY f.line_key, f.shift_key ORDER BY f.date_key)
        AS fpy_change_from_previous_window
FROM analytics.mart_line_shift_performance f
JOIN analytics.dim_date d USING (date_key);

CREATE TABLE analytics.diagnostic_mix_adjustment AS
WITH segment_baseline AS (
    SELECT
        product_code,
        grade_family,
        line_id,
        median(tbh) AS segment_median_tbh,
        count(*) AS baseline_order_count
    FROM analytics.mart_order_performance
    GROUP BY product_code, grade_family, line_id
),
weighted AS (
    SELECT
        o.date_key,
        o.line_key,
        min(o.line_id) AS line_id,
        sum(o.good_tonnes) AS good_tonnes,
        sum(o.productive_hours) AS productive_hours,
        sum(b.segment_median_tbh * o.productive_hours) AS mix_expected_good_tonnes,
        count(*) AS order_count,
        sum((b.baseline_order_count < 3)::INTEGER) AS low_support_segment_orders
    FROM analytics.mart_order_performance o
    JOIN segment_baseline b USING (product_code, grade_family, line_id)
    GROUP BY o.date_key, o.line_key
),
metrics AS (
    SELECT
        *,
        good_tonnes / NULLIF(productive_hours, 0) AS actual_tbh,
        mix_expected_good_tonnes / NULLIF(productive_hours, 0) AS mix_expected_tbh
    FROM weighted
)
SELECT
    *,
    actual_tbh - mix_expected_tbh AS mix_adjusted_tbh_gap,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM metrics;

CREATE TABLE analytics.diagnostic_spc_tbh AS
WITH cutoff AS (
    SELECT quantile_disc(date_key, 0.30) AS baseline_end_date_key
    FROM analytics.mart_line_shift_performance
),
baseline AS (
    SELECT
        f.line_key,
        avg(f.tbh) AS centerline_tbh,
        stddev_samp(f.tbh) AS sigma_tbh,
        count(*) AS baseline_observations,
        max(f.date_key) AS baseline_end_date_key
    FROM analytics.mart_line_shift_performance f
    CROSS JOIN cutoff c
    WHERE f.date_key <= c.baseline_end_date_key
    GROUP BY f.line_key
)
SELECT
    f.date_key,
    f.line_key,
    f.shift_key,
    f.line_id,
    f.shift_id,
    f.tbh,
    b.centerline_tbh,
    greatest(b.centerline_tbh - 3.0 * coalesce(b.sigma_tbh, 0.0), 0.0) AS lower_control_tbh,
    b.centerline_tbh + 3.0 * coalesce(b.sigma_tbh, 0.0) AS upper_control_tbh,
    b.baseline_observations,
    b.baseline_end_date_key,
    b.baseline_observations >= 5 AS limits_reliable,
    CASE
        WHEN b.baseline_observations >= 5 AND b.sigma_tbh > 0
        THEN f.tbh < b.centerline_tbh - 3.0 * b.sigma_tbh
          OR f.tbh > b.centerline_tbh + 3.0 * b.sigma_tbh
        ELSE FALSE
    END AS control_signal,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM analytics.mart_line_shift_performance f
JOIN baseline b USING (line_key);

CREATE TABLE analytics.diagnostic_spc_quality AS
WITH cutoff AS (
    SELECT quantile_disc(date_key, 0.30) AS baseline_end_date_key
    FROM analytics.mart_quality_summary
),
baseline AS (
    SELECT
        q.line_key,
        q.characteristic,
        avg(q.mean_value) AS centerline_value,
        stddev_samp(q.mean_value) AS sigma_value,
        count(*) AS baseline_observations,
        max(q.date_key) AS baseline_end_date_key
    FROM analytics.mart_quality_summary q
    CROSS JOIN cutoff c
    WHERE q.date_key <= c.baseline_end_date_key
    GROUP BY q.line_key, q.characteristic
)
SELECT
    q.date_key,
    q.product_key,
    q.line_key,
    q.product_code,
    q.grade_family,
    q.line_id,
    q.characteristic,
    q.unit,
    q.inspection_count,
    q.mean_value,
    q.conformance_rate,
    b.centerline_value,
    b.centerline_value - 3.0 * coalesce(b.sigma_value, 0.0) AS lower_control_value,
    b.centerline_value + 3.0 * coalesce(b.sigma_value, 0.0) AS upper_control_value,
    b.baseline_observations,
    b.baseline_end_date_key,
    b.baseline_observations >= 5 AS limits_reliable,
    CASE
        WHEN b.baseline_observations >= 5 AND b.sigma_value > 0
        THEN q.mean_value < b.centerline_value - 3.0 * b.sigma_value
          OR q.mean_value > b.centerline_value + 3.0 * b.sigma_value
        ELSE FALSE
    END AS control_signal,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM analytics.mart_quality_summary q
JOIN baseline b USING (line_key, characteristic);

CREATE TABLE analytics.diagnostic_process_interactions AS
WITH quality AS (
    SELECT
        tube_id,
        max(measured_value) FILTER (WHERE characteristic = 'wall_eccentricity_pct')
            AS wall_eccentricity_pct,
        max(measured_value) FILTER (WHERE characteristic = 'outer_diameter_deviation_mm')
            AS outer_diameter_deviation_mm,
        max(measured_value) FILTER (WHERE characteristic = 'ovality_pct') AS ovality_pct
    FROM analytics.fact_quality
    GROUP BY tube_id
),
energy AS (
    SELECT tube_id, sum(energy_kwh) AS energy_kwh
    FROM analytics.fact_energy
    GROUP BY tube_id
),
ranked AS (
    SELECT
        p.*,
        pp.roll_speed_rpm,
        pp.thermal_uniformity_index,
        pp.tool_wear_index,
        q.wall_eccentricity_pct,
        q.outer_diameter_deviation_mm,
        q.ovality_pct,
        e.energy_kwh,
        ntile(3) OVER (
            PARTITION BY p.product_code, p.grade_family
            ORDER BY pp.roll_speed_rpm, p.tube_id
        ) AS roll_speed_band,
        ntile(3) OVER (
            PARTITION BY p.product_code, p.grade_family
            ORDER BY pp.thermal_uniformity_index, p.tube_id
        ) AS thermal_uniformity_band
    FROM analytics.fact_production p
    JOIN curated.process_parameters pp USING (tube_id)
    JOIN quality q USING (tube_id)
    JOIN energy e USING (tube_id)
)
SELECT
    product_code,
    grade_family,
    line_id,
    roll_speed_band,
    thermal_uniformity_band,
    count(*) AS tube_count,
    avg(actual_tph) AS mean_actual_tph,
    avg(approved_first_pass::INTEGER) AS fpy,
    avg((disposition = 'REWORK')::INTEGER) AS rework_rate,
    avg((disposition = 'SCRAP')::INTEGER) AS scrap_rate,
    avg(wall_eccentricity_pct) AS mean_wall_eccentricity_pct,
    avg(outer_diameter_deviation_mm) AS mean_outer_diameter_deviation_mm,
    avg(ovality_pct) AS mean_ovality_pct,
    avg(energy_kwh) AS mean_energy_kwh,
    avg(roll_speed_rpm) AS mean_roll_speed_rpm,
    avg(thermal_uniformity_index) AS mean_thermal_uniformity_index,
    avg(tool_wear_index) AS mean_tool_wear_index,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM ranked
GROUP BY product_code, grade_family, line_id, roll_speed_band, thermal_uniformity_band;

CREATE TABLE analytics.diagnostic_segment_associations AS
WITH quality AS (
    SELECT
        tube_id,
        max(measured_value) FILTER (WHERE characteristic = 'wall_eccentricity_pct')
            AS wall_eccentricity_pct
    FROM analytics.fact_quality
    GROUP BY tube_id
)
SELECT
    p.product_code,
    p.grade_family,
    p.line_id,
    count(*) AS tube_count,
    corr(pp.roll_speed_rpm, p.actual_tph) AS association_roll_speed_tph,
    corr(pp.thermal_uniformity_index, q.wall_eccentricity_pct)
        AS association_uniformity_eccentricity,
    corr(pp.tool_wear_index, q.wall_eccentricity_pct)
        AS association_wear_eccentricity,
    corr(pp.sensor_degradation_index, p.actual_tph)
        AS association_sensor_degradation_tph,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM analytics.fact_production p
JOIN curated.process_parameters pp USING (tube_id)
JOIN quality q USING (tube_id)
GROUP BY p.product_code, p.grade_family, p.line_id;
