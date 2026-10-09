"""B10 calibration acceptance tests and golden snapshots."""

import json
from pathlib import Path

import pytest

from app.simulation import default_scenario, load_hospital_config, parse_interventions, run
from app.simulation.result import MODEL_VERSION

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "demo_hospital.json"


@pytest.fixture(scope="module")
def cfg():
    return load_hospital_config(DATA)


class TestB10Calibration:
    def test_normal_operations_steady_state(self, cfg):
        res = run(cfg, default_scenario("normal_operations"))
        ward_initial = 100.0 * cfg.ward.initial_occupied / min(cfg.ward.beds, cfg.ward.nurse_roster * cfg.ward.patients_per_nurse)
        icu_initial = 100.0 * cfg.icu.initial_occupied / min(cfg.icu.beds, cfg.icu.nurse_roster * cfg.icu.patients_per_nurse)

        def mean_occupancy(unit):
            vals = [r["units"][unit]["occupancy_pct"] for r in res.series[-24:]]
            vals = [v for v in vals if v is not None]
            return sum(vals) / len(vals)

        # steady state judged as mean occupancy over the final 24 hours
        # (single-hour integer rounding on small units is noisy)
        assert abs(mean_occupancy("ward") - ward_initial) <= 5.0
        assert abs(mean_occupancy("icu") - icu_initial) <= 5.0
        assert res.alerts == []
        assert res.summary["hours_power_deficit"] == 0

    def test_heatwave_stress_reaches_90pct(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_stress"))
        peak = max(res.summary["peak_ward_occupancy_pct"] or 0,
                   res.summary["peak_icu_occupancy_pct"] or 0)
        assert peak >= 90.0

    def test_heatwave_stress_interventions_help_but_not_fully(self, cfg):
        sc = default_scenario("heatwave_power_stress")
        baseline = run(cfg, sc)
        iv = parse_interventions({
            "recall_staff": [{"unit": "ward", "nurses": 2, "start_hour": 6},
                             {"unit": "icu", "nurses": 1, "start_hour": 6}],
            "activate_surge_beds": [{"unit": "ward", "beds": 10, "start_hour": 6},
                                    {"unit": "icu", "beds": 2, "start_hour": 6}],
            "reallocate_staff": [{"from_unit": "ed", "to_unit": "icu", "nurses": 2, "start_hour": 6}],
        })
        treated = run(cfg, sc, iv)
        assert treated.summary["overflow_patient_hours"] < baseline.summary["overflow_patient_hours"]
        above_b = baseline.summary["hours_ward_above_threshold"] + baseline.summary["hours_icu_above_threshold"]
        above_t = treated.summary["hours_ward_above_threshold"] + treated.summary["hours_icu_above_threshold"]
        assert above_t < above_b
        assert treated.summary["overflow_patient_hours"] > 0  # not every problem eliminated

    def test_outage_deficit_and_fuel_event(self, cfg):
        res = run(cfg, default_scenario("heatwave_power_outage"))
        assert res.summary["hours_power_deficit"] > 0
        assert res.summary["hours_to_fuel_exhaustion"] is not None or res.summary["hours_critical_load_at_risk"] > 0

    def test_outage_combined_plan_beats_single_interventions(self, cfg):
        sc = default_scenario("heatwave_power_outage")
        combined = parse_interventions({
            "activate_surge_beds": [{"unit": "ward", "beds": 8, "start_hour": 6},
                                    {"unit": "icu", "beds": 2, "start_hour": 6}],
            "reallocate_staff": [{"from_unit": "ed", "to_unit": "icu", "nurses": 2, "start_hour": 6}],
            "reduce_noncritical_load_kw": [{"kw": 40, "start_hour": 24, "end_hour": 60}],
            "emergency_resupply": [{"fuel_l": 1000.0, "start_hour": 0}],
        })
        combined_res = run(cfg, sc, combined)
        singles = [
            parse_interventions({"activate_surge_beds": [{"unit": "ward", "beds": 8, "start_hour": 6},
                                                         {"unit": "icu", "beds": 2, "start_hour": 6}]}),
            parse_interventions({"reallocate_staff": [{"from_unit": "ed", "to_unit": "icu", "nurses": 2, "start_hour": 6}]}),
            parse_interventions({"reduce_noncritical_load_kw": [{"kw": 40, "start_hour": 24, "end_hour": 60}]}),
            parse_interventions({"emergency_resupply": [{"fuel_l": 1000.0, "start_hour": 0}]}),
        ]
        for single in singles:
            single_res = run(cfg, sc, single)
            assert combined_res.summary["resilience_index"] >= single_res.summary["resilience_index"], \
                f"combined must beat single {single}"

    def test_flood_cover_or_shortfall_in_first_half(self, cfg):
        res = run(cfg, default_scenario("flood_storm_access"))
        cover_ok = min(v for v in res.summary["min_supply_cover_hours"].values() if v is not None) < 24
        shortfall_early = any(a["rule_id"] == "R04" and a["first_hour"] <= 36 for a in res.alerts)
        assert cover_ok and shortfall_early

    def test_flood_combined_measures_improves_resilience(self, cfg):
        sc = default_scenario("flood_storm_access")
        baseline = run(cfg, sc)
        iv = parse_interventions({
            "recall_staff": [{"unit": "ed", "nurses": 1, "start_hour": 0},
                             {"unit": "ward", "nurses": 2, "start_hour": 0},
                             {"unit": "icu", "nurses": 1, "start_hour": 0}],
            "reallocate_staff": [{"from_unit": "ward", "to_unit": "icu", "nurses": 1, "start_hour": 0}],
            "emergency_resupply": [{"items": {"oxygen": 2000.0, "essential_meds": 2000.0}, "start_hour": 0}],
        })
        treated = run(cfg, sc, iv)
        assert treated.summary["resilience_index"] > baseline.summary["resilience_index"]

    def test_resupply_sequencing_early_is_better(self, cfg):
        sc = default_scenario("flood_storm_access")
        early = run(cfg, sc, parse_interventions(
            {"emergency_resupply": [{"items": {"oxygen": 2000.0}, "start_hour": 0}]}))
        late = run(cfg, sc, parse_interventions(
            {"emergency_resupply": [{"items": {"oxygen": 2000.0}, "start_hour": 24}]}))
        early_cover = early.summary["min_supply_cover_hours"]["oxygen"]
        late_cover = late.summary["min_supply_cover_hours"]["oxygen"]
        assert early_cover is not None and late_cover is not None
        assert early_cover >= late_cover


GOLDEN = Path(__file__).parent / "golden"

GOLDEN_CASES = ("normal_operations", "heatwave_power_stress",
                "heatwave_power_outage", "flood_storm_access")


def _slim(res_dict):
    """Golden files keep summary, alerts, failure points and a series sample."""
    return {
        "model_version": res_dict["model_version"],
        "summary": res_dict["summary"],
        "alerts": res_dict["alerts"],
        "failure_points": res_dict["failure_points"],
        "series_first_24": res_dict["series"][:24],
    }


class TestGoldenSnapshots:
    @pytest.mark.parametrize("name", GOLDEN_CASES)
    def test_golden_matches(self, cfg, name):
        res = run(cfg, default_scenario(name))
        slim = _slim(res.to_dict())
        path = GOLDEN / f"{name}.json"
        if not path.exists():
            path.write_text(json.dumps(slim, indent=1, sort_keys=True), encoding="utf-8")
            pytest.fail(f"golden file {path.name} was missing and has been created; re-run")
        golden = json.loads(path.read_text(encoding="utf-8"))
        assert golden == slim

    def test_model_version_recorded(self):
        assert MODEL_VERSION == "1.0.0"
