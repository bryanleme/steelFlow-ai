-- Star-schema dimensions and atomic facts.

CREATE TABLE analytics.dim_date AS
SELECT
    CAST(strftime(calendar_date, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(calendar_date AS DATE) AS full_date,
    year(calendar_date) AS year_number,
    month(calendar_date) AS month_number,
    strftime(calendar_date, '%Y-%m') AS year_month,
    week(calendar_date) AS iso_week,
    dayofweek(calendar_date) AS day_of_week,
    dayname(calendar_date) AS day_name,
    CASE WHEN dayofweek(calendar_date) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
FROM range(
    DATE '{{START_DATE}}',
    DATE '{{END_DATE}}' + INTERVAL 1 DAY,
    INTERVAL 1 DAY
) AS dates(calendar_date);

CREATE TABLE analytics.dim_product AS
SELECT
    CAST(row_number() OVER (ORDER BY product_code) AS INTEGER) AS product_key,
    product_code,
    product_family,
    outer_diameter_mm,
    wall_thickness_mm,
    nominal_length_m,
    nominal_mass_kg,
    internal_simulated_spec
FROM curated.dim_products;

CREATE TABLE analytics.dim_line AS
SELECT
    CAST(row_number() OVER (ORDER BY line_id) AS INTEGER) AS line_key,
    line_id,
    minimum_outer_diameter_mm,
    nominal_roll_speed_rpm,
    energy_efficiency_index,
    internal_simulated_limits
FROM curated.dim_lines;

CREATE TABLE analytics.dim_shift AS
SELECT
    CAST(row_number() OVER (ORDER BY shift_id) AS INTEGER) AS shift_key,
    shift_id,
    start_hour,
    duration_hours
FROM curated.dim_shifts;

CREATE TABLE analytics.dim_asset AS
SELECT
    CAST(row_number() OVER (ORDER BY asset_id) AS INTEGER) AS asset_key,
    asset_id,
    dl.line_key,
    a.line_id,
    a.asset_type,
    a.criticality
FROM curated.dim_assets a
JOIN analytics.dim_line dl USING (line_id);

CREATE TABLE analytics.fact_production AS
SELECT
    t.tube_id,
    t.order_id,
    CAST(strftime(t.actual_start_ts, '%Y%m%d') AS INTEGER) AS date_key,
    dp.product_key,
    dl.line_key,
    ds.shift_key,
    t.product_code,
    t.grade_family,
    t.line_id,
    t.shift_id,
    t.actual_start_ts,
    t.actual_end_ts,
    t.tube_mass_kg / 1000.0 AS total_mass_t,
    t.good_mass_t,
    t.productive_hours,
    t.actual_tph,
    t.approved_first_pass,
    t.disposition,
    CASE WHEN t.disposition = 'REWORK' THEN t.tube_mass_kg / 1000.0 ELSE 0.0 END AS rework_mass_t,
    CASE WHEN t.disposition = 'SCRAP' THEN t.tube_mass_kg / 1000.0 ELSE 0.0 END AS scrap_mass_t,
    t.simulation_run_id
FROM curated.tubes t
JOIN analytics.dim_product dp USING (product_code)
JOIN analytics.dim_line dl USING (line_id)
JOIN analytics.dim_shift ds USING (shift_id);

CREATE TABLE analytics.fact_quality AS
SELECT
    q.quality_result_id,
    q.tube_id,
    q.order_id,
    CAST(strftime(q.inspection_ts, '%Y%m%d') AS INTEGER) AS date_key,
    fp.product_key,
    fp.line_key,
    fp.shift_key,
    fp.product_code,
    fp.grade_family,
    fp.line_id,
    fp.shift_id,
    q.characteristic,
    q.measured_value,
    q.internal_simulated_lower_limit,
    q.internal_simulated_upper_limit,
    q.unit,
    q.passed,
    q.inspection_ts,
    q.simulation_run_id
FROM curated.quality_results q
JOIN analytics.fact_production fp USING (tube_id);

CREATE TABLE analytics.fact_energy AS
SELECT
    e.energy_event_id,
    e.tube_id,
    e.order_id,
    CAST(strftime(e.event_ts, '%Y%m%d') AS INTEGER) AS date_key,
    fp.product_key,
    fp.line_key,
    fp.shift_key,
    fp.product_code,
    fp.grade_family,
    fp.line_id,
    fp.shift_id,
    e.stage_name,
    e.event_ts,
    e.energy_kwh,
    e.good_mass_t,
    e.energy_per_good_tonne_kwh_t,
    e.simulation_run_id
FROM curated.energy_events e
JOIN analytics.fact_production fp USING (tube_id);

CREATE TABLE analytics.fact_downtime AS
SELECT
    d.downtime_event_id,
    CAST(strftime(d.event_start_ts, '%Y%m%d') AS INTEGER) AS date_key,
    dl.line_key,
    ds.shift_key,
    da.asset_key,
    d.line_id,
    ds.shift_id,
    d.asset_id,
    d.reason_code,
    d.event_start_ts,
    d.event_end_ts,
    d.duration_minutes,
    d.hours_since_maintenance,
    d.sensor_degradation_index,
    d.maintenance_deferred,
    d.production_impact_t,
    d.unplanned,
    d.simulation_run_id
FROM curated.downtime_events d
JOIN analytics.dim_line dl USING (line_id)
JOIN analytics.dim_asset da USING (asset_id)
JOIN analytics.dim_shift ds
    ON ds.start_hour = 8 * floor(hour(d.event_start_ts) / 8);

CREATE TABLE analytics.fact_maintenance AS
SELECT
    m.maintenance_event_id,
    CAST(strftime(m.actual_start_ts, '%Y%m%d') AS INTEGER) AS date_key,
    dl.line_key,
    da.asset_key,
    m.line_id,
    m.asset_id,
    m.maintenance_type,
    m.scheduled_start_ts,
    m.actual_start_ts,
    m.actual_end_ts,
    m.duration_minutes,
    m.was_deferred,
    m.work_order_status,
    m.simulation_run_id
FROM curated.maintenance_events m
JOIN analytics.dim_line dl USING (line_id)
JOIN analytics.dim_asset da USING (asset_id);

CREATE UNIQUE INDEX idx_dim_date_pk ON analytics.dim_date(date_key);
CREATE UNIQUE INDEX idx_dim_product_pk ON analytics.dim_product(product_key);
CREATE UNIQUE INDEX idx_dim_line_pk ON analytics.dim_line(line_key);
CREATE UNIQUE INDEX idx_dim_shift_pk ON analytics.dim_shift(shift_key);
CREATE UNIQUE INDEX idx_dim_asset_pk ON analytics.dim_asset(asset_key);
CREATE UNIQUE INDEX idx_fact_production_pk ON analytics.fact_production(tube_id);
CREATE UNIQUE INDEX idx_fact_quality_pk ON analytics.fact_quality(quality_result_id);
CREATE UNIQUE INDEX idx_fact_energy_pk ON analytics.fact_energy(energy_event_id);
CREATE UNIQUE INDEX idx_fact_downtime_pk ON analytics.fact_downtime(downtime_event_id);
CREATE UNIQUE INDEX idx_fact_maintenance_pk ON analytics.fact_maintenance(maintenance_event_id);
