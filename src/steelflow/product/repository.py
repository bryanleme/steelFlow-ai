"""Small cached-query-friendly read model for the Streamlit pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from steelflow.product.artifacts import ProductArtifacts


class ProductRepository:
    def __init__(self, artifacts: ProductArtifacts) -> None:
        self.artifacts = artifacts

    def _query(self, query: str, parameters: list[Any] | None = None) -> pd.DataFrame:
        connection = duckdb.connect(str(self.artifacts.analytics_database), read_only=True)
        try:
            return connection.execute(query, parameters or []).fetchdf()
        finally:
            connection.close()

    def executive_trend(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                full_date,
                line_id,
                shift_id,
                tube_count,
                total_tonnes,
                good_tonnes,
                productive_hours,
                fpy,
                energy_kwh,
                unplanned_downtime_minutes,
                tbh,
                energy_per_good_tonne_kwh_t,
                oee
            FROM analytics.diagnostic_daily_trend
            ORDER BY full_date, line_id, shift_id
            """
        )

    def line_summary(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                line_id,
                sum(tube_count) AS tube_count,
                sum(good_tonnes) / nullif(sum(productive_hours), 0) AS tbh,
                sum(good_tonnes) / nullif(sum(total_tonnes), 0) AS quality,
                sum(energy_kwh) / nullif(sum(good_tonnes), 0) AS energy_per_good_tonne_kwh_t,
                sum(unplanned_downtime_minutes) AS unplanned_downtime_minutes,
                sum(oee * tube_count) / nullif(sum(tube_count), 0) AS oee
            FROM analytics.mart_line_shift_performance
            GROUP BY line_id
            ORDER BY line_id
            """
        )

    def loss_pareto(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                loss_type,
                sum(event_count) AS event_count,
                sum(loss_tonnes_equivalent) AS loss_tonnes_equivalent
            FROM analytics.mart_loss_pareto
            GROUP BY loss_type
            ORDER BY loss_tonnes_equivalent DESC
            """
        )

    def mix_adjustment(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                d.full_date,
                m.line_id,
                m.actual_tbh,
                m.mix_expected_tbh,
                m.mix_adjusted_tbh_gap,
                m.order_count
            FROM analytics.diagnostic_mix_adjustment m
            JOIN analytics.dim_date d USING (date_key)
            ORDER BY d.full_date, m.line_id
            """
        )

    def quality_alerts(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                d.full_date,
                q.line_id,
                q.product_code,
                q.grade_family,
                q.characteristic,
                q.mean_value,
                q.conformance_rate,
                q.control_signal
            FROM analytics.diagnostic_spc_quality q
            JOIN analytics.dim_date d USING (date_key)
            WHERE q.limits_reliable AND q.control_signal
            ORDER BY d.full_date DESC
            LIMIT 100
            """
        )

    def tbh_control_signals(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                d.full_date,
                s.line_id,
                s.shift_id,
                s.tbh,
                s.lower_control_tbh,
                s.upper_control_tbh,
                s.control_signal
            FROM analytics.diagnostic_spc_tbh s
            JOIN analytics.dim_date d USING (date_key)
            WHERE s.limits_reliable
            ORDER BY d.full_date, s.line_id, s.shift_id
            """
        )

    def asset_condition(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT
                d.full_date,
                a.line_id,
                a.mean_tool_wear_index,
                a.mean_sensor_degradation_index,
                a.mean_hours_since_maintenance,
                a.maintenance_deferred_rate,
                a.unplanned_downtime_minutes
            FROM analytics.mart_asset_condition a
            JOIN analytics.dim_date d USING (date_key)
            ORDER BY d.full_date, a.line_id
            """
        )

    def process_interactions(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT *
            FROM analytics.diagnostic_process_interactions
            ORDER BY product_code, grade_family, line_id,
                     roll_speed_band, thermal_uniformity_band
            """
        )

    def segment_associations(self) -> pd.DataFrame:
        return self._query(
            """
            SELECT *
            FROM analytics.diagnostic_segment_associations
            ORDER BY product_code, grade_family, line_id
            """
        )

    def final_metrics(self) -> pd.DataFrame:
        return pd.read_parquet(self.artifacts.evaluation_root / "metrics/final_test.parquet")

    def segment_metrics(self) -> pd.DataFrame:
        return pd.read_parquet(self.artifacts.evaluation_root / "metrics/segments.parquet")

    def global_shap(self, task: str) -> pd.DataFrame:
        return pd.read_parquet(
            self.artifacts.evaluation_root / "explanations" / task / "global.parquet"
        )

    def segment_shap(self, task: str) -> pd.DataFrame:
        return pd.read_parquet(
            self.artifacts.evaluation_root / "explanations" / task / "segments.parquet"
        )

    def local_explanations(self, task: str) -> pd.DataFrame:
        return pd.read_parquet(
            self.artifacts.evaluation_root / "explanations" / task / "scenarios.parquet"
        )

    def evaluation_manifest(self) -> dict[str, Any]:
        return json.loads(
            (self.artifacts.evaluation_root / "evaluation_manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def optimization_manifest(self) -> dict[str, Any]:
        return json.loads(
            (self.artifacts.optimization_root / "optimization_manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def scenarios(self) -> list[dict[str, Any]]:
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.artifacts.optimization_root / "scenarios").glob("*.json"))
        ]

    def model_card(self, task: str) -> str:
        path = self.artifacts.model_root / "models" / task / "MODEL_CARD.md"
        return path.read_text(encoding="utf-8")


def project_root_from_file(path: Path) -> Path:
    for parent in (path.resolve(), *path.resolve().parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("não foi possível localizar a raiz do projeto")
