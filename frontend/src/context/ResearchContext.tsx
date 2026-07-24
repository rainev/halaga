import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Sentiment } from '../lib/types'

// Shared research controls: risk profile (persisted), valuation sentiment, and
// the selected company — so switching pages keeps your lens.
export type { Sentiment }

interface ResearchState {
  risk: number
  setRisk: (risk: number) => void
  sentiment: Sentiment
  setSentiment: (s: Sentiment) => void
  selectedSymbol: string
  setSelectedSymbol: (s: string) => void
}

const ResearchContext = createContext<ResearchState | null>(null)

function initialRisk(): number {
  const saved = Number(localStorage.getItem('finsight-risk'))
  return saved >= 1 && saved <= 5 ? saved : 3
}

export function ResearchProvider({ children }: { children: ReactNode }) {
  const [risk, setRiskState] = useState<number>(initialRisk)
  const [sentiment, setSentiment] = useState<Sentiment>('base')
  const [selectedSymbol, setSelectedSymbol] = useState('SCC')

  const value = useMemo<ResearchState>(
    () => ({
      risk,
      setRisk: (next) => {
        localStorage.setItem('finsight-risk', String(next))
        setRiskState(next)
      },
      sentiment,
      setSentiment,
      selectedSymbol,
      setSelectedSymbol,
    }),
    [risk, sentiment, selectedSymbol],
  )

  return <ResearchContext.Provider value={value}>{children}</ResearchContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useResearch() {
  const ctx = useContext(ResearchContext)
  if (!ctx) throw new Error('useResearch must be used within a ResearchProvider')
  return ctx
}

export const RISK_LABELS: Record<number, string> = {
  1: 'Capital Keeper',
  2: 'Steady Builder',
  3: 'Balanced Explorer',
  4: 'Growth Seeker',
  5: 'High-Conviction',
}
