import type { FinancialHistory } from './history'

export type USSegmentAssumption = {
  label?: string
  initial_revenue_growth?: number | null
  target_operating_margin?: number | null
  target_gross_margin?: number | null
}

export type USPublicationState = 'pass' | 'review_required' | 'withheld'

export type USValuation = {
  ticker: string
  source_financial_statement: {
    period_end: string
  }
  public_assumptions: {
    forecast_mode: string
    forecast_years: number | null
    segment_assumptions?: Record<string, USSegmentAssumption>
    policy_wacc: number | null
    risk_free_rate: number | null
    equity_risk_premium: number | null
    terminal_growth: number | null
    target_operating_margin: number | null
    risk_free_source_url: string
  }
  review: {
    publication_state: USPublicationState
    confidence_grade: string
    errors?: string[]
    warnings?: string[]
  }
  models: Record<string, {
    intrinsic_value_per_share: number | null
    publication_state?: USPublicationState
  }>
  data_boundary: {
    stock_prices_used: boolean
  }
}

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
  market?: string
  currency?: string
  archetype?: string
  color: string
  dataConfidence: number
  insight: string
  source: { label: string; href: string }
  financials: Record<string, any>
  financialHistory?: FinancialHistory
  valuation: Record<string, any> & { us?: USValuation }
}>
export const VALUATION_COMPANIES: typeof INDUSTRIAL_COMPANIES
export const FILING_NEWS: Array<{ id: string; symbol: string; scope: string; date: string; title: string; summary: string; tag: string }>
