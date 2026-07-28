import { PHILIPPINE_ASSUMPTIONS } from "./data.js";
import {
  getFinancialHistorySummary,
  getFinancialSnapshot,
  selectCashFlowBasis,
  validateFinancialHistory,
} from "./history.js";

export {
  getFinancialHistorySummary,
  getFinancialSnapshot,
  validateFinancialHistory,
};

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

export const VALUATION_CONTROLS = {
  minimumRateGrowthSpread: 0.03,
  maximumTerminalGrowth: 0.04,
  terminalValueWarningShare: 0.75,
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
  const f = getFinancialSnapshot(company);
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
  const f = getFinancialSnapshot(company);

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
      description:
        Number.isFinite(f.eps) && Number.isFinite(f.epsPrevious)
          ? `PHP${f.eps.toFixed(f.eps < 1 ? 3 : 2)} in ${f.period} vs PHP${f.epsPrevious.toFixed(f.epsPrevious < 1 ? 3 : 2)} in ${f.previousPeriod}`
          : "Current EPS compared with the previous comparable period",
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
  const f = getFinancialSnapshot(company);
  const cashFlowBasis = selectCashFlowBasis(company);
  const normalizedFcf = cashFlowBasis.value;
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const growth = v.fcfGrowth + adjustment.fcfGrowth;
  const terminalGrowth = v.terminalGrowth + adjustment.terminalGrowth;
  const discountRate = v.discountRate + adjustment.discountRate;
  const cashFlowType = v.cashFlowType || "unknown";
  const errors = [];
  const warnings = [];

  if (!Number.isFinite(normalizedFcf) || normalizedFcf <= 0) {
    errors.push("Normalized cash flow must be a positive, documented amount.");
  }
  if (!["fcff", "fcfe"].includes(cashFlowType)) {
    errors.push("Cash flow must be identified as FCFF or FCFE before valuation.");
  }
  if (!Number.isFinite(discountRate) || !Number.isFinite(terminalGrowth)) {
    errors.push("Discount rate and terminal growth must be finite numbers.");
  } else {
    if (discountRate <= terminalGrowth) {
      errors.push("Discount rate must exceed terminal growth.");
    } else if (
      discountRate - terminalGrowth + 1e-12 <
      VALUATION_CONTROLS.minimumRateGrowthSpread
    ) {
      errors.push("Discount rate must exceed terminal growth by at least 3 percentage points.");
    }
    if (terminalGrowth > VALUATION_CONTROLS.maximumTerminalGrowth) {
      errors.push("Terminal growth above 4% requires a separately approved scenario.");
    }
  }
  if (!Number.isFinite(growth) || growth <= -1) {
    errors.push("Forecast growth must be finite and greater than -100%.");
  }
  if (cashFlowBasis.source !== "primary_source_fact") {
    warnings.push("Normalized cash flow is an internal estimate, not a filing-tied FCFF schedule.");
  }
  warnings.push(
    ...cashFlowBasis.history.errors.map((issue) => `Optional history ignored: ${issue}`),
    ...cashFlowBasis.history.warnings,
  );
  if (cashFlowType === "fcff" && v.bridgeComplete !== true) {
    warnings.push("The enterprise-to-equity bridge has not been confirmed for all material claims.");
  }

  if (errors.length) {
    return {
      perShare: null,
      enterpriseValue: null,
      equityValue: null,
      growth,
      terminalGrowth,
      discountRate,
      normalizedFcf,
      cashFlowBasis,
      cashFlowType,
      terminalValueShare: null,
      status: "blocked",
      errors,
      warnings,
    };
  }

  let presentValue = 0;
  let futureFcf = normalizedFcf;
  for (let year = 1; year <= 5; year += 1) {
    futureFcf *= 1 + growth;
    presentValue += futureFcf / (1 + discountRate) ** year;
  }
  const terminalValue =
    (futureFcf * (1 + terminalGrowth)) / (discountRate - terminalGrowth);
  const presentValueOfTerminal =
    terminalValue / (1 + discountRate) ** 5;
  const enterpriseValue = presentValue + presentValueOfTerminal;
  const netDebt = f.debt - f.cash;
  const preferredStock = f.preferredStock || 0;
  const nonControllingInterest = f.nonControllingInterest || 0;
  const equityValue =
    cashFlowType === "fcfe"
      ? presentValue + presentValueOfTerminal
      : enterpriseValue - netDebt - preferredStock - nonControllingInterest;
  const terminalValueShare =
    enterpriseValue !== 0 ? presentValueOfTerminal / enterpriseValue : null;
  if (
    terminalValueShare !== null &&
    terminalValueShare > VALUATION_CONTROLS.terminalValueWarningShare
  ) {
    warnings.push("Terminal value exceeds 75% of enterprise value.");
  }
  return {
    perShare: equityValue / f.shares,
    enterpriseValue,
    equityValue,
    growth,
    terminalGrowth,
    discountRate,
    normalizedFcf,
    cashFlowBasis,
    cashFlowType,
    terminalValue,
    presentValueOfTerminal,
    terminalValueShare,
    status: warnings.length ? "review" : "pass",
    errors,
    warnings,
  };
}

