import { PHILIPPINE_ASSUMPTIONS } from "./data/industrial.js";

export const RISK_PROFILES = {
  1: { label: "Capital Keeper", short: "Very cautious", tone: "Protect first" },
  2: { label: "Steady Builder", short: "Cautious", tone: "Prefer resilience" },
  3: { label: "Balanced Explorer", short: "Balanced", tone: "Balance quality and growth" },
  4: { label: "Growth Seeker", short: "Adventurous", tone: "Accept more variability" },
  5: { label: "High-Conviction", short: "Very adventurous", tone: "Accept substantial risk" },
};

export const SENTIMENTS = {
  bear: {
    label: "Bear",
    fcfGrowth: -0.015,
    discountRate: 0.015,
    terminalGrowth: -0.005,
    multipleFactor: 0.85,
    epsGrowthPoints: -1,
    dividendGrowth: -0.005,
  },
  base: {
    label: "Base",
    fcfGrowth: 0,
    discountRate: 0,
    terminalGrowth: 0,
    multipleFactor: 1,
    epsGrowthPoints: 0,
    dividendGrowth: 0,
  },
  bull: {
    label: "Bull",
    fcfGrowth: 0.015,
    discountRate: -0.01,
    terminalGrowth: 0.005,
    multipleFactor: 1.15,
    epsGrowthPoints: 1,
    dividendGrowth: 0.005,
  },
};

const THRESHOLDS = {
  1: {
    cashToDebt: 1,
    debtToEquity: 0.6,
    grossMargin: 0.45,
    sgnaToGrossProfit: 0.25,
    interestToOperatingIncome: 0.1,
    netMargin: 0.2,
    epsGrowth: 0.05,
    retainedGrowth: 0.03,
    taxTolerance: 0.04,
  },
  2: {
    cashToDebt: 0.75,
    debtToEquity: 0.8,
    grossMargin: 0.42,
    sgnaToGrossProfit: 0.28,
    interestToOperatingIncome: 0.15,
    netMargin: 0.18,
    epsGrowth: 0.02,
    retainedGrowth: 0.02,
    taxTolerance: 0.055,
  },
  3: {
    cashToDebt: 0.5,
    debtToEquity: 1,
    grossMargin: 0.4,
    sgnaToGrossProfit: 0.3,
    interestToOperatingIncome: 0.2,
    netMargin: 0.15,
    epsGrowth: 0,
    retainedGrowth: 0.01,
    taxTolerance: 0.07,
  },
  4: {
    cashToDebt: 0.3,
    debtToEquity: 1.3,
    grossMargin: 0.35,
    sgnaToGrossProfit: 0.35,
    interestToOperatingIncome: 0.3,
    netMargin: 0.12,
    epsGrowth: -0.1,
    retainedGrowth: 0,
    taxTolerance: 0.09,
  },
  5: {
    cashToDebt: 0.15,
    debtToEquity: 1.8,
    grossMargin: 0.3,
    sgnaToGrossProfit: 0.4,
    interestToOperatingIncome: 0.45,
    netMargin: 0.08,
    epsGrowth: -0.2,
    retainedGrowth: -0.05,
    taxTolerance: 0.12,
  },
};

export function getThresholds(risk) {
  const normalized = Math.min(5, Math.max(1, Number(risk) || 3));
  return { ...THRESHOLDS[normalized] };
}

