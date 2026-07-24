// Shared types. The backend is Python/Pydantic, so these are hand-kept in sync
// with app/models/*.py (JSON is snake_case on both sides).

export type Role = 'user' | 'admin'

export interface PublicUser {
  id: number
  email: string
  role: Role
  is_verified: boolean
}

export interface AuthResponse {
  user: PublicUser
  access_token: string
}

export interface Company {
  id: number
  ticker: string
  name: string
  sector: string | null
  currency: string
}

export type ModelKind = 'dcf' | 'ddm' | 'graham' | 'multiples'

export interface ValuationResult {
  model: ModelKind
  intrinsic_value: number
  current_price: number | null
  upside_pct: number | null
  verdict: string | null
  detail: Record<string, unknown>
  saved_id?: number
}

export interface SavedValuation {
  id: number
  company_id: number | null
  model: ModelKind
  inputs: Record<string, unknown>
  assumptions: Record<string, unknown>
  result: ValuationResult
  created_at: string
}

// --- Portfolio-aware insights ---

export interface Holding {
  id: number
  company_id: number
  ticker: string
  name: string
  sector: string | null
}

export type InsightDirection = 'headwind' | 'tailwind' | 'mixed' | 'neutral'

export interface InsightSource {
  title: string | null
  url: string | null
}

export interface FeedInsight {
  id: number
  company_id: number
  ticker: string
  name: string
  sector: string | null
  summary: string
  possible_impact: string
  direction: InsightDirection | null
  confidence: number | null
  sources: InsightSource[]
  link_type: 'direct' | 'thematic'
  article_title: string
  article_url: string
  published_at: string | null
  created_at: string
}

// --- Research workbench (filing-based) ---

export type Sentiment = 'bear' | 'base' | 'bull'

export interface ResearchCompany {
  symbol: string
  name: string
  shortName: string | null
  sector: string | null
  subsector: string | null
  color: string | null
  insight: string | null
  source: { label: string; href: string } | null
  period: string | null
}

export interface RankedCompany extends ResearchCompany {
  score: number
  checks: { passes: number; total: number }
}

export interface RankingsResponse {
  risk: number
  profile: { label: string; short: string; tone: string }
  ranked: RankedCompany[]
}

export type MetricStatus = 'pass' | 'watch' | 'unavailable' | 'context'

export interface HealthMetric {
  key: string
  label: string
  description: string
  value: number | null
  target: number | null
  direction: 'min' | 'max' | 'range' | 'context'
  tolerance?: number
  format: 'percent' | 'multiple' | 'currency'
  status: MetricStatus
  score: number
}

export interface HealthResponse {
  company: ResearchCompany
  risk: number
  profile: { label: string; short: string; tone: string }
  pnl: HealthMetric[]
  balance: HealthMetric[]
}

export interface ValuationModel {
  perShare: number
  peerPe?: number
  discountRate?: number
  terminalGrowth?: number
  normalizedFcf?: number
}

export interface ResearchValuation {
  company: ResearchCompany
  sentiment: Sentiment
  weights: Record<string, number>
  valuationNote: string | null
  assumptions: {
    riskFreeRate: number
    grahamBaselineYield: number
    note: string
    sourceUrl: string
    sourceLabel: string
  }
  blended: number
  low: number
  high: number
  models: {
    dcf: ValuationModel
    graham: ValuationModel
    multiples: ValuationModel
    ddm: ValuationModel | null
  }
}

export interface SmartBrief {
  company: ResearchCompany
  risk: number
  sentiment: Sentiment
  headline: string
  score: number
  paragraphs: string[]
  passLabels: string[]
  watchLabels: string[]
}
