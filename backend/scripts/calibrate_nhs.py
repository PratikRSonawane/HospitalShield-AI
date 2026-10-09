"""Scale the synthetic hospital to an imported NHS reference (optional tool).

Reads data/reference/nhs_beds_<trust>.json, writes data/demo_hospital.nhs.json
with beds and initial occupancy scaled to the reference, and re-runs the B10
acceptance checks. The result stays a planning prototype on labelled data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.simulation import default_scenario, load_hospital_config, run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="path to nhs_beds_<trust>.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "demo_hospital.nhs.json")
    args = parser.parse_args()

    ref = json.loads(args.reference.read_text(encoding="utf-8"))
    base = json.loads((ROOT / "data" / "demo_hospital.json").read_text(encoding="utf-8"))

    total = ref.get("total_beds")
    occupancy = ref.get("occupancy_pct")
    if not total:
        raise SystemExit("reference file lacks total_beds; cannot scale")
    factor = float(total) / (base["ward"]["beds"] + base["icu"]["beds"])
    base["ward"]["beds"] = round(base["ward"]["beds"] * factor)
    base["icu"]["beds"] = round(base["icu"]["beds"] * factor)
    if occupancy:
        base["ward"]["initial_occupied"] = round(base["ward"]["beds"] * float(occupancy) / 100)
    base["hospital_name"] = f"Calibrated to NHS trust {ref.get('trust_code')} (reference aggregate, not real patient data)"

    args.out.write_text(json.dumps(base, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")

    cfg = load_hospital_config(args.out)
    result = run(cfg, default_scenario("normal_operations"))
    print("B10 normal-operations check: "
          f"alerts={len(result.alerts)} deficit_hours={result.summary['hours_power_deficit']} "
          f"resilience={result.summary['resilience_index']}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else 1)
