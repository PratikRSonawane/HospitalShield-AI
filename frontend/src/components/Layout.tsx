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
          <h2 className="text-lg font-semibold text-rose-400">Something went wrong</h2>
          <p className="mt-2 text-sm text-mist-300">{this.state.error.message}</p>
          <button className="mt-4 rounded bg-ink-700 px-3 py-1.5 text-sm" onClick={() => this.setState({ error: null })}>
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
    <div role="status" className="border-b border-amber-400/40 bg-amber-400/10 px-4 py-2 text-sm text-amber-400">
      ⚠ {offlineNote} Editing is disabled.
    </div>
  )
}

export function Layout() {
  const { offline, modelVersion } = useRun()
  return (
    <div className="min-h-screen">
      <OfflineBanner />
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-teal-400 focus:px-4 focus:py-2 focus:text-ink-950">Skip to content</a>
      <header className="no-print sticky top-0 z-40 border-b border-ink-700/80 bg-ink-900/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3 lg:px-6">
          <NavLink to="/" className="group flex shrink-0 items-center gap-2.5" aria-label="HospitalShield AI overview">
            <span aria-hidden className="grid size-8 place-items-center rounded-xl border border-teal-400/30 bg-teal-400/10 text-sm font-bold text-teal-400 shadow-inner shadow-teal-400/10 transition-colors group-hover:border-teal-400/60 group-hover:bg-teal-400/15">HS</span>
            <span className="leading-none">
              <span className="block text-sm font-semibold tracking-tight text-mist-100">HospitalShield</span>
              <span className="mt-1 block text-[10px] font-medium uppercase tracking-[0.18em] text-mist-500">Resilience intelligence</span>
            </span>
          </NavLink>

          <nav aria-label="Main" className="order-3 flex w-full gap-1 overflow-x-auto border-t border-ink-800 pt-3 pb-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `relative shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-teal-400 after:transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/70 ${isActive ? 'bg-ink-800 text-mist-100 after:opacity-100' : 'text-mist-400 after:opacity-0 hover:bg-ink-850 hover:text-mist-200'}`}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1.5">
            <div className="hidden items-center gap-1.5 sm:flex">
              <ProvenanceBadge kind="SYNTHETIC" />
              <ProvenanceBadge kind="CALCULATED" />
            </div>
            <DemoMode />
          </div>
        </div>
      </header>

      <ErrorBoundary>
        <main id="main-content" tabIndex={-1} className="mx-auto min-h-[calc(100vh-280px)] max-w-7xl px-4 py-6 outline-none sm:py-8 lg:px-6">
          <Outlet />
        </main>
      </ErrorBoundary>

      <footer className="no-print mt-8 border-t border-ink-700 bg-ink-900/60 px-4 py-4 text-xs text-mist-400">
        <div className="mx-auto max-w-7xl space-y-1">
          <p>
            Model version <span className="text-mist-200">{modelVersion ?? '—'}</span> · Data:{' '}
            <span className="text-mist-200">SYNTHETIC hospital baseline</span>
            {offline ? ' · PRECOMPUTED demo data (backend unreachable)' : ' · live backend'}
          </p>
          <p>
            Limitations: planning prototype — not a clinical, engineering-safety or live-operations system. No claim of
            clinical validity or predictive accuracy. Multipliers are scenario assumptions.
          </p>
        </div>
      </footer>
    </div>
  )
}
