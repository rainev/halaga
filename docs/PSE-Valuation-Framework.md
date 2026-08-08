# PSE Sector-Aware Valuation Framework

**A practical, subsector-by-subsector valuation methodology for every company listed on the Philippine Stock Exchange (PSE) — engineered for automation.**

*Prepared as an equity-research / investment-banking reference for the FinSight valuation engine.*
*Version 1.0 — July 2026*

---

## Table of Contents

1. [How to Use This Document](#0-how-to-use-this-document)
2. [Cross-Cutting Foundations](#1-cross-cutting-foundations)
   - 1.1 Discount-rate calibration for the Philippines (Ke, Kd, WACC)
   - 1.2 Terminal-value discipline
   - 1.3 Data-source map (where each input lives)
   - 1.4 Output types and how to reconcile them
3. [The Valuation Model Library](#2-the-valuation-model-library) — every equation, variable, input, data source and output
4. [Subsector Valuation Frameworks](#3-subsector-valuation-frameworks) — all 23 PSE subsectors
5. [Master Reference Table](#4-master-reference-table)
6. [The Automated Valuation Decision Framework](#5-the-automated-valuation-decision-framework) — engine logic, model routing, blending, fallbacks
7. [Appendix A — Philippine Data Proxies](#appendix-a-philippine-data-proxy-cheat-sheet)
8. [Appendix B — Sources & Methodological Basis](#appendix-b-sources-methodological-basis)

---

## 0. How to Use This Document

This is a **reference specification**, not a company report. It answers one question for each PSE subsector: *"If a professional equity analyst had to value every company in this subsector using only publicly available Philippine data, which models would they run, in what order, and with what inputs?"*

The document is organized so a software engineer can implement it directly:

- **Part 2 (Model Library)** defines each valuation model **once** — equation, every variable, required inputs, where the input is sourced, and whether it outputs Enterprise Value (EV), Equity Value, or Intrinsic Value per Share. Subsector sections reference these models by name rather than re-deriving them.
- **Part 3 (Subsector Frameworks)** gives each of the 23 PSE subsectors a **primary model**, **supporting models**, **key multiples**, **key metrics**, the **rationale** for the combination, **special cases**, and **PH data notes**.
- **Part 5 (Decision Framework)** turns all of the above into deterministic engine logic: routing rules, blend weights, and fallback chains keyed to data availability.

**Guiding principles used throughout (from Damodaran, Koller/McKinsey, CFA Institute):**

1. **Match the model to the cash-flow claim.** Value equity directly (FCFE, DDM, RI, P/B) when leverage is intrinsic to operations (banks, insurers, financial holcos); value the enterprise (FCFF, EV/EBITDA) when capital structure is a financing choice.
2. **Never value a holding company on consolidated cash flows.** Use Sum-of-the-Parts / NAV.
3. **Never value a bank on EV/EBITDA or FCFF.** Debt *is* raw material for a bank; there is no meaningful "enterprise value" or "unlevered cash flow."
4. **Prefer models the data can actually feed.** A theoretically superior DCF that requires broker forecasts loses to a disciplined multiple that runs off filed statements. Every model below is scored on Philippine data availability.
5. **Triangulate, then blend.** No single point estimate is trusted. The engine runs a primary intrinsic model, cross-checks with relative multiples against PSE peers, and blends when both are reliable.

---

## 1. Cross-Cutting Foundations

These inputs recur in almost every model and should be computed **once per company per valuation run** and cached.

### 1.1 Discount-Rate Calibration for the Philippines

#### Cost of equity (Ke) — CAPM, PH-calibrated

```
Ke = Rf + β_levered × ERP_PH   (+ optional size/illiquidity premium α)
```

| Variable | Definition | Recommended PH value / source |
|---|---|---|
| `Rf` | Risk-free rate | **Philippine 10-year local-currency government bond yield** (BVAL / PDST-R2 reference rate). Local-currency cash flows must be discounted at a peso risk-free rate — *do not* use US Treasuries. Typical range 5.5%–6.5%. |
| `ERP_PH` | Equity risk premium for the Philippines | Damodaran country-risk approach: **Mature-market ERP (~4.3%) + Philippine country-risk premium (~2.5–3.5%) ≈ 6.5%–7.5%.** Updated on Damodaran's "ERP by country" dataset (public, semi-annual). |
| `β_levered` | Equity beta relevered to the firm's capital structure | Bottom-up: take Damodaran's unlevered industry beta (public dataset), relever with the firm's D/E and PH tax rate. Preferred over noisy single-stock regressions vs. the PSEi for thin/illiquid names. |
| `α` | Optional small-cap / illiquidity premium | Add **1.5%–3.0%** for SME-board, thinly traded, or micro-cap names where free float and turnover are low. |

**Relevering beta:**
```
β_levered = β_unlevered × [1 + (1 − Tax) × (Debt / Equity)]
```

#### Cost of debt (Kd)

```
Kd_after-tax = Kd_pre-tax × (1 − Tax)
```
- `Kd_pre-tax` proxy: **Interest Expense ÷ Average Interest-Bearing Debt** from the financials, floored at the PH 10Y govvy + a credit spread appropriate to leverage. For firms with public bonds, use the disclosed coupon/yield.
- `Tax` = **25%** statutory PH corporate income tax (CREATE Act; 20% for qualifying small domestic corporations). Use the effective tax rate from the income statement when it is stable.

#### Weighted average cost of capital (WACC)

```
WACC = (E / (D + E)) × Ke + (D / (D + E)) × Kd × (1 − Tax)
```
- `E` = market value of equity (market cap). `D` = total interest-bearing debt (book is an acceptable proxy for PH non-financials).
- Weights should use **target/market** capital structure; for stability the engine may use a 3-year average D/E.

> **Rule:** Ke discounts equity cash flows (FCFE, dividends, residual income). WACC discounts firm cash flows (FCFF). Mixing them is the single most common valuation error the engine must prevent.

### 1.2 Terminal-Value Discipline

Terminal value routinely drives 60–80% of a DCF. Two accepted methods; the engine should compute **both** and flag divergence.

**Gordon growth (perpetuity):**
```
TV_n = CF_(n+1) / (r − g)         where g ≤ long-run nominal GDP growth
```
- PH long-run terminal growth `g`: cap at **4.0%–5.0%** (nominal peso GDP growth trend). Never let `g ≥ r`.

**Exit multiple:**
```
TV_n = Metric_n × Steady-State Multiple   (e.g., EV/EBITDA or P/E of mature peers)
```

Discount TV back: `PV(TV) = TV_n / (1 + r)^n`.

### 1.3 Data-Source Map — Where Each Input Lives

Every required input in this document is tagged with a source code:

| Code | Source | Typical contents |
|---|---|---|
| **SFP** | Statement of Financial Position (Balance Sheet) | Assets, liabilities, equity, debt, book value, cash |
| **IS** | Income Statement | Revenue, EBIT, EBITDA (derived), net income, interest, tax |
| **CF** | Statement of Cash Flows | Operating CF, CapEx, D&A, working-capital changes |
| **NOTES** | Notes to Financial Statements | Debt schedules, segment detail, reserves, lease detail, fair values |
| **AR** | Annual Report / 17-A | MD&A, strategy, guidance, operational KPIs |
| **MDA** | Management Discussion & Analysis | Volumes, capacity, occupancy, subscriber counts, ASP |
| **EDGE** | PSE EDGE disclosures | Shares outstanding, dividends declared, ownership, quarterly (17-Q) and annual (17-A) filings, price |
| **MKT** | Market data | Price, market cap, EV, trading multiples of peers |
| **PROXY** | Estimated when not directly disclosed | See Appendix A for the standard proxy for each |

The core Philippine filings are the **SEC/PSE Form 17-A (annual)** and **17-Q (quarterly)**, both free on **PSE EDGE**. Segment notes (PFRS 8) are the backbone of every Sum-of-the-Parts valuation.

### 1.4 Output Types & Reconciliation

Every model outputs one of three things. The engine must convert everything to **intrinsic value per share** before blending.

```
Equity Value      = Enterprise Value − Net Debt − Minority Interest − Preferred + Investments in Associates (at FV)
Value per Share   = Equity Value / Diluted Shares Outstanding
Net Debt          = Total Interest-Bearing Debt − Cash & Cash Equivalents − Current Financial Investments
```

| Model family | Native output | Bridge to per-share |
|---|---|---|
| FCFF DCF, EV/EBITDA, EV/EBIT, EV/Sales, EV/MW, EV/Reserve, EV/Room | **Enterprise Value** | Subtract net debt & minorities → equity → ÷ shares |
| FCFE DCF, DDM, Residual Income, Excess Return, P/B, P/E | **Equity Value** | ÷ shares |
| NAV / RNAV / SOTP | **Equity Value (NAV)** | ÷ shares (often apply holdco discount) |
| Graham, EPV | **Intrinsic Value per Share / Equity Value** | direct or ÷ shares |

---

## 2. The Valuation Model Library

Each model is defined once. Subsector sections reference these by name.

### 2.1 Discounted Cash Flow — FCFF (Free Cash Flow to Firm)

**Use for:** operating companies where capital structure is a financing choice (industrials, telcos, utilities-by-project, retail, consumer, property developers on a project basis). **Not** for banks/insurers.

```
Enterprise Value = Σ_{t=1..n} [ FCFF_t / (1 + WACC)^t ] + PV(Terminal Value)

FCFF_t = EBIT_t × (1 − Tax) + D&A_t − CapEx_t − ΔNWC_t

Terminal Value = FCFF_(n+1) / (WACC − g)

Equity Value = Enterprise Value − Net Debt − Minority Interest − Preferred
Value/Share  = Equity Value / Diluted Shares
```

| Variable | Definition | Source |
|---|---|---|
| `EBIT` | Operating profit before interest & tax | IS |
| `Tax` | Effective or statutory (25%) tax rate | IS / statutory |
| `D&A` | Depreciation & amortization (added back, non-cash) | CF / NOTES |
| `CapEx` | Capital expenditure (cash out for PP&E) | CF |
| `ΔNWC` | Change in non-cash net working capital | SFP (two periods) |
| `WACC` | Discount rate (§1.1) | Computed |
| `g` | Terminal growth (≤4–5% PH) | Assumption |
| `Net Debt` | Interest-bearing debt − cash | SFP |
| `Shares` | Diluted shares outstanding | EDGE |

**Output:** Enterprise Value → Equity Value → Intrinsic Value per Share.

### 2.2 Discounted Cash Flow — FCFE (Free Cash Flow to Equity)

**Use for:** firms where leverage is core (financial-adjacent) or where net borrowing is a stable policy; a natural equity-side complement to FCFF.

```
Equity Value = Σ_{t=1..n} [ FCFE_t / (1 + Ke)^t ] + PV(Terminal Value)

FCFE_t = Net Income_t + D&A_t − CapEx_t − ΔNWC_t + Net Borrowing_t
Terminal Value = FCFE_(n+1) / (Ke − g)
Value/Share = Equity Value / Diluted Shares
```

| Variable | Definition | Source |
|---|---|---|
| `Net Income` | Profit after tax attributable to shareholders | IS |
| `Net Borrowing` | New debt issued − debt repaid | CF (financing) |
| `Ke` | Cost of equity (§1.1) | Computed |
| others | as in FCFF | — |

**Output:** Equity Value → per share.

### 2.3 Dividend Discount Model (DDM)

**Use for:** stable, high-payout, dividend-committed firms — banks, mature utilities, telcos, consumer staples, REITs (as a proxy).

**Gordon (single-stage):**
```
Equity Value/Share = D_1 / (Ke − g)          D_1 = D_0 × (1 + g)
```
**Two-stage (explicit high-growth then perpetuity):**
```
Value/Share = Σ_{t=1..n} [ D_t / (1+Ke)^t ] + [ D_(n+1)/(Ke − g_terminal) ] / (1+Ke)^n
```

| Variable | Definition | Source |
|---|---|---|
| `D_0`, `D_t` | Dividend per share (trailing / projected) | EDGE (dividend declarations) |
| `g` | Sustainable dividend growth = `ROE × (1 − payout)` | IS + EDGE |
| `Ke` | Cost of equity | Computed |

**Output:** Intrinsic Value per Share directly.

### 2.4 Residual Income Model (RIM)

**Use for:** banks and any firm with reliable book value but lumpy/negative near-term FCF. Less sensitive to terminal value than DCF.

```
Equity Value = BV_0 + Σ_{t=1..n} [ RI_t / (1 + Ke)^t ] + PV(Terminal RI)

RI_t = Net Income_t − (Ke × BV_(t−1))
     = (ROE_t − Ke) × BV_(t−1)
```

| Variable | Definition | Source |
|---|---|---|
| `BV_0` | Current book value of equity | SFP |
| `Net Income` | Attributable net income | IS |
| `ROE` | Return on equity | IS/SFP |
| `Ke` | Cost of equity | Computed |

**Output:** Equity Value → per share.

### 2.5 Excess Return / Excess Equity Return Model (bank-specific RI variant)

**Use for:** banks — the institutional standard equity-side intrinsic model.

```
Value of Equity = BV_equity_0 + Σ [ Excess Equity Return_t / (1 + Ke)^t ] + PV(Terminal)

Excess Equity Return_t = (ROE_t − Ke) × BV_equity_(t−1)
```
Same inputs as RIM; framed on regulatory equity. Terminal value uses a fade of ROE toward Ke.

**Output:** Equity Value → per share.

### 2.6 Earnings Power Value (EPV)

**Use for:** mature, cyclical, low-growth firms (cement, some industrials, tobacco); a no-growth sanity check.

```
EPV (Enterprise) = Normalized EBIT × (1 − Tax) / WACC
EPV (Equity)     = EPV Enterprise − Net Debt + Excess Cash
Value/Share      = EPV Equity / Shares
```
- `Normalized EBIT` = mid-cycle operating earnings (average margin × current revenue), stripping one-offs.

**Output:** Enterprise → Equity → per share. Assumes zero value for growth (deliberately conservative).

### 2.7 Graham Intrinsic Value

**Use for:** a fast, conservative screen across all sectors; useful fallback when only EPS and a growth estimate exist.

```
Intrinsic Value/Share = [ EPS × (8.5 + 2g) × 4.4 ] / Y

g = expected annual EPS growth (%, next 5–7 yrs)
Y = current yield on high-grade corporate bonds (PH: use 10Y govvy + spread)
```
- `EPS` from IS; `4.4` is Graham's benchmark AAA yield (rebased by `Y`).

**Output:** Intrinsic Value per Share. Treat as a floor/screen, not a precise estimate.

### 2.8 Asset-Based / Net Asset Value (Book & Adjusted)

**Use for:** asset-heavy, cyclical, or loss-making firms; liquidation floor.

```
NAV (book)     = Total Assets − Total Liabilities  (= Book Equity)
NAV (adjusted) = Σ Fair-value of assets − Σ Liabilities  (mark PP&E, investment property, investments, inventory to FV)
Value/Share    = NAV / Shares
```
**Output:** Equity Value → per share.

### 2.9 Revalued Net Asset Value (RNAV)

**Use for:** property developers, REITs, land-rich holdcos. Marks land/investment property to appraised market value.

```
RNAV = Market Value of Investment Properties + Appraised Landbank + Other Assets (FV)
       − Net Debt − Other Liabilities − Minorities

Target Price = RNAV/Share × (1 − NAV Discount)
```
- Investment-property fair values and landbank hectarage/valuation come from **NOTES** and **AR/MDA**. PH developers disclose investment property at fair value under PAS 40.

**Output:** Equity (RNAV) → per share, usually with a discount (or premium).

### 2.10 Sum-of-the-Parts (SOTP)

**Use for:** holding companies and conglomerates. The single most important model for the PSE, which is holdco-heavy.

```
SOTP Equity Value = Σ_i [ Value_i × Ownership%_i ]
                    + Parent Net Cash − Parent Net Debt − Parent Overheads (capitalized)

Value_i = value of stake i, computed by:
   • Listed subsidiary/associate → Market Cap × ownership%
   • Unlisted operating unit     → segment EV/EBITDA or DCF on segment cash flows
   • Real estate / land          → RNAV

Target Price = (SOTP Equity Value / Shares) × (1 − Holdco Discount)
```
- **Holdco (conglomerate) discount:** PH holdcos typically trade at **15%–40%** below SOTP. Apply an empirical discount by name; default 20–25%.

**Output:** Equity Value → per share.

### 2.11 Relative Valuation — Equity Multiples

Applied by multiplying the company's metric by a **peer-median** multiple derived from comparable PSE-listed companies (and, where PH comps are too few, regional ASEAN comps as a cross-check).

| Multiple | Formula | Best for | Output |
|---|---|---|---|
| **P/E** | Price ÷ EPS; or Market Cap ÷ Net Income | Profitable, stable earners | Equity |
| **Forward P/E** | Price ÷ next-12M EPS | Growth names with visible earnings | Equity |
| **PEG** | (P/E) ÷ (EPS growth %) | Comparing growth-adjusted value | screen |
| **P/B** | Price ÷ Book Value/Share | Banks, financials, asset-heavy | Equity |
| **P/Tangible Book** | Price ÷ (BV − intangibles)/Share | Banks with goodwill | Equity |
| **P/Cash Flow** | Price ÷ Operating CF/Share | Capex-heavy, D&A-distorted | Equity |
| **P/FCF** | Market Cap ÷ Free Cash Flow to Equity | Cash-generative mature firms | Equity |
| **P/NAV** | Price ÷ NAV/Share | Property, REITs, holdcos | Equity |
| **Dividend Yield** | DPS ÷ Price | Income names (REITs, utilities) | screen |

**Implied value:** `Value/Share = Peer-Median Multiple × Company Metric per Share`.

### 2.12 Relative Valuation — Enterprise-Value Multiples

Applied to enterprise value; bridge back to equity by subtracting net debt.

| Multiple | Formula | Best for |
|---|---|---|
| **EV/EBITDA** | EV ÷ EBITDA | Capital-intensive, cross-leverage comparability (telco, industrials, utilities, gaming, retail) |
| **EV/EBIT** | EV ÷ EBIT | When D&A intensity differs across peers |
| **EV/Sales** | EV ÷ Revenue | High-growth/pre-profit (tech, early SME) |
| **EV/Operating Cash Flow** | EV ÷ Operating CF | Earnings-quality-sensitive sectors |

```
Implied EV     = Peer Multiple × Company Metric
Implied Equity = Implied EV − Net Debt − Minorities
Value/Share    = Implied Equity / Shares
```
**Output:** EV → Equity → per share.

### 2.13 Industry-Specific ("Value-Driver") Multiples

Used where a physical/operational unit predicts value better than accounting earnings.

| Multiple | Formula | Subsector | Data source |
|---|---|---|---|
| **EV/MW (installed capacity)** | EV ÷ Attributable MW | Power generation | MDA/AR capacity tables |
| **EV/Subscriber** | EV ÷ Subscribers (mobile/broadband) | Telecom | MDA subscriber KPIs |
| **EV/Reserve (2P) & EV/Resource** | EV ÷ Proven+Probable reserves (tonnes/oz/boe) | Mining, Oil | NOTES / reserve reports |
| **EV/Tonne (production)** | EV ÷ Annual output (t) | Mining, Cement | MDA production volumes |
| **EV/Room (or per key)** | EV ÷ Number of rooms | Hotel & Leisure | AR property portfolio |
| **EV/GDV or Price/GDV** | Equity ÷ Gross Development Value of pipeline | Property developers | AR project pipeline |
| **P/AUM, P/Book** | Price ÷ Assets under mgmt / book | Asset managers, brokers | NOTES |
| **EV/Seat, Rev/ASK** | Airline capacity metrics | Air transport | MDA (ASK, load factor) |
| **EV/TEU** | Port throughput (twenty-foot equiv. units) | Ports/logistics | MDA throughput |
| **EV/Student, EV/Seat** | Per enrolled student | Education | AR enrollment |

**Output:** typically EV → Equity → per share.

### 2.14 REIT-Specific Metrics (used within Property)

```
FFO  = Net Income + Depreciation & Amortization − Gains on property sales
AFFO = FFO − Maintenance CapEx − Straight-line rent adjustments
NAV  = Fair Value of Investment Properties − Net Debt
Value/Share via: P/FFO multiple, Dividend Yield, or P/NAV
```
Sources: FFO from IS+CF; investment-property fair values from NOTES (PAS 40).

---

## 3. Subsector Valuation Frameworks

Each subsector below lists: **Primary models · Supporting models · Key multiples · Key metrics · Rationale · Special cases · PH data notes.** Representative PSE companies are named only where they justify the methodology.

---

### 3.1 Banks

*Representative: BDO, BPI, Metrobank (MBT), China Bank (CBC), Security Bank (SECB), PNB, EastWest (EW).*

| Element | Recommendation |
|---|---|
| **Primary models** | **Excess Return / Residual Income Model** (§2.5/2.4); **P/B ↔ ROE regression** (§2.11) |
| **Supporting models** | Dividend Discount Model (§2.3); P/E and P/TBV cross-check |
| **Key multiples** | **P/B**, **P/Tangible Book**, P/E, Dividend Yield |
| **Key metrics** | **ROE**, **ROA**, **CET1 / CAR**, **NPL ratio**, **NIM**, cost-to-income, book-value/share growth, loan growth, provision coverage |

**Rationale.** A bank's balance sheet *is* its business; debt (deposits, borrowings) is raw material, so FCFF/EV multiples are meaningless. Value equity directly. The **P/B–ROE relationship** is the workhorse: justified `P/B = (ROE − g) / (Ke − g)`. Residual income anchors on current book value plus the present value of ROE earned above Ke, which is exactly how the market prices banks. DDM works because Philippine banks are stable dividend payers. Always cross-check the RI/justified-P/B output against where the stock and peers trade on trailing P/B.

**Justified P/B (must-have engine formula):**
```
Justified P/B = (ROE − g) / (Ke − g)      →   Fair Price = Justified P/B × BV/Share
```

**Special cases.** Universal banks embedded in conglomerates (e.g., BPI within Ayala, Metrobank within GT Capital) are valued standalone here and folded into the parent's SOTP. Thrift/consumer-tilted banks warrant a higher provision/NPL sensitivity.

**PH data notes.** CET1/CAR and NPL ratios are disclosed in **NOTES** and BSP-mandated disclosures / **MD&A**; NIM often must be **PROXY**'d as Net Interest Income ÷ Average Earning Assets. Book value and net income from **SFP/IS**; dividends from **EDGE**.

---

### 3.2 Other Financial Institutions

*Representative: COL Financial (COL, brokerage), National Reinsurance (NRCP, reinsurance), The Philippine Stock Exchange (PSE, exchange operator), Vantage Equities (V), insurers/holding-adjacent financials.*

| Element | Recommendation |
|---|---|
| **Primary models** | **P/B ↔ ROE** and **Residual Income** for balance-sheet businesses (insurers, reinsurers, lenders); **P/E / DDM** for fee-based (brokers, exchange) |
| **Supporting models** | Dividend Discount Model; P/AUM or P/Revenue for asset-light platforms |
| **Key multiples** | P/B, P/E, P/AUM, Dividend Yield; **P/Embedded Value** for life insurers |
| **Key metrics** | ROE, combined ratio (insurers), solvency/RBC ratio, AUM growth, take rate, cost-to-income |

**Rationale.** This subsector is heterogeneous, so the engine must **split by business model**: (a) *balance-sheet financials* (insurers, reinsurers, financing/leasing) behave like banks → P/B, RI, embedded value; (b) *fee/transaction platforms* (brokers, the exchange) are asset-light, capital-light annuity businesses → P/E and DDM on stable payout. EV/EBITDA is acceptable for the fee-based subset but not the balance-sheet subset.

**Special cases.** Life insurers are ideally valued on **Embedded Value + Value of New Business**, but full EV disclosure is thin in PH; fall back to P/B and ROE. NRCP (reinsurance) is P/B-and-combined-ratio driven.

**PH data notes.** Combined/solvency ratios from **NOTES/AR**; AUM and take rate from **MDA**. Where embedded value is undisclosed, **PROXY** with adjusted book value.

---

### 3.3 Electricity, Energy, Power & Water

*Representative: Meralco (MER, distribution), Aboitiz Power (AP), First Gen (FGEN), ACEN (ACEN, renewables), Manila Water (MWC), SPC Power.*

| Element | Recommendation |
|---|---|
| **Primary models** | **FCFF DCF** (project/asset-level where possible) and **Dividend Discount Model** |
| **Supporting models** | **EV/EBITDA**; **EV/MW** (generation); Regulated Asset Base (RAB) valuation for regulated distribution/water |
| **Key multiples** | **EV/EBITDA**, **EV/MW**, P/E, Dividend Yield, EV/RAB |
| **Key metrics** | Installed & attributable MW, capacity factor, availability, PPA tenor & offtake, tariff/RAB, WACC vs. allowed return, net debt/EBITDA, payout |

**Rationale.** Power is capital-intensive with long-lived, contracted (PPA) or regulated cash flows — ideal for **DCF** because cash flows are forecastable from capacity, capacity factor, and tariff. **EV/EBITDA** normalizes across differing leverage and D&A. **EV/MW** cross-checks generation asset value against replacement cost and transaction comps. **Regulated distribution/water** (Meralco, Manila Water) is best framed as a **RAB × allowed return** utility model — value tracks the regulated asset base and the regulator-approved WACC. Stable, high payouts make **DDM** a strong co-primary.

**Special cases.** *Renewables (ACEN):* growth pipeline of MW favors DCF on contracted capacity + EV/MW on the pipeline; near-term earnings understate value. *Water concessions (Manila Water, Maynilad):* concession-life DCF with the concession-expiry as a hard terminal date (no perpetuity). *Generation vs. distribution vs. RE* should be modeled separately and, for diversified players, summed.

**PH data notes.** MW capacity, capacity factor, and PPA detail from **MDA/AR**; RAB and allowed return from ERC filings (**AR/NOTES**). EBITDA is often **PROXY** = Operating Income + D&A.

---

### 3.4 Food, Beverage & Tobacco

*Representative: Universal Robina (URC), San Miguel Food & Beverage (FB/SMFB), Century Pacific (CNPF), Monde Nissin (MONDE), Emperador (EMP), Ginebra San Miguel (GSMI), Del Monte (DMPL); tobacco via LT Group (LTG).*

| Element | Recommendation |
|---|---|
| **Primary models** | **FCFF DCF** and **EV/EBITDA** |
| **Supporting models** | P/E, DDM (mature staples), EPV (tobacco/mature) |
| **Key multiples** | **EV/EBITDA**, **P/E**, EV/Sales (for growth brands), Dividend Yield |
| **Key metrics** | Revenue growth, gross & EBITDA margin, volume vs. price/mix, market share, ROIC, input-cost sensitivity, net debt/EBITDA |

**Rationale.** Consumer staples have stable, predictable margins and strong brands → clean **DCF** and reliable **EV/EBITDA** peer comps (deep set of PH and ASEAN comparables). **P/E** is the market's headline lens for these names. Mature, cash-cow lines (tobacco, spirits) suit **EPV/DDM** because growth is modest and payout high.

**Special cases.** *Tobacco (PMFTC within LT Group):* extremely stable, high-margin cash flow → EPV and DDM; excise-tax trajectory is the key risk variable. *High-growth brands (Century Pacific, Monde early):* forward P/E and EV/Sales capture growth the trailing multiple misses.

**PH data notes.** Volume/price-mix and market share from **MDA/AR**; margins and D&A from **IS/CF**. Deep comp set makes relative valuation robust.

---

### 3.5 Construction, Infrastructure & Allied Services

*Representative: EEI Corp (EEI), Megawide Construction (MWIDE), infrastructure concessionaires (toll roads via MPTC), St. Gerrard.*

| Element | Recommendation |
|---|---|
| **Primary models** | **FCFF DCF** (esp. concession-life DCF for infrastructure assets); **EV/EBITDA** |
| **Supporting models** | P/E; SOTP where a builder also holds concessions; **Order-book / P/Book** |
| **Key multiples** | EV/EBITDA, P/E, EV/EBIT, Price/Book, EV/Order-Book |
| **Key metrics** | Order book / backlog, backlog-to-revenue coverage, EBIT margin, working-capital cycle, net gearing, concession IRR & tenor |

**Rationale.** Split the subsector: (a) *Contractors/EPC (EEI, Megawide-construction)* are cyclical, working-capital-heavy, thin-margin → **EV/EBITDA and P/E** with heavy weight on **backlog** as the forward-revenue driver; (b) *Infrastructure concessions (toll roads, airports, rail)* are annuity assets → **concession-life DCF** (finite terminal at concession expiry), like utilities. Megawide (builder + airport concession) is a natural **SOTP**.

**Special cases.** Concession assets must **not** use a perpetuity terminal value — the asset reverts to government at expiry; terminal value ≈ residual/handover value only.

**PH data notes.** Backlog/order book from **MDA/AR**; concession terms (tenor, tariff, IRR) from **NOTES/AR**. Percentage-of-completion accounting distorts working capital — model on cash.

---

### 3.6 Chemicals

*Representative: D&L Industries (DNL), Mabuhay Vinyl (MVC), LMG Chemicals-adjacent specialty players.*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** |
| **Supporting models** | P/E; EPV for commodity chemicals; EV/EBIT |
| **Key multiples** | EV/EBITDA, P/E, EV/Sales, EV/Tonne (commodity) |
| **Key metrics** | EBITDA margin, specialty vs. commodity mix, capacity utilization, feedstock spread, ROIC, volume growth |

**Rationale.** Distinguish **specialty** from **commodity** chemicals. *Specialty (D&L Industries)* earns durable margins on formulation IP → value like a branded industrial: **DCF + EV/EBITDA + P/E**, with growth (capacity expansion) explicitly modeled. *Commodity chemicals* are cyclical price-takers → **EV/EBITDA on mid-cycle margins** and **EPV**, with EV/Tonne as a capacity cross-check.

**Special cases.** D&L's Batangas capacity expansion is a growth story — use forward EV/EBITDA and DCF that captures utilization ramp, not trailing multiples.

**PH data notes.** Segment (specialty vs. commodity) mix from **MDA/AR**; capacity/utilization from **MDA**. Feedstock spreads may need **PROXY** from commodity indices.

---

### 3.7 Other Industrials

*Representative: Eagle Cement (EAGLE), Cemex Holdings Philippines (CHP), Holcim Philippines (HLCM) — cement; packaging & diversified manufacturers.*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** |
| **Supporting models** | **EPV** (mature/cyclical), P/E, EV/Tonne (cement capacity), Replacement-cost NAV |
| **Key multiples** | **EV/EBITDA**, **EV/Tonne**, P/E, EV/EBIT |
| **Key metrics** | Capacity (MTPA), utilization, cement volumes & ASP, energy/fuel cost, EBITDA/tonne, net debt/EBITDA |

**Rationale.** Cement and heavy manufacturing are capital-intensive and cyclical → **EV/EBITDA** (leverage- and D&A-neutral) is the primary lens, with **EV/Tonne** benchmarking installed capacity against replacement cost and M&A comps. **DCF** on normalized mid-cycle margins captures the cycle; **EPV** provides a no-growth floor for mature players.

**Special cases.** Cement is a near-textbook commodity-industrial: value on **mid-cycle EBITDA/tonne**, never peak or trough. Import competition and fuel (coal) costs are the swing variables.

**PH data notes.** Capacity (MTPA), utilization, and volumes from **MDA/AR**; EBITDA/tonne is **PROXY** = EBITDA ÷ tonnes sold.

---

### 3.8 Holding Firms

*Representative: Ayala Corp (AC), SM Investments (SM), JG Summit (JGS), Aboitiz Equity Ventures (AEV), GT Capital (GTCAP), San Miguel Corp (SMC), DMCI Holdings (DMC), LT Group (LTG), Alliance Global (AGI), Cosco Capital (COSCO), Filinvest Development (FDC).*

| Element | Recommendation |
|---|---|
| **Primary models** | **Sum-of-the-Parts (SOTP) / NAV** (§2.10) |
| **Supporting models** | P/E and P/B (consolidated cross-check); Look-through DDM |
| **Key multiples** | **Price/NAV (NAV discount)**, P/E, P/B |
| **Key metrics** | NAV per share, **holdco discount to NAV**, look-through earnings, parent net debt, dividend upstream from subsidiaries, portfolio mix (listed vs. unlisted) |

**Rationale.** A conglomerate's consolidated income statement blends unrelated businesses at different multiples — valuing it on a single P/E or DCF is meaningless. **SOTP is mandatory:** value each stake at its own appropriate multiple (listed stakes at market, unlisted at segment EV/EBITDA or DCF, real estate at RNAV), sum, subtract parent-level net debt and capitalized overhead, then apply an empirical **holdco discount**. This is the defining model of the PSE, whose top of the index is dominated by holding firms.

**Special cases.** Holdco discount varies by name — driven by liquidity, governance, capital-allocation track record, and portfolio transparency. Deeply diversified, opaque holdcos (e.g., SMC's mix of food, power, infrastructure, fuel) carry wider discounts; focused, well-governed holdcos (Ayala) narrower. GT Capital's value is dominated by its Metrobank + Toyota Motors Philippines stakes.

**PH data notes.** Segment values from PFRS 8 **segment NOTES**; listed-stake values from **MKT**; ownership % from **AR/EDGE**. Parent-only (non-consolidated) balance sheet, needed for parent net debt, is in the **NOTES**.

---

### 3.9 Property

*Representative: Ayala Land (ALI), SM Prime (SMPH), Robinsons Land (RLC), Megaworld (MEG), Vista Land (VLL), Filinvest Land (FLI), Cebu Landmasters (CLI), DoubleDragon (DD); REITs — AREIT, RCR, MREIT, FILRT.*

| Element | Recommendation |
|---|---|
| **Primary models** | **RNAV / NAV** (§2.9) for developers; **NAV + Dividend Yield / P/FFO** for REITs |
| **Supporting models** | **SOTP** (recurring lease income vs. residential dev); FCFF DCF on residential pipeline; P/E, P/B |
| **Key multiples** | **P/NAV (RNAV discount)**, P/E, P/B; **P/FFO, Dividend Yield, Cap Rate** (REITs); Price/GDV |
| **Key metrics** | RNAV/share, landbank (ha) & fair value, GDV of pipeline, reservation/pre-sales, recurring vs. dev income mix, occupancy, rental reversion, net gearing; (REIT) FFO/AFFO, DPU, WALE, cap rate |

**Rationale.** Property developers hold appreciating land carried below market → **RNAV** marks landbank and investment property to appraised value, the standard analyst anchor (usually applied at a discount). Integrated developers earn two distinct streams — lumpy residential **development** income and stable **recurring lease** (mall/office) income — best captured by **SOTP** (capitalize recurring income at a low cap rate; DCF/RNAV the development pipeline). **REITs** are valued as income vehicles: **P/FFO, dividend yield vs. required yield, and P/NAV**.

**Special cases.** *REITs (AREIT, RCR, MREIT):* Philippine REIT law mandates ≥90% income distribution → value primarily on **dividend yield vs. a required spread over the 10Y govvy** and **P/NAV**; FFO/AFFO replace net income. *SM Prime:* mall-recurring-income heavy → weight the capitalized-lease-income (SOTP) leg. *Vista Land / mass-housing:* pre-sales momentum and NAV discount dominate.

**PH data notes.** Investment-property fair values (PAS 40) and landbank in **NOTES/AR**; pre-sales/reservations and GDV in **MDA/AR**; REIT DPU and occupancy in **EDGE** disclosures.

---

### 3.10 Media

*Representative: GMA Network (GMA7), ABS-CBN (ABS), Manila Bulletin (MB), DFNN, Manila Broadcasting.*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** |
| **Supporting models** | P/E, DDM (GMA — high payout), EV/Sales (digital transition) |
| **Key multiples** | EV/EBITDA, P/E, Dividend Yield, EV/Sales |
| **Key metrics** | Ad revenue, audience share/ratings, EBITDA margin, digital revenue mix, content cost, cord-cutting/structural decline rate, payout |

**Rationale.** Traditional broadcast media is a mature, ad-cyclical, cash-generative business → **EV/EBITDA** and **DCF**. GMA's high, stable payout makes **DDM** a strong support. The overriding modeling issue is **structural decline** of linear TV/print vs. **digital pivot** — the DCF terminal growth assumption (often near-zero or negative for linear) is the key value driver, and EV/Sales helps where a digital arm is scaling but not yet profitable.

**Special cases.** ABS-CBN post-franchise-denial is a restructuring/asset story (content library + real estate) → lean on **NAV/SOTP** over earnings multiples. Structurally declining assets should carry conservative (≤0%) terminal growth.

**PH data notes.** Ad revenue and audience share from **MDA/AR**; digital-mix disclosure is often qualitative (**PROXY** from segment revenue).

---

### 3.11 Telecommunications

*Representative: PLDT (TEL), Globe Telecom (GLO), Converge ICT (CNVRG), DITO CME (DITO).*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** |
| **Supporting models** | **DDM** (PLDT, Globe — dividend payers); **EV/Subscriber**; SOTP (tower/data-center carve-outs) |
| **Key multiples** | **EV/EBITDA**, **EV/Subscriber**, P/E, Dividend Yield, EV/OpFCF |
| **Key metrics** | Subscribers (mobile/home broadband), **ARPU**, churn, data traffic, EBITDA margin, **CapEx/Sales (capex intensity)**, net debt/EBITDA, spectrum |

**Rationale.** Telcos are capital-intensive with heavy, differing D&A and leverage → **EV/EBITDA** is the primary comparability lens; **DCF** captures the capex cycle and free-cash-flow inflection as network build matures. **EV/Subscriber** benchmarks value per customer against transaction and regional comps. Mature incumbents (PLDT, Globe) pay large dividends → **DDM** support. **SOTP** increasingly matters as telcos monetize **towers and data centers** (PLDT) at higher multiples than the connectivity business.

**Special cases.** *DITO CME:* pre-profitability challenger burning cash to build share → value on **EV/Subscriber and EV/Sales / subscriber-ramp DCF**, not earnings multiples. *Converge:* growth broadband → forward EV/EBITDA and subscriber-driven DCF. *PLDT:* explicit SOTP crediting the data-center (ePLDT/tower) value.

**PH data notes.** Subscribers, ARPU, churn, data traffic from **MDA/AR**; capex from **CF**; tower/DC detail from **AR** and disclosures.

---

### 3.12 Information Technology

*Representative: NOW Corp (NOW), Xurpas (X), DFNN, IT-services & software microcaps; (electronics manufacturers sit in Electrical Components, §3.20).*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/Sales** and **FCFF DCF** (growth-stage); **EV/EBITDA / P/E** once profitable |
| **Supporting models** | EV/EBITDA, P/E, EV/Users or EV/GMV (platforms), VC-style scenario DCF |
| **Key multiples** | **EV/Sales**, **EV/EBITDA**, P/E, PEG, EV/Gross Profit |
| **Key metrics** | Revenue growth, gross margin, recurring/SaaS mix, retention, rule-of-40 (growth+margin), cash burn/runway, unit economics |

**Rationale.** PSE-listed IT names are mostly small, high-growth or pre-profit → earnings multiples are unstable or undefined. **EV/Sales** (and EV/Gross Profit) is the practical primary multiple, cross-checked with a **scenario DCF** that models the path to profitability. Once a name matures into consistent earnings, migrate to **EV/EBITDA and P/E** with **PEG** to growth-adjust.

**Special cases.** Platform/marketplace names value on **EV/GMV or EV/Users**; loss-making growth names need **cash-runway and burn** as a survival gate before any DCF. Given thin float and volatility, apply an **illiquidity premium** to Ke.

**PH data notes.** Revenue mix, retention, and GMV are often only in **MDA/AR** narrative — many KPIs must be **PROXY**'d. Small-sample comps: supplement with regional/global software multiples, haircut for size and liquidity.

---

### 3.13 Transportation Services

*Representative: International Container Terminal Services (ICT, ports), Cebu Air (CEB, airline), PAL Holdings (PAL), 2GO Group (2GO, shipping/logistics), Asian Terminals (ATI), MacroAsia (MAC), Chelsea Logistics (C).*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** (asset/concession-aware) |
| **Supporting models** | P/E; **EV/TEU** (ports), **EV/Seat / EV/ASK** (airlines); SOTP; NAV (fleet) |
| **Key multiples** | **EV/EBITDA**, **EV/TEU**, EV/ASK, P/E, EV/EBITDAR (lease-adjusted) |
| **Key metrics** | Throughput (TEU), tariff, utilization; (air) RPK/ASK, load factor, yield, fuel cost, fleet age; net debt/EBITDA, concession tenor |

**Rationale.** Transport is capital-intensive with heavy leases/debt → **EV/EBITDA** (and lease-adjusted **EV/EBITDAR** for airlines) is primary. **DCF** captures capex and concession economics. Sub-segments need value-driver multiples: **ports → EV/TEU** and concession-life DCF (ICTSI's global port portfolio is best done **SOTP by terminal/concession**); **airlines → EV/ASK, yield, load factor** with fuel as the swing variable and a fleet-based NAV floor.

**Special cases.** *ICTSI (ICT):* a portfolio of global port concessions → **SOTP / concession-life DCF**, each terminal finite-lived. *Airlines (CEB, PAL):* highly cyclical, operationally leveraged, often negative-equity in downturns → EV/EBITDAR and fleet NAV, with scenario analysis on fuel and demand.

**PH data notes.** Throughput, ASK/RPK, load factor, yield from **MDA/AR**; lease detail (PFRS 16) from **NOTES**; concession terms from **AR**.

---

### 3.14 Hotel & Leisure

*Representative: Waterfront Philippines (WPI), Grand Plaza Hotel (GPH), Acesite/Holiday Inn (ACE), Boulevard Holdings (BHI); leisure/resort operators.*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **RNAV / NAV** (property-backed) |
| **Supporting models** | **FCFF DCF**; **EV/Room (per key)**; P/E |
| **Key multiples** | **EV/EBITDA**, **EV/Room**, P/NAV, EV/Sales |
| **Key metrics** | Occupancy, **ADR** (average daily rate), **RevPAR**, GOP margin, room count/pipeline, property fair value, seasonality |

**Rationale.** Hotels are real-estate-backed operating businesses → dual lens: **EV/EBITDA** on operations and **RNAV** on the underlying property (land + buildings carried below market). **EV/Room** benchmarks value per key against transaction comps, useful when earnings are depressed or volatile. **RevPAR (= occupancy × ADR)** is the fundamental revenue driver feeding the DCF.

**Special cases.** Many PH hotel stocks are asset-rich but earnings-thin/illiquid → **NAV dominates** and earnings multiples are secondary. Casino-integrated resorts belong in Casinos & Gaming (§3.21), not here.

**PH data notes.** Occupancy/ADR/RevPAR from **MDA/AR** (sometimes only partially disclosed — **PROXY** RevPAR from room revenue ÷ available room-nights); property fair values from **NOTES**.

---

### 3.15 Education

*Representative: Far Eastern University (FEU), Centro Escolar University (CEU), iPeople (IPO, holds Mapúa), STI Education Systems (STI), Republic Central Colleges.*

| Element | Recommendation |
|---|---|
| **Primary models** | **DCF (FCFF)** and **P/E** |
| **Supporting models** | **DDM** (high, stable payout); EV/EBITDA; **RNAV** (campus real estate) |
| **Key multiples** | P/E, EV/EBITDA, Dividend Yield, **EV/Student**, P/NAV |
| **Key metrics** | Enrollment, tuition/student, EBITDA margin, campus utilization, real-estate value, payout, demographic/enrollment growth |

**Rationale.** Private education generates stable, annuity-like, high-margin cash flows with predictable enrollment → clean **DCF** and **P/E**, with **DDM** support given consistently high payouts. **EV/Student** benchmarks per-enrollee value. Many schools also sit on **valuable urban campus real estate** carried at cost → **RNAV** provides an asset floor and can exceed the operating value for land-rich, enrollment-challenged schools.

**Special cases.** *iPeople (IPO):* a holdco for Mapúa + basic-ed → **SOTP**. Land-rich, low-enrollment schools (e.g., older Manila campuses) → RNAV can dominate earnings value.

**PH data notes.** Enrollment and tuition from **MDA/AR**; campus/real-estate fair value from **NOTES** (often at cost — needs appraisal **PROXY**).

---

### 3.16 Other Services

*Heterogeneous catch-all: diversified service firms, business-process and support-services companies, misc. operating companies not fitting other buckets.*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** (default for cash-generative services) |
| **Supporting models** | P/E; EV/Sales (asset-light/growth); NAV/SOTP (asset-heavy or diversified) |
| **Key multiples** | EV/EBITDA, P/E, EV/Sales, P/B |
| **Key metrics** | Revenue growth, EBITDA margin, ROIC, recurring-revenue mix, net gearing |

**Rationale.** Because this is a residual classification, the engine must **infer sub-type from financial structure** rather than apply a fixed model: asset-light, profitable services → **EV/EBITDA + P/E**; growth/pre-profit → **EV/Sales**; asset-heavy or clearly diversified → **NAV/SOTP**. Default to EV/EBITDA + DCF and let the routing rules (Part 5) reclassify based on margins, asset intensity, and segment count.

**Special cases.** Any constituent that is effectively a holding company must be routed to **SOTP** (§3.8); any that is real-estate-backed to **RNAV**.

**PH data notes.** Segment detail from **NOTES** is essential for correct routing.

---

### 3.17 Mining

*Representative: Semirara Mining & Power (SCC, coal + power), Nickel Asia (NIKL), Philex Mining (PX), Global Ferronickel (FNI), Apex Mining (APX), Atlas Consolidated (AT), Marcventures (MARC), OceanaGold (OGP).*

| Element | Recommendation |
|---|---|
| **Primary models** | **NAV (reserve-based / life-of-mine DCF)** and **EV/EBITDA** |
| **Supporting models** | **EV/Reserve (2P)**, **EV/Resource**, EV/Tonne (production), P/NAV, P/E |
| **Key multiples** | **P/NAV**, **EV/EBITDA**, **EV/Reserve**, EV/Tonne |
| **Key metrics** | 2P reserves & resources (tonnes/oz), mine life, grade, C1/AISC cash cost, strip ratio, realized commodity price, production volume, FX (USD revenue) |

**Rationale.** A mine is a **depleting asset with a finite life** — the correct model is a **life-of-mine (reserve-based) NAV/DCF**: forecast production from the reserve schedule, apply commodity-price decks and cash costs, discount to a finite terminal (reserve exhaustion), never a perpetuity. **P/NAV** is the primary trading metric miners are quoted on. **EV/Reserve** and **EV/Tonne** cross-check against transaction and peer comps. **EV/EBITDA** on mid-cycle prices supports for producing miners.

**Special cases.** *Semirara (SCC):* integrated coal + power — **SOTP** (mining NAV + power DCF). *Explorers/developers (pre-production):* no earnings → value on **EV/Resource** and risked NAV only. Commodity price and FX (revenue is USD-linked, costs partly peso) are the dominant value drivers → run **price scenarios**, not a point estimate.

**PH data notes.** 2P reserves, grade, mine life, and cash costs from **NOTES / AR / reserve statements** (MGB/JORC-style disclosures); production volumes from **MDA**; commodity prices from external decks (**PROXY** from forward curves/consensus long-run).

---

### 3.18 Oil

*Representative: Petron (PCOR, downstream refining/marketing), PXP Energy (PXP, upstream E&P), Philodrill (OV), Oriental Petroleum (OPM), Basic Energy (BSC).*

| Element | Recommendation |
|---|---|
| **Primary models** | **Reserve-based NAV / DCF** (upstream E&P); **EV/EBITDA + FCFF DCF** (downstream refining/marketing) |
| **Supporting models** | **EV/Reserve (boe)**, EV/Resource (upstream); EV/EBIT, P/E, replacement-cost NAV (downstream) |
| **Key multiples** | **EV/EBITDA**, **EV/Reserve (2P boe)**, P/NAV, EV/Throughput (refining) |
| **Key metrics** | 2P reserves (boe), production, lifting cost, realized crude price; (downstream) refining margin/crack spread, throughput, retail volumes, inventory gains/losses |

**Rationale.** Oil splits sharply into **upstream** and **downstream** — the engine must classify first. *Upstream E&P (PXP, Philodrill):* depleting reserves → **reserve-based NAV/DCF** and **EV/Reserve**, finite-life like mining, driven by crude price and reserve certainty. *Downstream (Petron):* a refining-and-marketing throughput business, not a reserve story → **EV/EBITDA and DCF** on refining margins and volumes, with inventory-holding gains/losses normalized.

**Special cases.** *PXP Energy:* value is dominated by the **risked (probability-weighted) NAV** of contested/undeveloped blocks (e.g., Reed Bank) — an option/scenario NAV, not a producing-asset DCF. *Petron:* highly leveraged, thin refining margins → EV/EBITDA with net-debt sensitivity and mid-cycle crack spreads.

**PH data notes.** Reserves and lifting costs from **NOTES/AR**; refining margins and crack spreads are largely external (**PROXY** from regional Dubai/Singapore benchmarks); throughput and retail volumes from **MDA**.

---

### 3.19 Small, Medium & Emerging Board

*Early-stage and smaller-cap issuers on the SME board (heterogeneous across industries).*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/Sales** and **scenario/VC-style DCF** (pre-profit); **EV/EBITDA / P/E** (profitable) |
| **Supporting models** | NAV/asset-based (floor); comparable-company multiples with size & liquidity discounts |
| **Key multiples** | EV/Sales, EV/EBITDA, P/E, P/B |
| **Key metrics** | Revenue growth, path-to-profit, cash burn/runway, gross margin, promoter ownership, free float/liquidity |

**Rationale.** SME-board names are small, often early-stage, thinly traded, and data-sparse → apply the **relevant mature-sector model but with heavy adjustments**: (1) add a **size/illiquidity premium (1.5–3.0%)** to Ke; (2) prefer **revenue-based multiples** and **asset-based floors** where earnings are unreliable; (3) use **scenario DCF** rather than a single base case. Route each name to its *industry* framework (Parts 3.1–3.18, 3.20–3.22), then apply the SME risk overlay.

**Special cases.** Governance, related-party transactions, and free-float concentration are material risks — reflect them in the discount rate and in a wider valuation range, not a point estimate.

**PH data notes.** Disclosure is thinner; lean on **NAV** and audited **SFP** as the reliable floor.

---

### 3.20 Electrical Components & Equipment

*Representative: Integrated Micro-Electronics (IMI), Cirtek Holdings (TECH), Ionics (ION); electronics-manufacturing-services (EMS) and components.*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** |
| **Supporting models** | P/E, EV/Sales (cyclical trough), EV/EBIT |
| **Key multiples** | **EV/EBITDA**, P/E, EV/Sales, PEG |
| **Key metrics** | Revenue growth, EBITDA/EBIT margin, capacity utilization, order book, customer concentration, FX (USD revenue), inventory turns, ROIC |

**Rationale.** EMS/components are cyclical, capital-intensive, thin-but-scalable-margin export businesses tied to the global electronics cycle → **EV/EBITDA** (leverage-neutral, cross-border comparable) is primary, with **DCF** capturing the capex-and-utilization cycle. **P/E** and **PEG** support in up-cycles; **EV/Sales** is the trough fallback when margins compress to near zero.

**Special cases.** Revenue is USD-linked with peso costs → **FX is a core driver**; customer concentration (a few large OEMs) warrants a scenario/haircut. Global cycle means **mid-cycle margins**, not spot, in the DCF and multiples.

**PH data notes.** Utilization, order book, and customer mix from **MDA/AR**; margins from **IS**. Benchmark against regional EMS comps (Malaysia/Thailand) given the thin PH peer set.

---

### 3.21 Casinos & Gaming

*Representative: Bloomberry Resorts (BLOOM, Solaire), DigiPlus Interactive (PLUS, e-games/e-bingo), Premium Leisure (PLC), Leisure & Resorts (LR), PhilWeb (WEB), Manila Jockey (MJC), Belle Corp (BEL).*

| Element | Recommendation |
|---|---|
| **Primary models** | **EV/EBITDA** and **FCFF DCF** |
| **Supporting models** | **RNAV** (integrated-resort real estate); EV/Sales (online-gaming growth); P/E; SOTP |
| **Key multiples** | **EV/EBITDA**, EV/Sales (online), P/E, P/NAV |
| **Key metrics** | GGR (gross gaming revenue), mass vs. VIP mix, hold %, **EBITDA margin**, property EBITDA, GMV/active users (online), license tenor, net debt/EBITDA |

**Rationale.** Casinos are capital-intensive integrated resorts with strong operating leverage → **EV/EBITDA** is the global-standard primary metric (property-level EBITDA especially), with **DCF** capturing ramp of new properties. The underlying **real estate** supports an **RNAV** floor. **GGR mix (mass vs. VIP)** and **hold %** drive the revenue model.

**Special cases.** *Online/e-games (DigiPlus/PLUS):* explosive, asset-light growth → value on **EV/EBITDA on forward earnings and EV/Sales / GGR**, with regulatory (PAGCOR license, POGO policy) risk as a discrete scenario/haircut — regulatory risk is the dominant swing factor for this subsector. *Bloomberry:* SOTP across Solaire Entertainment City + Solaire North + Jeju, each a property-level EBITDA/DCF.

**PH data notes.** GGR, mass/VIP mix, and hold from **MDA/AR**; property-level EBITDA sometimes only partly disclosed (**PROXY** from segment reporting).

---

### 3.22 Retail

*Representative: Puregold (PGOLD), Robinsons Retail (RRHI), Wilcon Depot (WLCON), Metro Retail (MRSGI), Philippine Seven (SEVN), SSI Group (SSI), AllHome (HOME); SM Retail (within SM).*

| Element | Recommendation |
|---|---|
| **Primary models** | **FCFF DCF** and **EV/EBITDA** |
| **Supporting models** | P/E, EV/Sales (high-growth formats), DDM (mature) |
| **Key multiples** | **EV/EBITDA**, **P/E**, EV/Sales, P/FCF |
| **Key metrics** | **SSSG (same-store sales growth)**, store count & net openings, sales/sqm, gross & EBITDA margin, inventory turns, cash conversion cycle, lease-adjusted leverage (PFRS 16) |

**Rationale.** Retail is a scalable, cash-generative, store-rollout business → **DCF** built from **store-count growth × sales/store × margin** is the natural intrinsic model, with **EV/EBITDA** the primary trading comp (lease-adjusted for PFRS 16 comparability). **SSSG** and **new-store productivity** are the core operating drivers; **P/E** is the headline retail multiple.

**Special cases.** *High-growth formats (Wilcon, AllHome):* forward EV/EBITDA and EV/Sales capture the rollout runway. Post-PFRS 16, capitalized leases inflate EBITDA and debt → use **EV/EBITDAR or lease-adjusted metrics** for cross-company comparability.

**PH data notes.** SSSG, store count, and sales/sqm from **MDA/AR**; lease liabilities from **NOTES** (PFRS 16).

---

### 3.23 ETF – Equity

*Representative: First Metro Philippine Equity Exchange-Traded Fund (FMETF) — currently the sole PSE-listed equity ETF.*

| Element | Recommendation |
|---|---|
| **Primary model** | **Net Asset Value (NAV) pass-through** — no intrinsic corporate model applies |
| **Supporting** | Premium/discount-to-NAV monitoring; tracking-error check |
| **Key multiples** | Price/NAV (premium or discount), expense ratio, tracking error |
| **Key metrics** | Published NAV per unit, index tracked (PSEi), AUM, bid-ask spread |

**Rationale.** An ETF has no independent cash flows — its fair value **is** the published NAV of its underlying basket. The engine should **bypass all fundamental models** and treat fair value = **official NAV per unit** (published daily by the fund manager), flag any price premium/discount to NAV, and note tracking error and expense ratio. No DCF, multiples, or SOTP.

**PH data notes.** NAV per unit is published daily by the fund manager and on **EDGE**; underlying index is the PSEi.

---

## 4. Master Reference Table

| PSE Subsector | Primary Model(s) | Supporting Model(s) | Key Multiples | Core Required Inputs | Representative Companies | Special Notes / Exceptions |
|---|---|---|---|---|---|---|
| **Banks** | Excess Return / Residual Income; P/B–ROE | DDM; P/E; P/TBV | P/B, P/TBV, P/E, Div Yield | Book value, Net income, ROE, Ke, CAR/CET1, NPL, dividends | BDO, BPI, MBT, SECB, CBC | No FCFF/EV multiples — debt is raw material. Justified P/B=(ROE−g)/(Ke−g) |
| **Other Financial Institutions** | P/B–ROE / RI (balance-sheet); P/E / DDM (fee-based) | DDM; P/AUM; Embedded Value | P/B, P/E, P/AUM, Div Yield | Book value, NI, ROE, AUM, combined/solvency ratio | COL, NRCP, PSE, Vantage | Split balance-sheet vs. fee-based; insurers → embedded value (proxy: adj. book) |
| **Electricity, Energy, Power & Water** | FCFF DCF; DDM | EV/EBITDA; EV/MW; RAB model | EV/EBITDA, EV/MW, P/E, Div Yield | MW, capacity factor, PPA/tariff, EBITDA, net debt, WACC | MER, AP, FGEN, ACEN, MWC | Regulated (MER, MWC) → RAB×allowed return; water/concessions → finite terminal |
| **Food, Beverage & Tobacco** | FCFF DCF; EV/EBITDA | P/E; DDM; EPV | EV/EBITDA, P/E, EV/Sales, Div Yield | Revenue, margins, volume/price-mix, D&A, WACC | URC, CNPF, SMFB, MONDE, EMP | Tobacco/spirits → EPV/DDM; growth brands → forward P/E, EV/Sales |
| **Construction, Infrastructure & Allied** | FCFF/Concession DCF; EV/EBITDA | P/E; SOTP; P/Book | EV/EBITDA, P/E, EV/Order-Book | Order book, EBIT margin, WC cycle, concession IRR/tenor | EEI, MWIDE, MPTC | Concessions → finite terminal (no perpetuity); builder+concession → SOTP |
| **Chemicals** | EV/EBITDA; FCFF DCF | P/E; EPV; EV/EBIT | EV/EBITDA, P/E, EV/Tonne | EBITDA margin, mix, utilization, feedstock spread | DNL, MVC | Specialty → DCF/growth; commodity → mid-cycle EBITDA/EPV |
| **Other Industrials** | EV/EBITDA; FCFF DCF | EPV; P/E; EV/Tonne; Replacement NAV | EV/EBITDA, EV/Tonne, P/E | Capacity (MTPA), utilization, volumes/ASP, EBITDA/tonne | EAGLE, CHP, HLCM | Cement → mid-cycle EBITDA/tonne; never peak/trough |
| **Holding Firms** | **SOTP / NAV** | P/E, P/B (cross-check); look-through DDM | P/NAV, P/E, P/B | Stake values, ownership %, parent net debt, segment data | AC, SM, JGS, AEV, GTCAP, SMC | Holdco discount 15–40%; never consolidated P/E/DCF |
| **Property** | RNAV/NAV (developers); NAV+Div Yield/P/FFO (REITs) | SOTP; FCFF DCF; P/E, P/B | P/NAV, P/FFO, Div Yield, Cap Rate | Landbank FV, investment-property FV, pre-sales, GDV, FFO/DPU | ALI, SMPH, MEG, AREIT | REITs → yield vs. required spread; integrated devs → SOTP (recurring vs. dev) |
| **Media** | EV/EBITDA; FCFF DCF | P/E; DDM; EV/Sales | EV/EBITDA, P/E, EV/Sales, Div Yield | Ad revenue, audience share, EBITDA margin, digital mix | GMA7, ABS, MB | Structural decline → ≤0% terminal; ABS-CBN → NAV/SOTP restructuring story |
| **Telecommunications** | EV/EBITDA; FCFF DCF | DDM; EV/Subscriber; SOTP | EV/EBITDA, EV/Sub, P/E, Div Yield | Subscribers, ARPU, churn, EBITDA, capex/sales, net debt | TEL, GLO, CNVRG, DITO | DITO → EV/Sub, subscriber-ramp; PLDT → SOTP (towers/data centers) |
| **Information Technology** | EV/Sales; scenario DCF | EV/EBITDA; P/E; EV/GMV | EV/Sales, EV/EBITDA, PEG | Revenue growth, gross margin, retention, burn/runway | NOW, X, DFNN | Pre-profit → EV/Sales; add illiquidity premium; use regional comps |
| **Transportation Services** | EV/EBITDA; FCFF DCF | P/E; EV/TEU; EV/ASK; SOTP; fleet NAV | EV/EBITDA, EV/EBITDAR, EV/TEU | Throughput/ASK, load factor, yield, fuel, concession tenor | ICT, CEB, PAL, 2GO, ATI | ICTSI → SOTP by concession; airlines → EV/EBITDAR + fleet NAV |
| **Hotel & Leisure** | EV/EBITDA; RNAV/NAV | FCFF DCF; EV/Room; P/E | EV/EBITDA, EV/Room, P/NAV | Occupancy, ADR, RevPAR, GOP, property FV, room count | WPI, GPH, ACE | Asset-rich/earnings-thin → NAV dominates |
| **Education** | FCFF DCF; P/E | DDM; EV/EBITDA; RNAV | P/E, EV/EBITDA, EV/Student, Div Yield | Enrollment, tuition, EBITDA margin, campus FV, payout | FEU, CEU, IPO, STI | Land-rich schools → RNAV floor; iPeople → SOTP |
| **Other Services** | EV/EBITDA; FCFF DCF | P/E; EV/Sales; NAV/SOTP | EV/EBITDA, P/E, EV/Sales, P/B | Revenue, margins, asset intensity, segment data | (heterogeneous) | Infer sub-type from financials; holdco-like → SOTP; asset-backed → RNAV |
| **Mining** | Reserve-based NAV / LOM DCF; EV/EBITDA | EV/Reserve; EV/Tonne; P/NAV; P/E | P/NAV, EV/EBITDA, EV/Reserve | 2P reserves, grade, mine life, AISC, commodity price, FX | SCC, NIKL, PX, FNI, APX | Finite LOM terminal; run price scenarios; SCC → SOTP (coal+power) |
| **Oil** | Reserve NAV/DCF (upstream); EV/EBITDA+DCF (downstream) | EV/Reserve (boe); EV/EBIT; P/E | EV/EBITDA, EV/Reserve, P/NAV | 2P boe, lifting cost, crude price, refining margin, throughput | PCOR, PXP, OV | Split up/downstream; PXP → risked option NAV (Reed Bank) |
| **Small, Medium & Emerging Board** | EV/Sales; scenario DCF; (EV/EBITDA if profitable) | NAV floor; sector comps w/ discounts | EV/Sales, EV/EBITDA, P/E, P/B | Revenue, burn/runway, gross margin, float, promoter stake | (mixed) | Route to industry model + SME risk overlay (illiquidity premium, NAV floor) |
| **Electrical Components & Equipment** | EV/EBITDA; FCFF DCF | P/E; EV/Sales; EV/EBIT | EV/EBITDA, P/E, EV/Sales, PEG | Revenue, margins, utilization, order book, FX | IMI, TECH, ION | USD-revenue FX driver; mid-cycle margins; regional EMS comps |
| **Casinos & Gaming** | EV/EBITDA; FCFF DCF | RNAV; EV/Sales (online); SOTP | EV/EBITDA, EV/Sales, P/NAV | GGR, mass/VIP mix, hold %, property EBITDA, license tenor | BLOOM, PLUS, PLC | Regulatory risk = key scenario; online → EV/Sales; BLOOM → SOTP by property |
| **Retail** | FCFF DCF; EV/EBITDA | P/E; EV/Sales; DDM | EV/EBITDA, P/E, EV/Sales, P/FCF | SSSG, store count, sales/sqm, margins, lease liabilities | PGOLD, RRHI, WLCON, SEVN | DCF from store rollout × sales/store; lease-adjust (PFRS 16) |
| **ETF – Equity** | **NAV pass-through** | Premium/discount & tracking-error monitor | Price/NAV, expense ratio | Published NAV/unit, index, AUM | FMETF | Bypass all fundamental models; fair value = official NAV |

---

## 5. The Automated Valuation Decision Framework

This section converts the research into deterministic engine logic. It is structured as (5.1) a classification-and-routing pipeline, (5.2) per-family execution rules, (5.3) blending weights, and (5.4) fallback chains.

### 5.1 Classification & Routing Pipeline

The engine runs this decision cascade for every ticker, in order. The **first matching rule wins** the "family," which then selects the model stack.

```
STEP 1 — Hard overrides by PSE subsector classification
  IF subsector == "ETF – Equity"            → FAMILY = PASSTHROUGH_NAV        (stop)
  IF subsector == "Banks"                    → FAMILY = FINANCIAL_EQUITY
  IF subsector == "Other Financial Institutions":
        IF balance-sheet type (insurer/lender/reinsurer) → FAMILY = FINANCIAL_EQUITY
        ELSE (broker/exchange/fee)                        → FAMILY = FEE_LIGHT
  IF subsector == "Holding Firms"            → FAMILY = SOTP
  IF subsector == "Mining"                   → FAMILY = DEPLETING_ASSET
  IF subsector == "Oil":
        IF upstream (E&P)                    → FAMILY = DEPLETING_ASSET
        ELSE (downstream refining/mktg)      → FAMILY = CAPITAL_INTENSIVE

STEP 2 — Structural detectors (for Property, Utilities, Transport, Services, SME)
  IF is_REIT flag OR mandated ≥90% payout    → FAMILY = INCOME_VEHICLE
  IF subsector == "Property"                 → FAMILY = ASSET_REVALUED  (RNAV/SOTP)
  IF has_concession (finite-life contract)   → FAMILY = FINITE_LIFE_DCF
  IF segment_count ≥ 3 AND cross-industry    → FAMILY = SOTP
  IF asset_intensity_high AND EBITDA_stable  → FAMILY = CAPITAL_INTENSIVE  (EV/EBITDA+DCF)

STEP 3 — Profitability / lifecycle gate (applies within family)
  IF Net Income ≤ 0 for ≥2 of last 3 yrs OR pre-revenue-scaling:
        DEMOTE earnings multiples; PROMOTE EV/Sales, NAV floor, scenario DCF
  IF SME board:                              APPLY size/illiquidity premium (+1.5–3.0% to Ke)
                                             WIDEN output to a range, not a point

STEP 4 — Default
  ELSE                                       → FAMILY = CAPITAL_INTENSIVE (EV/EBITDA + FCFF DCF + P/E)
```

**Subsector → default family map:**

| Family | Subsectors routed here |
|---|---|
| `FINANCIAL_EQUITY` | Banks; balance-sheet Other Financials |
| `FEE_LIGHT` | Broker/exchange Other Financials |
| `SOTP` | Holding Firms; multi-segment cross-industry names; iPeople; Semirara (with DEPLETING sub-leg) |
| `ASSET_REVALUED` | Property developers; land-rich Hotels, Education, Media-restructuring |
| `INCOME_VEHICLE` | REITs |
| `FINITE_LIFE_DCF` | Water/power concessions; infrastructure concessions; port/airport concessions; upstream reserves |
| `DEPLETING_ASSET` | Mining; upstream Oil |
| `CAPITAL_INTENSIVE` | Utilities/generation, Telecom, Media, Industrials, Chemicals, Cement, Transport, Casinos, Retail, F&B, Downstream Oil, Electrical Components, Other Services (default) |
| `GROWTH_SALES` | IT; pre-profit SME; DITO/Converge-type; online gaming |
| `PASSTHROUGH_NAV` | ETF |

### 5.2 Per-Family Execution Rules

Each family defines: **run first**, **always-accompany**, **cross-check multiple**, **key gate**.

| Family | Run first (primary) | Always accompany | Relative cross-check | Terminal-value rule | Output |
|---|---|---|---|---|---|
| `FINANCIAL_EQUITY` | Residual Income / Excess Return | Justified P/B–ROE; DDM | Trailing P/B, P/TBV, P/E vs. peers | ROE fades to Ke | Equity/share |
| `FEE_LIGHT` | P/E (normalized) | DDM | P/E, EV/EBITDA vs. peers | Gordon g ≤ GDP | Equity/share |
| `SOTP` | Sum-of-the-Parts | Look-through P/E; parent NAV | P/NAV discount vs. history | per-part appropriate | Equity/share × (1−holdco disc.) |
| `ASSET_REVALUED` | RNAV | SOTP (recurring vs. dev); DCF on pipeline | P/NAV, P/B vs. peers | dev pipeline finite | Equity/share × (1−NAV disc.) |
| `INCOME_VEHICLE` | Dividend Yield vs. required (Gordon on DPU) | P/NAV; P/FFO | Yield & P/FFO vs. peers | Gordon on DPU | Equity/share |
| `FINITE_LIFE_DCF` | Concession-life FCFF DCF | EV/EBITDA | EV/EBITDA vs. peers | **finite — NO perpetuity** (residual/handover) | EV→Equity/share |
| `DEPLETING_ASSET` | Reserve-based (LOM) NAV/DCF | EV/Reserve; EV/EBITDA | P/NAV, EV/Reserve, EV/Tonne | **finite — reserve exhaustion** | EV→Equity/share; run price scenarios |
| `CAPITAL_INTENSIVE` | FCFF DCF | EV/EBITDA | EV/EBITDA, P/E, EV/Sales vs. peers | Gordon g≤GDP or exit multiple | EV→Equity/share |
| `GROWTH_SALES` | EV/Sales | Scenario/VC DCF; EV/Gross Profit | EV/Sales, EV/GMV vs. regional | path-to-profit modeled | EV→Equity/share (range) |
| `PASSTHROUGH_NAV` | Official NAV/unit | premium/discount monitor | Price/NAV | n/a | NAV/unit |

### 5.3 Blending Into a Weighted Intrinsic Value

When ≥2 models produce reliable outputs, blend them into a single intrinsic value per share. **Weights are confidence-scaled**, not fixed: each model returns a `(value, confidence 0–1)` pair, where confidence is penalized for missing inputs, proxy-heavy inputs, thin comp sets, and negative/volatile earnings.

```
Intrinsic Value = Σ_m [ w_m × Value_m ]      w_m = (base_weight_m × confidence_m) / Σ (base_weight × confidence)
```

**Recommended base weights (intrinsic-anchored, relative as cross-check):**

| Family | Base weight split |
|---|---|
| `FINANCIAL_EQUITY` | 45% Residual Income · 30% Justified P/B · 15% DDM · 10% peer P/B |
| `SOTP` | 70% SOTP · 20% look-through earnings · 10% historical P/NAV |
| `ASSET_REVALUED` | 55% RNAV · 25% SOTP/DCF · 20% peer P/NAV |
| `INCOME_VEHICLE` | 50% Gordon-on-DPU · 30% P/NAV · 20% peer yield |
| `FINITE_LIFE_DCF` | 60% concession DCF · 40% EV/EBITDA |
| `DEPLETING_ASSET` | 55% reserve NAV · 25% EV/EBITDA · 20% EV/Reserve |
| `CAPITAL_INTENSIVE` | 50% FCFF DCF · 35% EV/EBITDA · 15% P/E |
| `GROWTH_SALES` | 45% EV/Sales · 35% scenario DCF · 20% EV/Gross Profit |
| `FEE_LIGHT` | 50% P/E · 30% DDM · 20% EV/EBITDA |
| `PASSTHROUGH_NAV` | 100% NAV |

**Guardrails:**
- If intrinsic and relative estimates diverge by **>40%**, do **not** silently average — flag for review and widen the reported range.
- Always report a **range (bear/base/bull)** driven by the 2–3 most sensitive inputs (discount rate, terminal growth, commodity price, occupancy, etc.), never a single false-precision number.
- Drop any model whose `confidence < 0.3` from the blend entirely.

### 5.4 Fallback Chains (When Inputs Are Missing)

The engine degrades gracefully. Each family has an ordered fallback; drop to the next when the current model's required inputs are unavailable or unreliable.

| Family | Fallback order (best → last resort) |
|---|---|
| `FINANCIAL_EQUITY` | Residual Income → Justified P/B–ROE → trailing P/B → P/E → book value (NAV floor) |
| `SOTP` | Full SOTP → market value of listed stakes only + book of unlisted → consolidated P/B → NAV |
| `ASSET_REVALUED` | RNAV (appraised) → investment-property fair value (PAS 40) as NAV → P/B → book NAV |
| `INCOME_VEHICLE` | Gordon-on-DPU → dividend yield vs. peers → P/NAV → P/FFO |
| `FINITE_LIFE_DCF` | Concession DCF → EV/EBITDA → EV/value-driver (MW, TEU) → P/E |
| `DEPLETING_ASSET` | Reserve NAV → EV/Reserve → EV/EBITDA (mid-cycle) → EV/Tonne → P/B (asset floor) |
| `CAPITAL_INTENSIVE` | FCFF DCF → EV/EBITDA → EV/EBIT → EV/Sales → P/E → EPV → book NAV |
| `GROWTH_SALES` | EV/Sales → EV/Gross Profit → scenario DCF → peer regional multiple → NAV floor |
| all | **Ultimate floor:** Adjusted NAV (book equity, marked where possible) — never return "no value" for a solvent going concern |

### 5.5 Subsector-Specific Engine Considerations (checklist)

- **Currency:** Mining, Oil, and Electrical Components earn **USD revenue** with partly peso costs — model FX explicitly; discount peso-translated cash flows at the peso Ke/WACC.
- **Finite life:** Concessions (water, power, toll, airport, port) and reserves (mining, upstream oil) must use a **finite terminal**, never a Gordon perpetuity. Hard-code the expiry/exhaustion date.
- **Holdco discount:** Apply an empirical per-name discount (default 20–25%) to SOTP; store as a tunable parameter.
- **REIT payout floor:** PH REIT law mandates ≥90% distribution — the engine should treat DPU as near-fully-distributed FFO.
- **Cyclicality:** Cement, chemicals, mining, EMS, airlines — always feed **mid-cycle** margins/prices into DCF and multiples, never spot peak/trough.
- **PFRS 16 leases:** Retail, transport, and hospitality — capitalized leases distort EBITDA and net debt; prefer **EV/EBITDAR** or lease-adjusted metrics for cross-company comparability.
- **Structural decline:** Traditional media, linear TV/print — cap terminal growth at ≤0% unless a credible digital pivot is quantified.
- **Regulatory scenarios:** Casinos/online gaming (PAGCOR/POGO), utilities (ERC), banks (BSP) — model discrete regulatory outcomes as scenarios, not a single deterministic path.
- **Illiquidity:** SME board and thin-float names — add a size/illiquidity premium to Ke and report wider ranges.
- **Data confidence:** Every proxy-derived input lowers the model's confidence weight; the blend must reflect data quality, not just model theory.

---

## Appendix A — Philippine Data Proxy Cheat-Sheet

When a required input is not directly disclosed in PSE filings, use these consistently reproducible proxies:

| Required input | If not disclosed, proxy with | Source of proxy |
|---|---|---|
| EBITDA | Operating Income + Depreciation & Amortization | IS + CF |
| D&A | From cash-flow statement add-backs; or PP&E note movement | CF / NOTES |
| CapEx | "Purchases of PP&E / investment property" in investing section | CF |
| ΔNWC | Period-over-period change in (receivables + inventory − payables) | SFP (2 periods) |
| Net Debt | Total interest-bearing debt (short + long) − cash & equivalents − current investments | SFP + NOTES |
| Cost of debt (Kd) | Interest expense ÷ average interest-bearing debt (floor at 10Y govvy + spread) | IS + SFP |
| Beta | Damodaran unlevered industry beta, relevered to firm D/E | Damodaran dataset + SFP |
| Risk-free rate | PH 10-year government bond (BVAL/PDST) yield | BSP / PDS |
| Equity risk premium | Damodaran country ERP for the Philippines | Damodaran dataset |
| NIM (banks) | Net interest income ÷ average earning assets | IS + SFP |
| RevPAR (hotels) | Room revenue ÷ available room-nights (or occupancy × ADR) | MDA |
| EBITDA/tonne (cement) | EBITDA ÷ tonnes sold | IS + MDA |
| Reserve life | 2P reserves ÷ annual production | NOTES + MDA |
| Refining margin (oil) | Regional Dubai/Singapore crack-spread benchmark | External deck |
| Commodity price deck (mining/oil) | Forward curve / long-run consensus | External |
| Embedded value (life insurers) | Adjusted book value | SFP + NOTES |
| Landbank / property fair value | PAS 40 investment-property fair-value note; else independent appraisal in AR | NOTES / AR |
| Segment values (SOTP) | PFRS 8 operating-segment note (revenue, EBIT, assets per segment) | NOTES |
| Subscribers / ARPU (telco) | MD&A operating KPIs; ARPU = service revenue ÷ average subscribers | MDA / IS |
| Diluted shares | Latest 17-Q/17-A cover + options/convertibles note | EDGE / NOTES |

---

## Appendix B — Sources & Methodological Basis

This framework synthesizes standard institutional valuation practice, adapted to Philippine data availability:

- **Aswath Damodaran** — *Investment Valuation*; *The Dark Side of Valuation*; *Damodaran on Valuation*; and the public NYU-Stern datasets for country equity-risk premia, unlevered industry betas, and industry multiples. Basis for CAPM calibration, sector-model selection (banks via excess-return/RI, cyclicals via normalized earnings, depleting assets via finite-life NAV), and relative-valuation discipline.
- **McKinsey & Company (Koller, Goedhart, Wessels)** — *Valuation: Measuring and Managing the Value of Companies*. Basis for FCFF/ROIC-driven DCF, EV bridges, and the treatment of financial vs. non-financial firms.
- **CFA Institute Curriculum** — *Equity Asset Valuation* (Pinto, Henry, Robinson, Stowe). Basis for the residual-income model, DDM variants, justified multiples (justified P/B, P/E), and model-selection guidance by industry.
- **Investment-banking methodology** — Rosenbaum & Pearl, *Investment Banking* (comparable companies, precedent transactions, DCF, SOTP), and standard sell-side sector primers (banks → P/B–ROE; telco → EV/EBITDA + EV/sub; power → EV/MW; property/REIT → RNAV + P/FFO; mining/oil → reserve NAV + EV/reserve).
- **Philippine market specifics** — PSE EDGE filings (Form 17-A / 17-Q), SEC financial-reporting standards (PFRS/PAS, incl. PAS 40 investment property, PFRS 8 segments, PFRS 16 leases), BSP prudential disclosures for banks, the Philippine REIT Act (RA 9856) 90% distribution rule, and the CREATE Act 25% corporate tax rate.

> **Disclaimer.** This document specifies valuation *methodology* for an automated engine. It is a research and engineering reference, not investment advice. All outputs are model estimates conditioned on public data and stated assumptions and should be presented as ranges with explicit sensitivities.

---

*End of document — PSE Sector-Aware Valuation Framework v1.0.*
