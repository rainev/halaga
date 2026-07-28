# PSE Valuation Engine Framework - Consolidated Production Standard

**Version:** 2.0
**Prepared:** July 2026
**Purpose:** A sector-aware, auditable valuation methodology for a software application covering Philippine Stock Exchange (PSE) issuers.

This document is a calculation and implementation standard. It is not an investment recommendation, fairness opinion, or guarantee of market value. Automated results are screening estimates conditioned on public information and stated assumptions. Unusual issuers, restatements, material proxy use, and low-confidence results require human review before external publication.

## 1. Governing Principles

1. **The PSE subsector determines the default model family, not the final answer.** Company-specific economics, financial structure, data quality, and business mix may override the default.
2. **Match the discount rate to the cash flow.** Use WACC for FCFF and enterprise-value models; use cost of equity for FCFE, dividends, residual income, and other equity-value models.
3. **Triangulate.** Run one primary model and at least one suitable supporting method when data permits.
4. **Do not force invalid models.** Negative denominators, missing operating data, unstable margins, stale prices, or unavailable reserve/property data must trigger a documented fallback.
5. **Do not manufacture false precision.** Publish a range and confidence grade. Withhold a blended point estimate when valid models materially disagree.
6. **Preserve source lineage.** Every reported fact, normalization, proxy, and assumption must retain a source reference and effective date.
7. **Separate reported facts from estimates.** Never overwrite a filed amount with a normalized or estimated amount.
8. **Use current classifications.** PSE classifications, listings, and company structures can change. Store the classification source and effective date.

## 2. Data, Frequency, and Provenance

### 2.1 Public-data source hierarchy

| Priority | Source | Typical fields |
|---:|---|---|
| 1 | Audited annual financial statements and annual report | Three-statement history, notes, segments, debt, leases, shares, related parties |
| 2 | Quarterly/interim financial statements | Current-year earnings, cash flow, balance sheet, debt, segment updates |
| 3 | MD&A, earnings releases, technical and operating reports | Operational KPIs, project pipeline, production, subscribers, occupancy, guidance |
| 4 | PSE EDGE disclosures | Filings, corporate actions, dividends, shares, material events |
| 5 | BSP, BTr, ERC, DOE, MGB, PAGCOR and other public authorities | Prudential ratios, rates, tariffs, permits, capacity, reserves, regulation |
| 6 | Authorized market-data source | Closing price, trading date, volume and peer-market inputs |

The engine may calculate derived values from licensed or otherwise permitted inputs. Data access, storage, scraping, reproduction, and publication rights remain separate compliance matters and must be reviewed independently.

### 2.2 Annual and quarterly consolidation

- Store annual and quarterly facts separately.
- Never add a full-year amount to quarters already contained in that year.
- For flow items, calculate TTM only from four consecutive, non-overlapping quarters.
- For balance-sheet items, use the latest period-end balance; never sum quarterly balances.
- Use annual history for normalized margins, reinvestment, cyclicality, and terminal assumptions.
- Use quarterly history for seasonality, current run-rate, and recent inflections.
- With three annual years and eight quarters, treat the forecast as **screening-grade**: use conservative mean reversion, disclose limited history, and widen sensitivities.
- If quarterly cash-flow statements are year-to-date, derive stand-alone quarters before constructing TTM:

```text
Standalone Q2 = YTD Q2 - Q1
Standalone Q3 = YTD Q3 - YTD Q2
Standalone Q4 = FY - YTD Q3
TTM flow = latest four stand-alone quarters
```

- Retain the latest restated comparative series and mark earlier values as superseded.
- Align differing fiscal year-ends before peer comparisons.

### 2.3 Share-count and market-value rules

```text
Basic Market Capitalization = Closing Price x Current Basic Shares Outstanding
Fully Diluted Equity Value per Share = Equity Value / Fully Diluted Shares
```

- Use current basic shares outstanding for conventional market capitalization.
- Use fully diluted shares for intrinsic per-share value when options, convertibles, or other dilutive instruments are material.
- Use weighted-average diluted shares only for period EPS.
- Adjust historical per-share data for splits, consolidations, and similar corporate actions.
- Store price date, price source, trading status, and staleness flag.

