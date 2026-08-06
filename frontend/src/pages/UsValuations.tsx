import { useEffect, useState } from 'react'
import { AlertTriangle, ExternalLink } from 'lucide-react'
import { getUsValuation } from '@/lib/api'
import type { UsModelResult, UsValuation } from '@/lib/types'
import { PageHeading, panel, percent } from '@/lib/format'
import { cn } from '@/lib/utils'

// The precomputed, reviewed filing-only set served by the backend. There is no
// list endpoint yet, so the picker is the known published universe.
const US_TICKERS = [
  'AAPL', 'MSFT', 'ANET', 'ADSK', 'CRM', 'DELL',
  'FTNT', 'NTAP', 'PANW', 'STX', 'WDC', 'NOW',
]

const usd = (value: number | null | undefined, digits = 2) =>
  Number.isFinite(value)
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(value as number)
    : '—'

const humanize = (value: string | undefined) =>
  (value ?? '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

function StateBadge({ state }: { state: string | null | undefined }) {
  const tone =
    state === 'pass'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500'
      : state === 'withheld'
        ? 'border-red-500/40 bg-red-500/10 text-red-500'
        : 'border-amber-500/40 bg-amber-500/10 text-amber-500'
  return (
    <span className={cn('rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[.12em]', tone)}>
      {humanize(state ?? 'review required')}
    </span>
  )
}

function ModelCard({ label, primary, result }: { label: string; primary?: boolean; result: UsModelResult | undefined }) {
  if (!result) return null
  return (
    <div className={cn(panel, 'p-5')}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-[.16em] text-[var(--app-muted)]">
          {label}
          {primary && <span className="ml-2 text-[var(--app-text)]">· primary</span>}
        </p>
        <StateBadge state={result.publication_state} />
      </div>
      <p className="mt-3 font-serif text-3xl font-semibold tracking-[-.03em]">
        {usd(result.intrinsic_value_per_share)}
      </p>
      <p className="mt-1 text-xs text-[var(--app-muted)]">intrinsic value / share</p>
      {result.warnings?.length > 0 && (
        <ul className="mt-3 space-y-1">
          {result.warnings.map((w, i) => (
            <li key={i} className="flex gap-1.5 text-[11px] leading-snug text-amber-500">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-[.14em] text-[var(--app-muted)]">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  )
}

export default function UsValuations() {
  const [ticker, setTicker] = useState('AAPL')
  const [data, setData] = useState<UsValuation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setLoading(true)
    setError(null)
    getUsValuation(ticker)
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
  }, [ticker])

  const pa = data?.public_assumptions
  const segments = pa?.segment_assumptions ? Object.values(pa.segment_assumptions) : []

  return (
    <div>
      <PageHeading
        eyebrow="Filing-only · U.S. SEC"
        title="US Valuations"
        description="Reviewed, price-free intrinsic-value ranges derived from SEC filings — FCFF DCF with an EPV cross-check, under governed forecast and discount policy. No market price, no buy/hold/sell call."
      />

      <div className="mb-7 flex flex-wrap gap-2">
        {US_TICKERS.map((t) => (
          <button
            key={t}
            onClick={() => setTicker(t)}
            className={cn(
              'rounded-lg border px-3 py-1.5 text-xs font-bold tracking-wide',
              t === ticker
                ? 'border-[var(--app-text)] bg-[var(--app-text)] text-[var(--app-bg)]'
                : 'border-[var(--app-border)] text-[var(--app-muted)] hover:bg-[var(--app-subtle)] hover:text-[var(--app-text)]',
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-[var(--app-muted)]">Loading {ticker}…</p>}

      {error && !loading && (
        <div className={cn(panel, 'flex items-center gap-2 p-5 text-sm text-red-500')}>
          <AlertTriangle className="h-4 w-4" /> Could not load {ticker}: {error}
        </div>
      )}

      {data && !loading && !error && (
        <div className="space-y-6">
          {/* Issuer + headline range */}
          <div className={cn(panel, 'p-6')}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-semibold tracking-[-.02em]">{data.issuer.issuer_name}</h2>
                  <StateBadge state={data.review?.publication_state} />
                </div>
                <p className="mt-1 text-sm text-[var(--app-muted)]">
                  {data.ticker} · {data.issuer.finsight_sector} · {humanize(data.issuer.primary_archetype)} ·{' '}
                  {percent(data.issuer.classification_confidence, 0)} confidence
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-semibold uppercase tracking-[.14em] text-[var(--app-muted)]">
                  Assumption range
                </p>
                <p className="font-serif text-3xl font-semibold tracking-[-.03em]">
                  {usd(data.scenario_range.low, 0)} – {usd(data.scenario_range.high, 0)}
                </p>
                <p className="mt-0.5 text-xs text-[var(--app-muted)]">base {usd(data.scenario_range.base)}</p>
              </div>
            </div>
            {data.issuer.classification_reason && (
              <p className="mt-4 max-w-3xl text-xs leading-relaxed text-[var(--app-muted)]">
                {data.issuer.classification_reason}
              </p>
            )}
          </div>

          {/* Models */}
          <div className="grid gap-4 md:grid-cols-2">
            <ModelCard label="FCFF DCF" primary result={data.models.fcff_dcf} />
            <ModelCard label="Earnings Power Value" result={data.models.epv} />
          </div>

          {/* Governed assumptions */}
          {pa && (
            <div className={cn(panel, 'p-6')}>
              <p className="mb-4 text-[11px] font-semibold uppercase tracking-[.16em] text-[var(--app-muted)]">
                Governed assumptions
              </p>
              <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-6">
                <Stat label="Policy WACC" value={percent(pa.policy_wacc)} />
                <Stat label="Risk-free" value={percent(pa.risk_free_rate)} />
                <Stat label="Equity risk prem." value={percent(pa.equity_risk_premium)} />
                <Stat label="Terminal growth" value={percent(pa.terminal_growth)} />
                <Stat label="Forecast years" value={String(pa.forecast_years)} />
                <Stat label="Forecast mode" value={humanize(pa.forecast_mode)} />
              </div>
              {segments.length > 0 && (
                <div className="mt-6 border-t border-[var(--app-border)] pt-5">
                  <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-[var(--app-muted)]">
                    Segment forecast
                  </p>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {segments.map((s) => (
                      <div key={s.label} className="rounded-xl border border-[var(--app-border)] p-3.5">
                        <p className="text-sm font-semibold">{s.label}</p>
                        <p className="mt-1 text-xs text-[var(--app-muted)]">
                          growth {percent(s.initial_revenue_growth ?? null)} · margin{' '}
                          {percent(s.target_gross_margin ?? s.target_operating_margin ?? null)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Provenance */}
          <div className={cn(panel, 'p-6')}>
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-[var(--app-muted)]">
              Source filing
            </p>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <span className="font-semibold">{data.source_financial_statement.form}</span>
              <span className="text-[var(--app-muted)]">period end {data.source_financial_statement.period_end}</span>
              <span className="text-[var(--app-muted)]">filed {data.source_financial_statement.filed_date}</span>
              <span className="font-mono text-xs text-[var(--app-muted)]">
                {data.source_financial_statement.accession}
              </span>
              <a
                href={data.source_financial_statement.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-semibold text-[var(--app-text)] underline decoration-dotted"
              >
                SEC filing <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
            <p className="mt-4 text-[11px] leading-relaxed text-[var(--app-muted)]">
              {data.data_boundary ??
                'Public artifact: derived outputs and governed assumptions only — no reported statement amounts, prices, or recommendations.'}
              {' '}Valuation date {data.valuation_date}. Educational estimate, not investment advice.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}