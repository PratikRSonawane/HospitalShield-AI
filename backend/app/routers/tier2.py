"""Tier 2 endpoints: POST /api/v1/ensembles and POST /api/v1/sensitivity."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import ConfigDict, Field

from app.routers.simulations import _spec_from_request
from app.schemas import SimulationRequest
from app.services.tier2 import run_ensemble, run_sensitivity
from app.simulation.result import ASSUMPTIONS, LIMITATIONS, MODEL_VERSION

router = APIRouter(prefix="/api/v1")


class EnsembleRequest(SimulationRequest):
    runs: int = Field(default=60, ge=2, le=200)

    model_config = ConfigDict(extra="forbid")


class SensitivityRequest(SimulationRequest):
    pass


@router.post("/ensembles")
def ensembles(request: EnsembleRequest) -> dict:
    scenario, _interventions, _data, profile_id = _spec_from_request(request)
    cfg = _cfg(profile_id)
    return {
        "model_version": MODEL_VERSION,
        "seed": scenario.seed,
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
        **run_ensemble(cfg, scenario, request.runs),
    }


@router.post("/sensitivity")
def sensitivity(request: SensitivityRequest) -> dict:
    scenario, _interventions, _data, profile_id = _spec_from_request(request)
    cfg = _cfg(profile_id)
    return {
        "model_version": MODEL_VERSION,
        "seed": scenario.seed,
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
        **run_sensitivity(cfg, scenario),
    }


def _cfg_path() -> str:
    from pathlib import Path
    return str(Path(__file__).resolve().parents[3] / "data" / "demo_hospital.json")


def _cfg(profile_id: str = "demo"):
    from app.routers.hospitals import load_active_config
    return load_active_config(profile_id)