## 3. Philippine Discount-Rate and Terminal Policy

### 3.1 Cost of equity

```text
Ke = Rf_PH + Beta_bottom_up x ERP_PH + Explicit Risk Overlay
```

Where:

- `Rf_PH` is a Philippine peso government-bond yield matched to the valuation duration, normally the 10-year benchmark for a long-lived equity valuation.
- `Beta_bottom_up` is the median unlevered beta of economically comparable businesses, relevered to the target's sustainable capital structure.
- `ERP_PH` is a documented Philippine equity-risk premium. It may be an implied Philippine ERP or a mature-market ERP plus a country-risk component.
- `Explicit Risk Overlay` is optional. It may address material size, liquidity, concentration, governance, or project risk only when the factor is not already captured elsewhere.

Do not automatically add both a Philippine country-risk premium and a Philippine ERP that already includes country risk. Do not automatically apply a fixed SME or illiquidity premium. Any overlay must be documented, capped by policy, sensitivity-tested, and reviewed for double counting.

Beta relevering:

```text
Beta_levered = Beta_unlevered x [1 + (1 - Tax Rate) x Debt / Equity]
```

For financial institutions, use an equity-side cost of equity and avoid generic debt/equity relevering when deposits and other funding are operating inputs.

### 3.2 Cost of debt and WACC

Use the current marginal pre-tax borrowing cost, not a stale historical coupon. Preferred public proxies, in order:

1. Current effective borrowing rate disclosed by the company.
2. Yield or coupon on recently issued comparable company debt.
3. Philippine government yield of matching tenor plus a defensible issuer or sector spread.
4. Disclosed weighted-average borrowing cost, if reasonably current.
5. Interest expense divided by average interest-bearing debt as a low-confidence fallback.

```text
WACC = E/V x Ke + D/V x Kd x (1 - Tax Rate) + P/V x Kp
V = E + D + P
```

`E`, `D`, and `P` must be measured consistently. Include lease liabilities, preferred equity, and non-controlling interests in valuation bridges or capital structure when material and consistent with the cash flows and peer definitions.

### 3.3 Terminal value

```text
TV_Gordon = Cash Flow_(n+1) / (Discount Rate - g)
TV_Exit = Steady-state Metric_n x Defensible Exit Multiple
```

Controls:

- `g` must be below the applicable discount rate by a policy buffer.
- Long-run growth must not exceed a defensible sustainable nominal growth rate for the Philippine economy and the company's mature sector.
- Reinvestment and return on invested capital must support the terminal growth rate.
- Calculate both Gordon-growth and exit-multiple terminal values when appropriate and investigate material divergence.
- Use finite-life valuation for concessions, mines, upstream oil assets, and other assets that expire or deplete. Do not force a perpetuity.
- Report terminal value as a percentage of total value and flag excessive concentration.

## 4. Model Library

### M1. FCFF Discounted Cash Flow

```text
FCFF_t = EBIT_t x (1 - Tax Rate_t) + D&A_t - CapEx_t - Change in NWC_t
EV = Sum[FCFF_t / (1 + WACC)^t] + TV_n / (1 + WACC)^n
TV_n = FCFF_(n+1) / (WACC - g)

Equity Value =
    EV
    - Gross Debt
    - Lease Liabilities not already included in debt
    - Preferred Equity
    - Non-controlling Interests
    + Cash
    + Non-operating Investments

Value per Share = Equity Value / Fully Diluted Shares
```

**Use:** Non-financial operating businesses.
**Output:** Enterprise value, equity value, and intrinsic value per share.
**Do not use as the primary model for:** Banks, insurers, ETFs, or businesses where funding liabilities are operating inputs.

### M2. FCFE Discounted Cash Flow

```text
FCFE_t = Net Income_t + D&A_t - CapEx_t - Change in NWC_t + Net Borrowing_t
Equity Value = Sum[FCFE_t / (1 + Ke)^t] + TV_n / (1 + Ke)^n
TV_n = FCFE_(n+1) / (Ke - g)
Value per Share = Equity Value / Fully Diluted Shares
```

