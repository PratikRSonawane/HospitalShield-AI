"""Hospital configuration: load and validate into frozen dataclasses.

All values come from data/demo_hospital.json (SYNTHETIC baseline).
Units are stated per field; ``_fraction`` fields are 0-1, ``_pct`` are 0-100,
``_kw`` kilowatts, ``_kwh`` kilowatt-hours, ``_l`` litres, ``_c`` degrees Celsius,
``_hours`` hours.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import Issue, SimulationValidationError

UNITS = ("ed", "ward", "icu")


@dataclass(frozen=True)
class EdConfig:
    bays: int
    nurse_roster: int
    patients_per_nurse: int
    los_hours: float  # hours


@dataclass(frozen=True)
class InpatientConfig:
    beds: int
    nurse_roster: int
    patients_per_nurse: int
    alos_hours: float  # hours
    initial_occupied: int
    surge_beds_available: int


@dataclass(frozen=True)
class ArrivalsConfig:
    baseline_per_hour: float  # patients per hour
    diurnal_profile: tuple[float, ...]  # 24 factors, mean 1.0
    p_admit_ward: float  # fraction 0-1
    p_admit_icu: float  # fraction 0-1


@dataclass(frozen=True)
class PowerConfig:
    grid_capacity_kw: float
    critical_load_kw: float
    noncritical_load_kw: float
    noncritical_diurnal_profile: tuple[float, ...]
    cooling_base_kw: float
    cooling_threshold_c: float  # degrees Celsius
    cooling_kw_per_deg_c_above: float  # kW per degree C above threshold
    cooling_critical_fraction: float  # fraction of cooling that is critical
    generator_capacity_kw: float
    fuel_litres: float
    fuel_l_per_kwh: float
    surge_bed_kw: float
    max_shed_fraction_of_noncritical: float
    power_derate_factor_when_critical_at_risk: float


@dataclass(frozen=True)
class StaffingConfig:
    max_reallocation_fraction_of_source: float
    min_source_floor_fraction: float


@dataclass(frozen=True)
class SurgeConfig:
    activation_delay_hours: int


@dataclass(frozen=True)
class SuppliesConfig:
    items: tuple[str, ...]
    units_per_weighted_bed_hour: Mapping[str, float]  # units per weighted bed-hour
    initial_cover_hours: float
    icu_weight: float
    ed_weight: float
    scheduled_resupply_fraction: float
    low_cover_hours: float
    stockout_derate_factor: float
    emergency_resupply_max_cover_hours: float
    emergency_lead_time_hours: int


@dataclass(frozen=True)
class RecallConfig:
    max_fraction_of_roster: float
    lead_time_hours: int


@dataclass(frozen=True)
class ThresholdsConfig:
    occupancy_warn_pct: float  # 0-100
    reserve_low_pct: float  # 0-100
    fuel_low_hours: float
    ed_boarding_warn: int
    ed_waiting_high: int


@dataclass(frozen=True)
class ResilienceWeightsConfig:
    occupancy: float
    overflow: float
    staffing: float
    power_deficit: float
    critical_risk: float
    supply: float


@dataclass(frozen=True)
class HospitalConfig:
    hospital_name: str
    ed: EdConfig
    ward: InpatientConfig
    icu: InpatientConfig
    arrivals: ArrivalsConfig
    power: PowerConfig
    staffing: StaffingConfig
    surge: SurgeConfig
    supplies: SuppliesConfig
    recall: RecallConfig
    thresholds: ThresholdsConfig
    resilience_weights: ResilienceWeightsConfig
    source_path: str = "data/demo_hospital.json"

    def physical_beds(self, unit: str) -> int:
        """Physical bed/bay count per unit (integer beds)."""
        if unit == "ed":
            return self.ed.bays
        if unit == "ward":
            return self.ward.beds
        if unit == "icu":
            return self.icu.beds
        raise KeyError(f"unknown unit {unit}")

    def nurse_roster(self, unit: str) -> int:
        """Rostered nurses per unit (integer nurses)."""
        rosters = {"ed": self.ed.nurse_roster, "ward": self.ward.nurse_roster, "icu": self.icu.nurse_roster}
        return rosters[unit]

    def patients_per_nurse(self, unit: str) -> int:
        """Ratio patients per nurse per unit."""
        ppn = {"ed": self.ed.patients_per_nurse, "ward": self.ward.patients_per_nurse, "icu": self.icu.patients_per_nurse}
        return ppn[unit]


def _require(data: Mapping[str, Any], key: str, issues: list[Issue], prefix: str = "") -> Any:
    if key not in data:
        issues.append(Issue(field=f"{prefix}{key}", reason="missing required field", rule="required"))
        return None
    return data[key]


def _profile(value: Any, name: str, issues: list[Issue]) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != 24:
        issues.append(Issue(field=name, reason="must be a list of 24 hourly factors", rule="shape"))
        return tuple([1.0] * 24)
    return tuple(float(v) for v in value)


def parse_hospital_config(data: Mapping[str, Any], source_path: str = "data/demo_hospital.json") -> HospitalConfig:
    """Validate a hospital config dict into a frozen HospitalConfig.

    Raises SimulationValidationError listing every problem found.
    """
    issues: list[Issue] = []
    try:
        ed_raw = _require(data, "ed", issues) or {}
        ward_raw = _require(data, "ward", issues) or {}
        icu_raw = _require(data, "icu", issues) or {}
        arr_raw = _require(data, "arrivals", issues) or {}
        pow_raw = _require(data, "power", issues) or {}
        sta_raw = _require(data, "staffing", issues) or {}
        sur_raw = _require(data, "surge", issues) or {}
        sup_raw = _require(data, "supplies", issues) or {}
        rec_raw = _require(data, "recall", issues) or {}
        thr_raw = _require(data, "thresholds", issues) or {}
        res_raw = _require(data, "resilience_weights", issues) or {}

        ed = EdConfig(
            bays=int(ed_raw["bays"]), nurse_roster=int(ed_raw["nurse_roster"]),
            patients_per_nurse=int(ed_raw["patients_per_nurse"]), los_hours=float(ed_raw["los_hours"]),
        )
        ward = InpatientConfig(
            beds=int(ward_raw["beds"]), nurse_roster=int(ward_raw["nurse_roster"]),
            patients_per_nurse=int(ward_raw["patients_per_nurse"]), alos_hours=float(ward_raw["alos_hours"]),
            initial_occupied=int(ward_raw["initial_occupied"]), surge_beds_available=int(ward_raw["surge_beds_available"]),
        )
        icu = InpatientConfig(
            beds=int(icu_raw["beds"]), nurse_roster=int(icu_raw["nurse_roster"]),
            patients_per_nurse=int(icu_raw["patients_per_nurse"]), alos_hours=float(icu_raw["alos_hours"]),
            initial_occupied=int(icu_raw["initial_occupied"]), surge_beds_available=int(icu_raw["surge_beds_available"]),
        )
        arrivals = ArrivalsConfig(
            baseline_per_hour=float(arr_raw["baseline_per_hour"]),
            diurnal_profile=_profile(arr_raw.get("diurnal_profile"), "arrivals.diurnal_profile", issues),
            p_admit_ward=float(arr_raw["p_admit_ward"]), p_admit_icu=float(arr_raw["p_admit_icu"]),
        )
        power = PowerConfig(
            grid_capacity_kw=float(pow_raw["grid_capacity_kw"]), critical_load_kw=float(pow_raw["critical_load_kw"]),
            noncritical_load_kw=float(pow_raw["noncritical_load_kw"]),
            noncritical_diurnal_profile=_profile(pow_raw.get("noncritical_diurnal_profile"), "power.noncritical_diurnal_profile", issues),
            cooling_base_kw=float(pow_raw["cooling_base_kw"]), cooling_threshold_c=float(pow_raw["cooling_threshold_c"]),
            cooling_kw_per_deg_c_above=float(pow_raw["cooling_kw_per_deg_c_above"]),
            cooling_critical_fraction=float(pow_raw["cooling_critical_fraction"]),
            generator_capacity_kw=float(pow_raw["generator_capacity_kw"]), fuel_litres=float(pow_raw["fuel_litres"]),
            fuel_l_per_kwh=float(pow_raw["fuel_l_per_kwh"]), surge_bed_kw=float(pow_raw["surge_bed_kw"]),
            max_shed_fraction_of_noncritical=float(pow_raw["max_shed_fraction_of_noncritical"]),
            power_derate_factor_when_critical_at_risk=float(pow_raw["power_derate_factor_when_critical_at_risk"]),
        )
        items = tuple(str(i) for i in sup_raw.get("items", []))
        rates = {str(k): float(v) for k, v in dict(sup_raw.get("units_per_weighted_bed_hour", {})).items()}
        for item in items:
            if item not in rates:
                issues.append(Issue(field=f"supplies.units_per_weighted_bed_hour.{item}", reason="rate missing for item", rule="required"))
        supplies = SuppliesConfig(
            items=items, units_per_weighted_bed_hour=rates,
            initial_cover_hours=float(sup_raw["initial_cover_hours"]), icu_weight=float(sup_raw["icu_weight"]),
            ed_weight=float(sup_raw["ed_weight"]), scheduled_resupply_fraction=float(sup_raw["scheduled_resupply_fraction"]),
            low_cover_hours=float(sup_raw["low_cover_hours"]), stockout_derate_factor=float(sup_raw["stockout_derate_factor"]),
            emergency_resupply_max_cover_hours=float(sup_raw["emergency_resupply_max_cover_hours"]),
            emergency_lead_time_hours=int(sup_raw["emergency_lead_time_hours"]),
        )
        cfg = HospitalConfig(
            hospital_name=str(data.get("hospital_name", "unnamed")),
            ed=ed, ward=ward, icu=icu, arrivals=arrivals, power=power,
            staffing=StaffingConfig(
                max_reallocation_fraction_of_source=float(sta_raw["max_reallocation_fraction_of_source"]),
                min_source_floor_fraction=float(sta_raw["min_source_floor_fraction"]),
            ),
            surge=SurgeConfig(activation_delay_hours=int(sur_raw["activation_delay_hours"])),
            supplies=supplies,
            recall=RecallConfig(
                max_fraction_of_roster=float(rec_raw["max_fraction_of_roster"]),
                lead_time_hours=int(rec_raw["lead_time_hours"]),
            ),
            thresholds=ThresholdsConfig(
                occupancy_warn_pct=float(thr_raw["occupancy_warn_pct"]), reserve_low_pct=float(thr_raw["reserve_low_pct"]),
                fuel_low_hours=float(thr_raw["fuel_low_hours"]), ed_boarding_warn=int(thr_raw["ed_boarding_warn"]),
                ed_waiting_high=int(thr_raw["ed_waiting_high"]),
            ),
            resilience_weights=ResilienceWeightsConfig(
                occupancy=float(res_raw["occupancy"]), overflow=float(res_raw["overflow"]),
                staffing=float(res_raw["staffing"]), power_deficit=float(res_raw["power_deficit"]),
                critical_risk=float(res_raw["critical_risk"]), supply=float(res_raw["supply"]),
            ),
            source_path=source_path,
        )
    except (KeyError, TypeError, ValueError) as exc:
        issues.append(Issue(field="config", reason=f"malformed value: {exc}", rule="type"))
        raise SimulationValidationError(issues) from exc
    if issues:
        raise SimulationValidationError(issues)
    return cfg


def load_hospital_config(path: str | Path) -> HospitalConfig:
    """Read a hospital JSON file from disk (callers outside the engine may do IO)."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return parse_hospital_config(data, source_path=str(p))
