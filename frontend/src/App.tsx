import { Navigate, Route, Routes } from 'react-router-dom'
import { CygnetAppShell } from './components/layout/AppShell'
import { AIInsightsPage } from './pages/AIInsightsPage'
import { GenerationPage } from './pages/GenerationPage'
import { IngestionPage } from './pages/IngestionPage'

export default function App() {
  return (
    <CygnetAppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/generation" replace />} />
        <Route path="/generation" element={<GenerationPage />} />
        <Route path="/insights" element={<AIInsightsPage />} />
        <Route path="/ingest" element={<IngestionPage />} />
      </Routes>
    </CygnetAppShell>
  )
}
