"""Pure simulation engine (B3): run(config, scenario, interventions) -> result.

No web framework, no file or network IO, no global state, no wall-clock
time. The hourly loop follows the B3 step order exactly. Deterministic mode
consumes no randomness; stochastic mode uses a local seeded PCG64 generator.
"""

from __future__ import annotations

import math
from typing import Any

from .alerts import build_alert_episodes
from .config import HospitalConfig
from .failure_points import analyze_failure_points, binding_constraint, hourly_margins
from .flow import StochasticFlows
from .interventions import InterventionsSpec, ed_in_service_estimate, validate_feasible, weighted_occupied_baseline
from .invariants import verify_row_invariants, verify_series_invariants
from .metrics import compute_metrics
from .patient_flow import FlowAccumulators, step_patient_flow
from .power import compute_power
from .result import SimulationResult, input_hash_for, run_id_for
from .scenario import (
    ScenarioSpec,
    arrival_multiplier_at,
    delivery_fraction_at,
    grid_fraction_at,
    staff_access_fraction_at,
    temperature_series,
)
from .state import EdState, RunState, make_unit_row
from .supplies import compute_supplies, scheduled_delivery_rate
from .timeline import InterventionTimeline

UNITS = ("ed", "ward", "icu")


def run(cfg: HospitalConfig, scenario: ScenarioSpec, interventions: InterventionsSpec | None = None,
        seed: int | None = None, stochastic: bool | None = None,
        skip_feasibility: bool = False) -> SimulationResult:
    """Run one simulation; returns the full SimulationResult.

    ``seed``/``stochastic`` default to the values in ``scenario``. The
    feasibility validator runs here too so the engine can never be driven
    with infeasible interventions (the planner uses the same gate).
    """
    spec_interventions = interventions or InterventionsSpec()
    if not skip_feasibility:
        validate_feasible(spec_interventions, cfg, scenario)
    seed = scenario.seed if seed is None else seed
    stochastic = scenario.stochastic if stochastic is None else stochastic
    scenario_dict = _scenario_to_dict(cfg, scenario, spec_interventions, seed, stochastic)

    t = scenario.duration_hours
    temps = temperature_series(scenario)
    rng = StochasticFlows(seed) if stochastic else None
    acc = FlowAccumulators()
    timeline = InterventionTimeline(spec_interventions, cfg, scenario)

    weighted_base = weighted_occupied_baseline(cfg)
    stock0 = {item: cfg.supplies.initial_cover_hours * cfg.supplies.units_per_weighted_bed_hour.get(item, 0.0) * weighted_base
              for item in cfg.supplies.items}
    ed0 = EdState(in_service=ed_in_service_estimate(cfg))
    state = RunState(ward_occupied=cfg.ward.initial_occupied, icu_occupied=cfg.icu.initial_occupied,
                     fuel_l=cfg.power.fuel_litres, stock=stock0, ed=ed0,
                     arrived_total=cfg.ward.initial_occupied + cfg.icu.initial_occupied + ed0.occupied_bays)
    rows: list[dict[str, Any]] = []

    for h in range(t):
        stock_before = dict(state.stock)
        row, state = _step(cfg, scenario, timeline, state, h, temps[h], rng, acc)
        verify_row_invariants(row, cfg, state.arrived_total, state.discharged_total, stock_before)
        rows.append(row)

    verify_series_invariants(rows, cfg, set(timeline.resupply_hours))
    alerts = build_alert_episodes(cfg, rows)
    failure_points, summary_extras = analyze_failure_points(rows, alerts)
    summary = compute_metrics(cfg, t, rows, summary_extras)

    return SimulationResult(
        scenario=scenario_dict, series=rows, summary=summary, alerts=alerts,
        failure_points=failure_points, seed=seed, stochastic=stochastic,
        input_hash=input_hash_for(scenario_dict), run_id=run_id_for(scenario_dict),
    )


