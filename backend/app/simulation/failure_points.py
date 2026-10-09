"""Critical failure-point analysis (B11): hourly margins, binding constraint,
ranked failure episodes and cascade detection.

Margins are raw plus normalised 0-1 (zero denominator counts as zero margin;
never NaN). A failure point is the first hour a margin reaches 0 or any alert
rule R01-R11 reaches high/critical severity.
"""

from __future__ import annotations

from typing import Any

MARGIN_ORDER = ("power", "supplies", "staff", "beds", "ed_flow")

# Coupling table: parent rule -> child rules it can cascade into
# (documented in docs/equations.md).
COUPLINGS: dict[str, tuple[str, ...]] = {
    "R06": ("R01", "R02"),   # critical power at risk -> ED/ICU derate -> bed margin
    "R11": ("R01", "R02"),   # supply stockout -> ED/ICU derate -> bed margin
    "R04": ("R01", "R02"),   # staff shortfall -> staffed capacity -> bed margin
    "R01": ("R03",),         # ward bed margin -> ED boarding
    "R02": ("R03",),         # ICU bed margin -> ED boarding
    "R09": ("R05",),         # fuel exhaustion -> power deficit
}

MARGIN_RULE = {"power": "R05", "supplies": "R10", "staff": "R04", "beds": "R01", "ed_flow": "R03"}
SEVERITY_RANK = {"warning": 1, "high": 2, "critical": 3}


def _safe_div(numerator: float, denominator: float) -> float:
    """0-1 margin; a zero denominator counts as zero margin (never NaN)."""
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def hourly_margins(row: dict[str, Any]) -> dict[str, float]:
    """Normalised 0-1 margins for one hourly row (B11)."""
    units = row["units"]
    power = row["power"]

    bed_margins = []
    for u in ("ward", "icu"):
        usable = units[u]["usable_beds"]
        bed_margins.append(_safe_div(usable - units[u]["occupied"], usable))
    bed = min(bed_margins)

    ed = units["ed"]
    ed_usable = ed["usable_beds"]
    ed_flow = _safe_div(ed_usable - ed["occupied"], ed_usable)

    staff_margins = []
    for u in ("ed", "ward", "icu"):
        req = row["staffing"][u]["required"]
        avail = row["staffing"][u]["available"]
        staff_margins.append(_safe_div(avail - req, req))
    staff = min(staff_margins)

    supply = row["supply"]
    power_margin = _safe_div(power["available_supply_kw"] - power["demand_kw"], power["available_supply_kw"])
    critical_margin = _safe_div(power["available_supply_kw"] - power["critical_demand_kw"], power["available_supply_kw"])
    power_m = min(power_margin, critical_margin)

    fuel_hours = supply["fuel_hours"]
    fuel_low = supply["fuel_low_hours"]
    fuel_margin = min(1.0, _safe_div(fuel_hours, fuel_low)) if fuel_hours is not None else 1.0

    covers = supply["cover_hours"] or {}
    low_cover = supply["low_cover_hours"]
    if covers:
        supply_margin = min(min(1.0, _safe_div(c, low_cover)) for c in covers.values())
    else:
        supply_margin = 1.0

    return {
        "power": min(power_m, fuel_margin),
        "supplies": supply_margin,
        "staff": staff,
        "beds": bed,
        "ed_flow": ed_flow,
    }


def binding_constraint(margins: dict[str, float]) -> str:
    """Resource with the smallest margin; ties broken in fixed MARGIN_ORDER."""
    return min(MARGIN_ORDER, key=lambda r: (margins[r], MARGIN_ORDER.index(r)))


