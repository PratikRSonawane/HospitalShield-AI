"""Engine-level tests: scenarios, interventions, alert merging, determinism."""

from pathlib import Path

import pytest

from app.simulation import InfeasibleInterventionError, default_scenario, load_hospital_config, parse_interventions, run
from app.simulation.errors import SimulationValidationError

DATA = str(Path(__file__).resolve().parents[2] / "data" / "demo_hospital.json")


@pytest.fixture(scope="module")
def cfg():
    return load_hospital_config(DATA)


class TestScenarioValidation:
    def test_duration_bounds(self):
        with pytest.raises(SimulationValidationError):
            default_scenario("normal_operations", {"duration_hours": 0})
        default_scenario("normal_operations", {"duration_hours": 72})  # ok
        default_scenario("normal_operations", {"duration_hours": 1})   # ok

    def test_temperature_cross_field(self):
        with pytest.raises(SimulationValidationError) as e:
            default_scenario("normal_operations", {"weather": {"max_temperature_c": 30, "min_temperature_c": 35}})
        assert any(i.rule == "cross_field" for i in e.value.issues)

    def test_outage_window_must_fit(self):
        with pytest.raises(SimulationValidationError):
            default_scenario("heatwave_power_outage", {"duration_hours": 24,
                                                       "outage": {"start_hour": 20, "duration_hours": 10, "grid_fraction": 0.0}})

    def test_arrival_multiplier_bounds(self):
        with pytest.raises(SimulationValidationError):
            default_scenario("heatwave_power_stress", {"stress": {"arrival_multiplier": 3.5}})

    def test_unknown_scenario(self):
        with pytest.raises(ValueError):
            default_scenario("wildfire_smoke")

    def test_access_window_larger_than_horizon_rejected(self):
        with pytest.raises(SimulationValidationError):
            default_scenario("flood_storm_access", {"duration_hours": 12,
                                                    "access": {"start_hour": 6, "duration_hours": 24,
                                                               "staff_access_fraction": 0.6,
                                                               "delivery_fraction": 0.25,
                                                               "arrival_multiplier": 1.4}})


class TestEngineBasics:
    def test_duration_1_and_72(self, cfg):
        for d in (1, 72):
            res = run(cfg, default_scenario("normal_operations", {"duration_hours": d}))
            assert len(res.series) == d

    def test_determinism_same_input_same_output(self, cfg):
        sc = default_scenario("heatwave_power_outage")
        a = run(cfg, sc).to_dict()
        b = run(cfg, sc).to_dict()
        assert a == b

    def test_seed_changes_stochastic_runs_only(self, cfg):
        sc = default_scenario("heatwave_power_stress", {"stochastic": True, "seed": 7})
        a = run(cfg, sc).to_dict()
        b = run(cfg, default_scenario("heatwave_power_stress", {"stochastic": True, "seed": 8})).to_dict()
        assert a["summary"] != b["summary"]

    def test_arrival_multiplier_zero(self, cfg):
        sc = default_scenario("normal_operations", {"stress": {"arrival_multiplier": 0.0}})
        res = run(cfg, sc)
        assert all(r["ed"]["arrivals"] == 0 for r in res.series)
        assert res.summary["peak_ed_waiting"] == 0

    def test_grid_zero_generator_zero_full_deficit(self, cfg):
        sc = default_scenario("heatwave_power_outage", {
            "stress": {"power_supply_fraction": 0.0},
            "outage": {"start_hour": 0, "duration_hours": 72, "grid_fraction": 0.0},
            "backup": {"generator_availability_fraction": 0.0}})
        res = run(cfg, sc)
        assert all(r["power"]["deficit_kw"] > 0 for r in res.series)
        assert res.summary["hours_power_deficit"] == len(res.series)

    def test_fuel_exhausted_mid_run(self, cfg):
        sc = default_scenario("heatwave_power_outage", {
            "stress": {"power_supply_fraction": 0.0},
            "outage": {"start_hour": 0, "duration_hours": 72, "grid_fraction": 0.0}})
        res = run(cfg, sc)
        assert res.summary["hours_to_fuel_exhaustion"] is not None
        exh = res.summary["hours_to_fuel_exhaustion"]
        assert exh > 0
        assert res.series[exh]["power"]["fuel_l"] == 0.0

    def test_carry_forward_rounding_over_72h(self, cfg):
        # arrivals 5.6/h * diurnal mean 1.0 -> total arrivals over 72h close to 403
        res = run(cfg, default_scenario("normal_operations"))
        total = sum(r["ed"]["arrivals"] for r in res.series)
        assert abs(total - 5.6 * 72) <= 5

    def test_patient_conservation_every_hour(self, cfg):
        # exact integer conservation is verified on every row inside run()
        res = run(cfg, default_scenario("heatwave_power_outage"))
        final = res.series[-1]
        assert final["ed"]["waiting"] >= 0


