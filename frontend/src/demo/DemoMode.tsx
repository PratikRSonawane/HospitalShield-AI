/**
 * Demo Mode: one-click scripted sequence following the 3-minute demo script
 * (baseline → heatwave outage → failure points + alert → planner → compare →
 * limitations), with guided annotations.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRun } from '@/state/RunContext'
import { applyPreset, DEFAULT_REQUEST } from '@/components/ScenarioControls'

interface Step {
  title: string
  annotation: string
  run?: () => Promise<unknown>
  goto?: string
  waitMs?: number
}

export function DemoMode() {
  const run = useRun()
  const navigate = useNavigate()
  const [active, setActive] = useState(false)
  const [stepIndex, setStepIndex] = useState(-1)

  const steps: Step[] = [
    {
      title: '1/6 Persona and baseline',
      annotation: "A hospital planner asks: 'if this happens, which constraints appear and which intervention helps?' Here is the SYNTHETIC baseline hospital (fictional, labelled).",
      run: async () => { return run.runScenario(applyPreset(DEFAULT_REQUEST, 'normal_operations')) },
      goto: '/',
    },
    {
      title: '2/6 Run the heatwave + outage',
      annotation: '72-hour heatwave with a 36-hour grid outage from hour 24. Occupancy, boarding, fuel and critical power are all CALCULATED by the engine — nothing is typed in.',
      run: async () => { return run.runScenario(applyPreset(DEFAULT_REQUEST, 'heatwave_power_outage')) },
      goto: '/twin',
    },
    {
      title: '3/6 Failure points and cascades',
      annotation: 'First failure, the cascade it triggers (fuel → power → ICU derate), and the binding-constraint ribbon. Open an alert: rule id, threshold, observed value, hour range.',
      goto: '/failures',
    },
    {
      title: '4/6 Run the action planner',
      annotation: 'Beam search over surge beds, staff moves, load shedding, recall and resupply — with lead times and feasibility. The plan says what, in what order, when.',
      run: async () => { return run.runPlanner(applyPreset(DEFAULT_REQUEST, 'heatwave_power_outage')) },
      goto: '/lab',
    },
    {
      title: '5/6 Apply plan and compare',
      annotation: 'Same initial state, seed and weather. Deltas and attribution show which intervention bought what — and the wrong-order reference does worse.',
      run: async () => {
        const scenario = applyPreset(DEFAULT_REQUEST, 'heatwave_power_outage')
        const plan = run.plan ?? await run.runPlanner(scenario)
        if (plan) return run.applyPlanToComparison(scenario, plan)
        return null
      },
      goto: '/compare',
    },
    {
      title: '6/6 Limitations',
      annotation: 'Synthetic data, scenario assumptions, planning prototype — not clinical or engineering-safety. NHS/MIMIC are optional calibration references; the path to real data needs validation.',
      goto: '/assumptions',
    },
  ]

  const current = stepIndex >= 0 ? steps[stepIndex] : null

  useEffect(() => {
    if (!active || !current) return
    let cancelled = false
    void (async () => {
      if (current.goto) navigate(current.goto)
      if (current.run) await current.run()
      if (!cancelled && current.waitMs) await new Promise((r) => setTimeout(r, current.waitMs))
    })()
    return () => { cancelled = true }
  }, [active, stepIndex, current, navigate])

  return (
    <div className="no-print">
      <button
        type="button"
        onClick={() => { setActive(!active); setStepIndex(active ? -1 : 0) }}
        className="rounded-md bg-teal-500 px-3 py-1.5 text-xs font-semibold text-ink-950 transition-colors hover:bg-teal-400"
        aria-pressed={active}
      >
        ▶ Demo Mode
      </button>
      {active && current && (
        <div role="dialog" aria-label="Demo mode" className="fixed bottom-4 left-4 right-4 z-50 rounded-lg border border-teal-400/40 bg-ink-900/95 p-4 shadow-xl backdrop-blur md:left-auto md:right-6 md:w-96">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-sm font-semibold tracking-tight text-teal-400">{current.title}</h2>
            <button className="text-xs text-mist-400 hover:text-mist-200" onClick={() => { setActive(false); setStepIndex(-1) }} aria-label="Close demo mode">✕</button>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-mist-300">{current.annotation}</p>
          <div className="mt-3 flex items-center justify-between">
            <div className="flex gap-1" aria-hidden>
              {steps.map((_, i) => (
                <span key={i} className={`h-1.5 w-6 rounded-full transition-colors ${i <= stepIndex ? 'bg-teal-400' : 'bg-ink-600'}`} />
              ))}
            </div>
            <div className="flex gap-2">
              <button className="rounded-md border border-ink-600 px-2.5 py-1 text-xs font-medium text-mist-300 transition-colors hover:border-ink-500 hover:text-mist-100 disabled:opacity-40" disabled={stepIndex === 0}
                onClick={() => setStepIndex((i) => Math.max(0, i - 1))}>Back</button>
              <button className="rounded-md bg-teal-500 px-3 py-1 text-xs font-semibold text-ink-950 transition-colors hover:bg-teal-400"
                onClick={() => stepIndex === steps.length - 1 ? (setActive(false), setStepIndex(-1)) : setStepIndex((i) => i + 1)}>
                {stepIndex === steps.length - 1 ? 'Finish' : 'Next'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
