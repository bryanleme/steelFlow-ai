-- Materialized curated layer. Raw Parquet has already passed Phase 2 contracts;
-- this layer freezes types and provides a stable database boundary.

CREATE TABLE curated.dim_products AS SELECT * FROM raw.dim_products;
CREATE TABLE curated.dim_lines AS SELECT * FROM raw.dim_lines;
CREATE TABLE curated.dim_shifts AS SELECT * FROM raw.dim_shifts;
CREATE TABLE curated.dim_assets AS SELECT * FROM raw.dim_assets;
CREATE TABLE curated.feature_availability AS SELECT * FROM raw.feature_availability;
CREATE TABLE curated.production_orders AS SELECT * FROM raw.production_orders;
CREATE TABLE curated.billet_batches AS SELECT * FROM raw.billet_batches;
CREATE TABLE curated.tubes AS SELECT * FROM raw.tubes;
CREATE TABLE curated.process_parameters AS SELECT * FROM raw.process_parameters;
CREATE TABLE curated.stage_events AS SELECT * FROM raw.stage_events;
CREATE TABLE curated.sensor_windows AS SELECT * FROM raw.sensor_windows;
CREATE TABLE curated.quality_results AS SELECT * FROM raw.quality_results;
CREATE TABLE curated.energy_events AS SELECT * FROM raw.energy_events;
CREATE TABLE curated.downtime_events AS SELECT * FROM raw.downtime_events;
CREATE TABLE curated.maintenance_events AS SELECT * FROM raw.maintenance_events;

CREATE UNIQUE INDEX idx_curated_products_pk ON curated.dim_products(product_code);
CREATE UNIQUE INDEX idx_curated_lines_pk ON curated.dim_lines(line_id);
CREATE UNIQUE INDEX idx_curated_shifts_pk ON curated.dim_shifts(shift_id);
CREATE UNIQUE INDEX idx_curated_assets_pk ON curated.dim_assets(asset_id);
CREATE UNIQUE INDEX idx_curated_orders_pk ON curated.production_orders(order_id);
CREATE UNIQUE INDEX idx_curated_billets_pk ON curated.billet_batches(billet_batch_id);
CREATE UNIQUE INDEX idx_curated_tubes_pk ON curated.tubes(tube_id);
CREATE UNIQUE INDEX idx_curated_process_pk ON curated.process_parameters(tube_id);
CREATE UNIQUE INDEX idx_curated_stages_pk ON curated.stage_events(stage_event_id);
CREATE UNIQUE INDEX idx_curated_sensors_pk ON curated.sensor_windows(sensor_window_id);
CREATE UNIQUE INDEX idx_curated_quality_pk ON curated.quality_results(quality_result_id);
CREATE UNIQUE INDEX idx_curated_energy_pk ON curated.energy_events(energy_event_id);
CREATE UNIQUE INDEX idx_curated_downtime_pk ON curated.downtime_events(downtime_event_id);
CREATE UNIQUE INDEX idx_curated_maintenance_pk ON curated.maintenance_events(maintenance_event_id);

CREATE TABLE metadata.table_contracts (
    table_schema VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    grain VARCHAR NOT NULL,
    primary_key VARCHAR NOT NULL,
    partition_rule VARCHAR NOT NULL,
    synthetic_only BOOLEAN NOT NULL,
    PRIMARY KEY (table_schema, table_name)
);

INSERT INTO metadata.table_contracts VALUES
    ('curated', 'dim_products', 'one row per synthetic product combination', 'product_code', 'none', TRUE),
    ('curated', 'dim_lines', 'one row per production line', 'line_id', 'none', TRUE),
    ('curated', 'dim_shifts', 'one row per shift', 'shift_id', 'none', TRUE),
    ('curated', 'dim_assets', 'one row per line and asset type', 'asset_id', 'none', TRUE),
    ('curated', 'production_orders', 'one row per order', 'order_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'billet_batches', 'one row per billet batch and order', 'billet_batch_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'tubes', 'one row per traceable tube', 'tube_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'process_parameters', 'one row per tube process recipe', 'tube_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'stage_events', 'one row per tube and stage', 'stage_event_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'sensor_windows', 'one row per tube, sensor and window', 'sensor_window_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'quality_results', 'one row per tube and characteristic', 'quality_result_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'energy_events', 'one row per tube and energy stage', 'energy_event_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'downtime_events', 'one row per unplanned downtime event', 'downtime_event_id', '{{PARTITION_FREQUENCY}}', TRUE),
    ('curated', 'maintenance_events', 'one row per maintenance intervention', 'maintenance_event_id', '{{PARTITION_FREQUENCY}}', TRUE);
