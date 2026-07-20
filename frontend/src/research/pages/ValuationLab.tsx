import { AlertTriangle, ExternalLink } from 'lucide-react'
import { INDUSTRIAL_COMPANIES, PHILIPPINE_ASSUMPTIONS } from '../data.js'
import { calculateValuation, SENTIMENTS } from '../engine.js'
import { compactPeso, PageHeading, panel, percent, peso } from '../format'
import { useResearch, type Sentiment } from '../ResearchContext'
import { cn } from '@/lib/utils'

const MODEL_META = [
  ['dcf', 'DCF', 'Values future cash flow today', '5-year forecast + terminal value'],
  ['graham', 'Graham', 'Uses earnings, growth, and bond yields', 'EPS × (8.5 + 2g) × 6.0% / 7.052%'],
  ['multiples', 'Multiples', 'Compares earnings with a peer P/E', 'EPS × adjusted peer P/E'],
  ['ddm', 'Dividend', 'Values expected dividend payments', 'Next dividend / (return − growth)'],
]

const MODEL_GUIDE = [
  ['DCF', 'Estimates today’s value of future business cash flow.'],
  ['Graham', 'Estimates value from earnings, expected growth, and bond yields.'],
  ['Multiples', 'Applies a comparable P/E ratio to company earnings.'],
  ['Dividend', 'Estimates value from expected dividend payments.'],
]

export default function ValuationLab() {
  const { selectedSymbol, setSelectedSymbol, sentiment, setSentiment } = useResearch()
  const company = INDUSTRIAL_COMPANIES.find((item) => item.symbol === selectedSymbol) ?? INDUSTRIAL_COMPANIES[0]
  const valuation = calculateValuation(company, sentiment)
  const dcf = valuation.models.dcf

  return (
    <>
      <PageHeading eyebrow="Valuation" title="Estimate what a share is worth." description="Compare bear, base, and bull assumptions.">
        <label className="grid w-full gap-1 text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)] md:w-64">Company<select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)} className="h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm normal-case tracking-normal text-[var(--app-text)]">{INDUSTRIAL_COMPANIES.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.shortName}</option>)}</select></label>
      </PageHeading>

      <section className={cn(panel, 'grid overflow-hidden lg:grid-cols-[1fr_330px]')}>
        <div className="p-6 sm:p-10">
          <div className="inline-grid grid-cols-3 rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-1">{Object.entries(SENTIMENTS).map(([key, item]) => <button key={key} onClick={() => setSentiment(key as Sentiment)} className={cn('min-w-20 rounded-lg px-4 py-2 text-xs font-bold text-[var(--app-muted)]', sentiment === key && 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm')}>{item.label}</button>)}</div>
          <p className="mt-8 text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-text)]">Blended intrinsic value</p>
          <strong className="mt-2 block font-serif text-6xl font-normal tracking-[-.05em] sm:text-7xl">{peso(valuation.blended)}</strong>
          <p className="mt-1 text-xs text-[var(--app-muted)]">per share · {SENTIMENTS[sentiment].label} case · filing-based estimate</p>
          <div className="mt-9 h-1.5 rounded-full bg-gradient-to-r from-[#d4d4d4] to-[#121212]" />
          <div className="mt-3 flex justify-between font-serif"><span><small className="block font-sans text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">MODEL LOW</small>{peso(valuation.low)}</span><span className="text-right"><small className="block font-sans text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">MODEL HIGH</small>{peso(valuation.high)}</span></div>
        </div>
        <aside className="flex gap-3 border-t border-[var(--app-border)] bg-[var(--app-subtle)] p-7 lg:border-l lg:border-t-0"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[var(--app-subtle)] text-[var(--app-muted-strong)]"><AlertTriangle className="h-4 w-4" /></span><div><strong className="text-sm">No current-price comparison</strong><p className="mt-2 text-xs leading-relaxed text-[var(--app-muted)]">This app does not publish a market quote. Treat the estimate as a model output, not an upside or downside signal.</p></div></aside>
      </section>

      <section className="mt-11"><div className="mb-4"><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-muted)]">Model mix</p><h2 className="mt-1 text-xl font-bold">Four estimates, one blended value</h2></div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{MODEL_META.map(([key, label, explanation, formula]) => { const result = valuation.models[key]; return <article key={key} className={cn(panel, 'p-5', !result && 'opacity-50')}><div className="flex justify-between text-xs font-extrabold text-[var(--app-text)]"><span>{label}</span><small className="text-[9px] text-[var(--app-muted)]">{Math.round((company.valuation.weights[key] ?? 0) * 100)}% weight</small></div><strong className="mt-7 block font-serif text-3xl font-normal">{result ? peso(result.perShare) : 'Not applicable'}</strong><p className="mt-3 text-xs text-[var(--app-muted)]">{explanation}</p><small className="mt-4 block text-[9px] leading-relaxed text-[var(--app-muted)]">{formula}</small></article>})}</div>
      </section>

      <section className="mt-11 grid gap-9 rounded-[21px] border border-[var(--app-border)] bg-[var(--app-feature)] p-7 text-[var(--app-text)] lg:grid-cols-[.85fr_1.15fr] lg:p-9">
        <div><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">Philippine adjustment</p><h2 className="mt-2 text-2xl font-bold">Local rates replace the U.S. AAA yield.</h2><p className="mt-3 text-xs leading-relaxed text-[var(--app-muted)]">{PHILIPPINE_ASSUMPTIONS.note}</p><a className="mt-4 inline-flex items-center gap-2 text-[10px] font-bold text-[var(--app-text)]" href={PHILIPPINE_ASSUMPTIONS.sourceUrl} target="_blank" rel="noreferrer">Official Treasury auction result <ExternalLink className="h-3 w-3" /></a></div>
        <dl className="grid grid-cols-2 gap-2"><Assumption label="Current long-bond proxy" value={percent(PHILIPPINE_ASSUMPTIONS.riskFreeRate, 3)} /><Assumption label="Through-cycle normalizer" value={percent(PHILIPPINE_ASSUMPTIONS.grahamBaselineYield)} /><Assumption label="DCF discount rate" value={percent(dcf.discountRate)} /><Assumption label="Terminal growth" value={percent(dcf.terminalGrowth)} /><Assumption label="Normalized annual FCF" value={compactPeso(dcf.normalizedFcf)} /><Assumption label="Adjusted peer P/E" value={`${valuation.models.multiples.peerPe.toFixed(1)}×`} /></dl>
      </section>
      <p className="mt-4 text-xs leading-relaxed text-[var(--app-muted)]"><strong>Filing source:</strong> {company.source.label}. {company.valuation.note}</p>

      <section className="mt-12 border-t border-[var(--app-border)] pt-8" aria-labelledby="model-guide-title">
        <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-muted)]">Model guide</p>
        <h2 id="model-guide-title" className="mt-1 text-xl font-bold">What each model does</h2>
        <div className="mt-5 grid gap-x-10 gap-y-5 sm:grid-cols-2">
          {MODEL_GUIDE.map(([name, description]) => (
            <div key={name} className="grid grid-cols-[88px_1fr] gap-3 border-t border-[var(--app-border)] pt-4">
              <strong className="text-sm">{name}</strong>
              <p className="text-xs leading-relaxed text-[var(--app-muted)]">{description}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 max-w-3xl text-xs leading-relaxed text-[var(--app-muted)]">Models are estimates, not predictions. Their output changes when the assumptions change.</p>
      </section>
    </>
  )
}

function Assumption({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] p-3"><dt className="text-[9px] text-[var(--app-muted)]">{label}</dt><dd className="mt-1 font-serif text-lg">{value}</dd></div>
}
