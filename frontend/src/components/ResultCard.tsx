import type { ValuationResult } from '../lib/types'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ValuationGauge } from './ValuationGauge'

const php = (n: number) =>
  new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP', maximumFractionDigits: 2 }).format(n)

function verdictBadge(verdict: string | null) {
  if (!verdict) return null
  const v = verdict.toLowerCase()
  if (v === 'undervalued' || v === 'buy') return <Badge variant="success">{verdict}</Badge>
  if (v === 'overvalued' || v === 'sell') return <Badge variant="destructive">{verdict}</Badge>
  return <Badge variant="muted">{verdict}</Badge>
}

function fmt(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(4)
  if (Array.isArray(v)) return `${v.length} item(s)`
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return ''
  return String(v)
}

const LABELS: Record<string, string> = {
  method: 'Method',
  metric: 'Metric',
  enterprise_value: 'Enterprise value',
  equity_value: 'Equity value',
  terminal_value: 'Terminal value',
  pv_terminal: 'PV of terminal value',
  pv_high_growth: 'PV of high-growth dividends',
  discount_rate: 'Discount rate',
  cost_of_equity: 'Cost of equity',
  perpetual_growth_rate: 'Perpetual growth',
  next_dividend: 'Next dividend (D₁)',
  growth_rate: 'Growth rate',
  high_growth: 'High growth rate',
  high_growth_years: 'High-growth years',
  terminal_growth: 'Terminal growth',
  acceptable_buy_price: 'Acceptable buy price',
  margin_of_safety: 'Margin of safety',
  current_yield: 'Bond yield (Y)',
  average_pe: 'Average P/E',
  median_pe: 'Median P/E',
  average_pb: 'Average P/B',
  median_pb: 'Median P/B',
  average_ev_ebitda: 'Average EV/EBITDA',
  median_ev_ebitda: 'Median EV/EBITDA',
  value_on_average: 'Value @ average',
  value_on_median: 'Value @ median',
  target_eps: 'Target EPS',
  target_book_value_per_share: 'Target book value/share',
  target_ebitda: 'Target EBITDA',
}

function PeerTable({ peers }: { peers: Record<string, unknown>[] }) {
  if (!peers.length) return null
  const cols = Object.keys(peers[0]).filter((k) => k !== 'ticker')
  const grid = { gridTemplateColumns: `1fr repeat(${cols.length}, 1fr)` }
  return (
    <div className="mt-4 overflow-hidden rounded-lg border">
      <div className="grid gap-2 bg-muted/40 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground" style={grid}>
        <span>Peer</span>
        {cols.map((c) => (
          <span key={c} className="text-right">{c.replace(/_/g, '/')}</span>
        ))}
      </div>
      {peers.map((p, i) => (
        <div key={i} className="grid gap-2 border-t px-3 py-2 text-sm" style={grid}>
          <span className="font-mono text-xs">{(p.ticker as string) ?? '—'}</span>
          {cols.map((c) => (
            <span key={c} className="tnum text-right font-mono text-xs">{typeof p[c] === 'number' ? (p[c] as number).toFixed(2) : '—'}</span>
          ))}
        </div>
      ))}
    </div>
  )
}

export function ResultCard({ result }: { result: ValuationResult }) {
  const { intrinsic_value, current_price, verdict, detail } = result

  return (
    <Card className="sticky top-24 overflow-hidden motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-500">
      {/* Ink hero — the headline number */}
      <div className="bg-[hsl(var(--ink))] px-6 pb-7 pt-6 text-slate-100">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
            Intrinsic value / share
          </span>
          {verdictBadge(verdict)}
        </div>
        <div className="tnum mt-2 font-display text-[2.75rem] font-bold leading-none tracking-tight">
          {php(intrinsic_value)}
        </div>
        <ValuationGauge intrinsic={intrinsic_value} price={current_price} />
      </div>

      <CardContent className="p-6">
        <details open>
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Breakdown
          </summary>
          <div className="mt-3 divide-y">
            {Object.entries(detail)
              .filter(([, v]) => typeof v !== 'object' || v === null)
              .map(([k, v]) => (
                <div key={k} className="flex justify-between py-1.5 text-sm">
                  <span className="text-muted-foreground">{LABELS[k] ?? k}</span>
                  <span className="tnum font-mono text-xs">{fmt(v)}</span>
                </div>
              ))}
          </div>
          {Array.isArray((detail as { peers?: unknown }).peers) && (
            <PeerTable peers={detail.peers as Record<string, unknown>[]} />
          )}
        </details>

        {result.saved_id && (
          <p className="mt-4 text-sm font-medium text-success">Saved as run #{result.saved_id}</p>
        )}
      </CardContent>
    </Card>
  )
}
