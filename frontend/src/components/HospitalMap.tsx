/**
 * HospitalMap SVG: ED, Ward, ICU, Generator, Grid link, Supplies store and
 * the access road. Colours come from backend unit_status with icon + text
 * (never colour alone) and a time scrubber with play button.
 */

import { useEffect, useRef, useState } from 'react'
import type { HourRow } from '@/types/domain'

const STATUS_STYLE: Record<string, { fill: string; stroke: string; icon: string; word: string }> = {
  ok: { fill: '#0f2f2a', stroke: '#14b8a6', icon: '●', word: 'OK' },
  warn: { fill: '#33260a', stroke: '#fbbf24', icon: '▲', word: 'WARN' },
  critical: { fill: '#38131c', stroke: '#fb7185', icon: '■', word: 'CRITICAL' },
  unavailable: { fill: '#1f1633', stroke: '#a78bfa', icon: '○', word: 'UNAVAILABLE' },
}

function statusOf(row: HourRow, unit: 'ed' | 'ward' | 'icu') {
  return row?.units?.[unit]?.status ?? 'unavailable'
}

function Block({ x, y, w, h, title, line2, status }: {
  x: number; y: number; w: number; h: number; title: string; line2: string; status: string
}) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.unavailable
  return (
    <g role="img" aria-label={`${title}: ${style.word} (${line2})`}>
      <rect x={x} y={y} width={w} height={h} rx={8} fill={style.fill} stroke={style.stroke} strokeWidth={2} />
      <text x={x + 12} y={y + 24} fill="#ccd5e6" fontSize={13} fontWeight={600}>{title}</text>
      <text x={x + 12} y={y + 42} fill="#8b9bb8" fontSize={11}>{line2}</text>
      <text x={x + w - 12} y={y + 24} fill={style.stroke} fontSize={12} textAnchor="end">
        {style.icon} {style.word}
      </text>
    </g>
  )
}

const word = (s: string) => STATUS_STYLE[s]?.word ?? s.toUpperCase()

