"""Comparison service (S4): baseline vs intervention from identical initial
state, seed and weather. Returns absolute and relative deltas for every
metric, an attribution table (each intervention alone plus the combined
plan) and rule-traced template explanations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.services.explainer import explain_comparison, explain_intervention
from app.simulation import HospitalConfig, InterventionsSpec, ScenarioSpec, run, validate_feasible

KEY_METRICS = ("resilience_index", "overflow_patient_hours", "hours_ward_above_threshold",
               "hours_icu_above_threshold", "peak_ed_waiting", "staff_shortfall_nurse_hours",
               "hours_power_deficit", "energy_unserved_kwh", "hours_critical_load_at_risk",
               "min_supply_cover_hours", "hours_to_fuel_exhaustion", "peak_power_deficit_kw")


def _single_interventions(spec: InterventionsSpec) -> list[tuple[str, dict[str, Any], InterventionsSpec]]:
    """Split a combined plan into one-intervention specs for attribution."""
    out: list[tuple[str, dict[str, Any], InterventionsSpec]] = []
    for act in spec.activate_surge_beds:
        d: dict[str, Any] = {"unit": act.unit, "beds": act.beds, "start_hour": act.start_hour}
        out.append(("activate_surge_beds", d, InterventionsSpec(activate_surge_beds=(act,))))
    for mv in spec.reallocate_staff:
        d = {"from_unit": mv.from_unit, "to_unit": mv.to_unit, "nurses": mv.nurses, "start_hour": mv.start_hour}
        out.append(("reallocate_staff", d, InterventionsSpec(reallocate_staff=(mv,))))
    for sh in spec.reduce_noncritical_load:
        d = {"kw": sh.kw, "start_hour": sh.start_hour, "end_hour": sh.end_hour}
        out.append(("reduce_noncritical_load_kw", d, InterventionsSpec(reduce_noncritical_load=(sh,))))
    for rec in spec.recall_staff:
        d = {"unit": rec.unit, "nurses": rec.nurses, "start_hour": rec.start_hour}
        out.append(("recall_staff", d, InterventionsSpec(recall_staff=(rec,))))
    for res in spec.emergency_resupply:
        d = {"fuel_l": res.fuel_l, "items": dict(res.items), "start_hour": res.start_hour}
        out.append(("emergency_resupply", d, InterventionsSpec(emergency_resupply=(res,))))
    return out


def _relative(before: float, after: float) -> float | None:
    """Relative change; null when the baseline is 0 (never divide by zero)."""
    if before == 0:
        return None
    return round((after - before) / before, 4)


def _delta_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Absolute and relative deltas for every scalar summary metric."""
    deltas: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, dict) or isinstance(after_value, dict):
            nested: dict[str, Any] = {}
            for k in set(before_value) | set(after_value or {}):
                bv, av = before_value.get(k), (after_value or {}).get(k)
                if isinstance(bv, int | float) and isinstance(av, int | float) and not isinstance(bv, bool):
                    nested[k] = {"absolute": round(av - bv, 4), "relative": _relative(bv, av)}
            deltas[key] = nested
            continue
        if isinstance(before_value, int | float) and isinstance(after_value, int | float) \
                and not isinstance(before_value, bool):
            deltas[key] = {"absolute": round(after_value - before_value, 4),
                           "relative": _relative(before_value, after_value)}
    return deltas


def _detail_effective(kind: str, detail: dict[str, Any], cfg: HospitalConfig) -> dict[str, Any]:
    """Copy of the detail with the effective hour (after lead time) filled in."""
    d = dict(detail)
    if kind == "activate_surge_beds":
        d["effective_hour"] = d.get("start_hour", 0) + cfg.surge.activation_delay_hours
    if kind == "recall_staff":
        d["effective_hour"] = d.get("start_hour", 0) + cfg.recall.lead_time_hours
    if kind == "emergency_resupply":
        d["effective_hour"] = d.get("start_hour", 0) + cfg.supplies.emergency_lead_time_hours
    return d


@dataclass(frozen=True)
class ComparisonResult:
    """Full comparison payload (all values CALCULATED)."""

    baseline: dict[str, Any]
    treatment: dict[str, Any]
    deltas: dict[str, Any]
    attribution: list[dict[str, Any]]
    explanations: list[str]
    key_metric_deltas: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare(cfg: HospitalConfig, scenario: ScenarioSpec, interventions: InterventionsSpec,
            seed: int | None = None, stochastic: bool | None = None) -> ComparisonResult:
    """Run baseline and intervention cases and build the comparison payload.

    Both runs start from identical initial state with the same seed and the
    same weather series (the engine is stateless and deterministic).
    """
    validate_feasible(interventions, cfg, scenario)
    baseline = run(cfg, scenario, None, seed, stochastic)
    treatment = run(cfg, scenario, interventions, seed, stochastic)

    attribution: list[dict[str, Any]] = []
    for kind, detail, single in _single_interventions(interventions):
        single_run = run(cfg, scenario, single, seed, stochastic)
        attribution.append({
            "intervention": kind,
            "detail": _detail_effective(kind, detail, cfg),
            "deltas": _delta_metrics(baseline.summary, single_run.summary),
            "explanation": explain_intervention(kind, _detail_effective(kind, detail, cfg),
                                                baseline.to_dict(), single_run.to_dict()),
        })

    combined_deltas = _delta_metrics(baseline.summary, treatment.summary)
    explanations = explain_comparison(baseline.to_dict(), treatment.to_dict())
    key_deltas = {k: combined_deltas.get(k) for k in KEY_METRICS if k in combined_deltas}

    return ComparisonResult(
        baseline=baseline.to_dict(),
        treatment=treatment.to_dict(),
        deltas=combined_deltas,
        attribution=attribution,
        explanations=explanations,
        key_metric_deltas=key_deltas,
    )
