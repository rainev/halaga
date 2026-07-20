import { createContext, useContext, useMemo, useState } from 'react'

export type Sentiment = 'bear' | 'base' | 'bull'
export interface PortfolioLot {
  id: string
  symbol: string
  quantity: number
  purchasePrice: number
  purchaseDate: string
  salePrice?: number
  saleDate?: string
}

interface ResearchState {
  risk: number | null
  setRisk: (risk: number) => void
  resetRisk: () => void
  selectedSymbol: string
  setSelectedSymbol: (symbol: string) => void
  sentiment: Sentiment
  setSentiment: (sentiment: Sentiment) => void
  lots: PortfolioLot[]
  addLot: (lot: Omit<PortfolioLot, 'id'>) => void
  updateLot: (id: string, updates: Partial<Omit<PortfolioLot, 'id' | 'symbol' | 'quantity' | 'purchasePrice' | 'purchaseDate'>>) => void
  removeLot: (id: string) => void
}

const ResearchContext = createContext<ResearchState | null>(null)

function readLots(): PortfolioLot[] {
  try {
    const saved = localStorage.getItem('finsight-portfolio') ?? localStorage.getItem('halaga-portfolio') ?? '[]'
    return JSON.parse(saved) as PortfolioLot[]
  } catch {
    return []
  }
}

export function ResearchProvider({ children }: { children: React.ReactNode }) {
  const storedRisk = Number(localStorage.getItem('finsight-risk') ?? localStorage.getItem('halaga-risk'))
  const [risk, updateRisk] = useState<number | null>(storedRisk >= 1 && storedRisk <= 5 ? storedRisk : null)
  const [selectedSymbol, setSelectedSymbol] = useState('SCC')
  const [sentiment, setSentiment] = useState<Sentiment>('base')
  const [lots, setLots] = useState<PortfolioLot[]>(readLots)

  const value = useMemo<ResearchState>(() => ({
    risk,
    setRisk: (next) => {
      localStorage.setItem('finsight-risk', String(next))
      updateRisk(next)
    },
    resetRisk: () => {
      localStorage.removeItem('finsight-risk')
      localStorage.removeItem('halaga-risk')
      updateRisk(null)
    },
    selectedSymbol,
    setSelectedSymbol,
    sentiment,
    setSentiment,
    lots,
    addLot: (lot) => {
      setLots((current) => {
        const next = [...current, { ...lot, id: crypto.randomUUID() }]
        localStorage.setItem('finsight-portfolio', JSON.stringify(next))
        return next
      })
    },
    updateLot: (id, updates) => {
      setLots((current) => {
        const next = current.map((lot) => lot.id === id ? { ...lot, ...updates } : lot)
        localStorage.setItem('finsight-portfolio', JSON.stringify(next))
        return next
      })
    },
    removeLot: (id) => {
      setLots((current) => {
        const next = current.filter((lot) => lot.id !== id)
        localStorage.setItem('finsight-portfolio', JSON.stringify(next))
        return next
      })
    },
  }), [risk, selectedSymbol, sentiment, lots])

  return <ResearchContext.Provider value={value}>{children}</ResearchContext.Provider>
}

export function useResearch() {
  const value = useContext(ResearchContext)
  if (!value) throw new Error('useResearch must be used inside ResearchProvider')
  return value
}
