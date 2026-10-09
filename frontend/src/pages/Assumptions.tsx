/** Assumptions and Data page: every parameter with provenance labels,
 * dataset rules and the adaptation guide. */

import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'

interface BaselineHospital {
  hospital_name: string
  ed: { bays: number; nurse_roster: number; patients_per_nurse: number; los_hours: number }
  ward: { beds: number; nurse_roster: number; patients_per_nurse: number; alos_hours: number; initial_occupied: number; surge_beds_available: number }
  icu: { beds: number; nurse_roster: number; patients_per_nurse: number; alos_hours: number; initial_occupied: number; surge_beds_available: number }
  arrivals: { baseline_per_hour: number; p_admit_ward: number; p_admit_icu: number }
  power: Record<string, number>
  supplies: Record<string, unknown>
  thresholds: Record<string, number>
  resilience_weights: Record<string, number>
}

const PARAM_ROWS: { group: string; rows: { name: string; unit: string; get: (h: BaselineHospital) => string; label: 'SYNTHETIC' | 'CALCULATED' | 'SCENARIO_ASSUMPTION'; why: string }[] }[] = [
  {
    group: 'Emergency Department',
    rows: [
      { name: 'ed.bays', unit: 'bays', get: (h) => String(h.ed.bays), label: 'SYNTHETIC', why: 'Calibrated so baseline arrivals stay below ED throughput (bays / LOS) in normal operations.' },
      { name: 'ed.los_hours', unit: 'hours', get: (h) => String(h.ed.los_hours), label: 'SYNTHETIC', why: '4-hour ED length of stay; sets ED service completion rate 1/LOS.' },
      { name: 'arrivals.baseline_per_hour', unit: 'patients/hour', get: (h) => String(h.arrivals.baseline_per_hour), label: 'SYNTHETIC', why: 'Mean 24h arrivals; with the diurnal profile it keeps normal operations near steady state (B10).' },
      { name: 'arrivals.p_admit_ward / p_admit_icu', unit: 'fraction', get: (h) => `${h.arrivals.p_admit_ward} / ${h.arrivals.p_admit_icu}`, label: 'SYNTHETIC', why: 'Admission split calibrated so ward and ICU equilibrate at their initial occupancy (80 / 14 beds).' },
    ],
  },
  {
    group: 'Ward and ICU',
    rows: [
      { name: 'ward.beds', unit: 'beds', get: (h) => String(h.ward.beds), label: 'SYNTHETIC', why: '100-bed general ward for a mid-size hospital.' },
      { name: 'ward.alos_hours', unit: 'hours', get: (h) => String(h.ward.alos_hours), label: 'SYNTHETIC', why: '108-hour average length of stay; discharge rate 1/ALOS per hour.' },
      { name: 'ward.surge_beds_available', unit: 'beds', get: (h) => String(h.ward.surge_beds_available), label: 'SYNTHETIC', why: 'Surge capacity ceiling; usable only when staffed and powered.' },
      { name: 'icu.beds', unit: 'beds', get: (h) => String(h.icu.beds), label: 'SYNTHETIC', why: '20-bed ICU; nurse ratio 1:2 makes staffing the binding constraint under absence.' },
    ],
  },
  {
    group: 'Power and cooling',
    rows: [
      { name: 'power.grid_capacity_kw', unit: 'kW', get: (h) => String(h.power.grid_capacity_kw), label: 'SYNTHETIC', why: 'Grid connection sized so heat + derated grid forces generator use but normal ops has reserve.' },
      { name: 'power.cooling_kw_per_deg_c_above', unit: 'kW/°C', get: (h) => String(h.power.cooling_kw_per_deg_c_above), label: 'SCENARIO_ASSUMPTION', why: 'Linear heat-to-cooling-load slope above 28 °C — a planning assumption, not an empirical relationship.' },
      { name: 'power.generator_capacity_kw', unit: 'kW', get: (h) => String(h.power.generator_capacity_kw), label: 'SYNTHETIC', why: 'Generator smaller than peak demand: outages produce a deficit even with fuel (constraint-coupled story).' },
      { name: 'power.fuel_litres', unit: 'litres', get: (h) => String(h.power.fuel_litres), label: 'SYNTHETIC', why: 'Fuel sized so a 36-hour full outage exhausts it mid-run (B10) unless resupplied.' },
    ],
  },
  {
    group: 'Supplies',
    rows: [
      { name: 'supplies.initial_cover_hours', unit: 'hours', get: (h) => String((h.supplies as { initial_cover_hours: number }).initial_cover_hours), label: 'SYNTHETIC', why: '36 h of cover at baseline consumption; flood preset blocks deliveries until cover drops below 24 h.' },
      { name: 'supplies.low_cover_hours', unit: 'hours', get: (h) => String((h.supplies as { low_cover_hours: number }).low_cover_hours), label: 'SYNTHETIC', why: 'R10 supply_low threshold.' },
    ],
  },
  {
    group: 'Thresholds and weights',
    rows: [
      { name: 'thresholds.occupancy_warn_pct', unit: '%', get: (h) => String(h.thresholds.occupancy_warn_pct), label: 'SYNTHETIC', why: 'R01/R02 warning threshold at 90% occupancy.' },
      { name: 'resilience_weights', unit: 'weights', get: (h) => Object.values(h.resilience_weights).join(' / '), label: 'SYNTHETIC', why: 'Penalty weights for the Resilience Index (sum 1.0); formula in docs/equations.md.' },
    ],
  },
]

