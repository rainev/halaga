import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Bookmark,
  BriefcaseBusiness,
  HeartPulse,
  LogOut,
  Newspaper,
  Scale,
  Sparkles,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/', label: 'Insights', icon: Newspaper, end: true },
  { to: '/rankings', label: 'Rankings', icon: BarChart3, end: false },
  { to: '/health', label: 'Financial Health', icon: HeartPulse, end: false },
  { to: '/valuation', label: 'Valuation', icon: Scale, end: false },
  { to: '/brief', label: 'Smart Brief', icon: Sparkles, end: false },
  { to: '/portfolio', label: 'Portfolio', icon: BriefcaseBusiness, end: false },
  { to: '/saved', label: 'Saved', icon: Bookmark, end: false },
]

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-[var(--app-bg)] text-[var(--app-text)]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[216px] flex-col border-r border-[var(--app-border)] bg-[var(--app-sidebar)] px-4 py-6 text-[var(--app-text)] lg:flex">
        <NavLink to="/" className="flex items-center gap-3 no-underline">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--app-bg)] font-serif text-lg font-bold text-[var(--app-text)] shadow-[0_8px_30px_var(--app-shadow)]">
            F
          </span>
          <span className="font-display text-lg font-bold tracking-tight">
            FinSight
            <small className="block text-[8px] font-medium tracking-[.22em] text-[var(--app-muted)]">
              INVESTING, SIMPLIFIED
            </small>
          </span>
        </NavLink>

        <nav className="mt-12 flex flex-1 flex-col gap-1" aria-label="Main navigation">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--app-muted)] hover:bg-[var(--app-subtle)] hover:text-[var(--app-text)]',
                  isActive && 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-[0_5px_18px_var(--app-shadow)]',
                )
              }
            >
              <Icon className="h-[18px] w-[18px]" /> {label}
            </NavLink>
          ))}
        </nav>

        {/* Account card — replaces the prototype's risk widget. */}
        <div className="rounded-2xl border border-[var(--app-border)] bg-[var(--app-surface)] p-3.5">
          <div className="flex items-center gap-2 text-[9px] font-bold tracking-[.15em] text-[var(--app-text)]">
            <span className="h-2 w-2 rounded-full bg-[var(--app-text)]" /> SIGNED IN
          </div>
          <strong className="mt-2 block truncate text-xs" title={user?.email}>
            {user?.email}
          </strong>
          <button
            onClick={handleLogout}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--app-border)] px-3 py-2 text-[11px] font-bold text-[var(--app-muted-strong)] hover:bg-[var(--app-subtle)] hover:text-[var(--app-text)]"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
        <p className="mt-4 px-1 text-[9px] leading-relaxed text-[var(--app-muted)]">
          Filing-based educational estimates<br />Not investment advice
        </p>
      </aside>

      <div className="min-h-screen pb-20 lg:ml-[216px] lg:pb-0">
        <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-[var(--app-border)] bg-[var(--app-bg)]/90 px-5 backdrop-blur-xl lg:justify-end lg:px-[4.5vw]">
          <NavLink to="/" className="flex items-center gap-2 font-display font-bold lg:hidden">
            <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[var(--app-text)] font-serif text-[var(--app-bg)]">F</span>{' '}
            FinSight
          </NavLink>
          <div className="flex items-center gap-2">
            <span className="mr-2 hidden font-mono text-xs text-[var(--app-muted)] sm:inline">{user?.email}</span>
            <ThemeToggle />
          </div>
        </header>

        <main className="mx-auto min-h-[calc(100vh-120px)] w-full max-w-[1420px] px-5 py-9 lg:px-[4.5vw] lg:py-12">
          <div key={location.pathname} className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-7 border-t border-[var(--app-border)] bg-[var(--app-surface)]/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
        aria-label="Mobile navigation"
      >
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-1 py-2 text-[8px] font-medium text-[var(--app-muted)]',
                isActive && 'text-[var(--app-text)]',
              )
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
