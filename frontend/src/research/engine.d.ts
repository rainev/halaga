import type { PortfolioLot, Sentiment } from './ResearchContext'
import type { HistorySummary } from './history'

export interface HealthMetric {
  key: string
  label: string
  description: string
  value: number | null
  target: number | null
  direction: 'min' | 'max' | 'range' | 'context'
  tolerance?: number
  format: 'percent' | 'multiple' | 'currency'
  status: 'pass' | 'watch' | 'unavailable' | 'context'
  score: number
}

export const RISK_PROFILES: Record<number, { label: string; short: string; tone: string }>
export const SENTIMENTS: Record<Sentiment, { label: string; fcfGrowth: number; discountRate: number; terminalGrowth: number; multipleFactor: number; epsGrowthPoints: number; dividendGrowth: number }>
export function getHealthMetrics(company: any, risk?: number): { pnl: HealthMetric[]; balance: HealthMetric[]; thresholds: Record<string, number>; derived: Record<string, number | null> }
export function getFinancialSnapshot(company: any): Record<string, any>
export function getFinancialHistorySummary(company: any): HistorySummary
export function validateFinancialHistory(company: any): {
  annual: any[]
  quarterly: any[]
  errors: string[]
  warnings: string[]
}
export function scoreCompany(company: any, risk?: number): number
export function calculateResidualIncome(company: any, sentiment?: Sentiment): any
export function calculateBankDdm(company: any, sentiment?: Sentiment): any
export function calculateJustifiedPb(company: any, sentiment?: Sentiment): any
export function calculateValuation(company: any, sentiment?: Sentiment): {
  primaryModel: string
  primaryValue: number | null
  scenarioLow: number | null
  scenarioHigh: number | null
  crossChecks: string[]
  status: 'pass' | 'review' | 'blocked'
  policyReason: string
  warnings: string[]
  errors: string[]
  models: Record<string, any>
}
export function portfolioCostBasis(lots?: Array<{ quantity: number; purchasePrice: number }>): number
export function portfolioRealizedReturn(lots?: Array<{ quantity: number; purchasePrice: number; salePrice?: number; saleDate?: string }>): {
  cost: number
  proceeds: number
  amount: number
  percent: number
}
export function buildSmartBrief(company: any, risk?: number, sentiment?: Sentiment, lots?: PortfolioLot[]): {
  headline: string
  score: number
  paragraphs: string[]
  passLabels: string[]
  watchLabels: string[]
}
