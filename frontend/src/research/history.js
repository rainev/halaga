export const OPTIONAL_HISTORY_TARGETS = {
  annual: 3,
  quarterly: 8,
};

const FLOW_FIELDS = [
  "revenue",
  "grossProfit",
  "operatingIncome",
  "generalAdmin",
  "interestExpense",
  "pretaxIncome",
  "taxExpense",
  "netIncome",
  "parentNetIncome",
  "operatingCashFlow",
  "capitalExpenditure",
  "valuationCashFlow",
  "eps",
  "dividendPerShare",
];

const STOCK_FIELDS = [
  "cash",
  "debt",
  "liabilities",
  "equity",
  "retainedEarnings",
  "treasuryStock",
  "preferredStock",
  "nonControllingInterest",
  "shares",
];

const finite = (value) => Number.isFinite(value);

function yearFrom(record) {
  if (Number.isInteger(record?.fiscalYear)) return record.fiscalYear;
  const match = String(record?.period || "").match(/\b(20\d{2})\b/);
  return match ? Number(match[1]) : null;
}

function quarterFrom(record) {
  if (Number.isInteger(record?.fiscalQuarter)) return record.fiscalQuarter;
  const match = String(record?.period || "").match(/\bQ([1-4])\b/i);
  return match ? Number(match[1]) : null;
}

function annualKey(record) {
  const year = yearFrom(record);
  return year === null ? null : String(year);
}

function quarterlyKey(record) {
  const year = yearFrom(record);
  const quarter = quarterFrom(record);
  return year === null || quarter === null ? null : `${year}-Q${quarter}`;
}

function periodEnd(record, type) {
  if (record?.periodEnd && !Number.isNaN(Date.parse(record.periodEnd))) {
    return record.periodEnd;
  }
  const year = yearFrom(record);
  if (year === null) return null;
  if (type === "annual") return `${year}-12-31`;
  const quarter = quarterFrom(record);
  if (quarter === null) return null;
  const monthDay = ["03-31", "06-30", "09-30", "12-31"][quarter - 1];
  return `${year}-${monthDay}`;
}

function withPeriodMetadata(record, type, fallbackSource) {
  const year = yearFrom(record);
  const quarter = type === "quarterly" ? quarterFrom(record) : null;
  return {
    ...record,
    periodType: type,
    fiscalYear: year,
    ...(type === "quarterly" ? { fiscalQuarter: quarter } : {}),
    periodEnd: periodEnd(record, type),
    source: record?.source || fallbackSource || null,
  };
}

function uniquePeriods(records, type, fallbackSource) {
  const keyed = new Map();
  const invalid = [];
  const keyFor = type === "annual" ? annualKey : quarterlyKey;

  for (const record of records) {
    const normalized = withPeriodMetadata(record, type, fallbackSource);
    const key = keyFor(normalized);
    if (key === null) invalid.push(normalized);
    else keyed.set(key, normalized);
  }

  const valid = [...keyed.values()].sort((a, b) =>
    String(a.periodEnd).localeCompare(String(b.periodEnd)),
  );
  return { valid, invalid, duplicateCount: records.length - invalid.length - valid.length };
}

export function getFinancialHistory(company) {
  const configured = company?.financialHistory || {};
  const current = company?.financials
    ? [
        {
          ...company.financials,
          periodType: "annual",
          fiscalYear: yearFrom(company.financials),
          periodEnd: periodEnd(company.financials, "annual"),
          source: company.financials.source || company.source || null,
        },
      ]
    : [];

  // Configured records come last, so a filing-specific history record can
  // intentionally replace the legacy current snapshot for the same fiscal year.
  const annual = uniquePeriods(
    [...current, ...(Array.isArray(configured.annual) ? configured.annual : [])],
    "annual",
    company?.source,
  );
  const quarterly = uniquePeriods(
    Array.isArray(configured.quarterly) ? configured.quarterly : [],
    "quarterly",
    company?.source,
  );

  return {
    annual: annual.valid,
    quarterly: quarterly.valid,
    invalidAnnual: annual.invalid,
    invalidQuarterly: quarterly.invalid,
    duplicateAnnualCount: annual.duplicateCount,
    duplicateQuarterlyCount: quarterly.duplicateCount,
  };
}

function quarterIndex(record) {
  const year = yearFrom(record);
  const quarter = quarterFrom(record);
  return year === null || quarter === null ? null : year * 4 + quarter - 1;
}

