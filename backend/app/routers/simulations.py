"""Simulation, comparison and plan endpoints (B9)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.response_models import ComparisonResponse, PlanResponse, SimulationResponse
from app.schemas import ComparisonRequest, PlanRequest, SimulationRequest
from app.services.comparison import compare
from app.services.planner import PlannerBudget, plan
from app.simulation import (
    MODEL_VERSION,
    parse_interventions,
    parse_scenario,
    run,
)
from app.simulation.result import ASSUMPTIONS, LIMITATIONS
from app.simulation.scenario import default_scenario

router = APIRouter(prefix="/api/v1")

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "data" / "demo_hospital.json"


def _cfg(profile_id: str = "demo"):
    from app.routers.hospitals import load_active_config
    return load_active_config(profile_id)


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
    profile_id = data.pop("hospital_profile", "demo")
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
    return scenario, interventions, data, profile_id


@router.post("/simulations")
def create_simulation(request: SimulationRequest) -> SimulationResponse:
    scenario, interventions, data, profile_id = _spec_from_request(request)
    result = run(_cfg(profile_id), scenario, interventions)
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
    scenario, interventions, data, profile_id = _spec_from_request(request)
    comparison = compare(_cfg(profile_id), scenario, interventions)
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
    profile_id = data.pop("hospital_profile", "demo")
    data.pop("interventions", None)
    scenario = parse_scenario(data)
    budget = PlannerBudget(
        max_simulations=request.budget.max_simulations,
        max_seconds=request.budget.max_seconds,
        max_actions=request.budget.max_actions,
        grid_hours=request.budget.grid_hours,
        lambda_burden=request.objective.lambda_burden,
    )
    result = plan(_cfg(profile_id), scenario, budget)
    baseline_run = run(_cfg(profile_id), scenario)
    return {
        "model_version": MODEL_VERSION,
        "input_hash": baseline_run.input_hash,
        "seed": scenario.seed,
        "assumptions": list(ASSUMPTIONS),
        "provenance": baseline_run.provenance,
        "limitations": list(LIMITATIONS),
        **result,
    }


@router.get("/simulations/{run_id}")
def get_simulation(run_id: str) -> dict:
    """Stored run history (Tier 2); 404 with the standard error shape."""
    from fastapi import HTTPException

    from app.db import get_run
    data = get_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="run not found in history")
    return data


@router.get("/runs")
def list_simulations(limit: int = 50) -> dict:
    """Recent runs (history is best-effort; empty when the store failed)."""
    from app.db import list_runs
    return {"runs": list_runs(limit=min(limit, 200))}
