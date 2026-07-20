import { useState } from 'react'
import { FILING_NEWS, INDUSTRIAL_COMPANIES } from '../data.js'
import { PageHeading, panel } from '../format'
import { cn } from '@/lib/utils'

export default function Briefings() {
  const [filter, setFilter] = useState('ALL')
  const items = FILING_NEWS.filter((item) => filter === 'ALL' || item.symbol === filter)
  return (
    <>
      <PageHeading eyebrow="Briefings" title="See what changed." description="Short notes from company filings.">
        <label className="grid w-full gap-1 text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)] md:w-60">Show<select value={filter} onChange={(event) => setFilter(event.target.value)} className="h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm normal-case tracking-normal text-[var(--app-text)]"><option value="ALL">All briefings</option>{INDUSTRIAL_COMPANIES.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.shortName}</option>)}</select></label>
      </PageHeading>
      <div className="mb-5 flex items-center gap-3 rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-3 text-xs text-[var(--app-muted-strong)]"><span className="h-2 w-2 shrink-0 rounded-full bg-[var(--app-muted)] shadow-[0_0_0_4px_rgba(225,163,62,.14)]" /><p><strong>Demo briefing feed.</strong> These are not live news articles. Production would require a properly licensed news source.</p></div>
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{items.map((item, index) => {
        const company = INDUSTRIAL_COMPANIES.find((entry) => entry.symbol === item.symbol)
        return <article key={item.id} className={cn(panel, 'flex min-h-[270px] flex-col p-6', index === 0 && 'border-[var(--app-border)] bg-[var(--app-feature)] text-[var(--app-text)]')}><div className={cn('flex justify-between text-[9px] text-[var(--app-muted)]', index === 0 && 'text-[var(--app-muted)]')}><span className={cn('rounded-md bg-[var(--app-subtle)] px-2 py-1 font-bold text-[var(--app-text)]', index === 0 && 'bg-[var(--app-surface)] text-[var(--app-text)]')}>{item.tag}</span><span>{item.date}</span></div><h2 className="mt-7 text-xl font-bold leading-snug">{item.title}</h2><p className={cn('mt-3 text-xs leading-relaxed text-[var(--app-muted)]', index === 0 && 'text-[var(--app-muted)]')}>{item.summary}</p><div className={cn('mt-auto flex items-center gap-3 border-t border-[var(--app-border)] pt-5', index === 0 && 'border-[var(--app-border)]')}><span className="grid h-9 w-9 place-items-center rounded-xl text-[10px] font-extrabold text-white" style={{ background: company?.color ?? '#3a3a3a' }}>{item.symbol === 'ALL' ? 'PH' : item.symbol.slice(0, 2)}</span><span><strong className="block text-xs">{item.scope} briefing</strong><small className="text-[9px] text-[var(--app-muted)]">{company?.shortName ?? 'Industrial sector'}</small></span></div></article>
      })}</section>
    </>
  )
}
