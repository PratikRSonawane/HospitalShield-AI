/** ScenarioControls: preset picker, duration and stress inputs with ranges
 * from /api/v1/scenarios, inline backend errors, reset. */

import type { ScenarioInfo } from '@/types/domain'
import type { SimulationRequest } from '@/api/client'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'

export const DEFAULT_REQUEST: SimulationRequest = {
  scenario: 'heatwave_power_outage',
  hospital_profile: 'demo',
  duration_hours: 72,
  weather: { mode: 'synthetic_profile', max_temperature_c: 43, min_temperature_c: 30, humidity_pct: 55 },
  stress: { arrival_multiplier: 1.15, los_multiplier: 1.5, staff_availability_fraction: 0.9, power_supply_fraction: 0.8 },
  outage: { start_hour: 24, duration_hours: 36, grid_fraction: 0.0 },
  access: null,
  backup: { generator_availability_fraction: 1.0 },
  interventions: null,
  stochastic: false,
  seed: 42,
}

export function applyPreset(request: SimulationRequest, presetName: string): SimulationRequest {
  const overrides: Record<string, Partial<SimulationRequest>> = {
    normal_operations: {
      weather: { mode: 'synthetic_profile', max_temperature_c: 30, min_temperature_c: 20, humidity_pct: 55 },
      stress: { arrival_multiplier: 1.0, los_multiplier: 1.0, staff_availability_fraction: 1.0, power_supply_fraction: 1.0 },
      outage: null, access: null, backup: { generator_availability_fraction: 1.0 },
    },
    heatwave_power_stress: {
      weather: { mode: 'synthetic_profile', max_temperature_c: 41, min_temperature_c: 29, humidity_pct: 55 },
      stress: { arrival_multiplier: 1.15, los_multiplier: 1.5, staff_availability_fraction: 0.9, power_supply_fraction: 0.8 },
      outage: null, access: null, backup: { generator_availability_fraction: 1.0 },
    },
    heatwave_power_outage: {
      weather: { mode: 'synthetic_profile', max_temperature_c: 43, min_temperature_c: 30, humidity_pct: 55 },
      stress: { arrival_multiplier: 1.15, los_multiplier: 1.5, staff_availability_fraction: 0.9, power_supply_fraction: 0.8 },
      outage: { start_hour: 24, duration_hours: 36, grid_fraction: 0.0 }, access: null,
      backup: { generator_availability_fraction: 1.0 },
    },
    flood_storm_access: {
      weather: { mode: 'synthetic_profile', max_temperature_c: 30, min_temperature_c: 22, humidity_pct: 90 },
      stress: { arrival_multiplier: 1.0, los_multiplier: 1.0, staff_availability_fraction: 0.95, power_supply_fraction: 0.9 },
      outage: null,
      access: { start_hour: 18, duration_hours: 24, staff_access_fraction: 0.6, delivery_fraction: 0.15, arrival_multiplier: 1.4 },
      backup: { generator_availability_fraction: 0.6 },
    },
  }
  return { ...request, scenario: presetName as SimulationRequest['scenario'], ...(overrides[presetName] ?? {}) }
}

function NumField({ label, value, min, max, step, unit, onChange, disabled }: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  onChange: (n: number) => void
  disabled?: boolean
}) {
  return (
    <label className="block text-xs">
      <span className="text-mist-400">{label} <span className="text-mist-600">({min}–{max} {unit})</span></span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full rounded border border-ink-600 bg-ink-900 px-2 py-1.5 text-sm text-mist-200 disabled:opacity-50"
      />
    </label>
  )
}

