"""Staffing step (B3 step 5): availability, staffed capacity, required, shortfall.

Nurses are integers; ratios are patients per nurse. Reallocation and recall
enter as pre-computed net effects from interventions.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import HospitalConfig

UNITS = ("ed", "ward", "icu")


@dataclass(frozen=True)
class StaffOutcome:
    """Per-unit staffing for one hour (integer nurses / patients)."""

    available: dict[str, int]
    staffed_capacity: dict[str, int]
    required: dict[str, int]
    shortfall: dict[str, int]


def compute_staffing(
    cfg: HospitalConfig,
    staff_availability_fraction: float,
    staff_access_fraction: float,
    occupied_prev: dict[str, int],
    net_reallocation: dict[str, int],
    recalled: dict[str, int],
) -> StaffOutcome:
    """One hourly staffing step following B3 step 5 exactly.

    ``occupied_prev`` maps unit -> patients occupying that unit at the start
    of the hour (ED counts in-service plus boarders).
    """
    available: dict[str, int] = {}
    staffed_capacity: dict[str, int] = {}
    required: dict[str, int] = {}
    shortfall: dict[str, int] = {}
    for unit in UNITS:
        roster = cfg.nurse_roster(unit)
        ppn = cfg.patients_per_nurse(unit)
        avail = int(math.floor(roster * staff_availability_fraction * staff_access_fraction)) \
            + net_reallocation.get(unit, 0) + recalled.get(unit, 0)
        avail = max(0, avail)
        available[unit] = avail
        staffed_capacity[unit] = int(math.floor(avail * ppn))
        req = int(math.ceil(occupied_prev.get(unit, 0) / ppn))
        required[unit] = req
        shortfall[unit] = max(0, req - avail)
    return StaffOutcome(available=available, staffed_capacity=staffed_capacity,
                        required=required, shortfall=shortfall)
