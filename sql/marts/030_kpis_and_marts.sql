-- KPI catalog and executive marts. Every ratio uses NULLIF for zero denominators.

CREATE TABLE analytics.kpi_catalog (
    kpi_name VARCHAR PRIMARY KEY,
    business_label VARCHAR NOT NULL,
    formula VARCHAR NOT NULL,
    grain VARCHAR NOT NULL,
    unit VARCHAR NOT NULL,
    filters VARCHAR NOT NULL,
    source_fields VARCHAR NOT NULL,
    zero_division VARCHAR NOT NULL,
    synthetic_scope VARCHAR NOT NULL
);

INSERT INTO analytics.kpi_catalog VALUES
    ('good_tonnes', 'Good Tonnes', 'SUM(good_mass_t)', 'date x line x shift; order', 't', 'first-pass approved mass only', 'tubes.good_mass_t', 'not applicable', 'internal synthetic prototype'),
    ('productive_hours', 'Productive Hours', 'SUM(productive_hours)', 'date x line x shift; order', 'h', 'all processed tubes', 'tubes.productive_hours', 'not applicable', 'internal synthetic prototype'),
    ('tbh', 'Good Tonnes per Hour', 'SUM(good_mass_t) / SUM(productive_hours)', 'date x line x shift; order', 't/h', 'first-pass good mass', 'tubes.good_mass_t; tubes.productive_hours', 'NULL', 'internal synthetic prototype'),
    ('fpy', 'First Pass Yield', 'SUM(approved_first_pass) / COUNT(tube_id)', 'date x line x shift; order', 'ratio', 'all dispositions', 'tubes.approved_first_pass; tubes.tube_id', 'NULL', 'internal synthetic prototype'),
    ('availability', 'Availability', 'productive_hours / (productive_hours + unplanned_downtime_hours)', 'date x line x shift', 'ratio', 'unplanned downtime only', 'tubes.productive_hours; downtime.duration_minutes', 'NULL', 'internal synthetic prototype'),
    ('performance', 'Performance', 'total_mass_t / (42 internal simulated t/h * productive_hours)', 'date x line x shift', 'ratio', 'capped at 1', 'tubes.tube_mass_kg; tubes.productive_hours', 'NULL', 'internal synthetic prototype'),
    ('quality', 'Quality', 'good_mass_t / total_mass_t', 'date x line x shift', 'ratio', 'first-pass good mass', 'tubes.good_mass_t; tubes.tube_mass_kg', 'NULL', 'internal synthetic prototype'),
    ('oee', 'Overall Equipment Effectiveness', 'availability * performance * quality', 'date x line x shift', 'ratio', 'internal simulated components', 'derived availability; performance; quality', 'NULL', 'internal synthetic prototype'),
    ('scrap_rate', 'Scrap Rate', 'SUM(disposition = SCRAP) / COUNT(tube_id)', 'date x line x shift; order', 'ratio', 'all dispositions', 'tubes.disposition; tubes.tube_id', 'NULL', 'internal synthetic prototype'),
    ('rework_rate', 'Rework Rate', 'SUM(disposition = REWORK) / COUNT(tube_id)', 'date x line x shift; order', 'ratio', 'all dispositions', 'tubes.disposition; tubes.tube_id', 'NULL', 'internal synthetic prototype'),
    ('energy_per_good_tonne', 'Energy per Good Tonne', 'SUM(energy_kwh) / SUM(good_mass_t once per tube)', 'date x line x shift; order', 'kWh/t', 'first-pass good mass', 'energy.energy_kwh; tubes.good_mass_t', 'NULL', 'internal synthetic prototype'),
    ('unplanned_downtime', 'Unplanned Downtime', 'SUM(duration_minutes)', 'date x line x shift', 'min', 'unplanned events', 'downtime.duration_minutes', 'not applicable', 'internal synthetic prototype'),
    ('outer_diameter_deviation', 'Outer Diameter Deviation', 'AVG(measured_value)', 'date x product x line', 'mm', 'characteristic = outer_diameter_deviation_mm', 'quality_results.measured_value; quality_results.characteristic', 'NULL when no inspections exist', 'internal synthetic prototype'),
    ('wall_eccentricity', 'Wall Eccentricity', 'AVG(measured_value)', 'date x product x line', 'pct', 'characteristic = wall_eccentricity_pct', 'quality_results.measured_value; quality_results.characteristic', 'NULL when no inspections exist', 'internal synthetic prototype'),
    ('ovality', 'Ovality', 'AVG(measured_value)', 'date x product x line', 'pct', 'characteristic = ovality_pct', 'quality_results.measured_value; quality_results.characteristic', 'NULL when no inspections exist', 'internal synthetic prototype'),
    ('simulated_mechanical_conformance', 'Simulated Mechanical Conformance', 'SUM(passed) / COUNT(quality_result_id)', 'date x product x line', 'ratio', 'characteristic in yield_strength_mpa, tensile_strength_mpa', 'quality_results.passed; quality_results.characteristic', 'NULL', 'internal simulated limits; not API 5CT validation'),
    ('next_window_downtime_probability', 'Next-window Downtime Probability', 'calibrated_probability; populated only after Phase 5 modeling', 'asset x operational window', 'probability', 'target_name = next_window_downtime', 'model_outputs.predictions.calibrated_probability', 'NULL before a validated model output exists', 'planned model KPI; internal synthetic prototype');