**Use:** Businesses with stable leverage and meaningful, forecastable net borrowing.
**Output:** Equity value and intrinsic value per share.

### M3. Dividend Discount Model

```text
V0 = Sum[DPS_t / (1 + Ke)^t] + DPS_(n+1) / [(Ke - g) x (1 + Ke)^n]
```

Single-stage Gordon model:

```text
V0 = DPS_1 / (Ke - g)
```

**Use:** Companies with an observable, sustainable payout policy that reasonably tracks distributable earnings.
**Inputs:** Dividends per share, payout policy, earnings, growth, cost of equity.
**Output:** Intrinsic equity value per share.

### M4. Residual Income / Excess Return

```text
Residual Income_t = Net Income_t - Ke x Beginning Common Equity_t
Equity Value =
    Current Common Equity
    + Sum[Residual Income_t / (1 + Ke)^t]
    + Present Value of Continuing Residual Income

Equivalent:
Residual Income_t = (ROE_t - Ke) x Beginning Common Equity_t
```

Book-equity roll-forward:

```text
Ending Common Equity =
    Beginning Common Equity
    + Net Income attributable to common shareholders
    - Common Dividends
    + Net Common Equity Issuance
    + Other Clean-surplus Adjustments
```

**Use:** Banks, balance-sheet financial institutions, and firms with meaningful book equity but noisy free cash flow.
**Output:** Equity value and intrinsic value per share.

Stable justified price-to-book:

```text
Justified P/B = (ROE - g) / (Ke - g)
```

This is valid only when ROE, growth, payout, and risk are mutually consistent in a stable period.

### M5. Bank Regulatory-Capital FCFE

```text
Bank FCFE_t = Net Income_t - Required Increase in Common Equity_t
Required Common Equity_t = Target CET1 or CAR x Forecast Risk-weighted Assets_t
```

Use residual income as the principal bank intrinsic model. Bank FCFE is a supporting formulation when regulatory-capital disclosures are sufficient. Deposits are not treated as ordinary financing debt.

### M6. Trading Comparables

```text
Equity-multiple Value per Share = Selected Peer Multiple x Target Metric per Share

Implied EV = Selected Peer EV Multiple x Target Metric
Implied Equity Value =
    Implied EV
    - Gross Debt
    - Lease Liabilities not included in debt
    - Preferred Equity
    - Non-controlling Interests
    + Cash
    + Non-operating Investments
```

Use median or trimmed peer statistics after testing business mix, period basis, accounting treatment, profitability, leverage, and outliers. Do not use negative or economically meaningless denominators.

### M7. NAV and RNAV

```text
NAV = Fair Value of Operating Assets + Cash + Investments - Total Liabilities - Other Claims

RNAV =
    Sum[Probability_i x After-tax Fair Value_i]
    + Other Assets
    + Cash and Investments
    - Gross Debt
    - Other Liabilities and Claims

Value per Share = NAV or RNAV / Fully Diluted Shares
```

**Use:** Property, hotels with material owned real estate, mines, upstream oil, and other asset-backed businesses.
Book value is a low-confidence reference, not a guaranteed valuation floor.

### M8. Sum-of-the-Parts

```text
SOTP Equity Value =
    Sum[Value of Business_i x Attributable Ownership_i]
    + Parent Cash
    + Parent Non-operating Investments
    - Parent Gross Debt
    - Parent Preferred Equity
    - Parent Other Claims
    - Present Value of Unfunded Parent Costs

Value per Share = SOTP Equity Value / Fully Diluted Shares
```

Do not add parent cash and then subtract a net-debt figure that already deducts the same cash. Eliminate cross-holdings and intra-group duplication. A holding-company discount may be presented as a sensitivity or empirically supported market adjustment; it must not be an unexplained automatic haircut.

### M9. Earnings Power Value

```text
Normalized NOPAT = Normalized EBIT x (1 - Normalized Tax Rate)
EPV Enterprise Value = Normalized NOPAT / WACC

EPV Equity Value =
    EPV Enterprise Value
    + Excess Cash
    + Non-operating Assets
    - Gross Debt
    - Preferred Equity
    - Non-controlling Interests
```

