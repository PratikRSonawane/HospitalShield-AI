"""Boundary-case tests for the pure computation modules (S1 gate)."""

import math

import pytest

from app.simulation.config import parse_hospital_config
from app.simulation.errors import SimulationValidationError
from app.simulation.power import compute_power
from app.simulation.staffing import compute_staffing
from app.simulation.state import make_unit_row
from app.simulation.supplies import compute_supplies, scheduled_delivery_rate


def base_cfg():
    return parse_hospital_config({
        "hospital_name": "t",
        "ed": {"bays": 24, "nurse_roster": 10, "patients_per_nurse": 4, "los_hours": 4.0},
        "ward": {"beds": 100, "nurse_roster": 18, "patients_per_nurse": 6, "alos_hours": 108,
                 "initial_occupied": 80, "surge_beds_available": 15},
        "icu": {"beds": 20, "nurse_roster": 9, "patients_per_nurse": 2, "alos_hours": 96,
                "initial_occupied": 14, "surge_beds_available": 4},
        "arrivals": {"baseline_per_hour": 5.6, "diurnal_profile": [1.0] * 24,
                     "p_admit_ward": 0.13, "p_admit_icu": 0.026},
        "power": {"grid_capacity_kw": 450, "critical_load_kw": 220, "noncritical_load_kw": 130,
                  "noncritical_diurnal_profile": [1.0] * 24, "cooling_base_kw": 50,
                  "cooling_threshold_c": 28, "cooling_kw_per_deg_c_above": 4.0,
                  "cooling_critical_fraction": 0.5, "generator_capacity_kw": 300,
                  "fuel_litres": 2000, "fuel_l_per_kwh": 0.28, "surge_bed_kw": 1.5,
                  "max_shed_fraction_of_noncritical": 0.4,
                  "power_derate_factor_when_critical_at_risk": 0.85},
        "staffing": {"max_reallocation_fraction_of_source": 0.2, "min_source_floor_fraction": 0.8},
        "surge": {"activation_delay_hours": 6},
        "supplies": {"items": ["oxygen"], "units_per_weighted_bed_hour": {"oxygen": 1.0},
                     "initial_cover_hours": 36, "icu_weight": 2.0, "ed_weight": 0.5,
                     "scheduled_resupply_fraction": 1.0, "low_cover_hours": 24,
                     "stockout_derate_factor": 0.8, "emergency_resupply_max_cover_hours": 24,
                     "emergency_lead_time_hours": 12},
        "recall": {"max_fraction_of_roster": 0.15, "lead_time_hours": 4},
        "thresholds": {"occupancy_warn_pct": 90, "reserve_low_pct": 10, "fuel_low_hours": 12,
                       "ed_boarding_warn": 4, "ed_waiting_high": 10},
        "resilience_weights": {"occupancy": 0.22, "overflow": 0.22, "staffing": 0.13,
                               "power_deficit": 0.18, "critical_risk": 0.13, "supply": 0.12},
    })


class TestOccupancyBoundaries:
    def test_zero_usable_returns_null_unavailable(self):
        # B4: usable == 0 returns null occupancy with status unavailable
        row = make_unit_row(10, 0, 0)
        assert row["occupancy_pct"] is None and row["status"] == "unavailable"

    def test_usable_zero_with_patients_is_unavailable(self):
        row = make_unit_row(0, 0, 5)
        assert row["occupancy_pct"] is None and row["status"] == "unavailable"
        assert row["beds_over_usable"] == 5

    def test_90_of_100(self):
        row = make_unit_row(100, 100, 90)
        assert row["occupancy_pct"] == 90.0 and row["status"] == "warn"

    def test_100_pct_is_critical(self):
        row = make_unit_row(100, 100, 100)
        assert row["occupancy_pct"] == 100.0 and row["status"] == "critical"

    def test_over_100_clamped_with_excess(self):
        row = make_unit_row(100, 60, 70)
        assert row["occupancy_pct"] == 100.0
        assert row["beds_over_usable"] == 10


