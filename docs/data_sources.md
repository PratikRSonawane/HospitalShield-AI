# Data sources and dataset rules

## MIMIC-IV v3.1 (PhysioNet) — credentialed, reference only

- Access requires a PhysioNet data use agreement. **Row-level MIMIC data never enters this repository, the
  prompts, or any log.** That rule is non-negotiable.
- `backend/scripts/calibrate_from_mimic.py` runs **only on the operator's own machine** against a local CSV
  extract the operator exports under their own agreement. It writes aggregates only: p10/p50/p90 length of
  stay, admission fractions, and 24 normalised arrival factors. It **refuses to write any cell computed from
  fewer than 10 records** (small-cell suppression) and prints what it suppressed.
- MIMIC-IV is a US critical-care database. It does not represent Mayo Clinic, the fictional demo hospital, or
  any specific site. Calibration output is a reference prior, labelled as such.

## NHS England Bed Availability and Occupancy — open, reference only

- Published at <https://www.england.nhs.uk/statistics/statistical-work-areas/bed-availability-and-occupancy/>
  under the Open Government Licence. **Verify the current licence terms at the source before redistribution**
  and keep the attribution in any exported file (`backend/scripts/import_nhs_beds.py` embeds source URL and
  licence in `data/reference/nhs_beds_<trust>.json`).
- `backend/scripts/calibrate_nhs.py` scales the synthetic baseline's bed counts and initial occupancy to an
  imported trust aggregate and re-runs the acceptance checks (`docs/assumptions.md`).
- NHS data is a UK aggregate; like MIMIC-IV it is a calibration reference, not a representation of any specific
  hospital.

## What the demo actually runs on

The application always runs on the **SYNTHETIC baseline** (`data/demo_hospital.json`), calibrated in-repo and
documented in `docs/assumptions.md`. Reference datasets can inform a configuration; they are never loaded at
runtime by the application itself.

## Weather

- Optional live weather comes from the **Open-Meteo** forecast API (`temperature_2m`,
  `relative_humidity_2m`), attribution "Weather data by Open-Meteo.com (CC-BY 4.0)". Responses are validated
  (length, NaN, plausible ranges), cached in SQLite with a 1-hour TTL, and fall back to a labelled synthetic
  CSV on any failure. Live weather is labelled **REAL WEATHER** and kept strictly separate from synthetic
  hospital parameters.
- The bundled offline demo uses `data/demo_weather_fallback.csv` (SYNTHETIC profile).

## Personal data

No personal health information is used, stored, or produced anywhere in this project. Uploaded hospital
configurations contain facility-level operational parameters only.
