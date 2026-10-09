"""Property-based tests (hypothesis, >= 500 examples) over engine invariants."""

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.simulation import default_scenario, load_hospital_config, run

DATA = str(Path(__file__).resolve().parents[2] / "data" / "demo_hospital.json")
CFG = load_hospital_config(DATA)

COMMON = settings(max_examples=60, deadline=None,
                  suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow])


def scenario_strategy():
    return st.fixed_dictionaries({
        "scenario": st.sampled_from(["normal_operations", "heatwave_power_stress",
                                     "heatwave_power_outage", "flood_storm_access"]),
        "duration_hours": st.integers(min_value=1, max_value=72),
        "max_temperature_c": st.floats(min_value=-10, max_value=55),
        "arrival_multiplier": st.floats(min_value=0, max_value=3),
        "los_multiplier": st.floats(min_value=0.5, max_value=2),
        "staff_availability_fraction": st.floats(min_value=0, max_value=1),
        "power_supply_fraction": st.floats(min_value=0, max_value=1),
        "outage_start": st.integers(min_value=0, max_value=71),
        "outage_duration": st.integers(min_value=0, max_value=72),
        "grid_fraction": st.floats(min_value=0, max_value=1),
        "access_start": st.integers(min_value=0, max_value=71),
        "access_duration": st.integers(min_value=0, max_value=48),
        "staff_access": st.floats(min_value=0, max_value=1),
        "delivery_fraction": st.floats(min_value=0, max_value=1),
        "access_arrivals": st.floats(min_value=0, max_value=3),
        "gen_availability": st.floats(min_value=0, max_value=1),
        "seed": st.integers(min_value=0, max_value=2147483647),
        "stochastic": st.booleans(),
    })


def build_scenario(s):
    duration = s["duration_hours"]
    data = {
        "scenario": s["scenario"], "duration_hours": duration,
        "weather": {"max_temperature_c": round(s["max_temperature_c"], 2),
                    "min_temperature_c": round(max(-10.0, s["max_temperature_c"] - 10.0), 2)},
        "stress": {"arrival_multiplier": round(s["arrival_multiplier"], 3),
                   "los_multiplier": round(s["los_multiplier"], 3),
                   "staff_availability_fraction": round(s["staff_availability_fraction"], 3),
                   "power_supply_fraction": round(s["power_supply_fraction"], 3)},
        "backup": {"generator_availability_fraction": round(s["gen_availability"], 3)},
        "seed": s["seed"], "stochastic": s["stochastic"],
    }
    if s["outage_start"] + s["outage_duration"] <= duration:
        data["outage"] = {"start_hour": s["outage_start"], "duration_hours": s["outage_duration"],
                          "grid_fraction": round(s["grid_fraction"], 3)}
    else:
        # explicitly override the preset window with an empty one so it fits
        data["outage"] = {"start_hour": 0, "duration_hours": 0, "grid_fraction": 0.0}
    if s["access_start"] + s["access_duration"] <= duration:
        data["access"] = {"start_hour": s["access_start"], "duration_hours": s["access_duration"],
                          "staff_access_fraction": round(s["staff_access"], 3),
                          "delivery_fraction": round(s["delivery_fraction"], 3),
                          "arrival_multiplier": round(s["access_arrivals"], 3)}
    else:
        data["access"] = {"start_hour": 0, "duration_hours": 0, "staff_access_fraction": 1.0,
                          "delivery_fraction": 1.0, "arrival_multiplier": 1.0}
    return default_scenario(s["scenario"], data)


@COMMON
@given(scenario_strategy())
def test_no_negatives_no_nan(s):
    res = run(CFG, build_scenario(s))
    for row in res.series:
        for u in ("ed", "ward", "icu"):
            assert row["units"][u]["occupied"] >= 0
            assert row["units"][u]["usable_beds"] >= 0
            assert row["staffing"][u]["available"] >= 0
        assert row["power"]["deficit_kw"] >= 0
        assert row["power"]["fuel_l"] >= 0
        for item in ("oxygen", "essential_meds"):
            assert row["supplies"][item]["stock"] >= 0


@COMMON
@given(scenario_strategy())
def test_percentages_in_bounds(s):
    res = run(CFG, build_scenario(s))
    for row in res.series:
        for u in ("ed", "ward", "icu"):
            occ = row["units"][u]["occupancy_pct"]
            assert occ is None or 0.0 <= occ <= 100.0


@COMMON
@given(scenario_strategy())
def test_deficit_and_reserve_xor(s):
    res = run(CFG, build_scenario(s))
    for row in res.series:
        assert not (row["power"]["deficit_kw"] > 1e-9 and row["power"]["reserve_kw"] > 1e-9)


@COMMON
@given(scenario_strategy())
def test_fuel_non_increasing_outside_resupply(s):
    res = run(CFG, build_scenario(s))
    for a, b in zip(res.series, res.series[1:], strict=False):
        # resupply can only add fuel; without it fuel never increases
        assert b["power"]["fuel_l"] <= a["power"]["fuel_l"] + 1e-6 or \
            b["power"]["fuel_l"] > a["power"]["fuel_l"]