def _rule_active_in(row: dict[str, Any], rule_id: str) -> bool:
    """True when the alert rule fires (any severity) in this hourly row."""
    supply = row["supply"]
    units = row["units"]
    power = row["power"]
    if rule_id == "R01":
        return bool(units["ward"]["status"] in ("warn", "critical"))
    if rule_id == "R02":
        return bool(units["icu"]["status"] in ("warn", "critical"))
    if rule_id == "R03":
        boarding = row["ed"]["boarding_ward"] + row["ed"]["boarding_icu"]
        return bool(boarding >= supply["ed_boarding_warn"] or row["ed"]["waiting"] >= supply["ed_waiting_high"])
    if rule_id == "R04":
        return any(row["staffing"][u]["shortfall"] > 0 for u in ("ed", "ward", "icu"))
    if rule_id == "R05":
        return bool(power["deficit_kw"] > 0)
    if rule_id == "R06":
        return bool(power["critical_at_risk_kw"] > 0)
    if rule_id == "R07":
        return bool(power["deficit_kw"] == 0 and supply["reserve_pct"] is not None
                    and supply["reserve_pct"] < supply["reserve_low_pct"])
    if rule_id == "R08":
        return bool(power["gen_output_kw"] > 0 and supply["fuel_hours"] is not None
                    and supply["fuel_hours"] < supply["fuel_low_hours"])
    if rule_id == "R09":
        return bool(power["fuel_l"] <= 0 and power["demand_kw"] > power["grid_supply_kw"])
    if rule_id == "R10":
        return bool(supply["supply_low"])
    if rule_id == "R11":
        return bool(supply["stockout"])
    return False


def _rule_severity_in(row: dict[str, Any], rule_id: str) -> str | None:
    """Peak severity of the rule in this row (None when inactive)."""
    if not _rule_active_in(row, rule_id):
        return None
    if rule_id == "R01":
        return "critical" if row["units"]["ward"]["occupancy_pct"] is not None and row["units"]["ward"]["occupancy_pct"] >= 100 else "high"
    if rule_id == "R02":
        return "critical" if row["units"]["icu"]["occupancy_pct"] is not None and row["units"]["icu"]["occupancy_pct"] >= 100 else "high"
    if rule_id == "R03":
        if row["ed"]["waiting"] >= row["supply"]["ed_waiting_high"]:
            return "high"
        return "warning"
    if rule_id == "R04":
        return "high" if any(row["units"][u]["beds_over_usable"] > 0 for u in ("ed", "ward", "icu")) else "warning"
    if rule_id == "R05":
        return "high"
    if rule_id == "R06":
        return "critical"
    if rule_id == "R07":
        return "warning"
    if rule_id == "R08":
        return "high"
    if rule_id == "R09":
        return "critical"
    if rule_id == "R10":
        return "high"
    if rule_id == "R11":
        return "critical"
    return "warning"


FAILURE_RESOURCE_RULES = {
    "power": ("R05", "R06", "R08", "R09"),
    "supplies": ("R10", "R11"),
    "staff": ("R04",),
    "beds": ("R01", "R02"),
    "ed_flow": ("R03",),
}


def failure_rule_for_margin(resource: str, row: dict[str, Any]) -> str:
    """Map a zero margin to its most severe active rule (or the default)."""
    for rule_id in FAILURE_RESOURCE_RULES[resource]:
        if _rule_active_in(row, rule_id):
            return rule_id
    return MARGIN_RULE[resource]


