"""Invariant verification (B4). Verified on every hourly row; violations
raise InvariantViolationError (a bug, never bad input). Float equality uses
a 1e-6 tolerance; all other checks are exact.
"""

from __future__ import annotations

import math
from typing import Any

from .errors import InvariantViolationError

TOL = 1e-6


def _finite(value: Any, path: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        if not math.isfinite(value):
            raise InvariantViolationError(f"non-finite value at {path}")


def _walk_finite(obj: Any, path: str) -> None:
    """Finite check over known numeric fields (single pass, no recursion).

    Integer fields cannot be NaN; only float fields need isfinite. The
    targeted reads below cover every numeric field the engine emits.
    """
    h = obj["hour"]
    for key in ("critical_demand_kw", "noncritical_unshed_kw", "shed_kw", "demand_kw",
                "grid_supply_kw", "gen_available_kw", "gen_output_kw", "available_supply_kw",
                "deficit_kw", "reserve_kw", "critical_at_risk_kw", "fuel_l"):
        _finite(obj["power"][key], f"row{h}.power.{key}")
    for u in ("ed", "ward", "icu"):
        occ = obj["units"][u]["occupancy_pct"]
        if occ is not None:
            _finite(occ, f"row{h}.units.{u}.occupancy_pct")
        for k in ("open_beds", "usable_beds", "occupied", "available_beds", "beds_over_usable"):
            _finite(obj["units"][u][k], f"row{h}.units.{u}.{k}")
        for k in ("available", "staffed_capacity", "required", "shortfall"):
            _finite(obj["staffing"][u][k], f"row{h}.staffing.{u}.{k}")
    for item, srow in obj["supplies"].items():
        for k in ("stock", "delivered", "consumption", "unmet"):
            _finite(srow[k], f"row{h}.supplies.{item}.{k}")
        if srow["cover_hours"] is not None:
            _finite(srow["cover_hours"], f"row{h}.supplies.{item}.cover_hours")
    for k in ("waiting", "in_service", "boarding_ward", "boarding_icu", "arrivals",
              "admitted_ward", "admitted_icu"):
        _finite(obj["ed"][k], f"row{h}.ed.{k}")
    _finite(obj["weather"]["temperature_c"], f"row{h}.weather.temperature_c")
    _finite(obj["discharged"], f"row{h}.discharged")
    fh = obj["supply"]["fuel_hours"]
    if fh is not None:
        _finite(fh, f"row{h}.supply.fuel_hours")
    rp = obj["supply"]["reserve_pct"]
    if rp is not None:
        _finite(rp, f"row{h}.supply.reserve_pct")
    for m in obj.get("margins", {}).values():
        _finite(m, f"row{h}.margins")


def _non_negative(row: dict[str, Any]) -> None:
    h = row["hour"]
    for u in ("ed", "ward", "icu"):
        for key in ("open_beds", "usable_beds", "occupied", "available_beds", "beds_over_usable"):
            if row["units"][u][key] < 0:
                raise InvariantViolationError(f"hour {h}: negative {key} for {u}")
    for u in ("ed", "ward", "icu"):
        for key in ("available", "staffed_capacity", "required", "shortfall"):
            if row["staffing"][u][key] < 0:
                raise InvariantViolationError(f"hour {h}: negative {key} for {u}")
    power = row["power"]
    for key in ("demand_kw", "grid_supply_kw", "gen_available_kw", "gen_output_kw",
                "available_supply_kw", "deficit_kw", "reserve_kw", "critical_at_risk_kw",
                "fuel_l", "shed_kw"):
        if power[key] < -TOL:
            raise InvariantViolationError(f"hour {h}: negative {key}")
    for item, srow in row["supplies"].items():
        if srow["stock"] < -TOL:
            raise InvariantViolationError(f"hour {h}: negative stock for {item}")
    for key in ("waiting", "in_service", "boarding_ward", "boarding_icu", "arrivals",
                "admitted_ward", "admitted_icu"):
        if row["ed"][key] < 0:
            raise InvariantViolationError(f"hour {h}: negative ed.{key}")


def _percent_bounds(row: dict[str, Any]) -> None:
    h = row["hour"]
    for u in ("ed", "ward", "icu"):
        occ = row["units"][u]["occupancy_pct"]
        if occ is not None and not (-TOL <= occ <= 100.0 + TOL):
            raise InvariantViolationError(f"hour {h}: occupancy_pct {occ} out of 0-100 for {u}")
    reserve_pct = row["supply"]["reserve_pct"]
    if reserve_pct is not None and not (-TOL <= reserve_pct <= 1000.0 + TOL):
        raise InvariantViolationError(f"hour {h}: reserve_pct out of range")


def _power_rules(row: dict[str, Any], cfg: Any) -> None:
    h = row["hour"]
    p = row["power"]
    if p["deficit_kw"] > TOL and p["reserve_kw"] > TOL:
        raise InvariantViolationError(f"hour {h}: deficit and reserve both positive")
    if p["shed_kw"] > p["noncritical_unshed_kw"] + TOL:
        raise InvariantViolationError(f"hour {h}: shed exceeds non-critical demand")
    if p["gen_output_kw"] > cfg.power.generator_capacity_kw + TOL:
        raise InvariantViolationError(f"hour {h}: generator output exceeds capacity")
    if p["critical_demand_kw"] < cfg.power.critical_load_kw - TOL:
        raise InvariantViolationError(f"hour {h}: critical demand reduced below base load")


def _fuel_rules(rows: list[dict[str, Any]], resupply_hours: set[int], cfg: Any) -> None:
    for i in range(1, len(rows)):
        prev_fuel = rows[i - 1]["power"]["fuel_l"]
        cur = rows[i]["power"]["fuel_l"]
        h = rows[i]["hour"]
        if h in resupply_hours:
            if cur < prev_fuel - TOL and cur < rows[i]["power"].get("fuel_after_resupply_l", cur) - TOL:
                raise InvariantViolationError(f"hour {h}: fuel dropped despite resupply")
            continue
        if cur > prev_fuel + TOL:
            raise InvariantViolationError(f"hour {h}: fuel increased without resupply")
    if rows and rows[0]["power"]["fuel_l"] > cfg.power.fuel_litres + TOL:
        raise InvariantViolationError("hour 0: fuel above initial stock")


def _patient_conservation(row: dict[str, Any], arrived_total: int, discharged_total: int) -> None:
    ed = row["ed"]
    counted = (ed["waiting"] + ed["in_service"] + ed["boarding_ward"] + ed["boarding_icu"]
               + row["units"]["ward"]["occupied"] + row["units"]["icu"]["occupied"] + discharged_total)
    if counted != arrived_total:
        raise InvariantViolationError(
            f"hour {row['hour']}: patient conservation violated: {arrived_total} arrived vs {counted} counted")


def _supply_conservation(row: dict[str, Any], prev_stock: dict[str, float]) -> None:
    h = row["hour"]
    for item, srow in row["supplies"].items():
        change = srow["stock"] - prev_stock[item]
        expected = srow["delivered"] - srow["consumption"]
        if abs(change - expected) > 1e-4:
            raise InvariantViolationError(
                f"hour {h}: supply identity violated for {item}: change {change} vs delivered-consumption {expected}")


def _usable_bounds(row: dict[str, Any]) -> None:
    for u in ("ed", "ward", "icu"):
        if row["units"][u]["usable_beds"] > row["units"][u]["open_beds"]:
            raise InvariantViolationError(f"hour {row['hour']}: usable exceeds open beds for {u}")


def verify_row_invariants(row: dict[str, Any], cfg: Any, arrived_total: int,
                          discharged_total: int, prev_stock: dict[str, float]) -> None:
    """All per-row B4 invariants; raises InvariantViolationError on breach."""
    _walk_finite(row, f"row{row['hour']}")
    _non_negative(row)
    _percent_bounds(row)
    _power_rules(row, cfg)
    _usable_bounds(row)
    _patient_conservation(row, arrived_total, discharged_total)
    _supply_conservation(row, prev_stock)


def verify_series_invariants(rows: list[dict[str, Any]], cfg: Any, resupply_hours: set[int]) -> None:
    """Cross-row invariants: fuel behaviour (B4)."""
    _fuel_rules(rows, resupply_hours, cfg)
