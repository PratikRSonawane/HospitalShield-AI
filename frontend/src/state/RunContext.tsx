/**
 * RunContext: shared state for the current simulation, comparison and plan.
 * The backend is the only source of truth; this context only holds and
 * passes the computed payloads plus UI selections (hour scrubber, alerts).
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ApiError,
  api,
  loadDemoSnapshot,
  type ComparisonResponse,
  type DemoSnapshot,
  type PlanResponse,
  type SimulationRequest,
  type SimulationResponse,
} from '@/api/client'
import { DEFAULT_REQUEST, applyPreset } from '@/components/ScenarioControls'

export interface RunState {
  result: SimulationResponse | null
  comparison: ComparisonResponse | null
  plan: PlanResponse | null
  loading: boolean
  planning: boolean
  offline: boolean
  offlineNote: string | null
  error: string | null
  errorDetails: { field: string; reason: string }[]
  selectedHour: number | null
  highlightRange: [number, number] | null
  request: SimulationRequest | null
  modelVersion: string | null
  runScenario: (request: SimulationRequest) => Promise<SimulationResponse | null>
  runComparison: (request: SimulationRequest) => Promise<ComparisonResponse | null>
  runPlanner: (request: SimulationRequest) => Promise<PlanResponse | null>
  applyPlanToComparison: (request: SimulationRequest, plan: PlanResponse) => Promise<ComparisonResponse | null>
  selectHour: (hour: number | null) => void
  highlight: (range: [number, number] | null) => void
  clearPlan: () => void
  clearComparison: () => void
}

const RunContext = createContext<RunState | null>(null)

function planToInterventions(plan: PlanResponse): Record<string, unknown> {
  const out: Record<string, unknown> = {
    activate_surge_beds: [],
    reallocate_staff: [],
    reduce_noncritical_load_kw: [],
    recall_staff: [],
    emergency_resupply: [],
  }
  // only schema fields are sent back (the API forbids extra keys like effective_hour)
  const schemaKeys: Record<string, string[]> = {
    activate_surge_beds: ['unit', 'beds', 'start_hour'],
    reallocate_staff: ['from_unit', 'to_unit', 'nurses', 'start_hour'],
    reduce_noncritical_load_kw: ['kw', 'start_hour', 'end_hour'],
    recall_staff: ['unit', 'nurses', 'start_hour'],
    emergency_resupply: ['fuel_l', 'items', 'start_hour'],
  }
  for (const step of plan.action_plan) {
    const raw = (step.detail ?? {}) as Record<string, unknown>
    const allowed = schemaKeys[step.action]
    if (!allowed) continue
    const clean: Record<string, unknown> = {}
    for (const key of allowed) {
      if (raw[key] !== undefined) clean[key] = raw[key]
    }
    if (step.action === 'activate_surge_beds') {
      out.activate_surge_beds = [...(out.activate_surge_beds as unknown[]), clean]
    } else if (step.action === 'reallocate_staff') {
      out.reallocate_staff = [...(out.reallocate_staff as unknown[]), clean]
    } else if (step.action === 'reduce_noncritical_load_kw') {
      out.reduce_noncritical_load_kw = [...(out.reduce_noncritical_load_kw as unknown[]), clean]
    } else if (step.action === 'recall_staff') {
      out.recall_staff = [...(out.recall_staff as unknown[]), clean]
    } else if (step.action === 'emergency_resupply') {
      out.emergency_resupply = [...(out.emergency_resupply as unknown[]), clean]
    }
  }
  return out
}

export function RunProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<SimulationResponse | null>(null)
  const autoRan = useRef(false)
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [offline, setOffline] = useState(false)
  const [offlineNote, setOfflineNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [errorDetails, setErrorDetails] = useState<{ field: string; reason: string }[]>([])
  const [selectedHour, setSelectedHour] = useState<number | null>(null)
  const [highlightRange, setHighlightRange] = useState<[number, number] | null>(null)
  const [request, setRequest] = useState<SimulationRequest | null>(null)
  const snapshot = useRef<DemoSnapshot | null>(null)
  const modelVersion = result?.model_version ?? snapshot.current?.model_version ?? null

  // Load the default scenario once on mount so every page (twin, failures,
  // compare) has data even after a hard reload; falls back to PRECOMPUTED
  // demo data when the backend is unreachable.
  useEffect(() => {
    if (autoRan.current) return
    autoRan.current = true
    const preset = applyPreset(DEFAULT_REQUEST, 'heatwave_power_outage')
    void runScenarioRef.current(preset)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const runScenarioRef = useRef<(req: SimulationRequest) => Promise<SimulationResponse | null>>(async () => null)
  const runScenario = useCallback(async (req: SimulationRequest) => {
    setLoading(true)
    setError(null)
    setErrorDetails([])
    setRequest(req)
    try {
      const response = await api.simulate(req)
      setResult(response)
      setSelectedHour(null)
      return response
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        setErrorDetails(err.details)
        return null
      }
      // network failure: fall back to PRECOMPUTED data
      try {
        if (!snapshot.current) snapshot.current = await loadDemoSnapshot()
        const key = req.scenario
        const demo = snapshot.current.scenarios[key]
        if (demo) {
          setResult(demo.baseline)
          setOffline(true)
          setOfflineNote(`PRECOMPUTED — backend unreachable. Showing demo data for ${key}.`)
          return demo.baseline
        }
        setError('Backend unreachable and no precomputed data for this scenario.')
        return null
      } catch {
        setError('Backend unreachable and no precomputed data available.')
        return null
      }
    } finally {
      setLoading(false)
    }
  }, [])

  runScenarioRef.current = runScenario

  const runComparison = useCallback(async (req: SimulationRequest) => {
    setLoading(true)
    setError(null)
    setErrorDetails([])
    setRequest(req)
    try {
      const response = await api.compare(req)
      setComparison(response)
      return response
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        setErrorDetails(err.details)
        return null
      }
      try {
        if (!snapshot.current) snapshot.current = await loadDemoSnapshot()
        const demo = snapshot.current.scenarios[req.scenario]
        if (demo) {
          const treatedAsBaseline = { ...demo.baseline, summary: demo.treated.summary }
          const pseudo: ComparisonResponse = {
            baseline: demo.baseline,
            treatment: treatedAsBaseline,
            explanations: ['PRECOMPUTED demo comparison (backend unreachable).'],
          } as unknown as ComparisonResponse
          setComparison(pseudo)
          setOffline(true)
          setOfflineNote('PRECOMPUTED — backend unreachable. Demo comparison shown.')
          return pseudo
        }
        setError('Backend unreachable and no precomputed data for this scenario.')
        return null
      } catch {
        setError('Backend unreachable and no precomputed data available.')
        return null
      }
    } finally {
      setLoading(false)
    }
  }, [])

  const runPlanner = useCallback(async (req: SimulationRequest) => {
    setPlanning(true)
    setError(null)
    setErrorDetails([])
    setRequest(req)
    try {
      const body = { ...req, objective: { lambda_burden: 0.5 }, budget: { max_simulations: 600, max_seconds: 5, max_actions: 5, grid_hours: 3 } }
      const response = await api.plan(body as unknown as Record<string, unknown>)
      setPlan(response)
      return response
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Backend unreachable — planner needs the API.')
      if (err instanceof ApiError) setErrorDetails(err.details)
      return null
    } finally {
      setPlanning(false)
    }
  }, [])

  const applyPlanToComparison = useCallback(async (req: SimulationRequest, thePlan: PlanResponse) => {
    const withPlan: SimulationRequest = {
      ...req,
      interventions: planToInterventions(thePlan) as SimulationRequest['interventions'],
    }
    return runComparison(withPlan)
  }, [runComparison])

  const value = useMemo<RunState>(() => ({
    result, comparison, plan, loading, planning, offline, offlineNote, error, errorDetails,
    selectedHour, highlightRange, request, modelVersion,
    runScenario, runComparison, runPlanner, applyPlanToComparison,
    selectHour: setSelectedHour,
    highlight: setHighlightRange,
    clearPlan: () => setPlan(null),
    clearComparison: () => setComparison(null),
  }), [result, comparison, plan, loading, planning, offline, offlineNote, error, errorDetails,
    selectedHour, highlightRange, request, modelVersion, runScenario, runComparison, runPlanner, applyPlanToComparison])

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>
}

export function useRun(): RunState {
  const ctx = useContext(RunContext)
  if (!ctx) throw new Error('useRun must be used inside RunProvider')
  return ctx
}
