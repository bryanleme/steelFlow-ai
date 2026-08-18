from __future__ import annotations

import pandas as pd
import pytest

from steelflow.models.baselines import ConditionedMedianRegressor, ConditionedRateClassifier


def test_conditioned_median_uses_global_fallback_for_unseen_context() -> None:
    X = pd.DataFrame({"line_id": ["L1", "L1", "L2"]})
    model = ConditionedMedianRegressor(("line_id",)).fit(X, pd.Series([1.0, 3.0, 10.0]))

    predictions = model.predict(pd.DataFrame({"line_id": ["L1", "NEW"]}))

    assert predictions[0] == pytest.approx(2.0)
    assert predictions[1] == pytest.approx(3.0)


def test_conditioned_rate_is_smoothed_and_bounded() -> None:
    X = pd.DataFrame({"line_id": ["L1", "L1", "L2", "L2"]})
    model = ConditionedRateClassifier(("line_id",), smoothing=2.0).fit(
        X, pd.Series([1, 1, 0, 0])
    )

    probabilities = model.predict_proba(pd.DataFrame({"line_id": ["L1", "L2", "NEW"]}))

    assert probabilities.shape == (3, 2)
    assert all(0.0 <= value <= 1.0 for value in probabilities[:, 1])
    assert probabilities[0, 1] > probabilities[1, 1]
    assert probabilities[2, 1] == pytest.approx(0.5)
