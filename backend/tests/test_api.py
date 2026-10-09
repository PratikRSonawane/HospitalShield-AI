"""API contract tests (S3): endpoints, error shapes, determinism, CORS."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import MAX_BODY_BYTES, create_app

client = TestClient(create_app())

BASE = str(Path(__file__).resolve().parents[2])


class TestHealthAndMeta:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok" and body["services"]["weather"]["required"] is False

    def test_baseline(self):
        r = client.get("/api/v1/hospital/baseline")
        assert r.status_code == 200
        assert r.json()["provenance"]["hospital_data"] == "SYNTHETIC"
        assert r.json()["hospital"]["ed"]["bays"] == 26

    def test_scenarios(self):
        r = client.get("/api/v1/scenarios")
        assert r.status_code == 200
        body = r.json()
        assert set(body["presets"]) >= {"normal_operations", "heatwave_power_stress",
                                        "heatwave_power_outage", "flood_storm_access"}
        assert body["ranges"]["duration_hours"]["max"] == 72

    def test_model_card(self):
        r = client.get("/api/v1/model-card")
        assert r.status_code == 200
        assert "SYNTHETIC" in r.json()["data"]["hospital"]

    def test_weather_optional(self):
        r = client.get("/api/v1/weather")
        assert r.status_code == 200
        assert r.json()["source"] in ("synthetic", "live", "cache", "fallback")

    def test_openapi_docs(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "/api/v1/simulations" in r.json()["paths"]


VALID = {"scenario": "heatwave_power_outage", "duration_hours": 48,
         "weather": {"max_temperature_c": 43}, "outage": {"start_hour": 12, "duration_hours": 12, "grid_fraction": 0.0}}


class TestSimulations:
    def test_valid_run(self):
        r = client.post("/api/v1/simulations", json=VALID)
        assert r.status_code == 200
        body = r.json()
        for key in ("run_id", "model_version", "input_hash", "seed", "assumptions",
                    "provenance", "limitations", "summary", "series", "alerts", "failure_points"):
            assert key in body
        assert len(body["series"]) == 48
        assert 0 <= body["summary"]["resilience_index"] <= 100

    def test_byte_identical_repeats(self):
        a = client.post("/api/v1/simulations", json=VALID)
        b = client.post("/api/v1/simulations", json=VALID)
        assert a.content == b.content

    def test_run_id_is_16_hex(self):
        rid = client.post("/api/v1/simulations", json=VALID).json()["run_id"]
        assert len(rid) == 16
        int(rid, 16)

    def test_interventions_and_comparison(self):
        # ED->ICU reallocation raises ICU staffed capacity, so it must move the result
        req = {**VALID, "interventions": {"reallocate_staff": [
            {"from_unit": "ed", "to_unit": "icu", "nurses": 2, "start_hour": 6}]}}
        r = client.post("/api/v1/simulations", json=req)
        assert r.status_code == 200
        r = client.post("/api/v1/comparisons", json=req)
        assert r.status_code == 200
        body = r.json()
        assert body["deltas"]["resilience_index"]["absolute"] != 0
        assert body["attribution"]


class TestValidationErrors:
    def test_each_invalid_field_422(self):
        cases = [
            {"scenario": "earthquake"},
            {"scenario": "heatwave_power_outage", "duration_hours": 0},
            {"scenario": "heatwave_power_outage", "duration_hours": 73},
            {"scenario": "heatwave_power_outage", "weather": {"max_temperature_c": 99}},
            {"scenario": "heatwave_power_outage", "weather": {"min_temperature_c": 50, "max_temperature_c": 30}},
            {"scenario": "heatwave_power_outage", "stress": {"arrival_multiplier": 4.0}},
            {"scenario": "heatwave_power_outage", "stress": {"los_multiplier": 0.1}},
            {"scenario": "heatwave_power_outage", "outage": {"start_hour": 40, "duration_hours": 40, "grid_fraction": 0.0}, "duration_hours": 48},
            {"scenario": "heatwave_power_outage", "seed": -1},
            {**VALID, "unknown_field": 1},
        ]
        for case in cases:
            r = client.post("/api/v1/simulations", json=case)
            assert r.status_code == 422, f"{case} -> {r.status_code}"
            body = r.json()
            assert body["error"]["code"] == "VALIDATION_ERROR"
            assert isinstance(body["error"]["details"], list) and body["error"]["details"]

    def test_infeasible_intervention_422(self):
        req = {**VALID, "interventions": {"activate_surge_beds": [{"unit": "icu", "beds": 99, "start_hour": 0}]}}
        r = client.post("/api/v1/simulations", json=req)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INFEASIBLE_INTERVENTION"
        assert r.json()["error"]["details"][0]["rule"] == "surge_capacity"

    def test_malformed_json_422(self):
        r = client.post("/api/v1/simulations", content=b"{not json",
                        headers={"content-type": "application/json"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_empty_body_422(self):
        r = client.post("/api/v1/simulations", content=b"",
                        headers={"content-type": "application/json"})
        assert r.status_code == 422

    def test_null_body_422(self):
        r = client.post("/api/v1/simulations", content=b"null",
                        headers={"content-type": "application/json"})
        assert r.status_code == 422

    def test_string_for_number_422(self):
        r = client.post("/api/v1/simulations", json={"scenario": "heatwave_power_outage", "duration_hours": "soon"})
        assert r.status_code == 422

    def test_nan_literal_rejected(self):
        r = client.post("/api/v1/simulations", content=b'{"scenario": "heatwave_power_outage", "weather": {"max_temperature_c": NaN}}',
                        headers={"content-type": "application/json"})
        assert r.status_code == 422

    def test_unknown_unit_rejected(self):
        req = {**VALID, "interventions": {"activate_surge_beds": [{"unit": "parking", "beds": 2, "start_hour": 0}]}}
        r = client.post("/api/v1/simulations", json=req)
        assert r.status_code == 422

    def test_not_found_404(self):
        r = client.get("/api/v1/nope")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"

    def test_method_not_allowed_405(self):
        r = client.delete("/api/v1/simulations")
        assert r.status_code == 405

    def test_payload_too_large_413(self):
        r = client.post("/api/v1/simulations", content=b"x" * (MAX_BODY_BYTES + 10),
                        headers={"content-type": "application/json", "content-length": str(MAX_BODY_BYTES + 10)})
        assert r.status_code == 413

    def test_error_shape_documented(self):
        r = client.post("/api/v1/simulations", json={"scenario": 123})
        body = r.json()
        assert set(body) == {"error"}
        assert set(body["error"]) >= {"code", "message", "details"}


class TestPlans:
    def test_plan_returns_ordered_plan(self):
        r = client.post("/api/v1/plans", json={"scenario": "flood_storm_access",
                                               "budget": {"max_simulations": 80, "max_seconds": 5}})
        assert r.status_code == 200
        body = r.json()
        assert body["label"] == "best found within budget"
        starts = [a["start_hour"] for a in body["action_plan"]]
        assert starts == sorted(starts)
        assert body["search_stats"]["simulations_used"] <= body["search_stats"]["max_simulations"]


class TestCors:
    def test_cors_headers_present(self):
        app = create_app()
        c = TestClient(app)
        r = c.options("/api/v1/simulations", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST"})
        assert r.status_code in (200, 204)
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
