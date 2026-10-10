/** InterventionPanel: the five interventions with sizes; feasibility errors
 * from the backend are shown verbatim. */

import { useState } from 'react'
import type { SimulationRequest } from '@/api/client'

interface Surge { unit: 'ward' | 'icu'; beds: number; start_hour: number }
type Unit = 'ed' | 'ward' | 'icu'
interface Move { from_unit: Unit; to_unit: Unit; nurses: number; start_hour: number }
interface Shed { kw: number; start_hour: number; end_hour: number }
interface Recall { unit: Unit; nurses: number; start_hour: number }
interface Resupply { fuel_l: number; items?: Record<string, number>; start_hour: number }

export interface InterventionDraft {
  surge: Surge[]
  moves: Move[]
  sheds: Shed[]
  recalls: Recall[]
  resupplies: Resupply[]
}

export function emptyDraft(): InterventionDraft {
  return { surge: [], moves: [], sheds: [], recalls: [], resupplies: [] }
}

export function draftToRequest(draft: InterventionDraft, base: SimulationRequest): SimulationRequest {
  const hasAny = draft.surge.length + draft.moves.length + draft.sheds.length + draft.recalls.length + draft.resupplies.length > 0
  return {
    ...base,
    interventions: hasAny
      ? {
          activate_surge_beds: draft.surge,
          reallocate_staff: draft.moves,
          reduce_noncritical_load_kw: draft.sheds,
          recall_staff: draft.recalls,
          emergency_resupply: draft.resupplies,
        }
      : null,
  }
}

const btn = 'rounded-md border border-ink-700/80 bg-ink-850 px-2.5 py-1 text-xs font-medium text-mist-300 transition-all hover:border-teal-400 hover:text-teal-300 disabled:opacity-40'