export function getDerivedMetrics(company) {
  const f = company.financials;
  const safeDivide = (numerator, denominator) =>
    Number.isFinite(numerator) && Number.isFinite(denominator) && denominator !== 0
      ? numerator / denominator
      : null;

  return {
    cashToDebt: safeDivide(f.cash, f.debt),
    debtToEquity: safeDivide(f.liabilities, f.equity),
    grossMargin: safeDivide(f.grossProfit, f.revenue),
    operatingMargin: safeDivide(f.operatingIncome, f.revenue),
    sgnaToGrossProfit: safeDivide(f.generalAdmin, f.grossProfit),
    interestToOperatingIncome: safeDivide(f.interestExpense, f.operatingIncome),
    effectiveTaxRate: safeDivide(f.taxExpense, f.pretaxIncome),
    netMargin: safeDivide(f.netIncome, f.revenue),
    epsGrowth: safeDivide(f.eps - f.epsPrevious, Math.abs(f.epsPrevious)),
    retainedGrowth:
      f.retainedEarnings === null || f.retainedEarningsPrevious === null
        ? null
        : safeDivide(
            f.retainedEarnings - f.retainedEarningsPrevious,
            Math.abs(f.retainedEarningsPrevious),
          ),
  };
}

function compareMetric(value, target, direction, tolerance = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return { status: "unavailable", score: 0.55 };
  }
  if (direction === "range") {
    const distance = Math.abs(value - target);
    return {
      status: distance <= tolerance ? "pass" : "watch",
      score: Math.max(0, 1 - distance / Math.max(tolerance * 2.5, 0.01)),
    };
  }
  if (direction === "context") return { status: "context", score: 0.7 };
  const pass = direction === "min" ? value >= target : value <= target;
  let score;
  if (target === 0) score = pass ? 1 : 0;
  else if (direction === "min" && target < 0) score = pass ? 1 : Math.max(0, 1 - (target - value) * 3);
  else if (direction === "min") score = Math.min(1.1, Math.max(0, value / target));
  else score = value === 0 ? 1.1 : Math.min(1.1, Math.max(0, target / value));
  return { status: pass ? "pass" : "watch", score };
}

export function getHealthMetrics(company, risk = 3) {
  const thresholds = getThresholds(risk);
  const d = getDerivedMetrics(company);
  const f = company.financials;

  const pnl = [
    {
      key: "grossMargin",
      label: "Gross margin",
      description: "Gross profit kept from each peso of revenue",
      value: d.grossMargin,
      target: thresholds.grossMargin,
      direction: "min",
      format: "percent",
    },
    {
      key: "sgnaToGrossProfit",
      label: "G&A load",
      description: "General and administrative cost as a share of gross profit",
      value: d.sgnaToGrossProfit,
      target: thresholds.sgnaToGrossProfit,
      direction: "max",
      format: "percent",
    },
    {
      key: "interestToOperatingIncome",
      label: "Interest burden",
      description: "Financing cost compared with operating income",
      value: d.interestToOperatingIncome,
      target: thresholds.interestToOperatingIncome,
      direction: "max",
      format: "percent",
    },
    {
      key: "effectiveTaxRate",
      label: "Effective tax rate",
      description: "Compared with the 25% Philippine corporate-tax reference",
      value: d.effectiveTaxRate,
      target: PHILIPPINE_ASSUMPTIONS.corporateTaxReference,
      direction: "range",
      tolerance: thresholds.taxTolerance,
      format: "percent",
    },
    {
      key: "netMargin",
      label: "Net margin",
      description: "Profit left from each peso of revenue",
      value: d.netMargin,
      target: thresholds.netMargin,
      direction: "min",
      format: "percent",
    },
    {
      key: "epsGrowth",
      label: "EPS direction",
      description: `PHP${f.eps.toFixed(f.eps < 1 ? 3 : 2)} in 2025 vs PHP${f.epsPrevious.toFixed(f.epsPrevious < 1 ? 3 : 2)} in 2024`,
      value: d.epsGrowth,
      target: thresholds.epsGrowth,
      direction: "min",
      format: "percent",
    },
  ];

  const balance = [
    {
      key: "cashToDebt",
      label: "Cash coverage",
      description: "Cash and equivalents compared with interest-bearing debt",
      value: d.cashToDebt,
      target: thresholds.cashToDebt,
      direction: "min",
      format: "multiple",
    },
    {
      key: "debtToEquity",
      label: "Liabilities to equity",
      description: "Total liabilities compared with total equity",
      value: d.debtToEquity,
      target: thresholds.debtToEquity,
      direction: "max",
      format: "multiple",
    },
    {
      key: "preferredStock",
      label: "Preferred stock",
      description: "No preferred stock separately reported in the reviewed balance sheet",
      value: f.preferredStock,
      target: 0,
      direction: "max",
      format: "currency",
    },
    {
      key: "retainedGrowth",
      label: "Retained earnings growth",
      description: "Change in accumulated earnings available to support the business",
      value: d.retainedGrowth,
      target: thresholds.retainedGrowth,
      direction: "min",
      format: "percent",
    },
    {
      key: "treasuryStock",
      label: "Treasury stock",
      description: f.treasuryStock > 0 ? "Repurchased shares are present" : "No treasury stock reported",
      value: f.treasuryStock,
      target: null,
      direction: "context",
      format: "currency",
    },
  ];

  for (const metric of [...pnl, ...balance]) {
    Object.assign(
      metric,
      compareMetric(metric.value, metric.target, metric.direction, metric.tolerance),
    );
  }

  return { pnl, balance, thresholds, derived: d };
}

