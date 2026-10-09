/**
 * API client: the backend is the single source of truth. The frontend never
 * recalculates, re-thresholds or hard-codes results. When the API is
 * unreachable we load /demo-results.json (PRECOMPUTED, editing disabled).
 */

import type { components } from '@/types/api'

export type SimulationResponse = components['schemas']['SimulationResponse']
export type ComparisonResponse = components['schemas']['ComparisonResponse']
export type PlanResponse = components['schemas']['PlanResponse']
export type ScenarioInfo = components['schemas']['ScenarioInfo']
export type SimulationRequest = components['schemas']['SimulationRequest']

export const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  details: { field: string; reason: string }[]
  code: string

  constructor(code: string, message: string, details: { field: string; reason: string }[]) {
    super(message)
    this.code = code
    this.details = details
  }
}

export class OfflineError extends Error {
  constructor() {
    super('Backend unreachable — using PRECOMPUTED demo data; editing is disabled.')
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'content-type': 'application/json' },
    signal: init?.signal,
    ...init,
  })
  if (!response.ok) {
    let code = 'HTTP_ERROR'
    let message = `Request failed with status ${response.status}`
    let details: { field: string; reason: string }[] = []
    try {
      const body = await response.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
        details = body.error.details ?? []
      }
    } catch {
      /* non-JSON error body: keep defaults */
    }
    throw new ApiError(code, message, details)
  }
  return (await response.json()) as T
}

export const api = {
  health: (signal?: AbortSignal) => request<{ status: string; model_version: string }>('/health', { signal }),

  scenarios: (signal?: AbortSignal) => request<ScenarioInfo>('/api/v1/scenarios', { signal }),

  baseline: (signal?: AbortSignal) => request<{ hospital: Record<string, unknown> }>('/api/v1/hospital/baseline', { signal }),

  simulate: (body: SimulationRequest, signal?: AbortSignal) =>
    request<SimulationResponse>('/api/v1/simulations', { method: 'POST', body: JSON.stringify(body), signal }),

  compare: (body: SimulationRequest, signal?: AbortSignal) =>
    request<ComparisonResponse>('/api/v1/comparisons', { method: 'POST', body: JSON.stringify(body), signal }),

  plan: (body: Record<string, unknown>, signal?: AbortSignal) =>
    request<PlanResponse>('/api/v1/plans', { method: 'POST', body: JSON.stringify(body), signal }),

  ensemble: (body: Record<string, unknown>, signal?: AbortSignal) =>
    request<Record<string, unknown>>('/api/v1/ensembles', { method: 'POST', body: JSON.stringify(body), signal }),

  sensitivity: (body: Record<string, unknown>, signal?: AbortSignal) =>
    request<Record<string, unknown>>('/api/v1/sensitivity', { method: 'POST', body: JSON.stringify(body), signal }),
}

/** Shape of frontend/public/demo-results.json (PRECOMPUTED). */
export interface DemoSnapshot {
  model_version: string
  label: string
  scenarios: Record<string, { baseline: SimulationResponse; treated: SimulationResponse; deltas: Record<string, { absolute: number }> }>
}

export async function loadDemoSnapshot(): Promise<DemoSnapshot> {
  const response = await fetch('/demo-results.json')
  if (!response.ok) throw new OfflineError()
  return (await response.json()) as DemoSnapshot
}