**Use:** Mature or cyclical businesses as a no-growth supporting value.
Do not deduct net debt and then add the same cash again.

### M10. REIT Valuation

```text
FFO = Net Income + Real-estate D&A - Gains on Property Sales
AFFO = FFO - Recurring Maintenance CapEx - Other Sustainable Adjustments
NAV = Fair Value of Investment Properties + Other Assets - Liabilities
```

Use DPU/DDM, dividend yield, P/FFO or P/AFFO, and P/NAV. Philippine REIT distribution requirements refer to distributable income, not automatically accounting net income or FFO. The engine must use the issuer's disclosed distributable-income reconciliation.

### M11. ETF NAV Pass-through

```text
Fair Value per Unit = Official NAV per Unit
Premium or Discount = Market Price / NAV per Unit - 1
```

Also report tracking error, expense ratio, liquidity, and NAV staleness. Do not apply corporate DCF or corporate multiples.

### M12. Graham Educational Screens

Keep the two historical Graham heuristics separate:

```text
Graham Number = sqrt(22.5 x Normalized EPS x BVPS)

Graham Growth Formula =
    Normalized EPS x (8.5 + 2g) x (4.4% / Y)
```

`Y` is a current high-grade bond yield expressed on the same percentage basis as 4.4%. For a Philippine educational implementation, use a clearly disclosed Philippine high-grade yield proxy. Neither formula is an institutional primary valuation model. Do not run with negative EPS or BVPS. Weight at zero by default; display only as an optional educational screen.

## 5. Subsector Model Matrix

