"""Generate frontend/public/demo-results.json with PRECOMPUTED results.

Labels every payload PRECOMPUTED with the current model_version. A backend
test proves the snapshots equal live engine output for the current version.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.simulation import load_hospital_config, parse_interventions, run  # noqa: E402
from app.simulation.result import MODEL_VERSION  # noqa: E402
from app.simulation.scenario import default_scenario  # noqa: E402


def demo_interventions(scenario: str) -> dict:
    """The demo's guided intervention set per scenario."""
    if scenario == "heatwave_power_outage":
        return {
            "activate_surge_beds": [{"unit": "ward", "beds": 8, "start_hour": 6},
                                    {"unit": "icu", "beds": 2, "start_hour": 6}],
            "reallocate_staff": [{"from_unit": "ed", "to_unit": "icu", "nurses": 2, "start_hour": 6}],
            "reduce_noncritical_load_kw": [{"kw": 40, "start_hour": 24, "end_hour": 60}],
            "emergency_resupply": [{"fuel_l": 1000.0, "start_hour": 0}],
        }
    if scenario == "flood_storm_access":
        return {
            "recall_staff": [{"unit": "ed", "nurses": 1, "start_hour": 0},
                             {"unit": "ward", "nurses": 2, "start_hour": 0},
                             {"unit": "icu", "nurses": 1, "start_hour": 0}],
            "reallocate_staff": [{"from_unit": "ward", "to_unit": "icu", "nurses": 1, "start_hour": 0}],
            "emergency_resupply": [{"items": {"oxygen": 2000.0, "essential_meds": 2000.0}, "start_hour": 0}],
        }
    return {}


def build_snapshot() -> dict:
    cfg = load_hospital_config(ROOT / "data" / "demo_hospital.json")
    out: dict = {"model_version": MODEL_VERSION, "label": "PRECOMPUTED", "scenarios": {}}
    for name in ("heatwave_power_stress", "heatwave_power_outage", "flood_storm_access"):
        scenario = default_scenario(name)
        baseline = run(cfg, scenario)
        iv = parse_interventions(demo_interventions(name))
        treated = run(cfg, scenario, iv)
        deltas = {}
        for key, b in baseline.summary.items():
            t = treated.summary.get(key)
            if isinstance(b, int | float) and isinstance(t, int | float) and not isinstance(b, bool):
                deltas[key] = {"absolute": round(t - b, 2)}
        out["scenarios"][name] = {
            "baseline": baseline.to_dict(),
            "treated": treated.to_dict(),
            "deltas": deltas,
        }
    return out


def main() -> None:
    target = ROOT / "frontend" / "public" / "demo-results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    target.write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {target} ({target.stat().st_size // 1024} KB) for model_version {MODEL_VERSION}")


if __name__ == "__main__":
    main()
