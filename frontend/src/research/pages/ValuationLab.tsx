import { AlertTriangle, ExternalLink } from 'lucide-react'
import { PHILIPPINE_ASSUMPTIONS, VALUATION_COMPANIES } from '../data.js'
import { calculateValuation, getFinancialHistorySummary, getUsPublicationPresentation, SENTIMENTS } from '../engine.js'
import { compactPeso, money, PageHeading, panel, percent, peso } from '../format'
import { useResearch, type Sentiment } from '../ResearchContext'
import { cn } from '@/lib/utils'

const MODEL_META: Array<[string, string, string, string]> = [
  ['dcf', 'DCF', 'Values future cash flow today', '5-year forecast + terminal value'],
  ['graham', 'Graham diagnostic', 'A legacy earnings-and-yield reference', 'Shown for education; never blended'],
  ['multiples', 'Multiples', 'Compares earnings with a peer P/E', 'EPS × adjusted peer P/E'],
  ['ddm', 'Dividend', 'Values expected dividend payments', 'Next dividend / (return − growth)'],
]

const BANK_MODEL_META: Array<[string, string, string, string]> = [
  ['residual_income', 'Residual income', 'Book value plus profit earned above the required return', 'BVPS + present value of excess returns'],
  ['ddm', 'Dividend cross-check', 'Values the forecast common-dividend stream', 'Forecast DPS discounted at cost of equity'],
  ['justified_pb', 'Justified P/B', 'Stable ROE, growth, and risk cross-check', '(ROE − growth) / (cost of equity − growth) × BVPS'],
]

const US_MODEL_META: Array<[string, string, string, string]> = [
  ['fcff_dcf', 'FCFF DCF', 'Values filing-derived operating cash flow before the financing bridge', 'Forecast FCFF + terminal value, discounted at policy WACC'],
  ['epv', 'Earnings power', 'Shows a no-growth support value from normalized operating profit', 'Normalized NOPAT / policy WACC'],
]

const MODEL_GUIDE = [
  ['DCF', 'Estimates today’s value of future business cash flow.'],
  ['Graham', 'A legacy diagnostic only; it is not used as a headline valuation.'],
  ['Multiples', 'Applies a comparable P/E ratio to company earnings.'],
  ['Dividend', 'Estimates value from expected dividend payments.'],
]

const BANK_MODEL_GUIDE = [
  ['Residual income', 'Adds today’s common book value to the present value of future earnings above the required return.'],
  ['Dividend', 'Revalues the same clean-surplus earnings path through common dividends; it is a reconciliation check, not independent evidence.'],
  ['Justified P/B', 'Checks the value implied by sustainable ROE, growth, and cost of equity.'],
]

const US_MODEL_GUIDE = [
  ['FCFF DCF', 'The primary estimate: forecasts filing-derived operating earnings and required reinvestment, then applies the governed enterprise-to-equity bridge.'],
  ['Earnings power', 'A conservative support value that assumes no future growth and stable normalized operations.'],
]

