/** Failure Points and Action Plan page. */

import { useNavigate } from 'react-router-dom'
import { useRun } from '@/state/RunContext'
import { FailurePointTimeline, BindingRibbon } from '@/components/FailurePointTimeline'
import { ActionPlanTimeline } from '@/components/ActionPlanTimeline'
import { AlertPanel } from '@/components/AlertPanel'

export function FailurePointsPage() {
  const { result, plan, highlight, highlightRange, loading, planning, offline, request, applyPlanToComparison } = useRun()
  const navigate = useNavigate()

  if (!result) {
    return (
      <div className="rounded-lg border border-dashed border-ink-600 p-10 text-center">
        <p className="text-sm text-mist-400">No run yet.</p>
        <button
          className="mt-3 rounded bg-teal-500 px-3 py-1.5 text-sm font-semibold text-ink-950 hover:bg-teal-400"
          onClick={() => void navigate('/')}
        >
          Go to Overview and run a scenario
        </button>
      </div>
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <FailurePointTimeline failures={result.failure_points} />
        <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
          <h3 className="text-sm font-semibold text-mist-200">Binding constraint ribbon</h3>
          <p className="mb-2 text-xs text-mist-400">The tightest resource each hour: power → supplies → staff → beds → ED flow.</p>
          <BindingRibbon constraints={result.series.map((r) => r.binding_constraint)} hours={result.series.length} />
          <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] text-mist-400 md:grid-cols-4">
            {result.series.filter((_, i) => i % 12 === 0).map((r) => (
              <span key={r.hour}>h{r.hour}: {r.binding_constraint}</span>
            ))}
          </div>
        </div>
      </div>
      <div className="space-y-4">
        <AlertPanel alerts={result.alerts} onHighlight={highlight} highlight={highlightRange} />
        {plan ? (
          <ActionPlanTimeline
            plan={plan}
            horizon={result.series.length}
            applying={loading}
            onApply={() => {
              if (request) {
                void applyPlanToComparison(request, plan).then((ok) => {
                  if (ok) void navigate('/compare')
                })
              }
            }}
          />
        ) : (
          <div className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-400">
            {planning
              ? 'Planner searching…'
              : offline
                ? 'Planner needs the backend (offline mode shows precomputed data).'
                : 'Run the planner from the Scenario Lab to get the ordered action plan.'}
          </div>
        )}
        <p className="text-xs text-mist-600">
          Every value on this page is computed by the engine: rule ids, thresholds, observed peaks and hour ranges.
        </p>
      </div>
    </div>
  )
}
