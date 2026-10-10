/** Shared chart frame: title, unit, threshold note, table alternative. */

import { useState, type ReactNode } from 'react'

export interface ChartFrameProps {
  title: string
  subtitle?: string
  table: { columns: string[]; rows: (string | number | null)[][] }
  children: ReactNode
  defaultTab?: 'chart' | 'table'
}

export function ChartFrame({ title, subtitle, table, children, defaultTab = 'chart' }: ChartFrameProps) {
  const [tab, setTab] = useState<'chart' | 'table'>(defaultTab)
  return (
    <section className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4 transition-colors hover:border-ink-600/70" aria-label={title}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-mist-100">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-mist-400">{subtitle}</p>}
        </div>
        <div className="flex rounded-md border border-ink-700/80 bg-ink-950/70 p-0.5 text-xs" role="tablist" aria-label={`${title} view`}>
          <button role="tab" aria-selected={tab === 'chart'} onClick={() => setTab('chart')}
            className={`rounded px-2.5 py-0.5 font-medium transition-all ${tab === 'chart' ? 'bg-ink-800 text-teal-300 shadow-xs' : 'text-mist-400 hover:text-mist-200'}`}>
            Chart
          </button>
          <button role="tab" aria-selected={tab === 'table'} onClick={() => setTab('table')}
            className={`rounded px-2.5 py-0.5 font-medium transition-all ${tab === 'table' ? 'bg-ink-800 text-teal-300 shadow-xs' : 'text-mist-400 hover:text-mist-200'}`}>
            Table
          </button>
        </div>
      </div>
      {tab === 'chart' ? (
        children
      ) : (
        <div className="max-h-64 overflow-auto rounded border border-ink-800/60">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wider text-mist-400 border-b border-ink-800 bg-ink-950/40">
                {table.columns.map((c) => (
                  <th key={c} scope="col" className="px-2.5 py-1.5">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className="border-t border-ink-800/50 hover:bg-ink-850/40">
                  {row.map((cell, j) => (
                    <td key={j} className="px-2.5 py-1.5 tabular-nums text-mist-300">{cell ?? '—'}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