function isConsecutive(records, indexFor) {
  if (records.length < 2) return true;
  return records.every((record, index) =>
    index === 0 || indexFor(record) === indexFor(records[index - 1]) + 1,
  );
}

function cashFlowValue(record) {
  if (finite(record?.valuationCashFlow)) return record.valuationCashFlow;
  if (finite(record?.freeCashFlow)) return record.freeCashFlow;
  if (finite(record?.operatingCashFlow) && finite(record?.capitalExpenditure)) {
    return record.operatingCashFlow - Math.abs(record.capitalExpenditure);
  }
  return null;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function latestFourQuarterCashFlow(quarterly) {
  const usable = quarterly.filter(
    (record) => record.isCumulative !== true && finite(cashFlowValue(record)),
  );
  if (usable.length < 4) return null;
  const latestFour = usable.slice(-4);
  if (!isConsecutive(latestFour, quarterIndex)) return null;
  return {
    value: latestFour.reduce((sum, record) => sum + cashFlowValue(record), 0),
    records: latestFour,
    periodEnd: latestFour.at(-1).periodEnd,
  };
}

function latestAnnualCashFlows(annual) {
  return annual
    .filter((record) => finite(cashFlowValue(record)))
    .map((record) => ({ ...record, cashFlowValue: cashFlowValue(record) }));
}

export function validateFinancialHistory(company) {
  const history = getFinancialHistory(company);
  const errors = [];
  const warnings = [];

  if (history.invalidAnnual.length) {
    errors.push("Annual history contains a record without a valid fiscal year.");
  }
  if (history.invalidQuarterly.length) {
    errors.push("Quarterly history contains a record without a valid fiscal year and quarter.");
  }
  if (history.duplicateAnnualCount) {
    warnings.push("A duplicate annual period was replaced by the last supplied record.");
  }
  if (history.duplicateQuarterlyCount) {
    warnings.push("A duplicate quarterly period was replaced by the last supplied record.");
  }
  if (
    history.annual.length > 1 &&
    !isConsecutive(history.annual, (record) => yearFrom(record))
  ) {
    warnings.push("Annual history has a gap; available periods remain usable.");
  }
  if (
    history.quarterly.length > 1 &&
    !isConsecutive(history.quarterly, quarterIndex)
  ) {
    warnings.push("Quarterly history has a gap; TTM is used only when the latest four quarters are complete.");
  }
  if (history.quarterly.some((record) => record.isCumulative === true)) {
    warnings.push("Cumulative year-to-date quarters are stored but excluded from TTM to prevent double counting.");
  }
  if (
    [...history.annual, ...history.quarterly].some(
      (record) => !record.source?.label,
    )
  ) {
    warnings.push("At least one period is missing a named filing source.");
  }

  return { ...history, errors, warnings };
}

function aggregateQuarterlySnapshot(records) {
  const latest = records.at(-1);
  const snapshot = {
    ...latest,
    period: `TTM through ${latest.period || `Q${latest.fiscalQuarter} ${latest.fiscalYear}`}`,
    periodType: "ttm",
    sourcePeriods: records.map((record) => record.period),
  };

  for (const field of FLOW_FIELDS) {
    const values = records.map((record) => record[field]);
    snapshot[field] = values.every(finite)
      ? values.reduce((sum, value) => sum + value, 0)
      : null;
  }
  for (const field of STOCK_FIELDS) {
    snapshot[field] = finite(latest[field]) ? latest[field] : null;
  }

  return snapshot;
}

export function getFinancialSnapshot(company) {
  const history = getFinancialHistory(company);
  const latestAnnual = history.annual.at(-1) || company.financials;
  const previousAnnual = history.annual.at(-2);
  const usableQuarters = history.quarterly.filter((record) => record.isCumulative !== true);
  const latestFour = usableQuarters.slice(-4);
  const hasCompleteTtm =
    latestFour.length === 4 && isConsecutive(latestFour, quarterIndex);
  const latestQuarterEnd = latestFour.at(-1)?.periodEnd;
  const annualEnd = latestAnnual?.periodEnd || periodEnd(latestAnnual, "annual");

  if (
    hasCompleteTtm &&
    latestQuarterEnd &&
    (!annualEnd || latestQuarterEnd > annualEnd)
  ) {
    const snapshot = aggregateQuarterlySnapshot(latestFour);
    const previousFour = usableQuarters.slice(-8, -4);
    if (
      previousFour.length === 4 &&
      isConsecutive(previousFour, quarterIndex) &&
      quarterIndex(latestFour[0]) === quarterIndex(previousFour.at(-1)) + 1
    ) {
      const previousEps = previousFour.map((record) => record.eps);
      snapshot.epsPrevious = previousEps.every(finite)
        ? previousEps.reduce((sum, value) => sum + value, 0)
        : null;
      snapshot.retainedEarningsPrevious = finite(previousFour.at(-1).retainedEarnings)
        ? previousFour.at(-1).retainedEarnings
        : null;
      snapshot.previousPeriod = `Previous TTM through ${previousFour.at(-1).period}`;
    }
    return snapshot;
  }
  return {
    ...latestAnnual,
    epsPrevious: finite(previousAnnual?.eps)
      ? previousAnnual.eps
      : latestAnnual?.epsPrevious,
    retainedEarningsPrevious: finite(previousAnnual?.retainedEarnings)
      ? previousAnnual.retainedEarnings
      : latestAnnual?.retainedEarningsPrevious,
    previousPeriod:
      previousAnnual?.period ||
      (yearFrom(latestAnnual) ? `FY ${yearFrom(latestAnnual) - 1}` : "previous period"),
  };
}

export function selectCashFlowBasis(company) {
  const validation = validateFinancialHistory(company);
  const annualCashFlows = latestAnnualCashFlows(validation.annual);
  const latestThree = annualCashFlows.slice(-3);
  const hasConsecutiveThreeYears =
    latestThree.length === 3 &&
    isConsecutive(latestThree, (record) => yearFrom(record));
  const ttm = latestFourQuarterCashFlow(validation.quarterly);
  const latestAnnualEnd = annualCashFlows.at(-1)?.periodEnd;
  const ttmIsNewer = ttm && (!latestAnnualEnd || ttm.periodEnd > latestAnnualEnd);
  const preference = company?.valuation?.cashFlowBasisPreference || "auto";
  const legacy = {
    value: company?.valuation?.normalizedFcf,
    key: "legacy_estimate",
    label: "Current normalized FCF estimate",
    periodCount: 1,
    source: company?.valuation?.cashFlowSource || "internal_estimate",
  };
  const annualMedian = hasConsecutiveThreeYears
    ? {
        value: median(latestThree.map((record) => record.cashFlowValue)),
        key: "three_year_median",
        label: "Median of latest 3 annual periods",
        periodCount: 3,
        source: latestThree.every(
          (record) => record.cashFlowSource === "primary_source_fact",
        )
          ? "primary_source_fact"
          : "mixed_or_derived",
      }
    : null;
  const ttmBasis = ttm
    ? {
        value: ttm.value,
        key: "ttm",
        label: "Latest 4 consecutive quarters (TTM)",
        periodCount: 4,
        source: ttm.records.every(
          (record) => record.cashFlowSource === "primary_source_fact",
        )
          ? "primary_source_fact"
          : "mixed_or_derived",
      }
    : null;
  const latestAnnual = annualCashFlows.length
    ? {
        value: annualCashFlows.at(-1).cashFlowValue,
        key: "latest_annual",
        label: `Latest annual period (${annualCashFlows.at(-1).period})`,
        periodCount: 1,
        source:
          annualCashFlows.at(-1).cashFlowSource ||
          company?.valuation?.cashFlowSource ||
          "mixed_or_derived",
      }
    : null;

  let selected;
  if (preference === "three_year_median") selected = annualMedian;
  else if (preference === "ttm") selected = ttmBasis;
  else if (preference === "latest_annual") selected = latestAnnual;
  else if (preference === "legacy_estimate") selected = legacy;
  else {
    selected =
      (ttmIsNewer ? ttmBasis : null) ||
      annualMedian ||
      ttmBasis ||
      latestAnnual ||
      legacy;
  }

  if (!selected || !finite(selected.value)) selected = legacy;

  return {
    ...selected,
    preference,
    history: {
      annualCount: validation.annual.length,
      quarterlyCount: validation.quarterly.length,
      annualTarget: OPTIONAL_HISTORY_TARGETS.annual,
      quarterlyTarget: OPTIONAL_HISTORY_TARGETS.quarterly,
      ttmAvailable: Boolean(ttm),
      errors: validation.errors,
      warnings: validation.warnings,
    },
  };
}

export function getFinancialHistorySummary(company) {
  const basis = selectCashFlowBasis(company);
  return {
    ...basis.history,
    cashFlowBasisKey: basis.key,
    cashFlowBasisLabel: basis.label,
    cashFlowPeriodCount: basis.periodCount,
  };
}