export function scoreCompany(company, risk = 3) {
  const { pnl, balance } = getHealthMetrics(company, risk);
  const weights = {
    grossMargin: 1.1,
    sgnaToGrossProfit: 0.7,
    interestToOperatingIncome: 1.15,
    effectiveTaxRate: 0.35,
    netMargin: 1.2,
    epsGrowth: 1,
    cashToDebt: 1.1,
    debtToEquity: 1.2,
    preferredStock: 0.25,
    retainedGrowth: 0.7,
    treasuryStock: 0.2,
  };
  const metrics = [...pnl, ...balance];
  const totalWeight = metrics.reduce((sum, metric) => sum + weights[metric.key], 0);
  const health = metrics.reduce(
    (sum, metric) => sum + Math.min(1, metric.score) * weights[metric.key],
    0,
  );
  return Math.round((health / totalWeight) * 88 + company.dataConfidence * 12);
}

export function calculateDCF(company, sentiment = "base") {
  const v = company.valuation;
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const growth = Math.max(-0.05, Math.min(0.15, v.fcfGrowth + adjustment.fcfGrowth));
  const terminalGrowth = Math.max(0, v.terminalGrowth + adjustment.terminalGrowth);
  const discountRate = Math.max(
    terminalGrowth + 0.025,
    v.discountRate + adjustment.discountRate,
  );
  let presentValue = 0;
  let futureFcf = v.normalizedFcf;
  for (let year = 1; year <= 5; year += 1) {
    futureFcf *= 1 + growth;
    presentValue += futureFcf / (1 + discountRate) ** year;
  }
  const terminalValue =
    (futureFcf * (1 + terminalGrowth)) / (discountRate - terminalGrowth);
  const enterpriseValue = presentValue + terminalValue / (1 + discountRate) ** 5;
  const netDebt = company.financials.debt - company.financials.cash;
  const equityValue = enterpriseValue - netDebt;
  return {
    perShare: Math.max(0, equityValue / company.financials.shares),
    enterpriseValue,
    equityValue,
    growth,
    terminalGrowth,
    discountRate,
    normalizedFcf: v.normalizedFcf,
  };
}

export function calculateGraham(company, sentiment = "base") {
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const growthPercent = Math.max(
    0,
    company.valuation.epsGrowthPercent + adjustment.epsGrowthPoints,
  );
  const value =
    company.financials.eps *
    (8.5 + 2 * growthPercent) *
    (PHILIPPINE_ASSUMPTIONS.grahamBaselineYield / PHILIPPINE_ASSUMPTIONS.riskFreeRate);
  return { perShare: Math.max(0, value), growthPercent };
}

export function calculateMultiples(company, sentiment = "base") {
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const peerPe = company.valuation.peerPe * adjustment.multipleFactor;
  return { perShare: company.financials.eps * peerPe, peerPe };
}

