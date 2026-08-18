from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from steelflow.optimization.contracts import load_optimization_config
from steelflow.optimization.envelope import build_historical_envelope

ROOT = Path(__file__).resolve().parents[2]


def _supported_training_frame() -> pd.DataFrame:
    config = load_optimization_config(ROOT)
    rng = np.random.default_rng(20260818)
    rows = 300
    frame = pd.DataFrame(
        {
            "product_code": "PROD_01",
            "grade_family": "GRADE_A",
            "line_id": "LINE_01",
            "shift_id": "SHIFT_01",
            "tool_wear_index": 0.4,
        },
        index=np.arange(rows),
    )
    for name, specification in config.controllables.items():
        center = (specification.internal_min + specification.internal_max) / 2
        width = (specification.internal_max - specification.internal_min) * 0.04
        frame[name] = rng.normal(center, width, rows)
    return frame


def test_conditional_envelope_accepts_supported_context_and_refuses_ood() -> None:
    config = load_optimization_config(ROOT)
    training = _supported_training_frame()
    controls = list(config.controllables)
    center = training[controls].median().to_numpy(float)
    scale = training[controls].std(ddof=0).to_numpy(float)
    row_index = int(
        np.square((training[controls].to_numpy(float) - center) / scale)
        .mean(axis=1)
        .argmin()
    )
    envelope = build_historical_envelope(training, training.iloc[row_index], config)

    current = envelope.assess(envelope.current).iloc[0]
    assert bool(current["in_distribution"])
    assert envelope.support_rows == len(training)
    assert np.all(envelope.lower_bounds <= envelope.current)
    assert np.all(envelope.current <= envelope.upper_bounds)

    ood = envelope.current.copy()
    ood[0] = envelope.upper_bounds[0] + 1.0
    refusal = envelope.assess(ood).iloc[0]
    assert not bool(refusal["within_conditional_bounds"])
    assert not bool(refusal["in_distribution"])
