import { RISK_LABELS, useResearch } from '../context/ResearchContext'
import type { ResearchCompany, Sentiment } from '../lib/types'
import { cn } from '@/lib/utils'

const seg = 'rounded-lg px-3 py-2 text-xs font-bold transition-colors'
const segOff = 'text-[var(--app-muted)] hover:text-[var(--app-text)]'
const segOn = 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm'
const wrap = 'inline-grid rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-1'

/** 1–5 risk profile, shared + persisted. */
export function RiskSelector() {
  const { risk, setRisk } = useResearch()
  return (
    <label className="grid gap-1.5">
      <span className="text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)]">
        Risk profile · {RISK_LABELS[risk]}
      </span>
      <div className={cn(wrap, 'grid-cols-5')}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => setRisk(n)} className={cn(seg, risk === n ? segOn : segOff)}>
            {n}
          </button>
        ))}
      </div>
    </label>
  )
}

/** bear / base / bull valuation scenario. */
export function SentimentToggle() {
  const { sentiment, setSentiment } = useResearch()
  const options: Sentiment[] = ['bear', 'base', 'bull']
  return (
    <div className={cn(wrap, 'grid-cols-3')}>
      {options.map((s) => (
        <button
          key={s}
          onClick={() => setSentiment(s)}
          className={cn(seg, 'min-w-16 capitalize', sentiment === s ? segOn : segOff)}
        >
          {s}
        </button>
      ))}
    </div>
  )
}

/** Company picker for the health/valuation/brief pages. */
export function CompanySelect({ companies }: { companies: ResearchCompany[] }) {
  const { selectedSymbol, setSelectedSymbol } = useResearch()
  return (
    <label className="grid w-full gap-1.5 md:w-64">
      <span className="text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)]">
        Company
      </span>
      <select
        value={selectedSymbol}
        onChange={(e) => setSelectedSymbol(e.target.value)}
        className="h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)]"
      >
        {companies.map((c) => (
          <option key={c.symbol} value={c.symbol}>
            {c.symbol} · {c.shortName}
          </option>
        ))}
      </select>
    </label>
  )
}
