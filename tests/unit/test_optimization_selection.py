from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from steelflow.optimization.problem import select_alternatives


def test_pareto_selector_returns_three_distinct_named_alternatives() -> None:
    controls = ("control_a", "control_b")
    pareto = pd.DataFrame(
        {
            "control_a": [0.1, 0.2, 0.3, 0.4, 0.5],
            "control_b": [0.5, 0.4, 0.3, 0.2, 0.1],
            "objective_negative_tbh_proxy": [-20.0, -21.0, -22.0, -23.0, -24.0],
            "objective_quality_risk": [0.05, 0.06, 0.07, 0.08, 0.09],
            "objective_energy": [540.0, 530.0, 520.0, 510.0, 500.0],
            "objective_downtime_risk": 0.1,
            "objective_expected_downtime": 1.8,
            "objective_intervention_magnitude": [0.1, 0.2, 0.3, 0.4, 0.5],
            "estimated_tbh_proxy": [20.0, 21.0, 22.0, 23.0, 24.0],
            "quality_failure_probability": [0.05, 0.06, 0.07, 0.08, 0.09],
            "energy_p50": [540.0, 530.0, 520.0, 510.0, 500.0],
            "throughput_interval_width": [3.0, 3.1, 3.2, 3.3, 3.4],
            "energy_interval_width": [30.0, 31.0, 32.0, 33.0, 34.0],
            "distance_ratio": [0.2, 0.3, 0.4, 0.5, 0.6],
        }
    )
    envelope = SimpleNamespace(
        controllables=controls,
        current=np.array([0.0, 0.0]),
        lower_bounds=np.array([0.0, 0.0]),
        upper_bounds=np.array([1.0, 1.0]),
    )

    selected = select_alternatives(pareto, envelope=envelope)

    assert set(selected) == {"conservative", "balanced", "productivity"}
    assert len({tuple(row[list(controls)]) for row in selected.values()}) == 3
