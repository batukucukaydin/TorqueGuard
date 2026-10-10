"""Seeded trajectory campaigns, paired regression checks and bounded witnesses."""

import random
from . import MODEL_VERSION
from .model import Scenario, simulate, DT


def compare(s: Scenario):
    return {"model_version": MODEL_VERSION, "model_kind": "illustrative; synthetic injected fault",
            "dt_s": DT, "scenario": s.to_dict(),
            "runs": {v: simulate(s, v) for v in ("faulty", "corrected")}}


def generated_scenarios(seed, cases):
    rng = random.Random(seed)
    for i in range(cases):
        hold = rng.choice([1.0, 2.0, 3.0])
        yield Scenario(name=f"Seed {seed} / case {i}", initial_speed_kph=rng.choice([0, 2.9, 3, 5, 18, 45]),
                       soc=rng.choice([0, 0.099, 0.10, 0.101, 0.3, 0.9, 1]),
                       grip=rng.choice([0, 0.05, 0.2, 0.35, 0.8]), wet=rng.random() < 0.75,
                       restricted_sector=rng.random() < 0.8,
                       deployment_limit_kw=rng.choice([0, 100, 250, 350]),
                       throttle=rng.choice([0.0, 0.69, 0.70, 0.85, 1]),
                       brake_overlap=rng.random() < 0.1, clutch_engaged=rng.random() < 0.95,
                       engine_available=rng.random() < 0.95, hold_s=hold, duration_s=hold + 2)


def campaign(seed=2026, cases=100):
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer in [0, 4294967295]")
    if type(cases) is not int or not 1 <= cases <= 1_000_000:
        raise ValueError("cases must be an integer in [1, 1000000]")
    failures = {"faulty": 0, "corrected": 0}
    states = {v: set() for v in failures}
    edges = {v: set() for v in failures}
    conditions = set()
    witness = None
    corrected_witness = None
    rescued = 0
    for index, s in enumerate(generated_scenarios(seed, cases)):
        paired = {}
        conditions.add((s.wet, s.restricted_sector, s.brake_overlap, s.clutch_engaged, s.engine_available))
        for v in failures:
            result = simulate(s, v, retain_trace=False)
            paired[v] = result
            failures[v] += int(not result["passed"])
            states[v].update(result["states"])
            edges[v].update(result["edges"])
            if not result["passed"] and v == "faulty" and witness is None:
                witness = {"case_index": index, "scenario": s.to_dict(), "findings": result["findings"]}
            if not result["passed"] and v == "corrected" and corrected_witness is None:
                corrected_witness = {"case_index": index, "scenario": s.to_dict(), "findings": result["findings"]}
        rescued += int(not paired["faulty"]["passed"] and paired["corrected"]["passed"])
    return {"model_version": MODEL_VERSION, "seed": seed, "cases": cases, "failures": failures,
            "rescued_cases": rescued, "condition_combinations_observed": len(conditions),
            "condition_combinations_possible": 32,
            "states": {v: sorted(x) for v, x in states.items()},
            "edges": {v: sorted(x) for v, x in edges.items()},
            "first_counterexample": witness, "first_corrected_counterexample": corrected_witness,
            "scope": "Seeded sampled trajectories; not exhaustive state-space coverage or ECU certification"}
