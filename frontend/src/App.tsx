import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { OnboardingGate } from './research/Onboarding'
import { ResearchProvider } from './research/ResearchContext'
import Rankings from './research/pages/Rankings'
import ValuationLab from './research/pages/ValuationLab'
import FinancialHealth from './research/pages/FinancialHealth'
import Briefings from './research/pages/Briefings'
import Portfolio from './research/pages/Portfolio'
import SmartBrief from './research/pages/SmartBrief'

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ResearchProvider>
        <OnboardingGate>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Rankings />} />
              <Route path="valuation" element={<ValuationLab />} />
              <Route path="health" element={<FinancialHealth />} />
              <Route path="briefings" element={<Briefings />} />
              <Route path="portfolio" element={<Portfolio />} />
              <Route path="brief" element={<SmartBrief />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </OnboardingGate>
      </ResearchProvider>
    </BrowserRouter>
  )
}