export function calculateGraham(company, sentiment = "base") {
  const f = getFinancialSnapshot(company);
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const growthPercent = Math.max(
    0,
    company.valuation.epsGrowthPercent + adjustment.epsGrowthPoints,
  );
  const value =
    f.eps *
    (8.5 + 2 * growthPercent) *
    (PHILIPPINE_ASSUMPTIONS.grahamBaselineYield /
      PHILIPPINE_ASSUMPTIONS.localGovernmentYield);
  return {
    perShare: value,
    growthPercent,
    status: "diagnostic",
    errors: [],
    warnings: ["Graham is an educational diagnostic, not a headline valuation method."],
  };
}

export function calculateMultiples(company, sentiment = "base") {
  const f = getFinancialSnapshot(company);
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const peerPe = company.valuation.peerPe * adjustment.multipleFactor;
  if (!Number.isFinite(f.eps) || f.eps <= 0) {
    return {
      perShare: null,
      peerPe,
      status: "blocked",
      errors: ["P/E cannot be applied when target EPS is zero or negative."],
      warnings: [],
    };
  }
  return {
    perShare: f.eps * peerPe,
    peerPe,
    status: "review",
    errors: [],
    warnings: ["The current app stores one benchmark P/E, not a validated four-peer set."],
  };
}

export function calculateDDM(company, sentiment = "base") {
  if (!Number.isFinite(company.valuation.dividendPerShare)) return null;
  const adjustment = SENTIMENTS[sentiment] || SENTIMENTS.base;
  const growth = company.valuation.dividendGrowth + adjustment.dividendGrowth;
  const discountRate =
    company.valuation.dividendDiscountRate + adjustment.discountRate;
  const errors = [];
  if (discountRate <= growth) {
    errors.push("Dividend discount rate must exceed dividend growth.");
  } else if (
    discountRate - growth + 1e-12 <
    VALUATION_CONTROLS.minimumRateGrowthSpread
  ) {
    errors.push("Dividend discount rate must exceed growth by at least 3 percentage points.");
  }
  if (growth > VALUATION_CONTROLS.maximumTerminalGrowth) {
    errors.push("Perpetual dividend growth above 4% is not approved.");
  }
  if (errors.length) {
    return {
      perShare: null,
      growth,
      discountRate,
      status: "blocked",
      errors,
      warnings: [],
    };
  }
  const nextDividend = company.valuation.dividendPerShare * (1 + growth);
  return {
    perShare: nextDividend / (discountRate - growth),
    growth,
    discountRate,
    status: "review",
    errors: [],
    warnings: ["Use DDM only when dividends are supported by a stable payout policy."],
  };
}

export function calculateResidualIncome(company, sentiment = "base") {
  const scenario = company?.valuation?.bank?.scenarios?.[sentiment];
  if (!scenario || !Number.isFinite(scenario.intrinsic_value)) {
    return {
      perShare: null,
      status: "blocked",
      errors: ["A source-traceable bank residual-income scenario is unavailable."],
      warnings: [],
    };
  }
  return {
    perShare: scenario.intrinsic_value,
    costOfEquity: scenario.detail.cost_of_equity,
    currentRoe: scenario.detail.current_roe,
    terminalRoe: scenario.detail.terminal_roe,
    terminalGrowth: scenario.detail.terminal_growth,
    payoutRatio: scenario.detail.current_payout_ratio,
    bookValuePerShare: scenario.detail.book_value_per_share,
    schedule: scenario.detail.schedule,
    status: scenario.validation?.status || "review",
    errors: [],
    warnings: scenario.validation?.warnings || [],
  };
}

export function calculateBankDdm(company, sentiment = "base") {
  const scenario = company?.valuation?.bank?.scenarios?.[sentiment];
  const value = scenario?.detail?.ddm_cross_check;
  if (!Number.isFinite(value)) return null;
  return {
    perShare: value,
    costOfEquity: scenario.detail.cost_of_equity,
    terminalGrowth: scenario.detail.terminal_growth,
    status: "review",
    errors: [],
    warnings: [
      "This DDM uses the same clean-surplus earnings and payout path as residual income.",
    ],
  };
}

export function calculateJustifiedPb(company, sentiment = "base") {
  const scenario = company?.valuation?.bank?.scenarios?.[sentiment];
  const value = scenario?.detail?.justified_pb_value;
  if (!Number.isFinite(value)) return null;
  return {
    perShare: value,
    multiple: scenario.detail.justified_pb_multiple,
    status: "review",
    errors: [],
    warnings: ["Stable-state justified P/B is not a live peer-market multiple."],
  };
}

