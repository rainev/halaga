import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, Plus, X } from 'lucide-react'
import { runValuation } from '../lib/api'
import type { ModelKind, ValuationResult } from '../lib/types'
import { ResultCard } from '../components/ResultCard'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const MODELS: { key: ModelKind; label: string; blurb: string }[] = [
  { key: 'dcf', label: 'DCF', blurb: 'Discounted free cash flow to intrinsic value per share.' },
  { key: 'ddm', label: 'DDM', blurb: 'Dividend discount model — value from dividends paid.' },
  { key: 'graham', label: 'Graham', blurb: "Benjamin Graham's revised intrinsic-value formula." },
  { key: 'multiples', label: 'Multiples', blurb: 'Relative valuation from what peers trade at.' },
]

const VARIANTS: Record<ModelKind, { key: string; label: string; desc: string }[]> = {
  dcf: [
    { key: 'simple', label: 'Simple', desc: 'Quick estimate: discount one cash-flow stream and bridge to equity. Good for a fast look or learning.' },
    { key: 'fcff', label: 'FCFF (Enterprise)', desc: 'Discount free cash flow to the FIRM at WACC, then subtract debt. Best for comparing companies with different debt loads. Leave Discount rate blank to build WACC from Beta + Cost of debt.' },
    { key: 'fcfe', label: 'FCFE (Equity)', desc: 'Discount cash flow that already belongs to shareholders (after debt) at the cost of equity — no debt subtraction. Avoids double-counting debt.' },
  ],
  ddm: [
    { key: 'gordon', label: 'Single-stage (Gordon)', desc: 'One constant dividend growth rate forever. For mature, steady dividend payers.' },
    { key: 'two_stage', label: 'Two-stage', desc: 'A high-growth phase, then a fade to a sustainable rate. Use for fast-growing or low-payout payers (e.g. banks) where single-stage understates value.' },
  ],
  graham: [
    { key: 'graham', label: 'Graham', desc: 'A rule-of-thumb screen from EPS, growth and bond yields. Fast first pass — not a precise valuation.' },
  ],
  multiples: [
    { key: 'pe', label: 'P/E', desc: "Value from peers' Price/Earnings. The default when earnings are stable and comparable." },
    { key: 'pb', label: 'P/B', desc: "Value from peers' Price/Book. The standard for banks & financials — book equity is the earning engine and steadier than earnings." },
    { key: 'ev_ebitda', label: 'EV/EBITDA', desc: "Value from peers' EV/EBITDA — capital-structure-neutral, so it fairly compares firms with different debt loads." },
  ],
}

const defaultVariant = (m: ModelKind) => VARIANTS[m][0].key

const PEER_FIELDS: Record<string, { key: string; ph: string }[]> = {
  pe: [{ key: 'price', ph: 'Price' }, { key: 'eps', ph: 'EPS' }],
  pb: [{ key: 'price', ph: 'Price' }, { key: 'bvps', ph: 'Book/share' }],
  ev_ebitda: [{ key: 'ev', ph: 'EV' }, { key: 'ebitda', ph: 'EBITDA' }],
}

const num = (s: string | undefined) => (s === undefined || s.trim() === '' ? undefined : Number(s))
const numList = (s: string | undefined) =>
  !s || s.trim() === '' ? undefined : s.split(',').map((x) => Number(x.trim())).filter((n) => !isNaN(n))

function inputWarnings(model: ModelKind, f: Record<string, string>): string[] {
  const w: string[] = []
  const dr = num(f.discount_rate)
  if (dr !== undefined && dr > 0.5)
    w.push(`Discount rate ${dr} means ${(dr * 100).toFixed(0)}%. It's a decimal (0.10 = 10%) — did you mean to put ${dr} in Beta?`)
  const beta = num(f.beta)
  if (beta !== undefined && beta > 4) w.push(`Beta ${beta} is unusually high (utilities ~0.5–1, most stocks 0–2.5).`)
  for (const key of ['growth_rate', 'high_growth', 'terminal_growth', 'cost_of_debt']) {
    const v = num(f[key])
    if (v !== undefined && Math.abs(v) > 1) w.push(`${key.replace(/_/g, ' ')} ${v} means ${(v * 100).toFixed(0)}%. It's a decimal (0.09 = 9%).`)
  }
  const pg = num(f.perpetual_growth_rate)
  if (pg !== undefined && pg > 0.1) w.push(`Perpetual growth ${pg} looks high — it's a decimal (0.03 = 3%) and must stay below the discount rate.`)
  if (model === 'graham') {
    const gp = num(f.growth_rate_pct)
    if (gp !== undefined && gp > 0 && gp < 1) w.push(`Graham growth is a WHOLE-number percent — enter ${(gp * 100).toFixed(2)}, not ${gp}.`)
  }
  return w
}

