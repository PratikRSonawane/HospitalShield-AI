"""Summary metrics (B7) including the transparent Resilience Index.

All values are CALCULATED from the hourly series. The Resilience Index is
100 minus weighted normalised penalties; it is a planning index, not a
validated safety score (formula shown in docs/equations.md and the UI).
"""

from __future__ import annotations

import math
from typing import Any


def _pct_list(rows: list[dict[str, Any]], unit: str) -> list[float]:
    return [r["units"][unit]["occupancy_pct"] for r in rows if r["units"][unit]["occupancy_pct"] is not None]


def compute_metrics(cfg: Any, duration_hours: int, rows: list[dict[str, Any]],
                    summary_extras: dict[str, Any] | None = None) -> dict[str, Any]:
    """All B7 metrics from the hourly rows."""
    occ_ward = _pct_list(rows, "ward")
    occ_icu = _pct_list(rows, "icu")
    occ_ed = _pct_list(rows, "ed")

    hours_ward_above = sum(1 for r in rows if r["units"]["ward"]["occupancy_pct"] is not None
                           and r["units"]["ward"]["occupancy_pct"] >= cfg.thresholds.occupancy_warn_pct)
    hours_icu_above = sum(1 for r in rows if r["units"]["icu"]["occupancy_pct"] is not None
                          and r["units"]["icu"]["occupancy_pct"] >= cfg.thresholds.occupancy_warn_pct)

    overflow_patient_hours = sum(r["ed"]["waiting"] + r["ed"]["boarding_ward"] + r["ed"]["boarding_icu"] for r in rows)
    staff_shortfall_nurse_hours = sum(r["staffing"][u]["shortfall"] for r in rows for u in ("ed", "ward", "icu"))
    hours_beds_over_usable = sum(1 for r in rows for u in ("ed", "ward", "icu") if r["units"][u]["beds_over_usable"] > 0)

    hours_power_deficit = sum(1 for r in rows if r["power"]["deficit_kw"] > 0)
    peak_deficit = max((r["power"]["deficit_kw"] for r in rows), default=0.0)
    energy_unserved_kwh = sum(r["power"]["deficit_kw"] for r in rows)
    min_reserve = min((r["power"]["reserve_kw"] for r in rows), default=0.0)
    hours_critical_risk = sum(1 for r in rows if r["power"]["critical_at_risk_kw"] > 0)

    fuel_remaining_l = rows[-1]["power"]["fuel_l"] if rows else cfg.power.fuel_litres
    hours_to_fuel_exhaustion = next((r["hour"] for r in rows if r["power"]["fuel_l"] <= 0), None)

    min_cover: dict[str, float | None] = {}
    hours_stockout: dict[str, int] = {}
    for item in cfg.supplies.items:
        covers = [r["supply"]["cover_hours"].get(item) for r in rows]
        numeric = [c for c in covers if c is not None]
        min_cover[item] = min(numeric) if numeric else None
        hours_stockout[item] = sum(1 for r in rows if r["supply"]["stockout"].get(item))

    metrics: dict[str, Any] = {
        "peak_ward_occupancy_pct": round(max(occ_ward), 2) if occ_ward else None,
        "peak_icu_occupancy_pct": round(max(occ_icu), 2) if occ_icu else None,
        "peak_ed_occupancy_pct": round(max(occ_ed), 2) if occ_ed else None,
        "hours_ward_above_threshold": hours_ward_above,
        "hours_icu_above_threshold": hours_icu_above,
        "peak_ed_waiting": max((r["ed"]["waiting"] for r in rows), default=0),
        "peak_ed_boarding": max((r["ed"]["boarding_ward"] + r["ed"]["boarding_icu"] for r in rows), default=0),
        "overflow_patient_hours": overflow_patient_hours,
        "staff_shortfall_nurse_hours": staff_shortfall_nurse_hours,
        "hours_beds_over_usable": hours_beds_over_usable,
        "peak_power_demand_kw": round(max((r["power"]["demand_kw"] for r in rows), default=0.0), 2),
        "hours_power_deficit": hours_power_deficit,
        "peak_power_deficit_kw": round(peak_deficit, 2),
        "energy_unserved_kwh": round(energy_unserved_kwh, 2),
        "min_power_reserve_kw": round(min_reserve, 2),
        "hours_critical_load_at_risk": hours_critical_risk,
        "fuel_remaining_l": round(fuel_remaining_l, 2),
        "hours_to_fuel_exhaustion": hours_to_fuel_exhaustion,
        "min_supply_cover_hours": {k: (round(v, 2) if v is not None else None) for k, v in min_cover.items()},
        "hours_supply_stockout": hours_stockout,
        "resilience_index": compute_resilience_index(cfg, duration_hours, rows),
    }
    if summary_extras:
        metrics.update(summary_extras)
    return metrics


def compute_resilience_index(cfg: Any, duration_hours: int, rows: list[dict[str, Any]]) -> float:
    """Resilience Index = 100 - weighted normalised penalties, clamped 0-100.

    Penalties over the horizon T (normalised to 0-1):
      occupancy   (hours ward above threshold + hours ICU above threshold) / (2T)
      overflow    overflow patient-hours / (T * ED bays)
      staffing    nurse shortfall hours / (T * total roster)
      power       hours power deficit / T
      critical    hours critical load at risk / T
      supply      sum of per-item stockout hours / (T * number of items)
    """
    if duration_hours <= 0 or not rows:
        return 100.0
    t = duration_hours
    w = cfg.resilience_weights

    hours_ward_above = sum(1 for r in rows if r["units"]["ward"]["occupancy_pct"] is not None
                           and r["units"]["ward"]["occupancy_pct"] >= cfg.thresholds.occupancy_warn_pct)
    hours_icu_above = sum(1 for r in rows if r["units"]["icu"]["occupancy_pct"] is not None
                          and r["units"]["icu"]["occupancy_pct"] >= cfg.thresholds.occupancy_warn_pct)
    p_occ = (hours_ward_above + hours_icu_above) / (2.0 * t)

    overflow = sum(r["ed"]["waiting"] + r["ed"]["boarding_ward"] + r["ed"]["boarding_icu"] for r in rows)
    p_overflow = overflow / (t * max(1, cfg.ed.bays))

    shortfall = sum(r["staffing"][u]["shortfall"] for r in rows for u in ("ed", "ward", "icu"))
    total_roster = cfg.ed.nurse_roster + cfg.ward.nurse_roster + cfg.icu.nurse_roster
    p_staff = shortfall / (t * max(1, total_roster))

    p_power = sum(1 for r in rows if r["power"]["deficit_kw"] > 0) / t
    p_critical = sum(1 for r in rows if r["power"]["critical_at_risk_kw"] > 0) / t

    stockout_hours = sum(r["supply"]["stockout"].get(item, False) for r in rows for item in cfg.supplies.items)
    n_items = max(1, len(cfg.supplies.items))
    p_supply = stockout_hours / (t * n_items)

    penalty = (w.occupancy * p_occ + w.overflow * p_overflow + w.staffing * p_staff
               + w.power_deficit * p_power + w.critical_risk * p_critical + w.supply * p_supply)
    index = 100.0 * (1.0 - float(penalty))
    if not math.isfinite(index):  # defensive; inputs are validated upstream
        return 0.0
    return float(round(min(100.0, max(0.0, index)), 2))
