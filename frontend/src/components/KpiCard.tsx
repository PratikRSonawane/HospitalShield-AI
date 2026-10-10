/** KpiCard: value, unit, delta and a tooltip carrying the alert rule. */

import type { ReactNode } from 'react'

export interface KpiCardProps {
  label: string
  value: string | number | null
  unit: string
  delta?: { absolute: number; unit?: string } | null
  goodWhenDown?: boolean
  tooltip?: string
  children?: ReactNode
}

function fmt(n: number): string {
  return Math.abs(n) >= 100 ? Math.round(n).toLocaleString() : Math.abs(n) >= 10 ? n.toFixed(1) : n.toFixed(2)
}

export function KpiCard({ label, value, unit, delta, goodWhenDown = true, tooltip, children }: KpiCardProps) {
  const deltaText = delta ? `${delta.absolute > 0 ? '+' : ''}${fmt(delta.absolute)} ${delta.unit ?? unit}` : null
  const deltaTone = delta
    ? delta.absolute === 0
      ? 'text-mist-400'
      : (delta.absolute < 0) === goodWhenDown
        ? 'text-teal-400'
        : 'text-rose-400'
    : ''
  return (
    <div
      className="relative rounded-lg border border-ink-700/60 bg-ink-900/60 p-3.5 transition-all hover:border-ink-600/70 hover:bg-ink-900/80 shadow-xs"
      title={tooltip}
    >
      <div className="text-[11px] font-semibold uppercase tracking-wider text-mist-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tracking-tight text-mist-100 tabular-nums">{value ?? '—'}</span>
        <span className="text-xs font-normal text-mist-400">{unit}</span>
      </div>
      {deltaText && <div className={`mt-1 text-[11px] font-medium tabular-nums ${deltaTone}`}>{deltaText} vs baseline</div>}
      {children}
    </div>
  )
}
