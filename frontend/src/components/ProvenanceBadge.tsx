/** Provenance badges: honest labels everywhere (rule 7). */

const KINDS = {
  SYNTHETIC: { label: 'SYNTHETIC', cls: 'border-violet-500/30 bg-violet-500/10 text-violet-300', hint: 'Synthetic hospital data — not real-patient or real-facility data.' },
  CALCULATED: { label: 'CALCULATED', cls: 'border-teal-500/30 bg-teal-500/10 text-teal-300', hint: 'Value computed by the deterministic engine from inputs.' },
  SCENARIO_ASSUMPTION: { label: 'SCENARIO ASSUMPTION', cls: 'border-amber-500/30 bg-amber-500/10 text-amber-300', hint: 'Planning assumption for stress scenarios, not an empirical relationship.' },
  PRECOMPUTED: { label: 'PRECOMPUTED', cls: 'border-amber-500/30 bg-amber-500/10 text-amber-300', hint: 'Offline snapshot generated ahead of time; editing disabled.' },
  'REAL WEATHER': { label: 'REAL WEATHER', cls: 'border-teal-500/30 bg-teal-500/10 text-teal-300', hint: 'Live or cached weather from Open-Meteo with source and timestamp.' },
} as const

export type BadgeKind = keyof typeof KINDS

export function ProvenanceBadge({ kind, title }: { kind: BadgeKind; title?: string }) {
  const meta = KINDS[kind]
  return (
    <span
      title={title ?? meta.hint}
      className={`inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] font-medium tracking-wider uppercase border shadow-2xs ${meta.cls}`}
    >
      {meta.label}
    </span>
  )
}
