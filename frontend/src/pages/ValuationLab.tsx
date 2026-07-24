import { useEffect, useState } from 'react'
import { AlertTriangle, ExternalLink } from 'lucide-react'
import { getValuation, listResearchCompanies } from '../lib/api'
import type { ResearchCompany, ResearchValuation } from '../lib/types'
import { compactPeso, PageHeading, panel, percent, peso } from '../lib/format'
import { useResearch } from '../context/ResearchContext'
import { CompanySelect, SentimentToggle } from '../components/ResearchControls'
import { cn } from '@/lib/utils'

const MODEL_META: [string, string, string, string][] = [
  ['dcf', 'DCF', 'Values future cash flow today', '5-year forecast + terminal value'],
  ['graham', 'Graham', 'Earnings, growth, and bond yields', 'EPS × (8.5 + 2g) × 6.0% / 7.052%'],
  ['multiples', 'Multiples', 'Earnings vs a peer P/E', 'EPS × adjusted peer P/E'],
  ['ddm', 'Dividend', 'Values expected dividends', 'Next dividend / (return − growth)'],
]

export default function ValuationLab() {
  const { selectedSymbol, sentiment } = useResearch()
  const [companies, setCompanies] = useState<ResearchCompany[]>([])
  const [data, setData] = useState<ResearchValuation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listResearchCompanies().then(setCompanies).catch(() => {})
  }, [])

  useEffect(() => {
    getValuation(selectedSymbol, sentiment)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [selectedSymbol, sentiment])

  return (
    <>
      <PageHeading eyebrow="Valuation" title="Estimate what a share is worth." description="Compare bear, base, and bull assumptions — an intrinsic-value estimate, not a market quote.">
        <CompanySelect companies={companies} />
      </PageHeading>

      {error && <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">{error}</p>}

      {!data ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : (
        <>
          <section className={cn(panel, 'grid overflow-hidden lg:grid-cols-[1fr_320px]')}>
            <div className="p-6 sm:p-10">
              <SentimentToggle />
              <p className="mt-8 text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-text)]">Blended intrinsic value</p>
              <strong className="mt-2 block font-serif text-6xl font-normal tracking-[-.05em] sm:text-7xl">{peso(data.blended)}</strong>
              <p className="mt-1 text-xs text-[var(--app-muted)]">
                per share · {sentiment} case · {data.company.symbol} filing-based estimate
              </p>
              <div className="mt-9 h-1.5 rounded-full bg-gradient-to-r from-[var(--app-border)] to-[var(--app-text)]" />
              <div className="mt-3 flex justify-between font-serif">
                <span>
                  <small className="block font-sans text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">MODEL LOW</small>
                  {peso(data.low)}
                </span>
                <span className="text-right">
                  <small className="block font-sans text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">MODEL HIGH</small>
                  {peso(data.high)}
                </span>
              </div>
            </div>
            <aside className="flex gap-3 border-t border-[var(--app-border)] bg-[var(--app-subtle)] p-7 lg:border-l lg:border-t-0">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-[var(--app-muted-strong)]">
                <AlertTriangle className="h-4 w-4" />
              </span>
              <div>
                <strong className="text-sm">No current-price comparison</strong>
                <p className="mt-2 text-xs leading-relaxed text-[var(--app-muted)]">
                  FinSight does not publish a market quote. Treat this as a model output, not an upside or downside signal.
                </p>
              </div>
            </aside>
          </section>

          <section className="mt-10">
            <div className="mb-4">
              <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-muted)]">Model mix</p>
              <h2 className="mt-1 text-xl font-bold">Four estimates, one blended value</h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {MODEL_META.map(([key, label, explanation, formula]) => {
                const result = data.models[key as keyof typeof data.models]
                return (
                  <article key={key} className={cn(panel, 'p-5', !result && 'opacity-50')}>
                    <div className="flex justify-between text-xs font-extrabold">
                      <span>{label}</span>
                      <small className="text-[9px] text-[var(--app-muted)]">{Math.round((data.weights[key] ?? 0) * 100)}% weight</small>
                    </div>
                    <strong className="mt-7 block font-serif text-3xl font-normal">{result ? peso(result.perShare) : 'N/A'}</strong>
                    <p className="mt-3 text-xs text-[var(--app-muted)]">{explanation}</p>
                    <small className="mt-4 block text-[9px] leading-relaxed text-[var(--app-muted)]">{formula}</small>
                  </article>
                )
              })}
            </div>
          </section>

          <section className="mt-10 grid gap-8 rounded-[21px] border border-[var(--app-border)] bg-[var(--app-feature)] p-7 lg:grid-cols-[.85fr_1.15fr] lg:p-9">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">Philippine adjustment</p>
              <h2 className="mt-2 text-2xl font-bold">Local rates replace the U.S. AAA yield.</h2>
              <p className="mt-3 text-xs leading-relaxed text-[var(--app-muted)]">{data.assumptions.note}</p>
              <a className="mt-4 inline-flex items-center gap-2 text-[10px] font-bold" href={data.assumptions.sourceUrl} target="_blank" rel="noreferrer">
                Official Treasury auction result <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <dl className="grid grid-cols-2 gap-2">
              <Assumption label="Current long-bond proxy" value={percent(data.assumptions.riskFreeRate, 3)} />
              <Assumption label="Through-cycle normalizer" value={percent(data.assumptions.grahamBaselineYield)} />
              <Assumption label="DCF discount rate" value={percent(data.models.dcf.discountRate ?? null)} />
              <Assumption label="Terminal growth" value={percent(data.models.dcf.terminalGrowth ?? null)} />
              <Assumption label="Normalized annual FCF" value={compactPeso(data.models.dcf.normalizedFcf ?? null)} />
              <Assumption label="Adjusted peer P/E" value={`${(data.models.multiples.peerPe ?? 0).toFixed(1)}×`} />
            </dl>
          </section>
          {data.valuationNote && (
            <p className="mt-4 text-xs leading-relaxed text-[var(--app-muted)]">
              <strong>Filing source:</strong> {data.company.source?.label}. {data.valuationNote}
            </p>
          )}
        </>
      )}
    </>
  )
}

function Assumption({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] p-3">
      <dt className="text-[9px] text-[var(--app-muted)]">{label}</dt>
      <dd className="mt-1 font-serif text-lg">{value}</dd>
    </div>
  )
}