| PSE subsector | Default primary model | Mandatory support when valid | Core operating drivers | Principal override |
|---|---|---|---|---|
| Banks | Residual income / excess return | Justified P/B, peer P/B and P/TBV; DDM | ROE, NIM, CET1/CAR, NPL, provision coverage, loan and deposit growth | Regulatory-capital FCFE when data is sufficient |
| Other Financial Institutions | Residual income for balance-sheet firms; normalized earnings/DDM for fee firms | P/B, P/E, P/AUM or EV/EBITDA as appropriate | ROE, solvency, combined ratio, AUM, take rate, cost-to-income | Split insurer/lender/reinsurer from broker/exchange/fee platform |
| Electricity, Energy, Power & Water | Asset/project FCFF DCF | EV/EBITDA, EV/MW, DDM, RAB cross-check | MW, capacity factor, tariff, PPA tenor, fuel, CapEx, allowed return | Finite-life concession DCF; regulated-asset model |
| Food, Beverage & Tobacco | FCFF DCF | EV/EBITDA, P/E, EPV or DDM | Volume, price/mix, gross margin, brand strength, input costs, ROIC | EV/Sales for credible loss-making growth; normalize commodity cycles |
| Construction, Infrastructure & Allied Services | FCFF or concession-life DCF | EV/EBITDA, P/E, backlog cross-check | Backlog, margin, cash conversion, working capital, concession tenor | SOTP for builders owning concessions |
| Chemicals | FCFF DCF on normalized margins | EV/EBITDA, EPV, EV/tonne | Specialty/commodity mix, spreads, utilization, maintenance CapEx | Mid-cycle EPV for commodity producers |
| Other Industrials | FCFF DCF on mid-cycle economics | EV/EBITDA, EV/EBIT, EPV, replacement-cost check | Capacity, utilization, volume, ASP, energy cost, maintenance CapEx | Segment SOTP for diversified issuers |
| Holding Firms | SOTP | P/NAV, look-through earnings and dividends | Ownership, stake values, parent cash/debt, upstream dividends, overhead | No consolidated DCF unless one operating business clearly dominates |
| Property | RNAV/SOTP | Project DCF, P/NAV, P/E; REIT module where applicable | Landbank, project GDV, pre-sales, occupancy, rent, cap rate, gearing | Separate development, recurring property, REIT and hotel components |
| Media | FCFF DCF on normalized or declining cash flow | EV/EBITDA, EV/Sales, P/E or DDM | Advertising, audience, digital mix, content cost, payout | NAV/SOTP for distressed or restructuring asset stories |
| Telecommunications | FCFF DCF | EV/EBITDA, EV/subscriber, P/FCF, DDM | Subscribers, ARPU, churn, CapEx/sales, spectrum, leases, leverage | Subscriber-ramp scenario for pre-profit challenger; SOTP for towers/data centers |
| Information Technology | Scenario DCF when feasible; EV/Sales for pre-profit | EV/gross profit, EV/EBITDA or P/E after profitability | Recurring revenue, growth, gross margin, retention, burn and runway | Survival gate before DCF; regional peers only with size/liquidity adjustment |
| Transportation Services | Asset/concession FCFF DCF | EV/EBITDA or EV/EBITDAR, EV/TEU, EV/ASK, fleet NAV | Throughput, load factor, yield, fuel, fleet, leases, concession tenor | Terminal-by-terminal SOTP for ports; fleet NAV and scenarios for airlines |
| Hotel & Leisure | Operating DCF plus RNAV where owned | EV/EBITDA, EV/room, P/NAV | Occupancy, ADR, RevPAR, GOP margin, rooms, property value | NAV may dominate for asset-rich, earnings-thin issuers |
| Education | FCFF DCF | P/E, DDM, EV/student, campus RNAV | Enrollment, tuition, retention, capacity, payout, campus utilization | SOTP for education holding firms; RNAV for material excess land |
| Other Services | Business-model-specific FCFF DCF | EV/EBITDA, P/E, EV/Sales, NAV/SOTP | Recurring revenue, margin, asset intensity, working capital | Route by economic type; subsector label alone is insufficient |
| Mining | Reserve-based life-of-mine NAV | EV/reserve, EV/resource, EV/EBITDA, P/NAV | Reserves, grade, recovery, production, AISC, commodity price, mine life | SOTP for integrated mine-and-power; risked NAV for pre-production |
| Oil | Reserve/project NAV for upstream; FCFF for downstream | EV/reserve, EV/production, EV/EBITDA, P/NAV | Reserves, production, lifting cost, refining margin, throughput, royalties | Split upstream, refining, distribution and renewable investments |
| Small, Medium & Emerging Board | Underlying industry model | EV/Sales, NAV, EPV or applicable sector multiple | Cash runway, governance, free float, disclosure quality plus sector KPIs | Apply wider ranges and lower confidence; no automatic premium |
| Electrical Components & Equipment | FCFF DCF on mid-cycle margins | EV/EBITDA, EV/Sales, P/E | Utilization, orders, customer concentration, FX, inventory, CapEx | Regional EMS peers with explicit comparability adjustment |
| Casinos & Gaming | Property/segment FCFF DCF | EV/EBITDA, EV/Sales for online, RNAV and SOTP | GGR, mass/VIP mix, hold, users, property EBITDA, license tenor | Separate integrated resort, online gaming, hotel and real estate |
| Retail | Store-driver FCFF DCF | EV/EBITDA, P/E, EV/Sales, P/FCF | Same-store sales, stores, sales/sqm, margin, inventory turns, leases | Lease-adjusted comparison under PFRS 16 |
| ETF - Equity | Official NAV pass-through | Premium/discount and tracking error | NAV, holdings, fees, units, liquidity | No corporate valuation model |

## 6. Subsector Implementation Notes

### 6.1 Financial institutions

Banks and balance-sheet financial firms must be valued directly on equity. Deposits, policyholder funds, and similar liabilities are operating inputs rather than ordinary capital structure. Model ROE, capital requirements, asset quality, and book-value growth. Fee-based financial companies may be valued using normalized earnings or operating DCF if client assets and funding risks are not borne on the balance sheet.

### 6.2 Utilities, power, and infrastructure

Separate regulated, contracted, and merchant earnings. Project-level cash flows should reflect tariff escalation, PPA tenor, capacity factor, fuel pass-through, maintenance CapEx, and concession expiry. Finite concessions should not receive a perpetual terminal value unless renewal or residual rights are legally and economically supported.

### 6.3 Consumer, industrial, and retail businesses

Normalize margins and working capital across the available annual history and quarterly seasonality. For retail, forecast store count, sales per store or square meter, same-store growth, gross margin, inventory, leases, and maintenance CapEx. For cyclicals such as chemicals, cement, EMS, and heavy manufacturing, use mid-cycle economics rather than current peak or trough results.