export function HospitalMap({ rows, selectedHour, onSelectHour }: {
  rows: HourRow[]
  selectedHour: number | null
  onSelectHour: (hour: number | null) => void
}) {
  const maxHour = rows.length - 1
  const hour = Math.min(selectedHour ?? 0, Math.max(maxHour, 0))
  const row = rows[Math.min(hour, maxHour)]
  const [playing, setPlaying] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (!playing) return
    timer.current = window.setInterval(() => {
      onSelectHour(Math.min((selectedHour ?? 0) + 1, maxHour))
    }, 400)
    return () => {
      if (timer.current) window.clearInterval(timer.current)
    }
  }, [playing, selectedHour, maxHour, onSelectHour])

  useEffect(() => {
    if (selectedHour != null && selectedHour >= maxHour) setPlaying(false)
  }, [selectedHour, maxHour])

  if (!row) {
    return <p className="p-4 text-sm text-mist-400">Run a scenario to see the live twin.</p>
  }

  const ed = row.units.ed
  const ward = row.units.ward
  const icu = row.units.icu
  const genRunning = row.power.gen_output_kw > 0
  const gridUp = row.grid_fraction > 0
  const delivery = row.access?.delivery_fraction ?? 1
  const supplyBlocked = delivery < 0.5
  const staffAccess = row.access?.staff_access_fraction ?? 1

  return (
    <div className="space-y-3">
      <svg viewBox="0 0 720 360" className="w-full rounded-lg border border-ink-700 bg-ink-900 font-sans" role="img"
        aria-label={`Hospital map at hour ${hour}. Ward ${word(ward.status)}, ICU ${word(icu.status)}, ED ${word(ed.status)}. Grid ${gridUp ? 'up' : 'down'}, generator ${genRunning ? 'running' : 'idle'}, access ${staffAccess === 1 ? 'clear' : 'restricted'}.`}>
        {/* access road */}
        <path d="M 10 330 L 710 330" stroke={supplyBlocked ? '#fb7185' : '#33415e'} strokeWidth={supplyBlocked ? 4 : 8} strokeDasharray={supplyBlocked ? '12 8' : undefined} fill="none" />
        <text x={16} y={322} fill={supplyBlocked ? '#fb7185' : '#8b9bb8'} fontSize={11} fontFamily="var(--font-sans)">
          {supplyBlocked ? '■ Access road restricted' : '● Access road clear'} (staff access {(staffAccess * 100).toFixed(0)}%, deliveries {(delivery * 100).toFixed(0)}%)
        </text>

        <Block x={30} y={40} w={200} h={72} title="Emergency Department" line2={`${ed.occupied}/${ed.usable_beds} bays · ${ed.occupancy_pct != null ? ed.occupancy_pct.toFixed(0) + '%' : 'n/a'}`} status={statusOf(row, 'ed')} />
        <Block x={260} y={40} w={200} h={72} title="Inpatient Ward" line2={`${ward.occupied}/${ward.usable_beds} beds · ${ward.occupancy_pct != null ? ward.occupancy_pct.toFixed(0) + '%' : 'n/a'}`} status={statusOf(row, 'ward')} />
        <Block x={490} y={40} w={200} h={72} title="Intensive Care" line2={`${icu.occupied}/${icu.usable_beds} beds · ${icu.occupancy_pct != null ? icu.occupancy_pct.toFixed(0) + '%' : 'n/a'}`} status={statusOf(row, 'icu')} />

        {/* grid link */}
        <g role="img" aria-label={`Grid ${gridUp ? 'connected' : 'disconnected'}`}>
          <line x1={90} y1={330} x2={90} y2={200} stroke={gridUp ? '#2dd4bf' : '#fb7185'} strokeWidth={3} strokeDasharray={gridUp ? undefined : '6 6'} />
          <rect x={30} y={130} width={120} height={70} rx={8} fill="#131c30" stroke={gridUp ? '#2dd4bf' : '#fb7185'} strokeWidth={2} />
          <text x={44} y={155} fill="#ccd5e6" fontSize={13} fontWeight={600} fontFamily="var(--font-sans)">Grid link</text>
          <text x={44} y={173} fill={gridUp ? '#2dd4bf' : '#fb7185'} fontSize={11} fontFamily="var(--font-sans)">
            {gridUp ? `● Up · ${(row.grid_fraction * 100).toFixed(0)}%` : '■ Down (outage)'}
          </text>
        </g>

        {/* generator */}
        <g role="img" aria-label={`Generator ${genRunning ? 'running' : 'idle'}, fuel ${Math.round(row.power.fuel_l)} litres`}>
          <rect x={190} y={130} width={140} height={70} rx={8} fill="#131c30" stroke={genRunning ? '#fbbf24' : '#33415e'} strokeWidth={2} />
          <text x={204} y={155} fill="#ccd5e6" fontSize={13} fontWeight={600} fontFamily="var(--font-sans)">Generator</text>
          <text x={204} y={173} fill={genRunning ? '#fbbf24' : '#8b9bb8'} fontSize={11} fontFamily="var(--font-sans)">
            {genRunning ? `▲ Running · ${row.power.gen_output_kw.toFixed(0)} kW` : '○ Idle'} · {Math.round(row.power.fuel_l)} L
          </text>
        </g>

        {/* supplies store */}
        <g role="img" aria-label={`Supplies store, oxygen cover ${row.supplies?.oxygen?.cover_hours ?? '—'} hours`}>
          <rect x={370} y={130} width={160} height={70} rx={8} fill="#131c30" stroke={supplyBlocked ? '#fb7185' : '#2dd4bf'} strokeWidth={2} />
          <text x={384} y={155} fill="#ccd5e6" fontSize={13} fontWeight={600} fontFamily="var(--font-sans)">Supplies store</text>
          <text x={384} y={173} fill="#8b9bb8" fontSize={11} fontFamily="var(--font-sans)">
            O₂ cover {row.supplies?.oxygen?.cover_hours != null ? row.supplies.oxygen.cover_hours.toFixed(0) : '—'} h
          </text>
          <text x={384} y={189} fill={supplyBlocked ? '#fb7185' : '#2dd4bf'} fontSize={11} fontFamily="var(--font-sans)">
            {supplyBlocked ? '■ Deliveries disrupted' : '● Deliveries normal'}
          </text>
        </g>

        {/* binding constraint */}
        <g role="img" aria-label={`Binding constraint at hour ${hour}: ${row.binding_constraint}`}>
          <rect x={560} y={130} width={130} height={70} rx={8} fill="#131c30" stroke="#33415e" strokeWidth={1} />
          <text x={574} y={155} fill="#8b9bb8" fontSize={11} fontFamily="var(--font-sans)">Binding constraint</text>
          <text x={574} y={176} fill="#ccd5e6" fontSize={13} fontWeight={600} fontFamily="var(--font-sans)">{row.binding_constraint}</text>
        </g>

        {/* temperature */}
        <text x={16} y={22} fill="#8b9bb8" fontSize={11} fontFamily="var(--font-sans)">Hour {hour} · {row.temperature_c != null ? `${row.temperature_c.toFixed(1)} °C` : ''} · demand {row.power.demand_kw.toFixed(0)} kW</text>
      </svg>

      <div className="flex items-center gap-3 no-print">
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          className="rounded-md bg-ink-700 px-3 py-1.5 text-xs font-medium text-mist-100 transition-colors hover:bg-ink-600"
          aria-pressed={playing}
        >
          {playing ? '⏸ Pause' : '▶ Play'}
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(maxHour, 0)}
          value={hour}
          onChange={(e) => { setPlaying(false); onSelectHour(Number(e.target.value)) }}
          className="h-1.5 w-full accent-teal-400"
          aria-label="Time scrubber (hour)"
        />
        <span className="w-16 text-right font-mono text-xs tabular-nums text-mist-400">h {hour}/{maxHour}</span>
      </div>
    </div>
  )
}
