"""Alert rules R01-R11 (B8) merged into traceable episodes.

Each episode carries rule_id, rule_text, severity, metric, unit,
observed_peak, threshold, first_hour, last_hour, duration_hours and
affected_variable. Consecutive hours of the same rule (and metric) merge
into one episode; severity is the peak observed during the episode.
"""

from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"warning": 0, "high": 1, "critical": 2}

SEVERITY_RANK = {"warning": 1, "high": 2, "critical": 3}


def _add_hour(buckets: dict[tuple[str, str], list[dict[str, Any]]], row: dict[str, Any],
              rule_id: str, rule_text: str, severity: str, metric: str, unit: str,
              observed: float, threshold: float, affected: str) -> None:
    buckets.setdefault((rule_id, metric), []).append({
        "rule_id": rule_id, "rule_text": rule_text, "severity": severity, "metric": metric,
        "unit": unit, "observed": observed, "threshold": threshold, "hour": row["hour"],
        "affected_variable": affected,
    })


def collect_alert_hours(cfg: Any, rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Evaluate R01-R11 on every hourly row; bucket hours per (rule, metric)."""
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    thr = cfg.thresholds
    for row in rows:
        units = row["units"]
        power = row["power"]
        supply = row["supply"]
        staffing = row["staffing"]
        ed = row["ed"]

        for rule_id, uname, label in (("R01", "ward", "ward"), ("R02", "icu", "ICU")):
            occ = units[uname]["occupancy_pct"]
            if occ is not None and occ >= thr.occupancy_warn_pct:
                sev = "critical" if occ >= 100 else "high"
                _add_hour(buckets, row, rule_id, f"{label}_occupancy_high", sev, "occupancy_pct", "pct",
                          round(occ, 2), thr.occupancy_warn_pct, uname)

        boarding = ed["boarding_ward"] + ed["boarding_icu"]
        if boarding >= thr.ed_boarding_warn:
            _add_hour(buckets, row, "R03", "ed_boarding", "warning", "ed_boarding", "patients",
                      boarding, thr.ed_boarding_warn, "ed")
        if ed["waiting"] >= thr.ed_waiting_high:
            _add_hour(buckets, row, "R03", "ed_waiting", "high", "ed_waiting", "patients",
                      ed["waiting"], thr.ed_waiting_high, "ed")

        for uname in ("ed", "ward", "icu"):
            if staffing[uname]["shortfall"] > 0:
                _add_hour(buckets, row, "R04", "staffing_shortfall", "warning", "shortfall_nurses", "nurses",
                          staffing[uname]["shortfall"], 0, uname)
            if units[uname]["beds_over_usable"] > 0:
                _add_hour(buckets, row, "R04", "staffing_shortfall", "high", "beds_over_usable", "beds",
                          units[uname]["beds_over_usable"], 0, uname)

        if power["deficit_kw"] > 0:
            _add_hour(buckets, row, "R05", "power_deficit", "high", "power_deficit_kw", "kW",
                      round(power["deficit_kw"], 2), 0, "power")
        if power["critical_at_risk_kw"] > 0:
            _add_hour(buckets, row, "R06", "critical_load_at_risk", "critical", "critical_at_risk_kw", "kW",
                      round(power["critical_at_risk_kw"], 2), 0, "power")
        if power["deficit_kw"] == 0 and supply["reserve_pct"] is not None and supply["reserve_pct"] < thr.reserve_low_pct:
            _add_hour(buckets, row, "R07", "reserve_low", "warning", "reserve_pct", "pct",
                      round(supply["reserve_pct"], 2), thr.reserve_low_pct, "power")
        if power["gen_output_kw"] > 0 and supply["fuel_hours"] is not None and supply["fuel_hours"] < thr.fuel_low_hours:
            _add_hour(buckets, row, "R08", "fuel_low", "high", "fuel_hours", "hours",
                      round(supply["fuel_hours"], 2), thr.fuel_low_hours, "fuel")
        if power["fuel_l"] <= 0 and power["demand_kw"] > power["grid_supply_kw"]:
            _add_hour(buckets, row, "R09", "fuel_exhausted", "critical", "fuel_l", "litres",
                      round(power["fuel_l"], 2), 0, "fuel")

        for item, cover in supply["cover_hours"].items():
            if cover is not None and cover < cfg.supplies.low_cover_hours:
                _add_hour(buckets, row, "R10", "supply_low", "high", "cover_hours", "hours",
                          round(cover, 2), cfg.supplies.low_cover_hours, item)
        for item in cfg.supplies.items:
            if supply["stockout"].get(item):
                _add_hour(buckets, row, "R11", "supply_stockout", "critical", "stock_units", "units",
                          round(row["supplies"][item]["stock"], 2), 0, item)
    return buckets


def build_alert_episodes(cfg: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive hours of the same (rule, metric) into episodes (B8)."""
    episodes: list[dict[str, Any]] = []
    for (rule_id, metric), hours in collect_alert_hours(cfg, rows).items():
        runs: list[list[dict[str, Any]]] = []
        for entry in sorted(hours, key=lambda e: e["hour"]):
            if runs and entry["hour"] == runs[-1][-1]["hour"] + 1:
                runs[-1].append(entry)
            else:
                runs.append([entry])
        for run in runs:
            peak = max(run, key=lambda e: (SEVERITY_ORDER.get(e["severity"], 0), e["observed"]))
            episodes.append({
                "rule_id": rule_id,
                "rule_text": run[0]["rule_text"],
                "severity": peak["severity"],
                "metric": metric,
                "unit": run[0]["unit"],
                "observed_peak": round(max(e["observed"] for e in run), 2),
                "threshold": run[0]["threshold"],
                "first_hour": run[0]["hour"],
                "last_hour": run[-1]["hour"],
                "duration_hours": run[-1]["hour"] - run[0]["hour"] + 1,
                "affected_variable": run[0]["affected_variable"],
            })
    episodes.sort(key=lambda a: (a["first_hour"], -SEVERITY_ORDER.get(a["severity"], 0), a["rule_id"]))
    return episodes