### 6.4 Holding companies

Value listed stakes using current attributable market value only when the application is permitted to use the relevant data. Value unlisted businesses using their own sector methods. Apply ownership percentages before subtracting parent-level obligations. Eliminate cross-holdings and avoid duplicating consolidated cash, debt, earnings, or minority interests.

### 6.5 Property and REITs

Property developers normally require separate valuation of recurring rental assets, residential or commercial development, landbank, hotels, and listed REIT interests. RNAV depends on defensible appraisal dates, remaining development cost, tax leakage, completion timing, and net debt. REITs require disclosed distributable income, DPU, property NAV, occupancy, WALE, cap rates, gearing, and sponsor-related transactions.

### 6.6 Technology and high-growth issuers

Before applying EV/Sales, test whether revenue is recurring, economically comparable, and supported by cash runway. A scenario DCF must explicitly model the path to sustainable margins, reinvestment, financing needs, and dilution. Negative earnings do not automatically imply zero value, but they reduce model reliability.

### 6.7 Transport, hotels, and gaming

Airlines require fuel, load factor, yield, fleet and lease scenarios. Ports and terminals require concession-level throughput and tariff forecasts. Hotels require occupancy, ADR, RevPAR, property ownership, and recurring refurbishment CapEx. Casinos require property-level EBITDA, gaming mix, license tenure, tax and regulatory scenarios. Online gaming should not be valued as a physical integrated resort.

### 6.8 Mining and oil

Use after-tax, finite-life project cash flow tied to economically recoverable reserves, production schedules, operating costs, development and sustaining CapEx, royalties, rehabilitation, permits, and commodity-price scenarios. Resources that are not reserves require probability and development-risk adjustments. Downstream refining and marketing belong in an operating-company framework, not reserve NAV.

## 7. Automated Decision Framework

### 7.1 Routing

```text
if subsector == ETF-Equity:
    run ETF NAV module
elif bank or balance-sheet financial institution:
    run residual income + justified/peer P-B
elif fee-based financial institution:
    run normalized earnings/DDM + suitable comparables
elif holding company or material cross-industry segments:
    run SOTP
elif REIT:
    run DPU/DDM + P-NAV + P-FFO/AFFO
elif property and asset data are sufficient:
    run RNAV/SOTP
elif mining or upstream oil and reserve data are sufficient:
    run finite-life reserve NAV
elif finite concession exists:
    run concession-life DCF
elif profitable non-financial operating company:
    run FCFF DCF + suitable comparables
elif positive, economically meaningful revenue and credible path to profitability:
    run EV-Sales/EV-Gross-Profit + scenario DCF
else:
    run the best-supported NAV, EPV, or comparable fallback
    label result screening-grade or insufficient-data
```

### 7.2 Model validity gates

A model may run only when:

- required inputs and dates are present;
- units and currency reconcile;
- flow periods do not overlap;
- peer and target periods match;
- share counts and corporate actions reconcile;
- denominators are positive and economically meaningful;
- cash-flow signs and bridges pass accounting checks;
- terminal growth is below the discount rate;
- NAV has a defensible asset and liability bridge;
- banks have capital and asset-quality data;
- reserve models have reserve/resource classification and project timing;
- ETF NAV is sufficiently current.

Example failure codes:

```text
NEGATIVE_DENOMINATOR
MISSING_SHARE_COUNT
OVERLAPPING_PERIODS
STALE_MARKET_PRICE
STALE_NAV
UNAVAILABLE_RESERVE_DATA
INSUFFICIENT_PEERS
TERMINAL_GROWTH_INVALID
EV_MODEL_INAPPROPRIATE_FOR_FINANCIAL
SOURCE_RECONCILIATION_FAILED
```

### 7.3 Confidence scoring

Score each valid model using configurable components:

| Component | Question |
|---|---|
| Model fit | Does the model match the company's economics and capital structure? |
| Data completeness | Are all material inputs available? |
| Data freshness | Are statements, prices, operating KPIs, and assumptions current? |
| Source quality | Are values reported, independently verifiable, or proxy-derived? |
| Forecast stability | Are margins, growth, leverage, and reinvestment forecastable? |
| Peer quality | Are there enough economically comparable companies? |
| Output convergence | Do valid methods produce a defensible range? |

