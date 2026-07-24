import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import * as api from '../lib/api'
import type { PublicUser } from '../lib/types'

interface AuthContextValue {
  user: PublicUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  googleLogin: (credential: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<PublicUser | null>(null)
  const [loading, setLoading] = useState(true)

  // On first load, try to restore the session from the refresh cookie.
  useEffect(() => {
    api
      .refresh()
      .then(setUser)
      .catch(() => setUser(null)) // no valid session — that's fine
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => setUser(await api.login(email, password))
  const register = async (email: string, password: string) =>
    setUser(await api.register(email, password))
  const googleLogin = async (credential: string) => setUser(await api.google(credential))
  const logout = async () => {
    await api.logout()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, googleLogin, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
