/** FailurePointTimeline: ranked failures with cascade arrows and the
 * binding-constraint ribbon rendered under the timeline. */

import type { FailurePoint } from '@/types/domain'

const SEV = { warning: '#fbbf24', high: '#fb923c', critical: '#fb7185' } as const

export function BindingRibbon({ constraints, hours }: { constraints: string[]; hours: number }) {
  const colors: Record<string, string> = {
    power: '#fb7185', supplies: '#a78bfa', staff: '#fbbf24', beds: '#2dd4bf', ed_flow: '#38bdf8',
  }
  return (
    <div aria-label="Binding constraint ribbon" className="flex h-4 w-full overflow-hidden rounded">
      {constraints.slice(0, hours).map((c, i) => (
        <div key={i} title={`hour ${i}: ${c}`} className="h-full flex-1"
          style={{ backgroundColor: colors[c] ?? '#33415e' }} />
      ))}
    </div>
  )
}

export function FailurePointTimeline({ failures }: { failures: FailurePoint[] }) {
  if (!failures.length) {
    return (
      <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
        <h3 className="text-sm font-semibold tracking-tight text-mist-100">Failure points</h3>
        <p className="mt-2 text-xs text-teal-400">● No failure points in this run.</p>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70">
      <h3 className="text-sm font-semibold tracking-tight text-mist-100">
        Failure points <span className="ml-1 text-xs font-normal text-mist-400">({failures.length})</span>
      </h3>
      <p className="mt-0.5 text-xs text-mist-400">Ranked by first hour then severity. ↳ marks a cascade child.</p>
      <ol className="mt-3 space-y-2">
        {failures.map((f) => {
          const color = SEV[(f.peak_severity as keyof typeof SEV) ?? 'high'] ?? SEV.high
          return (
            <li key={`${f.rank}-${f.rule_id}-${f.resource}`} className="rounded-md border border-ink-800/80 bg-ink-950/60 p-3 transition-colors hover:border-ink-700">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-mist-200 tabular-nums">#{f.rank}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color }}>{f.peak_severity.toUpperCase()}</span>
                <span className="font-medium text-mist-200">{f.resource}</span>
                <span className="rounded border border-ink-600 px-1.5 py-0.5 font-mono text-[10px] text-mist-400">{f.rule_id}</span>
                <span className="font-mono text-[11px] tabular-nums text-mist-400">
                  h {f.first_hour}–{f.last_hour}
                </span>
                {f.cascade_parent && (
                  <span className="text-xs text-violet-400" title={`cascades from ${f.cascade_parent}`}>
                    ↳ cascade from {f.cascade_parent}
                  </span>
                )}
                {f.cascade_children.length > 0 && (
                  <span className="text-xs text-violet-400" title={`cascades into ${f.cascade_children.join(', ')}`}>
                    ↳ triggers {f.cascade_children.join(', ')}
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-mist-300">{f.explanation}</p>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