Do not use one universal hard-coded confidence cutoff without back-testing. The engine should retain the component scores and the reason for every penalty.

### 7.4 Blending policy

- Blend only valid, economically distinct methods.
- Do not treat P/B and justified P/B as fully independent evidence when both are driven by the same book value and ROE.
- Weight intrinsic models more heavily when forecasts and inputs are reliable.
- Weight comparables more heavily when intrinsic forecasts are weak but the peer set is strong.
- Do not blend an invalid model merely to avoid a missing result.
- Make divergence thresholds configurable and back-tested by subsector.
- When divergence exceeds the review threshold, publish separate model ranges and `INSUFFICIENT_CONVERGENCE`.
- Always retain every component valuation, sensitivity range, weight, and confidence score.

Indicative starting ranges for back-testing:

| Company family | Intrinsic/asset methods | Relative/supporting methods |
|---|---:|---:|
| Mature profitable non-financial | 50%-75% | 25%-50% |
| Bank or balance-sheet financial | 50%-75% residual income/DDM | 25%-50% peer P/B/P/E |
| Property | 50%-75% RNAV/SOTP | 25%-50% P/NAV and operating checks |
| Holding company | 65%-85% SOTP | 15%-35% P/NAV/look-through checks |
| Mining/upstream oil | 60%-85% reserve/project NAV | 15%-40% operating/resource multiples |
| Pre-profit growth | 25%-50% scenario DCF | 50%-75% sales/gross-profit multiples |
| ETF | 100% official NAV | Market premium/discount disclosed separately |

These ranges are initialization parameters, not permanent truths. Calibrate them using historical out-of-sample error and analyst review.

### 7.5 Output contract

```json
{
  "ticker": "...",
  "pse_sector": "...",
  "pse_subsector": "...",
  "classification_date": "YYYY-MM-DD",
  "valuation_date": "YYYY-MM-DD",
  "financial_period_end": "YYYY-MM-DD",
  "period_basis": "FY|TTM|forward|NAV",
  "price_date": "YYYY-MM-DD",
  "models": [
    {
      "name": "FCFF_DCF",
      "status": "valid|failed|screening",
      "value_per_share": 0,
      "range_low": 0,
      "range_high": 0,
      "weight": 0,
      "confidence": 0,
      "failure_code": null
    }
  ],
  "blended_value_per_share": null,
  "confidence_grade": "high|medium|low|screening|insufficient",
  "assumptions": {},
  "source_ids": [],
  "proxy_fields": [],
  "warnings": [],
  "human_review_required": false
}
```

## 8. Required Inputs and Public Proxies

| Input | Preferred source | Practical proxy or rule |
|---|---|---|
| EBITDA | Income statement, cash-flow statement and notes | Operating income + relevant D&A; reconcile exceptional items |
| CapEx | Cash-flow statement and asset notes | Purchases/additions of PPE and intangibles, adjusted for non-cash additions |
| Change in NWC | Two balance sheets and cash-flow notes | Change in non-cash operating current assets less non-debt operating current liabilities |
| Debt | Balance sheet and debt note | Short- and long-term interest-bearing obligations; separately identify leases |
| Cost of debt | Current debt disclosure | Current yield/coupon or government benchmark plus defensible spread |
| Beta | Public industry data | Bottom-up industry beta, relevered to sustainable company leverage |
| Risk-free rate | BTr/BSP or authorized public yield source | Duration-matched Philippine peso government yield |
| ERP | Transparent public methodology | Philippine implied ERP or mature-market ERP plus non-duplicated country risk |
| TTM earnings/cash flow | Latest four stand-alone quarters | Derive stand-alone quarters from YTD filings before summing |
| Bank NIM | Bank disclosures | Net interest income divided by average earning assets |
| Bank required capital | BSP/company disclosures | Target CET1/CAR multiplied by forecast risk-weighted assets |
| Property value | Notes, appraisal and annual report | Use disclosed fair value/appraisal; book value only as low-confidence reference |
| Reserve life | Technical/annual report | Economically recoverable reserves divided by sustainable annual production |
| Hotel RevPAR | MD&A | Occupancy multiplied by ADR, or room revenue divided by available room nights |
| Telco ARPU | MD&A | Service revenue divided by average subscribers and relevant months |
| Diluted shares | Filing and instrument notes | Basic shares plus treasury-stock-method/options and if-converted dilution where applicable |

