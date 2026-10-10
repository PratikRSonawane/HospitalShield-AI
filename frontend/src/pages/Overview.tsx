/** Overview (Command Center): run the current scenario, headline KPIs,
 * alerts and the hospital map. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ScenarioInfo, type SimulationRequest } from '@/api/client'
import { useRun } from '@/state/RunContext'
import { KpiCard } from '@/components/KpiCard'
import { AlertPanel } from '@/components/AlertPanel'
import { HospitalMap } from '@/components/HospitalMap'
import { ScenarioControls, DEFAULT_REQUEST } from '@/components/ScenarioControls'
import { PowerChart, chartTable } from '@/components/charts'
import { ChartFrame } from '@/components/ChartFrame'
import { exportResult, exportSeriesCsv } from '@/components/export'

export function OverviewPage() {
  const run = useRun()
  const [info, setInfo] = useState<ScenarioInfo | null>(null)
  const [request, setRequest] = useState<SimulationRequest>(() => run.request ?? DEFAULT_REQUEST)

  useEffect(() => {
    const controller = new AbortController()
    api.scenarios(controller.signal).then(setInfo).catch(() => setInfo(null))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!run.request) return
    setRequest(run.request)
  }, [run.request])



  const result = run.result
  const summary = result?.summary

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="space-y-4">
        <ScenarioControls
          request={request}
          onChange={setRequest}
          info={info}
          error={run.error}
          errorDetails={run.errorDetails}
          loading={run.loading}
          onRun={() => { if (request) void run.runScenario(request) }}
        />
        <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 text-xs text-mist-400 transition-colors hover:border-ink-600/70">
          <p className="text-xs font-semibold tracking-tight text-mist-200">Mission</p>
          <p className="mt-1 text-xs leading-relaxed text-mist-400">scenario → calculated impact → failure points → actions in the best order → measured before/after.</p>
          <div className="mt-3 flex flex-col gap-2">
            <Link to="/failures" className="rounded-md border border-ink-700/80 bg-ink-950/40 px-3 py-1.5 text-center text-xs font-medium text-mist-300 transition-all hover:border-teal-400 hover:text-teal-300">Failure points & plan →</Link>
            <Link to="/compare" className="rounded-md border border-ink-700/80 bg-ink-950/40 px-3 py-1.5 text-center text-xs font-medium text-mist-300 transition-all hover:border-teal-400 hover:text-teal-300">Compare runs →</Link>
          </div>
          {result && (
            <div className="mt-3 flex gap-2 no-print">
              <button className="flex-1 rounded-md border border-ink-700/80 bg-ink-950/40 px-2 py-1 text-xs font-medium text-mist-300 transition-all hover:border-teal-400 hover:text-teal-300" onClick={() => exportResult(result)}>Export JSON</button>
              <button className="flex-1 rounded-md border border-ink-700/80 bg-ink-950/40 px-2 py-1 text-xs font-medium text-mist-300 transition-all hover:border-teal-400 hover:text-teal-300" onClick={() => exportSeriesCsv(result)}>Export CSV</button>
              <button className="rounded-md border border-ink-700/80 bg-ink-950/40 px-2 py-1 text-xs font-medium text-mist-300 transition-all hover:border-teal-400 hover:text-teal-300" onClick={() => window.print()}>Print</button>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {!result && !run.loading && (
          <div className="rounded-lg border border-dashed border-ink-700/80 bg-ink-900/30 p-10 text-center">
            <p className="text-sm font-medium text-mist-300">Run a scenario to see the calculated operational impact.</p>
            <p className="mt-1 text-xs text-mist-400 leading-relaxed">Everything you will see is computed by the backend engine — nothing is hard-coded here.</p>
          </div>
        )}
        {run.loading && <div className="h-40 animate-pulse rounded-lg bg-ink-850 border border-ink-700/60" role="status" aria-label="Running simulation" />}

        {summary && result && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <KpiCard label="Resilience Index" value={summary.resilience_index.toFixed(1)} unit="0-100"
                tooltip="100 minus weighted normalised penalties; transparent planning index, not a validated safety score. Formula in docs/equations.md." />
              <KpiCard label="Peak ward occupancy" value={summary.peak_ward_occupancy_pct?.toFixed(1) ?? '—'} unit="%"
                tooltip="R01 ward_occupancy_high fires at >= 90% (high), >= 100% (critical)." />
              <KpiCard label="Peak ICU occupancy" value={summary.peak_icu_occupancy_pct?.toFixed(1) ?? '—'} unit="%"
                tooltip="R02 icu_occupancy_high fires at >= 90% (high), >= 100% (critical)." />
              <KpiCard label="Peak ED waiting" value={summary.peak_ed_waiting} unit="patients"
                tooltip="R03 ed_waiting >= 10 is high severity." />
              <KpiCard label="Overflow patient-hours" value={summary.overflow_patient_hours} unit="p-h"
                tooltip="Sum of ED waiting + boarding across the horizon." />
              <KpiCard label="Hours power deficit" value={summary.hours_power_deficit} unit="h"
                tooltip="R05 power_deficit: demand exceeds available supply." />
              <KpiCard label="Critical at risk" value={summary.hours_critical_load_at_risk} unit="h"
                tooltip="R06 critical_load_at_risk: critical demand exceeds supply (never silently shed)." />
              <KpiCard label="First failure" value={summary.first_failure ? `h${summary.first_failure.hour}` : 'none'} unit=""
                tooltip={summary.first_failure ? `${summary.first_failure.rule_id} on ${summary.first_failure.resource}` : 'No failure point in this run.'} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
                <h3 className="mb-2 text-sm font-semibold tracking-tight text-mist-100">
                  Hospital twin — hour <span className="font-mono tabular-nums">{run.selectedHour ?? 0}</span>
                </h3>
                <HospitalMap rows={result.series} selectedHour={run.selectedHour} onSelectHour={run.selectHour} />
              </div>
              <AlertPanel alerts={result.alerts} onHighlight={run.highlight} highlight={run.highlightRange} />
            </div>

            <ChartFrame
              title="Power demand vs available supply"
              subtitle="Deficit shading shows unserved demand (kW)"
              table={chartTable(result.series, (r) => [r.power.demand_kw.toFixed(0), r.power.available_supply_kw.toFixed(0), r.power.deficit_kw.toFixed(0), r.power.fuel_l.toFixed(0)], ['hour', 'demand kW', 'supply kW', 'deficit kW', 'fuel L'])}
            >
              <PowerChart rows={result.series} highlight={run.highlightRange} selectedHour={run.selectedHour} />
            </ChartFrame>
          </>
        )}
      </div>
    </div>
  )
}
