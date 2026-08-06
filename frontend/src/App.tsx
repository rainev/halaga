import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ResearchProvider } from './context/ResearchContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
import Companies from './pages/Companies'
import Valuation from './pages/Valuation'
import Saved from './pages/Saved'
import Portfolio from './pages/Portfolio'
import Insights from './pages/Insights'
import News from './pages/News'
import Rankings from './pages/Rankings'
import FinancialHealth from './pages/FinancialHealth'
import ValuationLab from './pages/ValuationLab'
import UsValuations from './pages/UsValuations'
import SmartBrief from './pages/SmartBrief'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ResearchProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<Insights />} />
                <Route path="/news" element={<News />} />
                <Route path="/rankings" element={<Rankings />} />
                <Route path="/health" element={<FinancialHealth />} />
                <Route path="/valuation" element={<ValuationLab />} />
                <Route path="/us-valuations" element={<UsValuations />} />
                <Route path="/brief" element={<SmartBrief />} />
                <Route path="/portfolio" element={<Portfolio />} />
                <Route path="/companies" element={<Companies />} />
                <Route path="/value" element={<Valuation />} />
                <Route path="/saved" element={<Saved />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ResearchProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
