import { NavLink, Outlet } from 'react-router-dom'
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

  return (
    <div className="min-h-screen bg-[#f4f6f2] text-[#14201d]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[244px] flex-col bg-[#112820] px-5 py-7 text-white lg:flex">
        <NavLink to="/" className="flex items-center gap-3 no-underline">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#b8d98c] font-serif text-lg font-bold text-[#10231d]">H</span>
          <span className="font-display text-lg font-bold tracking-tight">Halaga<span className="text-[#b8d98c]">.</span><small className="block text-[8px] tracking-[.22em] text-[#9cb0a8]">GABAY RESEARCH</small></span>
        </NavLink>

        <nav className="mt-12 flex flex-1 flex-col gap-1" aria-label="Main navigation">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cn(
                'flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-medium text-[#aec0b8] transition hover:bg-white/[.07] hover:text-white',
                isActive && 'bg-white/[.09] text-white',
              )}
            >
              <Icon className="h-[18px] w-[18px]" /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4">
          <div className="flex items-center gap-2 text-[9px] font-bold tracking-[.15em] text-[#b8d98c]"><span className="h-2 w-2 rounded-full bg-[#8fca75]" />NO-COST MODE</div>
          <strong className="mt-3 block text-sm">Local & private</strong>
          <p className="mt-1 text-[11px] leading-relaxed text-[#91a79d]">No API key or paid market-data feed.</p>
        </div>
        <p className="mt-4 px-1 text-[9px] leading-relaxed text-[#70867d]">Educational mockup<br />Not investment advice</p>
      </aside>

      <div className="min-h-screen pb-20 lg:ml-[244px] lg:pb-0">
        <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-[#dce2dc] bg-[#f4f6f2]/90 px-5 backdrop-blur-xl lg:justify-end lg:px-[4.5vw]">
          <NavLink to="/" className="flex items-center gap-2 font-display font-bold lg:hidden">
            <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[#b8d98c] font-serif text-[#10231d]">H</span> Halaga
          </NavLink>
          <div className="hidden items-center gap-2 text-xs font-medium text-[#68736f] lg:flex"><span className="h-2 w-2 rounded-full border-2 border-[#1c6b57]" /> Filing data · FY2025</div>
          <button onClick={resetRisk} className="ml-5 flex items-center gap-2 rounded-xl border border-[#dfe5df] bg-white p-1.5 pr-3 text-left shadow-sm" title="Change risk profile">
            <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-[#1c6b57] text-xs font-extrabold text-white">{risk}</span>
            <span className="hidden sm:block"><small className="block text-[8px] font-bold tracking-[.12em] text-[#82908a]">RISK PROFILE</small><strong className="block text-[11px]">{profile.label}</strong></span>
          </button>
        </header>

        <main className="mx-auto min-h-[calc(100vh-120px)] w-full max-w-[1420px] px-5 py-9 lg:px-[4.5vw] lg:py-12">
          <Outlet />
        </main>
        <footer className="px-5 pb-6 text-center text-[9px] text-[#8c9692]">Filing-based educational estimates · No live quotes · Not investment advice</footer>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-6 border-t border-[#dfe5df] bg-white/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => cn('flex flex-col items-center gap-1 py-2 text-[8px] font-medium text-[#8a958f]', isActive && 'text-[#1c6b57]')}>
            <Icon className="h-[18px] w-[18px]" />{label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
