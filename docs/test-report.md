# Test Report — Final Build Verification

## Backend Tests (pytest)
- **Framework:** `pytest` + `hypothesis`
- **Core Tests:** 118 passed
- **Scenario Matrix Tests:** 1,008 passed (4 scenarios × 3 stress × 7 interventions × 4 stochastic × 3 durations)
- **Total Tests:** 1,126 passed, 0 failed
- **Runtime:** ~13 seconds
- **Coverage:** > 90% on `app/simulation`

## Frontend Tests (vitest)
- **Framework:** `vitest` + `React Testing Library`
- **Total Tests:** 12 passed
- **Components covered:** KpiCard, AlertPanel, HospitalMap, ScenarioControls, ProvenanceBadge
- **Runtime:** ~2 seconds

## Frontend Build
- **Toolchain:** TypeScript (`tsc -b`) + Vite
- **Status:** ✅ Clean build, 0 errors
- **Output:** `dist/index.html` (0.62 kB), `index.css` (20.27 kB), `index.js` (744.20 kB gzip 212.76 kB)

## Golden Snapshots
Golden snapshots for four baseline scenarios (`normal_operations`, `heatwave_power_stress`, `heatwave_power_outage`, `flood_storm_access`) are generated and verified. Output is byte-identical across runs (deterministic).

## API Endpoints Verified
| Endpoint | Status |
|---|---|
| `POST /api/v1/simulations` | ✅ Run + persist to SQLite |
| `POST /api/v1/comparisons` | ✅ Baseline vs treatment |
| `POST /api/v1/plans` | ✅ Deterministic planner |
| `POST /api/v1/ensembles` | ✅ 3-seed ensemble, P10/P50/P90 |
| `POST /api/v1/sensitivity` | ✅ Tornado analysis (±20% stress) |
| `GET /api/v1/simulations/{id}` | ✅ Run history retrieval |
| `GET /api/v1/simulations/{id}/report` | ✅ Markdown report export |

## Hardening
- **Docker:** `Dockerfile` (multi-stage: node + python) + `docker-compose.yml`
- **Offline Fallback:** Frontend loads precomputed demo data when backend is unreachable
- **Error Boundary:** React ErrorBoundary wraps all pages
- **Provenance:** Every page shows `SYNTHETIC` / `CALCULATED` badges + model version

## Frontend Pages (6/6)
1. **Overview** — KPIs, alert panel, hour scrubber
2. **Hospital Twin** — SVG floor plan, unit status colours with icons
3. **Scenario Lab** — Preset selector, scenario controls, intervention panel
4. **Failure Points & Plan** — Timeline, action plan, planner integration
5. **Compare Runs** — Side-by-side baseline vs treatment delta table
6. **Assumptions & Data** — Full assumption list, limitation disclosures
