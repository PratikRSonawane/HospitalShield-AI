"""Scenario metadata endpoints: presets, ranges, weather."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app.response_models import ScenarioInfo
from app.simulation import MODEL_VERSION
from app.simulation.result import ASSUMPTIONS, LIMITATIONS

router = APIRouter(prefix="/api/v1")

ROOT = Path(__file__).resolve().parents[3]
PRESETS_PATH = ROOT / "data" / "scenario_presets.json"


@router.get("/scenarios")
def scenarios() -> ScenarioInfo:
    """Presets and validated ranges for the Scenario Lab UI (B9)."""
    data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    return {
        "model_version": MODEL_VERSION,
        "presets": data["presets"],
        "ranges": data["ranges"],
        "provenance": {"scenario_assumptions": True},
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
    }


@router.get("/weather")
def weather() -> dict:
    """Weather source status. The default demo weather is SYNTHETIC_PROFILE;
    live Open-Meteo is optional and labelled REAL WEATHER when used."""
    return {
        "source": "synthetic",
        "fetched_at": None,
        "location": None,
        "series": [],
        "label": "SYNTHETIC_PROFILE",
        "note": "Set weather mode live_or_cached in a simulation request to use the Open-Meteo adapter.",
    }
