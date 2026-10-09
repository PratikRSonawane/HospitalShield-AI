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
    <div className="space-y-5">
      <section className="relative overflow-hidden rounded-2xl border border-ink-700 bg-gradient-to-br from-ink-900 via-ink-850 to-ink-900 px-5 py-5 shadow-2xl shadow-black/10 sm:px-6">
        <div className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-teal-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-teal-400">
              <span className="size-1.5 rounded-full bg-teal-400 shadow-[0_0_0_4px] shadow-teal-400/10" />
              Operational command center
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-mist-100 sm:text-3xl">Hospital resilience overview</h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-mist-400">Model the impact of a disruption, identify where capacity breaks, and turn the result into an ordered action plan.</p>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-ink-600 bg-ink-950/40 px-3 py-2 text-xs text-mist-300">
            <span className={`size-2 rounded-full ${run.offline ? 'bg-amber-400' : 'bg-teal-400'}`} />
            {run.offline ? 'Demo data' : 'Engine ready'}
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="space-y-4">
        <div className="flex items-center justify-between px-1">
          <div>
            <p className="text-sm font-semibold text-mist-200">Build a scenario</p>
            <p className="text-xs text-mist-500">Tune assumptions before running</p>
          </div>
          <span className="rounded-full border border-ink-700 bg-ink-850 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-mist-400">Step 1</span>
        </div>
        <ScenarioControls
          request={request}
          onChange={setRequest}
          info={info}
          error={run.error}
          errorDetails={run.errorDetails}
          loading={run.loading}
          onRun={() => { if (request) void run.runScenario(request) }}
        />
        <div className="rounded-lg border border-ink-700 bg-ink-850 p-4 text-xs text-mist-400">
          <p className="font-semibold text-mist-300">Mission</p>
          <p className="mt-1">scenario → calculated impact → failure points → actions in the best order → measured before/after.</p>
          <div className="mt-3 flex flex-col gap-2">
            <Link to="/failures" className="rounded border border-ink-600 px-3 py-1.5 text-center hover:border-teal-400">Failure points & plan →</Link>
            <Link to="/compare" className="rounded border border-ink-600 px-3 py-1.5 text-center hover:border-teal-400">Compare runs →</Link>
          </div>
          {result && (
            <div className="mt-3 flex gap-2 no-print">
              <button className="flex-1 rounded border border-ink-600 px-2 py-1 hover:border-teal-400" onClick={() => exportResult(result)}>Export JSON</button>
              <button className="flex-1 rounded border border-ink-600 px-2 py-1 hover:border-teal-400" onClick={() => exportSeriesCsv(result)}>Export CSV</button>
              <button className="rounded border border-ink-600 px-2 py-1 hover:border-teal-400" onClick={() => window.print()}>Print</button>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {!result && !run.loading && (
          <section className="flex min-h-80 flex-col items-center justify-center gap-5 rounded-2xl border border-ink-700 bg-ink-900 px-6 py-12 text-center">
            <span aria-hidden="true" className="grid size-14 place-items-center rounded-2xl border border-teal-400/20 bg-teal-400/10 text-xl font-medium text-teal-400">01</span>
            <div className="flex max-w-sm flex-col gap-2">
              <h2 className="text-xl font-semibold text-mist-100">Your next insight starts here</h2>
              <p className="text-sm leading-6 text-mist-400">Choose a disruption and adjust your scenario settings. Run the simulation to reveal capacity pressures and the resources that need attention.</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 text-xs text-mist-300">
              {['Capacity impact', 'Resource risks', 'Response priorities'].map((label) => <span key={label} className="rounded-full border border-ink-700 px-3 py-1.5">{label}</span>)}
            </div>
            <p className="text-xs text-mist-500">Results are calculated by the simulation engine.</p>
          </section>
        )}
        {run.loading && <div className="h-40 animate-pulse rounded-lg bg-ink-800" role="status" aria-label="Running simulation" />}

        {summary && result && (
          <>
            <div className="mb-1 flex items-end justify-between px-1">
              <div>
                <p className="text-sm font-semibold text-mist-200">Resilience snapshot</p>
                <p className="text-xs text-mist-500">Calculated from the selected scenario</p>
              </div>
              <span className="text-xs text-mist-500">72-hour horizon</span>
            </div>
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
              <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
                <h3 className="mb-2 text-sm font-semibold text-mist-200">Hospital twin — hour {run.selectedHour ?? 0}</h3>
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
    </div>
  )
}