export function AssumptionsPage() {
  const [hospital, setHospital] = useState<BaselineHospital | null>(null)
  const [modelVersion, setModelVersion] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    api.baseline(controller.signal)
      .then((r) => { setHospital(r.hospital as unknown as BaselineHospital); setModelVersion(String((r as unknown as { provenance: { model_version?: string } }).provenance?.model_version ?? '')) })
      .catch(() => setHospital(null))
    return () => controller.abort()
  }, [])

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-ink-700 bg-ink-850 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-mist-200">Assumptions and data</h2>
          <ProvenanceBadge kind="SYNTHETIC" />
          {modelVersion && <span className="text-xs text-mist-400">model {modelVersion}</span>}
        </div>
        <p className="mt-2 text-xs text-mist-400">
          {hospital?.hospital_name ?? 'Fictional General Hospital (synthetic)'}. Every number below is a labelled
          configuration input; all outputs elsewhere are CALCULATED from them. Scenario multipliers are planning
          assumptions, never empirical relationships.
        </p>
      </section>

      {hospital ? (
        PARAM_ROWS.map((group) => (
          <section key={group.group} className="rounded-lg border border-ink-700 bg-ink-850 p-4" aria-label={group.group}>
            <h3 className="text-sm font-semibold text-mist-200">{group.group}</h3>
            <div className="mt-2 overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-mist-400">
                    <th scope="col" className="px-2 py-1">Parameter</th>
                    <th scope="col" className="px-2 py-1">Value</th>
                    <th scope="col" className="px-2 py-1">Unit</th>
                    <th scope="col" className="px-2 py-1">Label</th>
                    <th scope="col" className="px-2 py-1">Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((row) => (
                    <tr key={row.name} className="border-t border-ink-700">
                      <td className="px-2 py-1 font-mono text-mist-300">{row.name}</td>
                      <td className="px-2 py-1 text-mist-200">{row.get(hospital)}</td>
                      <td className="px-2 py-1 text-mist-400">{row.unit}</td>
                      <td className="px-2 py-1"><ProvenanceBadge kind={row.label} /></td>
                      <td className="px-2 py-1 text-mist-400">{row.why}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      ) : (
        <div className="rounded-lg border border-dashed border-ink-600 p-8 text-center text-sm text-mist-400">
          Backend unreachable — showing nothing rather than hard-coded values. Start the API to review parameters.
        </div>
      )}

      <section className="rounded-lg border border-ink-700 bg-ink-850 p-4">
        <h3 className="text-sm font-semibold text-mist-200">Datasets and calibration path</h3>
        <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-mist-300">
          <li><span className="text-mist-200">MIMIC-IV v3.1 (PhysioNet)</span> — credentialed access under a data use agreement. Row-level data never enters this repo, prompts or logs. Only locally computed aggregates with small-cell suppression (cells &lt; 10 removed) may calibrate LOS/admission distributions, if your agreement allows. See scripts/calibrate_from_mimic.py.</li>
          <li><span className="text-mist-200">NHS England Bed Availability and Occupancy</span> — open data (verify licence and attribution). scripts/import_nhs_beds.py converts a downloaded file into data/reference/ for optional bed-count calibration. Neither dataset represents Mayo Clinic or this fictional hospital.</li>
          <li>The demo always runs on the synthetic baseline (rule: honest labels everywhere).</li>
        </ul>
      </section>

      <section className="rounded-lg border border-ink-700 bg-ink-850 p-4">
        <h3 className="text-sm font-semibold text-mist-200">Adapting to real hospital data</h3>
        <p className="mt-1 text-xs text-mist-400">
          Replace data/demo_hospital.json with local values: beds CSV (unit, physical_beds, surge_beds), staff CSV
          (unit, roster, patients_per_nurse), power CSV (grid_kw, critical_kw, noncritical_kw, generator_kw, fuel_l,
          l_per_kwh), supplies CSV (item, units_per_weighted_bed_hour, initial_cover_hours). Expert and engineering
          validation is required before any real use.
        </p>
      </section>
    </div>
  )
}