def analyze_failure_points(rows: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ranked failure episodes plus cascade/summary metadata (B11).

    Returns (failure_points, summary_extras) where summary_extras holds
    time_to_first_failure_hours, root_failures and cascade_children counts.
    """
    episodes: dict[tuple[str, str], dict[str, Any]] = {}
    margins_by_hour: list[dict[str, float]] = []
    for row in rows:
        stored = row.get("margins")
        margins: dict[str, float] = dict(stored) if isinstance(stored, dict) else hourly_margins(row)
        margins_by_hour.append(margins)
        for resource, margin in margins.items():
            if margin <= 0.0:
                rule_id = failure_rule_for_margin(resource, row)
                key = (resource, rule_id)
                ep: dict[str, Any] = episodes.setdefault(key, {
                    "resource": resource, "rule_id": rule_id, "first_hour": row["hour"],
                    "last_hour": row["hour"], "peak_severity": "high", "hours": [], "margin_trace": [],
                    "min_margin": 1.0,
                })
                ep["last_hour"] = row["hour"]
                ep["hours"].append(row["hour"])
                ep["margin_trace"].append({"hour": row["hour"], "margin": round(margin, 4)})
                ep["min_margin"] = min(ep["min_margin"], margin)

    # episodes from high/critical alert hours even when margins stay positive
    for alert in alerts:
        if SEVERITY_RANK.get(alert["severity"], 0) < 2:
            continue
        key = (alert["affected_variable"], alert["rule_id"])
        existing = episodes.get(key)
        if existing is None:
            new_ep: dict[str, Any] = {"resource": alert["affected_variable"], "rule_id": alert["rule_id"],
                                      "first_hour": alert["first_hour"], "last_hour": alert["last_hour"],
                                      "peak_severity": alert["severity"], "hours": [], "margin_trace": [],
                                      "min_margin": 1.0}
            episodes[key] = new_ep
            ep = new_ep
        else:
            ep = existing
        for h in range(alert["first_hour"], alert["last_hour"] + 1):
            if h < len(margins_by_hour):
                ep["margin_trace"].append({"hour": h, "margin": round(margins_by_hour[h].get(ep["resource"], 0.0), 4)})
        ep["peak_severity"] = max(ep["peak_severity"], alert["severity"], key=lambda s: SEVERITY_RANK.get(s, 0))
        ep["last_hour"] = max(ep["last_hour"], alert["last_hour"])

    ordered = sorted(episodes.values(), key=lambda e: (e["first_hour"], -SEVERITY_RANK.get(e["peak_severity"], 0), e["resource"], e["rule_id"]))
    failure_points: list[dict[str, Any]] = []
    for rank, ep in enumerate(ordered, start=1):
        failure_points.append({
            "rank": rank,
            "resource": ep["resource"],
            "rule_id": ep["rule_id"],
            "first_hour": ep["first_hour"],
            "last_hour": ep["last_hour"],
            "peak_severity": ep["peak_severity"],
            "margin_trace": sorted(ep["margin_trace"], key=lambda m: m["hour"]),
            "explanation": _explain(ep),
            "cascade_parent": None,
            "cascade_children": [],
        })

    # cascade detection: parent rule active in the hour before the child
    # episode started and the parent failed earlier.
    for child in failure_points:
        for parent in failure_points:
            if parent is child or parent["first_hour"] >= child["first_hour"]:
                continue
            if child["rule_id"] not in COUPLINGS.get(parent["rule_id"], ()):
                continue
            if (child["first_hour"] - 1) in range(parent["first_hour"], parent["last_hour"] + 1) or \
               (child["first_hour"] in range(parent["first_hour"], parent["last_hour"] + 1)):
                child["cascade_parent"] = parent["rule_id"]
                parent["cascade_children"].append(child["rule_id"])
                break

    roots = sum(1 for f in failure_points if f["cascade_parent"] is None)
    children = len(failure_points) - roots
    first_failure = None
    if failure_points:
        first = min(f["first_hour"] for f in failure_points)
        first_ep = min((f for f in failure_points if f["first_hour"] == first),
                       key=lambda f: -SEVERITY_RANK.get(f["peak_severity"], 0))
        first_failure = {"rule_id": first_ep["rule_id"], "hour": first_ep["first_hour"], "resource": first_ep["resource"]}
    summary_extras = {
        "first_failure": first_failure,
        "time_to_first_failure_hours": first_failure["hour"] if first_failure else None,
        "root_failures": roots,
        "cascade_children": children,
    }
    return failure_points, summary_extras


def _explain(ep: dict[str, Any]) -> str:
    """Template explanation referencing only computed values."""
    resource_text = {
        "power": "power supply could not cover demand",
        "supplies": "supply cover fell below the low-cover threshold",
        "staff": "required nurses exceeded available nurses",
        "beds": "occupied beds reached usable capacity",
        "ed_flow": "ED bays and boarding filled, blocking new flow",
    }
    return (f"{ep['resource'].replace('_', ' ').capitalize()} failure from hour {ep['first_hour']} to "
            f"{ep['last_hour']}: {resource_text.get(ep['resource'], ep['resource'])} (rule {ep['rule_id']}).")
