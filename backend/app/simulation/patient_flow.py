"""Patient flow step (B3 step 8): arrivals, ED service, boarding, admissions,
discharges. Integer patients throughout; deterministic mode uses carry-forward
rounding, stochastic mode uses seeded Binomial/Poisson samplers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import HospitalConfig
from .flow import CarryForward, StochasticFlows, split_cohorts
from .state import EdState

UNITS = ("ed", "ward", "icu")


@dataclass
class FlowAccumulators:
    """Carry-forward residuals for deterministic integer flows.

    One accumulator per flow so rounding residue persists across hours
    without drift; sums always match the underlying expected totals.
    """

    arrivals: CarryForward = field(default_factory=CarryForward)
    complete_nonadmit: CarryForward = field(default_factory=CarryForward)
    complete_ward_admit: CarryForward = field(default_factory=CarryForward)
    complete_icu_admit: CarryForward = field(default_factory=CarryForward)
    discharge_ward: CarryForward = field(default_factory=CarryForward)
    discharge_icu: CarryForward = field(default_factory=CarryForward)

    ward_split: CarryForward = field(default_factory=CarryForward)
    icu_split: CarryForward = field(default_factory=CarryForward)


@dataclass(frozen=True)
class FlowResult:
    """Outcome of one hourly patient-flow step (integer patients)."""

    ed: EdState
    ward_occupied: int
    icu_occupied: int
    arrivals: int
    admitted_ward: int
    admitted_icu: int
    discharged: int


def step_patient_flow(
    cfg: HospitalConfig,
    ed: EdState,
    ward_occupied: int,
    icu_occupied: int,
    usable_ed: int,
    usable_ward: int,
    usable_icu: int,
    arrivals_expected: float,
    los_multiplier: float,
    acc: FlowAccumulators,
    stochastic: StochasticFlows | None,
) -> FlowResult:
    """One hourly patient-flow step following B3 step 8 order (a)-(e).

    ``usable_*`` are the usable bed counts from B3 step 7. Returns the
    updated ED cohorts, inpatient occupancy and per-hour integer counts.
    """
    # (a) arrivals join ed_waiting
    if stochastic is not None:
        arrivals = stochastic.arrivals(arrivals_expected)
    else:
        arrivals = acc.arrivals.draw(arrivals_expected)
    ed.waiting += arrivals

    # (b) free ED bays take waiting patients, split into cohorts
    occupied_bays_start = ed.occupied_bays
    free_bays = max(0, usable_ed - occupied_bays_start)
    take = min(ed.waiting, free_bays)
    ed.waiting -= take
    if stochastic is not None:
        non_admit, ward_admit, icu_admit = stochastic.split_cohorts(take, cfg.arrivals.p_admit_ward, cfg.arrivals.p_admit_icu)
    else:
        non_admit, ward_admit, icu_admit = split_cohorts(
            take, cfg.arrivals.p_admit_ward, cfg.arrivals.p_admit_icu, acc.ward_split, acc.icu_split)
    ed.in_service += non_admit
    ed.in_service_ward += ward_admit
    ed.in_service_icu += icu_admit

    # (c) each cohort completes service at rate 1/los_hours
    ed_rate = 1.0 / cfg.ed.los_hours if cfg.ed.los_hours > 0 else 0.0
    done_non = _draw(acc.complete_nonadmit, ed.in_service, ed_rate, stochastic)
    done_non = min(done_non, ed.in_service)
    ed.in_service -= done_non
    done_w = _draw(acc.complete_ward_admit, ed.in_service_ward, ed_rate, stochastic)
    done_w = min(done_w, ed.in_service_ward)
    ed.in_service_ward -= done_w
    ed.boarding_ward += done_w
    done_i = _draw(acc.complete_icu_admit, ed.in_service_icu, ed_rate, stochastic)
    done_i = min(done_i, ed.in_service_icu)
    ed.in_service_icu -= done_i
    ed.boarding_icu += done_i
    ed_discharged = done_non  # non-admit completions leave the hospital

    # (d) boarding patients enter ward or ICU when usable - occupied > 0
    admitted_ward = min(ed.boarding_ward, max(0, usable_ward - ward_occupied))
    ed.boarding_ward -= admitted_ward
    ward_occupied += admitted_ward
    admitted_icu = min(ed.boarding_icu, max(0, usable_icu - icu_occupied))
    ed.boarding_icu -= admitted_icu
    icu_occupied += admitted_icu

    # (e) ward and ICU discharges at rate 1/(alos * los_multiplier)
    ward_rate = 1.0 / (cfg.ward.alos_hours * los_multiplier) if cfg.ward.alos_hours > 0 else 0.0
    icu_rate = 1.0 / (cfg.icu.alos_hours * los_multiplier) if cfg.icu.alos_hours > 0 else 0.0
    dis_ward = _draw(acc.discharge_ward, ward_occupied, ward_rate, stochastic)
    dis_ward = min(dis_ward, ward_occupied)
    ward_occupied -= dis_ward
    dis_icu = _draw(acc.discharge_icu, icu_occupied, icu_rate, stochastic)
    dis_icu = min(dis_icu, icu_occupied)
    icu_occupied -= dis_icu

    discharged = ed_discharged + dis_ward + dis_icu
    return FlowResult(ed=ed, ward_occupied=ward_occupied, icu_occupied=icu_occupied,
                      arrivals=arrivals, admitted_ward=admitted_ward, admitted_icu=admitted_icu,
                      discharged=discharged)


def _draw(acc: CarryForward, cohort: int, rate: float, stochastic: StochasticFlows | None) -> int:
    """Expected completions from a cohort this hour, as an integer."""
    if cohort <= 0:
        return 0
    if stochastic is not None:
        return stochastic.completions(cohort, rate)
    return acc.draw(cohort * rate)
