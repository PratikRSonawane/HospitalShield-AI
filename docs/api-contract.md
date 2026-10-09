# API contract

Base URL (dev): `http://127.0.0.1:8000`. Interactive docs: `/docs`, OpenAPI schema: `/openapi.json`
(also committed at `frontend/openapi.json`; the TypeScript types in `frontend/src/types/api.ts` are generated
from it and never hand-written).

## Envelope

Every response carries: `model_version`, `input_hash`, `seed`, `assumptions[]`, `provenance{}`,
`limitations[]`. `run_id` = first 16 hex chars of `sha256(canonical input JSON + model_version)`.
Identical input + seed + model version gives byte-identical JSON.

## Endpoints

| Method & path | Purpose |
|---|---|
| GET `/health` | Liveness; optional services (weather, history) reported as optional, never as failure. |
| GET `/api/v1/hospital/baseline` | The SYNTHETIC baseline configuration. |
| GET `/api/v1/hospital/profiles` | Available hospital profiles (demo + uploaded). |
| POST `/api/v1/hospital/upload` | Multipart upload of a hospital configuration JSON; validated, stored, sanity-checked. |
| GET `/api/v1/scenarios` | Presets, validated ranges, descriptions. |
| GET `/api/v1/weather` | Weather source status (`synthetic` in the offline demo; `live`/`cache`/`fallback` when the adapter is used). |
| GET `/api/v1/model-card` | Model card: purpose, scope, limitations. |
| POST `/api/v1/simulations` | Run one simulation; returns summary, hourly series, alerts, failure points. |
| POST `/api/v1/comparisons` | Baseline vs intervention from identical state/seed/weather; deltas, attribution, template explanations. |
| POST `/api/v1/plans` | Deterministic beam-search action planner ("best found within budget"). |
| POST `/api/v1/ensembles` | P10/P50/P90 bands across ≤ 200 seeded runs (Tier 2). |
| POST `/api/v1/sensitivity` | One-at-a-time tornado for Resilience Index and overflow (Tier 2). |
| GET `/api/v1/simulations/{run_id}` | Stored run history (best-effort SQLite). |
| GET `/api/v1/runs` | Recent runs. |

### Simulation request

All fields optional except `scenario`; unknown fields are rejected (`extra="forbid"`). Named presets are
applied server-side first (so `{"scenario": "heatwave_power_outage"}` alone uses the documented preset);
explicit fields override. `hospital_profile` (default `"demo"`) selects an uploaded hospital configuration.

```json
{
  "scenario": "heatwave_power_outage",
  "hospital_profile": "demo",
  "duration_hours": 72,
  "weather": {"mode": "synthetic_profile", "max_temperature_c": 43, "min_temperature_c": 30, "humidity_pct": 55},
  "stress": {"arrival_multiplier": 1.15, "los_multiplier": 1.5, "staff_availability_fraction": 0.9,
             "power_supply_fraction": 0.8},
  "outage": {"start_hour": 24, "duration_hours": 36, "grid_fraction": 0.0},
  "access": null,
  "backup": {"generator_availability_fraction": 1.0},
  "interventions": {
    "activate_surge_beds": [{"unit": "ward", "beds": 8, "start_hour": 6}],
    "reallocate_staff": [{"from_unit": "ed", "to_unit": "icu", "nurses": 2, "start_hour": 6}],
    "reduce_noncritical_load_kw": [{"kw": 40, "start_hour": 24, "end_hour": 60}],
    "recall_staff": [{"unit": "ed", "nurses": 1, "start_hour": 0}],
    "emergency_resupply": [{"fuel_l": 1000.0, "start_hour": 0}]
  },
  "stochastic": false,
  "seed": 42
}
```

### Validated ranges (B5)

`duration_hours` 1..72 (default 72) · `max_temperature_c` −10..55 with `min ≤ max` (default min = max − 10) ·
`humidity_pct` 0..100 (55) · `arrival_multiplier` 0..3 (preset) · `los_multiplier` 0.5..2 (1.0) ·
`staff_availability_fraction`, `power_supply_fraction`, `grid_fraction`, all access fractions 0..1 ·
`outage.start_hour` 0..71 and windows must fit the horizon · `seed` 0..2147483647 · `stochastic` bool.

### Error shape (all 4xx)

```json
{"error": {"code": "VALIDATION_ERROR | INFEASIBLE_INTERVENTION | NOT_FOUND | PAYLOAD_TOO_LARGE",
           "message": "...",
           "details": [{"field": "stress.arrival_multiplier", "reason": "must be <= 3.0", "rule": "bound"}]}}
```

A catch-all 500 returns a generic body with a request id and never a stack trace. Infeasible interventions are
rejected with `INFEASIBLE_INTERVENTION` and per-rule machine-readable reasons — nothing is clamped silently.

### curl smoke test

```bash
# success
curl -s -X POST http://127.0.0.1:8000/api/v1/simulations \
  -H "content-type: application/json" \
  -d '{"scenario": "heatwave_power_outage"}'

# validation error (arrival multiplier out of range)
curl -s -X POST http://127.0.0.1:8000/api/v1/simulations \
  -H "content-type: application/json" \
  -d '{"scenario": "heatwave_power_outage", "stress": {"arrival_multiplier": 9.9}}'
```

### Configuration endpoints

- `POST /api/v1/hospital/upload` — multipart file upload of a JSON configuration (schema:
  `data/hospital_template.json`). The strict engine parser validates every field and returns 422 with
  per-field reasons; a 24-hour sanity run flags sites whose normal-operations profile already trips alerts
  (returned as `warnings`, never as rejection). Uploaded profiles land in `data/hospitals/` and become
  selectable immediately via `hospital_profile`.
- `GET /api/v1/hospital/profiles` — the demo baseline plus every uploaded profile.
