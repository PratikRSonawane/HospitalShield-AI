"""Tier 2 services (S8): ensembles and one-at-a-time sensitivity.

Both are deterministic, engine-only computations; both degrade gracefully
and add no external dependencies.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.simulation import HospitalConfig, ScenarioSpec, run

ENSEMBLE_METRICS = ("resilience_index", "overflow_patient_hours", "hours_power_deficit",
                    "peak_icu_occupancy_pct", "peak_ward_occupancy_pct", "peak_ed_waiting")


def run_ensemble(cfg: HospitalConfig, scenario: ScenarioSpec, runs: int) -> dict[str, Any]:
    """Run `runs` stochastic simulations with seeds seed+i (i = 0..runs-1).

    Returns P10/P50/P90 bands for key series and the distribution of
    summary metrics. Variability reflects seeded demand randomness only,
    never forecast confidence.
    """
    runs = max(2, min(runs, 200))
    results = []
    for i in range(runs):
        spec = replace(scenario, seed=(scenario.seed + i) % 2147483647, stochastic=True)
        results.append(run(cfg, spec))

    series_keys = ["ward_occ", "icu_occ", "ed_waiting", "deficit_kw"]
    bands: dict[str, list[dict[str, float | None]]] = {}
    for key in series_keys:
        extractor = _series_extractor(key)
        rows = []
        for h in range(scenario.duration_hours):
            values = sorted(extractor(r.series[h]) for r in results)
            rows.append({
                "hour": h,
                "p10": _percentile(values, 0.1),
                "p50": _percentile(values, 0.5),
                "p90": _percentile(values, 0.9),
            })
        bands[key] = rows

    metric_distributions: dict[str, dict[str, float | None]] = {}
    for metric in ENSEMBLE_METRICS:
        values = sorted(float(r.summary[metric]) for r in results if r.summary.get(metric) is not None)
        if not values:
            continue
        metric_distributions[metric] = {
            "p10": _percentile(values, 0.1), "p50": _percentile(values, 0.5),
            "p90": _percentile(values, 0.9), "min": values[0], "max": values[-1],
        }

    return {
        "runs": runs,
        "seed_base": scenario.seed,
        "label": "variability from seeded demand randomness, not forecast confidence",
        "series_bands": bands,
        "summary_distributions": metric_distributions,
    }


def _series_extractor(key: str):
    """Hourly value extractor for band construction."""
    def ward_occ(row: dict[str, Any]) -> float:
        v = row["units"]["ward"]["occupancy_pct"]
        return float(v) if v is not None else 0.0

    def icu_occ(row: dict[str, Any]) -> float:
        v = row["units"]["icu"]["occupancy_pct"]
        return float(v) if v is not None else 0.0

    return {
        "ward_occ": ward_occ,
        "icu_occ": icu_occ,
        "ed_waiting": lambda row: float(row["ed"]["waiting"]),
        "deficit_kw": lambda row: float(row["power"]["deficit_kw"]),
    }[key]


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile on pre-sorted values."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 3)
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return round(sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac, 3)


# one-at-a-time sensitivity knobs: (field path, low, high, apply fn)
def _sensitivity_knobs(scenario: ScenarioSpec) -> list[tuple[str, float, float, Any]]:
    return [
        ("stress.arrival_multiplier", 0.5, 2.0,
         lambda v: replace(scenario, stress=replace(scenario.stress, arrival_multiplier=v))),
        ("stress.staff_availability_fraction", 0.6, 1.0,
         lambda v: replace(scenario, stress=replace(scenario.stress, staff_availability_fraction=v))),
        ("stress.power_supply_fraction", 0.5, 1.0,
         lambda v: replace(scenario, stress=replace(scenario.stress, power_supply_fraction=v))),
        ("weather.max_temperature_c", 30.0, 48.0,
         lambda v: replace(scenario, weather=replace(scenario.weather, max_temperature_c=v))),
        ("outage.duration_hours", 12.0, 48.0, _outage_knob(scenario)),
        ("access.staff_access_fraction", 0.4, 1.0, _access_knob(scenario)),
        ("access.delivery_fraction", 0.05, 1.0, _delivery_knob(scenario)),
    ]


def _outage_knob(scenario: ScenarioSpec):
    if scenario.outage is None:
        return None
    def apply(v: float) -> ScenarioSpec:
        duration = int(max(1, min(72, round(v))))
        return replace(scenario, outage=replace(scenario.outage, duration_hours=duration))
    return apply


def _access_knob(scenario: ScenarioSpec):
    if scenario.access is None:
        return None
    def apply(v: float) -> ScenarioSpec:
        return replace(scenario, access=replace(scenario.access, staff_access_fraction=v))
    return apply


def _delivery_knob(scenario: ScenarioSpec):
    if scenario.access is None:
        return None
    def apply(v: float) -> ScenarioSpec:
        return replace(scenario, access=replace(scenario.access, delivery_fraction=v))
    return apply


def run_sensitivity(cfg: HospitalConfig, scenario: ScenarioSpec) -> dict[str, Any]:
    """Vary one input at a time (low/high); tornado data for the Resilience
    Index and overflow patient-hours."""
    baseline = run(cfg, scenario)
    tornado: list[dict[str, Any]] = []
    for field, low, high, apply in _sensitivity_knobs(scenario):
        if apply is None:
            continue
        low_run = run(cfg, apply(low))
        high_run = run(cfg, apply(high))
        tornado.append({
            "field": field,
            "low": low,
            "high": high,
            "resilience_low": low_run.summary["resilience_index"],
            "resilience_high": high_run.summary["resilience_index"],
            "overflow_low": low_run.summary["overflow_patient_hours"],
            "overflow_high": high_run.summary["overflow_patient_hours"],
        })
    tornado.sort(key=lambda t: -abs(t["resilience_high"] - t["resilience_low"]))
    return {
        "baseline": {"resilience_index": baseline.summary["resilience_index"],
                     "overflow_patient_hours": baseline.summary["overflow_patient_hours"]},
        "tornado": tornado,
    }
