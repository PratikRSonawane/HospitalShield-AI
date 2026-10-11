/** Compare Runs page: baseline vs plan, with export. */

import { useNavigate } from 'react-router-dom'
import { useRun } from '@/state/RunContext'
import { CompareView } from '@/components/CompareView'
import { OccupancyChart } from '@/components/charts'
import { downloadJson } from '@/components/export'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'

export function ComparePage() {
  const { comparison, result, request, runComparison, loading, offline } = useRun()
  const navigate = useNavigate()

  return (
    <div className="space-y-4">
      {!comparison && !loading && (
        <div className="rounded-lg border border-dashed border-ink-600 p-10 text-center">
          <p className="text-sm text-mist-400">
            No comparison yet. Run a scenario, then use the planner's <em>Apply plan → Compare</em> button —
            or compare any run against its baseline from the Scenario Lab.
          </p>
          <button
            className="mt-3 rounded bg-teal-500 px-3 py-1.5 text-sm font-semibold text-ink-950 hover:bg-teal-400"
            onClick={() => {
              if (request && result) {
                void runComparison(request).then((ok) => {
                  if (ok) void navigate('/compare')
                })
              } else {
                void navigate('/lab')
              }
            }}
          >
            {request && result ? 'Compare current run vs baseline' : 'Go to Scenario Lab'}
          </button>
        </div>
      )}
      {loading && <div className="h-40 animate-pulse rounded-lg bg-ink-800" role="status" aria-label="Running comparison" />}
      {comparison && (
        <>
          {offline && <p className="text-xs text-amber-400">PRECOMPUTED demo comparison (backend unreachable).</p>}
          <div className="flex items-center gap-2 no-print">
            <ProvenanceBadge kind="CALCULATED" />
            <button className="rounded border border-ink-600 px-2 py-1 text-xs hover:border-teal-400"
              onClick={() => downloadJson(comparison, `hospitalshield-comparison-${comparison.baseline.run_id}.json`)}>
              Export comparison JSON
            </button>
          </div>
          <CompareView comparison={comparison} />
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
              <h3 className="mb-2 text-sm font-semibold text-mist-200">Baseline occupancy</h3>
              <OccupancyChart rows={comparison.baseline.series} />
            </div>
            <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
              <h3 className="mb-2 text-sm font-semibold text-mist-200">With interventions</h3>
              <OccupancyChart rows={comparison.treatment.series} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