## 9. Update Frequency

| Variable | Routine refresh | Immediate trigger |
|---|---|---|
| Price and basic shares | Each valuation run | Corporate action, issuance, buyback, split |
| Quarterly statements and TTM | Each filing | Restatement or corrected filing |
| Annual statements and segments | Annually | Restatement, acquisition, disposal, segment change |
| Dividends and distributable income | Declaration/payment or REIT filing | Special dividend or policy change |
| Philippine risk-free rate | Each valuation date or controlled monthly snapshot | Material rate move |
| ERP and country-risk methodology | Monthly or quarterly governance review | Regime or methodology change |
| Beta, peer multiples and spreads | Monthly; at least quarterly | Earnings, refinancing, credit or price shock |
| WACC/Ke and terminal assumptions | Each formal valuation run | Capital structure or risk-profile change |
| Property values and cap rates | Quarterly/annual as disclosed | Appraisal, sale, impairment, major rate move |
| Commodity prices | Each valuation run | Material commodity or FX move |
| Reserves and mine plans | Annual or technical update | Reserve revision, permit, mine-plan change |
| Bank capital and asset quality | Quarterly | Capital raise or regulatory change |
| ETF NAV and holdings | Each published NAV | Rebalance, creation/redemption, stale NAV |

## 10. Quality Control and Governance

Before publication, require:

1. Statement and period reconciliation.
2. Balance-sheet identity and cash-flow sign checks.
3. Share-count and corporate-action reconciliation.
4. EV-to-equity bridge reconciliation.
5. Discount-rate and terminal-growth consistency.
6. Terminal-value concentration and sensitivity review.
7. Peer-set and multiple-definition review.
8. Source freshness and proxy disclosure.
9. Subsector and business-model override review.
10. Human review for material warnings, restatements, unusual ownership, cross-holdings, reserve uncertainty, or insufficient convergence.

Every external result should display:

- valuation date and financial period;
- model names and model status;
- low/base/high range;
- material assumptions and sensitivities;
- confidence grade;
- missing or proxy-derived inputs;
- classification and override rationale;
- statement that the output is a model estimate, not a guaranteed target or individualized recommendation.

## 11. Sources and Methodological Basis

- [PSE indices and sector classification](https://www.pse.com.ph/indices/)
- [PSE Sector Classification Guide](https://documents.pse.com.ph/wp-content/uploads/sites/15/2021/01/PSE-Sector-Classification-Guide.pdf)
- [PSE EDGE disclosures](https://edge.pse.com.ph/)
- [CFA Institute - Free Cash Flow Valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation)
- [CFA Institute - Discounted Dividend Valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/discounted-dividend-valuation)
- [CFA Institute - Residual Income Valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/residual-income-valuation)
- [Damodaran valuation resources](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valuation/val.htm)
- [Damodaran financial-service valuation resources](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/littlebook/financialsvccompanies.htm)
- [IFRS - IAS 7 Statement of Cash Flows](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows.html)
- [Bangko Sentral ng Pilipinas](https://www.bsp.gov.ph/)
- [Bureau of the Treasury](https://www.treasury.gov.ph/)
- Republic Act No. 9856, the Philippine REIT Act, and its current implementing rules
- Koller, Goedhart and Wessels, *Valuation: Measuring and Managing the Value of Companies*
- Pinto, Henry, Robinson and Stowe, *Equity Asset Valuation*

## 12. Final Implementation Position

This framework is suitable as the valuation engine's controlling methodology after its configurable thresholds, peer-selection policy, and confidence scoring are back-tested. PSE subsectors should route companies into default model families, but company-specific inputs and business-model overrides determine the actual valuation. No automated point estimate should be published when the data, model fit, or model convergence is insufficient.
