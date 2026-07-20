import { useState } from 'react'
import { AlertTriangle, Check } from 'lucide-react'
import { INDUSTRIAL_COMPANIES } from '../data.js'
import { getHealthMetrics, RISK_PROFILES } from '../engine.js'
import { compactPeso, PageHeading, panel, percent } from '../format'
import { useResearch } from '../ResearchContext'
import { cn } from '@/lib/utils'

export default function FinancialHealth() {
  const { risk, selectedSymbol, setSelectedSymbol, resetRisk } = useResearch()
  const [tab, setTab] = useState<'pnl' | 'balance'>('pnl')
  const activeRisk = risk ?? 3
  const company = INDUSTRIAL_COMPANIES.find((item) => item.symbol === selectedSymbol) ?? INDUSTRIAL_COMPANIES[0]
  const health = getHealthMetrics(company, activeRisk)
  const metrics = health[tab]
  const available = metrics.filter((metric) => metric.status !== 'unavailable')
  const passCount = available.filter((metric) => metric.status === 'pass').length

  return (
    <>
      <PageHeading eyebrow="Financial health" title="Check the fundamentals." description="See each metric against your risk screen.">
        <label className="grid w-full gap-1 text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)] md:w-64">Company<select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)} className="h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm normal-case tracking-normal text-[var(--app-text)]">{INDUSTRIAL_COMPANIES.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.shortName}</option>)}</select></label>
      </PageHeading>

      <section className={cn(panel, 'grid items-center gap-5 p-6 md:grid-cols-[auto_1fr_auto]')}>
        <div className="flex items-center gap-3 border-b border-[var(--app-border)] pb-5 md:border-b-0 md:border-r md:pb-0 md:pr-7"><strong className="font-serif text-5xl font-normal">{passCount}</strong><p className="text-xs text-[var(--app-muted)]"><b className="block text-sm text-[var(--app-text)]">of {available.length}</b> available checks cleared</p></div>
        <div><p className="text-[9px] font-bold uppercase tracking-[.14em] text-[var(--app-text)]">Your lens</p><h2 className="mt-1 text-lg font-bold">Level {activeRisk} · {RISK_PROFILES[activeRisk].label}</h2><p className="mt-1 text-xs text-[var(--app-muted)]">{RISK_PROFILES[activeRisk].tone}. These are screening guardrails, not universal accounting rules.</p></div>
        <button onClick={resetRisk} className="h-10 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-4 text-xs font-bold">Adjust profile</button>
      </section>

      <section className="mt-10">
        <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div className="inline-grid grid-cols-2 rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-1"><button onClick={() => setTab('pnl')} className={cn('rounded-lg px-4 py-2 text-xs font-bold text-[var(--app-muted)]', tab === 'pnl' && 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm')}>Profit & loss</button><button onClick={() => setTab('balance')} className={cn('rounded-lg px-4 py-2 text-xs font-bold text-[var(--app-muted)]', tab === 'balance' && 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm')}>Balance sheet</button></div><span className="text-[10px] text-[var(--app-muted)]">Source: {company.source.label}</span></div>
        <div className="grid gap-3 md:grid-cols-2">{metrics.map((metric) => {
          const progress = metric.direction === 'context' ? 70 : Math.max(5, Math.min(100, metric.score * 100))
          const isPass = metric.status === 'pass'
          return <article key={metric.key} className={cn(panel, 'p-5')}><div className="grid grid-cols-[34px_1fr_auto] items-start gap-3"><span className={cn('grid h-9 w-9 place-items-center rounded-xl', isPass ? 'bg-[var(--app-subtle)] text-[var(--app-text)]' : metric.status === 'watch' ? 'bg-[var(--app-subtle)] text-[var(--app-muted-strong)]' : 'bg-[var(--app-subtle)] text-[var(--app-muted)]')}>{isPass ? <Check className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}</span><div><strong className="text-sm">{metric.label}</strong><p className="mt-1 text-[11px] leading-relaxed text-[var(--app-muted)]">{metric.description}</p></div><span className={cn('rounded-full px-2 py-1 text-[9px] font-bold', isPass ? 'bg-[var(--app-subtle)] text-[var(--app-text)]' : metric.status === 'watch' ? 'bg-[var(--app-subtle)] text-[var(--app-muted-strong)]' : 'bg-[var(--app-subtle)] text-[var(--app-muted)]')}>{isPass ? 'Clears screen' : metric.status === 'watch' ? 'Needs a look' : metric.status === 'context' ? 'Context' : 'Not reported'}</span></div><div className="mt-6 grid grid-cols-2 gap-4"><MetricValue label="ACTUAL · FY2025" value={formatMetric(metric)} /><MetricValue label={`YOUR LEVEL ${activeRisk} SCREEN`} value={thresholdText(metric)} compact /></div><div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[var(--app-subtle)]"><span className={cn('block h-full rounded-full', isPass ? 'bg-[var(--app-text)]' : metric.status === 'watch' ? 'bg-[var(--app-muted)]' : 'bg-[var(--app-muted)]')} style={{ width: `${progress}%` }} /></div></article>
        })}</div>
        <div className="mt-4 flex gap-3 rounded-xl bg-[var(--app-subtle)] p-4 text-xs leading-relaxed text-[var(--app-muted)]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--app-text)]" /><p><strong>Interpret carefully:</strong> Issuers group line items differently. “Not reported” remains neutral, while treasury stock is context—not an automatic pass or fail.</p></div>
      </section>
    </>
  )
}

function MetricValue({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) {
  return <div><small className="block text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">{label}</small><strong className={cn('mt-1 block font-serif font-normal', compact ? 'text-base text-[var(--app-muted-strong)]' : 'text-xl')}>{value}</strong></div>
}

function formatMetric(metric: { value: number | null; format: string }) {
  if (!Number.isFinite(metric.value)) return 'Not reported'
  if (metric.format === 'percent') return percent(metric.value)
  if (metric.format === 'multiple') return `${metric.value?.toFixed(2)}×`
  if (metric.format === 'currency') return compactPeso(metric.value)
  return String(metric.value)
}

function thresholdText(metric: { target: number | null; direction: string; tolerance?: number; format: string }) {
  if (metric.direction === 'context') return 'Review in context'
  if (metric.direction === 'range' && Number.isFinite(metric.tolerance)) return `${percent((metric.target ?? 0) - (metric.tolerance ?? 0), 0)}–${percent((metric.target ?? 0) + (metric.tolerance ?? 0), 0)}`
  if (!Number.isFinite(metric.target)) return 'Context only'
  const formatted = metric.format === 'percent' ? percent(metric.target) : metric.format === 'multiple' ? `${metric.target?.toFixed(2)}×` : compactPeso(metric.target)
  return `${metric.direction === 'min' ? 'At least' : 'At most'} ${formatted}`
}
