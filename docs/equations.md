# Equations, step order and invariants

The engine (`backend/app/simulation/`) is a pure module: no IO, no globals, no wall clock. One run is a loop
over hours `h = 0..T-1` that follows a fixed step order; every number below is computed there and nowhere else.

## Notation

- `T` = duration in hours (1..72). Time is an integer hour index; one step = one hour.
- Units follow field suffixes: `_pct` 0–100, `_fraction` 0–1, `_kw` kilowatts, `_kwh` kilowatt-hours,
  `_l` litres, `_c` Celsius, `_hours` hours. Percentages and fractions are never mixed.
- Division by zero returns `null`/an explicit unavailable state, never NaN.

## B3 hourly step order (implemented exactly)

1. **Weather and access.** `temperature_c[h]` from the diurnal sine (min → max, peak 15:00) or a provided
   series. From the flood/storm access window: `staff_access_fraction(h)`, `delivery_fraction(h)`,
   `arrival_multiplier(h)` — all 1.0 outside the window.
2. **Cooling.** `cooling_kw = cooling_base_kw + cooling_kw_per_deg_c_above × max(0, temperature_c −
   cooling_threshold_c)`, split by `cooling_critical_fraction` into critical and non-critical cooling.
3. **Active interventions** for the hour. Surge beds open only from `start_hour + activation_delay_hours`.
4. **Power.**
   - `critical_demand_kw = critical_load_kw + critical_cooling + surge_open × surge_bed_kw`
   - `noncritical_unshed_kw = noncritical_load_kw × diurnal[h] + noncritical_cooling`
   - `shed_kw = min(requested_kw, max_shed_fraction × noncritical_unshed, noncritical_unshed)`
   - `demand_kw = critical_demand_kw + noncritical_unshed_kw − shed_kw`
   - `grid_supply_kw = grid_capacity_kw × grid_fraction(h)`
   - `gen_available_kw = min(generator_capacity × availability_fraction, fuel_l ÷ fuel_l_per_kwh)`
   - `available_supply_kw = grid_supply_kw + gen_available_kw`
   - `deficit_kw = max(0, demand − available_supply)`; `reserve_kw = max(0, available_supply − demand)`
   - `critical_at_risk_kw = max(0, critical_demand − available_supply)` — critical demand is never reduced
   - generator output `= min(gen_available, max(0, demand − grid_supply))`; fuel falls by
     `output × fuel_l_per_kwh`, floored at 0. Emergency fuel resupply lands only after its lead time and is
     scaled by the delivery fraction at the arrival hour.
5. **Staffing** (per unit u ∈ {ed, ward, icu}, integer nurses):
   - `available[u] = floor(roster[u] × staff_availability × staff_access(h)) + net_reallocation[u] + recalled[u]`
   - `staffed_capacity[u] = floor(available[u] × patients_per_nurse[u])`
   - `required[u] = ceil(occupied_prev[u] ÷ patients_per_nurse[u])`; `shortfall[u] = max(0, required − available)`
6. **Supplies** (per item):
   - `weighted_occupied = ward_occupied + icu_occupied × icu_weight + ed_in_bays × ed_weight` (previous hour)
   - `consumption = weighted_occupied × units_per_weighted_bed_hour`
   - `delivered = scheduled_rate × delivery_fraction(h) + emergency_arriving(h)` where the scheduled rate is
     baseline consumption × `scheduled_resupply_fraction`
   - `served = min(consumption, stock + delivered)`; `stock ← stock + delivered − served` (never negative);
     unmet demand is reported, not hidden
   - `cover_hours = stock ÷ consumption` (null when consumption is 0); stockout when stock reaches 0 while
     consumption > 0
7. **Usable beds.** `open[u] = physical[u] + surge_open[u]`; `usable[u] = min(open[u], staffed_capacity[u])`.
   If `critical_at_risk_kw > 0`, ED and ICU usable are multiplied by
   `power_derate_factor_when_critical_at_risk`; if any item is in stockout, also by `stockout_derate_factor`.
   Occupied patients are never ejected: excess is reported as `beds_over_usable` and admissions to that unit
   stop for the hour.
