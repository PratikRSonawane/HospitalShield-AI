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
    <section className="rounded-lg border border-ink-700 bg-ink-850 p-4" aria-label={title}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-mist-100">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-mist-400">{subtitle}</p>}
        </div>
        <div className="flex rounded-md border border-ink-600 text-xs overflow-hidden" role="tablist" aria-label={`${title} view`}>
          <button role="tab" aria-selected={tab === 'chart'} onClick={() => setTab('chart')}
            className={`px-2.5 py-1 font-medium transition-colors ${tab === 'chart' ? 'bg-ink-700 text-mist-100' : 'text-mist-400 hover:text-mist-200'}`}>
            Chart
          </button>
          <button role="tab" aria-selected={tab === 'table'} onClick={() => setTab('table')}
            className={`px-2.5 py-1 font-medium transition-colors ${tab === 'table' ? 'bg-ink-700 text-mist-100' : 'text-mist-400 hover:text-mist-200'}`}>
            Table
          </button>
        </div>
      </div>
      {tab === 'chart' ? (
        children
      ) : (
        <div className="max-h-64 overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wider text-mist-400 border-b border-ink-700">
                {table.columns.map((c) => (
                  <th key={c} scope="col" className="px-2.5 py-1.5">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className="border-t border-ink-700/60 hover:bg-ink-800/40">
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