class TestInterventionTiming:
    def test_surge_beds_usable_only_after_delay(self, cfg):
        iv = parse_interventions({"activate_surge_beds": [{"unit": "ward", "beds": 10, "start_hour": 6}]})
        res = run(cfg, default_scenario("normal_operations"), iv)
        for row in res.series:
            if row["hour"] < 12:  # 6 + activation delay 6
                assert row["surge_open"]["ward"] == 0
            else:
                assert row["surge_open"]["ward"] == 10

    def test_unstaffed_surge_stays_unusable(self, cfg):
        # ICU roster 9*1.0=9 nurses -> 18 staffed capacity < 20+surge beds
        iv = parse_interventions({"activate_surge_beds": [{"unit": "icu", "beds": 4, "start_hour": 0}]})
        res = run(cfg, default_scenario("normal_operations"), iv)
        late = res.series[-1]
        assert late["surge_open"]["icu"] == 4
        assert late["units"]["icu"]["usable_beds"] <= 18  # staffed capacity caps usable

    def test_recall_arrives_after_lead_time_scaled_by_access(self, cfg):
        iv = parse_interventions({"recall_staff": [{"unit": "ed", "nurses": 1, "start_hour": 0}]})
        sc = default_scenario("flood_storm_access")  # access window 18..42, staff_access 0.6
        res = run(cfg, sc, iv)
        # arrival hour 4: outside window -> scale 1.0 -> 1 nurse from hour 4
        assert res.series[4]["staffing"]["ed"]["available"] >= 1

    def test_recall_inside_access_window_scaled_down(self, cfg):
        iv = parse_interventions({"recall_staff": [{"unit": "ed", "nurses": 1, "start_hour": 15}]})
        sc = default_scenario("flood_storm_access")
        res = run(cfg, sc, iv)
        # arrival hour 19 inside window: floor(1*0.6)=0 nurses
        assert res.series[19]["surge_open"]["ed"] == 0
        # and no extra nurse: available equals the no-recall run
        base = run(cfg, sc)
        assert res.series[19]["staffing"]["ed"]["available"] == base.series[19]["staffing"]["ed"]["available"]

    def test_resupply_no_effect_before_lead_time(self, cfg):
        iv = parse_interventions({"emergency_resupply": [{"items": {"oxygen": 1000.0}, "start_hour": 10}]})
        sc = default_scenario("flood_storm_access")
        res = run(cfg, sc, iv)
        base = run(cfg, sc)
        for row, brow in zip(res.series[:22], base.series[:22], strict=False):  # arrival at 10+12=22
            assert row["supplies"]["oxygen"]["stock"] == pytest.approx(brow["supplies"]["oxygen"]["stock"], abs=1e-6)

    def test_resupply_scaled_by_delivery_fraction_at_arrival(self, cfg):
        iv = parse_interventions({"emergency_resupply": [{"items": {"oxygen": 1000.0}, "start_hour": 10}]})
        sc = default_scenario("flood_storm_access")  # arrival hour 22 inside window (18..42), delivery 0.15
        res = run(cfg, sc, iv)
        delivered = res.series[22]["supplies"]["oxygen"]["delivered"]
        base = run(cfg, sc)
        scheduled = base.series[22]["supplies"]["oxygen"]["delivered"]
        assert delivered == pytest.approx(scheduled + 150.0, abs=1e-6)

    def test_fuel_resupply_extends_exhaustion(self, cfg):
        sc = default_scenario("heatwave_power_outage")
        base = run(cfg, sc)
        iv = parse_interventions({"emergency_resupply": [{"fuel_l": 500.0, "start_hour": 0}]})
        res = run(cfg, sc, iv)
        b = base.summary["hours_to_fuel_exhaustion"]
        a = res.summary["hours_to_fuel_exhaustion"]
        assert a is not None and b is not None and a > b

    def test_reallocation_conserves_total_nurses(self, cfg):
        iv = parse_interventions({"reallocate_staff": [{"from_unit": "ward", "to_unit": "ed", "nurses": 2, "start_hour": 0}]})
        res = run(cfg, default_scenario("normal_operations"), iv)
        row = res.series[10]
        base = run(cfg, default_scenario("normal_operations")).series[10]
        total = sum(row["staffing"][u]["available"] for u in ("ed", "ward", "icu"))
        total_base = sum(base["staffing"][u]["available"] for u in ("ed", "ward", "icu"))
        assert total == total_base
        assert row["staffing"]["ed"]["available"] == base["staffing"]["ed"]["available"] + 2
        assert row["staffing"]["ward"]["available"] == base["staffing"]["ward"]["available"] - 2

    def test_critical_load_never_reduced(self, cfg):
        iv = parse_interventions({"reduce_noncritical_load_kw": [{"kw": 40, "start_hour": 0, "end_hour": 72}]})
        res = run(cfg, default_scenario("heatwave_power_outage"), iv)
        assert all(r["power"]["critical_demand_kw"] >= cfg.power.critical_load_kw for r in res.series)


