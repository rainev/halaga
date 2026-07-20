import test from 'node:test'
import assert from 'node:assert/strict'
import { INDUSTRIAL_COMPANIES } from './data.js'
import { buildSmartBrief, calculateValuation, getHealthMetrics, portfolioCostBasis, portfolioRealizedReturn, scoreCompany } from './engine.js'

test('sentiment cases are ordered for every Industrial company', () => {
  for (const company of INDUSTRIAL_COMPANIES) {
    const bear = calculateValuation(company, 'bear').blended
    const base = calculateValuation(company, 'base').blended
    const bull = calculateValuation(company, 'bull').blended
    assert.ok(bear < base, `${company.symbol}: bear must be below base`)
    assert.ok(base < bull, `${company.symbol}: base must be below bull`)
  }
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