export default function ValuationLab() {
  const { selectedSymbol, setSelectedSymbol, sentiment, setSentiment } = useResearch()
  const company = VALUATION_COMPANIES.find((item) => item.symbol === selectedSymbol) ?? VALUATION_COMPANIES[0]
  const valuation = calculateValuation(company, sentiment)
  const isBank = company.subsector === 'Banks'
  const isUS = company.market === 'US'
  const modelMeta = isUS ? US_MODEL_META : isBank ? BANK_MODEL_META : MODEL_META
  const modelGuide = isUS ? US_MODEL_GUIDE : isBank ? BANK_MODEL_GUIDE : MODEL_GUIDE
  const currency = company.currency ?? 'PHP'
  const formatValue = (value: number) => money(value, currency)
  const dcf = valuation.models.dcf
  const bank = company.valuation.bank
  const history = getFinancialHistorySummary(company)
  const usValuation = company.valuation.us
  const usPresentation = getUsPublicationPresentation(usValuation?.review.publication_state)
  const { isWithheld, requiresDataReview } = usPresentation
  const publicationReason = usValuation?.review.errors?.[0] ?? 'Publication is withheld pending data review.'
  const hasPrimaryValue = !isWithheld && valuation.primaryValue !== null
  const segmentEntries = Object.entries(
    usValuation?.public_assumptions.segment_assumptions ?? {},
  )
  const isOperatingIncomeRoute =
    usValuation?.public_assumptions.forecast_mode === 'segment_operating_income'
  const usPanelTitle = isOperatingIncomeRoute
    ? 'Segment operating-income forecast.'
    : usValuation?.public_assumptions.forecast_mode === 'segment_gross_profit'
      ? 'Segment gross-profit forecast.'
      : 'Forecast unavailable pending data review.'
  const segmentMetricLabel = isOperatingIncomeRoute
    ? 'Target operating margin'
    : 'Target gross margin'
  const pageDescription = isUS
    ? usPresentation.pageDescription
    : 'Compare bear, base, and bull assumptions.'
  const historyTitle = isWithheld
    ? usPresentation.historyTitle
    : 'More periods can be added without blocking today’s valuation.'
  const historyDescription = isWithheld
    ? usPresentation.historyDescription
    : isBank
      ? 'BDO uses the latest four standalone quarters for TTM earnings and the latest balance sheet for common book value. Cumulative YTD figures are used only to derive standalone quarters and are never added to annual values.'
      : 'The engine accepts optional annual and standalone quarterly records. It can use a three-year annual median or the latest four consecutive quarters when enough filing-tied cash-flow data becomes available. Annual and quarterly values are never added together.'
  const valuationNote = isWithheld
    ? usPresentation.valuationNote
    : company.valuation.note
  const valuationStatusLine = isWithheld
    ? `${usPresentation.statusLabel} · ${SENTIMENTS[sentiment].label} case`
    : `per share · ${SENTIMENTS[sentiment].label} case · ${isUS ? usPresentation.statusLabel : valuation.status === 'pass' ? 'validation passed' : valuation.status === 'review' ? 'preliminary — review required' : 'blocked by validation'}`
  const modelRole = (key: string) => {
    if (key === valuation.primaryModel) return 'Primary'
    if (valuation.crossChecks.includes(key)) return 'Cross-check'
    return 'Diagnostic'
  }

  return (
    <>
      <PageHeading eyebrow="Valuation" title="Estimate what a share is worth." description={pageDescription}>
        <label className="grid w-full gap-1 text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)] md:w-64">Company<select value={company.symbol} onChange={(event) => setSelectedSymbol(event.target.value)} className="h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm normal-case tracking-normal text-[var(--app-text)]">{VALUATION_COMPANIES.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.shortName}</option>)}</select></label>
      </PageHeading>

      <section className={cn(panel, 'grid overflow-hidden lg:grid-cols-[1fr_330px]')}>
        <div className="p-6 sm:p-10">
          <div className="inline-grid grid-cols-3 rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-1">{Object.entries(SENTIMENTS).map(([key, item]) => <button key={key} onClick={() => setSentiment(key as Sentiment)} className={cn('min-w-20 rounded-lg px-4 py-2 text-xs font-bold text-[var(--app-muted)]', sentiment === key && 'bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm')}>{item.label}</button>)}</div>
          <p className="mt-8 text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-text)]">{hasPrimaryValue ? `${valuation.primaryModel.toUpperCase()} primary estimate` : 'Headline estimate withheld'}</p>
          <strong className="mt-2 block font-serif text-6xl font-normal tracking-[-.05em] sm:text-7xl">{hasPrimaryValue ? formatValue(valuation.primaryValue as number) : '—'}</strong>
          <p className="mt-1 text-xs text-[var(--app-muted)]">{valuationStatusLine}</p>
          {!isWithheld && hasPrimaryValue && valuation.scenarioLow !== null && valuation.scenarioHigh !== null ? <>
            <div className="mt-9 h-1.5 rounded-full bg-gradient-to-r from-[#d4d4d4] to-[#121212]" />
            <div className="mt-3 flex justify-between font-serif"><span><small className="block font-sans text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">BEAR / BULL RANGE LOW</small>{formatValue(valuation.scenarioLow)}</span><span className="text-right"><small className="block font-sans text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">BEAR / BULL RANGE HIGH</small>{formatValue(valuation.scenarioHigh)}</span></div>
          </> : <p className="mt-8 max-w-xl text-sm leading-relaxed text-[var(--app-muted)]">{isWithheld ? publicationReason : valuation.errors[0]}.</p>}
        </div>
        <aside className="flex gap-3 border-t border-[var(--app-border)] bg-[var(--app-subtle)] p-7 lg:border-l lg:border-t-0"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[var(--app-subtle)] text-[var(--app-muted-strong)]"><AlertTriangle className="h-4 w-4" /></span><div><strong className="text-sm">{isUS ? usPresentation.isWithheld ? 'Method gate stopped publication' : 'Review controls' : valuation.status === 'blocked' ? 'Method gate stopped publication' : 'Review controls'}</strong><p className="mt-2 text-xs leading-relaxed text-[var(--app-muted)]">{valuation.policyReason} The app keeps model outputs separate.</p>{valuation.warnings.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-4 text-[10px] leading-relaxed text-[var(--app-muted)]">{valuation.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}</div></aside>
      </section>

      <section className="mt-11"><div className="mb-4"><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-muted)]">Model roles</p><h2 className="mt-1 text-xl font-bold">One primary method; cross-checks stay separate</h2></div>
        <div className={cn('grid gap-3 sm:grid-cols-2', isBank ? 'xl:grid-cols-3' : isUS ? 'xl:grid-cols-2' : 'xl:grid-cols-4')}>{modelMeta.map(([key, label, explanation, formula]) => { const result = valuation.models[key]; const valueAvailable = !isWithheld && result && Number.isFinite(result.perShare); return <article key={key} className={cn(panel, 'p-5', !result && 'opacity-50')}><div className="flex justify-between gap-3 text-xs font-extrabold text-[var(--app-text)]"><span>{label}</span><small className="text-right text-[9px] uppercase tracking-[.08em] text-[var(--app-muted)]">{modelRole(key)}</small></div><strong className="mt-7 block font-serif text-3xl font-normal">{valueAvailable ? formatValue(result.perShare) : 'Not available'}</strong><p className="mt-3 text-xs text-[var(--app-muted)]">{explanation}</p><small className="mt-4 block text-[9px] leading-relaxed text-[var(--app-muted)]">{formula}</small>{result?.errors?.[0] && <small className="mt-3 block text-[9px] leading-relaxed text-red-700">{result.errors[0]}</small>}</article>})}</div>
      </section>

      {isUS ? (
        <section className="mt-11 grid gap-9 rounded-[21px] border border-[var(--app-border)] bg-[var(--app-feature)] p-7 text-[var(--app-text)] lg:grid-cols-[.85fr_1.15fr] lg:p-9">
          <div><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">U.S. filing-only controls</p><h2 className="mt-2 text-2xl font-bold">{usPanelTitle}</h2><p className="mt-3 text-xs leading-relaxed text-[var(--app-muted)]">{segmentEntries.length > 0 ? `The model forecasts ${segmentEntries.map(([, segment]) => segment.label ?? 'a filing segment').join(', ')} separately using governed public assumptions and a policy-calibrated discount rate. Raw filing amounts stay outside the public app.` : 'The filing period is available, but governed segment forecast evidence is not yet available for publication. No intrinsic value is shown until the review can be cleared.'}</p>{requiresDataReview && <p className="mt-3 text-xs font-bold text-[#a16207]">{usPresentation.statusLabel}</p>}{isWithheld && <p className="mt-3 text-xs font-bold text-[#a16207]">Valuation withheld: {publicationReason}</p>}<a className="mt-4 inline-flex items-center gap-2 text-[10px] font-bold text-[var(--app-text)]" href={usValuation?.public_assumptions.risk_free_source_url} target="_blank" rel="noreferrer">Official U.S. Treasury rate source <ExternalLink className="h-3 w-3" /></a></div>
          <dl className="grid grid-cols-2 gap-2"><Assumption label="10-year Treasury" value={percent(usValuation?.public_assumptions.risk_free_rate ?? null)} /><Assumption label="Policy ERP" value={percent(usValuation?.public_assumptions.equity_risk_premium ?? null)} /><Assumption label="Policy WACC" value={percent(usValuation?.public_assumptions.policy_wacc ?? null)} /><Assumption label="Terminal growth" value={percent(usValuation?.public_assumptions.terminal_growth ?? null)} />{segmentEntries.flatMap(([key, segment]) => [<Assumption key={`${key}-growth`} label={`${segment.label ?? key} initial growth`} value={percent(segment.initial_revenue_growth ?? null)} />, <Assumption key={`${key}-margin`} label={`${segment.label ?? key} ${segmentMetricLabel.toLowerCase()}`} value={percent(isOperatingIncomeRoute ? segment.target_operating_margin ?? null : segment.target_gross_margin ?? null)} />])}<Assumption label="Forecast horizon" value={usValuation?.public_assumptions.forecast_years === null ? 'Not reported' : `${usValuation?.public_assumptions.forecast_years} years`} /><Assumption label="Target operating margin" value={percent(usValuation?.public_assumptions.target_operating_margin ?? null)} /><Assumption label="Statement period" value={usValuation?.source_financial_statement.period_end ?? 'Not reported'} /><Assumption label="Confidence" value={usValuation?.review.confidence_grade ?? 'Not reported'} /></dl>
        </section>
      ) : isBank ? (
        <section className="mt-11 grid gap-9 rounded-[21px] border border-[var(--app-border)] bg-[var(--app-feature)] p-7 text-[var(--app-text)] lg:grid-cols-[.85fr_1.15fr] lg:p-9">
          <div><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">Bank valuation controls</p><h2 className="mt-2 text-2xl font-bold">Equity returns replace enterprise cash flow.</h2><p className="mt-3 text-xs leading-relaxed text-[var(--app-muted)]">Deposits are operating funding for a bank, so BDO is valued from common book equity, sustainable ROE, payout, and cost of equity. The beta is a disclosed 1.0 sector fallback.</p></div>
          <dl className="grid grid-cols-2 gap-2"><Assumption label="Common BVPS" value={peso(bank.book_value_per_share)} /><Assumption label="TTM ROE" value={percent(bank.ttm_roe)} /><Assumption label="Cost of equity" value={percent(bank.assumptions.base_cost_of_equity)} /><Assumption label="TTM payout" value={percent(bank.current_payout_ratio)} /><Assumption label="Terminal ROE" value={percent(bank.assumptions.terminal_roe)} /><Assumption label="Terminal growth" value={percent(bank.assumptions.terminal_growth)} /><Assumption label="CET1 ratio" value={percent(bank.cet1_ratio)} /><Assumption label="Capital ratio" value={percent(bank.capital_adequacy_ratio)} /></dl>
        </section>
      ) : (
        <section className="mt-11 grid gap-9 rounded-[21px] border border-[var(--app-border)] bg-[var(--app-feature)] p-7 text-[var(--app-text)] lg:grid-cols-[.85fr_1.15fr] lg:p-9">
          <div><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">Philippine rate controls</p><h2 className="mt-2 text-2xl font-bold">Local yield is an input, not the whole discount rate.</h2><p className="mt-3 text-xs leading-relaxed text-[var(--app-muted)]">{PHILIPPINE_ASSUMPTIONS.note}</p><a className="mt-4 inline-flex items-center gap-2 text-[10px] font-bold text-[var(--app-text)]" href={PHILIPPINE_ASSUMPTIONS.sourceUrl} target="_blank" rel="noreferrer">Official Treasury auction result <ExternalLink className="h-3 w-3" /></a></div>
          <dl className="grid grid-cols-2 gap-2"><Assumption label="Local government yield" value={percent(PHILIPPINE_ASSUMPTIONS.localGovernmentYield, 3)} /><Assumption label="Graham normalizer" value={percent(PHILIPPINE_ASSUMPTIONS.grahamBaselineYield)} /><Assumption label="DCF discount rate" value={percent(dcf.discountRate)} /><Assumption label="Terminal growth" value={percent(dcf.terminalGrowth)} /><Assumption label="Normalized annual FCF" value={compactPeso(dcf.normalizedFcf)} /><Assumption label="PV terminal / EV" value={dcf.terminalValueShare === null ? '—' : percent(dcf.terminalValueShare)} /><Assumption label="Cash-flow basis" value={history.cashFlowBasisLabel} /><Assumption label="History loaded" value={`${history.annualCount} annual · ${history.quarterlyCount} quarterly`} /></dl>
        </section>
      )}
      <section className={cn(panel, 'mt-4 grid gap-4 p-5 sm:grid-cols-[1fr_auto] sm:items-center')}>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">Flexible history enabled</p>
          <h2 className="mt-1 text-base font-bold">{historyTitle}</h2>
          <p className="mt-2 text-xs leading-relaxed text-[var(--app-muted)]">{historyDescription}</p>
          {[...history.errors, ...history.warnings].length > 0 && <ul className="mt-3 list-disc space-y-1 pl-4 text-[10px] leading-relaxed text-[#a16207]">{[...history.errors, ...history.warnings].map((issue) => <li key={issue}>{issue}</li>)}</ul>}
        </div>
        <div className="grid min-w-52 grid-cols-2 gap-2">
          <HistoryCount label="Annual loaded" value={history.annualCount} capacity={history.annualTarget} />
          <HistoryCount label="Quarterly loaded" value={history.quarterlyCount} capacity={history.quarterlyTarget} />
        </div>
      </section>
      <p className="mt-4 text-xs leading-relaxed text-[var(--app-muted)]"><strong>Filing source:</strong> {company.source.label}. {valuationNote}</p>

      <section className="mt-12 border-t border-[var(--app-border)] pt-8" aria-labelledby="model-guide-title">
        <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-muted)]">Model guide</p>
        <h2 id="model-guide-title" className="mt-1 text-xl font-bold">What each model does</h2>
        <div className="mt-5 grid gap-x-10 gap-y-5 sm:grid-cols-2">
          {modelGuide.map(([name, description]) => (
            <div key={name} className="grid grid-cols-[88px_1fr] gap-3 border-t border-[var(--app-border)] pt-4">
              <strong className="text-sm">{name}</strong>
              <p className="text-xs leading-relaxed text-[var(--app-muted)]">{description}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 max-w-3xl text-xs leading-relaxed text-[var(--app-muted)]">Models are estimates, not predictions. A cross-check can challenge the primary method, but the app will not average incompatible methods into false precision.</p>
      </section>
    </>
  )
}

function Assumption({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] p-3"><dt className="text-[9px] text-[var(--app-muted)]">{label}</dt><dd className="mt-1 font-serif text-lg">{value}</dd></div>
}

function HistoryCount({ label, value, capacity }: { label: string; value: number; capacity: number }) {
  return <div className="rounded-xl border border-[var(--app-border)] bg-[var(--app-bg)] p-3 text-center"><small className="block text-[8px] font-bold uppercase tracking-[.1em] text-[var(--app-muted)]">{label}</small><strong className="mt-1 block font-serif text-2xl font-normal">{value}</strong><span className="text-[9px] text-[var(--app-muted)]">supports {capacity}+ periods</span></div>
}
