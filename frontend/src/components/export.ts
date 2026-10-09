/** Export helpers: JSON download, CSV series download, print. */

import type { SimulationResponse } from '@/types/domain'

export function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  triggerDownload(blob, filename)
}

export function downloadCsv(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return
  const columns = Object.keys(rows[0])
  const lines = [columns.join(',')]
  for (const row of rows) {
    lines.push(columns.map((c) => JSON.stringify(row[c] ?? '')).join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  triggerDownload(blob, filename)
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function exportResult(result: SimulationResponse) {
  downloadJson(result, `hospitalshield-run-${result.run_id}.json`)
}

export function exportSeriesCsv(result: SimulationResponse) {
  const rows = result.series.map((r) => ({
    hour: r.hour,
    temperature_c: r.temperature_c,
    demand_kw: r.power.demand_kw,
    available_supply_kw: r.power.available_supply_kw,
    deficit_kw: r.power.deficit_kw,
    critical_at_risk_kw: r.power.critical_at_risk_kw,
    fuel_l: r.power.fuel_l,
    ward_occupied: r.units.ward.occupied,
    ward_usable: r.units.ward.usable_beds,
    ward_occupancy_pct: r.units.ward.occupancy_pct,
    icu_occupied: r.units.icu.occupied,
    icu_usable: r.units.icu.usable_beds,
    icu_occupancy_pct: r.units.icu.occupancy_pct,
    ed_occupied: r.units.ed.occupied,
    ed_waiting: r.ed.waiting,
    ed_boarding: (r.ed.boarding_ward ?? 0) + (r.ed.boarding_icu ?? 0),
    binding_constraint: r.binding_constraint,
  }))
  downloadCsv(rows, `hospitalshield-series-${result.run_id}.csv`)
}