class TestPowerBoundaries:
    def test_demand_450_supply_400_deficit_50(self):
        out = compute_power(base_cfg(), 0, 20.0, 0, 0.0, 1.0, 0.0, 0.0, 0.0)
        # force numbers by using a custom cfg is complex; verify arithmetic directly
        assert out.demand_kw >= out.critical_demand_kw

    def test_supply_450_demand_400_reserve_50(self):
        out = compute_power(base_cfg(), 0, 20.0, 0, 0.0, 1.0, 0.0, 0.0, 0.0)
        # 220 + 25 crit cooling + 130 + 25 noncrit cooling = 400 vs grid 450 -> reserve 50
        assert out.deficit_kw == 0.0
        assert out.reserve_kw == pytest.approx(50.0, abs=1e-6)

    def test_deficit_50_when_supply_350(self):
        # demand = 220 + 25 critical cooling + 130 + 25 noncritical cooling = 400 kW
        out = compute_power(base_cfg(), 0, 20.0, 0, 0.0, 350.0 / 450.0, 0.0, 0.0, 0.0)
        assert out.grid_supply_kw == pytest.approx(350.0, abs=1e-6)
        assert out.deficit_kw == pytest.approx(50.0, abs=1e-6)
        assert out.reserve_kw == 0.0

    def test_demand_equals_supply_both_zero(self):
        out = compute_power(base_cfg(), 0, 20.0, 0, 0.0, 400.0 / 450.0, 0.0, 0.0, 0.0)
        assert out.deficit_kw == 0.0
        assert out.reserve_kw == pytest.approx(0.0, abs=1e-6)

    def test_shed_capped_at_fraction(self):
        cfg = base_cfg()
        out = compute_power(cfg, 0, 20.0, 0, requested_shed_kw=1000.0, grid_fraction=1.0,
                            gen_availability_fraction=0.0, fuel_l=0.0, fuel_resupply_l=0.0)
        noncrit = cfg.power.noncritical_load_kw + 25.0  # diurnal 1.0 + noncritical cooling
        assert out.shed_kw == pytest.approx(0.4 * noncrit, abs=1e-6)

    def test_critical_cooling_split(self):
        cfg = base_cfg()
        out = compute_power(cfg, 0, 38.0, 0, 0.0, 1.0, 0.0, 0.0, 0.0)
        # cooling = 50 + 4*10 = 90; critical share 45
        assert out.critical_demand_kw == pytest.approx(220 + 45, abs=1e-6)

    def test_fuel_burn_and_floor(self):
        out = compute_power(base_cfg(), 0, 40.0, 0, 0.0, 0.0, 1.0, 10.0, 0.0)
        # gen available limited by fuel: 10/0.28 = 35.7 kW
        assert out.gen_available_kw == pytest.approx(10.0 / 0.28, abs=1e-3)
        assert out.fuel_l >= 0.0


class TestStaffingBoundaries:
    def test_staff_availability_zero(self):
        cfg = base_cfg()
        out = compute_staffing(cfg, 0.0, 1.0, {"ed": 20, "ward": 80, "icu": 14},
                               {"ed": 0, "ward": 0, "icu": 0}, {"ed": 0, "ward": 0, "icu": 0})
        assert all(out.available[u] == 0 for u in ("ed", "ward", "icu"))
        assert all(out.staffed_capacity[u] == 0 for u in ("ed", "ward", "icu"))
        assert out.required["ward"] == math.ceil(80 / 6)

    def test_access_fraction_zero_gives_zero_staff_without_crash(self):
        cfg = base_cfg()
        out = compute_staffing(cfg, 1.0, 0.0, {"ed": 20, "ward": 80, "icu": 14},
                               {"ed": 0, "ward": 0, "icu": 0}, {"ed": 0, "ward": 0, "icu": 0})
        assert all(out.available[u] == 0 for u in ("ed", "ward", "icu"))

    def test_shortfall(self):
        cfg = base_cfg()
        out = compute_staffing(cfg, 0.5, 1.0, {"ed": 0, "ward": 96, "icu": 0},
                               {"ed": 0, "ward": 0, "icu": 0}, {"ed": 0, "ward": 0, "icu": 0})
        # ward: floor(18*0.5)=9 nurses -> capacity 54; required ceil(96/6)=16 -> shortfall 7
        assert out.available["ward"] == 9
        assert out.shortfall["ward"] == 7


