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

// --- News feed (raw market news, pre-insight) ---

export interface NewsArticle {
  id: number
  source: string
  url: string
  title: string
  snippet: string | null
  published_at: string | null
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

// Filing-only U.S. valuations served by GET /api/us-valuations/{ticker}.
// The public artifact is price-free by design: no reported statement amounts,
// no market price, no buy/hold/sell label — only derived intrinsic values,
// governed assumptions, and provenance. Fields are optional/loose because the
// artifact carries provenance the UI shows opportunistically.
export type UsPublicationState = 'pass' | 'review_required' | 'withheld' | null

export interface UsModelResult {
  model: string
  output_type: string
  currency: string
  intrinsic_value_per_share: number | null
  publication_state: UsPublicationState
  errors: string[]
  warnings: string[]
}

export interface UsSegmentAssumption {
  label: string
  initial_revenue_growth?: number | null
  target_operating_margin?: number | null
  target_gross_margin?: number | null
}

export interface UsValuation {
  schema_version: string
  valuation_date: string
  market: string
  currency: string
  ticker: string
  issuer: {
    cik: string
    ticker: string
    issuer_name: string
    finsight_sector: string
    primary_archetype: string
    secondary_archetypes: string[]
    classification_confidence: number
    classification_reason?: string
  }
  source_financial_statement: {
    form: string
    period_end: string
    filed_date: string
    accession: string
    url: string
    note?: string
  }
  model_policy: { primary: string; supporting: string[]; blend_models: boolean; reason?: string }
  public_assumptions: {
    forecast_years: number
    forecast_mode?: string
    initial_revenue_growth?: number | null
    target_operating_margin?: number | null
    segment_assumptions?: Record<string, UsSegmentAssumption>
    terminal_growth: number
    policy_wacc: number
    risk_free_rate: number
    risk_free_effective_date?: string
    risk_free_source_url?: string
    equity_risk_premium: number
  }
  models: Record<string, UsModelResult>
  scenarios: Record<string, Record<string, UsModelResult>>
  scenario_range: { low: number; base: number; high: number; label?: string }
  review?: { publication_state: UsPublicationState; errors?: string[]; warnings?: string[] }
  methodology?: string
  // Machine-readable public-safety attestation baked into every artifact.
  data_boundary?: {
    raw_financial_statement_values_included: boolean
    stock_prices_used: boolean
    public_payload_contains: string
  }
}

export interface UsValuationSummary {
  ticker: string
  name: string | null
  sector: string | null
  model: string | null
  base: number | null
  publication_state: UsPublicationState
}

export interface UsValuationList {
  count: number
  items: UsValuationSummary[]
}
