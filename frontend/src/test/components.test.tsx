/** Component tests (S6): units and deltas, alert highlighting, hospital map
 * status from backend, scenario control validation messages, offline state. */

import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { KpiCard } from '@/components/KpiCard'
import { AlertPanel } from '@/components/AlertPanel'
import { HospitalMap } from '@/components/HospitalMap'
import { ScenarioControls, applyPreset, DEFAULT_REQUEST } from '@/components/ScenarioControls'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'
import type { AlertEpisode, HourRow } from '@/types/domain'

function row(overrides: Partial<HourRow> = {}): HourRow {
  return {
    hour: 0,
    temperature_c: 30,
    grid_fraction: 1,
    power: {
      demand_kw: 400, grid_supply_kw: 450, gen_output_kw: 0, available_supply_kw: 450,
      deficit_kw: 0, reserve_kw: 50, critical_at_risk_kw: 0, critical_demand_kw: 250,
      shed_kw: 0, fuel_l: 2500,
    },
    staffing: {
      ed: { available: 9, staffed_capacity: 36, required: 6, shortfall: 0 },
      ward: { available: 16, staffed_capacity: 96, required: 14, shortfall: 0 },
      icu: { available: 8, staffed_capacity: 16, required: 7, shortfall: 0 },
    },
    units: {
      ed: { open_beds: 26, usable_beds: 26, occupied: 20, available_beds: 6, occupancy_pct: 76.9, beds_over_usable: 0, status: 'ok' },
      ward: { open_beds: 100, usable_beds: 96, occupied: 95, available_beds: 1, occupancy_pct: 99, beds_over_usable: 0, status: 'critical' },
      icu: { open_beds: 20, usable_beds: 16, occupied: 14, available_beds: 2, occupancy_pct: 87.5, beds_over_usable: 0, status: 'ok' },
    },
    supplies: {},
    access: { staff_access_fraction: 1, delivery_fraction: 1, arrival_multiplier: 1 },
    ed: { waiting: 3, in_service: 20, boarding_ward: 0, boarding_icu: 0, arrivals: 6, admitted_ward: 1, admitted_icu: 0 },
    discharged: 1,
    binding_constraint: 'beds',
    margins: { power: 0.9, supplies: 1, staff: 0.9, beds: 0, ed_flow: 0.7 },
    ...overrides,
  } as HourRow
}

describe('KpiCard', () => {
  it('shows value and unit', () => {
    render(<KpiCard label="Peak ward occupancy" value={95.2} unit="%" />)
    expect(screen.getByText('95.2')).toBeInTheDocument()
    expect(screen.getByText('%')).toBeInTheDocument()
  })

  it('shows delta with sign', () => {
    render(<KpiCard label="Overflow" value={100} unit="p-h" delta={{ absolute: -42 }} />)
    expect(screen.getByText((_, el) => /^-42(\.0)? p-h vs baseline$/.test(el?.textContent ?? ''))).toBeInTheDocument()
  })

  it('renders null value as em dash (never NaN)', () => {
    render(<KpiCard label="Cover" value={null} unit="h" />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

describe('AlertPanel', () => {
  const alerts: AlertEpisode[] = [{
    rule_id: 'R01', rule_text: 'ward_occupancy_high', severity: 'high', metric: 'occupancy_pct',
    unit: 'pct', observed_peak: 99, threshold: 90, first_hour: 12, last_hour: 30,
    duration_hours: 19, affected_variable: 'ward',
  }]

  it('shows rule id, threshold, observed value and hours', () => {
    render(<AlertPanel alerts={alerts} onHighlight={() => {}} highlight={null} />)
    expect(screen.getByText(/R01/)).toBeInTheDocument()
    expect(screen.getByText(/peak/i)).toBeInTheDocument()
    expect(screen.getByText(/99 pct/)).toBeInTheDocument()
    expect(screen.getByText(/threshold 90 pct/)).toBeInTheDocument()
  })

  it('clicking an alert highlights its hour range', async () => {
    let range: [number, number] | null = null
    render(<AlertPanel alerts={alerts} onHighlight={(r) => { range = r }} highlight={null} />)
    await userEvent.click(screen.getByRole('button'))
    expect(range).toEqual([12, 30])
  })

  it('shows a calm empty state when no alerts', () => {
    render(<AlertPanel alerts={[]} onHighlight={() => {}} highlight={null} />)
    expect(screen.getByText(/no alerts/i)).toBeInTheDocument()
  })
})

describe('HospitalMap', () => {
  it('colours follow backend status with icon and text (not colour alone)', () => {
    render(<HospitalMap rows={[row()]} selectedHour={0} onSelectHour={() => {}} />)
    expect(screen.getByText(/■ CRITICAL/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Inpatient Ward: CRITICAL/ })).toBeInTheDocument()
  })

  it('scrubber selects an hour', async () => {
    const hours = [row(), row({ hour: 1 })]
    let selected: number | null = null
    render(<HospitalMap rows={hours} selectedHour={0} onSelectHour={(h) => { selected = h }} />)
    const slider = screen.getByRole('slider', { name: /time scrubber/i })
    slider.focus()
    fireEvent.change(slider, { target: { value: '1' } })
    expect(selected).toBe(1)
  })
})

describe('ScenarioControls', () => {
  it('shows backend validation messages inline', () => {
    render(
      <ScenarioControls
        request={DEFAULT_REQUEST} onChange={() => {}} info={null}
        error="request payload failed validation"
        errorDetails={[{ field: 'stress.arrival_multiplier', reason: 'must be <= 3.0' }]}
        onRun={() => {}} loading={false} />,
    )
    expect(screen.getByText(/request payload failed validation/)).toBeInTheDocument()
    expect(screen.getByText(/stress.arrival_multiplier/)).toBeInTheDocument()
    expect(screen.getByText(/must be <= 3.0/)).toBeInTheDocument()
  })

  it('presets switch the scenario', async () => {
    let current = DEFAULT_REQUEST
    render(
      <ScenarioControls request={DEFAULT_REQUEST} onChange={(r) => { current = r }} info={null}
        error={null} errorDetails={[]} onRun={() => {}} loading={false} />,
    )
    await userEvent.click(screen.getByRole('radio', { name: /flood storm access/i }))
    expect(current.scenario).toBe('flood_storm_access')
    expect(current.access?.staff_access_fraction).toBe(0.6)
  })

  it('applyPreset resets outage for normal operations', () => {
    const req = applyPreset(DEFAULT_REQUEST, 'normal_operations')
    expect(req.outage).toBeNull()
    expect(req.stress?.arrival_multiplier).toBe(1.0)
  })
})

describe('ProvenanceBadge', () => {
  it('renders the honest label', () => {
    render(<ProvenanceBadge kind="SYNTHETIC" />)
    expect(screen.getByText('SYNTHETIC')).toBeInTheDocument()
  })
})
