/** ActionPlanTimeline: Gantt-style plan with lead-time bars and marginal
 * gains, plus an "apply plan" button that runs the comparison. */

import type { PlanResponse } from '@/types/domain'

const ACTION_COLORS: Record<string, string> = {
  activate_surge_beds: '#2dd4bf',
  reallocate_staff: '#38bdf8',
  reduce_noncritical_load_kw: '#a78bfa',
  recall_staff: '#fbbf24',
  emergency_resupply: '#fb923c',
}

function describe(action: string, detail: Record<string, unknown>): string {
  const d = detail as unknown as Record<string, string | number>
  switch (action) {
    case 'activate_surge_beds':
      return `Open ${d.beds} surge beds (${d.unit})`
    case 'reallocate_staff':
      return `Move ${d.nurses} nurses ${d.from_unit}→${d.to_unit}`
    case 'reduce_noncritical_load_kw':
      return `Shed ${d.kw} kW non-critical load`
    case 'recall_staff':
      return `Recall ${d.nurses} nurses to ${d.unit}`
    case 'emergency_resupply': {
      if (d.fuel_l) return `Emergency fuel resupply ${d.fuel_l} L`
      const items = (d.items ?? {}) as unknown as Record<string, number>
      const first = Object.entries(items)[0]
      return first ? `Emergency resupply ${first[1]} ${first[0]}` : 'Emergency resupply'
    }
    default:
      return action
  }
}

export function ActionPlanTimeline({ plan, horizon, onApply, applying }: {
  plan: PlanResponse
  horizon: number
  onApply: () => void
  applying: boolean
}) {
  const steps = plan.action_plan
  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-mist-100">
            Action plan <span className="ml-1 text-xs font-normal text-mist-400">({steps.length} steps)</span>
          </h3>
          <p className="mt-0.5 text-xs text-mist-400 tabular-nums">
            {plan.label} · objective {plan.score?.objective != null ? Number(plan.score.objective).toFixed(1) : '—'}{' '}
            (resilience {plan.score?.resilience_index != null ? Number(plan.score.resilience_index).toFixed(1) : '—'}
            {' '}- burden {plan.score?.burden != null ? Number(plan.score.burden).toFixed(2) : '—'})
          </p>
        </div>
        <button
          type="button"
          onClick={onApply}
          disabled={applying || steps.length === 0}
          className="rounded-md bg-teal-500 px-3.5 py-1.5 text-xs font-semibold text-ink-950 shadow-xs transition-all hover:bg-teal-400 active:scale-[0.99] disabled:opacity-50 no-print"
        >
          {applying ? 'Applying…' : 'Apply plan → Compare'}
        </button>
      </div>

      {steps.length === 0 ? (
        <p className="mt-3 text-xs leading-relaxed text-mist-400">
          No plan improves the objective within budget ({plan.search_stats?.stopped_reason}).
        </p>
      ) : (
        <div className="mt-4 space-y-2" role="list" aria-label="Ordered action plan">
          {steps.map((step, i) => {
            const color = ACTION_COLORS[step.action] ?? '#33415e'
            const start = step.start_hour
            const lead = step.effective_hour - start
            const width = Math.max(horizon - start, 4)
            return (
              <div key={i} role="listitem" className="text-xs">
                <div className="flex flex-wrap items-center justify-between gap-1">
                  <span className="font-medium text-mist-200">
                    <span className="mr-1.5 rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-mist-200 tabular-nums">{i + 1}</span>
                    {describe(step.action, step.detail as Record<string, unknown>)}
                  </span>
                  <span className="font-mono text-[11px] tabular-nums text-mist-400">
                    start h{start} → effective h{step.effective_hour}
                    {step.marginal_gain_resilience != null && (
                      <> · <span className="font-semibold text-teal-400">+{step.marginal_gain_resilience} resilience</span></>
                    )}
                  </span>
                </div>
                <div className="relative mt-1.5 h-3.5 w-full overflow-hidden rounded bg-ink-900">
                  <div className="absolute top-0 h-full" style={{ left: `${(start / horizon) * 100}%`, width: `${Math.max((lead / horizon) * 100, 1.5)}%`, backgroundColor: color, opacity: 0.35 }} title={`lead time (${lead} h)`} />
                  <div className="absolute top-0 h-full" style={{ left: `${(step.effective_hour / horizon) * 100}%`, width: `${(width / horizon) * 100}%`, backgroundColor: color, opacity: 0.85 }} title="active" />
                </div>
                <p className="mt-1 text-xs text-mist-400 leading-normal">{step.reason}</p>
              </div>
            )
          })}
        </div>
      )}

      <div className="mt-4 border-t border-ink-700 pt-2 text-[11px] text-mist-400 tabular-nums leading-relaxed">
        <p>Search: {plan.search_stats?.simulations_used} simulations · {(plan.search_stats?.seconds_ms / 1000).toFixed(1)} s · stopped: {plan.search_stats?.stopped_reason}</p>
        <p className="mt-1">
          References —{' '}
          {plan.references?.map((r, i) => (
            <span key={r.name}>
              {i > 0 && ' · '}
              {r.name}: {r.resilience_index != null ? Number(r.resilience_index).toFixed(1) : 'infeasible'}
            </span>
          ))}
        </p>
      </div>
    </div>
  )
}
