/** Scenario Lab: controls + interventions + live results + planner. */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type ScenarioInfo, type SimulationRequest } from '@/api/client'
import { useRun } from '@/state/RunContext'
import { ScenarioControls, applyPreset } from '@/components/ScenarioControls'
import { InterventionPanel, draftToRequest, emptyDraft, type InterventionDraft } from '@/components/InterventionPanel'
import { ActionPlanTimeline } from '@/components/ActionPlanTimeline'
import { OccupancyChart, PowerChart, chartTable } from '@/components/charts'
import { ChartFrame } from '@/components/ChartFrame'
import { KpiCard } from '@/components/KpiCard'

export function ScenarioLabPage() {
  const run = useRun()
  const navigate = useNavigate()
  const [info, setInfo] = useState<ScenarioInfo | null>(null)
  const [request, setRequest] = useState<SimulationRequest>(
    () => applyPreset({
      scenario: 'heatwave_power_outage', hospital_profile: 'demo', duration_hours: 72,
      weather: { mode: 'synthetic_profile', max_temperature_c: 43, min_temperature_c: 30, humidity_pct: 55 },
      stress: { arrival_multiplier: 1.15, los_multiplier: 1.5, staff_availability_fraction: 0.9, power_supply_fraction: 0.8 },
      outage: { start_hour: 24, duration_hours: 36, grid_fraction: 0.0 }, access: null,
      backup: { generator_availability_fraction: 1.0 }, interventions: null, stochastic: false, seed: 42,
    }, 'heatwave_power_outage'))
  const [draft, setDraft] = useState<InterventionDraft>(emptyDraft())

  useEffect(() => {
    const controller = new AbortController()
    api.scenarios(controller.signal).then(setInfo).catch(() => setInfo(null))
    return () => controller.abort()
  }, [])

  const effectiveRequest = draftToRequest(draft, request)
  const locked = run.offline

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="space-y-4">
        <ScenarioControls
          request={request}
          onChange={(req) => { setRequest(req); setDraft(emptyDraft()) }}
          info={info}
          error={run.error}
          errorDetails={run.errorDetails}
          onRun={() => void run.runScenario(effectiveRequest)}
          loading={run.loading}
          disabled={locked}
        />
        <InterventionPanel
          draft={draft}
          onChange={setDraft}
          errorDetails={run.errorDetails}
          duration={request.duration_hours}
          locked={locked}
        />
      </div>

      <div className="space-y-4">
        {run.plan && (
          <ActionPlanTimeline
            plan={run.plan}
            horizon={request.duration_hours}
            applying={run.loading}
            onApply={() => { const currentPlan = run.plan; if (currentPlan) void run.applyPlanToComparison(request, currentPlan).then((ok) => { if (ok) void navigate('/compare') }) }}
          />
        )}

        {!run.result && !run.loading && (
          <div className="rounded-lg border border-dashed border-ink-700/80 bg-ink-900/30 p-10 text-center text-xs leading-relaxed text-mist-300">
            Configure the scenario and run it. Or{' '}
            <button className="font-medium text-teal-400 underline hover:text-teal-300" onClick={() => void run.runPlanner(request)}>
              let the planner find the best sequence
            </button>{' '}
            for this scenario.
          </div>
        )}

        {run.result && (
          <>
            <div className="flex flex-wrap items-center gap-2 no-print">
              <button
                className="rounded-md bg-teal-500 px-3.5 py-1.5 text-xs font-semibold text-ink-950 shadow-xs transition-all hover:bg-teal-400 active:scale-[0.99] disabled:opacity-50"
                onClick={() => void run.runPlanner(request)}
                disabled={run.planning || locked}
              >
                {run.planning ? 'Searching (beam search)…' : '🧭 Find optimal action sequence'}
              </button>
              <span className="text-xs text-mist-400 leading-normal">
                Deterministic search over surge / staff / shed / recall / resupply; respects lead times and feasibility.
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <KpiCard label="Resilience Index" value={run.result.summary.resilience_index.toFixed(1)} unit="0-100" />
              <KpiCard label="Overflow patient-hours" value={run.result.summary.overflow_patient_hours} unit="p-h" />
              <KpiCard label="Hours power deficit" value={run.result.summary.hours_power_deficit} unit="h" />
              <KpiCard label="Nurse shortfall" value={run.result.summary.staff_shortfall_nurse_hours} unit="nurse-h" />
            </div>

            <ChartFrame title="Occupancy by unit" subtitle="Percent; amber line = 90% warning threshold"
              table={chartTable(run.result.series, (r) => [r.units.ward.occupancy_pct?.toFixed(1) ?? '—', r.units.icu.occupancy_pct?.toFixed(1) ?? '—'], ['hour', 'ward %', 'icu %'])}>
              <OccupancyChart rows={run.result.series} highlight={run.highlightRange} selectedHour={run.selectedHour} />
            </ChartFrame>
            <ChartFrame title="Power demand vs supply" subtitle="kW with deficit shading"
              table={chartTable(run.result.series, (r) => [r.power.demand_kw.toFixed(0), r.power.available_supply_kw.toFixed(0), r.power.deficit_kw.toFixed(0)], ['hour', 'demand', 'supply', 'deficit'])}>
              <PowerChart rows={run.result.series} highlight={run.highlightRange} selectedHour={run.selectedHour} />
            </ChartFrame>
          </>
        )}
      </div>
    </div>
  )
}
