import type { FinancialHistory } from './history'

export const PHILIPPINE_ASSUMPTIONS: {
  valuationDate: string
  localGovernmentYield: number
  grahamBaselineYield: number
  corporateTaxReference: number
  sourceLabel: string
  sourceUrl: string
  note: string
}
export const SOURCE_LINKS: Record<string, { label: string; href: string }>
export const INDUSTRIAL_COMPANIES: Array<{
  symbol: string
  name: string
  shortName: string
  sector: string
  subsector: string
  color: string
  dataConfidence: number
  insight: string
  source: { label: string; href: string }
  financials: Record<string, any>
  financialHistory?: FinancialHistory
  valuation: Record<string, any>
}>
export const VALUATION_COMPANIES: typeof INDUSTRIAL_COMPANIES
export const FILING_NEWS: Array<{ id: string; symbol: string; scope: string; date: string; title: string; summary: string; tag: string }>
