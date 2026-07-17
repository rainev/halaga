import test from "node:test";
import assert from "node:assert/strict";
import { INDUSTRIAL_COMPANIES } from "../src/data/industrial.js";
import {
  buildSmartBrief,
  calculateValuation,
  getHealthMetrics,
  getThresholds,
  portfolioCostBasis,
  scoreCompany,
} from "../src/engine.js";

test("bear, base, and bull cases remain ordered", () => {
  for (const company of INDUSTRIAL_COMPANIES) {
    const bear = calculateValuation(company, "bear").blended;
    const base = calculateValuation(company, "base").blended;
    const bull = calculateValuation(company, "bull").blended;
    assert.ok(bear < base, `${company.symbol}: bear should be below base`);
    assert.ok(base < bull, `${company.symbol}: base should be below bull`);
  }
});

test("risk thresholds loosen from level 1 to level 5", () => {
  const cautious = getThresholds(1);
  const adventurous = getThresholds(5);
  assert.ok(cautious.cashToDebt > adventurous.cashToDebt);
  assert.ok(cautious.debtToEquity < adventurous.debtToEquity);
  assert.ok(cautious.netMargin > adventurous.netMargin);
});

test("more risk tolerance never lowers Alsons' screening score", () => {
  const alsons = INDUSTRIAL_COMPANIES.find((company) => company.symbol === "ACR");
  assert.ok(scoreCompany(alsons, 5) >= scoreCompany(alsons, 1));
});

test("health engine returns both metric groups", () => {
  const health = getHealthMetrics(INDUSTRIAL_COMPANIES[0], 3);
  assert.equal(health.pnl.length, 6);
  assert.equal(health.balance.length, 5);
});

test("portfolio organizer calculates cost basis only", () => {
  const cost = portfolioCostBasis([
    { quantity: 100, purchasePrice: 31.5 },
    { quantity: 20, purchasePrice: 40 },
  ]);
  assert.equal(cost, 3950);
});

test("Smart Brief is explicit about the missing market quote", () => {
  const brief = buildSmartBrief(INDUSTRIAL_COMPANIES[1], 3, "base", []);
  assert.match(brief.paragraphs.join(" "), /not a market quote/i);
  assert.ok(brief.paragraphs.join(" ").length < 1200);
});