export function InterventionPanel({ draft, onChange, errorDetails, duration, locked }: {
  draft: InterventionDraft
  onChange: (d: InterventionDraft) => void
  errorDetails: { field: string; reason: string }[]
  duration: number
  locked?: boolean
}) {
  const [open, setOpen] = useState(false)
  const disabled = locked === true

  const add = (patch: Partial<InterventionDraft>) => onChange({ ...draft, ...patch })

  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-tight text-mist-100">Interventions</h3>
        <button type="button" className={btn} onClick={() => setOpen(!open)} aria-expanded={open} disabled={disabled}>
          {open ? 'Hide' : 'Edit interventions'}
        </button>
      </div>

      {errorDetails.length > 0 && (
        <div role="alert" className="mt-3 rounded border border-rose-400/40 bg-rose-400/10 p-2 text-xs text-rose-400">
          {errorDetails.map((d, i) => (
            <p key={i}><span className="font-semibold">{d.field}</span>: {d.reason}</p>
          ))}
        </div>
      )}

      {!open ? (
        <p className="mt-2 text-xs text-mist-400">
          {draft.surge.length + draft.moves.length + draft.sheds.length + draft.recalls.length + draft.resupplies.length === 0
            ? 'No interventions configured — this run is the baseline.'
            : `${draft.surge.length} surge · ${draft.moves.length} moves · ${draft.sheds.length} shed · ${draft.recalls.length} recall · ${draft.resupplies.length} resupply`}
        </p>
      ) : (
        <div className="mt-3 space-y-4 text-xs">
          <section aria-label="Activate surge beds">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-mist-300">Surge beds (6 h activation delay)</span>
              <button type="button" className={btn} disabled={disabled}
                onClick={() => add({ surge: [...draft.surge, { unit: 'ward', beds: 8, start_hour: 6 }] })}>+ add</button>
            </div>
            {draft.surge.map((s, i) => (
              <div key={i} className="mt-2 flex items-center gap-2">
                <select value={s.unit} disabled={disabled} aria-label="surge unit"
                  onChange={(e) => add({ surge: draft.surge.map((x, j) => (j === i ? { ...x, unit: e.target.value as 'ward' | 'icu' } : x)) })}
                  className="rounded border border-ink-600 bg-ink-900 px-1 py-1">
                  <option value="ward">ward</option>
                  <option value="icu">icu</option>
                </select>
                <input type="number" min={0} max={30} value={s.beds} disabled={disabled} aria-label="surge beds"
                  onChange={(e) => add({ surge: draft.surge.map((x, j) => (j === i ? { ...x, beds: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <span className="text-mist-400">beds @ h</span>
                <input type="number" min={0} max={duration - 1} value={s.start_hour} disabled={disabled} aria-label="surge start hour"
                  onChange={(e) => add({ surge: draft.surge.map((x, j) => (j === i ? { ...x, start_hour: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <button type="button" className="text-rose-400" disabled={disabled}
                  onClick={() => add({ surge: draft.surge.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
          </section>

          <section aria-label="Reallocate staff">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-mist-300">Reallocate staff (source floor enforced)</span>
              <button type="button" className={btn} disabled={disabled}
                onClick={() => add({ moves: [...draft.moves, { from_unit: 'ward', to_unit: 'ed', nurses: 2, start_hour: 6 }] })}>+ add</button>
            </div>
            {draft.moves.map((m, i) => (
              <div key={i} className="mt-2 flex items-center gap-2">
                <select value={m.from_unit} disabled={disabled} aria-label="from unit"
                  onChange={(e) => add({ moves: draft.moves.map((x, j) => (j === i ? { ...x, from_unit: e.target.value as Unit } : x)) })}
                  className="rounded border border-ink-600 bg-ink-900 px-1 py-1">
                  {['ed', 'ward', 'icu'].map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
                <span>→</span>
                <select value={m.to_unit} disabled={disabled} aria-label="to unit"
                  onChange={(e) => add({ moves: draft.moves.map((x, j) => (j === i ? { ...x, to_unit: e.target.value as Unit } : x)) })}
                  className="rounded border border-ink-600 bg-ink-900 px-1 py-1">
                  {['ed', 'ward', 'icu'].map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
                <input type="number" min={0} max={10} value={m.nurses} disabled={disabled} aria-label="nurses"
                  onChange={(e) => add({ moves: draft.moves.map((x, j) => (j === i ? { ...x, nurses: Number(e.target.value) } : x)) })}
                  className="w-14 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <span className="text-mist-400">nurses @ h</span>
                <input type="number" min={0} max={duration - 1} value={m.start_hour} disabled={disabled} aria-label="move start hour"
                  onChange={(e) => add({ moves: draft.moves.map((x, j) => (j === i ? { ...x, start_hour: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <button type="button" className="text-rose-400" disabled={disabled}
                  onClick={() => add({ moves: draft.moves.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
          </section>

          <section aria-label="Shed non-critical load">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-mist-300">Shed non-critical load (capped, never clinical)</span>
              <button type="button" className={btn} disabled={disabled}
                onClick={() => add({ sheds: [...draft.sheds, { kw: 40, start_hour: 24, end_hour: duration }] })}>+ add</button>
            </div>
            {draft.sheds.map((s, i) => (
              <div key={i} className="mt-2 flex items-center gap-2">
                <input type="number" min={0} max={200} value={s.kw} disabled={disabled} aria-label="shed kW"
                  onChange={(e) => add({ sheds: draft.sheds.map((x, j) => (j === i ? { ...x, kw: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <span className="text-mist-400">kW from h</span>
                <input type="number" min={0} max={duration - 1} value={s.start_hour} disabled={disabled} aria-label="shed start"
                  onChange={(e) => add({ sheds: draft.sheds.map((x, j) => (j === i ? { ...x, start_hour: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <span className="text-mist-400">to h</span>
                <input type="number" min={1} max={duration} value={s.end_hour} disabled={disabled} aria-label="shed end"
                  onChange={(e) => add({ sheds: draft.sheds.map((x, j) => (j === i ? { ...x, end_hour: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <button type="button" className="text-rose-400" disabled={disabled}
                  onClick={() => add({ sheds: draft.sheds.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
          </section>

          <section aria-label="Recall off-duty staff">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-mist-300">Recall off-duty staff (4 h lead time)</span>
              <button type="button" className={btn} disabled={disabled}
                onClick={() => add({ recalls: [...draft.recalls, { unit: 'ward', nurses: 2, start_hour: 0 }] })}>+ add</button>
            </div>
            {draft.recalls.map((r, i) => (
              <div key={i} className="mt-2 flex items-center gap-2">
                <select value={r.unit} disabled={disabled} aria-label="recall unit"
                  onChange={(e) => add({ recalls: draft.recalls.map((x, j) => (j === i ? { ...x, unit: e.target.value as Unit } : x)) })}
                  className="rounded border border-ink-600 bg-ink-900 px-1 py-1">
                  {['ed', 'ward', 'icu'].map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
                <input type="number" min={0} max={5} value={r.nurses} disabled={disabled} aria-label="recall nurses"
                  onChange={(e) => add({ recalls: draft.recalls.map((x, j) => (j === i ? { ...x, nurses: Number(e.target.value) } : x)) })}
                  className="w-14 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <span className="text-mist-400">nurses @ h</span>
                <input type="number" min={0} max={duration - 1} value={r.start_hour} disabled={disabled} aria-label="recall start hour"
                  onChange={(e) => add({ recalls: draft.recalls.map((x, j) => (j === i ? { ...x, start_hour: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <button type="button" className="text-rose-400" disabled={disabled}
                  onClick={() => add({ recalls: draft.recalls.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
          </section>

          <section aria-label="Emergency resupply">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-mist-300">Emergency resupply (12 h lead time)</span>
              <button type="button" className={btn} disabled={disabled}
                onClick={() => add({ resupplies: [...draft.resupplies, { fuel_l: 0, items: { oxygen: 1500 }, start_hour: 0 }] })}>+ add</button>
            </div>
            {draft.resupplies.map((r, i) => (
              <div key={i} className="mt-2 flex items-center gap-2">
                <select
                  value={r.fuel_l ? 'fuel' : Object.keys(r.items ?? {})[0] ?? 'oxygen'}
                  disabled={disabled}
                  aria-label="resupply item"
                  onChange={(e) => {
                    const v = e.target.value
                    add({
                      resupplies: draft.resupplies.map((x, j) =>
                        j === i ? (v === 'fuel' ? { fuel_l: 800, items: undefined, start_hour: x.start_hour } : { fuel_l: 0, items: { [v]: 1500 }, start_hour: x.start_hour }) : x),
                    })
                  }}
                  className="rounded border border-ink-600 bg-ink-900 px-1 py-1">
                  <option value="fuel">fuel (L)</option>
                  <option value="oxygen">oxygen</option>
                  <option value="essential_meds">essential meds</option>
                </select>
                <input type="number" min={0} value={r.fuel_l ?? Object.values(r.items ?? {})[0] ?? 0} disabled={disabled} aria-label="amount"
                  onChange={(e) => {
                    const n = Number(e.target.value)
                    add({
                      resupplies: draft.resupplies.map((x, j) =>
                        j === i ? (x.fuel_l ? { fuel_l: n, items: undefined, start_hour: x.start_hour } : { fuel_l: 0, items: { [(Object.keys(x.items ?? {}))[0] ?? 'oxygen']: n }, start_hour: x.start_hour }) : x),
                    })
                  }}
                  className="w-20 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <span className="text-mist-400">@ h</span>
                <input type="number" min={0} max={duration - 1} value={r.start_hour} disabled={disabled} aria-label="request hour"
                  onChange={(e) => add({ resupplies: draft.resupplies.map((x, j) => (j === i ? { ...x, start_hour: Number(e.target.value) } : x)) })}
                  className="w-16 rounded border border-ink-600 bg-ink-900 px-1 py-1" />
                <button type="button" className="text-rose-400" disabled={disabled}
                  onClick={() => add({ resupplies: draft.resupplies.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
          </section>
        </div>
      )}
    </div>
  )
}
