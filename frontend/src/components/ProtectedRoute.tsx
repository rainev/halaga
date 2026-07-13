import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../context/AuthContext'

// Gate for authenticated-only pages. While the initial session check runs we
// show a placeholder; after that, redirect to /login if there's no user.
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}
