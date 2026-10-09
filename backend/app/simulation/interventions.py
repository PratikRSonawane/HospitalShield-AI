"""Interventions (B6) and their feasibility validator.

An InterventionsSpec is the normalised description of planner-chosen
actions. The validator rejects impossible requests with structured
per-rule reasons; the engine never clamps an infeasible request silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .config import HospitalConfig
from .errors import InfeasibleInterventionError, Issue
from .scenario import ScenarioSpec

UNITS = ("ed", "ward", "icu")


@dataclass(frozen=True)
class SurgeActivation:
    unit: str
    beds: int
    start_hour: int


@dataclass(frozen=True)
class StaffMove:
    from_unit: str
    to_unit: str
    nurses: int
    start_hour: int


@dataclass(frozen=True)
class LoadShed:
    kw: float
    start_hour: int
    end_hour: int


@dataclass(frozen=True)
class StaffRecall:
    unit: str
    nurses: int
    start_hour: int


@dataclass(frozen=True)
class EmergencyResupply:
    fuel_l: float = 0.0
    items: Mapping[str, float] = field(default_factory=dict)
    start_hour: int = 0


@dataclass(frozen=True)
class InterventionsSpec:
    activate_surge_beds: tuple[SurgeActivation, ...] = ()
    reallocate_staff: tuple[StaffMove, ...] = ()
    reduce_noncritical_load: tuple[LoadShed, ...] = ()
    recall_staff: tuple[StaffRecall, ...] = ()
    emergency_resupply: tuple[EmergencyResupply, ...] = ()


def _pos_int(value: Any, name: str, issues: list[Issue], lo: int = 0) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        issues.append(Issue(field=name, reason="must be an integer", rule="type"))
        return lo
    if v < lo:
        issues.append(Issue(field=name, reason=f"must be >= {lo}", rule="bound"))
    return v


def _pos_num(value: Any, name: str, issues: list[Issue], lo: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        issues.append(Issue(field=name, reason="must be a number", rule="type"))
        return lo
    if v < lo:
        issues.append(Issue(field=name, reason=f"must be >= {lo}", rule="bound"))
    return v


def parse_interventions(data: Mapping[str, Any] | None) -> InterventionsSpec:
    """Normalise an interventions request dict; bounds are checked against the
    hospital config by validate_feasible (needs roster and duration context)."""
    if not data:
        return InterventionsSpec()
    issues: list[Issue] = []
    surge: list[SurgeActivation] = []
    for entry in data.get("activate_surge_beds") or []:
        e = dict(entry)
        unit = str(e.get("unit", ""))
        surge.append(SurgeActivation(
            unit=unit, beds=_pos_int(e.get("beds", 0), f"activate_surge_beds.{unit}.beds", issues),
            start_hour=_pos_int(e.get("start_hour", 0), f"activate_surge_beds.{unit}.start_hour", issues)))
    moves: list[StaffMove] = []
    for i, entry in enumerate(data.get("reallocate_staff") or []):
        e = dict(entry)
        moves.append(StaffMove(
            from_unit=str(e.get("from_unit", "")), to_unit=str(e.get("to_unit", "")),
            nurses=_pos_int(e.get("nurses", 0), f"reallocate_staff[{i}].nurses", issues),
            start_hour=_pos_int(e.get("start_hour", 0), f"reallocate_staff[{i}].start_hour", issues)))
    sheds: list[LoadShed] = []
    for i, entry in enumerate(data.get("reduce_noncritical_load_kw") or []):
        e = dict(entry)
        sheds.append(LoadShed(
            kw=_pos_num(e.get("kw", 0), f"reduce_noncritical_load_kw[{i}].kw", issues),
            start_hour=_pos_int(e.get("start_hour", 0), f"reduce_noncritical_load_kw[{i}].start_hour", issues),
            end_hour=_pos_int(e.get("end_hour", 0), f"reduce_noncritical_load_kw[{i}].end_hour", issues)))
    recalls: list[StaffRecall] = []
    for i, entry in enumerate(data.get("recall_staff") or []):
        e = dict(entry)
        recalls.append(StaffRecall(
            unit=str(e.get("unit", "")),
            nurses=_pos_int(e.get("nurses", 0), f"recall_staff[{i}].nurses", issues),
            start_hour=_pos_int(e.get("start_hour", 0), f"recall_staff[{i}].start_hour", issues)))
    resupply: list[EmergencyResupply] = []
    for i, entry in enumerate(data.get("emergency_resupply") or []):
        e = dict(entry)
        items = {str(k): _pos_num(v, f"emergency_resupply[{i}].{k}", issues)
                 for k, v in dict(e.get("items") or {}).items()}
        resupply.append(EmergencyResupply(
            fuel_l=_pos_num(e.get("fuel_l", 0.0), f"emergency_resupply[{i}].fuel_l", issues),
            items=items,
            start_hour=_pos_int(e.get("start_hour", 0), f"emergency_resupply[{i}].start_hour", issues)))
    if issues:
        raise InfeasibleInterventionError(issues)
    return InterventionsSpec(
        activate_surge_beds=tuple(surge), reallocate_staff=tuple(moves),
        reduce_noncritical_load=tuple(sheds), recall_staff=tuple(recalls),
        emergency_resupply=tuple(resupply))


def ed_in_service_estimate(cfg: HospitalConfig) -> int:
    """Steady-state ED patients in bays (integer) from baseline arrivals and LOS."""
    raw = cfg.arrivals.baseline_per_hour * cfg.ed.los_hours
    return max(0, min(cfg.ed.bays, round(raw)))


def weighted_occupied_baseline(cfg: HospitalConfig) -> float:
    """Weighted occupied beds (beds) at t=0: ward + icu*icu_weight + ed*ed_weight."""
    ed_occ = ed_in_service_estimate(cfg)
    return cfg.ward.initial_occupied + cfg.icu.initial_occupied * cfg.supplies.icu_weight + ed_occ * cfg.supplies.ed_weight


def validate_feasible(spec: InterventionsSpec, cfg: HospitalConfig, scenario: ScenarioSpec) -> None:
    """Raise InfeasibleInterventionError with per-rule reasons if any action
    violates B6. Called by the API and by the planner; the engine trusts it."""
    issues: list[Issue] = []
    duration = scenario.duration_hours

    for act in spec.activate_surge_beds:
        if act.unit not in UNITS:
            issues.append(Issue(field=f"activate_surge_beds.{act.unit}.unit", reason="unit must be ed, ward or icu", rule="enum"))
            continue
        avail = cfg.icu.surge_beds_available if act.unit == "icu" else cfg.ward.surge_beds_available
        if act.beds > avail:
            issues.append(Issue(field=f"activate_surge_beds.{act.unit}.beds",
                                reason=f"requests {act.beds} but only {avail} surge beds available", rule="surge_capacity"))
        if act.start_hour >= duration:
            issues.append(Issue(field=f"activate_surge_beds.{act.unit}.start_hour",
                                reason=f"start {act.start_hour} at or beyond horizon {duration}", rule="horizon"))

    out_by_source: dict[str, int] = {}
    for mv in spec.reallocate_staff:
        if mv.from_unit not in UNITS or mv.to_unit not in UNITS:
            issues.append(Issue(field="reallocate_staff", reason="units must be ed, ward or icu", rule="enum"))
            continue
        if mv.from_unit == mv.to_unit:
            issues.append(Issue(field="reallocate_staff", reason="self-move is not allowed", rule="self_move"))
            continue
        out_by_source[mv.from_unit] = out_by_source.get(mv.from_unit, 0) + mv.nurses
        if mv.start_hour >= duration:
            issues.append(Issue(field="reallocate_staff", reason=f"start {mv.start_hour} at or beyond horizon {duration}", rule="horizon"))
    for src, total_out in out_by_source.items():
        roster = cfg.nurse_roster(src)
        floor_nurses = cfg.staffing.min_source_floor_fraction * roster
        cap = cfg.staffing.max_reallocation_fraction_of_source * roster
        if total_out > cap:
            issues.append(Issue(field=f"reallocate_staff.{src}",
                                reason=f"moving {total_out} exceeds max {cap:.1f} (max_reallocation_fraction_of_source)", rule="reallocation_cap"))
        remaining = roster - total_out
        if remaining < floor_nurses:
            issues.append(Issue(field=f"reallocate_staff.{src}",
                                reason=f"source would keep {remaining} < floor {floor_nurses:.1f} (min_source_floor_fraction)", rule="source_floor"))
        required = _baseline_required(cfg, src)
        if remaining < required:
            issues.append(Issue(field=f"reallocate_staff.{src}",
                                reason=f"source would keep {remaining} < required {required} nurses at baseline occupancy", rule="source_required"))

    for i, shed in enumerate(spec.reduce_noncritical_load):
        if shed.end_hour <= shed.start_hour:
            issues.append(Issue(field=f"reduce_noncritical_load_kw[{i}]", reason="end_hour must be after start_hour", rule="window"))
        if shed.end_hour > duration:
            issues.append(Issue(field=f"reduce_noncritical_load_kw[{i}].end_hour",
                                reason=f"end {shed.end_hour} beyond horizon {duration}", rule="horizon"))

    for i, rec in enumerate(spec.recall_staff):
        if rec.unit not in UNITS:
            issues.append(Issue(field=f"recall_staff[{i}].unit", reason="unit must be ed, ward or icu", rule="enum"))
            continue
        cap = cfg.recall.max_fraction_of_roster * cfg.nurse_roster(rec.unit)
        if rec.nurses > cap:
            issues.append(Issue(field=f"recall_staff[{i}].nurses",
                                reason=f"recalling {rec.nurses} exceeds cap {cap:.1f} (max_fraction_of_roster)", rule="recall_cap"))
        arrival = rec.start_hour + cfg.recall.lead_time_hours
        if arrival >= duration:
            issues.append(Issue(field=f"recall_staff[{i}].start_hour",
                                reason=f"staff would arrive at hour {arrival}, at or beyond horizon {duration}", rule="horizon"))

    resupply_cap_fuel_l = cfg.supplies.emergency_resupply_max_cover_hours * cfg.power.generator_capacity_kw * cfg.power.fuel_l_per_kwh
    weighted = weighted_occupied_baseline(cfg)
    for i, res in enumerate(spec.emergency_resupply):
        if res.fuel_l > resupply_cap_fuel_l:
            issues.append(Issue(field=f"emergency_resupply[{i}].fuel_l",
                                reason=f"{res.fuel_l} L exceeds cap {resupply_cap_fuel_l:.0f} L "
                                       f"(emergency_resupply_max_cover_hours at full generator burn)", rule="resupply_cap"))
        for item, amount in res.items.items():
            if item not in cfg.supplies.items:
                issues.append(Issue(field=f"emergency_resupply[{i}].{item}", reason="unknown supply item", rule="enum"))
                continue
            rate = cfg.supplies.units_per_weighted_bed_hour[item] * weighted
            cap = cfg.supplies.emergency_resupply_max_cover_hours * rate
            if amount > cap:
                issues.append(Issue(field=f"emergency_resupply[{i}].{item}",
                                    reason=f"{amount} units exceeds cap {cap:.0f} "
                                           f"(emergency_resupply_max_cover_hours at baseline consumption)", rule="resupply_cap"))
        arrival = res.start_hour + cfg.supplies.emergency_lead_time_hours
        if arrival >= duration:
            issues.append(Issue(field=f"emergency_resupply[{i}].start_hour",
                                reason=f"delivery would arrive at hour {arrival}, at or beyond horizon {duration}", rule="horizon"))

    if issues:
        raise InfeasibleInterventionError(issues)


def _baseline_required(cfg: HospitalConfig, unit: str) -> int:
    """Nurses required at baseline occupancy (integer, ceil)."""
    import math
    if unit == "ed":
        occupied = ed_in_service_estimate(cfg)
    elif unit == "ward":
        occupied = cfg.ward.initial_occupied
    else:
        occupied = cfg.icu.initial_occupied
    return math.ceil(occupied / cfg.patients_per_nurse(unit))
