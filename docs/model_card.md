# Model card — HospitalShield AI

| | |
|---|---|
| Model version | 1.0.0 (semver; every API response carries it) |
| Problem | HC-03 — Climate-Resilient Hospital Digital Twin (Mayo Clinic problem statement, FUSION 2026) |
| Type | Deterministic discrete-time operational simulation (constraint-coupled digital twin), with an optional seeded stochastic mode |
| Horizon | 1–72 hours, hourly steps |
| Domains | Weather, infrastructure/utilities (grid, generator, fuel, cooling), staff, medical supplies, patient flow across ED/Ward/ICU |
| Determinism | Identical input + seed + model version ⇒ byte-identical output (`run_id` = sha256 prefix of canonical input) |

## Intended use

A **planning prototype** for hospital operations and emergency-preparedness planners to explore
"what happens to *this* hospital under *this* weather scenario, which constraints bind first, and which
sequence of mitigations buys the most resilience." The action planner answers what to do, in what order, and
when — as a decision aid with explicit lead times and feasibility rules.

## Out of scope / not intended for

- Clinical decisions of any kind
- Engineering-safety validation of power systems, generators, HVAC or life-support circuits
- Live operational control or incident command
- Prediction or forecasting of actual weather, demand, or outcomes

## Data

- Hospital parameters: **SYNTHETIC**, calibrated in-repo (`docs/assumptions.md`), plus **user-uploaded
  configurations** (facility-level operational values supplied by the operator; the engine validates structure
  and bounds only).
- Weather: synthetic diurnal profile by default; optional **REAL WEATHER** from Open-Meteo (labelled, cached,
  attributed), synthetic fallback.
- Reference datasets (MIMIC-IV via local credentialed aggregates with small-cell suppression; NHS England open
  bed statistics) are optional calibration priors — never runtime data, never row-level.

## Architecture in one paragraph

A pure Python engine computes an hourly loop over weather → cooling → interventions → power → staffing →
supplies → usable beds → integer patient flow, enforcing resource conservation and cross-domain couplings
(power risk derates ED/ICU capacity; staffing caps usable beds; stockouts derate; fuel exhaustion removes
generator output). Alert rules R01–R11, summary metrics, a transparent Resilience Index, failure-point and
cascade analysis, and a beam-search planner all read from the same hourly series. FastAPI wraps the engine
with strict validation; a React/TypeScript dashboard renders results and never recomputes them.

## Evaluation

- 1,133 backend tests including ~660 hypothesis property cases, a 1,008-cell scenario matrix, calibration
  acceptance tests (B10) and golden snapshots — see `docs/test-report.md`.
- Frontend: 12 component tests; typed API contract generated from the OpenAPI schema.

## Limitations (be upfront; it earns trust)

- All hospital values are synthetic or operator-supplied; heat-to-demand multipliers are scenario assumptions,
  not predictions.
- Power is an abstract operational constraint: no claim about real generator, ICU or life-support safety.
- Outputs support planning exploration, not clinical, engineering or live operational decisions; real use needs
  validated local data and expert review.
- The Resilience Index is a transparent planning index, not a validated safety score.
