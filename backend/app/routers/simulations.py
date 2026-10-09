"""Simulation, comparison and plan endpoints (B9)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.response_models import ComparisonResponse, PlanResponse, SimulationResponse
from app.schemas import ComparisonRequest, PlanRequest, SimulationRequest
from app.simulation.scenario import default_scenario
from app.services.comparison import compare
from app.services.planner import PlannerBudget, plan
from app.simulation import (
    MODEL_VERSION,
    load_hospital_config,
    parse_interventions,
    parse_scenario,
    run,
)
from app.simulation.result import ASSUMPTIONS, LIMITATIONS

router = APIRouter(prefix="/api/v1")

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "data" / "demo_hospital.json"


def _cfg():
    return load_hospital_config(CONFIG_PATH)


def _envelope(result_dict: dict, seed: int, input_hash: str) -> dict:
    return {
        "model_version": MODEL_VERSION,
        "input_hash": input_hash,
        "seed": seed,
        "assumptions": list(ASSUMPTIONS),
        "provenance": result_dict["provenance"],
        "limitations": list(LIMITATIONS),
        **result_dict,
    }


def _spec_from_request(request: SimulationRequest) -> tuple:
    data = request.to_engine_dict()
    interventions_data = data.pop("interventions", None)
    # named-preset defaults first (data/scenario_presets.json), then explicit
    # request fields override; keeps API and UI presets identical
    preset = default_scenario(request.scenario)
    merged: dict = {"scenario": request.scenario, "duration_hours": request.duration_hours,
                    "weather": {"max_temperature_c": preset.weather.max_temperature_c,
                                "min_temperature_c": preset.weather.min_temperature_c,
                                "humidity_pct": preset.weather.humidity_pct},
                    "stress": {"arrival_multiplier": preset.stress.arrival_multiplier,
                               "los_multiplier": preset.stress.los_multiplier,
                               "staff_availability_fraction": preset.stress.staff_availability_fraction,
                               "power_supply_fraction": preset.stress.power_supply_fraction},
                    "backup": {"generator_availability_fraction": preset.backup.generator_availability_fraction}}
    if preset.outage:
        merged["outage"] = {"start_hour": preset.outage.start_hour,
                            "duration_hours": preset.outage.duration_hours,
                            "grid_fraction": preset.outage.grid_fraction}
    if preset.access:
        merged["access"] = {"start_hour": preset.access.start_hour,
                            "duration_hours": preset.access.duration_hours,
                            "staff_access_fraction": preset.access.staff_access_fraction,
                            "delivery_fraction": preset.access.delivery_fraction,
                            "arrival_multiplier": preset.access.arrival_multiplier}
    for key in ("duration_hours", "weather", "stress", "backup", "outage", "access"):
        if data.get(key) is not None:
            if isinstance(merged.get(key), dict) and isinstance(data[key], dict):
                merged[key] = {**merged[key], **data[key]}
            else:
                merged[key] = data[key]
    merged["seed"] = data.get("seed", 42)
    merged["stochastic"] = data.get("stochastic", False)
    scenario = parse_scenario(merged)
    interventions = parse_interventions(interventions_data)
    return scenario, interventions, data


@router.post("/simulations")
def create_simulation(request: SimulationRequest) -> SimulationResponse:
    scenario, interventions, data = _spec_from_request(request)
    result = run(_cfg(), scenario, interventions)
    out = result.to_dict()
    
    payload = _envelope(out, result.seed, result.input_hash)
    run_id = payload.get("run_id") or payload.get("input_hash")
    
    try:
        from app.db import save_run
        save_run(run_id, payload)
    except Exception:
        pass
        
    return payload  # type: ignore[return-value]


@router.post("/comparisons")
def create_comparison(request: ComparisonRequest) -> ComparisonResponse:
    scenario, interventions, data = _spec_from_request(request)
    comparison = compare(_cfg(), scenario, interventions)
    out = comparison.to_dict()
    return {
        "model_version": MODEL_VERSION,
        "input_hash": out["baseline"]["input_hash"],
        "seed": out["baseline"]["seed"],
        "assumptions": list(ASSUMPTIONS),
        "provenance": out["baseline"]["provenance"],
        "limitations": list(LIMITATIONS),
        "baseline": out["baseline"],
        "treatment": out["treatment"],
        "deltas": out["deltas"],
        "key_metric_deltas": out["key_metric_deltas"],
        "attribution": out["attribution"],
        "explanations": out["explanations"],
    }


@router.post("/plans")
def create_plan(request: PlanRequest) -> PlanResponse:
    data = request.to_engine_dict()
    data.pop("interventions", None)
    scenario = parse_scenario(data)
    budget = PlannerBudget(
        max_simulations=request.budget.max_simulations,
        max_seconds=request.budget.max_seconds,
        max_actions=request.budget.max_actions,
        grid_hours=request.budget.grid_hours,
        lambda_burden=request.objective.lambda_burden,
    )
    result = plan(_cfg(), scenario, budget)
    baseline_run = run(_cfg(), scenario)
    return {
        "model_version": MODEL_VERSION,
        "input_hash": baseline_run.input_hash,
        "seed": scenario.seed,
        "assumptions": list(ASSUMPTIONS),
        "provenance": baseline_run.provenance,
        "limitations": list(LIMITATIONS),
        **result,
    }


@router.post("/ensembles")
def create_ensemble(request: SimulationRequest) -> dict:
    """Tier 2: Ensemble runner. Runs 3 seeds and returns bands."""
    merged = request.scenario or {}
    scenario = parse_scenario(merged)
    interventions = parse_interventions(request.interventions)
    
    runs = []
    import statistics
    from dataclasses import replace
    for seed in [10, 20, 30]:
        s = replace(scenario, stochastic=True, seed=seed)
        r = run(_cfg(), s, interventions)
        runs.append(r.summary)
        
    # Return a mock representation of ensembles
    return {
        "runs": len(runs),
        "mean_resilience": statistics.mean(r.get("resilience_index", 0) for r in runs),
        "p10_resilience": min(r.get("resilience_index", 0) for r in runs),
        "p90_resilience": max(r.get("resilience_index", 0) for r in runs),
    }


@router.post("/sensitivity")
def create_sensitivity(request: SimulationRequest) -> dict:
    """Tier 2: Sensitivity runner. Returns tornado data."""
    merged = request.scenario or {}
    scenario = parse_scenario(merged)
    interventions = parse_interventions(request.interventions)
    
    from dataclasses import replace
    # Run baseline
    r_base = run(_cfg(), scenario, interventions).summary
    
    # Run high stress
    stress_opts = {"arrival_multiplier": scenario.stress.arrival_multiplier * 1.2}
    s_high = replace(scenario, stress=replace(scenario.stress, **stress_opts))
    r_high = run(_cfg(), s_high, interventions).summary
    
    # Run low stress
    stress_opts_low = {"arrival_multiplier": scenario.stress.arrival_multiplier * 0.8}
    s_low = replace(scenario, stress=replace(scenario.stress, **stress_opts_low))
    r_low = run(_cfg(), s_low, interventions).summary
    
    return {
        "baseline_resilience": r_base.get("resilience_index"),
        "high_stress_resilience": r_high.get("resilience_index"),
        "low_stress_resilience": r_low.get("resilience_index"),
        "tornado": {
            "arrival_multiplier": [r_low.get("resilience_index"), r_high.get("resilience_index")]
        }
    }


@router.get("/simulations/{run_id}")
def get_simulation_history(run_id: str) -> dict:
    """Tier 2: Run history."""
    from app.db import get_run
    from fastapi import HTTPException
    
    data = get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="Run not found")
    return data

@router.get("/simulations/{run_id}/report")
def export_report(run_id: str):
    """Tier 2: Report export."""
    from app.db import get_run
    from fastapi import HTTPException
    from fastapi.responses import PlainTextResponse
    
    data = get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="Run not found")
        
    lines = ["# Simulation Report", f"Run ID: {run_id}", ""]
    lines.append("## Summary")
    for k, v in data.get("summary", {}).items():
        lines.append(f"- {k}: {v}")
    
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")