interface Peer {
  ticker: string
  [k: string]: string
}

export default function Valuation() {
  const [params] = useSearchParams()
  const companyId = params.get('company') ? Number(params.get('company')) : null
  const ticker = params.get('ticker')

  const [model, setModel] = useState<ModelKind>('dcf')
  const [variant, setVariant] = useState<string>('simple')
  const [f, setF] = useState<Record<string, string>>({})
  const [peers, setPeers] = useState<Peer[]>([{ ticker: '' }])
  const [save, setSave] = useState(false)
  const [result, setResult] = useState<ValuationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const set = (name: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((prev) => ({ ...prev, [name]: e.target.value }))

  function pickModel(m: ModelKind) {
    setModel(m)
    setVariant(defaultVariant(m))
    setResult(null)
    setError(null)
  }

  function buildPayload(): unknown {
    const base = { company_id: companyId, save }
    switch (model) {
      case 'dcf':
        return {
          ...base, method: variant,
          projected_fcf: numList(f.projected_fcf), base_fcf: num(f.base_fcf), growth_rate: num(f.growth_rate), years: num(f.years),
          discount_rate: num(f.discount_rate), beta: num(f.beta), cost_of_debt: num(f.cost_of_debt), tax_rate: num(f.tax_rate) ?? 0.25,
          perpetual_growth_rate: num(f.perpetual_growth_rate), cash: num(f.cash) ?? 0, total_debt: num(f.total_debt) ?? 0,
          shares_outstanding: num(f.shares_outstanding), current_price: num(f.current_price),
        }
      case 'ddm':
        return {
          ...base, method: variant,
          last_dividend: num(f.last_dividend), dividend_history: numList(f.dividend_history), growth_rate: num(f.growth_rate),
          discount_rate: num(f.discount_rate), beta: num(f.beta),
          high_growth: num(f.high_growth), high_growth_years: num(f.high_growth_years), terminal_growth: num(f.terminal_growth),
          current_price: num(f.current_price),
        }
      case 'graham':
        return {
          ...base, eps: num(f.eps), growth_rate_pct: num(f.growth_rate_pct), current_yield: num(f.current_yield),
          margin_of_safety: num(f.margin_of_safety) ?? 0.35, current_price: num(f.current_price),
        }
      case 'multiples': {
        const cols = PEER_FIELDS[variant]
        const mapped = peers
          .filter((p) => cols.every((c) => p[c.key] && !isNaN(Number(p[c.key]))))
          .map((p) => {
            const row: Record<string, unknown> = { ticker: p.ticker || null }
            if (variant === 'pe') Object.assign(row, { price: Number(p.price), eps: Number(p.eps) })
            else if (variant === 'pb') Object.assign(row, { price: Number(p.price), book_value_per_share: Number(p.bvps) })
            else Object.assign(row, { ev: Number(p.ev), ebitda: Number(p.ebitda) })
            return row
          })
        return {
          ...base, metric: variant, peers: mapped,
          target_eps: variant === 'pe' ? num(f.target_eps) : undefined,
          target_book_value_per_share: variant === 'pb' ? num(f.target_bvps) : undefined,
          target_ebitda: variant === 'ev_ebitda' ? num(f.target_ebitda) : undefined,
          cash: num(f.cash) ?? 0, total_debt: num(f.total_debt) ?? 0,
          shares_outstanding: variant === 'ev_ebitda' ? num(f.shares_outstanding) : undefined,
          current_price: num(f.current_price),
        }
      }
    }
  }

  const warnings = useMemo(() => inputWarnings(model, f), [model, f])

  async function handleRun() {
    setError(null)
    setBusy(true)
    setResult(null)
    try {
      setResult(await runValuation(model, buildPayload()))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Valuation failed')
    } finally {
      setBusy(false)
    }
  }

  const variants = VARIANTS[model]
  const variantDesc = variants.find((v) => v.key === variant)?.desc

  return (
    <section className="space-y-5">
      <header>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
          {ticker ? 'Valuing' : 'New valuation'}
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">
          {ticker ? <span className="font-mono">{ticker}</span> : 'Pick a model'}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {ticker ? 'Value it four ways, then compare to the market price.' : 'Or choose a company from Coverage to attach the run.'}
        </p>
      </header>

      <Tabs value={model} onValueChange={(v) => pickModel(v as ModelKind)}>
        <TabsList>
          {MODELS.map((m) => (
            <TabsTrigger key={m.key} value={m.key}>{m.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <p className="-mt-1 text-sm text-muted-foreground">{MODELS.find((m) => m.key === model)!.blurb}</p>

      <div className="grid items-start gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardContent className="space-y-4 p-6">
            {variants.length > 1 && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Method</Label>
                <Select value={variant} onValueChange={(v) => { setVariant(v); setResult(null) }}>
                  <SelectTrigger className="max-w-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {variants.map((v) => (<SelectItem key={v.key} value={v.key}>{v.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {variantDesc && (
              <p className="rounded-lg border border-accent bg-accent px-3 py-2.5 text-[13px] leading-relaxed text-accent-foreground">
                {variantDesc}
              </p>
            )}

            {model === 'dcf' && (
              <>
                <Field label={variant === 'fcfe' ? 'Projected FCFE (comma-separated)' : 'Projected FCF (comma-separated)'} hint="e.g. 20000, 21800, 23762">
                  <Input value={f.projected_fcf ?? ''} onChange={set('projected_fcf')} />
                </Field>
                <Divider>or build a projection</Divider>
                <Row3>
                  <Field label="Base FCF"><Input value={f.base_fcf ?? ''} onChange={set('base_fcf')} /></Field>
                  <Field label="Growth (decimal)" hint="0.09 = 9%"><Input value={f.growth_rate ?? ''} onChange={set('growth_rate')} /></Field>
                  <Field label="Years"><Input value={f.years ?? ''} onChange={set('years')} /></Field>
                </Row3>
                <Row3>
                  <Field label={variant === 'fcfe' ? 'Cost of equity (decimal)' : 'Discount rate (decimal)'} hint="or use beta"><Input value={f.discount_rate ?? ''} onChange={set('discount_rate')} /></Field>
                  <Field label="Beta" hint="CAPM cost of equity"><Input value={f.beta ?? ''} onChange={set('beta')} /></Field>
                  <Field label="Perpetual growth" hint="blank = 0.03"><Input value={f.perpetual_growth_rate ?? ''} onChange={set('perpetual_growth_rate')} /></Field>
                </Row3>
                {variant === 'fcff' && (
                  <Row3>
                    <Field label="Cost of debt (decimal)" hint="for WACC"><Input value={f.cost_of_debt ?? ''} onChange={set('cost_of_debt')} /></Field>
                    <Field label="Tax rate" hint="0.25 = 25%"><Input value={f.tax_rate ?? ''} onChange={set('tax_rate')} /></Field>
                    <div />
                  </Row3>
                )}
                <Row3>
                  {variant !== 'fcfe' && <Field label="Cash & equivalents"><Input value={f.cash ?? ''} onChange={set('cash')} /></Field>}
                  {variant !== 'fcfe' && <Field label="Total debt"><Input value={f.total_debt ?? ''} onChange={set('total_debt')} /></Field>}
                  <Field label="Shares outstanding"><Input value={f.shares_outstanding ?? ''} onChange={set('shares_outstanding')} /></Field>
                </Row3>
                <Field label="Current price (optional)"><Input value={f.current_price ?? ''} onChange={set('current_price')} /></Field>
              </>
            )}

            {model === 'ddm' && (
              <>
                <Field label="Dividend history (comma-separated)" hint="derives last dividend + growth">
                  <Input value={f.dividend_history ?? ''} onChange={set('dividend_history')} />
                </Field>
                <Divider>or enter directly</Divider>
                <Row2>
                  <Field label="Last dividend (annual)"><Input value={f.last_dividend ?? ''} onChange={set('last_dividend')} /></Field>
                  {variant === 'gordon' && <Field label="Growth (decimal)"><Input value={f.growth_rate ?? ''} onChange={set('growth_rate')} /></Field>}
                </Row2>
                {variant === 'two_stage' && (
                  <Row3>
                    <Field label="High growth (decimal)" hint="near-term"><Input value={f.high_growth ?? ''} onChange={set('high_growth')} /></Field>
                    <Field label="High-growth years"><Input value={f.high_growth_years ?? ''} onChange={set('high_growth_years')} /></Field>
                    <Field label="Terminal growth (decimal)" hint="long-run"><Input value={f.terminal_growth ?? ''} onChange={set('terminal_growth')} /></Field>
                  </Row3>
                )}
                <Row2>
                  <Field label="Discount rate (decimal)" hint="or use beta"><Input value={f.discount_rate ?? ''} onChange={set('discount_rate')} /></Field>
                  <Field label="Beta"><Input value={f.beta ?? ''} onChange={set('beta')} /></Field>
                </Row2>
                <Field label="Current price (optional)"><Input value={f.current_price ?? ''} onChange={set('current_price')} /></Field>
              </>
            )}

            {model === 'graham' && (
              <>
                <Row2>
                  <Field label="EPS"><Input value={f.eps ?? ''} onChange={set('eps')} /></Field>
                  <Field label="Growth rate (%)" hint="WHOLE number, e.g. 9.63"><Input value={f.growth_rate_pct ?? ''} onChange={set('growth_rate_pct')} /></Field>
                </Row2>
                <Row2>
                  <Field label="Current bond yield" hint="blank = 6.0"><Input value={f.current_yield ?? ''} onChange={set('current_yield')} /></Field>
                  <Field label="Margin of safety" hint="0.35 = 35%"><Input value={f.margin_of_safety ?? ''} onChange={set('margin_of_safety')} /></Field>
                </Row2>
                <Field label="Current price (optional)"><Input value={f.current_price ?? ''} onChange={set('current_price')} /></Field>
              </>
            )}

            {model === 'multiples' && (
              <>
                <Label className="text-xs text-muted-foreground">Peers</Label>
                <div className="space-y-2">
                  {peers.map((p, i) => (
                    <div key={i} className="flex gap-2">
                      <Input className="w-24" placeholder="Ticker" value={p.ticker} onChange={(e) => setPeers((ps) => ps.map((x, j) => (j === i ? { ...x, ticker: e.target.value } : x)))} />
                      {PEER_FIELDS[variant].map((c) => (
                        <Input key={c.key} placeholder={c.ph} value={p[c.key] ?? ''} onChange={(e) => setPeers((ps) => ps.map((x, j) => (j === i ? { ...x, [c.key]: e.target.value } : x)))} />
                      ))}
                      <Button variant="ghost" size="icon" onClick={() => setPeers((ps) => ps.filter((_, j) => j !== i))} disabled={peers.length === 1} aria-label="Remove peer">
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <Button variant="outline" size="sm" onClick={() => setPeers((ps) => [...ps, { ticker: '' }])}>
                  <Plus className="h-4 w-4" /> Add peer
                </Button>
                <Row2>
                  {variant === 'pe' && <Field label="Target company EPS"><Input value={f.target_eps ?? ''} onChange={set('target_eps')} /></Field>}
                  {variant === 'pb' && <Field label="Target book value / share"><Input value={f.target_bvps ?? ''} onChange={set('target_bvps')} /></Field>}
                  {variant === 'ev_ebitda' && <Field label="Target EBITDA"><Input value={f.target_ebitda ?? ''} onChange={set('target_ebitda')} /></Field>}
                  <Field label="Current price (optional)"><Input value={f.current_price ?? ''} onChange={set('current_price')} /></Field>
                </Row2>
                {variant === 'ev_ebitda' && (
                  <Row3>
                    <Field label="Cash & equivalents"><Input value={f.cash ?? ''} onChange={set('cash')} /></Field>
                    <Field label="Total debt"><Input value={f.total_debt ?? ''} onChange={set('total_debt')} /></Field>
                    <Field label="Shares outstanding"><Input value={f.shares_outstanding ?? ''} onChange={set('shares_outstanding')} /></Field>
                  </Row3>
                )}
              </>
            )}

            {warnings.length > 0 && (
              <div className="space-y-1 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-[13px] leading-relaxed text-warning">
                {warnings.map((msg, i) => (
                  <div key={i} className="flex gap-2">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> <span>{msg}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between border-t pt-4">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Checkbox checked={save} onCheckedChange={(v) => setSave(v === true)} /> Save this run
              </label>
              <Button onClick={handleRun} disabled={busy}>{busy ? 'Computing…' : 'Run valuation'}</Button>
            </div>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>

        <div>{result && <ResultCard result={result} />}</div>
      </div>
    </section>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">
        {label}
        {hint && <span className="font-normal opacity-70"> — {hint}</span>}
      </Label>
      {children}
    </div>
  )
}

function Row2({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{children}</div>
}
function Row3({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">{children}</div>
}
function Divider({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <span className="h-px flex-1 bg-border" />
      {children}
      <span className="h-px flex-1 bg-border" />
    </div>
  )
}
