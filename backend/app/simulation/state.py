"""Simulation state: ED cohorts, running totals and per-unit row builders.

Every field carries its unit in the name. Percentages are 0-100, fractions
0-1, power kW, energy kWh, fuel litres, stock in supply units. Nullable
numeric fields return None (never NaN) when the value is undefined, e.g.
occupancy when usable beds are zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EdState:
    """ED patient cohorts (integer patients)."""

    waiting: int = 0
    in_service: int = 0          # non-admit cohort occupying bays
    in_service_ward: int = 0     # ward-admits still being processed in bays
    in_service_icu: int = 0      # ICU-admits still being processed in bays
    boarding_ward: int = 0       # ward-admitted patients holding an ED bay
    boarding_icu: int = 0

    @property
    def occupied_bays(self) -> int:
        """Patients currently occupying ED bays (in service plus boarders)."""
        return self.in_service + self.in_service_ward + self.in_service_icu + self.boarding_ward + self.boarding_icu

    @property
    def total_in_service(self) -> int:
        """All patients currently in ED service (any cohort)."""
        return self.in_service + self.in_service_ward + self.in_service_icu


@dataclass
class RunState:
    """Mutable simulation state carried across hours (frozen rows are emitted)."""

    ward_occupied: int
    icu_occupied: int
    fuel_l: float
    stock: dict[str, float]
    ed: EdState = field(default_factory=EdState)
    discharged_total: int = 0
    arrived_total: int = 0

    def weighted_occupied(self, icu_weight: float, ed_weight: float) -> float:
        """Supply-consumption weight (weighted beds) from current occupancy.

        ED patients in bays (in service and boarders) all consume supplies.
        """
        return self.ward_occupied + self.icu_occupied * icu_weight + self.ed.occupied_bays * ed_weight


def unit_status(occupancy_pct: float | None, beds_over: int) -> str:
    """Backend-computed status string: ok / warn / critical / unavailable.

    warn at or above the configured occupancy threshold, critical at or
    above 100 percent or when patients exceed usable beds.
    """
    if occupancy_pct is None:
        return "unavailable"
    if beds_over > 0 or occupancy_pct >= 100.0:
        return "critical"
    if occupancy_pct >= 90.0:
        return "warn"
    return "ok"


def make_unit_row(open_beds: int, usable: int, occupied: int) -> dict[str, int | float | str | None]:
    """Build one unit's row entry including backend-computed status."""
    occ: float | None = None
    if usable > 0:
        occ = min(100.0, 100.0 * occupied / usable)
    status = unit_status(occ, max(0, occupied - usable))
    return {
        "open_beds": open_beds,
        "usable_beds": usable,
        "occupied": occupied,
        "available_beds": max(0, usable - occupied),
        "occupancy_pct": occ,
        "beds_over_usable": max(0, occupied - usable),
        "status": status,
    }
