/** Provenance badges: honest labels everywhere (rule 7). */

const KINDS = {
  SYNTHETIC: { label: 'SYNTHETIC', cls: 'border-violet-400/40 bg-violet-400/10 text-violet-400', hint: 'Synthetic hospital data — not real-patient or real-facility data.' },
  CALCULATED: { label: 'CALCULATED', cls: 'border-teal-400/40 bg-teal-400/10 text-teal-400', hint: 'Value computed by the deterministic engine from inputs.' },
  SCENARIO_ASSUMPTION: { label: 'SCENARIO ASSUMPTION', cls: 'border-amber-400/40 bg-amber-400/10 text-amber-400', hint: 'Planning assumption for stress scenarios, not an empirical relationship.' },
  PRECOMPUTED: { label: 'PRECOMPUTED', cls: 'border-amber-400/40 bg-amber-400/10 text-amber-400', hint: 'Offline snapshot generated ahead of time; editing disabled.' },
  'REAL WEATHER': { label: 'REAL WEATHER', cls: 'border-teal-400/40 bg-teal-400/10 text-teal-400', hint: 'Live or cached weather from Open-Meteo with source and timestamp.' },
} as const

export type BadgeKind = keyof typeof KINDS

export function ProvenanceBadge({ kind, title }: { kind: BadgeKind; title?: string }) {
  const meta = KINDS[kind]
  return (
    <span
      title={title ?? meta.hint}
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${meta.cls}`}
    >
      {meta.label}
    </span>
  )
}
