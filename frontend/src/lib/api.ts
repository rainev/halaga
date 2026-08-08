// Thin API client for the valuation backend.
//
// The access token is kept in memory (not localStorage) so it can't be lifted
// from disk by XSS. The refresh token lives in an httpOnly cookie the browser
// sends automatically because every request uses `credentials: 'include'`.

import type {
  AuthResponse,
  Company,
  FeedInsight,
  HealthResponse,
  Holding,
  NewsArticle,
  PublicUser,
  RankingsResponse,
  ResearchCompany,
  ResearchValuation,
  SavedValuation,
  Sentiment,
  SmartBrief,
  UsValuation,
  UsValuationList,
  ValuationResult,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:4001'

let accessToken: string | null = null
export function setAccessToken(token: string | null) {
  accessToken = token
}

interface RequestOpts extends RequestInit {
  _retried?: boolean
}

async function request<T>(path: string, options: RequestOpts = {}): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    ...options,
    credentials: 'include', // send/receive the refresh cookie
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  })

  // Access token expired mid-session: silently refresh once, then retry.
  if (res.status === 401 && !options._retried && !path.startsWith('/auth/')) {
    try {
      await refresh()
      return request<T>(path, { ...options, _retried: true })
    } catch {
      // fall through to the error below
    }
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error((data as { error?: string } | null)?.error ?? 'Request failed')
  }
  return data as T
}

// --- Auth ---
export async function register(email: string, password: string): Promise<PublicUser> {
  const data = await request<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setAccessToken(data.access_token)
  return data.user
}

export async function login(email: string, password: string): Promise<PublicUser> {
  const data = await request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setAccessToken(data.access_token)
  return data.user
}

// Sign in / register with Google: sends the ID token from Google Identity
// Services; the backend verifies it and finds-or-creates the account.
export async function google(credential: string): Promise<PublicUser> {
  const data = await request<AuthResponse>('/auth/google', {
    method: 'POST',
    body: JSON.stringify({ credential }),
  })
  setAccessToken(data.access_token)
  return data.user
}

export async function refresh(): Promise<PublicUser> {
  const data = await request<AuthResponse>('/auth/refresh', { method: 'POST' })
  setAccessToken(data.access_token)
  return data.user
}

export async function logout(): Promise<void> {
  await request<null>('/auth/logout', { method: 'POST' })
  setAccessToken(null)
}

// --- Companies ---
export function listCompanies(sector?: string): Promise<Company[]> {
  const q = sector ? `?sector=${encodeURIComponent(sector)}` : ''
  return request<Company[]>(`/companies${q}`)
}

// --- Valuations ---
export function runValuation(model: string, payload: unknown): Promise<ValuationResult> {
  return request<ValuationResult>(`/valuations/${model}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listValuations(): Promise<SavedValuation[]> {
  return request<SavedValuation[]>('/valuations')
}

export function deleteValuation(id: number): Promise<null> {
  return request<null>(`/valuations/${id}`, { method: 'DELETE' })
}

// --- Holdings (portfolio) ---
export function listHoldings(): Promise<Holding[]> {
  return request<Holding[]>('/holdings')
}

export function addHolding(ticker: string): Promise<Holding> {
  return request<Holding>('/holdings', {
    method: 'POST',
    body: JSON.stringify({ ticker }),
  })
}

export function removeHolding(id: number): Promise<null> {
  return request<null>(`/holdings/${id}`, { method: 'DELETE' })
}

// --- Insights feed (holdings-scoped) ---
export function listInsights(limit = 50): Promise<FeedInsight[]> {
  return request<FeedInsight[]>(`/insights?limit=${limit}`)
}

// --- News feed (raw market news) ---
export function listNews(limit = 50): Promise<NewsArticle[]> {
  return request<NewsArticle[]>(`/news?limit=${limit}`)
}

// Force a fresh pull from GNews (admin-only on the backend).
export function refreshNews(): Promise<{ ingested: number }> {
  return request<{ ingested: number }>('/news/refresh', { method: 'POST' })
}

// --- Research workbench (filing-based) ---
export function listResearchCompanies(): Promise<ResearchCompany[]> {
  return request<ResearchCompany[]>('/research/companies')
}

export function getRankings(risk: number): Promise<RankingsResponse> {
  return request<RankingsResponse>(`/research/rankings?risk=${risk}`)
}

export function getHealth(ticker: string, risk: number): Promise<HealthResponse> {
  return request<HealthResponse>(`/research/health/${ticker}?risk=${risk}`)
}

export function getValuation(ticker: string, sentiment: Sentiment): Promise<ResearchValuation> {
  return request<ResearchValuation>(`/research/valuation/${ticker}?sentiment=${sentiment}`)
}

export function getBrief(ticker: string, risk: number, sentiment: Sentiment): Promise<SmartBrief> {
  return request<SmartBrief>(`/research/brief/${ticker}?risk=${risk}&sentiment=${sentiment}`)
}

// Filing-only U.S. valuations (precomputed, reviewed, price-free public artifact).
export function listUsValuations(): Promise<UsValuationList> {
  return request<UsValuationList>('/us-valuations')
}

export function getUsValuation(ticker: string): Promise<UsValuation> {
  return request<UsValuation>(`/us-valuations/${ticker}`)
}
