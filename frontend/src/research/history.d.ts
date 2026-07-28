export interface FilingSource {
  label: string
  href?: string
  page?: string | number
}

export interface FinancialPeriod {
  period: string
  periodType?: 'annual' | 'quarterly' | 'ttm'
  fiscalYear: number
  fiscalQuarter?: 1 | 2 | 3 | 4
  periodEnd?: string
  isCumulative?: boolean
  source?: FilingSource
  cashFlowSource?: 'primary_source_fact' | 'internal_estimate' | 'mixed_or_derived'
  valuationCashFlow?: number | null
  freeCashFlow?: number | null
  operatingCashFlow?: number | null
  capitalExpenditure?: number | null
  [lineItem: string]: unknown
}

export interface FinancialHistory {
  annual?: FinancialPeriod[]
  quarterly?: FinancialPeriod[]
}

export interface HistorySummary {
  annualCount: number
  quarterlyCount: number
  annualTarget: number
  quarterlyTarget: number
  ttmAvailable: boolean
  errors: string[]
  warnings: string[]
  cashFlowBasisKey: string
  cashFlowBasisLabel: string
  cashFlowPeriodCount: number
}

export const OPTIONAL_HISTORY_TARGETS: { annual: number; quarterly: number }
export function getFinancialHistory(company: any): {
  annual: FinancialPeriod[]
  quarterly: FinancialPeriod[]
  invalidAnnual: FinancialPeriod[]
  invalidQuarterly: FinancialPeriod[]
  duplicateAnnualCount: number
  duplicateQuarterlyCount: number
}
export function validateFinancialHistory(company: any): ReturnType<typeof getFinancialHistory> & {
  errors: string[]
  warnings: string[]
}
export function getFinancialSnapshot(company: any): Record<string, any>
export function selectCashFlowBasis(company: any): {
  value: number
  key: string
  label: string
  periodCount: number
  source: string
  preference: string
  history: Omit<HistorySummary, 'cashFlowBasisKey' | 'cashFlowBasisLabel' | 'cashFlowPeriodCount'>
}
export function getFinancialHistorySummary(company: any): HistorySummary
