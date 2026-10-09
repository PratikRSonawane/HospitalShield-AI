from pathlib import Path

import pytest

from app.simulation.config import load_hospital_config
from app.simulation.engine import run
from app.simulation.errors import InfeasibleInterventionError
from app.simulation.scenario import default_scenario


@pytest.fixture(scope="session")
def cfg():
    return load_hospital_config(Path(__file__).resolve().parents[2] / "data" / "demo_hospital.json")

SCENARIOS = ["normal_operations", "heatwave_power_stress", "heatwave_power_outage", "flood_storm_access"]
STRESS_LEVELS = ["low", "medium", "high"]
INTERVENTIONS = ["none", "surge", "reallocation", "shed", "recall", "resupply", "all"]
STOCHASTIC_SEEDS = [None, 1, 2, 3] # None means stochastic=False
DURATIONS = [1, 24, 72]

@pytest.mark.parametrize("scenario_name", SCENARIOS)
@pytest.mark.parametrize("stress", STRESS_LEVELS)
@pytest.mark.parametrize("intervention", INTERVENTIONS)
@pytest.mark.parametrize("stoch_seed", STOCHASTIC_SEEDS)
@pytest.mark.parametrize("duration", DURATIONS)
def test_scenario_matrix(cfg, scenario_name, stress, intervention, stoch_seed, duration):
    from dataclasses import replace
    scenario = default_scenario(scenario_name)
    scenario = replace(scenario, duration_hours=duration)

    # Adjust stress levels
    stress_opts = {"arrival_multiplier": scenario.stress.arrival_multiplier}
    if stress == "low":
        stress_opts["arrival_multiplier"] = 0.8
    elif stress == "high":
        stress_opts["arrival_multiplier"] = 1.5
    scenario = replace(scenario, stress=replace(scenario.stress, **stress_opts))

    stoch = stoch_seed is not None
    seed = stoch_seed if stoch_seed is not None else scenario.seed
    scenario = replace(scenario, stochastic=stoch, seed=seed)

    from app.simulation.interventions import parse_interventions

    try:
        interventions = {}
        if intervention in ("surge", "all"):
            interventions["activate_surge_beds"] = [{"unit": "ward", "beds": 5, "start_hour": 0}]
        if intervention in ("reallocation", "all"):
            interventions["reallocate_staff"] = [{"from_unit": "ward", "to_unit": "ed", "nurses": 2, "start_hour": 0}]
        if intervention in ("shed", "all"):
            interventions["reduce_noncritical_load_kw"] = [{"kw": 50, "start_hour": 0, "end_hour": duration}]
        if intervention in ("recall", "all"):
            interventions["recall_staff"] = [{"unit": "ward", "nurses": 2, "start_hour": 0}]
        if intervention in ("resupply", "all"):
            interventions["emergency_resupply"] = [{"items": {"oxygen": 1000.0}, "start_hour": 0}]

        interventions_obj = parse_interventions(interventions) if intervention != "none" else None

        result = run(cfg, scenario, interventions_obj)
        # invariants are verified inside run(); here we additionally require
        # that summary values equal values recomputed from the series
        assert len(result.series) == duration
        summary = result.summary
        assert summary["hours_power_deficit"] == sum(
            1 for r in result.series if r["power"]["deficit_kw"] > 0)
        assert summary["overflow_patient_hours"] == sum(
            r["ed"]["waiting"] + r["ed"]["boarding_ward"] + r["ed"]["boarding_icu"]
            for r in result.series)
        assert summary["peak_power_deficit_kw"] == pytest.approx(
            max((r["power"]["deficit_kw"] for r in result.series), default=0.0), abs=0.05)
    except InfeasibleInterventionError:
        # infeasible combinations are rejected with a structured error (B6);
        # the engine must never silently clamp them
        pass