export function calculateDDM(company, sentiment = "base") {
  if (!Number.isFinite(company.valuation.dividendPerShare)) return null;
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const growth = Math.max(0, company.valuation.dividendGrowth + adjustment.dividendGrowth);
  const discountRate = Math.max(
    growth + 0.02,
    company.valuation.dividendDiscountRate + adjustment.discountRate,
  );
  const nextDividend = company.valuation.dividendPerShare * (1 + growth);
  return { perShare: nextDividend / (discountRate - growth), growth, discountRate };
}

export function calculateValuation(company, sentiment = "base") {
  const models = {
    dcf: calculateDCF(company, sentiment),
    graham: calculateGraham(company, sentiment),
    multiples: calculateMultiples(company, sentiment),
    ddm: calculateDDM(company, sentiment),
  };
  let weightedValue = 0;
  let activeWeight = 0;
  for (const [key, result] of Object.entries(models)) {
    const weight = company.valuation.weights[key] || 0;
    if (result && Number.isFinite(result.perShare) && weight > 0) {
      weightedValue += result.perShare * weight;
      activeWeight += weight;
    }
  }
  const values = Object.values(models)
    .filter(Boolean)
    .map((model) => model.perShare);
  return {
    blended: activeWeight ? weightedValue / activeWeight : 0,
    low: Math.min(...values),
    high: Math.max(...values),
    models,
  };
}

export function portfolioCostBasis(lots = []) {
  return lots.reduce(
    (total, lot) => total + Number(lot.quantity || 0) * Number(lot.purchasePrice || 0),
    0,
  );
}

export function buildSmartBrief(company, risk = 3, sentiment = "base", lots = []) {
  const profile = RISK_PROFILES[risk] || RISK_PROFILES[3];
  const health = getHealthMetrics(company, risk);
  const metrics = [...health.pnl, ...health.balance].filter(
    (metric) => metric.status !== "context" && metric.status !== "unavailable",
  );
  const passes = metrics.filter((metric) => metric.status === "pass");
  const watches = metrics.filter((metric) => metric.status === "watch");
  const valuation = calculateValuation(company, sentiment);
  const score = scoreCompany(company, risk);
  const companyLots = lots.filter((lot) => lot.symbol === company.symbol);
  const invested = portfolioCostBasis(companyLots);
  const topPass = passes.sort((a, b) => b.score - a.score)[0];
  const topWatch = watches.sort((a, b) => a.score - b.score)[0];

  let stance = "Needs a closer look";
  if (score >= 78) stance = "Stronger fundamentals in this test group";
  else if (score >= 65) stance = "Mixed, with investable strengths";

  const paragraphs = [
    `${company.shortName} clears ${passes.length} of ${metrics.length} available checks for a ${profile.short.toLowerCase()} investor. ${topPass ? `${topPass.label} is a relative strength.` : "No single metric leads the case."} ${topWatch ? `${topWatch.label} is the first item to investigate.` : "No major threshold miss appears in the available set."}`,
    `Under the ${SENTIMENTS[sentiment].label.toLowerCase()} case, the filing-based models center on PHP${valuation.blended.toFixed(2)} per share, with a PHP${valuation.low.toFixed(2)}-PHP${valuation.high.toFixed(2)} range. This is an intrinsic-value estimate, not a market quote.`,
    invested > 0
      ? `Your organizer contains ${companyLots.length} ${company.symbol} lot${companyLots.length === 1 ? "" : "s"} with PHP${Math.round(invested).toLocaleString("en-PH")} invested at cost. Current value and profit/loss stay blank because the app does not publish live prices.`
      : `You have no ${company.symbol} lot in the organizer yet. If you add one, this brief will include your quantity and cost basis without estimating a current market value.`,
  ];

  return {
    headline: stance,
    score,
    paragraphs,
    passLabels: passes.slice(0, 3).map((metric) => metric.label),
    watchLabels: watches.slice(0, 3).map((metric) => metric.label),
  };
}
