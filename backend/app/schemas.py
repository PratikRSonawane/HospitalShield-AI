"""Pydantic v2 API schemas: strict validation at the boundary (rule 10).

extra="forbid" everywhere, explicit bounds from B5, cross-field validators
for window fitting. These models mirror the engine's ScenarioSpec.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScenarioName = Literal["normal_operations", "heatwave_power_stress",
                       "heatwave_power_outage", "flood_storm_access"]
UnitName = Literal["ed", "ward", "icu"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WeatherIn(StrictModel):
    mode: Literal["synthetic_profile"] = "synthetic_profile"
    max_temperature_c: float = Field(default=41, ge=-10, le=55)
    min_temperature_c: float | None = Field(default=None, ge=-10, le=55)
    humidity_pct: float = Field(default=55, ge=0, le=100)

    @model_validator(mode="after")
    def _min_le_max(self) -> WeatherIn:
        if self.min_temperature_c is not None and self.min_temperature_c > self.max_temperature_c:
            raise ValueError("weather.min_temperature_c must be <= max_temperature_c")
        return self


class StressIn(StrictModel):
    arrival_multiplier: float = Field(default=1.25, ge=0, le=3)
    los_multiplier: float = Field(default=1.0, ge=0.5, le=2)
    staff_availability_fraction: float = Field(default=0.9, ge=0, le=1)
    power_supply_fraction: float = Field(default=0.8, ge=0, le=1)


class OutageIn(StrictModel):
    start_hour: int = Field(default=24, ge=0, le=71)
    duration_hours: int = Field(default=36, ge=0, le=72)
    grid_fraction: float = Field(default=0.0, ge=0, le=1)


class AccessIn(StrictModel):
    start_hour: int = Field(default=18, ge=0, le=71)
    duration_hours: int = Field(default=24, ge=0, le=72)
    staff_access_fraction: float = Field(default=0.6, ge=0, le=1)
    delivery_fraction: float = Field(default=0.25, ge=0, le=1)
    arrival_multiplier: float = Field(default=1.4, ge=0, le=3)


class BackupIn(StrictModel):
    generator_availability_fraction: float = Field(default=1.0, ge=0, le=1)


class SurgeIn(StrictModel):
    unit: UnitName
    beds: int = Field(ge=0, le=1000)
    start_hour: int = Field(ge=0, le=71)


class StaffMoveIn(StrictModel):
    from_unit: UnitName
    to_unit: UnitName
    nurses: int = Field(ge=0, le=1000)
    start_hour: int = Field(ge=0, le=71)


class ShedIn(StrictModel):
    kw: float = Field(ge=0, le=10000)
    start_hour: int = Field(ge=0, le=71)
    end_hour: int = Field(ge=0, le=72)


class RecallIn(StrictModel):
    unit: UnitName
    nurses: int = Field(ge=0, le=1000)
    start_hour: int = Field(ge=0, le=71)


class ResupplyIn(StrictModel):
    fuel_l: float = Field(default=0.0, ge=0, le=100000)
    items: dict[str, float] = Field(default_factory=dict)
    start_hour: int = Field(default=0, ge=0, le=71)


class InterventionsIn(StrictModel):
    activate_surge_beds: list[SurgeIn] = Field(default_factory=list)
    reallocate_staff: list[StaffMoveIn] = Field(default_factory=list)
    reduce_noncritical_load_kw: list[ShedIn] = Field(default_factory=list)
    recall_staff: list[RecallIn] = Field(default_factory=list)
    emergency_resupply: list[ResupplyIn] = Field(default_factory=list)


class SimulationRequest(StrictModel):
    scenario: ScenarioName
    duration_hours: int = Field(default=72, ge=1, le=72)
    weather: WeatherIn = Field(default_factory=WeatherIn)
    stress: StressIn = Field(default_factory=StressIn)
    outage: OutageIn | None = None
    access: AccessIn | None = None
    backup: BackupIn = Field(default_factory=BackupIn)
    interventions: InterventionsIn | None = None
    stochastic: bool = False
    seed: int = Field(default=42, ge=0, le=2147483647)

    @model_validator(mode="after")
    def _windows_fit(self) -> SimulationRequest:
        if self.outage is not None and self.outage.start_hour + self.outage.duration_hours > self.duration_hours:
            raise ValueError("outage window (start_hour + duration_hours) must fit within duration_hours")
        if self.access is not None and self.access.start_hour + self.access.duration_hours > self.duration_hours:
            raise ValueError("access window (start_hour + duration_hours) must fit within duration_hours")
        if self.interventions is not None:
            for shed in self.interventions.reduce_noncritical_load_kw:
                if shed.end_hour <= shed.start_hour:
                    raise ValueError("reduce_noncritical_load_kw end_hour must be after start_hour")
                if shed.end_hour > self.duration_hours:
                    raise ValueError("reduce_noncritical_load_kw end_hour beyond horizon")
        return self

    def to_engine_dict(self) -> dict[str, Any]:
        """Canonical dict for the engine and the input hash."""
        data = self.model_dump()
        if data.get("access") is not None:
            acc = data["access"]
            data["access"] = {"start_hour": acc["start_hour"], "duration_hours": acc["duration_hours"],
                              "staff_access_fraction": acc["staff_access_fraction"],
                              "delivery_fraction": acc["delivery_fraction"],
                              "arrival_multiplier": acc["arrival_multiplier"]}
        return data


class ComparisonRequest(SimulationRequest):
    pass


class PlannerObjectiveIn(StrictModel):
    lambda_burden: float = Field(default=0.5, ge=0, le=10)


class PlannerBudgetIn(StrictModel):
    max_simulations: int = Field(default=600, ge=10, le=5000)
    max_seconds: float = Field(default=5.0, ge=0.5, le=60)
    max_actions: int = Field(default=5, ge=1, le=10)
    grid_hours: int = Field(default=3, ge=1, le=24)


class PlanRequest(SimulationRequest):
    objective: PlannerObjectiveIn = Field(default_factory=PlannerObjectiveIn)
    budget: PlannerBudgetIn = Field(default_factory=PlannerBudgetIn)
