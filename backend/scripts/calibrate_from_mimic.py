"""Local MIMIC-IV calibration (optional tool - runs ONLY on your machine).

Requires your own PhysioNet credentialed access. Reads CSV extracts that you
export locally, computes aggregates only (p10/p50/p90 length of stay,
admission fractions, 24 normalised arrival factors) and refuses to write any
cell computed from fewer than 10 records (small-cell suppression). Row-level
MIMIC data never enters this repository, chat or logs.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

MIN_CELL = 10


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def calibrate(stays_csv: Path, out_path: Path) -> None:
    """stays_csv columns (your local export): unit, admit_hour, los_hours."""
    with stays_csv.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    los_by_unit: dict[str, list[float]] = {}
    arrival_by_hour: dict[int, int] = {}
    admits = {"ward": 0, "icu": 0}
    for row in rows:
        unit = row.get("unit", "ward")
        try:
            los = float(row["los_hours"])
            hour = int(float(row["admit_hour"])) % 24
        except (KeyError, ValueError):
            continue
        los_by_unit.setdefault(unit, []).append(los)
        arrival_by_hour[hour] = arrival_by_hour.get(hour, 0) + 1
        if unit in admits:
            admits[unit] += 1

    aggregates: dict[str, object] = {"source": "local MIMIC-IV extract (aggregates only, min cell 10)",
                                     "records": len(rows)}
    for unit, values in los_by_unit.items():
        if len(values) < MIN_CELL:
            print(f"suppressed {unit}: only {len(values)} records (< {MIN_CELL})")
            continue
        values.sort()
        aggregates[f"{unit}_los_p10_p50_p90"] = [round(_percentile(values, q), 2) for q in (0.1, 0.5, 0.9)]
    total_admits = sum(admits.values())
    if total_admits >= MIN_CELL:
        aggregates["p_admit_ward"] = round(admits["ward"] / total_admits, 4)
        aggregates["p_admit_icu"] = round(admits["icu"] / total_admits, 4)
    total_arrivals = sum(arrival_by_hour.values())
    if total_arrivals >= MIN_CELL:
        mean = total_arrivals / 24
        factors = [arrival_by_hour.get(h, 0) / mean for h in range(24)]
        scale = statistics.mean(factors) or 1.0
        aggregates["arrival_diurnal_profile"] = [round(f / scale, 3) for f in factors]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(aggregates, indent=2), encoding="utf-8")
    print(f"wrote {out_path} (aggregates only; review before use)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stays_csv", type=Path, help="your LOCAL CSV extract (unit, admit_hour, los_hours)")
    parser.add_argument("--out", type=Path, default=Path("data/reference/mimic_aggregates.json"))
    args = parser.parse_args()
    calibrate(args.stays_csv, args.out)


if __name__ == "__main__":
    main()
