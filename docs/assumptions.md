# Assumptions, calibration and decisions

Every number in this project is a **configuration input with a label**. Nothing here is measured from a real
hospital. The baseline is `data/demo_hospital.json` (SYNTHETIC), tuned so the acceptance criteria in
`backend/tests/test_calibration.py` hold. Scenario multipliers are **SCENARIO ASSUMPTIONS** — planning
assumptions, never empirical relationships.

## Calibration criteria (B10) and why each value is what it is

The engine is calibrated against four acceptance tests, all executed in the suite:

1. **Normal operations is a steady state.** Ward/ICU occupancy stays within ±5 pp of its initial value over
   72 h, no high/critical alerts, zero power deficit.
2. **Heatwave stress is meaningful but survivable.** Peak ward *or* ICU occupancy reaches ≥ 90%, with real
   overflow, and the documented intervention set measurably improves overflow patient-hours and hours above
   threshold without eliminating every problem.
3. **The outage bites.** Hours of power deficit plus a fuel-exhaustion or critical-risk event; load shedding
   alone reduces but does not remove the deficit; the combined plan beats any single intervention.
4. **The flood isolates.** Supply cover drops below the low-cover threshold or a staffing shortfall appears
   in the first half of the horizon; recall + resupply + reallocation measurably improves the Resilience
   Index; resupply requested *before* the access window outperforms one requested inside it.

### Arrivals and ED

| Parameter | Value | Unit | Rationale |
|---|---|---|---|
| `arrivals.baseline_per_hour` | 5.6 | patients/h | Mean 24-hour arrival rate. Kept below ED throughput (bays ÷ LOS = 6.5/h) so normal operations drains its own diurnal peak instead of accumulating a queue. |
| `arrivals.diurnal_profile` | 24 factors, mean 1.0, peak 1.20 at 15:00 | factor | Cosine profile peaking mid-afternoon. Amplitude chosen so the peak arrival rate stays close enough to throughput that queues drain overnight (peak waiting 1 in normal ops). |
| `ed.bays` | 26 | bays | Throughput anchor: 26 ÷ 4 h LOS = 6.5 patients/h, ~16% above the mean arrival rate. |
| `ed.los_hours` | 4.0 | hours | Typical ED length of stay for a mixed department; sets the completion rate 1/LOS. |
| `arrivals.p_admit_ward` | 0.13 | fraction | Admission split calibrated so the ward equilibrates at its initial occupancy: 5.6 × 0.13 × 108 h ≈ 79 beds. |
| `arrivals.p_admit_icu` | 0.026 | fraction | Same for the ICU: 5.6 × 0.026 × 96 h ≈ 14 beds. |

### Ward and ICU

| Parameter | Value | Unit | Rationale |
|---|---|---|---|
| `ward.beds` | 100 | beds | Mid-size general ward. |
| `ward.nurse_roster` | 18 | nurses | With ratio 1:6, staffed capacity is 108 ≥ beds, so staffing binds only under absence. |
| `ward.alos_hours` | 108 | hours | ~4.5-day average stay; discharge rate 1/ALOS. |
| `ward.initial_occupied` | 80 | beds | 80% starting occupancy; the steady-state target of the admission split. |
| `ward.surge_beds_available` | 15 | beds | Surge ceiling; usable only when staffed *and* powered (the coupling the planner exploits). |
| `icu.beds` | 20 | beds | 20-bed ICU. |
| `icu.nurse_roster` | 9 | nurses | With ratio 1:2, staffed capacity 18 < 20 beds: staffing is the ICU's binding constraint, deliberately. |
| `icu.alos_hours` / `initial_occupied` | 96 h / 14 | hours / beds | 70% starting occupancy matching the admission split equilibrium. |
| `icu.surge_beds_available` | 4 | beds | Small surge pool; opening beds without staff does nothing (by design). |

### Power, cooling and fuel

| Parameter | Value | Unit | Rationale |
|---|---|---|---|
| `grid_capacity_kw` | 450 | kW | Sized so a normal day (≈ 400 kW peak) keeps reserve, but a heatwave (cooling +10 °C) erodes it and an outage forces generator use. |
| `critical_load_kw` / `noncritical_load_kw` | 220 / 130 | kW | Operational split; critical load is never shed (rule 4 of the spec). |
| `cooling_base_kw`, threshold 28 °C, 4 kW/°C | 50 / — / 4 | kW / °C / kW/°C | Linear heat-to-cooling-load slope above 28 °C — a **scenario assumption**, not an engineering curve. |
| `cooling_critical_fraction` | 0.5 | fraction | Half of cooling load is treated as critical (server/equipment side), half comfort. |
| `generator_capacity_kw` | 300 | kW | Deliberately below peak heatwave demand (≈ 460 kW): outages produce a deficit even with fuel, which is the story B10 asks for. |
| `fuel_litres` | 2500 | litres | Sized so a 36-hour full outage exhausts fuel mid-run (~ hour 48) unless resupplied. |
| `fuel_l_per_kwh` | 0.28 | litres/kWh | Typical diesel specific consumption. |
| `max_shed_fraction_of_noncritical` | 0.4 | fraction | Cap on discretionary load shedding; comfort impact only, never clinical. |
| `power_derate_factor_when_critical_at_risk` | 0.85 | fraction | ED/ICU usable-bed derate when critical load is at risk (cascade coupling; scenario assumption). |

