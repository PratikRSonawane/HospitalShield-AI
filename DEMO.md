# Demo script — HospitalShield AI

Rehearse on the actual presentation machine and network. Backup: Demo Mode (▶ button, top right) runs the
same sequence with guided annotations; if the backend is unreachable it plays from precomputed data.

## 3-minute demo

| Time | What to show |
|---|---|
| 0:00–0:30 | **The planner's question.** "A 72-hour heatwave is forecast with a grid outage. Which constraints appear, and which intervention actually helps?" Show the Overview: the SYNTHETIC badge, the KPI cards (Resilience Index 63.7, ICU at 100%, 48 hours of power deficit), the hospital map with every unit green at hour 0. Say plainly: *synthetic baseline, planning prototype — the numbers you'll see are computed, none are typed in.* |
| 0:30–1:10 | **Run the scenario.** Drag the map's scrubber to hour 30: Generator amber (running), Grid down, ward and ICU flip to WARN/CRITICAL with icon + text. Point at the power chart: deficit shading from hour 24. Open the alerts panel: click the R09 fuel_exhausted alert — show rule id, threshold, observed peak, hour range. Every alert highlights its hours on every chart. |
| 1:10–1:50 | **Failure points.** Open Failure Points & Plan: the first failure (ICU, hour 16), the cascade chain (fuel → power → critical at risk → ED/ICU derate → beds), the binding-constraint ribbon walking power → staff → beds. |
| 1:50–2:30 | **The planner.** Scenario Lab → "Find optimal action sequence". ~10 seconds later: fuel resupply 2016 L requested at hour 0 (effective hour 12 — lead time as the pale bar) plus 2 nurses ED→ICU, +8.7 resilience marginal gain. References at the foot of the card: no-action 63.7, everything-at-hour-0 81.2, reverse 81.2 — order and timing matter and the app quantifies it. **Apply plan → Compare.** |
| 2:30–3:00 | **The measured after.** Compare Runs: resilience 63.7 → 81.2 (+17.5, +27.5%), overflow patient-hours 638 → 252, energy unserved 8,892 → 4,314 kWh, with per-intervention attribution and "why it changed" templates. Close on Assumptions & Data: **Bring your own hospital** — download the template, upload your site, and this twin runs on your hospital. Then the limitations paragraph — be upfront; it earns trust. |

Numbers quoted are from the committed configuration (seed 42, deterministic); re-verify on the demo machine
with `python backend/scripts/generate_demo_snapshots.py` if anything was recalibrated.

## 60-second backup

Demo Mode on precomputed data: scenario → one alert with its rule trace → one comparison with deltas →
limitations. If asked "is this real data?": *"No — synthetic by design and labelled everywhere. The engine
accepts your hospital's configuration; the calibration path to NHS England and MIMIC-IV aggregates is in the
repo."*

## Questions we expect

- **Why should we trust the numbers?** Every value is computed by one deterministic engine with enforced
  conservation laws (patient, staff, power, fuel, supplies); identical inputs give byte-identical outputs;
  1,133 tests including a 1,008-cell scenario matrix back it. The synthetic *parameters* are labelled, not
  the computations.
- **How does it know power derates beds?** An explicit, documented coupling table (docs/equations.md) —
  scenario assumptions, visible in the UI, debatable by design.
- **Can this run on our hospital?** Yes — that's the upload feature. Schema in `data/hospital_template.json`,
  validation with per-field reasons, sanity check on upload.
- **What's the planner's "optimal"?** "Best found within budget" by deterministic beam search — a planning
  aid, never a proof of optimality. It says so on the card.

## Pre-flight checklist

- [ ] Backend starts clean (`uvicorn app.main:app --port 8000`), `/health` returns 200
- [ ] Frontend dev server or `npm run preview` serves the built bundle
- [ ] Overview auto-run completes; KPIs populate
- [ ] Planner returns a plan within ~10 s on the demo machine
- [ ] Offline fallback verified once with the backend stopped
- [ ] Print stylesheet renders the summary legibly (Ctrl+P on Compare)
