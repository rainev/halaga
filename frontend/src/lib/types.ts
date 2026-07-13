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
