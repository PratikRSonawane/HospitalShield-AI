/** AlertPanel: traceable alert episodes; clicking highlights the hour range. */

import type { AlertEpisode } from '@/types/domain'

const SEVERITY = {
  warning: { cls: 'border-amber-400/40 bg-amber-400/10', text: 'text-amber-400', icon: '▲', word: 'WARNING' },
  high: { cls: 'border-orange-400/40 bg-orange-400/10', text: 'text-orange-400', icon: '◆', word: 'HIGH' },
  critical: { cls: 'border-rose-400/40 bg-rose-400/10', text: 'text-rose-400', icon: '■', word: 'CRITICAL' },
} as const

export function AlertPanel({ alerts, onHighlight, highlight }: {
  alerts: AlertEpisode[]
  onHighlight: (range: [number, number] | null) => void
  highlight: [number, number] | null
}) {
  if (!alerts.length) {
    return (
      <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
        <h3 className="text-sm font-semibold text-mist-200">Alerts</h3>
        <p className="mt-2 text-sm text-mist-400">● No alerts fired in this run.</p>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-850 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-mist-200">Alerts ({alerts.length} episodes)</h3>
        {highlight && (
          <button className="text-xs text-mist-400 underline" onClick={() => onHighlight(null)}>
            clear highlight
          </button>
        )}
      </div>
      <ul className="mt-3 max-h-72 space-y-2 overflow-auto">
        {alerts.map((a, i) => {
          const style = SEVERITY[(a.severity as keyof typeof SEVERITY) ?? 'warning'] ?? SEVERITY.warning
          const active = highlight?.[0] === a.first_hour && highlight?.[1] === a.last_hour
          return (
            <li key={`${a.rule_id}-${a.metric}-${i}`}>
              <button
                type="button"
                onClick={() => onHighlight(active ? null : [a.first_hour, a.last_hour])}
                aria-pressed={active}
                className={`w-full rounded border p-3 text-left ${style.cls} ${active ? 'ring-2 ring-teal-400' : ''}`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className={`font-semibold ${style.text}`}>{style.icon} {style.word}</span>
                  <span className="text-mist-400">
                    {a.rule_id} · hours {a.first_hour}–{a.last_hour} ({a.duration_hours} h)
                  </span>
                </div>
                <div className="mt-1 text-sm text-mist-200">{a.rule_text}</div>
                <div className="mt-1 text-xs text-mist-400">
                  {a.metric}: peak <span className="text-mist-200">{a.observed_peak} {a.unit}</span> · threshold {a.threshold} {a.unit} · affects {a.affected_variable}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
