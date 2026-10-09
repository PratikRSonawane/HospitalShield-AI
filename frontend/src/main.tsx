import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import '@/index.css'
import { Layout } from '@/components/Layout'
import { RunProvider } from '@/state/RunContext'
import { OverviewPage } from '@/pages/Overview'
import { HospitalTwinPage } from '@/pages/HospitalTwin'
import { ScenarioLabPage } from '@/pages/ScenarioLab'
import { FailurePointsPage } from '@/pages/FailurePoints'
import { ComparePage } from '@/pages/Compare'
import { AssumptionsPage } from '@/pages/Assumptions'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <RunProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="/twin" element={<HospitalTwinPage />} />
            <Route path="/lab" element={<ScenarioLabPage />} />
            <Route path="/failures" element={<FailurePointsPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/assumptions" element={<AssumptionsPage />} />
          </Route>
        </Routes>
      </RunProvider>
    </BrowserRouter>
  </StrictMode>,
)
