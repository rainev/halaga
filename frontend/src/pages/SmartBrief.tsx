import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Sparkles } from 'lucide-react'
import { getBrief, listResearchCompanies } from '../lib/api'
import type { ResearchCompany, SmartBrief as Brief } from '../lib/types'
import { PageHeading, panel } from '../lib/format'
import { useResearch } from '../context/ResearchContext'
import { CompanySelect, RiskSelector, SentimentToggle } from '../components/ResearchControls'
import { cn } from '@/lib/utils'

export default function SmartBrief() {
  const { risk, sentiment, selectedSymbol } = useResearch()
  const [companies, setCompanies] = useState<ResearchCompany[]>([])
  const [data, setData] = useState<Brief | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listResearchCompanies().then(setCompanies).catch(() => {})
  }, [])

  useEffect(() => {
    getBrief(selectedSymbol, risk, sentiment)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [selectedSymbol, risk, sentiment])

  const company = companies.find((c) => c.symbol === selectedSymbol)

  return (
    <>
      <PageHeading eyebrow="Smart Brief" title="The key points, quickly." description="A plain summary built from filing data — runs on our engine, sends nothing to any AI provider.">
        <div className="flex flex-wrap items-end gap-3">
          <CompanySelect companies={companies} />
          <RiskSelector />
        </div>
      </PageHeading>

      {error && <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">{error}</p>}

      {!data ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : (
        <section className={cn(panel, 'overflow-hidden')}>
          <div className="flex items-center justify-between border-b border-[var(--app-border)] px-5 py-4 sm:px-8">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5" />
              <span>
                <strong className="block text-[10px] tracking-[.12em]">LOCAL SMART BRIEF</strong>
                <small className="block text-[9px] text-[var(--app-muted)]">Deterministic · no API fees</small>
              </span>
            </div>
            <SentimentToggle />
          </div>

          <div className="grid items-center gap-4 px-5 py-7 sm:grid-cols-[auto_1fr_auto] sm:px-10">
            <span
              className="grid h-14 w-14 place-items-center rounded-2xl text-sm font-extrabold text-white"
              style={{ background: company?.color ?? '#555' }}
            >
              {data.company.symbol.slice(0, 2)}
            </span>
            <div>
              <p className="text-[10px] text-[var(--app-muted)]">{data.company.subsector ?? data.company.sector}</p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight">{data.company.name}</h2>
            </div>
            <div className="flex items-center gap-2 border-t border-[var(--app-border)] pt-3 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
              <strong className="font-serif text-5xl font-normal">{data.score}</strong>
              <span className="text-[9px] leading-tight text-[var(--app-muted)]">/100<br />screen score</span>
            </div>
          </div>

          <div className="border-y border-[var(--app-border)] bg-[var(--app-feature)] px-5 py-7 sm:px-10">
            <p className="text-[10px] text-[var(--app-muted)]">For your level {data.risk} lens · {sentiment} case</p>
            <h2 className="mt-2 font-serif text-3xl font-normal sm:text-4xl">{data.headline}</h2>
          </div>

          <div className="space-y-4 px-5 py-7 sm:px-10">
            {data.paragraphs.map((p) => (
              <p key={p} className="text-sm leading-[1.8] text-[var(--app-muted-strong)]">{p}</p>
            ))}
          </div>

          <div className="grid gap-6 px-5 pb-8 sm:grid-cols-2 sm:px-10">
            <SignalGroup label="WHAT CLEARS YOUR SCREEN" items={data.passLabels} pass />
            <SignalGroup label="WHAT TO INVESTIGATE" items={data.watchLabels} />
          </div>
        </section>
      )}
    </>
  )
}

function SignalGroup({ label, items, pass = false }: { label: string; items: string[]; pass?: boolean }) {
  return (
    <div>
      <small className="block text-[9px] font-bold tracking-[.1em] text-[var(--app-muted)]">{label}</small>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length ? (
          items.map((item) => (
            <span key={item} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--app-subtle)] px-2.5 py-2 text-[10px] font-bold text-[var(--app-muted-strong)]">
              {pass ? <Check className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
              {item}
            </span>
          ))
        ) : (
          <span className="rounded-lg bg-[var(--app-subtle)] px-2.5 py-2 text-[10px] text-[var(--app-muted)]">No leading signal</span>
        )}
      </div>
    </div>
  )
}