def _step(cfg: HospitalConfig, scenario: ScenarioSpec, timeline: InterventionTimeline,
          state: RunState, h: int, temperature_c: float, rng: StochasticFlows | None,
          acc: FlowAccumulators) -> tuple[dict[str, Any], RunState]:
    """One hourly step in exact B3 order; returns (row, updated state)."""
    # 1. weather-derived fractions
    access = staff_access_fraction_at(scenario, h)
    dfrac = delivery_fraction_at(scenario, h)
    amult = arrival_multiplier_at(scenario, h)
    gfrac = grid_fraction_at(scenario, h)

    # 3. active interventions
    active = timeline.at(h)
    surge_open = active["surge_open"]

    # 4. power
    power = compute_power(cfg, h, temperature_c, sum(surge_open.values()), active["shed_kw"],
                          gfrac, scenario.backup.generator_availability_fraction,
                          state.fuel_l, active["fuel_resupply_l"])
    state.fuel_l = power.fuel_l

    # 5. staffing (occupied_prev = start-of-hour occupancy)
    occupied_prev = {"ed": state.ed.occupied_bays, "ward": state.ward_occupied, "icu": state.icu_occupied}
    staff = compute_staff(cfg, scenario, access, occupied_prev, active)

    # 6. supplies
    weighted_prev = state.weighted_occupied(cfg.supplies.icu_weight, cfg.supplies.ed_weight)
    supplies = compute_supplies(cfg, state.stock, weighted_prev, dfrac, active["item_resupply"])
    state.stock = supplies.stock

    # 7. usable beds
    physical = {"ed": cfg.ed.bays, "ward": cfg.ward.beds, "icu": cfg.icu.beds}
    open_beds = {u: physical[u] + surge_open.get(u, 0) for u in UNITS}
    usable = {u: min(open_beds[u], staff.staffed_capacity[u]) for u in UNITS}
    if power.critical_at_risk_kw > 0:
        for u in ("ed", "icu"):
            usable[u] = int(math.floor(usable[u] * cfg.power.power_derate_factor_when_critical_at_risk))
    if any(supplies.stockout.values()):
        for u in ("ed", "icu"):
            usable[u] = int(math.floor(usable[u] * cfg.supplies.stockout_derate_factor))
    # Occupied patients are never ejected (B3 step 7); any excess above
    # usable is recorded per-unit as beds_over_usable and blocks admissions.

    # 8. patient flow
    arrivals_expected = cfg.arrivals.baseline_per_hour * cfg.arrivals.diurnal_profile[h % 24] * amult
    flow = step_patient_flow(cfg, state.ed, state.ward_occupied, state.icu_occupied,
                             usable["ed"], usable["ward"], usable["icu"],
                             arrivals_expected, scenario.stress.los_multiplier, acc, rng)
    state.ward_occupied = flow.ward_occupied
    state.icu_occupied = flow.icu_occupied
    state.arrived_total += flow.arrivals
    state.discharged_total += flow.discharged

    row = _build_row(cfg, h, temperature_c, gfrac, access, dfrac, amult, power, staff,
                     supplies, open_beds, usable, state, flow, surge_open)
    return row, state


def compute_staff(cfg: HospitalConfig, scenario: ScenarioSpec, access: float,
                  occupied_prev: dict[str, int], active: dict[str, Any]) -> Any:
    """Staffing step wrapper (B3 step 5) kept on the engine for import economy."""
    from .staffing import compute_staffing
    return compute_staffing(cfg, scenario.stress.staff_availability_fraction, access,
                            occupied_prev, active["net_reallocation"], active["recalled"])


def _build_row(cfg: HospitalConfig, h: int, temperature_c: float, gfrac: float, access: float,
               dfrac: float, amult: float, power: Any, staff: Any, supplies: Any,
               open_beds: dict[str, int], usable: dict[str, int], state: RunState,
               flow: Any, surge_open: dict[str, int]) -> dict[str, Any]:
    """Assemble the hourly row (B3 step 9) with backend-computed statuses."""
    occupied_end = {"ed": state.ed.occupied_bays, "ward": state.ward_occupied, "icu": state.icu_occupied}
    units = {u: make_unit_row(open_beds[u], usable[u], occupied_end[u]) for u in UNITS}
    staffing = {u: {"available": staff.available[u], "staffed_capacity": staff.staffed_capacity[u],
                    "required": staff.required[u], "shortfall": staff.shortfall[u]} for u in UNITS}
    supply_view = _supply_view(cfg, power, supplies)
    margins = hourly_margins({"units": units, "power": _power_dict(power), "staffing": staffing, "supply": supply_view, "ed": _ed_dict(state, flow)})

    return {
        "hour": h,
        "temperature_c": temperature_c,
        "weather": {"temperature_c": temperature_c},
        "grid_fraction": gfrac,
        "access": {"staff_access_fraction": access, "delivery_fraction": dfrac, "arrival_multiplier": amult},
        "power": _power_dict(power),
        "staffing": staffing,
        "supplies": {item: {"stock": round(supplies.stock[item], 4),
                            "delivered": round(supplies.delivered[item], 4),
                            "consumption": round(supplies.consumption[item], 4),
                            "unmet": round(supplies.unmet[item], 4),
                            "cover_hours": (round(supplies.cover_hours[item], 4)
                                            if supplies.cover_hours[item] is not None else None),
                            "stockout": supplies.stockout[item]} for item in cfg.supplies.items},
        "units": units,
        "ed": _ed_dict(state, flow),
        "discharged": flow.discharged,
        "surge_open": dict(surge_open),
        "supply": supply_view,
        "margins": {k: round(v, 4) for k, v in margins.items()},
        "binding_constraint": binding_constraint(margins),
    }


