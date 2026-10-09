"""Alert episode tests (B8), metrics (B7) and failure-point tests (B11)."""

from pathlib import Path

import pytest

from app.simulation import default_scenario, load_hospital_config, run

DATA = str(Path(__file__).resolve().parents[2] / "data" / "demo_hospital.json")


@pytest.fixture(scope="module")
def cfg():
    return load_hospital_config(DATA)


class TestAlertEpisodes:
    def test_normal_operations_no_alerts(self, cfg):
        res = run(cfg, default_scenario("normal_operations"))
        assert res.alerts == []

    def test_consecutive_hours_merge_into_one_episode(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_stress"))
        for alert in res.alerts:
            assert alert["duration_hours"] == alert["last_hour"] - alert["first_hour"] + 1

    def test_gap_splits_episodes(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_stress"))
        r03 = [a for a in res.alerts if a["rule_id"] == "R02"]
        if len(r03) > 1:
            for first, second in zip(r03, r03[1:], strict=False):
                assert first["last_hour"] + 1 < second["first_hour"]

    def test_alert_traceability_fields(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        assert res.alerts, "outage preset must produce alerts"
        for a in res.alerts:
            assert set(a) >= {"rule_id", "rule_text", "severity", "metric", "unit",
                              "observed_peak", "threshold", "first_hour", "last_hour",
                              "duration_hours", "affected_variable"}
            assert a["severity"] in ("warning", "high", "critical")

    def test_outage_has_fuel_and_critical_alerts(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        rule_ids = {a["rule_id"] for a in res.alerts}
        assert {"R05", "R09"} <= rule_ids  # deficit and fuel exhaustion

    def test_flood_has_supply_and_staff_alerts(self, cfg):
        res = run(cfg, default_scenario("flood_storm_access"))
        rule_ids = {a["rule_id"] for a in res.alerts}
        assert "R04" in rule_ids and "R10" in rule_ids


class TestMetrics:
    def test_resilience_bounds(self, cfg):
        for name in ("normal_operations", "heatwave_power_stress",
                     "heatwave_power_outage", "flood_storm_access"):
            res = run(cfg, default_scenario(name))
            assert 0.0 <= res.summary["resilience_index"] <= 100.0

    def test_normal_operations_high_resilience(self, cfg):
        res = run(cfg, default_scenario("normal_operations"))
        assert res.summary["resilience_index"] >= 95.0

    def test_summary_keys_complete(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        expected = {"peak_ward_occupancy_pct", "peak_icu_occupancy_pct", "peak_ed_occupancy_pct",
                    "hours_ward_above_threshold", "hours_icu_above_threshold", "peak_ed_waiting",
                    "peak_ed_boarding", "overflow_patient_hours", "staff_shortfall_nurse_hours",
                    "hours_beds_over_usable", "peak_power_demand_kw", "hours_power_deficit",
                    "peak_power_deficit_kw", "energy_unserved_kwh", "min_power_reserve_kw",
                    "hours_critical_load_at_risk", "fuel_remaining_l", "hours_to_fuel_exhaustion",
                    "min_supply_cover_hours", "hours_supply_stockout", "first_failure",
                    "time_to_first_failure_hours", "resilience_index", "root_failures",
                    "cascade_children"}
        assert expected <= set(res.summary)

    def test_supply_metrics_per_item(self, cfg):
        res = run(cfg, default_scenario("flood_storm_access"))
        assert set(res.summary["min_supply_cover_hours"]) == {"oxygen", "essential_meds"}
        assert res.summary["min_supply_cover_hours"]["oxygen"] < 24  # B10 flood criterion


class TestFailurePoints:
    def test_normal_operations_no_failures(self, cfg):
        res = run(cfg, default_scenario("normal_operations"))
        assert res.failure_points == []
        assert res.summary["time_to_first_failure_hours"] is None

    def test_stress_scenarios_have_failures(self, cfg):
        for name in ("heatwave_power_stress", "heatwave_power_outage", "flood_storm_access"):
            res = run(cfg, default_scenario(name))
            assert res.failure_points, f"{name} should have failure points"

    def test_ranking_deterministic_and_ordered(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        keys = [(f["first_hour"], -{"warning": 1, "high": 2, "critical": 3}[f["peak_severity"]], f["resource"], f["rule_id"])
                for f in res.failure_points]
        assert keys == sorted(keys)
        assert [f["rank"] for f in res.failure_points] == list(range(1, len(res.failure_points) + 1))

    def test_margin_trace_no_nan(self, cfg):
        res = run(cfg, default_scenario("flood_storm_access"))
        for f in res.failure_points:
            for point in f["margin_trace"]:
                assert point["margin"] == point["margin"]  # NaN check
                assert point["margin"] <= 1.0 + 1e-9  # can be negative when over capacity

    def test_cascades_present_in_outage(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        children = [f for f in res.failure_points if f["cascade_parent"]]
        assert children, "outage should show cascade children"
        assert res.summary["cascade_children"] == len(children)
        assert res.summary["root_failures"] == len(res.failure_points) - len(children)

    def test_cascade_parent_failed_earlier(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        by_rule = {}
        for f in res.failure_points:
            by_rule.setdefault(f["rule_id"], []).append(f)
        for f in res.failure_points:
            if f["cascade_parent"]:
                parents = by_rule.get(f["cascade_parent"], [])
                assert any(p["first_hour"] <= f["first_hour"] for p in parents)

    def test_hand_built_zero_margin_bed(self, cfg):
        from app.simulation.failure_points import hourly_margins
        row = {"units": {"ward": {"usable_beds": 10, "occupied": 10},
                         "icu": {"usable_beds": 10, "occupied": 5},
                         "ed": {"usable_beds": 10, "occupied": 4}},
               "power": {"available_supply_kw": 400.0, "demand_kw": 300.0, "critical_demand_kw": 250.0},
               "staffing": {"ed": {"available": 5, "required": 5}, "ward": {"available": 10, "required": 8},
                            "icu": {"available": 5, "required": 5}},
               "supply": {"fuel_hours": 100.0, "fuel_low_hours": 12, "cover_hours": {"oxygen": 40.0},
                          "low_cover_hours": 24}}
        m = hourly_margins(row)
        assert m["beds"] == 0.0
        assert m["power"] == pytest.approx(0.25, abs=1e-6)

    def test_zero_denominator_margin_is_zero_not_nan(self, cfg):
        from app.simulation.failure_points import hourly_margins
        row = {"units": {"ward": {"usable_beds": 0, "occupied": 0},
                         "icu": {"usable_beds": 0, "occupied": 0},
                         "ed": {"usable_beds": 0, "occupied": 0}},
               "power": {"available_supply_kw": 0.0, "demand_kw": 10.0, "critical_demand_kw": 10.0},
               "staffing": {"ed": {"available": 0, "required": 0}, "ward": {"available": 0, "required": 0},
                            "icu": {"available": 0, "required": 0}},
               "supply": {"fuel_hours": None, "fuel_low_hours": 12, "cover_hours": {},
                          "low_cover_hours": 24}}
        m = hourly_margins(row)
        # zero denominators count as zero margin; supplies with no items is 1.0
        assert m["power"] == 0.0 and m["staff"] == 0.0 and m["beds"] == 0.0 and m["ed_flow"] == 0.0
        assert m["supplies"] == 1.0
        assert all(v == v for v in m.values())  # no NaN
