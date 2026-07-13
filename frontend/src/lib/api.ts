// Thin API client for the valuation backend.
//
// The access token is kept in memory (not localStorage) so it can't be lifted
// from disk by XSS. The refresh token lives in an httpOnly cookie the browser
// sends automatically because every request uses `credentials: 'include'`.

import type {
  AuthResponse,
  Company,
  PublicUser,
  SavedValuation,
  ValuationResult,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

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
