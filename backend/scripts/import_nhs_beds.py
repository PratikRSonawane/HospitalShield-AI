"""Import an NHS England Bed Availability and Occupancy file (optional tool).

Takes a downloaded NHS England CSV and a trust code, writes
data/reference/nhs_beds_<trust>.json with beds, occupancy, critical care,
period, source URL and licence. Open data - keep the attribution and verify
the current licence on the NHS England statistics page before use.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SOURCE_URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/bed-availability-and-occupancy/"
LICENCE = "Open Government Licence v3.0 (verify current terms at source URL)"


def import_beds(csv_path: Path, trust_code: str, out_dir: Path) -> Path:
    with csv_path.open("r", encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if trust_code.lower() in str(r).lower()]
    if not rows:
        raise SystemExit(f"no rows matching trust code {trust_code!r} in {csv_path.name}")
    sample = rows[0]
    def pick(*keys: str) -> str | None:
        for k in keys:
            for col in sample:
                if k.lower() in col.lower():
                    return sample[col]
        return None
    record = {
        "trust_code": trust_code,
        "period": pick("period", "date") or "unknown",
        "total_beds": pick("total beds", "beds available"),
        "occupied_beds": pick("occupied"),
        "occupancy_pct": pick("occupancy %", "percentage"),
        "critical_care_beds": pick("critical"),
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "rows_matched": len(rows),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"nhs_beds_{trust_code}.json"
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="path to the downloaded NHS England CSV")
    parser.add_argument("trust_code", help="NHS trust code, e.g. RVR")
    parser.add_argument("--out-dir", type=Path, default=Path("data/reference"))
    args = parser.parse_args()
    out = import_beds(args.csv_path, args.trust_code, args.out_dir)
    print(f"wrote {out}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        sys.exit(exc.code)
