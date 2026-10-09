# HospitalShield AI — Developer Manual

Everything a new engineer (or a judge) needs to understand, run, modify and deploy this project. Read this
top to bottom once and the codebase should hold no surprises.

---

## 1. The problem we solve

**HC-03 (Mayo Clinic):** *Extreme weather can disrupt healthcare even when the hospital building remains
intact. Flooding may affect access or electrical systems, heat can increase cooling requirements, and storms
can disrupt utilities, staff availability and medical supply chains.*

Hospital emergency plans are usually static documents and spreadsheets. They answer "what is the policy?"
but not the questions a planner actually faces the night before a forecast storm:

- If the grid drops for 36 hours in a 43 °C heatwave, **when** does the generator fuel run out?
- Which department hits its limit first — ED bays, ward beds, ICU staffing?
- What should we do **first** — recall staff, order fuel, open surge beds, shed non-critical load?
- How much does each of those actually buy us, **measured**, not guessed?

HospitalShield AI is a **digital twin**: a computer model of one hospital's operational constraints that you
can stress with hypothetical weather and interrogate hour by hour. It computes the impact, pinpoints the
failure points and their cascades, searches for the best sequence of mitigations, and shows a measured
before/after comparison — all offline, all reproducible, all labelled honestly.

**What it is not** (and says so on every screen): not a clinical system, not an engineering-safety
certification of any real generator or ICU circuit, not a weather forecast, not a live operations tool.

## 2. What we used, and why

| Layer | Choice | Why this and not something else |
|---|---|---|
| Simulation engine | Python 3.11, plain functions + frozen dataclasses, NumPy only for seeded stochastic sampling | A simulation must be auditable line by line. No SimPy/OR-Tools/agent frameworks — every equation in the docs maps to a line of code. Deterministic by default; `numpy Generator(PCG64(seed))` only when stochastic mode is on. |
| API | FastAPI + Pydantic v2 | Strict boundary validation (`extra="forbid"`, explicit bounds, cross-field rules) so bad input dies with a structured 4xx, never a 500. |
| Frontend | React 19 + TypeScript (strict) + Vite + Tailwind v4 + Recharts + React Router | Fast to reason about, typed end-to-end from the OpenAPI schema (`openapi-typescript`). The UI renders backend results and never recomputes them. |
| Charts | Recharts | Standard, accessible, easy table-alternatives. |
| Storage | SQLite (optional) | Run history and weather cache only — best-effort, failures never block a simulation. No database is required to run anything. |
| Tests | pytest, hypothesis (property-based), Vitest + Testing Library | Conservation laws are properties, so they get property tests (~660 examples); boundaries get unit tests; the API gets contract tests. |
| Quality gates | ruff, mypy --strict (engine), tsc --strict | The engine package must typecheck strictly; it is the part whose arithmetic must be trustworthy. |
| Packaging | Docker Compose | One command for judges: `docker compose up --build`. |

