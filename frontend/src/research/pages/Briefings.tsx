import { useState } from 'react'
import { FILING_NEWS, INDUSTRIAL_COMPANIES } from '../data.js'
import { PageHeading, panel } from '../format'
import { cn } from '@/lib/utils'

export default function Briefings() {
  const [filter, setFilter] = useState('ALL')
  const items = FILING_NEWS.filter((item) => filter === 'ALL' || item.symbol === filter)
  return (
    <>
      <PageHeading eyebrow="Briefings" title="What changed—and why it matters." description="Plain-language briefs derived from the supplied filings and valuation context.">
        <label className="grid w-full gap-1 text-[9px] font-bold uppercase tracking-[.12em] text-[#68736f] md:w-60">Show<select value={filter} onChange={(event) => setFilter(event.target.value)} className="h-11 rounded-xl border border-[#dfe5df] bg-white px-3 text-sm normal-case tracking-normal text-[#14201d]"><option value="ALL">All briefings</option>{INDUSTRIAL_COMPANIES.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.shortName}</option>)}</select></label>
      </PageHeading>
      <div className="mb-5 flex items-center gap-3 rounded-xl border border-[#ecd8ad] bg-[#fff7e6] p-3 text-xs text-[#785b2c]"><span className="h-2 w-2 shrink-0 rounded-full bg-[#e1a33e] shadow-[0_0_0_4px_rgba(225,163,62,.14)]" /><p><strong>Demo briefing feed.</strong> These are not live news articles. Production would require a properly licensed news source.</p></div>
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{items.map((item, index) => {
        const company = INDUSTRIAL_COMPANIES.find((entry) => entry.symbol === item.symbol)
        return <article key={item.id} className={cn(panel, 'flex min-h-[270px] flex-col p-6', index === 0 && 'border-[#122a23] bg-[#122a23] text-white')}><div className={cn('flex justify-between text-[9px] text-[#89958f]', index === 0 && 'text-[#a9bbb4]')}><span className={cn('rounded-md bg-[#e4f1eb] px-2 py-1 font-bold text-[#1c6b57]', index === 0 && 'bg-[#b8d98c]/10 text-[#b8d98c]')}>{item.tag}</span><span>{item.date}</span></div><h2 className="mt-7 text-xl font-bold leading-snug">{item.title}</h2><p className={cn('mt-3 text-xs leading-relaxed text-[#68736f]', index === 0 && 'text-[#a9bbb4]')}>{item.summary}</p><div className={cn('mt-auto flex items-center gap-3 border-t border-[#dfe5df] pt-5', index === 0 && 'border-white/10')}><span className="grid h-9 w-9 place-items-center rounded-xl text-[10px] font-extrabold text-white" style={{ background: company?.color ?? '#375f53' }}>{item.symbol === 'ALL' ? 'PH' : item.symbol.slice(0, 2)}</span><span><strong className="block text-xs">{item.scope} briefing</strong><small className="text-[9px] text-[#8c9792]">{company?.shortName ?? 'Industrial sector'}</small></span></div></article>
      })}</section>
    </>
  )
}
