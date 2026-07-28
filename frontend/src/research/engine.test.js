import test from 'node:test'
import assert from 'node:assert/strict'
import { INDUSTRIAL_COMPANIES, VALUATION_COMPANIES } from './data.js'
import {
  buildSmartBrief,
  calculateValuation,
  getFinancialHistorySummary,
  getFinancialSnapshot,
  getHealthMetrics,
  portfolioCostBasis,
  portfolioRealizedReturn,
  scoreCompany,
  validateFinancialHistory,
} from './engine.js'

test('sentiment cases are ordered for every Industrial company', () => {
  for (const company of INDUSTRIAL_COMPANIES) {
    const policy = company.valuation.modelPolicy
    if (!policy.publishable) continue
    const bear = calculateValuation(company, 'bear').primaryValue
    const base = calculateValuation(company, 'base').primaryValue
    const bull = calculateValuation(company, 'bull').primaryValue
    assert.ok(bear < base, `${company.symbol}: bear must be below base`)
    assert.ok(base < bull, `${company.symbol}: base must be below bull`)
  }
})

test('BDO routes to bank valuation models with filing-derived inputs', () => {
  const bdo = VALUATION_COMPANIES.find((company) => company.symbol === 'BDO')
  const result = calculateValuation(bdo, 'base')

  assert.equal(bdo.subsector, 'Banks')
  assert.equal(result.primaryModel, 'residual_income')
  assert.equal(result.models.dcf, undefined)
  assert.ok(Math.abs(result.primaryValue - 150.4778) < 0.001)
  assert.ok(Math.abs(result.models.ddm.perShare - result.primaryValue) < 0.01)
  assert.ok(Math.abs(result.models.justified_pb.perShare - 144.7904) < 0.001)
  assert.ok(Math.abs(result.scenarioLow - 109.7277) < 0.001)
  assert.ok(Math.abs(result.scenarioHigh - 200.5609) < 0.001)
})

test('incompatible valuation methods are never blended', () => {
  const valuation = calculateValuation(INDUSTRIAL_COMPANIES[0], 'base')
  assert.equal('blended' in valuation, false)
  assert.equal(valuation.primaryModel, 'dcf')
  assert.deepEqual(valuation.crossChecks, ['multiples', 'ddm'])
})

test('method routing blocks finite-life and SOTP names until implemented', () => {
  const semirara = calculateValuation(INDUSTRIAL_COMPANIES.find((company) => company.symbol === 'SCC'))
  const petroEnergy = calculateValuation(INDUSTRIAL_COMPANIES.find((company) => company.symbol === 'PERC'))
  assert.equal(semirara.status, 'blocked')
  assert.equal(semirara.primaryValue, null)
  assert.match(semirara.errors.join(' '), /finite-life mining NAV/i)
  assert.equal(petroEnergy.status, 'blocked')
  assert.match(petroEnergy.errors.join(' '), /sum-of-the-parts/i)
})

test('DCF exposes terminal-value concentration and never floors negative equity value', () => {
  const alsons = INDUSTRIAL_COMPANIES.find((company) => company.symbol === 'ACR')
  const result = calculateValuation(alsons).models.dcf
  assert.ok(Number.isFinite(result.terminalValueShare))
  assert.equal(result.status, 'review')

  const stressed = structuredClone(alsons)
  stressed.financials.debt = 1_000_000_000_000
  const negative = calculateValuation(stressed).models.dcf
  assert.ok(negative.perShare < 0)
})

test('rate-growth spread below three points is blocked instead of silently floored', () => {
  const company = structuredClone(INDUSTRIAL_COMPANIES[0])
  company.valuation.discountRate = 0.055
  company.valuation.terminalGrowth = 0.035
  const result = calculateValuation(company).models.dcf
  assert.equal(result.status, 'blocked')
  assert.match(result.errors.join(' '), /at least 3 percentage points/i)
})

test('risk tolerance changes the screen without changing filing data', () => {
  const alsons = INDUSTRIAL_COMPANIES.find((company) => company.symbol === 'ACR')
  const revenue = alsons.financials.revenue
  assert.ok(scoreCompany(alsons, 5) >= scoreCompany(alsons, 1))
  assert.equal(alsons.financials.revenue, revenue)
})

test('health engine returns both statement groups', () => {
  const health = getHealthMetrics(INDUSTRIAL_COMPANIES[0], 3)
  assert.equal(health.pnl.length, 6)
  assert.equal(health.balance.length, 5)
})

test('portfolio calculates cost basis without inventing current value', () => {
  assert.equal(portfolioCostBasis([{ quantity: 100, purchasePrice: 25.5 }]), 2550)
})

