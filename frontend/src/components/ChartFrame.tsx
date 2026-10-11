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
          <h3 className="text-sm font-semibold text-mist-200">{title}</h3>
          {subtitle && <p className="text-xs text-mist-400">{subtitle}</p>}
        </div>
        <div className="flex rounded border border-ink-600 text-xs" role="tablist" aria-label={`${title} view`}>
          <button role="tab" aria-selected={tab === 'chart'} onClick={() => setTab('chart')}
            className={`px-2 py-1 ${tab === 'chart' ? 'bg-ink-700 text-mist-200' : 'text-mist-400'}`}>
            Chart
          </button>
          <button role="tab" aria-selected={tab === 'table'} onClick={() => setTab('table')}
            className={`px-2 py-1 ${tab === 'table' ? 'bg-ink-700 text-mist-200' : 'text-mist-400'}`}>
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
              <tr className="text-left text-mist-400">
                {table.columns.map((c) => (
                  <th key={c} scope="col" className="px-2 py-1 font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className="border-t border-ink-700">
                  {row.map((cell, j) => (
                    <td key={j} className="px-2 py-1 text-mist-300">{cell ?? '—'}</td>
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