CREATE TABLE analytics.mart_order_performance AS
WITH energy_by_order AS (
    SELECT order_id, sum(energy_kwh) AS energy_kwh
    FROM analytics.fact_energy
    GROUP BY order_id
),
production_by_order AS (
    SELECT
        order_id,
        min(date_key) AS date_key,
        min(product_key) AS product_key,
        min(line_key) AS line_key,
        min(shift_key) AS shift_key,
        min(product_code) AS product_code,
        min(grade_family) AS grade_family,
        min(line_id) AS line_id,
        min(shift_id) AS shift_id,
        count(*) AS tube_count,
        sum(total_mass_t) AS total_tonnes,
        sum(good_mass_t) AS good_tonnes,
        sum(productive_hours) AS productive_hours,
        sum(rework_mass_t) AS rework_tonnes,
        sum(scrap_mass_t) AS scrap_tonnes,
        avg(approved_first_pass::INTEGER) AS fpy,
        avg((disposition = 'REWORK')::INTEGER) AS rework_rate,
        avg((disposition = 'SCRAP')::INTEGER) AS scrap_rate
    FROM analytics.fact_production
    GROUP BY order_id
)
SELECT
    p.*,
    e.energy_kwh,
    p.good_tonnes / NULLIF(p.productive_hours, 0) AS tbh,
    e.energy_kwh / NULLIF(p.good_tonnes, 0) AS energy_per_good_tonne_kwh_t,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM production_by_order p
JOIN energy_by_order e USING (order_id);

CREATE TABLE analytics.mart_line_shift_performance AS
WITH production AS (
    SELECT
        date_key,
        line_key,
        shift_key,
        min(line_id) AS line_id,
        min(shift_id) AS shift_id,
        count(*) AS tube_count,
        sum(total_mass_t) AS total_tonnes,
        sum(good_mass_t) AS good_tonnes,
        sum(productive_hours) AS productive_hours,
        sum(rework_mass_t) AS rework_tonnes,
        sum(scrap_mass_t) AS scrap_tonnes,
        avg(approved_first_pass::INTEGER) AS fpy,
        avg((disposition = 'REWORK')::INTEGER) AS rework_rate,
        avg((disposition = 'SCRAP')::INTEGER) AS scrap_rate
    FROM analytics.fact_production
    GROUP BY date_key, line_key, shift_key
),
energy AS (
    SELECT date_key, line_key, shift_key, sum(energy_kwh) AS energy_kwh
    FROM analytics.fact_energy
    GROUP BY date_key, line_key, shift_key
),
downtime AS (
    SELECT date_key, line_key, shift_key, sum(duration_minutes) AS unplanned_downtime_minutes
    FROM analytics.fact_downtime
    GROUP BY date_key, line_key, shift_key
),
components AS (
    SELECT
        p.*,
        coalesce(e.energy_kwh, 0.0) AS energy_kwh,
        coalesce(d.unplanned_downtime_minutes, 0.0) AS unplanned_downtime_minutes,
        p.good_tonnes / NULLIF(p.productive_hours, 0) AS tbh,
        e.energy_kwh / NULLIF(p.good_tonnes, 0) AS energy_per_good_tonne_kwh_t,
        p.productive_hours
            / NULLIF(p.productive_hours + coalesce(d.unplanned_downtime_minutes, 0.0) / 60.0, 0)
            AS availability,
        least(p.total_tonnes / NULLIF(42.0 * p.productive_hours, 0), 1.0) AS performance,
        p.good_tonnes / NULLIF(p.total_tonnes, 0) AS quality
    FROM production p
    LEFT JOIN energy e USING (date_key, line_key, shift_key)
    LEFT JOIN downtime d USING (date_key, line_key, shift_key)
)
SELECT
    *,
    availability * performance * quality AS oee,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM components;

