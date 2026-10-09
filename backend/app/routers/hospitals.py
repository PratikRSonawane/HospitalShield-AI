"""Hospital profile management: upload and activate any hospital's
configuration so the twin can be deployed at a different site in minutes.

A profile is the same JSON schema as data/demo_hospital.json (documented in
docs/assumptions.md and data/hospital_template.json). Uploaded profiles are
validated with the strict engine parser, stored under data/hospitals/, and
selected per request via the `hospital_profile` field ("demo" by default).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from app.simulation import parse_hospital_config
from app.simulation.errors import SimulationValidationError
from app.simulation.result import ASSUMPTIONS, LIMITATIONS, MODEL_VERSION

router = APIRouter(prefix="/api/v1/hospital")

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
HOSPITALS_DIR = DATA / "hospitals"
DEMO_CONFIG = DATA / "demo_hospital.json"
MAX_UPLOAD_BYTES = 200_000

_SLUG = re.compile(r"[^a-z0-9_-]+")


def _slugify(name: str) -> str:
    slug = _SLUG.sub("-", name.lower()).strip("-")[:48]
    return slug or "uploaded"


class HospitalProfileInfo(BaseModel):
    id: str
    hospital_name: str
    source: str

    model_config = ConfigDict(extra="forbid")


class UploadResult(BaseModel):
    profile_id: str
    hospital_name: str
    beds_total: int
    warnings: list[str] = []

    model_config = ConfigDict(extra="forbid")


def load_active_config(profile_id: str = "demo"):
    """Load the hospital config for a profile id ('demo' = built-in baseline).

    Raises HTTPException 404 for unknown profiles, so callers map unknown
    profile ids onto the documented error shape.
    """
    if profile_id in ("", "demo"):
        return parse_hospital_config(json.loads(DEMO_CONFIG.read_text(encoding="utf-8")))
    path = HOSPITALS_DIR / f"{_slugify(profile_id)}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"unknown hospital profile {profile_id!r}")
    return parse_hospital_config(json.loads(path.read_text(encoding="utf-8")))


@router.get("/profiles")
def list_profiles() -> dict:
    """All available hospital profiles (built-in demo plus uploaded)."""
    profiles: list[HospitalProfileInfo] = [
        HospitalProfileInfo(id="demo", hospital_name="Fictional General Hospital (synthetic)",
                            source="data/demo_hospital.json"),
    ]
    if HOSPITALS_DIR.exists():
        for path in sorted(HOSPITALS_DIR.glob("*.json")):
            try:
                cfg = parse_hospital_config(json.loads(path.read_text(encoding="utf-8")))
                profiles.append(HospitalProfileInfo(id=path.stem, hospital_name=cfg.hospital_name,
                                                    source=str(path)))
            except (SimulationValidationError, json.JSONDecodeError):
                continue
    return {"model_version": MODEL_VERSION, "profiles": [p.model_dump() for p in profiles],
            "assumptions": list(ASSUMPTIONS), "limitations": list(LIMITATIONS)}


_REQUIRED_FILE = File(...)


@router.post("/upload", response_model=UploadResult)
async def upload_profile(file: UploadFile = _REQUIRED_FILE) -> UploadResult:
    """Upload a hospital configuration JSON (schema: data/hospital_template.json).

    The strict engine parser validates every parameter; invalid files are
    rejected with 422 and per-field reasons. Nothing is clamped silently.
    """
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="hospital configuration exceeds 200 KB")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"not valid JSON: {exc.msg}") from exc

    try:
        cfg = parse_hospital_config(data, source_path="upload")
    except SimulationValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "hospital configuration failed validation",
                    "details": [i.to_dict() for i in exc.issues]},
        ) from exc

    profile_id = _slugify(cfg.hospital_name)
    HOSPITALS_DIR.mkdir(parents=True, exist_ok=True)
    target = HOSPITALS_DIR / f"{profile_id}.json"
    if profile_id != "demo":
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")

    warnings: list[str] = []
    try:
        from app.simulation import default_scenario, run
        probe = run(cfg, default_scenario("normal_operations", {"duration_hours": 24}))
        if probe.summary["hours_power_deficit"] > 0 or probe.alerts:
            warnings.append("Sanity run (24 h normal operations) shows alerts or a power deficit; "
                            "review power and staffing parameters against docs/assumptions.md.")
    except Exception:  # the sanity probe must never block an otherwise valid upload
        warnings.append("Sanity run could not be executed; validation only.")

    return UploadResult(profile_id=profile_id, hospital_name=cfg.hospital_name,
                        beds_total=cfg.ward.beds + cfg.icu.beds + cfg.ed.bays, warnings=warnings)
