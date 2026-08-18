"""NSGA-II problem definition and deterministic Pareto alternative selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.optimize import minimize

from steelflow.optimization.contracts import OptimizationConfig
from steelflow.optimization.envelope import HistoricalEnvelope
from steelflow.optimization.predictor import AssetEstimate, ScenarioPredictor


class SteelFlowProblem(Problem):
    def __init__(
        self,
        *,
        predictor: ScenarioPredictor,
        current: pd.Series,
        envelope: HistoricalEnvelope,
        asset: AssetEstimate,
    ) -> None:
        super().__init__(
            n_var=len(envelope.controllables),
            n_obj=6,
            n_ieq_constr=9,
            xl=envelope.lower_bounds,
            xu=envelope.upper_bounds,
        )
        self.predictor = predictor
        self.current = current
        self.envelope = envelope
        self.asset = asset

    def _evaluate(
        self,
        x: np.ndarray,
        out: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        del args, kwargs
        evaluation = self.predictor.evaluate(
            x,
            current=self.current,
            envelope=self.envelope,
            asset=self.asset,
        )
        intervention = np.mean(
            np.abs(x - self.envelope.current)
            / np.maximum(self.envelope.upper_bounds - self.envelope.lower_bounds, 1e-12),
            axis=1,
        )
        out["F"] = np.column_stack(
            [self.predictor.objectives(evaluation), intervention]
        )
        out["G"] = self.predictor.constraints(evaluation)


@dataclass(frozen=True)
class OptimizationOutcome:
    pareto: pd.DataFrame
    evaluations: int
    generations: int


def optimize_context(
    *,
    predictor: ScenarioPredictor,
    current: pd.Series,
    envelope: HistoricalEnvelope,
    asset: AssetEstimate,
    config: OptimizationConfig,
    seed_offset: int,
) -> OptimizationOutcome:
    seed = config.random_seed + seed_offset
    problem = SteelFlowProblem(
        predictor=predictor,
        current=current,
        envelope=envelope,
        asset=asset,
    )
    algorithm = NSGA2(
        pop_size=config.nsga2.population_size,
        n_offsprings=config.nsga2.offspring,
        sampling=envelope.initial_population(
            config.nsga2.population_size,
            random_seed=seed,
        ),
        eliminate_duplicates=True,
    )
    result = minimize(
        problem,
        algorithm,
        ("n_gen", config.nsga2.generations),
        seed=seed,
        verbose=False,
        save_history=False,
        return_least_infeasible=False,
    )
    if result.X is None:
        raise RuntimeError("NSGA-II found no feasible in-distribution scenario")
    values = np.atleast_2d(np.asarray(result.X, dtype=float))
    evaluation = predictor.evaluate(
        values,
        current=current,
        envelope=envelope,
        asset=asset,
    )
    pareto = pd.DataFrame(values, columns=envelope.controllables)
    pareto = pd.concat([pareto.reset_index(drop=True), evaluation.reset_index(drop=True)], axis=1)
    objectives = predictor.objectives(evaluation)
    intervention = np.mean(
        np.abs(values - envelope.current)
        / np.maximum(envelope.upper_bounds - envelope.lower_bounds, 1e-12),
        axis=1,
    )
    for index, name in enumerate(
        (
            "objective_negative_tbh_proxy",
            "objective_quality_risk",
            "objective_energy",
            "objective_downtime_risk",
            "objective_expected_downtime",
        )
    ):
        pareto[name] = objectives[:, index]
    pareto["objective_intervention_magnitude"] = intervention
    pareto = pareto.loc[pareto["hard_constraints_pass"]].drop_duplicates(
        subset=list(envelope.controllables)
    )
    if len(pareto) < 3:
        raise RuntimeError("NSGA-II returned fewer than three distinct feasible alternatives")
    return OptimizationOutcome(
        pareto=pareto.reset_index(drop=True),
        evaluations=int(result.algorithm.evaluator.n_eval),
        generations=config.nsga2.generations,
    )


def _minmax(frame: pd.DataFrame) -> pd.DataFrame:
    lower = frame.min(axis=0)
    span = (frame.max(axis=0) - lower).replace(0.0, 1.0)
    return (frame - lower) / span


def select_alternatives(
    pareto: pd.DataFrame,
    *,
    envelope: HistoricalEnvelope,
) -> dict[str, pd.Series]:
    """Select conservative, balanced and productivity alternatives without duplicates."""

    objectives = pareto[
        [
            "objective_negative_tbh_proxy",
            "objective_quality_risk",
            "objective_energy",
            "objective_downtime_risk",
            "objective_expected_downtime",
            "objective_intervention_magnitude",
        ]
    ]
    normalized = _minmax(objectives)
    change = pareto["objective_intervention_magnitude"]
    uncertainty = _minmax(
        pareto[["throughput_interval_width", "energy_interval_width"]]
    ).mean(axis=1)
    distance = pareto["distance_ratio"].clip(lower=0.0)
    scores = {
        "conservative": (
            normalized["objective_quality_risk"]
            + normalized["objective_energy"]
            + normalized["objective_downtime_risk"]
            + normalized["objective_expected_downtime"]
            + uncertainty
            + distance
            + change
        ),
        "balanced": np.sqrt(np.square(normalized).sum(axis=1)),
        "productivity": pareto["objective_negative_tbh_proxy"],
    }
    selected: dict[str, pd.Series] = {}
    used: set[int] = set()
    signatures: set[tuple[float, ...]] = set()
    order = ("productivity", "conservative", "balanced")
    for label in order:
        for index in scores[label].sort_values(kind="stable").index:
            integer_index = int(index)
            row = pareto.loc[integer_index]
            signature = tuple(
                round(float(row[column]), 8)
                for column in (
                    "estimated_tbh_proxy",
                    "quality_failure_probability",
                    "energy_p50",
                )
            )
            exact_current = bool(
                np.allclose(
                    row[list(envelope.controllables)].to_numpy(float),
                    envelope.current,
                    rtol=0.0,
                    atol=1e-12,
                )
            )
            if integer_index not in used and signature not in signatures and not exact_current:
                selected[label] = pareto.loc[integer_index]
                used.add(integer_index)
                signatures.add(signature)
                break
        if label not in selected:
            for index in scores[label].sort_values(kind="stable").index:
                integer_index = int(index)
                if integer_index not in used:
                    selected[label] = pareto.loc[integer_index]
                    used.add(integer_index)
                    break
    if len(selected) != 3:
        raise RuntimeError("could not select three distinct Pareto alternatives")
    return selected
