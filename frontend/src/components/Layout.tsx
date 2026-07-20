import { NavLink, useLocation, useOutlet } from 'react-router-dom'
import {
  BarChart3,
  BriefcaseBusiness,
  FileText,
  HeartPulse,
  Newspaper,
  Sparkles,
} from 'lucide-react'
import { RISK_PROFILES } from '../research/engine.js'
import { useResearch } from '../research/ResearchContext'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/', label: 'Rankings', icon: BarChart3, end: true },
  { to: '/valuation', label: 'Valuation', icon: FileText, end: false },
  { to: '/health', label: 'Health', icon: HeartPulse, end: false },
  { to: '/briefings', label: 'Briefings', icon: Newspaper, end: false },
  { to: '/portfolio', label: 'Portfolio', icon: BriefcaseBusiness, end: false },
  { to: '/brief', label: 'Smart Brief', icon: Sparkles, end: false },
]

export function Layout() {
  const { risk, resetRisk } = useResearch()
  const profile = RISK_PROFILES[risk ?? 3]
  const location = useLocation()
  const outlet = useOutlet()

  return (
    <div className="min-h-screen bg-[var(--app-bg)] text-[var(--app-text)]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[244px] flex-col bg-[var(--app-text)] px-5 py-7 text-[var(--app-bg)] lg:flex">
        <NavLink to="/" className="flex items-center gap-3 no-underline">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--app-bg)] font-serif text-lg font-bold text-[var(--app-text)] shadow-[0_8px_30px_rgba(255,255,255,.12)]">F</span>
          <span className="font-display text-lg font-bold tracking-tight">FinSight<small className="block text-[8px] font-medium tracking-[.22em] text-[var(--app-muted)]">INVESTING, SIMPLIFIED</small></span>
        </NavLink>

        <nav className="mt-12 flex flex-1 flex-col gap-1" aria-label="Main navigation">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cn(
                'flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-medium text-[var(--app-muted)] hover:bg-[var(--app-surface)]/[.07] hover:text-[var(--app-bg)]',
                isActive && 'bg-[var(--app-bg)] text-[var(--app-text)] shadow-[0_8px_28px_rgba(0,0,0,.28)]',
              )}
            >
              <Icon className="h-[18px] w-[18px]" /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="rounded-2xl border border-white/10 bg-[var(--app-surface)]/[.045] p-4">
          <div className="flex items-center gap-2 text-[9px] font-bold tracking-[.15em] text-[var(--app-bg)]"><span className="h-2 w-2 rounded-full bg-[var(--app-bg)]" />PRIVATE BY DEFAULT</div>
          <strong className="mt-3 block text-sm">Stored on your device</strong>
          <p className="mt-1 text-[11px] leading-relaxed text-[var(--app-muted)]">No account or API key.</p>
        </div>
        <p className="mt-4 px-1 text-[9px] leading-relaxed text-[var(--app-muted)]">Educational mockup<br />Not investment advice</p>
      </aside>

      <div className="min-h-screen pb-20 lg:ml-[244px] lg:pb-0">
        <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-[var(--app-border)] bg-[var(--app-bg)]/90 px-5 backdrop-blur-xl lg:justify-end lg:px-[4.5vw]">
          <NavLink to="/" className="flex items-center gap-2 font-display font-bold lg:hidden">
            <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[var(--app-text)] font-serif text-[var(--app-bg)]">F</span> FinSight
          </NavLink>
          <div className="flex items-center gap-2">
            <div className="mr-2 hidden items-center gap-2 text-xs font-medium text-[var(--app-muted)] lg:flex"><span className="h-2 w-2 rounded-full bg-[var(--app-text)]" /> FY2025 filing data</div>
            <ThemeToggle />
            <button onClick={resetRisk} className="flex items-center gap-2 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] p-1.5 pr-3 text-left shadow-sm" title="Change risk profile">
              <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-[var(--app-text)] text-xs font-extrabold text-[var(--app-bg)]">{risk}</span>
              <span className="hidden sm:block"><small className="block text-[8px] font-bold tracking-[.12em] text-[var(--app-muted)]">RISK PROFILE</small><strong className="block text-[11px]">{profile.label}</strong></span>
            </button>
          </div>
        </header>

        <main className="mx-auto min-h-[calc(100vh-120px)] w-full max-w-[1420px] px-5 py-9 lg:px-[4.5vw] lg:py-12">
          <div key={location.pathname} className="page-enter">{outlet}</div>
        </main>
        <footer className="px-5 pb-6 text-center text-[9px] text-[var(--app-muted)]">Filing-based educational estimates · No live quotes · Not investment advice</footer>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-6 border-t border-[var(--app-border)] bg-[var(--app-surface)]/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => cn('flex flex-col items-center gap-1 py-2 text-[8px] font-medium text-[var(--app-muted)]', isActive && 'text-[var(--app-text)]')}>
            <Icon className="h-[18px] w-[18px]" />{label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
