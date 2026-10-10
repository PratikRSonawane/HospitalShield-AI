/**
 * App shell: navigation, offline banner, footer with provenance (on every
 * page), error boundary and the Demo Mode driver.
 */

import { Component, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useRun } from '@/state/RunContext'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'
import { DemoMode } from '@/demo/DemoMode'

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/twin', label: 'Hospital Twin' },
  { to: '/lab', label: 'Scenario Lab' },
  { to: '/failures', label: 'Failure Points & Plan' },
  { to: '/compare', label: 'Compare Runs' },
  { to: '/assumptions', label: 'Assumptions & Data' },
]

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="m-8 rounded-lg border border-rose-400/40 bg-rose-400/10 p-6">
          <h2 className="text-sm font-semibold tracking-tight text-rose-400">Something went wrong</h2>
          <p className="mt-2 text-xs leading-relaxed text-mist-300">{this.state.error.message}</p>
          <button className="mt-4 rounded bg-ink-700 px-3 py-1.5 text-xs font-medium text-mist-200 hover:bg-ink-600" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function OfflineBanner() {
  const { offline, offlineNote } = useRun()
  if (!offline || !offlineNote) return null
  return (
    <div role="status" className="border-b border-amber-400/40 bg-amber-400/10 px-4 py-2 text-xs font-medium text-amber-400">
      ⚠ {offlineNote} Editing is disabled.
    </div>
  )
}

export function Layout() {
  const { offline, modelVersion } = useRun()
  return (
    <div className="min-h-screen">
      <OfflineBanner />
      <header className="no-print sticky top-0 z-40 border-b border-ink-700 bg-ink-900/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-2">
            <span aria-hidden className="text-lg">🛡️</span>
            <span className="text-sm font-semibold tracking-tight text-mist-100">HospitalShield AI</span>
          </NavLink>
          <nav aria-label="Main" className="ml-4 hidden gap-1 md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-xs font-medium tracking-normal transition-colors ${isActive ? 'bg-ink-700 text-mist-100' : 'text-mist-400 hover:bg-ink-800 hover:text-mist-200'}`}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ProvenanceBadge kind="SYNTHETIC" />
            <ProvenanceBadge kind="CALCULATED" />
            <DemoMode />
          </div>
        </div>
      </header>

      <ErrorBoundary>
        <main className="mx-auto max-w-7xl px-4 py-6">
          <Outlet />
        </main>
      </ErrorBoundary>

      <footer className="no-print mt-8 border-t border-ink-700 bg-ink-900/60 px-4 py-4 text-[11px] leading-relaxed text-mist-400">
        <div className="mx-auto max-w-7xl space-y-1">
          <p>
            Model version <span className="font-mono text-mist-300">{modelVersion ?? '—'}</span> · Data:{' '}
            <span className="text-mist-200">SYNTHETIC hospital baseline</span>
            {offline ? ' · PRECOMPUTED demo data (backend unreachable)' : ' · live backend'}
          </p>
          <p className="text-mist-400">
            Limitations: planning prototype — not a clinical, engineering-safety or live-operations system. No claim of
            clinical validity or predictive accuracy. Multipliers are scenario assumptions.
          </p>
        </div>
      </footer>
    </div>
  )
}
