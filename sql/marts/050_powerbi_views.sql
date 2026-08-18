-- Compact export contract for Power BI.

CREATE VIEW analytics.pbi_dim_date AS SELECT * FROM analytics.dim_date;
CREATE VIEW analytics.pbi_dim_product AS SELECT * FROM analytics.dim_product;
CREATE VIEW analytics.pbi_dim_line AS SELECT * FROM analytics.dim_line;
CREATE VIEW analytics.pbi_dim_shift AS SELECT * FROM analytics.dim_shift;
CREATE VIEW analytics.pbi_dim_asset AS SELECT * FROM analytics.dim_asset;
CREATE VIEW analytics.pbi_fact_line_shift AS SELECT * FROM analytics.mart_line_shift_performance;
CREATE VIEW analytics.pbi_fact_order AS SELECT * FROM analytics.mart_order_performance;
CREATE VIEW analytics.pbi_fact_quality AS SELECT * FROM analytics.mart_quality_summary;
CREATE VIEW analytics.pbi_fact_energy AS SELECT * FROM analytics.mart_energy_summary;
CREATE VIEW analytics.pbi_fact_downtime AS SELECT * FROM analytics.fact_downtime;
CREATE VIEW analytics.pbi_fact_maintenance AS SELECT * FROM analytics.fact_maintenance;
CREATE VIEW analytics.pbi_fact_losses AS SELECT * FROM analytics.mart_loss_pareto;
CREATE VIEW analytics.pbi_fact_asset_condition AS SELECT * FROM analytics.mart_asset_condition;
