/** CompareView: side-by-side KPIs, absolute + delta table, attribution and
 * "why it changed" explanations — all backend computed. */

import type { ComparisonResponse } from '@/types/domain'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'

const METRICS: { key: string; label: string; unit: string; goodWhenDown?: boolean; digits?: number }[] = [
  { key: 'resilience_index', label: 'Resilience Index', unit: '0-100', goodWhenDown: false, digits: 1 },
  { key: 'peak_ward_occupancy_pct', label: 'Peak ward occupancy', unit: '%', digits: 1 },
  { key: 'peak_icu_occupancy_pct', label: 'Peak ICU occupancy', unit: '%', digits: 1 },
  { key: 'peak_ed_occupancy_pct', label: 'Peak ED occupancy', unit: '%', digits: 1 },
  { key: 'peak_ed_waiting', label: 'Peak ED waiting', unit: 'patients' },
  { key: 'peak_ed_boarding', label: 'Peak ED boarding', unit: 'patients' },
  { key: 'overflow_patient_hours', label: 'Overflow patient-hours', unit: 'p-h' },
  { key: 'staff_shortfall_nurse_hours', label: 'Nurse shortfall', unit: 'nurse-h' },
  { key: 'hours_ward_above_threshold', label: 'Hours ward > 90%', unit: 'h' },
  { key: 'hours_icu_above_threshold', label: 'Hours ICU > 90%', unit: 'h' },
  { key: 'hours_power_deficit', label: 'Hours power deficit', unit: 'h' },
  { key: 'energy_unserved_kwh', label: 'Energy unserved', unit: 'kWh', digits: 0 },
  { key: 'hours_critical_load_at_risk', label: 'Hours critical at risk', unit: 'h' },
  { key: 'fuel_remaining_l', label: 'Fuel remaining', unit: 'L', goodWhenDown: false, digits: 0 },
  { key: 'hours_to_fuel_exhaustion', label: 'Hours to fuel exhaustion', unit: 'h', goodWhenDown: false },
]

function num(v: unknown, digits = 1): string {
  return typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—'
}

type Delta = { absolute?: number | null; relative?: number | null }

function deltasOf(comparison: ComparisonResponse): Record<string, Delta> {
  return (comparison.deltas ?? {}) as Record<string, Delta>
}

