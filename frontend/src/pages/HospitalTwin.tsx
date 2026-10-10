/** Hospital Twin page: large map, all charts with scrubber sync. */

import { useRun } from '@/state/RunContext'
import { HospitalMap } from '@/components/HospitalMap'
import { ChartFrame } from '@/components/ChartFrame'
import { BindingRibbon } from '@/components/FailurePointTimeline'
import { EdFlowChart, FuelChart, OccupancyChart, PowerChart, StaffChart, SupplyCoverChart, chartTable } from '@/components/charts'

export function HospitalTwinPage() {
  const { result, selectedHour, selectHour, highlightRange, offline } = useRun()

  if (!result) {
    return (
      <div className="rounded-lg border border-dashed border-ink-600 p-10 text-center">
        <p className="text-sm font-medium text-mist-300">Run a scenario first (Overview or Scenario Lab).</p>
      </div>
    )
  }

  const binding = result.series.map((r) => r.binding_constraint)

  return (
    <div className="space-y-4">
      {offline && <p className="text-xs font-medium text-amber-400">PRECOMPUTED demo run.</p>}
      <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight text-mist-100">Hospital twin — time scrubber</h2>
          <p className="text-xs text-mist-400">Status = colour + icon + text, computed by the backend each hour.</p>
        </div>
        <div className="mt-3">
          <HospitalMap rows={result.series} selectedHour={selectedHour} onSelectHour={selectHour} />
        </div>
        <div className="mt-3">
          <p className="mb-1 text-xs text-mist-400">Binding constraint ribbon (smallest margin per hour; tie order power → supplies → staff → beds → ED flow)</p>
          <BindingRibbon constraints={binding} hours={result.series.length} />
          <div className="mt-1.5 flex gap-3 font-mono text-[10px] text-mist-400 tracking-wider">
            <span>■ power</span><span>■ supplies</span><span>■ staff</span><span>■ beds</span><span>■ ed_flow</span>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartFrame title="Occupancy by unit" subtitle="Occupied / usable, clamped 0-100; threshold 90%"
          table={chartTable(result.series, (r) => [r.units.ward.occupancy_pct?.toFixed(1) ?? '—', r.units.icu.occupancy_pct?.toFixed(1) ?? '—', r.units.ed.occupancy_pct?.toFixed(1) ?? '—'], ['hour', 'ward %', 'icu %', 'ed %'])}>
          <OccupancyChart rows={result.series} highlight={highlightRange} selectedHour={selectedHour} />
        </ChartFrame>
        <ChartFrame title="ED waiting and boarding" subtitle="Patients; R03 warns at 4 boarding / 10 waiting"
          table={chartTable(result.series, (r) => [r.ed.waiting, (r.ed.boarding_ward ?? 0) + (r.ed.boarding_icu ?? 0), r.ed.arrivals], ['hour', 'waiting', 'boarding', 'arrivals'])}>
          <EdFlowChart rows={result.series} highlight={highlightRange} selectedHour={selectedHour} />
        </ChartFrame>
        <ChartFrame title="Power demand vs supply" subtitle="kW; deficit shaded red"
          table={chartTable(result.series, (r) => [r.power.demand_kw.toFixed(0), r.power.available_supply_kw.toFixed(0), r.power.deficit_kw.toFixed(0)], ['hour', 'demand kW', 'supply kW', 'deficit kW'])}>
          <PowerChart rows={result.series} highlight={highlightRange} selectedHour={selectedHour} />
        </ChartFrame>
        <ChartFrame title="Staff required vs available" subtitle="Nurses; ward and ICU"
          table={chartTable(result.series, (r) => [r.staffing.ward.required, r.staffing.ward.available, r.staffing.icu.required, r.staffing.icu.available], ['hour', 'ward req', 'ward avail', 'icu req', 'icu avail'])}>
          <StaffChart rows={result.series} highlight={highlightRange} selectedHour={selectedHour} />
        </ChartFrame>
        <ChartFrame title="Fuel remaining" subtitle="Litres; generator burn only when covering the demand gap"
          table={chartTable(result.series, (r) => [r.power.fuel_l.toFixed(0), r.power.gen_output_kw.toFixed(0)], ['hour', 'fuel L', 'gen kW'])}>
          <FuelChart rows={result.series} highlight={highlightRange} selectedHour={selectedHour} />
        </ChartFrame>
        <ChartFrame title="Supply cover hours" subtitle="Stock / consumption per item; low cover threshold 24 h"
          table={chartTable(result.series, (r) => [r.supplies?.oxygen?.cover_hours?.toFixed(1) ?? '—', r.supplies?.essential_meds?.cover_hours?.toFixed(1) ?? '—'], ['hour', 'oxygen h', 'meds h'])}>
          <SupplyCoverChart rows={result.series} highlight={highlightRange} selectedHour={selectedHour} />
        </ChartFrame>
      </div>
    </div>
  )
}
