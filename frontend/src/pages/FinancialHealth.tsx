import { useEffect, useState } from 'react'
import { AlertTriangle, Check } from 'lucide-react'
import { getHealth, listResearchCompanies } from '../lib/api'
import type { HealthMetric, HealthResponse, ResearchCompany } from '../lib/types'
import { compactPeso, PageHeading, panel, percent } from '../lib/format'
import { useResearch } from '../context/ResearchContext'
import { CompanySelect, RiskSelector } from '../components/ResearchControls'
import { cn } from '@/lib/utils'

function formatMetric(m: HealthMetric) {
  if (m.value == null || !Number.isFinite(m.value)) return 'Not reported'
  if (m.format === 'percent') return percent(m.value)
  if (m.format === 'multiple') return `${m.value.toFixed(2)}×`
  return compactPeso(m.value)
}

function thresholdText(m: HealthMetric) {
  if (m.direction === 'context') return 'Review in context'
  if (m.direction === 'range' && m.tolerance != null)
    return `${percent((m.target ?? 0) - m.tolerance, 0)}–${percent((m.target ?? 0) + m.tolerance, 0)}`
  if (m.target == null || !Number.isFinite(m.target)) return 'Context only'
  const f = m.format === 'percent' ? percent(m.target) : m.format === 'multiple' ? `${m.target.toFixed(2)}×` : compactPeso(m.target)
  return `${m.direction === 'min' ? 'At least' : 'At most'} ${f}`
}

const statusChip: Record<string, string> = {
  pass: 'bg-[var(--app-subtle)] text-[var(--app-text)]',
  watch: 'bg-[var(--app-subtle)] text-[var(--app-muted-strong)]',
  unavailable: 'bg-[var(--app-subtle)] text-[var(--app-muted)]',
  context: 'bg-[var(--app-subtle)] text-[var(--app-muted)]',
}
const chipLabel: Record<string, string> = {
  pass: 'Clears screen',
  watch: 'Needs a look',
  unavailable: 'Not reported',
  context: 'Context',
}

export default function FinancialHealth() {
  const { risk, selectedSymbol } = useResearch()
  const [companies, setCompanies] = useState<ResearchCompany[]>([])
  const [data, setData] = useState<HealthResponse | null>(null)
  const [tab, setTab] = useState<'pnl' | 'balance'>('pnl')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listResearchCompanies().then(setCompanies).catch(() => {})
  }, [])

  useEffect(() => {
    getHealth(selectedSymbol, risk)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [selectedSymbol, risk])

  const metrics = data ? data[tab] : []
  const available = metrics.filter((m) => m.status !== 'unavailable')
  const passCount = available.filter((m) => m.status === 'pass').length

  return (
    <>
      <PageHeading eyebrow="Financial health" title="Check the fundamentals." description="Each metric against your risk screen — filing data only.">
        <div className="flex flex-wrap items-end gap-3">
          <CompanySelect companies={companies} />
          <RiskSelector />
        </div>
      </PageHeading>

      {error && <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">{error}</p>}

      {!data ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : (
        <>
          <section className={cn(panel, 'grid items-center gap-5 p-6 md:grid-cols-[auto_1fr]')}>
            <div className="flex items-center gap-3 border-b border-[var(--app-border)] pb-5 md:border-b-0 md:border-r md:pb-0 md:pr-7">
              <strong className="font-serif text-5xl font-normal">{passCount}</strong>
              <p className="text-xs text-[var(--app-muted)]">
                <b className="block text-sm text-[var(--app-text)]">of {available.length}</b> available checks cleared
              </p>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[.14em] text-[var(--app-text)]">Your lens</p>
              <h2 className="mt-1 text-lg font-bold">Level {data.risk} · {data.profile.label}</h2>
              <p className="mt-1 text-xs text-[var(--app-muted)]">{data.profile.tone}. Screening guardrails, not universal accounting rules.</p>
            </div>
          </section>

          <section className="mt-8">
            <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div className="inline-grid grid-cols-2 rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-1">
                <button onClick={() => setTab('pnl')} className={cn('rounded-lg px-4 py-2 text-xs font-bold', tab === 'pnl' ? 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm' : 'text-[var(--app-muted)]')}>Profit &amp; loss</button>
                <button onClick={() => setTab('balance')} className={cn('rounded-lg px-4 py-2 text-xs font-bold', tab === 'balance' ? 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm' : 'text-[var(--app-muted)]')}>Balance sheet</button>
              </div>
              {data.company.source && <span className="text-[10px] text-[var(--app-muted)]">Source: {data.company.source.label}</span>}
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {metrics.map((m) => {
                const isPass = m.status === 'pass'
                const progress = m.direction === 'context' ? 70 : Math.max(5, Math.min(100, m.score * 100))
                return (
                  <article key={m.key} className={cn(panel, 'p-5')}>
                    <div className="grid grid-cols-[34px_1fr_auto] items-start gap-3">
                      <span className={cn('grid h-9 w-9 place-items-center rounded-xl', statusChip[m.status])}>
                        {isPass ? <Check className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                      </span>
                      <div>
                        <strong className="text-sm">{m.label}</strong>
                        <p className="mt-1 text-[11px] leading-relaxed text-[var(--app-muted)]">{m.description}</p>
                      </div>
                      <span className={cn('rounded-full px-2 py-1 text-[9px] font-bold', statusChip[m.status])}>{chipLabel[m.status]}</span>
                    </div>
                    <div className="mt-5 grid grid-cols-2 gap-4">
                      <div>
                        <small className="block text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">ACTUAL · FY2025</small>
                        <strong className="mt-1 block font-serif text-xl font-normal">{formatMetric(m)}</strong>
                      </div>
                      <div>
                        <small className="block text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">YOUR LEVEL {data.risk} SCREEN</small>
                        <strong className="mt-1 block font-serif text-base font-normal text-[var(--app-muted-strong)]">{thresholdText(m)}</strong>
                      </div>
                    </div>
                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[var(--app-subtle)]">
                      <span className={cn('block h-full rounded-full', isPass ? 'bg-[var(--app-text)]' : 'bg-[var(--app-muted)]')} style={{ width: `${progress}%` }} />
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        </>
      )}
    </>
  )
}
