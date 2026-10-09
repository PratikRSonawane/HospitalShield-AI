"""Meta endpoints: /health, /api/v1/hospital/baseline, /api/v1/model-card, /api/v1/weather."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.simulation import MODEL_VERSION, load_hospital_config
from app.simulation.result import ASSUMPTIONS, LIMITATIONS

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "data" / "demo_hospital.json"


@router.get("/health")
def health() -> dict:
    """Liveness plus optional services, reported as optional (never failure)."""
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "services": {"weather": {"required": False, "status": "optional"},
                     "history": {"required": False, "status": "optional"}},
    }


@router.get("/api/v1/hospital/baseline")
def hospital_baseline() -> dict:
    """The SYNTHETIC baseline hospital configuration."""
    cfg = load_hospital_config(CONFIG_PATH)
    from dataclasses import asdict
    data = asdict(cfg)
    for key in ("units_per_weighted_bed_hour", "noncritical_diurnal_profile", "diurnal_profile"):
        if isinstance(data.get(key), tuple):
            data[key] = list(data[key])
    data = _freeze(data)
    return {
        "model_version": MODEL_VERSION,
        "provenance": {"hospital_data": "SYNTHETIC", "source": "data/demo_hospital.json"},
        "limitations": list(LIMITATIONS),
        "assumptions": list(ASSUMPTIONS),
        "hospital": data,
    }


def _freeze(obj):
    if isinstance(obj, dict):
        return {k: (list(v) if isinstance(v, tuple) else _freeze(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_freeze(v) for v in obj]
    return obj


@router.get("/api/v1/model-card")
def model_card() -> dict:
    """Model card: purpose, scope, honest limitations (B1)."""
    return {
        "model_version": MODEL_VERSION,
        "name": "HospitalShield AI",
        "purpose": "Climate-resilience planning prototype for a hospital operations planner (HC-03).",
        "intended_use": "Planning exploration of extreme-weather scenarios and mitigation sequences.",
        "out_of_scope": ["clinical decisions", "engineering-safety validation", "live operations", "prediction"],
        "data": {"hospital": "SYNTHETIC (data/demo_hospital.json)",
                 "weather": "SYNTHETIC_PROFILE or REAL WEATHER via Open-Meteo adapter (labelled)",
                 "calibration_references": ["NHS England bed availability (open aggregate)",
                                            "MIMIC-IV v3.1 (credentialed; aggregates only, never row-level)"]},
        "determinism": "identical input + seed + model_version gives byte-identical output",
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
        "evaluation": "docs/test-report.md with real executed numbers",
    }
