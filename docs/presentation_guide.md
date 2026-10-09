# HospitalShield AI: Presentation & Q&A Guide
**FUSION 2026 Hackathon — HC-03 Mayo Clinic Track**

---

## 1. Project Working Summary

**The Problem:**
Hospitals plan for climate disasters (heatwaves, floods) using static spreadsheets. These methods fail to
capture cascading failures — where an extreme weather event knocks out power, which disables cooling, which
forces ICU capacity down, causing patient backlogs in the Emergency Department (ED).

**The Solution: HospitalShield AI**
HospitalShield AI is a deterministic, climate-resilient hospital digital twin. It simulates how a disaster
cascades through a hospital's infrastructure hour by hour and generates an ordered action plan — what to do,
in what order, and when — with a measured before/after comparison for every claim.

### Key Technical Components
1. **Frontend (React + TypeScript + Vite):** A 6-page dashboard with a live SVG hospital map, time scrubber,
   traceable alerts, and a side-by-side comparison engine. Every displayed number comes from the backend.
2. **Backend engine (FastAPI + Python):** A pure deterministic simulator. It tracks power (kW), fuel (L),
   bed occupancy, staffing and supplies hourly over a 1–72-hour horizon, with conservation laws enforced and
   verified every hour.
3. **The planner (beam search):** When a disaster breaks the hospital, the planner evaluates feasible
   intervention paths — surge beds, emergency fuel, staff recall, load shedding, resupply — and scores them
   with the real engine, respecting lead times. It reports "best found within budget", never a proof of
   optimality.
4. **Hardened architecture:** 1,133 passing backend tests including a 1,008-cell scenario matrix, property
   tests for every conservation law, golden snapshots, ruff + strict mypy clean, Dockerized.
5. **Bring-your-own hospital:** upload your site's configuration (beds, staff ratios, generator, fuel,
   supplies) and the whole twin — scenarios, failure analysis, planner — runs on it. Optional calibration
   from NHS England open data or locally-aggregated MIMIC-IV.

---

## 2. Potential Judge Questions & Answers

### Innovation & Originality
**Q: How is this different from existing hospital planning software?**
**A:** Existing tools treat hospital units (ED, ward, power) as isolated silos. Ours is a constraint-coupled
digital twin: if the generator runs out of fuel, the engine propagates that failure into generator output,
then critical-power-at-risk, then ED/ICU capacity derates, then bed occupancy and ED boarding — and it shows
the cascade with rule-traced alerts. The planner then tells you which intervention, in what order, and when,
buys the most resilience back.

**Q: Why didn't you use a large language model for the planning?**
**A:** For critical infrastructure planning, invented numbers are unacceptable. The planner is a
deterministic beam search over the same engine that produces the dashboard numbers: same input, same plan,
every time. (An optional LLM layer could only ever *describe* computed results, never change them — that is
a hard rule in the codebase.)

### Technical Implementation
**Q: How does the planner work under the hood?**
**A:** Deterministic beam search within a stated budget (≤ 600 engine runs, 5 seconds). Each candidate
action is validated by the same feasibility rules the API enforces, then evaluated by running the real
engine with identical seed and weather. Candidates are scored `resilience_index − λ × burden`; the search
keeps the best 5 partial plans per round and reports reference plans (no action, everything at hour 0,
reverse order) so you can see whether order and timing actually mattered.

**Q: Is your data real Mayo Clinic data?**
**A:** No. All baseline data is deliberately SYNTHETIC and labelled as such on every screen. The model
encodes operational relationships (heat driving cooling load, staffing capping usable beds, fuel bounding
generator output) — the parameters are fictional starting points, documented with rationale in
docs/assumptions.md, and the whole point of the upload feature is that a real hospital swaps in its own.

**Q: How robust is the code? Did you test it?**
**A:** A 1,008-cell test matrix (4 scenarios × 3 stress levels × 7 intervention sets × 4 stochastic settings
× 3 durations), ~660 property-based cases asserting conservation laws hour by hour, calibration acceptance
tests for all four presets, golden snapshots, API contract tests — 1,133 backend tests, 92% coverage on the
engine package, ruff and strict mypy clean. docs/test-report.md has the executed numbers.

### Impact & Practicality
**Q: How would a real hospital actually adopt this?**
**A:** Assumptions & Data → "Bring your own hospital": download the template JSON, fill in physical beds,
surge beds, nurse rosters and patients-per-nurse ratios, the electrical split (grid, critical, non-critical,
generator, fuel), supply items and thresholds — then upload. The backend validates every field, runs a
24-hour sanity check, and stores it as a selectable profile. Calibration scripts can scale bed counts from
NHS England open data and derive length-of-stay aggregates from a hospital's own credentialed MIMIC-IV
extract (aggregates only, small cells suppressed). Expert review is required before real use — and we say so.

**Q: What is the "Resilience Index" metric?**
**A:** A transparent 0–100 planning index: 100 minus weighted, normalised penalties for hours above
occupancy thresholds, overflow patient-hours, nurse shortfall hours, power-deficit hours, critical-load-
at-risk hours and stockout hours. The weights and formula are published in the UI and docs/equations.md. It
exists so two plans can be compared honestly — it is explicitly not a validated safety score.

### UI & Presentation
**Q: What happens if the backend crashes or the network drops mid-demo?**
**A:** The frontend falls back to precomputed snapshots served with the app, banners itself "PRECOMPUTED —
backend unreachable", and disables editing rather than faking live results. The demo script has a 60-second
backup on exactly this path.

**Q: Why an SVG map instead of just charts?**
**A:** A command-center view that non-technical administrators read instantly. Status is colour + icon +
text (never colour alone), computed by the backend each hour, with a scrubber so you can literally watch the
grid link drop and the generator take the load.

### Honest limitations (say these before being asked)
- All baseline values are synthetic or operator-supplied; multipliers are scenario assumptions, not
  predictions.
- Power is an abstract operational constraint; no claim about real generator, ICU or life-support safety.
- Outputs support planning exploration only — not clinical, engineering-safety or live operational decisions.
- The planner's "optimal" means "best found within budget", a planning aid, not a proof.