export function CompareView({ comparison }: { comparison: ComparisonResponse }) {
  const b = comparison.baseline.summary
  const t = comparison.treatment.summary
  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold tracking-tight text-mist-100">Side by side</h3>
          <ProvenanceBadge kind="CALCULATED" />
          <span className="font-mono text-[11px] tabular-nums text-mist-400">
            identical initial state, seed {comparison.seed} and weather · run {comparison.baseline.run_id.slice(0, 8)}… vs {comparison.treatment.run_id.slice(0, 8)}…
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-md border border-ink-700/80 bg-ink-950/60 p-3 transition-colors hover:border-ink-600 shadow-xs">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-mist-400">Baseline</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-mist-100">{num(b.resilience_index)}</div>
            <div className="mt-0.5 text-xs text-mist-400">Resilience Index</div>
          </div>
          <div className="rounded-md border border-teal-500/40 bg-teal-500/10 p-3 transition-colors shadow-xs">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-mist-400">With interventions</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-teal-300">{num(t.resilience_index)}</div>
            <div className="mt-0.5 text-xs text-mist-400 tabular-nums">
              Δ {(() => { const d = deltasOf(comparison).resilience_index; return typeof d?.absolute === 'number' ? ((d.absolute > 0 ? '+' : '') + num(d.absolute)) : '—' })()}
            </div>
          </div>
          <div className="rounded-md border border-ink-700/80 bg-ink-950/60 p-3 transition-colors hover:border-ink-600 shadow-xs">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-mist-400">Overflow patient-hours</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-mist-100">{num(b.overflow_patient_hours, 0)} → {num(t.overflow_patient_hours, 0)}</div>
            <div className="mt-0.5 text-xs text-mist-400">baseline → intervention</div>
          </div>
          <div className="rounded-md border border-ink-700/80 bg-ink-950/60 p-3 transition-colors hover:border-ink-600 shadow-xs">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-mist-400">Energy unserved</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-mist-100">{num(b.energy_unserved_kwh, 0)} → {num(t.energy_unserved_kwh, 0)}</div>
            <div className="mt-0.5 text-xs text-mist-400">kWh</div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
        <h3 className="text-sm font-semibold tracking-tight text-mist-100">Absolute and delta table</h3>
        <div className="mt-2.5 overflow-auto rounded border border-ink-800/80">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wider text-mist-400 border-b border-ink-800 bg-ink-950/40">
                <th scope="col" className="px-2.5 py-1.5">Metric</th>
                <th scope="col" className="px-2.5 py-1.5">Baseline</th>
                <th scope="col" className="px-2.5 py-1.5">Intervention</th>
                <th scope="col" className="px-2.5 py-1.5">Δ absolute</th>
                <th scope="col" className="px-2.5 py-1.5">Δ relative</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.map((m) => {
                const bv = (b as unknown as Record<string, number | null>)[m.key]
                const tv = (t as unknown as Record<string, number | null>)[m.key]
                const deltas = deltasOf(comparison)
                const delta = deltas[m.key]?.absolute
                const rel = deltas[m.key]?.relative
                const better = typeof delta === 'number' && delta !== 0
                  ? ((delta < 0) === (m.goodWhenDown ?? true) ? 'text-teal-400' : 'text-rose-400')
                  : 'text-mist-400'
                return (
                  <tr key={m.key} className="border-t border-ink-800/50 hover:bg-ink-850/40">
                    <td className="px-2.5 py-1.5 font-medium text-mist-200">
                      {m.label} <span className="font-mono text-[10px] text-mist-400">{m.unit}</span>
                    </td>
                    <td className="px-2.5 py-1.5 font-mono tabular-nums text-mist-200">{bv == null ? '—' : num(bv, m.digits ?? 1)}</td>
                    <td className="px-2.5 py-1.5 font-mono tabular-nums text-mist-200">{tv == null ? '—' : num(tv, m.digits ?? 1)}</td>
                    <td className={`px-2.5 py-1.5 font-mono tabular-nums ${better}`}>
                      {typeof delta === 'number' ? ((delta > 0 ? '+' : '') + num(delta, m.digits ?? 1)) : '—'}
                    </td>
                    <td className="px-2.5 py-1.5 font-mono tabular-nums text-mist-400">
                      {typeof rel === 'number' ? `${(rel * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
        <h3 className="text-sm font-semibold tracking-tight text-mist-100">Attribution (each intervention alone)</h3>
        <ul className="mt-2.5 space-y-2 text-xs">
          {comparison.attribution?.map((a, i) => {
            const ri = ((a.deltas as unknown as Record<string, Delta>)?.resilience_index)?.absolute
            return (
              <li key={i} className="rounded-md border border-ink-800/80 bg-ink-950/60 p-2.5 transition-colors hover:border-ink-700">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-mist-200">{a.intervention}</span>
                  <span className={`font-mono text-[11px] tabular-nums ${typeof ri === 'number' && ri !== 0 ? (ri > 0 ? 'text-teal-400' : 'text-rose-400') : 'text-mist-400'}`}>
                    Δ resilience {typeof ri === 'number' ? (ri > 0 ? '+' : '') + ri.toFixed(1) : '—'}
                  </span>
                </div>
                <p className="mt-1 text-xs text-mist-400 leading-normal">{a.explanation}</p>
              </li>
            )
          })}
        </ul>
      </section>

      <section className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
        <h3 className="text-sm font-semibold tracking-tight text-mist-100">Why it changed</h3>
        <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-relaxed text-mist-300">
          {(comparison.explanations ?? []).map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      </section>
    </div>
  )
}
