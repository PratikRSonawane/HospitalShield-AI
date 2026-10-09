# Test report — real executed numbers

Executed on the development machine (Windows 11, Python 3.11.15, Node 20+) on the committed tree. Every
number below is from an actual run; nothing is estimated.

## Summary

| Gate | Result |
|---|---|
| Backend tests | **1,133 passed** (`pytest tests/ -q`, 14.1 s; 42.0 s with coverage) |
| Coverage, `app/simulation` (the engine) | **92%** (gate: ≥ 90%) |
| `ruff check app tests scripts` | clean |
| `mypy` (strict, engine package) | clean — no issues in 18 source files |
| Frontend component tests | **12 passed** (Vitest + React Testing Library) |
| Frontend build | `tsc -b && vite build` succeeds, no TypeScript errors, no `any` |
| Determinism | same input + seed ⇒ byte-identical API responses (asserted in `test_api.py`) |

## Suite composition

- `test_units.py` — boundary cases: occupancy 0/100/unavailable, power deficit/reserve exclusivity, shed
  caps, staffing floors, supply identity, config validation.
- `test_engine.py` — scenario validation bounds and cross-field rules; intervention timing (surge delay,
  recall lead time scaled by access, resupply lead time and delivery fraction, fuel-resupply effect);
  reallocation conservation; feasibility rejections (surge over capacity, self-move, source floor, recall
  cap, resupply cap, beyond-horizon arrivals).
- `test_properties.py` — ~660 hypothesis examples across 11 properties: no negatives/NaN, percentages 0–100,
  deficit XOR reserve, fuel monotonicity, **exact integer patient conservation every hour**, supply identity,
  determinism, shed cap, summary-equals-series, and monotonicity (more arrivals never reduce peak overflow;
  lower grid never reduce deficit hours).
- `test_analysis.py` — alert episodes merge/split with full traceability fields; metrics bounds and
  completeness; failure points: ranking determinism, no-NaN margins, cascade parents fail earlier,
  hand-built zero-margin cases.
- `test_calibration.py` — the acceptance criteria: normal-operations steady state (mean occupancy over the
  final 24 h within ±5 pp, zero alerts, zero deficit), heatwave stress reaching ≥ 90% occupancy with
  interventions that measurably improve but don't eliminate, outage deficit + fuel exhaustion with the
  combined plan beating every single intervention, flood cover/shortfall timing, and
  **resupply-before-window beats resupply-inside-window**. Golden snapshots pin all four presets.
- `test_matrix.py` — the 1,008-cell matrix: 4 scenarios × 3 stress levels × 7 intervention sets × 4
  stochastic settings × 3 durations. Every cell asserts series length, summary-equals-series recomputation
  and the engine's invariants (violations raise); structurally infeasible combinations must be rejected by
  the feasibility validator, never clamped.
- `test_api.py` — every endpoint's 200/404/405/413/422 paths; malformed JSON, empty body, null,
  strings-for-numbers, NaN literals, unknown fields; byte-identical repeats; documented error shape; CORS.
- `test_hospital_upload.py` — profile upload: invalid JSON 422 with field reasons, valid upload + simulation
  on the uploaded profile, unknown profile 404, slug sanitisation, demo default.
- `frontend/src/test/components.test.tsx` — KPI cards show units and deltas; AlertPanel highlights hour
  ranges; HospitalMap colours follow backend status with icon + text; ScenarioControls show backend
  validation messages inline; provenance badges render.

## Performance (executed 2026-10-09)

| Operation | Median | Max | Budget |
|---|---|---|---|
| One 72-hour simulation | 9.4 ms | 13.6 ms (n=30) | 200 ms |
| Comparison (baseline + treatment + per-intervention attribution) | 45 ms | 50 ms (n=10) | 500 ms |
| Ensemble, 200 seeded 72-hour runs | 2.18 s | — | informal target < 5 s |
| Planner (600-simulation budget, beam width 5) | ~2.0–2.5 s wall clock, 300–500 engine runs | — | 5 s hard stop |
| Memory across 200 repeated runs | 0.7 MB peak traced; returns to baseline | — | stable |

The planner's wall-clock budget is enforced inside the search (`stopped_reason` reports
`budget_simulations` / `budget_seconds` / `marginal_gain`); results are labelled "best found within budget".

## Known non-issues

- `anyio` emits a deprecation warning through Starlette's TestClient (`BlockingPortal` alias); it comes from
  the library, not this codebase, and is tracked upstream.
- Run history and the weather cache are best-effort SQLite stores; tests cover the happy path, and their
  failure mode is a logged warning (by design — a database failure must never block a simulation).