export function ScenarioControls({ request, onChange, info, error, errorDetails, onRun, loading, disabled }: {
  request: SimulationRequest
  onChange: (req: SimulationRequest) => void
  info: ScenarioInfo | null
  error: string | null
  errorDetails: { field: string; reason: string }[]
  onRun: () => void
  loading: boolean
  disabled?: boolean
}) {
  const set = (patch: Partial<SimulationRequest>) => onChange({ ...request, ...patch })
  const setStress = (patch: Partial<NonNullable<SimulationRequest['stress']>>) =>
    set({ stress: { ...request.stress, ...patch } as NonNullable<SimulationRequest['stress']> })
  const locked = disabled === true

  return (
    <div className={`space-y-4 rounded-lg border border-ink-700 bg-ink-850 p-4 ${locked ? 'opacity-70' : ''}`}>
      <div>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-mist-200">Scenario</h3>
          <ProvenanceBadge kind="SCENARIO_ASSUMPTION" />
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2" role="radiogroup" aria-label="Scenario preset">
          {(info ? Object.keys(info.presets) : ['normal_operations', 'heatwave_power_stress', 'heatwave_power_outage', 'flood_storm_access']).map((name) => (
            <button
              key={name}
              type="button"
              role="radio"
              aria-checked={request.scenario === name}
              disabled={locked}
              onClick={() => onChange(applyPreset(request, name))}
              className={`rounded border px-2 py-2 text-xs ${request.scenario === name ? 'border-teal-400 bg-teal-400/10 text-teal-400' : 'border-ink-600 text-mist-300 hover:border-ink-500'} disabled:cursor-not-allowed`}
            >
              {name.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
        {(() => { const preset = (info?.presets as unknown as Record<string, { description?: string } | undefined>)?.[request.scenario]; return preset?.description })() && (
          <p className="mt-2 text-xs text-mist-400">{String((info?.presets as unknown as Record<string, { description?: string }>)[request.scenario]?.description)}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <NumField label="Duration" value={request.duration_hours} min={1} max={72} step={1} unit="h"
          disabled={locked} onChange={(n) => set({ duration_hours: Math.min(Math.max(n, 1), 72) })} />
        <NumField label="Max temperature" value={request.weather?.max_temperature_c ?? 41} min={-10} max={55} step={1} unit="°C"
          disabled={locked} onChange={(n) => set({ weather: { mode: 'synthetic_profile', max_temperature_c: n, min_temperature_c: request.weather?.min_temperature_c ?? null, humidity_pct: request.weather?.humidity_pct ?? 55 } })} />
        <NumField label="Arrival multiplier" value={request.stress?.arrival_multiplier ?? 1.25} min={0} max={3} step={0.05} unit="×"
          disabled={locked} onChange={(n) => setStress({ arrival_multiplier: n })} />
        <NumField label="LOS multiplier" value={request.stress?.los_multiplier ?? 1.0} min={0.5} max={2} step={0.05} unit="×"
          disabled={locked} onChange={(n) => setStress({ los_multiplier: n })} />
        <NumField label="Staff availability" value={request.stress?.staff_availability_fraction ?? 0.9} min={0} max={1} step={0.05} unit=""
          disabled={locked} onChange={(n) => setStress({ staff_availability_fraction: n })} />
        <NumField label="Grid supply" value={request.stress?.power_supply_fraction ?? 0.8} min={0} max={1} step={0.05} unit=""
          disabled={locked} onChange={(n) => setStress({ power_supply_fraction: n })} />
        <NumField label="Outage start" value={request.outage?.start_hour ?? 0} min={0} max={71} step={1} unit="h"
          disabled={locked || !request.outage} onChange={(n) => set({ outage: { ...(request.outage ?? { duration_hours: 0, grid_fraction: 0 }), start_hour: n } })} />
        <NumField label="Outage length" value={request.outage?.duration_hours ?? 0} min={0} max={72} step={1} unit="h"
          disabled={locked || !request.outage} onChange={(n) => set({ outage: { ...(request.outage ?? { start_hour: 0, grid_fraction: 0 }), duration_hours: n } })} />
        <NumField label="Generator availability" value={request.backup?.generator_availability_fraction ?? 1} min={0} max={1} step={0.05} unit=""
          disabled={locked} onChange={(n) => set({ backup: { generator_availability_fraction: n } })} />
        <NumField label="Seed" value={request.seed} min={0} max={2147483647} step={1} unit=""
          disabled={locked} onChange={(n) => set({ seed: n })} />
      </div>

      <label className="flex items-center gap-2 text-xs text-mist-400">
        <input type="checkbox" checked={request.stochastic} disabled={locked}
          onChange={(e) => set({ stochastic: e.target.checked })} className="accent-teal-400" />
        Stochastic mode (seeded Poisson/Binomial demand randomness)
      </label>

      {error && (
        <div role="alert" className="rounded border border-rose-400/40 bg-rose-400/10 p-2 text-xs text-rose-400">
          {error}
          {errorDetails.length > 0 && (
            <ul className="mt-1 list-inside list-disc text-mist-300">
              {errorDetails.map((d, i) => (
                <li key={i}><span className="text-mist-200">{d.field}</span>: {d.reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onRun}
          disabled={loading || locked}
          className="flex-1 rounded bg-teal-500 px-3 py-2 text-sm font-semibold text-ink-950 hover:bg-teal-400 disabled:opacity-50"
        >
          {loading ? 'Running…' : 'Run simulation'}
        </button>
        <button
          type="button"
          onClick={() => onChange(applyPreset(request, request.scenario))}
          disabled={locked}
          className="rounded border border-ink-600 px-3 py-2 text-sm text-mist-300 hover:border-ink-500 disabled:opacity-50"
        >
          Reset
        </button>
      </div>
    </div>
  )
}
