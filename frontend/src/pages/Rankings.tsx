import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getRankings } from '../lib/api'
import type { RankingsResponse } from '../lib/types'
import { PageHeading, panel } from '../lib/format'
import { useResearch } from '../context/ResearchContext'
import { RiskSelector } from '../components/ResearchControls'
import { cn } from '@/lib/utils'

export default function Rankings() {
  const { risk, setSelectedSymbol } = useResearch()
  const navigate = useNavigate()
  const [data, setData] = useState<RankingsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getRankings(risk)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [risk])

  function openValuation(symbol: string) {
    setSelectedSymbol(symbol)
    navigate('/valuation')
  }

  const top = data?.ranked[0]

  return (
    <>
      <PageHeading
        eyebrow="Rankings"
        title="Find quality companies."
        description={`Screened for a ${data?.profile.short.toLowerCase() ?? 'balanced'} risk profile — filing data only, no live prices.`}
      >
        <RiskSelector />
      </PageHeading>

      {error && (
        <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">{error}</p>
      )}

      {!data ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : (
        <>
          {top && (
            <section className="grid overflow-hidden rounded-[26px] border border-[var(--app-border)] bg-[var(--app-feature)] shadow-[0_18px_50px_var(--app-shadow)] lg:grid-cols-[1.05fr_.95fr]">
              <div className="p-8 sm:p-11">
                <span className="inline-flex rounded-lg border border-[var(--app-border)] bg-[var(--app-surface)] px-3 py-2 text-[9px] font-bold tracking-[.15em] text-[var(--app-muted)]">
                  FUNDAMENTALS ONLY
                </span>
                <h2 className="mt-7 font-serif text-5xl font-semibold leading-[.94] tracking-[-.05em] sm:text-6xl">
                  Quality first.
                  <br />
                  <span className="text-[var(--app-muted-strong)]">Price later.</span>
                </h2>
                <p className="mt-5 max-w-xl text-sm leading-relaxed text-[var(--app-muted)]">
                  Scores compare filing data against your level {risk} thresholds.
                </p>
              </div>
              <div className="flex items-center gap-6 border-t border-[var(--app-border)] bg-[var(--app-surface)]/60 p-8 lg:border-l lg:border-t-0">
                <div
                  className="grid h-32 w-32 shrink-0 place-items-center rounded-full p-2 sm:h-40 sm:w-40"
                  style={{ background: `conic-gradient(var(--app-text) ${top.score}%, var(--app-border) 0)` }}
                >
                  <div className="grid h-full w-full place-items-center rounded-full bg-[var(--app-feature)] text-center">
                    <span>
                      <strong className="block font-serif text-5xl font-normal">{top.score}</strong>
                      <small className="text-[var(--app-muted)]">/ 100</small>
                    </span>
                  </div>
                </div>
                <div>
                  <small className="text-[9px] font-bold tracking-[.13em] text-[var(--app-muted)]">TOP SCREEN</small>
                  <strong className="mt-2 block text-lg">
                    {top.symbol} · {top.shortName}
                  </strong>
                  <p className="mt-2 text-xs leading-relaxed text-[var(--app-muted)]">{top.insight}</p>
                </div>
              </div>
            </section>
          )}

          <section className="mt-10">
            <div className="mb-4 flex items-end justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-text)]">Filing-backed set</p>
                <h2 className="mt-1 text-xl font-bold tracking-tight">Ranked by screen score</h2>
              </div>
              <span className="hidden rounded-lg border border-[var(--app-border)] bg-[var(--app-subtle)] px-3 py-2 text-[10px] font-bold sm:block">
                FY2025 filings
              </span>
            </div>
            <div className={cn(panel, 'overflow-hidden')}>
              {data.ranked.map((c, index) => (
                <article
                  key={c.symbol}
                  className="grid grid-cols-[28px_1fr_64px_70px_36px] items-center gap-4 border-b border-[var(--app-border)] px-4 py-4 last:border-0 sm:px-5"
                >
                  <span className="font-serif text-[var(--app-muted)]">{String(index + 1).padStart(2, '0')}</span>
                  <div className="flex min-w-0 items-center gap-3">
                    <span
                      className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-[11px] font-extrabold text-white"
                      style={{ background: c.color ?? '#555' }}
                    >
                      {c.symbol.slice(0, 2)}
                    </span>
                    <span className="min-w-0">
                      <strong className="block text-sm">{c.symbol}</strong>
                      <small className="block truncate text-[11px] text-[var(--app-muted)]">{c.shortName}</small>
                    </span>
                  </div>
                  <div>
                    <small className="block text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">SCORE</small>
                    <strong className="font-serif text-xl font-normal">{c.score}</strong>
                  </div>
                  <div>
                    <small className="block text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">CHECKS</small>
                    <strong className="font-serif text-xl font-normal">
                      {c.checks.passes}
                      <span className="text-xs text-[var(--app-muted)]">/{c.checks.total}</span>
                    </strong>
                  </div>
                  <button
                    onClick={() => openValuation(c.symbol)}
                    aria-label={`Open ${c.shortName} valuation`}
                    className="grid h-9 w-9 place-items-center rounded-xl border border-[var(--app-border)]"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </article>
              ))}
            </div>
            <p className="mt-3 text-xs text-[var(--app-muted)]">
              Scores adjust to your risk profile and should start — not finish — your research.
            </p>
          </section>
        </>
      )}
    </>
  )
}