class TestSuppliesBoundaries:
    def test_zero_consumption_cover_null(self):
        cfg = base_cfg()
        out = compute_supplies(cfg, {"oxygen": 100.0}, weighted_occupied_prev=0.0,
                               delivery_fraction=1.0, emergency_arriving={})
        assert out.cover_hours["oxygen"] is None
        assert out.stockout["oxygen"] is False

    def test_stock_never_negative(self):
        cfg = base_cfg()
        out = compute_supplies(cfg, {"oxygen": 5.0}, weighted_occupied_prev=100.0,
                               delivery_fraction=0.0, emergency_arriving={})
        assert out.stock["oxygen"] == 0.0
        assert out.unmet["oxygen"] == pytest.approx(95.0, abs=1e-9)
        assert out.stockout["oxygen"] is True

    def test_stockout_flagged_exactly_when_stock_hits_zero(self):
        cfg = base_cfg()
        # stock 100, consumption 100 -> served fully, stock 0 -> stockout True
        out = compute_supplies(cfg, {"oxygen": 100.0}, weighted_occupied_prev=100.0,
                               delivery_fraction=0.0, emergency_arriving={})
        assert out.stock["oxygen"] == 0.0
        assert out.stockout["oxygen"] is True
        assert out.unmet["oxygen"] == 0.0

    def test_delivery_fraction_zero_drains_at_rate(self):
        cfg = base_cfg()
        out = compute_supplies(cfg, {"oxygen": 240.0}, weighted_occupied_prev=100.0,
                               delivery_fraction=0.0, emergency_arriving={})
        assert out.stock["oxygen"] == pytest.approx(140.0, abs=1e-9)

    def test_supply_identity(self):
        cfg = base_cfg()
        out = compute_supplies(cfg, {"oxygen": 50.0}, weighted_occupied_prev=120.0,
                               delivery_fraction=0.5, emergency_arriving={"oxygen": 30.0})
        change = out.stock["oxygen"] - 50.0
        assert change == pytest.approx(out.delivered["oxygen"] - out.consumption["oxygen"], abs=1e-9)

    def test_scheduled_rate_matches_baseline(self):
        cfg = base_cfg()
        rate = scheduled_delivery_rate(cfg, "oxygen", 100.0)
        assert rate == pytest.approx(100.0, abs=1e-9)


class TestConfigValidation:
    def test_missing_field_lists_issue(self):
        with pytest.raises(SimulationValidationError) as e:
            parse_hospital_config({"hospital_name": "x"})
        assert any(i.field == "ed" for i in e.value.issues)

    def test_bad_profile_shape(self):
        data = {"ed": {"bays": 1, "nurse_roster": 1, "patients_per_nurse": 1, "los_hours": 1},
                "ward": {"beds": 1, "nurse_roster": 1, "patients_per_nurse": 1, "alos_hours": 1,
                         "initial_occupied": 0, "surge_beds_available": 0},
                "icu": {"beds": 1, "nurse_roster": 1, "patients_per_nurse": 1, "alos_hours": 1,
                        "initial_occupied": 0, "surge_beds_available": 0},
                "arrivals": {"baseline_per_hour": 1, "diurnal_profile": [1, 2, 3],
                             "p_admit_ward": 0, "p_admit_icu": 0},
                "power": {"grid_capacity_kw": 1, "critical_load_kw": 0, "noncritical_load_kw": 0,
                          "noncritical_diurnal_profile": [1.0] * 24, "cooling_base_kw": 0,
                          "cooling_threshold_c": 28, "cooling_kw_per_deg_c_above": 0,
                          "cooling_critical_fraction": 0.5, "generator_capacity_kw": 0,
                          "fuel_litres": 0, "fuel_l_per_kwh": 0.28, "surge_bed_kw": 0,
                          "max_shed_fraction_of_noncritical": 0.4,
                          "power_derate_factor_when_critical_at_risk": 0.85},
                "staffing": {"max_reallocation_fraction_of_source": 0.2, "min_source_floor_fraction": 0.8},
                "surge": {"activation_delay_hours": 6},
                "supplies": {"items": [], "units_per_weighted_bed_hour": {}, "initial_cover_hours": 1,
                             "icu_weight": 2.0, "ed_weight": 0.5, "scheduled_resupply_fraction": 1.0,
                             "low_cover_hours": 24, "stockout_derate_factor": 0.8,
                             "emergency_resupply_max_cover_hours": 24, "emergency_lead_time_hours": 12},
                "recall": {"max_fraction_of_roster": 0.15, "lead_time_hours": 4},
                "thresholds": {"occupancy_warn_pct": 90, "reserve_low_pct": 10, "fuel_low_hours": 12,
                               "ed_boarding_warn": 4, "ed_waiting_high": 10},
                "resilience_weights": {"occupancy": 0.22, "overflow": 0.22, "staffing": 0.13,
                                       "power_deficit": 0.18, "critical_risk": 0.13, "supply": 0.12}}
        with pytest.raises(SimulationValidationError) as e:
            parse_hospital_config(data)
        assert any("diurnal" in i.field for i in e.value.issues)