test('portfolio calculates realized returns only for sold lots', () => {
  const result = portfolioRealizedReturn([
    { quantity: 100, purchasePrice: 20, salePrice: 25, saleDate: '2026-07-20' },
    { quantity: 50, purchasePrice: 10 },
  ])
  assert.deepEqual(result, { cost: 2000, proceeds: 2500, amount: 500, percent: 0.25 })
})

test('Smart Brief calls intrinsic value not a market quote', () => {
  const brief = buildSmartBrief(INDUSTRIAL_COMPANIES[1], 3, 'base', [])
  assert.match(brief.paragraphs.join(' '), /not a market quote/i)
})

test('optional history does not block the existing one-period valuation', () => {
  const company = INDUSTRIAL_COMPANIES[0]
  const history = getFinancialHistorySummary(company)
  const valuation = calculateValuation(company)

  assert.equal(history.annualCount, 1)
  assert.equal(history.quarterlyCount, 0)
  assert.equal(history.cashFlowBasisKey, 'legacy_estimate')
  assert.ok(Number.isFinite(valuation.primaryValue))
})

test('three consecutive annual cash-flow records automatically use their median', () => {
  const company = structuredClone(INDUSTRIAL_COMPANIES[0])
  company.financialHistory.annual = [
    { period: 'FY 2023', fiscalYear: 2023, periodEnd: '2023-12-31', valuationCashFlow: 30, cashFlowSource: 'primary_source_fact', source: { label: 'FY 2023 filing' } },
    { period: 'FY 2024', fiscalYear: 2024, periodEnd: '2024-12-31', valuationCashFlow: 50, cashFlowSource: 'primary_source_fact', source: { label: 'FY 2024 filing' } },
    { ...company.financials, period: 'FY 2025', fiscalYear: 2025, periodEnd: '2025-12-31', valuationCashFlow: 40, cashFlowSource: 'primary_source_fact', source: { label: 'FY 2025 filing' } },
  ]

  const dcf = calculateValuation(company).models.dcf
  assert.equal(dcf.normalizedFcf, 40)
  assert.equal(dcf.cashFlowBasis.key, 'three_year_median')
  assert.equal(getFinancialHistorySummary(company).annualCount, 3)
})

test('eight standalone quarters support TTM without adding overlapping annual values', () => {
  const company = structuredClone(INDUSTRIAL_COMPANIES[0])
  company.financialHistory.quarterly = []
  for (const year of [2025, 2026]) {
    for (let quarter = 1; quarter <= 4; quarter += 1) {
      company.financialHistory.quarterly.push({
        period: `Q${quarter} ${year}`,
        fiscalYear: year,
        fiscalQuarter: quarter,
        periodEnd: `${year}-${['03-31', '06-30', '09-30', '12-31'][quarter - 1]}`,
        valuationCashFlow: year === 2026 ? quarter * 10 : quarter,
        revenue: year === 2026 ? quarter * 100 : quarter * 10,
        eps: year === 2026 ? quarter / 10 : quarter / 100,
        cash: 100,
        debt: 40,
        liabilities: 80,
        equity: 120,
        preferredStock: 0,
        treasuryStock: 0,
        retainedEarnings: 50,
        shares: 10,
        cashFlowSource: 'primary_source_fact',
        source: { label: `${year} Q${quarter} filing` },
      })
    }
  }

  const dcf = calculateValuation(company).models.dcf
  const snapshot = getFinancialSnapshot(company)
  const history = getFinancialHistorySummary(company)

  assert.equal(history.quarterlyCount, 8)
  assert.equal(history.ttmAvailable, true)
  assert.equal(dcf.cashFlowBasis.key, 'ttm')
  assert.equal(dcf.normalizedFcf, 100)
  assert.equal(snapshot.periodType, 'ttm')
  assert.equal(snapshot.revenue, 1000)
})

test('history gaps and cumulative quarters warn but do not become required inputs', () => {
  const company = structuredClone(INDUSTRIAL_COMPANIES[0])
  company.financialHistory.quarterly = [
    { period: 'Q1 2025', fiscalYear: 2025, fiscalQuarter: 1, isCumulative: true, source: { label: 'Q1 filing' } },
    { period: 'Q3 2025', fiscalYear: 2025, fiscalQuarter: 3, source: { label: 'Q3 filing' } },
  ]

  const validation = validateFinancialHistory(company)
  const valuation = calculateValuation(company)
  assert.match(validation.warnings.join(' '), /gap/i)
  assert.match(validation.warnings.join(' '), /cumulative/i)
  assert.ok(Number.isFinite(valuation.primaryValue))
})
