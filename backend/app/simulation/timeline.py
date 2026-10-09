"""Per-hour resolution of interventions (B3 step 3, B6).

The timeline precomputes, for every hour of the horizon, the active surge
beds, net staff reallocation, recalled nurses, requested shed kW and
resupply arrivals. Recall scaling uses staff_access_fraction at the arrival
hour (one-off decision documented in docs/assumptions.md).
"""

from __future__ import annotations

import math
from typing import Any

from .config import HospitalConfig
from .interventions import InterventionsSpec
from .scenario import ScenarioSpec, staff_access_fraction_at


class InterventionTimeline:
    """Precomputed hourly intervention effects (O(T) build, O(1) lookup)."""

    def __init__(self, spec: InterventionsSpec, cfg: HospitalConfig, scenario: ScenarioSpec) -> None:
        t = scenario.duration_hours
        self.t = t
        self.surge_open: list[dict[str, int]] = [{"ed": 0, "ward": 0, "icu": 0} for _ in range(t)]
        for act in spec.activate_surge_beds:
            effective = act.start_hour + cfg.surge.activation_delay_hours
            for h in range(max(0, effective), t):
                self.surge_open[h][act.unit] += act.beds

        self.net_reallocation: list[dict[str, int]] = [{u: 0 for u in ("ed", "ward", "icu")} for _ in range(t)]
        for mv in spec.reallocate_staff:
            for h in range(max(0, mv.start_hour), t):
                self.net_reallocation[h][mv.from_unit] -= mv.nurses
                self.net_reallocation[h][mv.to_unit] += mv.nurses

        self.recalled: list[dict[str, int]] = [{u: 0 for u in ("ed", "ward", "icu")} for _ in range(t)]
        for rec in spec.recall_staff:
            arrival = rec.start_hour + cfg.recall.lead_time_hours
            for h in range(max(0, arrival), t):
                scaled = int(math.floor(rec.nurses * staff_access_fraction_at(scenario, arrival)))
                self.recalled[h][rec.unit] += scaled

        self.shed_kw: list[float] = [0.0] * t
        for shed in spec.reduce_noncritical_load:
            for h in range(max(0, shed.start_hour), min(t, shed.end_hour)):
                self.shed_kw[h] += shed.kw

        self.fuel_resupply_l: list[float] = [0.0] * t
        self.item_resupply: list[dict[str, float]] = [{} for _ in range(t)]
        for res in spec.emergency_resupply:
            arrival = res.start_hour + cfg.supplies.emergency_lead_time_hours
            if arrival >= t:
                continue
            dfrac = _delivery_fraction_at_hour(scenario, arrival)
            self.fuel_resupply_l[arrival] += res.fuel_l * dfrac
            for item, amount in res.items.items():
                self.item_resupply[arrival][item] = self.item_resupply[arrival].get(item, 0.0) + amount * dfrac

        self.resupply_hours = {h for h in range(t)
                               if self.fuel_resupply_l[h] > 0 or self.item_resupply[h]}

    def at(self, hour: int) -> dict[str, Any]:
        """All active intervention effects for one hour."""
        h = min(max(hour, 0), self.t - 1)
        return {
            "surge_open": self.surge_open[h],
            "net_reallocation": self.net_reallocation[h],
            "recalled": self.recalled[h],
            "shed_kw": self.shed_kw[h],
            "fuel_resupply_l": self.fuel_resupply_l[h],
            "item_resupply": self.item_resupply[h],
        }


def _delivery_fraction_at_hour(scenario: ScenarioSpec, hour: int) -> float:
    """Delivery fraction at a specific hour (1.0 outside the access window)."""
    access = scenario.access
    if access and access.start_hour <= hour < access.start_hour + access.duration_hours:
        return access.delivery_fraction
    return 1.0