CREATE VIEW analytics.mart_line_shift_summary AS
WITH summary AS (
    SELECT
        line_key,
        shift_key,
        min(line_id) AS line_id,
        min(shift_id) AS shift_id,
        sum(tube_count) AS tube_count,
        sum(total_tonnes) AS total_tonnes,
        sum(good_tonnes) AS good_tonnes,
        sum(productive_hours) AS productive_hours,
        sum(rework_tonnes) AS rework_tonnes,
        sum(scrap_tonnes) AS scrap_tonnes,
        sum(energy_kwh) AS energy_kwh,
        sum(unplanned_downtime_minutes) AS unplanned_downtime_minutes
    FROM analytics.mart_line_shift_performance
    GROUP BY line_key, shift_key
)
SELECT
    *,
    good_tonnes / NULLIF(productive_hours, 0) AS tbh,
    good_tonnes / NULLIF(total_tonnes, 0) AS quality,
    energy_kwh / NULLIF(good_tonnes, 0) AS energy_per_good_tonne_kwh_t,
    productive_hours / NULLIF(productive_hours + unplanned_downtime_minutes / 60.0, 0)
        AS availability,
    least(total_tonnes / NULLIF(42.0 * productive_hours, 0), 1.0) AS performance
FROM summary;

CREATE TABLE analytics.mart_quality_summary AS
SELECT
    date_key,
    product_key,
    line_key,
    product_code,
    grade_family,
    line_id,
    characteristic,
    unit,
    count(*) AS inspection_count,
    avg(measured_value) AS mean_value,
    stddev_pop(measured_value) AS standard_deviation,
    min(measured_value) AS minimum_value,
    max(measured_value) AS maximum_value,
    avg(passed::INTEGER) AS conformance_rate,
    sum((NOT passed)::INTEGER) AS nonconforming_count,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM analytics.fact_quality
GROUP BY
    date_key, product_key, line_key, product_code, grade_family, line_id, characteristic, unit;

CREATE TABLE analytics.mart_energy_summary AS
SELECT
    date_key,
    line_key,
    shift_key,
    min(line_id) AS line_id,
    min(shift_id) AS shift_id,
    sum(energy_kwh) AS energy_kwh,
    sum(good_mass_t) / 3.0 AS good_tonnes,
    sum(energy_kwh) / NULLIF(sum(good_mass_t) / 3.0, 0) AS energy_per_good_tonne_kwh_t,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM analytics.fact_energy
GROUP BY date_key, line_key, shift_key;

