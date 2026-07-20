import { useState } from 'react'
import { AlertTriangle, Check, Copy, Sparkles } from 'lucide-react'
import { INDUSTRIAL_COMPANIES } from '../data.js'
import { buildSmartBrief, RISK_PROFILES, SENTIMENTS } from '../engine.js'
import { PageHeading, panel } from '../format'
import { useResearch, type Sentiment } from '../ResearchContext'
import { cn } from '@/lib/utils'

export default function SmartBrief() {
  const { risk, selectedSymbol, setSelectedSymbol, sentiment, setSentiment, lots } = useResearch()
  const [copied, setCopied] = useState(false)
  const activeRisk = risk ?? 3
  const company = INDUSTRIAL_COMPANIES.find((item) => item.symbol === selectedSymbol) ?? INDUSTRIAL_COMPANIES[0]
  const brief = buildSmartBrief(company, activeRisk, sentiment, lots)

  async function copy() {
    const text = `${company.name}\n${brief.headline}\n\n${brief.paragraphs.join('\n\n')}\n\nEducational filing-based estimate; not investment advice.`
    await navigator.clipboard.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <>
      <PageHeading eyebrow="Smart Brief" title="The key points, quickly." description="A plain summary built from filing data.">
        <label className="grid w-full gap-1 text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)] md:w-64">Company<select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)} className="h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm normal-case tracking-normal text-[var(--app-text)]">{INDUSTRIAL_COMPANIES.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.shortName}</option>)}</select></label>
      </PageHeading>
      <section className={cn(panel, 'overflow-hidden')}>
        <div className="flex items-center justify-between border-b border-[var(--app-border)] px-5 py-4 sm:px-8"><div className="flex items-center gap-2 text-[var(--app-text)]"><Sparkles className="h-5 w-5" /><span><strong className="block text-[10px] tracking-[.12em]">LOCAL SMART BRIEF</strong><small className="block text-[9px] text-[var(--app-muted)]">No API fees · Runs in your browser</small></span></div><button onClick={copy} className="flex h-9 items-center gap-2 rounded-xl border border-[var(--app-border)] px-3 text-xs font-bold"><Copy className="h-4 w-4" /><span className="hidden sm:inline">{copied ? 'Copied' : 'Copy summary'}</span></button></div>
        <div className="grid items-center gap-4 px-5 py-7 sm:grid-cols-[auto_1fr_auto] sm:px-10"><span className="grid h-14 w-14 place-items-center rounded-2xl text-sm font-extrabold text-white" style={{ background: company.color }}>{company.symbol.slice(0, 2)}</span><div><p className="text-[10px] text-[var(--app-muted)]">{company.subsector}</p><h2 className="mt-1 text-2xl font-bold tracking-tight">{company.name}</h2></div><div className="flex items-center gap-2 border-t border-[var(--app-border)] pt-3 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0"><strong className="font-serif text-5xl font-normal">{brief.score}</strong><span className="text-[9px] leading-tight text-[var(--app-muted)]">/100<br />screen score</span></div></div>
        <div className="relative bg-[var(--app-text)] px-5 py-7 text-[var(--app-bg)] sm:px-10"><span className="absolute left-5 top-0 h-[3px] w-10 bg-[var(--app-bg)] sm:left-10" /><p className="text-[10px] text-[var(--app-muted)]">For your level {activeRisk} · {RISK_PROFILES[activeRisk].label}</p><h2 className="mt-2 font-serif text-3xl font-normal sm:text-4xl">{brief.headline}</h2></div>
        <div className="space-y-4 px-5 py-7 sm:px-10">{brief.paragraphs.map((paragraph) => <p key={paragraph} className="text-sm leading-[1.8] text-[var(--app-muted-strong)]">{paragraph}</p>)}</div>
        <div className="grid gap-6 px-5 pb-7 sm:grid-cols-2 sm:px-10"><SignalGroup label="WHAT CLEARS YOUR SCREEN" items={brief.passLabels} pass /><SignalGroup label="WHAT TO INVESTIGATE" items={brief.watchLabels} /></div>
        <div className="mx-5 mb-7 flex items-center justify-center rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-1 sm:mx-10"><span className="hidden px-3 text-[10px] text-[var(--app-muted)] sm:inline">Valuation lens:</span>{Object.entries(SENTIMENTS).map(([key, item]) => <button key={key} onClick={() => setSentiment(key as Sentiment)} className={cn('rounded-lg px-4 py-2 text-xs font-bold text-[var(--app-muted)]', sentiment === key && 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm')}>{item.label}</button>)}</div>
      </section>
      <div className="mx-auto mt-4 flex max-w-3xl gap-3 rounded-xl bg-[var(--app-subtle)] p-4 text-xs leading-relaxed text-[var(--app-muted)]"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[var(--app-text)]" /><p><strong>Why this has no extra cost:</strong> The brief selects facts and sentences from deterministic rules in the app. It sends nothing to OpenAI or another AI provider and makes no hidden recommendation.</p></div>
    </>
  )
}

function SignalGroup({ label, items, pass = false }: { label: string; items: string[]; pass?: boolean }) {
  return <div><small className="block text-[9px] font-bold tracking-[.1em] text-[var(--app-muted)]">{label}</small><div className="mt-3 flex flex-wrap gap-2">{items.length ? items.map((item) => <span key={item} className={cn('inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[10px] font-bold', pass ? 'bg-[var(--app-subtle)] text-[var(--app-text)]' : 'bg-[var(--app-subtle)] text-[var(--app-muted-strong)]')}>{pass ? <Check className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}{item}</span>) : <span className="rounded-lg bg-[var(--app-subtle)] px-2.5 py-2 text-[10px] text-[var(--app-muted)]">No leading signal available</span>}</div></div>
}