## 3. Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│  Browser (React + TS, port 5173)                                       │
│  Overview · Hospital Twin · Scenario Lab · Failure Points & Plan ·     │
│  Compare Runs · Assumptions & Data                                     │
│  Renders only. Types generated from openapi.json. Never recomputes.    │
└───────────────┬────────────────────────────────────────────────────────┘
                │ /api/v1/* (JSON; vite dev proxy or CORS)
┌───────────────▼────────────────────────────────────────────────────────┐
│  FastAPI (port 8000)                                                   │
│  routers: simulations · comparisons · plans · tier2 · hospitals · meta │
│  schemas (Pydantic, extra=forbid) · error envelope · CORS · size guard │
└───────────────┬────────────────────────────────────────────────────────┘
                │ pure function calls
┌───────────────▼────────────────────────────────────────────────────────┐
│  Engine  backend/app/simulation/   (pure: no IO, no globals, no clock) │
│  config → scenario → timeline → [hourly loop] → alerts/metrics/        │
│  failure_points → invariants → SimulationResult                        │
│  Hourly loop (B3 order): weather → cooling → interventions → power →   │
│  staffing → supplies → usable beds → integer patient flow → row        │
└───────────────┬────────────────────────────────────────────────────────┘
                │ reads JSON at startup only
┌───────────────▼────────────────────────────────────────────────────────┐
│  data/  demo_hospital.json (SYNTHETIC baseline) · hospitals/*.json     │
│  (uploaded profiles) · scenario_presets.json · weather fallback CSV    │
└────────────────────────────────────────────────────────────────────────┘
        optional: SQLite run-history + weather cache · Open-Meteo (labelled)
```

### The engine's working principles

1. **Purity.** `backend/app/simulation/` has no file, network or clock access. A run is a pure function of
   (hospital config, scenario, interventions, seed, stochastic flag). That is what makes byte-identical
   reproducibility — and the golden-file tests — possible.
2. **Fixed step order.** Every hour executes the same ten steps (weather → cooling → interventions → power →
   staffing → supplies → usable beds → patient flow → record → post-processing). Order matters (e.g. staffing
   uses start-of-hour occupancy) and the tests pin it via golden snapshots.
3. **Conservation above convenience.** Patients, nurses, kW, litres and supply units are never created or
   destroyed. Patient conservation is verified **every hour**: arrivals = waiting + in ED + boarding + ward +
   ICU + discharged. Violations raise, they don't clamp.
4. **Constraint coupling is the point.** Power risk derates ED/ICU usable beds; staffing caps usable beds;
   stockouts derate them further; fuel exhaustion kills generator output. These couplings are explicit,
   documented in `docs/equations.md`, and drive the cascade analysis.
5. **Honesty at the boundary.** Synthetic data is labelled SYNTHETIC, scenario multipliers are labelled
   SCENARIO ASSUMPTION, computed outputs are CALCULATED, offline snapshots are PRECOMPUTED. Infeasible
   interventions are rejected with per-rule machine-readable reasons — never silently clamped.

### Data flow of one click ("Run simulation")

```
ScenarioControls (React state) ──POST /api/v1/simulations──▶ Pydantic SimulationRequest
  → named preset merged server-side → ScenarioSpec (validated) → InterventionsSpec (validated)
  → InterventionTimeline (per-hour effects, O(T))
  → engine.run(): hourly loop → rows[] → alerts → metrics → failure_points
  → SimulationResult (run_id = sha256(canonical input + model_version)[:16])
  → JSON envelope (model_version, input_hash, seed, assumptions, provenance, limitations)
  → React state (RunContext) → KPIs, charts, map, alerts, plan, compare
```

The planner is the same engine in a loop: deterministic beam search (width 5, ≤ 5 actions, ≤ 600 runs /
5 s wall clock) where each candidate is validated by the same feasibility rules and evaluated by a real run
with identical seed and weather. Score = `resilience_index − λ × burden`. Reference plans (no action,
everything at hour 0, reverse order) are always reported so order-and-timing effects are visible.

## 4. Module map

| Path | Responsibility |
|---|---|
| `backend/app/simulation/config.py` | Hospital JSON → frozen, validated dataclasses |
| `backend/app/simulation/scenario.py` | Scenario validation (B5 ranges), preset defaults, hourly weather/access resolution |
| `backend/app/simulation/interventions.py` | The five interventions + the feasibility validator (B6) |
| `backend/app/simulation/timeline.py` | Per-hour resolution of active interventions (delays, lead times, caps) |
| `backend/app/simulation/power.py` | Demand build-up, supply, deficit/reserve, fuel burn |
| `backend/app/simulation/staffing.py` | Availability × access, staffed capacity, required, shortfall |
| `backend/app/simulation/supplies.py` | Consumption vs deliveries, stock, cover hours, stockouts |
| `backend/app/simulation/patient_flow.py` | Arrivals, ED service cohorts, boarding, admissions, discharges (integers) |
| `backend/app/simulation/flow.py` | Carry-forward rounding (deterministic) and seeded samplers (stochastic) |
| `backend/app/simulation/engine.py` | The hourly loop, exact B3 order |
| `backend/app/simulation/alerts.py` | Rules R01–R11 merged into traceable episodes |
| `backend/app/simulation/metrics.py` | All summary metrics + the Resilience Index |
| `backend/app/simulation/failure_points.py` | Margins, binding constraint, ranked failures, cascades |
| `backend/app/simulation/invariants.py` | B4 conservation checks, raised as exceptions |
| `backend/app/services/` | comparison/attribution, planner, ensembles, sensitivity, weather adapter, template explainer |
| `backend/app/routers/` | HTTP surface incl. hospital profile upload |
| `frontend/src/` | pages/, components/ (map, charts, panels), state/RunContext, types/api.ts (generated) |

## 5. Run, test, verify

```bash
make setup && make verify     # install, lint, typecheck, test, build
make demo                     # verify + snapshots + start both servers
# or: docker compose up --build
```

Backend tests: `cd backend && ../.venv/Scripts/python -m pytest tests/ -q` (1,133 tests; see
`docs/test-report.md` for the executed numbers). Frontend: `npm test`, `npm run build`.

## 6. Extending it

- **Different hospital:** upload a configuration on the Assumptions & Data page (template at
  `data/hospital_template.json`), or drop a JSON into `data/hospitals/`. Schema reference and every bound:
  `docs/assumptions.md`.
- **New alert rule:** add the condition in `alerts.py::collect_alert_hours`, the severity mapping in
  `failure_points.py`, and a test; alerts are data, not UI.
- **New intervention:** model it in `interventions.py` (spec + feasibility rules), resolve it per hour in
  `timeline.py`, consume it in the relevant step, and add the planner candidate in
  `services/planner.py::enumerate_candidates`.
- **Different weather:** the engine accepts a provided hourly series (`weather.mode = "provided_series"`) or
  the Open-Meteo adapter (`app/services/weather.py`); both are labelled and cached/fallback-safe.

## 7. Glossary — every term used in the UI, API and docs

**Operational terms**

- **ED (Emergency Department)** — walk-in intake unit; capacity counted in *bays*.
- **Ward / ICU** — inpatient units; capacity counted in *beds*. ICU patients need ~1 nurse per 2 patients.
- **Bay** — an ED treatment slot; a boarding patient still occupies one.
- **LOS (length of stay)** — hours a patient occupies a slot. ED LOS (4 h) sets ED turnover; inpatient
  **ALOS** (average LOS, e.g. ward 108 h) sets the discharge rate `1/ALOS` per hour.
- **LOS multiplier** — scenario stress factor that stretches ALOS (sicker patients, slower turnover).
- **Boarding** — a patient admitted to ward/ICU but still held in an ED bay because no inpatient bed is
  usable. Boarding is the mechanism by which full wards clog the ED.
- **Surge beds** — extra physical beds that can be opened during an emergency. They are usable only after an
  **activation delay** (staff must set them up) and only if staffed and powered.
- **patients_per_nurse** — staffing ratio per unit; `staffed_capacity = floor(nurses × ratio)`.
- **Roster / recall** — roster = nurses assigned to a unit; recall = calling in off-duty staff (capped, with a
  lead time, scaled by how many can physically reach the hospital).
- **Reallocation** — permanently moving nurses between named units for the rest of the run; source unit must
  keep its floor fraction of roster and at least its required nurses.
- ** beds_over_usable** — occupied patients above usable capacity. Patients are never ejected; the excess is
  reported and admissions to that unit stop.

**Power terms**

- **Critical / non-critical load** — kW demand that must never be interrupted (life-safety, essential
  equipment) vs comfort/administrative demand. Only non-critical load may be shed, up to a cap.
- **Cooling load** — extra kW needed when temperature exceeds the cooling threshold (28 °C); split into a
  critical and a comfort share.
- **Grid fraction** — usable share of the grid connection (1.0 normally; 0.0 during an outage; derated in
  stress scenarios).
- **Generator** — backup supply, kW-capped and **fuel-limited**: `available = min(capacity, fuel ÷ burn rate)`.
  It only burns fuel for the gap between demand and grid supply.
- **Deficit / reserve** — unserved demand vs headroom; mutually exclusive by definition, checked every hour.
- **Critical load at risk** — the amount of critical demand that cannot be served this hour. Never hidden,
  never shed; it instead *derates* ED/ICU usable capacity (documented assumption).
- **Derate** — a proportional reduction of usable capacity under duress (power risk, stockout). Scenario
  assumptions, not physics.
- **Shed** — deliberately dropping non-critical load to reduce demand. Comfort impact only; comfort note
  shown, never a clinical claim.

**Supply terms**

- **Supply item** — oxygen, essential_meds; consumed per *weighted occupied bed-hour* (ICU weighs 2×, ED 0.5×).
- **Cover hours** — stock ÷ current consumption: how many hours until the item runs out.
- **Stockout** — stock at zero while demand continues; derates ED/ICU usable capacity and blocks further
  consumption (recorded as `unmet`, never negative stock).
- **Emergency resupply** — one-off delivery after a lead time, scaled by the delivery fraction at the arrival
  hour. A request made before a flood access window arrives; one made inside it may not — **sequencing is the
  lesson**.

**Analysis terms**

- **Margin** — normalised slack (0–1) per resource: beds, staffing, power, supplies, ED flow. Zero = the
  constraint is binding; negative = over capacity.
- **Binding constraint** — the resource with the smallest margin in an hour; ties break in the fixed order
  power → supplies → staff → beds → ED flow. Rendered as the ribbon under the map.
- **Failure point** — the first hour a margin hits zero or an alert reaches high/critical. Episodes are
  ranked by first hour, then severity.
- **Cascade** — a failure caused by an earlier one through a documented coupling (fuel exhaustion → power
  deficit; power risk → bed derate → ED boarding…). The UI marks children with ↳ and the parent rule.
- **Alert rules R01–R11** — fixed, named conditions (occupancy thresholds, ED boarding/waiting, staffing
  shortfall, power deficit, critical load at risk, reserve low, fuel low/exhausted, supply low/stockout),
  each episode carrying rule id, threshold, observed peak, unit and hour range.
- **Resilience Index (RI)** — 0–100 planning score: 100 minus weighted, normalised penalties for occupancy
  strain, overflow, staffing shortfall, power deficit, critical risk and stockouts. Weights and formula are
  published (`docs/equations.md`). For comparing runs — explicitly not a validated safety score.
- **run_id / input_hash** — sha256-derived fingerprints making every run reproducible and citable.
- **Deterministic vs stochastic mode** — deterministic rounds fractional flows with carry-forward (no
  randomness); stochastic samples Poisson arrivals and Binomial completions from a seeded generator. Same
  input + seed ⇒ byte-identical output either way.

**Scenario terms**

- **Preset** — a documented starting configuration per scenario; server-side merged so the raw API and the UI
  agree; every field overridable.
- **Stress** — the heatwave family: arrival multiplier, LOS multiplier, staff availability, grid supply
  fraction.
- **Outage window** — hours when grid fraction drops (usually to 0).
- **Access window** — flood/storm hours reducing staff access, deliveries and adding storm arrivals; the
  warning lead time is what makes early resupply valuable.

## 8. FAQ

**Why is everything synthetic?** Real hospital operations data is sensitive and site-specific. A synthetic
baseline calibrated to documented criteria lets anyone verify the model, and the upload feature takes real
parameters when a hospital is ready to provide them (with expert review).

**Why not machine learning?** The problem is constraint modelling, not pattern matching. Deterministic
simulation gives exact conservation, full auditability and reproducibility — the properties a planner needs
to defend a decision. An LLM layer could only annotate computed results, never produce them.

**Why hourly resolution?** Operational decisions (recall staff, order fuel, open surge beds) have lead times
of hours. Hourly steps keep every lead time meaningful and the conservation arithmetic exact in integers.

**How do I know the numbers are right?** You can't "know" — you verify. The invariants (conservation,
monotonicity, bounds) are machine-checked on every hour of a 1,008-cell scenario matrix; the calibration
targets are asserted in tests; the equations are published next to the code that implements them. Start at
`docs/equations.md` and read `patient_flow.py` — they match.
