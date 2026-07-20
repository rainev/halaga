import { useState } from 'react'
import { ArrowRight, Check, LockKeyhole } from 'lucide-react'
import { RISK_PROFILES } from './engine.js'
import { useResearch } from './ResearchContext'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '../components/ThemeToggle'

export function OnboardingGate({ children }: { children: React.ReactNode }) {
  const { risk, setRisk } = useResearch()
  const [choice, setChoice] = useState(3)
  if (risk) return children

  return (
    <main className="grid min-h-screen bg-[var(--app-bg)] text-[var(--app-text)] lg:grid-cols-[.9fr_1.1fr]">
      <ThemeToggle className="fixed right-5 top-5 z-50" />
      <section className="relative flex min-h-[390px] flex-col justify-between overflow-hidden bg-[var(--app-text)] px-7 py-8 text-[var(--app-bg)] lg:min-h-screen lg:px-[6vw] lg:py-11">
        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-[var(--app-bg)] font-serif text-2xl font-bold text-[var(--app-text)]">F</span>
        <div className="relative z-10 my-10">
          <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[var(--app-muted)]">FinSight</p>
          <h1 className="mt-4 max-w-2xl font-serif text-5xl font-semibold leading-[.95] tracking-[-.055em] sm:text-6xl lg:text-[5.4rem]">Understand value.<br />Invest with context.</h1>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-[var(--app-muted)]">Clear research from Philippine company filings.</p>
        </div>
        <div className="relative z-10 flex max-w-md gap-3 rounded-2xl border border-white/10 bg-[var(--app-surface)]/[.045] p-4 text-xs leading-relaxed text-[var(--app-muted)]"><span className="font-serif text-[var(--app-bg)]">01</span>Your risk level sets the screening thresholds.</div>
        <div className="absolute -bottom-40 -right-28 h-[430px] w-[430px] rounded-full border border-white/[.06] shadow-[0_0_0_55px_rgba(255,255,255,.018),0_0_0_110px_rgba(255,255,255,.012)]" />
      </section>

      <section className="mx-auto flex w-full max-w-2xl flex-col justify-center px-6 py-10 lg:px-12">
        <p className="text-[11px] font-bold uppercase tracking-[.18em] text-[var(--app-muted)]">Set your view</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-[-.035em] sm:text-4xl">How much risk feels right?</h2>
        <p className="mt-3 text-sm leading-relaxed text-[var(--app-muted)]">This only adjusts the app’s screens.</p>
        <div className="mt-6 grid gap-2">
          {Object.entries(RISK_PROFILES).map(([level, profile]) => {
            const selected = choice === Number(level)
            return (
              <button key={level} onClick={() => setChoice(Number(level))} aria-pressed={selected} className={cn('grid grid-cols-[38px_1fr_26px] items-center gap-3 rounded-2xl border bg-[var(--app-surface)] px-4 py-3 text-left hover:-translate-y-0.5 hover:border-[var(--app-text)] hover:shadow-lg', selected ? 'border-[var(--app-text)] bg-[var(--app-subtle)] ring-2 ring-[var(--app-text)]/10' : 'border-[var(--app-border)]')}>
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--app-subtle)] font-serif text-lg text-[var(--app-text)]">{level}</span>
                <span><strong className="block text-sm">{profile.label}</strong><small className="mt-0.5 block text-[11px] text-[var(--app-muted)]">{profile.tone}</small></span>
                {selected && <span className="grid h-6 w-6 place-items-center rounded-full bg-[var(--app-text)] text-[var(--app-bg)]"><Check className="h-3.5 w-3.5" /></span>}
              </button>
            )
          })}
        </div>
        <button onClick={() => setRisk(choice)} className="mt-5 flex h-12 items-center justify-center gap-2 rounded-xl bg-[var(--app-text)] text-sm font-bold text-[var(--app-bg)] shadow-[0_10px_30px_rgba(18,18,18,.18)] hover:-translate-y-0.5 hover:opacity-90 hover:shadow-[0_14px_38px_rgba(18,18,18,.24)]">Continue <ArrowRight className="h-4 w-4" /></button>
        <p className="mt-3 flex items-center justify-center gap-1.5 text-[10px] text-[var(--app-muted)]"><LockKeyhole className="h-3 w-3" /> Saved only in this browser · No account required</p>
      </section>
    </main>
  )
}