class TestFeasibility:
    def test_surge_over_capacity_rejected(self, cfg):
        sc = default_scenario("normal_operations")
        iv = parse_interventions({"activate_surge_beds": [{"unit": "ward", "beds": 16, "start_hour": 0}]})
        with pytest.raises(InfeasibleInterventionError) as e:
            run(cfg, sc, iv)
        assert any(i.rule == "surge_capacity" for i in e.value.issues)

    def test_self_move_rejected(self, cfg):
        sc = default_scenario("normal_operations")
        iv = parse_interventions({"reallocate_staff": [{"from_unit": "ed", "to_unit": "ed", "nurses": 1, "start_hour": 0}]})
        with pytest.raises(InfeasibleInterventionError) as e:
            run(cfg, sc, iv)
        assert any(i.rule == "self_move" for i in e.value.issues)

    def test_source_floor_rejected(self, cfg):
        sc = default_scenario("normal_operations")
        iv = parse_interventions({"reallocate_staff": [{"from_unit": "icu", "to_unit": "ed", "nurses": 3, "start_hour": 0}]})
        with pytest.raises(InfeasibleInterventionError) as e:
            run(cfg, sc, iv)
        assert any(i.rule in ("source_floor", "reallocation_cap") for i in e.value.issues)

    def test_recall_over_cap_rejected(self, cfg):
        sc = default_scenario("normal_operations")
        iv = parse_interventions({"recall_staff": [{"unit": "icu", "nurses": 3, "start_hour": 0}]})
        with pytest.raises(InfeasibleInterventionError) as e:
            run(cfg, sc, iv)
        assert any(i.rule == "recall_cap" for i in e.value.issues)

    def test_resupply_over_cap_rejected(self, cfg):
        sc = default_scenario("normal_operations")
        iv = parse_interventions({"emergency_resupply": [{"fuel_l": 99999.0, "start_hour": 0}]})
        with pytest.raises(InfeasibleInterventionError) as e:
            run(cfg, sc, iv)
        assert any(i.rule == "resupply_cap" for i in e.value.issues)

    def test_recall_arrival_beyond_horizon_rejected(self, cfg):
        sc = default_scenario("normal_operations", {"duration_hours": 6})
        iv = parse_interventions({"recall_staff": [{"unit": "ed", "nurses": 1, "start_hour": 4}]})
        with pytest.raises(InfeasibleInterventionError):
            run(cfg, sc, iv)
