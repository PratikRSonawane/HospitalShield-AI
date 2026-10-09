"""Hospital profile upload + per-profile simulation tests."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parents[2]
DEMO = json.loads((ROOT / "data" / "demo_hospital.json").read_text(encoding="utf-8"))


def _upload(payload: dict, name: str = "upload.json"):
    return client.post("/api/v1/hospital/upload",
                       files={"file": (name, json.dumps(payload).encode(), "application/json")})


class TestUpload:
    def test_invalid_json_422(self):
        r = client.post("/api/v1/hospital/upload",
                        files={"file": ("h.json", b"{not json", "application/json")})
        assert r.status_code == 422

    def test_missing_fields_listed(self):
        r = _upload({"hospital_name": "Half Hospital"})
        assert r.status_code == 422
        details = r.json()["error"]["details"]
        assert any(str(d.get("field", "")) in ("ed", "ward", "icu") for d in details)

    def test_valid_upload_and_run(self, tmp_path: Path):
        payload = dict(DEMO)
        payload["hospital_name"] = "Northfield Community Hospital"
        payload["ward"] = {**DEMO["ward"], "beds": 80, "initial_occupied": 64}
        r = _upload(payload)
        assert r.status_code == 200
        body = r.json()
        assert body["profile_id"] == "northfield-community-hospital"
        assert body["beds_total"] == 80 + DEMO["icu"]["beds"] + DEMO["ed"]["bays"]

        sim = client.post("/api/v1/simulations", json={
            "scenario": "normal_operations", "duration_hours": 24,
            "hospital_profile": "northfield-community-hospital"})
        assert sim.status_code == 200
        assert len(sim.json()["series"]) == 24

    def test_unknown_profile_404(self):
        r = client.post("/api/v1/simulations", json={
            "scenario": "normal_operations", "hospital_profile": "does-not-exist"})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"

    def test_profiles_list_includes_uploads(self):
        r = client.get("/api/v1/hospital/profiles")
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["profiles"]]
        assert "demo" in ids

    def test_upload_sanitises_profile_id(self):
        payload = dict(DEMO)
        payload["hospital_name"] = "St. Mary's / Trauma Centre!"
        r = _upload(payload)
        assert r.status_code == 200
        assert "/" not in r.json()["profile_id"] and r.json()["profile_id"] == "st-mary-s-trauma-centre"
        # cleanup
        (ROOT / "data" / "hospitals" / "st-marys-trauma-centre.json").unlink(missing_ok=True)

    def test_demo_profile_is_default(self):
        r = client.post("/api/v1/simulations", json={"scenario": "normal_operations", "duration_hours": 4})
        assert r.status_code == 200