### Staff, recall and reallocation

| Parameter | Value | Unit | Rationale |
|---|---|---|---|
| `staffing.max_reallocation_fraction_of_source` | 0.2 | fraction | At most 20% of a unit's roster may move out. |
| `staffing.min_source_floor_fraction` | 0.8 | fraction | Source unit keeps ≥ 80% of roster and at least its required nurses. |
| `recall.max_fraction_of_roster` | 0.15 | fraction | Off-duty recall cap per unit. |
| `recall.lead_time_hours` | 4 | hours | Time for recalled staff to arrive; scaled by staff access at the arrival hour. |

### Supplies

| Parameter | Value | Unit | Rationale |
|---|---|---|---|
| items `oxygen`, `essential_meds`; rate 1.0 unit/weighted-bed-hour | — | units | Consumption is tied to weighted occupancy (ward + 2×ICU + 0.5×ED). |
| `initial_cover_hours` | 36 | hours | 36 h of cover at baseline consumption: comfortable normally, drawn below the 24 h threshold by the flood window. |
| `scheduled_resupply_fraction` | 1.0 | fraction | Deliveries match baseline consumption; the access window scales them down. |
| `stockout_derate_factor` | 0.8 | fraction | ED/ICU usable-bed derate during a stockout (scenario assumption). |
| `emergency_resupply_max_cover_hours` / lead 12 h | 24 / 12 | hours | Emergency delivery cap and lead time; the lead time is what makes *when you ask* matter. |

### Scenario presets (see `data/scenario_presets.json`)

| Preset | Key settings | Why |
|---|---|---|
| `normal_operations` | baseline arrivals, full grid, 30 °C day | Control run; proves the steady state. |
| `heatwave_power_stress` | +15% arrivals, ×1.5 LOS, 10% staff absent, grid at 80%, 41 °C | Heat drives demand and admissions; no outage yet. The ×1.5 LOS is the load-bearing assumption that saturates ward/ICU within 72 h and creates fixable boarding. |
| `heatwave_power_outage` | stress + grid 0% for 36 h from hour 24, 43 °C | Generator < demand → deficit; fuel exhausts ~ hour 48 → critical load at risk → ED/ICU derate cascade. |
| `flood_storm_access` | access window h18–42: 60% staff access, 15% deliveries, ×1.4 storm arrivals; generator plant at 60%; 90% humidity | A forecast storm gives 18 h of warning — enough for the resupply-before-the-window sequencing story. |

### Resilience Index weights

`occupancy 0.22, overflow 0.22, staffing 0.13, power_deficit 0.18, critical_risk 0.13, supply 0.12` —
they sum to 1.0 and encode a planning view that occupancy strain and patient overflow dominate, with power
deficit next. The formula and normalisation are in `docs/equations.md` and the UI; it is a transparent
planning index, not a validated safety score.

## Decisions

Ambiguities in the source problem were resolved conservatively and recorded here:

- **ED starting occupancy** is the steady-state estimate `min(bays, baseline_per_hour × LOS)`; ward and ICU start
  from their configured `initial_occupied`.
- **Supply consumption is capped at availability.** The spec's stock identity (`stock change = deliveries −
  consumption`) holds exactly while stock > 0; at stockout, served consumption is capped at what exists, the
  shortfall is reported as `unmet`, and stock never goes negative.
- **Recall scaling is decided once**, at the arrival hour: `floor(nurses × staff_access_fraction(arrival_hour))`.
  An integer result keeps nurse counts exact.
- **Emergency fuel cap** is `max_cover_hours × generator_capacity × litres_per_kWh` (24 h at full generator
  burn) rather than current burn, because current burn can be zero at request time and the cap must be
  deterministic at validation time.
- **Stochastic mode** consumes randomness only through Poisson arrivals, Binomial service completions and
  multinomial cohort splits, all from a local `numpy Generator(PCG64(seed))`. Deterministic mode consumes none.
- **Scenario presets are merged server-side**: POSTing only `{"scenario": "heatwave_power_outage"}` applies the
  documented preset, and explicit request fields override it. The UI and the raw API therefore agree.
- **Excess over usable beds is never hidden**: patients are never ejected; the gap is reported as
  `beds_over_usable` and blocks admissions to that unit.
- **Run history and the weather cache** are best-effort SQLite stores; failures log a warning and never block a
  simulation.

## Verification

`backend/tests/test_calibration.py` asserts every criterion above against the committed configuration, and
`backend/tests/golden/` snapshots the four presets' summaries, alerts and failure points so any drift fails CI.
