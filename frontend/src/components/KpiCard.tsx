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
      className="relative rounded-lg border border-ink-700 bg-ink-850 p-4"
      title={tooltip}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-mist-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-mist-200">{value ?? '—'}</span>
        <span className="text-xs text-mist-400">{unit}</span>
      </div>
      {deltaText && <div className={`mt-1 text-xs ${deltaTone}`}>{deltaText} vs baseline</div>}
      {children}
    </div>
  )
}
