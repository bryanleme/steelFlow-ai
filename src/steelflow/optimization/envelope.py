"""Conditional historical envelopes and explicit OOD refusal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from steelflow.optimization.contracts import OptimizationConfig


class EnvelopeError(RuntimeError):
    """Raised when a context cannot support a safe scenario envelope."""


@dataclass(frozen=True)
class VariableBound:
    name: str
    unit: str
    historical_lower: float
    historical_upper: float
    decision_lower: float
    decision_upper: float
    current_value: float
    max_absolute_change: float


@dataclass
class HistoricalEnvelope:
    controllables: tuple[str, ...]
    conditioning_columns: tuple[str, ...]
    conditioning_values: dict[str, str]
    support_rows: int
    bounds: tuple[VariableBound, ...]
    distance_threshold: float
    _scale_lower: np.ndarray
    _scale_width: np.ndarray
    _support_controls: np.ndarray
    _neighbor_model: NearestNeighbors

    @property
    def lower_bounds(self) -> np.ndarray:
        return np.asarray([bound.decision_lower for bound in self.bounds], dtype=float)

    @property
    def upper_bounds(self) -> np.ndarray:
        return np.asarray([bound.decision_upper for bound in self.bounds], dtype=float)

    @property
    def current(self) -> np.ndarray:
        return np.asarray([bound.current_value for bound in self.bounds], dtype=float)

    def _normalize(self, values: np.ndarray) -> np.ndarray:
        return (values - self._scale_lower) / self._scale_width

    def assess(self, values: np.ndarray) -> pd.DataFrame:
        matrix = np.atleast_2d(np.asarray(values, dtype=float))
        if matrix.shape[1] != len(self.controllables):
            raise EnvelopeError("candidate dimension does not match controllable contract")
        lower = self.lower_bounds
        upper = self.upper_bounds
        span = np.maximum(upper - lower, 1e-12)
        below = np.maximum(lower - matrix, 0.0) / span
        above = np.maximum(matrix - upper, 0.0) / span
        range_violation = np.max(np.maximum(below, above), axis=1)
        distances = self._neighbor_model.kneighbors(
            self._normalize(matrix),
            return_distance=True,
        )[0][:, -1]
        distance_ratio = distances / max(self.distance_threshold, 1e-12)
        return pd.DataFrame(
            {
                "within_conditional_bounds": range_violation <= 1e-12,
                "range_violation": range_violation,
                "historical_distance": distances,
                "distance_threshold": self.distance_threshold,
                "distance_ratio": distance_ratio,
                "in_distribution": (range_violation <= 1e-12) & (distance_ratio <= 1.0),
            }
        )

    def initial_population(self, size: int, *, random_seed: int) -> np.ndarray:
        rng = np.random.default_rng(random_seed)
        current = self.current
        support = self._support_controls
        normalized_distance = np.linalg.norm(
            self._normalize(support) - self._normalize(current.reshape(1, -1)),
            axis=1,
        )
        nearest = support[np.argsort(normalized_distance, kind="stable")[: max(size * 4, size)]]
        candidates = [current.copy()]
        while len(candidates) < size:
            neighbor = nearest[int(rng.integers(0, len(nearest)))]
            alpha = float(rng.uniform(0.15, 0.95))
            candidate = current + alpha * (neighbor - current)
            jitter = rng.normal(0.0, 0.01, len(current)) * (
                self.upper_bounds - self.lower_bounds
            )
            candidates.append(np.clip(candidate + jitter, self.lower_bounds, self.upper_bounds))
        return np.asarray(candidates, dtype=float)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conditioning_columns": list(self.conditioning_columns),
            "conditioning_values": self.conditioning_values,
            "support_rows": self.support_rows,
            "nearest_neighbors": self._neighbor_model.n_neighbors,
            "distance_threshold": self.distance_threshold,
            "bounds": [bound.__dict__ for bound in self.bounds],
        }


def wear_band(values: pd.Series, edges: tuple[float, ...]) -> pd.Series:
    labels = [f"wear_{index}" for index in range(len(edges) - 1)]
    return pd.cut(
        values.astype(float),
        bins=list(edges),
        labels=labels,
        include_lowest=True,
        right=False,
    ).astype(str)


def _conditioned_support(
    training: pd.DataFrame,
    current: pd.Series,
    config: OptimizationConfig,
) -> tuple[pd.DataFrame, tuple[str, ...], dict[str, str]]:
    enriched = training.copy()
    enriched["wear_band"] = wear_band(
        enriched["tool_wear_index"], config.envelope.wear_band_edges
    )
    current_band = str(
        wear_band(
            pd.Series([current["tool_wear_index"]]),
            config.envelope.wear_band_edges,
        ).iloc[0]
    )
    for columns in config.conditioning_hierarchy:
        values = {
            column: current_band if column == "wear_band" else str(current[column])
            for column in columns
        }
        mask = pd.Series(True, index=enriched.index)
        for column, value in values.items():
            mask &= enriched[column].astype(str) == value
        support = enriched.loc[mask].copy()
        if len(support) >= config.envelope.minimum_support:
            return support, columns, values
    raise EnvelopeError("context has insufficient support in every conditioning level")


def build_historical_envelope(
    training: pd.DataFrame,
    current: pd.Series,
    config: OptimizationConfig,
) -> HistoricalEnvelope:
    controllables = tuple(config.controllables)
    missing = set(controllables) - set(training.columns)
    if missing:
        raise EnvelopeError(f"training frame is missing controllables: {sorted(missing)}")
    support, conditioning_columns, conditioning_values = _conditioned_support(
        training, current, config
    )
    support_controls_frame = support.loc[:, controllables].dropna().astype(float)
    if len(support_controls_frame) < config.envelope.minimum_support:
        raise EnvelopeError("conditional support is incomplete after dropping missing controls")
    historical_lower = support_controls_frame.quantile(config.envelope.lower_quantile)
    historical_upper = support_controls_frame.quantile(config.envelope.upper_quantile)

    bounds: list[VariableBound] = []
    for name in controllables:
        specification = config.controllables[name]
        lower = max(float(historical_lower[name]), specification.internal_min)
        upper = min(float(historical_upper[name]), specification.internal_max)
        current_value = float(current[name])
        if current_value < lower or current_value > upper:
            raise EnvelopeError(
                f"current context is OOD for {name}: {current_value} not in [{lower}, {upper}]"
            )
        historical_span = upper - lower
        max_change = historical_span * specification.max_change_fraction
        decision_lower = max(lower, current_value - max_change)
        decision_upper = min(upper, current_value + max_change)
        if decision_upper <= decision_lower:
            raise EnvelopeError(f"collapsed decision range for {name}")
        bounds.append(
            VariableBound(
                name=name,
                unit=specification.unit,
                historical_lower=lower,
                historical_upper=upper,
                decision_lower=decision_lower,
                decision_upper=decision_upper,
                current_value=current_value,
                max_absolute_change=max_change,
            )
        )

    scale_lower = historical_lower.loc[list(controllables)].to_numpy(dtype=float)
    scale_upper = historical_upper.loc[list(controllables)].to_numpy(dtype=float)
    scale_width = np.maximum(scale_upper - scale_lower, 1e-12)
    support_controls = support_controls_frame.to_numpy(dtype=float)
    normalized = (support_controls - scale_lower) / scale_width
    neighbors = config.envelope.nearest_neighbors
    threshold_model = NearestNeighbors(n_neighbors=neighbors + 1).fit(normalized)
    training_distances = threshold_model.kneighbors(normalized, return_distance=True)[0][:, -1]
    distance_threshold = float(
        np.quantile(training_distances, config.envelope.distance_quantile)
        * config.envelope.distance_multiplier
    )
    neighbor_model = NearestNeighbors(n_neighbors=neighbors).fit(normalized)
    envelope = HistoricalEnvelope(
        controllables=controllables,
        conditioning_columns=conditioning_columns,
        conditioning_values=conditioning_values,
        support_rows=len(support_controls_frame),
        bounds=tuple(bounds),
        distance_threshold=distance_threshold,
        _scale_lower=scale_lower,
        _scale_width=scale_width,
        _support_controls=support_controls,
        _neighbor_model=neighbor_model,
    )
    assessment = envelope.assess(envelope.current)
    if not bool(assessment.iloc[0]["in_distribution"]):
        raise EnvelopeError("current context fails the historical-distance OOD guard")
    return envelope