CREATE TABLE analytics.mart_downtime_maintenance AS
WITH downtime AS (
    SELECT
        date_key,
        line_key,
        min(line_id) AS line_id,
        count(*) AS downtime_event_count,
        sum(duration_minutes) AS unplanned_downtime_minutes,
        sum(production_impact_t) AS production_impact_t,
        avg(sensor_degradation_index) AS mean_sensor_degradation,
        avg(maintenance_deferred::INTEGER) AS deferred_context_rate
    FROM analytics.fact_downtime
    GROUP BY date_key, line_key
),
maintenance AS (
    SELECT
        date_key,
        line_key,
        count(*) AS maintenance_event_count,
        sum(duration_minutes) AS maintenance_minutes,
        avg(was_deferred::INTEGER) AS maintenance_deferred_rate
    FROM analytics.fact_maintenance
    GROUP BY date_key, line_key
)
SELECT
    coalesce(d.date_key, m.date_key) AS date_key,
    coalesce(d.line_key, m.line_key) AS line_key,
    coalesce(d.line_id, dl.line_id) AS line_id,
    coalesce(d.downtime_event_count, 0) AS downtime_event_count,
    coalesce(d.unplanned_downtime_minutes, 0.0) AS unplanned_downtime_minutes,
    coalesce(d.production_impact_t, 0.0) AS production_impact_t,
    d.mean_sensor_degradation,
    d.deferred_context_rate,
    coalesce(m.maintenance_event_count, 0) AS maintenance_event_count,
    coalesce(m.maintenance_minutes, 0.0) AS maintenance_minutes,
    m.maintenance_deferred_rate,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM downtime d
FULL OUTER JOIN maintenance m USING (date_key, line_key)
LEFT JOIN analytics.dim_line dl ON dl.line_key = coalesce(d.line_key, m.line_key);

CREATE TABLE analytics.mart_asset_condition AS
WITH process_condition AS (
    SELECT
        fp.date_key,
        fp.line_key,
        min(fp.line_id) AS line_id,
        avg(p.tool_wear_index) AS mean_tool_wear_index,
        max(p.tool_wear_index) AS maximum_tool_wear_index,
        avg(p.sensor_degradation_index) AS mean_sensor_degradation_index,
        avg(p.hours_since_maintenance) AS mean_hours_since_maintenance,
        avg(p.maintenance_deferred::INTEGER) AS maintenance_deferred_rate
    FROM curated.process_parameters p
    JOIN analytics.fact_production fp USING (tube_id)
    GROUP BY fp.date_key, fp.line_key
)
SELECT
    p.*,
    coalesce(dm.unplanned_downtime_minutes, 0.0) AS unplanned_downtime_minutes,
    coalesce(dm.maintenance_event_count, 0) AS maintenance_event_count,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM process_condition p
LEFT JOIN analytics.mart_downtime_maintenance dm USING (date_key, line_key);

CREATE TABLE analytics.mart_loss_pareto AS
WITH losses AS (
    SELECT
        date_key,
        line_key,
        shift_key,
        min(line_id) AS line_id,
        min(shift_id) AS shift_id,
        'REWORK' AS loss_type,
        sum((disposition = 'REWORK')::INTEGER) AS event_count,
        sum(rework_mass_t) AS loss_tonnes_equivalent
    FROM analytics.fact_production
    GROUP BY date_key, line_key, shift_key
    UNION ALL
    SELECT
        date_key,
        line_key,
        shift_key,
        min(line_id),
        min(shift_id),
        'SCRAP',
        sum((disposition = 'SCRAP')::INTEGER),
        sum(scrap_mass_t)
    FROM analytics.fact_production
    GROUP BY date_key, line_key, shift_key
    UNION ALL
    SELECT
        date_key,
        line_key,
        shift_key,
        min(line_id),
        min(shift_id),
        'UNPLANNED_DOWNTIME',
        count(*),
        sum(production_impact_t)
    FROM analytics.fact_downtime
    GROUP BY date_key, line_key, shift_key
),
positive_losses AS (
    SELECT * FROM losses WHERE loss_tonnes_equivalent > 0
)
SELECT
    *,
    loss_tonnes_equivalent
        / NULLIF(sum(loss_tonnes_equivalent) OVER (PARTITION BY date_key, line_key, shift_key), 0)
        AS loss_share,
    sum(loss_tonnes_equivalent) OVER (
        PARTITION BY date_key, line_key, shift_key
        ORDER BY loss_tonnes_equivalent DESC, loss_type
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / NULLIF(
        sum(loss_tonnes_equivalent) OVER (PARTITION BY date_key, line_key, shift_key),
        0
    ) AS cumulative_loss_share,
    '{{SIMULATION_RUN_ID}}' AS simulation_run_id
FROM positive_losses;