8. **Patient flow** (integer patients; deterministic carry-forward rounding, or seeded Poisson/Binomial in
   stochastic mode):
   (a) arrivals join `ed_waiting`;
   (b) free ED bays (`usable_ed − occupied`) take waiting patients, split into non-admit / ward-admit /
       ICU-admit by `p_admit_*`;
   (c) each cohort completes service at rate `1/los_hours`; non-admits leave, admit cohorts move to
       `ed_boarding_ward` / `ed_boarding_icu` and keep holding a bay;
   (d) boarders enter ward/ICU while `usable − occupied > 0`;
   (e) ward and ICU discharge at rate `1/(alos_hours × los_multiplier)`.
9. **Record** the hourly row: state, power, staffing, supplies, per-unit status (`ok`/`warn`/`critical`/
   `unavailable`, computed by the backend), margins and the binding constraint.
10. **After the loop:** alert episodes (B8), summary metrics (B7), failure-point analysis (B11). Invariants are
    verified on every row; a violation raises (see below).

## Margins, binding constraint and failure points (B11)

Normalised margins (0–1; a zero denominator counts as zero margin):

- bed margin `= (usable − occupied) / usable` (min over ward, ICU)
- ED-flow margin `= (usable_ed − occupied_ed) / usable_ed`
- staffing margin `= (available − required) / required` (min over units)
- power margin `= min((supply − demand)/supply, (supply − critical_demand)/supply)` and fuel margin
  `min(1, fuel_hours / fuel_low_hours)`
- supply margin `= min(1, cover_hours / low_cover_hours)` (min over items)

`binding_constraint[h]` = the smallest margin, ties broken in the fixed order **power → supplies → staff →
beds → ed_flow**. A failure point is the first hour a margin reaches 0 or any alert R01–R11 reaches
high/critical, ranked by first hour then severity.

### Cascade coupling table

| Parent (earlier failure) | Coupling | Child |
|---|---|---|
| R06 critical load at risk | ED/ICU power derate shrinks usable beds | R01/R02 bed occupancy |
| R11 supply stockout | stockout derate shrinks usable beds | R01/R02 |
| R04 staffing shortfall | staffed capacity caps usable beds | R01/R02 |
| R01/R02 unit full | no admission path out of the ED | R03 ED boarding |
| R09 fuel exhausted | generator output → 0 | R05 power deficit |

A child episode counts as a cascade child when its parent rule failed earlier **and** the parent was active in
the preceding hour. Summary reports `root_failures` vs `cascade_children` counts and
`time_to_first_failure_hours`.

## Resilience Index (B7)

```
RI = 100 × (1 − Σ wᵢ · penaltyᵢ), clamped to 0..100
```

with weights from config (sum 1.0) and penalties normalised over the horizon `T`:

| component | penalty |
|---|---|
| occupancy | (hours ward above threshold + hours ICU above threshold) / (2T) |
| overflow | overflow patient-hours / (T × ED bays) |
| staffing | nurse shortfall hours / (T × total roster) |
| power_deficit | hours power deficit / T |
| critical_risk | hours critical load at risk / T |
| supply | Σ per-item stockout hours / (T × number of items) |

It is a transparent planning index for comparing runs — not a validated safety score.

## Invariants (B4), verified every hour

- No negative beds, staff, kW, litres or stock; no NaN/Infinity anywhere in a row.
- Percentages 0–100 (null when usable = 0); excess reported as `beds_over_usable`.
- `deficit_kw` and `reserve_kw` are never both positive.
- `shed_kw` never exceeds non-critical demand or the shed cap; critical demand is never reduced.
- Fuel is non-increasing except on resupply-arrival hours; generator output never exceeds capacity or fuel.
- **Exact integer patient conservation** every hour:
  `arrived_total = ed_waiting + ed_in_service + boarding_ward + boarding_icu + ward_occupied + icu_occupied + discharged_total`
  (initial occupants count as arrived at hour 0).
- **Staff conservation:** reallocation moves nurses between named units; the total is unchanged; the source
  keeps at least the floor fraction of its roster and its required nurses.
- **Supply identity:** `stock[h] − stock[h−1] = delivered − served` exactly (float tolerance 1e-4).

Violations raise `InvariantViolationError` — a bug, never user input.