def _power_dict(power: Any) -> dict[str, float | None]:
    return {
        "critical_demand_kw": power.critical_demand_kw, "noncritical_unshed_kw": power.noncritical_unshed_kw,
        "shed_kw": power.shed_kw, "demand_kw": power.demand_kw, "grid_supply_kw": power.grid_supply_kw,
        "gen_available_kw": power.gen_available_kw, "gen_output_kw": power.gen_output_kw,
        "available_supply_kw": power.available_supply_kw, "deficit_kw": power.deficit_kw,
        "reserve_kw": power.reserve_kw, "critical_at_risk_kw": power.critical_at_risk_kw,
        "fuel_l": power.fuel_l,
    }


def _ed_dict(state: RunState, flow: Any) -> dict[str, int]:
    return {
        "waiting": state.ed.waiting, "in_service": state.ed.total_in_service,
        "boarding_ward": state.ed.boarding_ward, "boarding_icu": state.ed.boarding_icu,
        "arrivals": flow.arrivals, "admitted_ward": flow.admitted_ward, "admitted_icu": flow.admitted_icu,
    }


def _supply_view(cfg: HospitalConfig, power: Any, supplies: Any) -> dict[str, Any]:
    """Derived supply/power status values used by alerts and margins."""
    full_burn_kw = cfg.power.generator_capacity_kw
    fuel_hours = power.fuel_l / (full_burn_kw * cfg.power.fuel_l_per_kwh) if full_burn_kw > 0 else None
    reserve_pct = (100.0 * power.reserve_kw / power.available_supply_kw) if power.available_supply_kw > 0 else None
    supply_low = any(c is not None and c < cfg.supplies.low_cover_hours for c in supplies.cover_hours.values())
    return {
        "fuel_hours": round(fuel_hours, 4) if fuel_hours is not None else None,
        "fuel_low_hours": cfg.thresholds.fuel_low_hours,
        "reserve_pct": round(reserve_pct, 4) if reserve_pct is not None else None,
        "reserve_low_pct": cfg.thresholds.reserve_low_pct,
        "cover_hours": {k: (round(v, 4) if v is not None else None) for k, v in supplies.cover_hours.items()},
        "low_cover_hours": cfg.supplies.low_cover_hours,
        "supply_low": supply_low,
        "stockout": dict(supplies.stockout),
        "ed_boarding_warn": cfg.thresholds.ed_boarding_warn,
        "ed_waiting_high": cfg.thresholds.ed_waiting_high,
        "scheduled_delivery_rate": {item: round(scheduled_delivery_rate(cfg, item, cfg.ward.initial_occupied
                                                                      + cfg.icu.initial_occupied * cfg.supplies.icu_weight
                                                                      + ed_in_service_estimate(cfg) * cfg.supplies.ed_weight), 4)
                                    for item in cfg.supplies.items},
    }


def _scenario_to_dict(cfg: HospitalConfig, scenario: ScenarioSpec, interventions: InterventionsSpec,
                      seed: int, stochastic: bool) -> dict[str, Any]:
    """Canonical scenario dict used for the input hash and run id."""
    from dataclasses import asdict
    d = asdict(scenario)
    d["seed"] = seed
    d["stochastic"] = stochastic
    d["interventions"] = asdict(interventions)
    d["hospital"] = cfg.hospital_name
    return d
