"""Response models: typed envelopes for OpenAPI code generation.

The engine remains the single source of truth; these models describe the
envelope for the frontend (typed access to what the UI renders). They are
tolerant (extra fields allowed) so engine additions never break clients.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow")


class AlertEpisode(Tolerant):
    rule_id: str
    rule_text: str
    severity: str
    metric: str
    unit: str
    observed_peak: float
    threshold: float
    first_hour: int
    last_hour: int
    duration_hours: int
    affected_variable: str


class MarginPoint(Tolerant):
    hour: int
    margin: float


class FailurePoint(Tolerant):
    rank: int
    resource: str
    rule_id: str
    first_hour: int
    last_hour: int
    peak_severity: str
    margin_trace: list[MarginPoint]
    explanation: str
    cascade_parent: str | None = None
    cascade_children: list[str] = []


class FirstFailure(Tolerant):
    rule_id: str
    hour: int
    resource: str


class Summary(Tolerant):
    peak_ward_occupancy_pct: float | None = None
    peak_icu_occupancy_pct: float | None = None
    peak_ed_occupancy_pct: float | None = None
    hours_ward_above_threshold: int
    hours_icu_above_threshold: int
    peak_ed_waiting: int
    peak_ed_boarding: int
    overflow_patient_hours: int
    staff_shortfall_nurse_hours: int
    hours_beds_over_usable: int
    peak_power_demand_kw: float
    hours_power_deficit: int
    peak_power_deficit_kw: float
    energy_unserved_kwh: float
    min_power_reserve_kw: float
    hours_critical_load_at_risk: int
    fuel_remaining_l: float
    hours_to_fuel_exhaustion: int | None = None
    resilience_index: float
    first_failure: FirstFailure | None = None
    time_to_first_failure_hours: int | None = None
    root_failures: int = 0
    cascade_children: int = 0


class UnitRow(Tolerant):
    open_beds: int
    usable_beds: int
    occupied: int
    available_beds: int
    occupancy_pct: float | None
    beds_over_usable: int
    status: str


class StaffingRow(Tolerant):
    available: int
    staffed_capacity: int
    required: int
    shortfall: int


class PowerRow(Tolerant):
    demand_kw: float
    grid_supply_kw: float
    gen_output_kw: float
    available_supply_kw: float
    deficit_kw: float
    reserve_kw: float
    critical_at_risk_kw: float
    critical_demand_kw: float
    shed_kw: float
    fuel_l: float


class SupplyRow(Tolerant):
    stock: float
    delivered: float
    consumption: float
    unmet: float = 0.0
    cover_hours: float | None = None
    stockout: bool = False


class AccessRow(Tolerant):
    staff_access_fraction: float = 1.0
    delivery_fraction: float = 1.0
    arrival_multiplier: float = 1.0


class HourRow(Tolerant):
    hour: int
    temperature_c: float | None = None
    grid_fraction: float
    power: PowerRow
    staffing: dict[str, StaffingRow]
    units: dict[str, UnitRow]
    supplies: dict[str, SupplyRow] = {}
    access: AccessRow = AccessRow()
    ed: dict[str, int]
    discharged: int = 0
    binding_constraint: str
    margins: dict[str, float] | None = None


class Provenance(Tolerant):
    hospital_data: str = "SYNTHETIC"
    weather: str = "SYNTHETIC_PROFILE"
    outputs: str = "CALCULATED"
    model_version: str
    warnings: list[str] = []


class SimulationResponse(Tolerant):
    run_id: str
    model_version: str
    input_hash: str
    seed: int
    stochastic: bool
    summary: Summary
    series: list[HourRow]
    alerts: list[AlertEpisode]
    failure_points: list[FailurePoint]
    assumptions: list[str]
    provenance: Provenance
    limitations: list[str]


class MetricDelta(Tolerant):
    absolute: float
    relative: float | None = None


class AttributionEntry(Tolerant):
    intervention: str
    detail: dict[str, Any]
    deltas: dict[str, MetricDelta | dict[str, MetricDelta]]
    explanation: str


class ComparisonResponse(Tolerant):
    model_version: str
    input_hash: str
    seed: int
    baseline: SimulationResponse
    treatment: SimulationResponse
    deltas: dict[str, Any]
    key_metric_deltas: dict[str, Any]
    attribution: list[AttributionEntry]
    explanations: list[str]


class PlanStep(Tolerant):
    action: str
    detail: dict[str, Any]
    start_hour: int
    effective_hour: int
    marginal_gain_resilience: float | None
    resilience_index: float
    reason: str


class ReferencePlan(Tolerant):
    name: str
    resilience_index: float | None
    actions: list[str]


class PlanResponse(Tolerant):
    model_version: str
    input_hash: str
    seed: int
    label: str
    action_plan: list[PlanStep]
    score: dict[str, Any]
    references: list[ReferencePlan]
    search_stats: dict[str, Any]
    failure_points_before: list[FailurePoint]
    failure_points_after: list[FailurePoint]
    assumptions: list[str]
    provenance: Provenance
    limitations: list[str]


class ScenarioInfo(Tolerant):
    model_version: str
    presets: dict[str, Any]
    ranges: dict[str, Any]
    assumptions: list[str]
    limitations: list[str]
