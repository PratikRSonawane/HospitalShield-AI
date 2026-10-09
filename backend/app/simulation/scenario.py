"""Scenario specification and validation (B5 ranges, cross-field rules).

A ScenarioSpec is the normalised, immutable description of one run:
weather, stress multipliers, outage window, access window, backup
availability. Interventions are modelled separately (interventions.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import Issue, SimulationValidationError

SCENARIOS = ("normal_operations", "heatwave_power_stress", "heatwave_power_outage", "flood_storm_access")

MAX_SEED = 2147483647


@dataclass(frozen=True)
class WeatherSpec:
    mode: str = "synthetic_profile"  # synthetic_profile | provided_series
    max_temperature_c: float = 41.0  # degrees Celsius
    min_temperature_c: float | None = None  # defaults to max - 10
    humidity_pct: float = 55.0  # 0-100
    provided_series_c: tuple[float, ...] | None = None  # hourly Celsius, length == duration


@dataclass(frozen=True)
class StressSpec:
    arrival_multiplier: float = 1.25  # factor on arrivals
    los_multiplier: float = 1.0  # factor on inpatient length of stay
    staff_availability_fraction: float = 0.9  # fraction 0-1
    power_supply_fraction: float = 0.8  # fraction 0-1


@dataclass(frozen=True)
class OutageSpec:
    start_hour: int
    duration_hours: int
    grid_fraction: float  # fraction 0-1 of grid capacity during outage


@dataclass(frozen=True)
class AccessSpec:
    start_hour: int
    duration_hours: int
    staff_access_fraction: float  # fraction 0-1
    delivery_fraction: float  # fraction 0-1
    arrival_multiplier: float  # factor on arrivals inside the window


@dataclass(frozen=True)
class BackupSpec:
    generator_availability_fraction: float = 1.0  # fraction 0-1


@dataclass(frozen=True)
class ScenarioSpec:
    scenario: str
    duration_hours: int
    weather: WeatherSpec = field(default_factory=WeatherSpec)
    stress: StressSpec = field(default_factory=StressSpec)
    outage: OutageSpec | None = None
    access: AccessSpec | None = None
    backup: BackupSpec = field(default_factory=BackupSpec)
    stochastic: bool = False
    seed: int = 42


def _num(value: Any, lo: float, hi: float, name: str, issues: list[Issue]) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        issues.append(Issue(field=name, reason="must be a number", rule="type"))
        return lo
    if not (lo <= v <= hi):
        issues.append(Issue(field=name, reason=f"must be within {lo}..{hi}", rule="bound"))
        return min(max(v, lo), hi) if issues is None else v  # keep raw value; caller raises
    return v


def _int(value: Any, lo: int, hi: int, name: str, issues: list[Issue]) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        issues.append(Issue(field=name, reason="must be an integer", rule="type"))
        return lo
    if not (lo <= v <= hi):
        issues.append(Issue(field=name, reason=f"must be within {lo}..{hi}", rule="bound"))
    return v


def parse_scenario(data: Mapping[str, Any]) -> ScenarioSpec:
    """Validate and normalise a scenario request dict.

    Applies B5 defaults, enforces bounds and cross-field rules
    (min <= max temperature; outage and access windows fit the horizon).
    Raises SimulationValidationError with every issue when invalid.
    """
    issues: list[Issue] = []
    scenario = data.get("scenario")
    if scenario not in SCENARIOS:
        issues.append(Issue(field="scenario", reason=f"must be one of {SCENARIOS}", rule="enum"))
        scenario = SCENARIOS[0]
    duration = _int(data.get("duration_hours", 72), 1, 72, "duration_hours", issues)

    w_raw = dict(data.get("weather") or {})
    mode = w_raw.get("mode", "synthetic_profile")
    if mode not in ("synthetic_profile", "provided_series"):
        issues.append(Issue(field="weather.mode", reason="must be synthetic_profile or provided_series", rule="enum"))
        mode = "synthetic_profile"
    t_max = _num(w_raw.get("max_temperature_c", 41), -10, 55, "weather.max_temperature_c", issues)
    t_min_raw = w_raw.get("min_temperature_c")
    t_min: float | None
    if t_min_raw is None:
        t_min = t_max - 10.0
    else:
        t_min = _num(t_min_raw, -10, 55, "weather.min_temperature_c", issues)
        if t_min > t_max:
            issues.append(Issue(field="weather.min_temperature_c", reason="must be <= max_temperature_c", rule="cross_field"))
    humidity = _num(w_raw.get("humidity_pct", 55), 0, 100, "weather.humidity_pct", issues)
    series: tuple[float, ...] | None = None
    if mode == "provided_series":
        raw_series = w_raw.get("series_c")
        if not isinstance(raw_series, list) or len(raw_series) != duration:
            issues.append(Issue(field="weather.series_c", reason=f"must be a list of {duration} hourly values", rule="shape"))
        else:
            series = tuple(float(x) for x in raw_series)
            if any(not (-70 <= x <= 60) for x in series):
                issues.append(Issue(field="weather.series_c", reason="values must be plausible Celsius (-70..60)", rule="plausible"))
    weather = WeatherSpec(mode=mode, max_temperature_c=t_max, min_temperature_c=t_min,
                          humidity_pct=humidity, provided_series_c=series)

    s_raw = dict(data.get("stress") or {})
    stress = StressSpec(
        arrival_multiplier=_num(s_raw.get("arrival_multiplier", 1.25), 0, 3, "stress.arrival_multiplier", issues),
        los_multiplier=_num(s_raw.get("los_multiplier", 1.0), 0.5, 2, "stress.los_multiplier", issues),
        staff_availability_fraction=_num(s_raw.get("staff_availability_fraction", 0.9), 0, 1, "stress.staff_availability_fraction", issues),
        power_supply_fraction=_num(s_raw.get("power_supply_fraction", 0.8), 0, 1, "stress.power_supply_fraction", issues),
    )

    o_raw = data.get("outage")
    outage: OutageSpec | None = None
    if o_raw:
        o = dict(o_raw)
        start = _int(o.get("start_hour", 24), 0, 71, "outage.start_hour", issues)
        odur = _int(o.get("duration_hours", 36), 0, 72, "outage.duration_hours", issues)
        gfrac = _num(o.get("grid_fraction", 0.0), 0, 1, "outage.grid_fraction", issues)
        if start + odur > duration:
            issues.append(Issue(field="outage", reason="window (start_hour + duration_hours) must fit within duration_hours", rule="cross_field"))
        outage = OutageSpec(start_hour=start, duration_hours=odur, grid_fraction=gfrac)

    a_raw = data.get("access")
    access: AccessSpec | None = None
    if a_raw:
        a = dict(a_raw)
        start = _int(a.get("start_hour", 18), 0, 71, "access.start_hour", issues)
        adur = _int(a.get("duration_hours", 24), 0, 72, "access.duration_hours", issues)
        access = AccessSpec(
            start_hour=start, duration_hours=adur,
            staff_access_fraction=_num(a.get("staff_access_fraction", 0.6), 0, 1, "access.staff_access_fraction", issues),
            delivery_fraction=_num(a.get("delivery_fraction", 0.25), 0, 1, "access.delivery_fraction", issues),
            arrival_multiplier=_num(a.get("arrival_multiplier", 1.4), 0, 3, "access.arrival_multiplier", issues),
        )
        if start + adur > duration:
            issues.append(Issue(field="access", reason="window (start_hour + duration_hours) must fit within duration_hours", rule="cross_field"))

    b_raw = dict(data.get("backup") or {})
    backup = BackupSpec(generator_availability_fraction=_num(
        b_raw.get("generator_availability_fraction", 1.0), 0, 1, "backup.generator_availability_fraction", issues))

    stochastic = bool(data.get("stochastic", False))
    seed = _int(data.get("seed", 42), 0, MAX_SEED, "seed", issues)

    if issues:
        raise SimulationValidationError(issues)
    return ScenarioSpec(
        scenario=scenario, duration_hours=duration, weather=weather, stress=stress,
        outage=outage, access=access, backup=backup, stochastic=stochastic, seed=seed,
    )


def default_scenario(scenario: str, overrides: Mapping[str, Any] | None = None) -> ScenarioSpec:
    """Build a ScenarioSpec from a named preset plus optional overrides."""
    data: dict[str, Any] = {"scenario": scenario}
    if scenario == "normal_operations":
        data.update({
            "weather": {"max_temperature_c": 30, "min_temperature_c": 20},
            "stress": {"arrival_multiplier": 1.0, "los_multiplier": 1.0,
                       "staff_availability_fraction": 1.0, "power_supply_fraction": 1.0},
            "backup": {"generator_availability_fraction": 1.0},
        })
    elif scenario == "heatwave_power_stress":
        data.update({
            "weather": {"max_temperature_c": 41, "min_temperature_c": 29},
            "stress": {"arrival_multiplier": 1.15, "los_multiplier": 1.5,
                       "staff_availability_fraction": 0.9, "power_supply_fraction": 0.8},
        })
    elif scenario == "heatwave_power_outage":
        data.update({
            "weather": {"max_temperature_c": 43, "min_temperature_c": 30},
            "stress": {"arrival_multiplier": 1.15, "los_multiplier": 1.5,
                       "staff_availability_fraction": 0.9, "power_supply_fraction": 0.8},
            "outage": {"start_hour": 24, "duration_hours": 36, "grid_fraction": 0.0},
        })
    elif scenario == "flood_storm_access":
        data.update({
            "weather": {"max_temperature_c": 30, "min_temperature_c": 22, "humidity_pct": 90},
            "stress": {"arrival_multiplier": 1.0, "los_multiplier": 1.0,
                       "staff_availability_fraction": 0.95, "power_supply_fraction": 0.9},
            "access": {"start_hour": 18, "duration_hours": 24, "staff_access_fraction": 0.6,
                       "delivery_fraction": 0.15, "arrival_multiplier": 1.4},
            "backup": {"generator_availability_fraction": 0.6},
        })
    else:
        raise ValueError(f"unknown scenario {scenario}")
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
    return parse_scenario(data)


def grid_fraction_at(spec: ScenarioSpec, hour: int) -> float:
    """Grid supply fraction (0-1) at ``hour`` after the outage window."""
    if spec.outage and spec.outage.start_hour <= hour < spec.outage.start_hour + spec.outage.duration_hours:
        return spec.outage.grid_fraction
    return spec.stress.power_supply_fraction


def in_access_window(spec: ScenarioSpec, hour: int) -> bool:
    """True when ``hour`` falls inside the flood/storm access window."""
    return bool(spec.access and spec.access.start_hour <= hour < spec.access.start_hour + spec.access.duration_hours)


def staff_access_fraction_at(spec: ScenarioSpec, hour: int) -> float:
    """Staff access fraction (0-1) at ``hour``; 1.0 outside the access window."""
    if spec.access and in_access_window(spec, hour):
        return spec.access.staff_access_fraction
    return 1.0


def delivery_fraction_at(spec: ScenarioSpec, hour: int) -> float:
    """Delivery fraction (0-1) at ``hour``; 1.0 outside the access window."""
    if spec.access and in_access_window(spec, hour):
        return spec.access.delivery_fraction
    return 1.0


def arrival_multiplier_at(spec: ScenarioSpec, hour: int) -> float:
    """Arrival multiplier (factor) at ``hour``: stress multiplier times the storm multiplier inside the window."""
    mult = spec.stress.arrival_multiplier
    if spec.access and in_access_window(spec, hour):
        mult *= spec.access.arrival_multiplier
    return mult


def temperature_series(spec: ScenarioSpec) -> tuple[float, ...]:
    """Hourly temperatures (Celsius) for the horizon.

    Synthetic mode is a diurnal sine peaking at 15:00 between the min and
    max. Provided-series mode validates length upstream and returns as-is.
    """
    if spec.weather.provided_series_c is not None:
        return spec.weather.provided_series_c
    t_max = spec.weather.max_temperature_c
    t_min = spec.weather.min_temperature_c if spec.weather.min_temperature_c is not None else t_max - 10.0
    import math
    out: list[float] = []
    for h in range(spec.duration_hours):
        phase = 2.0 * math.pi * ((h - 9) % 24) / 24.0
        out.append(round(t_min + (t_max - t_min) * (1.0 + math.sin(phase)) / 2.0, 3))
    return tuple(out)