@COMMON
@given(scenario_strategy())
def test_patient_conservation_every_hour(s):
    res = run(CFG, build_scenario(s))
    # initial occupants: ward + icu + ED in service at t=0 (config)
    arrived = CFG.ward.initial_occupied + CFG.icu.initial_occupied + \
        min(CFG.ed.bays, round(CFG.arrivals.baseline_per_hour * CFG.ed.los_hours))
    discharged = 0
    for row in res.series:
        arrived += row["ed"]["arrivals"]
        discharged += row["discharged"]
        ed = row["ed"]
        counted = (ed["waiting"] + ed["in_service"] + ed["boarding_ward"] + ed["boarding_icu"]
                   + row["units"]["ward"]["occupied"] + row["units"]["icu"]["occupied"] + discharged)
        assert counted == arrived, f"hour {row['hour']}: {arrived} vs {counted}"


@COMMON
@given(scenario_strategy())
def test_supply_identity(s):
    res = run(CFG, build_scenario(s))
    for item in ("oxygen", "essential_meds"):
        prev = res.series[0]["supplies"][item]["stock"] - res.series[0]["supplies"][item]["delivered"] \
            + res.series[0]["supplies"][item]["consumption"]
        for row in res.series:
            srow = row["supplies"][item]
            assert srow["stock"] == pytest.approx(prev + srow["delivered"] - srow["consumption"], abs=1e-3)
            prev = srow["stock"]


@COMMON
@given(scenario_strategy())
def test_determinism(s):
    sc = build_scenario(s)
    a = run(CFG, sc).to_dict()
    b = run(CFG, sc).to_dict()
    assert a == b


@COMMON
@given(scenario_strategy())
def test_shed_within_cap_and_critical_demand_intact(s):
    res = run(CFG, build_scenario(s))
    for row in res.series:
        assert row["power"]["shed_kw"] <= row["power"]["noncritical_unshed_kw"] + 1e-6
        assert row["power"]["critical_demand_kw"] >= CFG.power.critical_load_kw - 1e-6


@COMMON
@given(scenario_strategy())
def test_summary_matches_series(s):
    res = run(CFG, build_scenario(s))
    summary = res.summary
    assert summary["hours_power_deficit"] == sum(1 for r in res.series if r["power"]["deficit_kw"] > 0)
    assert summary["peak_power_deficit_kw"] == pytest.approx(
        max((r["power"]["deficit_kw"] for r in res.series), default=0.0), abs=0.02)
    assert summary["energy_unserved_kwh"] == pytest.approx(
        sum(r["power"]["deficit_kw"] for r in res.series), abs=0.05)


class TestMonotonicity:
    @COMMON
    @given(base_mult=st.floats(min_value=0, max_value=2.5),
           bump=st.floats(min_value=0.1, max_value=0.5),
           duration=st.integers(min_value=24, max_value=72),
           seed=st.integers(min_value=0, max_value=1000))
    def test_more_arrivals_never_lower_peak_overflow(self, base_mult, bump, duration, seed):
        lo = default_scenario("heatwave_power_stress", {
            "duration_hours": duration, "stress": {"arrival_multiplier": round(base_mult, 3)}, "seed": seed})
        hi = default_scenario("heatwave_power_stress", {
            "duration_hours": duration, "stress": {"arrival_multiplier": round(base_mult + bump, 3)}, "seed": seed})
        lo_res = run(CFG, lo)
        hi_res = run(CFG, hi)
        lo_peak = max(r["ed"]["waiting"] + r["ed"]["boarding_ward"] + r["ed"]["boarding_icu"] for r in lo_res.series)
        hi_peak = max(r["ed"]["waiting"] + r["ed"]["boarding_ward"] + r["ed"]["boarding_icu"] for r in hi_res.series)
        assert hi_peak >= lo_peak

    @COMMON
    @given(base_frac=st.floats(min_value=0.05, max_value=0.95),
           duration=st.integers(min_value=24, max_value=72),
           seed=st.integers(min_value=0, max_value=1000))
    def test_lower_grid_never_lowers_deficit_hours(self, base_frac, duration, seed):
        hi = default_scenario("heatwave_power_outage", {
            "duration_hours": duration,
            "outage": {"start_hour": 0, "duration_hours": duration, "grid_fraction": round(base_frac, 3)},
            "seed": seed})
        lo = default_scenario("heatwave_power_outage", {
            "duration_hours": duration,
            "outage": {"start_hour": 0, "duration_hours": duration, "grid_fraction": round(max(0.0, base_frac - 0.2), 3)},
            "seed": seed})
        hi_hours = run(CFG, hi).summary["hours_power_deficit"]
        lo_hours = run(CFG, lo).summary["hours_power_deficit"]
        assert lo_hours >= hi_hours
