/** All time-series charts. Data comes only from the backend hourly rows. */

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { HourRow } from '@/types/domain'

const AXIS = { stroke: '#8b9bb8', fontSize: 11 }
const GRID = '#243049'
const TOOLTIP_STYLE = { backgroundColor: '#131c30', border: '1px solid #33415e', fontSize: 12 }

export interface SeriesProps {
  rows: HourRow[]
  highlight?: [number, number] | null
  selectedHour?: number | null
}

function toRows(rows: HourRow[]) {
  return rows.map((r) => ({
    hour: r.hour,
    temp: r.temperature_c,
    wardOcc: r.units.ward.occupancy_pct,
    icuOcc: r.units.icu.occupancy_pct,
    edOcc: r.units.ed.occupancy_pct,
    waiting: r.ed.waiting,
    boarding: (r.ed.boarding_ward ?? 0) + (r.ed.boarding_icu ?? 0),
    demand: r.power.demand_kw,
    supply: r.power.available_supply_kw,
    deficit: r.power.deficit_kw,
    staffReqW: r.staffing.ward.required,
    staffAvailW: r.staffing.ward.available,
    staffReqI: r.staffing.icu.required,
    staffAvailI: r.staffing.icu.available,
    fuel: r.power.fuel_l,
    coverO2: r.supplies?.oxygen?.cover_hours ?? null,
    coverMeds: r.supplies?.essential_meds?.cover_hours ?? null,
  }))
}

export function OccupancyChart({ rows, highlight, selectedHour }: SeriesProps) {
  const data = toRows(rows)
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="hour" {...AXIS} tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <YAxis domain={[0, 100]} {...AXIS} tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {highlight && <ReferenceArea x1={highlight[0]} x2={highlight[1]} fill="#fbbf24" fillOpacity={0.08} />}
        <ReferenceLine y={90} stroke="#fbbf24" strokeDasharray="4 4" label={{ value: 'warn 90%', fill: '#fbbf24', fontSize: 10 }} />
        <ReferenceLine y={100} stroke="#fb7185" strokeDasharray="4 4" label={{ value: 'critical', fill: '#fb7185', fontSize: 10 }} />
        <Line type="monotone" dataKey="wardOcc" name="Ward %" stroke="#2dd4bf" dot={false} />
        <Line type="monotone" dataKey="icuOcc" name="ICU %" stroke="#a78bfa" dot={false} />
        <Line type="monotone" dataKey="edOcc" name="ED %" stroke="#fbbf24" dot={false} />
        {selectedHour != null && <ReferenceLine x={selectedHour} stroke="#ccd5e6" />}
      </LineChart>
    </ResponsiveContainer>
  )
}

export function EdFlowChart({ rows, highlight, selectedHour }: SeriesProps) {
  const data = toRows(rows)
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="hour" tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {highlight && <ReferenceArea x1={highlight[0]} x2={highlight[1]} fill="#fbbf24" fillOpacity={0.08} />}
        <Bar dataKey="waiting" name="ED waiting" fill="#fbbf24" />
        <Bar dataKey="boarding" name="ED boarding" fill="#fb7185" />
        {selectedHour != null && <ReferenceLine x={selectedHour} stroke="#ccd5e6" />}
      </BarChart>
    </ResponsiveContainer>
  )
}

export function PowerChart({ rows, highlight, selectedHour }: SeriesProps) {
  const data = toRows(rows)
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="hour" tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {highlight && <ReferenceArea x1={highlight[0]} x2={highlight[1]} fill="#fbbf24" fillOpacity={0.08} />}
        <Area type="monotone" dataKey="demand" name="Demand kW" stroke="#fbbf24" fill="#fbbf24" fillOpacity={0.15} />
        <Area type="monotone" dataKey="supply" name="Available supply kW" stroke="#2dd4bf" fill="#2dd4bf" fillOpacity={0.1} />
        <Area type="monotone" dataKey="deficit" name="Deficit kW" stroke="#fb7185" fill="#fb7185" fillOpacity={0.35} />
        {selectedHour != null && <ReferenceLine x={selectedHour} stroke="#ccd5e6" />}
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function StaffChart({ rows, highlight, selectedHour }: SeriesProps) {
  const data = toRows(rows)
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="hour" tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {highlight && <ReferenceArea x1={highlight[0]} x2={highlight[1]} fill="#fbbf24" fillOpacity={0.08} />}
        <Line type="stepAfter" dataKey="staffReqW" name="Ward required" stroke="#fb7185" dot={false} />
        <Line type="stepAfter" dataKey="staffAvailW" name="Ward available" stroke="#2dd4bf" dot={false} />
        <Line type="stepAfter" dataKey="staffReqI" name="ICU required" stroke="#f472b6" dot={false} />
        <Line type="stepAfter" dataKey="staffAvailI" name="ICU available" stroke="#38bdf8" dot={false} />
        {selectedHour != null && <ReferenceLine x={selectedHour} stroke="#ccd5e6" />}
      </LineChart>
    </ResponsiveContainer>
  )
}

export function FuelChart({ rows, highlight, selectedHour }: SeriesProps) {
  const data = toRows(rows)
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="hour" tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {highlight && <ReferenceArea x1={highlight[0]} x2={highlight[1]} fill="#fbbf24" fillOpacity={0.08} />}
        <Area type="monotone" dataKey="fuel" name="Fuel litres" stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.2} />
        {selectedHour != null && <ReferenceLine x={selectedHour} stroke="#ccd5e6" />}
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function SupplyCoverChart({ rows, highlight, selectedHour }: SeriesProps) {
  const data = toRows(rows)
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="hour" tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8b9bb8', fontSize: 11 }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <ReferenceLine y={24} stroke="#fbbf24" strokeDasharray="4 4" label={{ value: 'low cover 24 h', fill: '#fbbf24', fontSize: 10 }} />
        {highlight && <ReferenceArea x1={highlight[0]} x2={highlight[1]} fill="#fbbf24" fillOpacity={0.08} />}
        <Line type="monotone" dataKey="coverO2" name="Oxygen cover h" stroke="#2dd4bf" dot={false} />
        <Line type="monotone" dataKey="coverMeds" name="Meds cover h" stroke="#a78bfa" dot={false} />
        {selectedHour != null && <ReferenceLine x={selectedHour} stroke="#ccd5e6" />}
      </LineChart>
    </ResponsiveContainer>
  )
}

export function chartTable(rows: HourRow[], pick: (r: HourRow) => (string | number | null)[], columns: string[]) {
  return {
    columns,
    rows: rows.filter((_, i) => i % 4 === 0 || i === rows.length - 1).map((r) => [r.hour, ...pick(r)]),
  }
}
