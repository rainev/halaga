import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LineChart, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Companies', end: true },
  { to: '/value', label: 'New Valuation', end: false },
  { to: '/saved', label: 'Saved', end: false },
]

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 bg-[hsl(var(--ink))] text-slate-100">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <LineChart className="h-[18px] w-[18px]" />
            </span>
            <div className="leading-none">
              <div className="font-display text-base font-bold tracking-tight">
                Halaga<span className="text-primary">.</span>
              </div>
              <div className="mt-0.5 text-[9px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                PSE Valuation
              </div>
            </div>
          </div>

          <nav className="flex items-center gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive ? 'bg-white/10 text-white' : 'text-slate-300 hover:bg-white/5 hover:text-white',
                  )
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <span className="hidden font-mono text-xs text-slate-400 sm:inline">{user?.email}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout} className="text-slate-300 hover:bg-white/10 hover:text-white">
              <LogOut className="h-4 w-4" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
