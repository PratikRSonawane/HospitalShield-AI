"""Deterministic template explainer (rule 5): rule-traced explanations built
only from metric names and values that exist in the results. Any LLM use is
optional and can never alter these computed values.
"""

from __future__ import annotations

from typing import Any


def _delta_phrase(metric: str, before: float, after: float, unit: str) -> str:
    """Human phrase for a before/after metric pair."""
    if after < before:
        return f"{metric} fell from {before} to {after} {unit}"
    if after > before:
        return f"{metric} rose from {before} to {after} {unit}"
    return f"{metric} stayed at {before} {unit}"


def explain_intervention(kind: str, detail: dict[str, Any], before: dict[str, Any],
                         after: dict[str, Any]) -> str:
    """One template explanation for one intervention, before vs after."""
    b, a = before["summary"], after["summary"]
    if kind == "activate_surge_beds":
        unit = detail.get("unit", "unit")
        beds = detail.get("beds", 0)
        hour = detail.get("effective_hour", detail.get("start_hour", 0))
        return (f"Surge beds raised {unit} open capacity by {beds} beds usable from hour {hour} "
                f"(rule: usable = min(open beds, staffed capacity)); "
                f"{_delta_phrase('overflow_patient_hours', b.get('overflow_patient_hours', 0), a.get('overflow_patient_hours', 0), 'patient-hours')}.")
    if kind == "reallocate_staff":
        return (f"Reallocating {detail.get('nurses', 0)} nurses from {detail.get('from_unit')} to "
                f"{detail.get('to_unit')} from hour {detail.get('start_hour', 0)} (rule: staffed capacity = "
                f"floor(available nurses x patients_per_nurse)); "
                f"{_delta_phrase('staff_shortfall_nurse_hours', b.get('staff_shortfall_nurse_hours', 0), a.get('staff_shortfall_nurse_hours', 0), 'nurse-hours')}.")
    if kind == "reduce_noncritical_load_kw":
        return (f"Shedding up to {detail.get('kw', 0)} kW of explicitly non-critical load from hour "
                f"{detail.get('start_hour', 0)} (comfort-impact note: non-clinical areas may lose comfort cooling; "
                f"critical load is never reduced); "
                f"{_delta_phrase('energy_unserved_kwh', b.get('energy_unserved_kwh', 0), a.get('energy_unserved_kwh', 0), 'kWh')}.")
    if kind == "recall_staff":
        return (f"Recalling {detail.get('nurses', 0)} off-duty nurses to {detail.get('unit')}, effective hour "
                f"{detail.get('effective_hour', detail.get('start_hour', 0))} after lead time (rule: recall cap "
                f"= max_fraction_of_roster x roster); "
                f"{_delta_phrase('staff_shortfall_nurse_hours', b.get('staff_shortfall_nurse_hours', 0), a.get('staff_shortfall_nurse_hours', 0), 'nurse-hours')}.")
    if kind == "emergency_resupply":
        what = ", ".join(filter(None, [
            f"{detail.get('fuel_l', 0)} L fuel" if detail.get("fuel_l") else None,
            *(f"{v} {k}" for k, v in dict(detail.get("items") or {}).items()),
        ])) or "supplies"
        cover_b = min((v for v in (b.get("min_supply_cover_hours") or {}).values() if v is not None), default=None)
        cover_a = min((v for v in (a.get("min_supply_cover_hours") or {}).values() if v is not None), default=None)
        return (f"Emergency resupply ({what}) arriving after lead time at hour "
                f"{detail.get('effective_hour', detail.get('start_hour', 0))}, scaled by delivery fraction; "
                f"min supply cover went from {cover_b} to {cover_a} hours "
                f"(rule: stock = max(0, stock + deliveries - consumption)).")
    return f"Intervention {kind} applied; see delta table."


def explain_comparison(baseline: dict[str, Any], treatment: dict[str, Any]) -> list[str]:
    """Overall explanation lines comparing baseline and intervention runs."""
    out: list[str] = []
    b, a = baseline["summary"], treatment["summary"]
    out.append(_delta_phrase("resilience_index", b.get("resilience_index", 0), a.get("resilience_index", 0), "index (0-100)"))
    out.append(_delta_phrase("overflow_patient_hours", b.get("overflow_patient_hours", 0), a.get("overflow_patient_hours", 0), "patient-hours"))
    out.append(_delta_phrase("hours_power_deficit", b.get("hours_power_deficit", 0), a.get("hours_power_deficit", 0), "hours"))
    out.append(_delta_phrase("energy_unserved_kwh", b.get("energy_unserved_kwh", 0), a.get("energy_unserved_kwh", 0), "kWh"))
    return out
