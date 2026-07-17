import { useState } from 'react'
import { ArrowRight, Check, LockKeyhole } from 'lucide-react'
import { RISK_PROFILES } from './engine.js'
import { useResearch } from './ResearchContext'
import { cn } from '@/lib/utils'

export function OnboardingGate({ children }: { children: React.ReactNode }) {
  const { risk, setRisk } = useResearch()
  const [choice, setChoice] = useState(3)
  if (risk) return children

  return (
    <main className="grid min-h-screen bg-[#f4f6f2] lg:grid-cols-[.9fr_1.1fr]">
      <section className="relative flex min-h-[390px] flex-col justify-between overflow-hidden bg-[#112820] px-7 py-8 text-white lg:min-h-screen lg:px-[6vw] lg:py-11">
        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-[#b8d98c] font-serif text-2xl font-bold text-[#10231d]">H</span>
        <div className="relative z-10 my-10">
          <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#b9d3c8]">Halaga · Gabay Research</p>
          <h1 className="mt-4 max-w-2xl font-serif text-5xl font-normal leading-[.95] tracking-[-.05em] sm:text-6xl lg:text-[5.4rem]">Know what fits<br />your comfort zone.</h1>
          <p className="mt-6 max-w-lg text-sm leading-relaxed text-[#aac0b6]">We turn Philippine company filings into beginner-friendly screens—without live quotes, noise, or paid APIs.</p>
        </div>
        <div className="relative z-10 flex max-w-md gap-3 rounded-2xl border border-white/10 bg-white/[.045] p-4 text-xs leading-relaxed text-[#afc3ba]"><span className="font-serif text-[#b8d98c]">01</span>Your risk level adjusts every health threshold. Change it anytime.</div>
        <div className="absolute -bottom-40 -right-28 h-[430px] w-[430px] rounded-full border border-white/[.06] shadow-[0_0_0_55px_rgba(255,255,255,.018),0_0_0_110px_rgba(255,255,255,.012)]" />
      </section>

      <section className="mx-auto flex w-full max-w-2xl flex-col justify-center px-6 py-10 lg:px-12">
        <p className="text-[11px] font-bold uppercase tracking-[.18em] text-[#1c6b57]">Your investing style</p>
        <h2 className="mt-3 text-3xl font-bold tracking-[-.035em] sm:text-4xl">How much uncertainty can you comfortably accept?</h2>
        <p className="mt-3 text-sm leading-relaxed text-[#68736f]">Choose the closest fit. This changes screening thresholds—not your money and not a recommendation.</p>
        <div className="mt-6 grid gap-2">
          {Object.entries(RISK_PROFILES).map(([level, profile]) => {
            const selected = choice === Number(level)
            return (
              <button key={level} onClick={() => setChoice(Number(level))} aria-pressed={selected} className={cn('grid grid-cols-[38px_1fr_26px] items-center gap-3 rounded-2xl border bg-white px-4 py-3 text-left transition hover:-translate-y-px hover:border-[#a8c5b9]', selected ? 'border-[#1c6b57] bg-[#edf6f1] ring-2 ring-[#1c6b57]/10' : 'border-[#dfe5df]')}>
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#e4f1eb] font-serif text-lg text-[#1c6b57]">{level}</span>
                <span><strong className="block text-sm">{profile.label}</strong><small className="mt-0.5 block text-[11px] text-[#68736f]">{profile.tone}</small></span>
                {selected && <span className="grid h-6 w-6 place-items-center rounded-full bg-[#1c6b57] text-white"><Check className="h-3.5 w-3.5" /></span>}
              </button>
            )
          })}
        </div>
        <button onClick={() => setRisk(choice)} className="mt-5 flex h-12 items-center justify-center gap-2 rounded-xl bg-[#1c6b57] text-sm font-bold text-white hover:bg-[#155743]">Build my view <ArrowRight className="h-4 w-4" /></button>
        <p className="mt-3 flex items-center justify-center gap-1.5 text-[10px] text-[#87928d]"><LockKeyhole className="h-3 w-3" /> Saved only in this browser · No account required</p>
      </section>
    </main>
  )
}
