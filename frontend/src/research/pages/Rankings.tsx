import { useMemo, useState } from 'react'
import { AlertTriangle, ArrowRight, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import listedCompanies from '../listed-companies.json'
import { INDUSTRIAL_COMPANIES } from '../data.js'
import { getHealthMetrics, RISK_PROFILES, scoreCompany } from '../engine.js'
import { PageHeading, panel } from '../format'
import { useResearch } from '../ResearchContext'
import { cn } from '@/lib/utils'

export default function Rankings() {
  const { risk, setSelectedSymbol } = useResearch()
  const navigate = useNavigate()
  const [scope, setScope] = useState<'industrial' | 'all'>('industrial')
  const [query, setQuery] = useState('')
  const [sector, setSector] = useState('All sectors')
  const activeRisk = risk ?? 3
  const ranked = useMemo(() => [...INDUSTRIAL_COMPANIES]
    .map((company) => ({ company, score: scoreCompany(company, activeRisk) }))
    .sort((a, b) => b.score - a.score), [activeRisk])
  const top = ranked[0]
  const sectors = useMemo(() => ['All sectors', ...Array.from(new Set(listedCompanies.map((company) => company.sector))).sort()], [])
  const directory = useMemo(() => listedCompanies.filter((company) => {
    const needle = query.toLowerCase()
    return (!needle || `${company.symbol} ${company.name}`.toLowerCase().includes(needle)) &&
      (sector === 'All sectors' || company.sector === sector)
  }), [query, sector])

  function openValuation(symbol: string) {
    setSelectedSymbol(symbol)
    navigate('/valuation')
  }

  return (
    <>
      <PageHeading eyebrow="Rankings" title="Fundamentals, ranked—not priced." description={`Tailored for a ${RISK_PROFILES[activeRisk].short.toLowerCase()} investor.`}>
        <div className="grid w-full grid-cols-2 rounded-xl border border-[#dfe5df] bg-[#e9ede8] p-1 md:w-auto">
          <button onClick={() => setScope('industrial')} className={cn('rounded-lg px-3 py-2 text-xs font-bold', scope === 'industrial' && 'bg-white shadow-sm')}>Industrial scored</button>
          <button onClick={() => setScope('all')} className={cn('rounded-lg px-3 py-2 text-xs font-bold text-[#68736f]', scope === 'all' && 'bg-white text-[#14201d] shadow-sm')}>All PSE directory</button>
        </div>
      </PageHeading>

      <section className="grid overflow-hidden rounded-[26px] bg-[#122d25] text-white shadow-[0_18px_50px_rgba(21,42,34,.12)] lg:grid-cols-[1.05fr_.95fr]">
        <div className="p-7 sm:p-10 lg:p-12">
          <span className="inline-flex rounded-lg border border-white/10 px-3 py-2 text-[9px] font-bold tracking-[.15em] text-[#b7ccc3]">YOUR FUNDAMENTALS LENS</span>
          <h2 className="mt-7 font-serif text-5xl font-normal leading-[.94] tracking-[-.05em] sm:text-6xl">Rank quality.<br /><em className="text-[#b8d98c]">Leave price out.</em></h2>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-[#a9beb5]">Scores compare available filing metrics against your level {activeRisk} thresholds. They start your research—they do not tell you to buy or sell.</p>
        </div>
        <div className="flex items-center gap-6 border-t border-white/[.08] bg-white/[.025] p-7 lg:border-l lg:border-t-0 lg:p-10">
          <div className="grid h-32 w-32 shrink-0 place-items-center rounded-full p-2 sm:h-40 sm:w-40" style={{ background: `conic-gradient(#b8d98c ${top.score}%, rgba(255,255,255,.1) 0)` }}><div className="grid h-full w-full place-items-center rounded-full bg-[#143027] text-center"><span><strong className="block font-serif text-5xl font-normal">{top.score}</strong><small className="text-[#9bb1a8]">/ 100</small></span></div></div>
          <div><small className="text-[9px] font-bold tracking-[.13em] text-[#91a99f]">TOP FIT TODAY</small><strong className="mt-2 block text-lg">{top.company.symbol} · {top.company.shortName}</strong><p className="mt-2 text-xs leading-relaxed text-[#aabeb6]">{top.company.insight}</p></div>
        </div>
      </section>

      {scope === 'industrial' ? (
        <section className="mt-11">
          <div className="mb-4 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#1c6b57]">Industrial test set</p><h2 className="mt-1 text-xl font-bold tracking-tight">Four filing-backed companies</h2></div><span className="hidden rounded-lg border border-[#cfe2d8] bg-[#e4f1eb] px-3 py-2 text-[10px] font-bold text-[#1c6b57] sm:block">FY2025 filings</span></div>
          <div className={cn(panel, 'overflow-hidden')}>
            {ranked.map(({ company, score }, index) => {
              const health = getHealthMetrics(company, activeRisk)
              const metrics = [...health.pnl, ...health.balance].filter((metric) => ['pass', 'watch'].includes(metric.status))
              const passes = metrics.filter((metric) => metric.status === 'pass').length
              return (
                <article key={company.symbol} className="grid grid-cols-[28px_1fr_60px_34px] items-center gap-3 border-b border-[#edf0ed] px-4 py-4 last:border-0 sm:grid-cols-[38px_1.2fr_90px_100px_80px_36px] sm:gap-5">
                  <span className="font-serif text-[#98a29e]">{String(index + 1).padStart(2, '0')}</span>
                  <div className="flex min-w-0 items-center gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-[11px] font-extrabold text-white" style={{ background: company.color }}>{company.symbol.slice(0, 2)}</span><span className="min-w-0"><strong className="block text-sm">{company.symbol}</strong><small className="block truncate text-[11px] text-[#68736f]">{company.shortName}</small></span></div>
                  <div><small className="block text-[8px] font-bold tracking-[.1em] text-[#87938e]">SCORE</small><strong className="font-serif text-xl font-normal">{score}</strong></div>
                  <div className="hidden sm:block"><small className="block text-[8px] font-bold tracking-[.1em] text-[#87938e]">CHECKS</small><strong className="font-serif text-xl font-normal">{passes}<span className="text-xs text-[#96a09c]">/{metrics.length}</span></strong></div>
                  <span className={cn('hidden w-fit rounded-full px-2.5 py-1.5 text-[9px] font-extrabold sm:inline-flex', score >= 78 ? 'bg-[#e4f4eb] text-[#176348]' : score >= 65 ? 'bg-[#f5f0d7] text-[#6d5b16]' : 'bg-[#fff3da] text-[#9a5912]')}>{score >= 78 ? 'Strong' : score >= 65 ? 'Mixed' : 'Watch'}</span>
                  <button onClick={() => openValuation(company.symbol)} aria-label={`Open ${company.shortName} valuation`} className="grid h-9 w-9 place-items-center rounded-xl border border-[#dfe5df] text-[#1c6b57]"><ArrowRight className="h-4 w-4" /></button>
                </article>
              )
            })}
          </div>
          <div className="mt-4 flex gap-3 rounded-xl bg-[#e9eeea] p-4 text-xs leading-relaxed text-[#5e6965]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#1c6b57]" /><p><strong>How this works:</strong> Missing line items remain neutral, not zero. Scores adjust to your risk profile and should start—not finish—your research.</p></div>
        </section>
      ) : (
        <section className="mt-11">
          <div className="flex gap-3 rounded-xl border border-[#dfe5df] bg-[#e9eeea] p-4 text-xs text-[#5e6965]"><AlertTriangle className="h-4 w-4 shrink-0 text-[#1c6b57]" /><p><strong>Directory view only.</strong> Per the current scope, only the four Industrial companies are scored. The rest are listed without quotes or invented fundamentals.</p></div>
          <div className="my-4 grid gap-2 sm:grid-cols-[1fr_220px]">
            <label className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#87938e]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company or ticker" className="h-11 w-full rounded-xl border border-[#dfe5df] bg-white pl-10 pr-3 text-sm outline-none focus:ring-2 focus:ring-[#1c6b57]/20" /></label>
            <select value={sector} onChange={(event) => setSector(event.target.value)} className="h-11 rounded-xl border border-[#dfe5df] bg-white px-3 text-sm">{sectors.map((item) => <option key={item}>{item}</option>)}</select>
          </div>
          <div className={cn(panel, 'overflow-x-auto')}><table className="w-full min-w-[700px] text-left text-xs"><thead className="bg-[#f7f8f6] text-[9px] uppercase tracking-[.1em] text-[#7c8883]"><tr><th className="p-4">Ticker</th><th>Company</th><th>Sector</th><th>Subsector</th><th>Status</th></tr></thead><tbody>{directory.slice(0, 80).map((company) => { const scored = INDUSTRIAL_COMPANIES.some((item) => item.symbol === company.symbol); return <tr key={`${company.symbol}-${company.name}`} className="border-t border-[#edf0ed]"><td className="p-4 font-bold">{company.symbol}</td><td>{company.name}</td><td>{company.sector}</td><td>{company.subsector}</td><td><span className={cn('rounded-full px-2 py-1 text-[9px] font-bold', scored ? 'bg-[#e4f4eb] text-[#176348]' : 'bg-[#edf0ed] text-[#69736f]')}>{scored ? 'Scored' : 'Queued'}</span></td></tr>})}</tbody></table></div>
          <p className="mt-3 text-xs text-[#68736f]">{directory.length} companies match · showing up to 80</p>
        </section>
      )}
    </>
  )
}