export function calculateValuation(company, sentiment = "base") {
  const policy = company.valuation.modelPolicy || {
    primary: "dcf",
    crossChecks: ["multiples"],
    publishable: true,
  };
  const isBank = policy.primary === "residual_income";
  const models = isBank
    ? {
        residual_income: calculateResidualIncome(company, sentiment),
        ddm: calculateBankDdm(company, sentiment),
        justified_pb: calculateJustifiedPb(company, sentiment),
      }
    : {
        dcf: calculateDCF(company, sentiment),
        graham: calculateGraham(company, sentiment),
        multiples: calculateMultiples(company, sentiment),
        ddm: calculateDDM(company, sentiment),
      };
  const primary = models[policy.primary] || null;
  const policyWarnings = [...(policy.warnings || [])];
  const blockedByPolicy = policy.publishable === false;
  const blockedByModel =
    !primary || primary.status === "blocked" || !Number.isFinite(primary.perShare);
  const status = blockedByPolicy || blockedByModel
    ? "blocked"
    : primary.status === "review" || policyWarnings.length
      ? "review"
      : "pass";

  const scenarioValues = blockedByPolicy
    ? []
    : ["bear", "base", "bull"]
        .map((caseName) => {
          const result = policy.primary === "dcf"
            ? calculateDCF(company, caseName)
            : policy.primary === "residual_income"
              ? calculateResidualIncome(company, caseName)
              : models[policy.primary];
          return result && Number.isFinite(result.perShare) ? result.perShare : null;
        })
        .filter((value) => value !== null);

  return {
    primaryModel: policy.primary,
    primaryValue: status === "blocked" ? null : primary.perShare,
    scenarioLow: scenarioValues.length ? Math.min(...scenarioValues) : null,
    scenarioHigh: scenarioValues.length ? Math.max(...scenarioValues) : null,
    crossChecks: policy.crossChecks || [],
    status,
    policyReason: policy.reason || "",
    warnings: [...policyWarnings, ...(primary?.warnings || [])],
    errors: [
      ...(blockedByPolicy ? [policy.blockReason || "Required primary method is not implemented."] : []),
      ...(primary?.errors || []),
    ],
    models,
  };
}

export function portfolioCostBasis(lots = []) {
  return lots.reduce(
    (total, lot) => total + Number(lot.quantity || 0) * Number(lot.purchasePrice || 0),
    0,
  );
}

export function portfolioRealizedReturn(lots = []) {
  const soldLots = lots.filter(
    (lot) => Number(lot.salePrice) > 0 && Boolean(lot.saleDate),
  );
  const cost = portfolioCostBasis(soldLots);
  const proceeds = soldLots.reduce(
    (total, lot) => total + Number(lot.quantity || 0) * Number(lot.salePrice || 0),
    0,
  );
  const amount = proceeds - cost;
  return {
    cost,
    proceeds,
    amount,
    percent: cost > 0 ? amount / cost : 0,
  };
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
  const openCompanyLots = companyLots.filter(
    (lot) => !(Number(lot.salePrice) > 0 && lot.saleDate),
  );
  const invested = portfolioCostBasis(openCompanyLots);
  const topPass = passes.sort((a, b) => b.score - a.score)[0];
  const topWatch = watches.sort((a, b) => a.score - b.score)[0];

  let stance = "Needs a closer look";
  if (score >= 78) stance = "Stronger fundamentals in this test group";
  else if (score >= 65) stance = "Mixed, with investable strengths";

  const valuationSentence =
    valuation.primaryValue === null
      ? `The ${SENTIMENTS[sentiment].label.toLowerCase()} valuation is withheld because ${valuation.errors[0] || "the primary method did not pass validation"}. Diagnostic model outputs remain available for review, but they are not blended.`
      : `Under the ${SENTIMENTS[sentiment].label.toLowerCase()} case, the primary ${valuation.primaryModel.toUpperCase()} estimate is PHP${valuation.primaryValue.toFixed(2)} per share, with a PHP${valuation.scenarioLow.toFixed(2)}-PHP${valuation.scenarioHigh.toFixed(2)} scenario range. Cross-checks are shown separately and are never averaged into the headline.`;

  const paragraphs = [
    `${company.shortName} clears ${passes.length} of ${metrics.length} available checks for a ${profile.short.toLowerCase()} investor. ${topPass ? `${topPass.label} is a relative strength.` : "No single metric leads the case."} ${topWatch ? `${topWatch.label} is the first item to investigate.` : "No major threshold miss appears in the available set."}`,
    `${valuationSentence} This is a model estimate, not a market quote or recommendation.`,
    invested > 0
      ? `Your organizer contains ${openCompanyLots.length} open ${company.symbol} lot${openCompanyLots.length === 1 ? "" : "s"} with PHP${Math.round(invested).toLocaleString("en-PH")} invested at cost. Current value stays blank because the app does not publish live prices.`
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
