# Valuation-Input Coverage Audit

**Framework reviewed:** `../PSE_VALUATION_ENGINE_FRAMEWORK_CONSOLIDATED.md`
**Parser reviewed:** `pdf-parser-script`, parser version 2.3.0
**Audit date:** July 2026

## Status definitions

- **Implemented:** The parser has an explicit canonical field, aliases, normalization, and output exposure in `facts.json` / `facts.csv`, or a deterministic derived rule.
- **Partial:** The parser can capture a reported value or components, but the valuation concept requires period selection, interpretation, external calibration, or a disclosure that is not consistently present.
- **Missing:** The value is not reliably obtainable from a company financial-statement PDF. It must come from market data, a regulator, an external assumption set, or analyst judgment.

## Common extraction evidence

- Direct statement and note fields: `config/line_item_catalog.json`, applied by `finsight_parser.core.build_fact_index` and `finsight_parser.core._append_prose_window_facts`.
- Numeric and percentage normalization: `finsight_parser.core._parse_number`, `_page_unit_context`, `_inline_unit_context`, and `_normalize_values`.
- Period mapping: `finsight_parser.core._page_period_context` and `_assign_period_hints`.
- Derived fields: `finsight_parser.core._append_derived_facts` and `_derive_total_debt`.
- Output exposure: `build_fact_index` writes every fact to `facts.json`; `_write_facts_csv` writes the same canonical fields to `facts.csv`.
- Requirement exposure: `config/wave1_requirements.json`, `finsight_parser.catalog.load_wave1_requirements`, and `finsight_parser.core.evaluate_requirements`.

## 1. Core accounting and valuation inputs

| Required input or variable | Status | Mapped field(s) | Evidence / implementation note |
|---|---|---|---|
| Revenue / sales | Implemented | `revenue` | Direct catalog aliases; statement-row and note/prose extraction |
| Service revenue | Implemented | `service_revenue` | Direct catalog aliases |
| Property sales | Implemented | `property_sales` | Direct catalog aliases |
| Rental income | Implemented | `rental_income` | Direct catalog aliases |
| EBIT / operating income | Implemented | `ebit` | Direct catalog aliases |
| Normalized or mid-cycle EBIT | Partial | `ebit`, `ebit_margin` | Historical EBIT is extracted; normalization remains a valuation-engine judgment |
| EBITDA | Implemented | `ebitda` | Direct reported EBITDA extraction |
| EBITDA fallback | Partial | `ebit`, `depreciation_amortization` | Components are available; parser does not force EBIT + D&A when definitions may differ |
| Gross profit | Implemented | `gross_profit` | Direct catalog aliases |
| Cost of sales | Implemented | `cost_of_sales` | Direct catalog aliases |
| Operating expenses | Implemented | `operating_expenses` | Direct catalog aliases |
| Gross margin | Implemented | `gross_margin` | `_append_derived_facts`: gross profit / revenue |
| EBIT margin | Implemented | `ebit_margin` | `_append_derived_facts`: EBIT / revenue |
| EBITDA margin | Implemented | `ebitda_margin` | `_append_derived_facts`: EBITDA / revenue |
| Pretax income | Implemented | `pretax_income` | Direct catalog aliases |
| Tax expense | Implemented | `tax_expense` | Direct catalog aliases |
| Effective tax rate | Implemented | `effective_tax_rate` | `_append_derived_facts`: tax expense / pretax income |
| Normalized/statutory tax rate | Partial | `effective_tax_rate`, `tax_expense` | Reported/effective rate is available; sustainable forecast tax rate requires policy |
| Net income | Implemented | `net_income` | Direct catalog aliases |
| Net income attributable to parent/common | Implemented | `parent_net_income` | Direct catalog aliases |
| Depreciation and amortization | Implemented | `depreciation_amortization` | Direct catalog aliases |
| Total capital expenditure | Implemented | `capital_expenditure` | Direct cash-flow aliases |
| Maintenance capital expenditure | Partial | `maintenance_capex` | Direct aliases added; many issuers do not separately disclose maintenance CapEx |
| Sustaining capital expenditure | Partial | `sustaining_capex` | Direct aliases added for mining/oil; disclosure-dependent |
| Development capital expenditure | Partial | `development_capex` | Direct aliases added; disclosure-dependent |
| Operating cash flow | Implemented | `operating_cash_flow` | Direct cash-flow aliases |
| Free cash flow | Implemented | `free_cash_flow` | `_append_derived_facts`: operating cash flow less absolute CapEx |
| Change in net working capital | Partial | `change_in_working_capital` | Direct cash-flow aliases; sign convention requires review |
| Core operating working-capital proxy | Implemented | `core_operating_working_capital` | `_append_derived_facts`: receivables + inventory - accounts payable |
| Full non-cash operating NWC | Partial | `receivables`, `inventory`, `contract_assets`, `prepayments`, `other_operating_current_assets`, `accounts_payable`, `accrued_expenses`, `contract_liabilities`, `other_operating_current_liabilities` | Components are extracted; downstream engine must select operating components and compare periods |
| Current assets / current liabilities | Implemented | `current_assets`, `current_liabilities` | Direct statement aliases |
| Legacy accounting working capital | Implemented | `working_capital` | `_append_derived_facts`: current assets - current liabilities; not the preferred FCFF NWC definition |
| Cash and cash equivalents | Implemented | `cash` | Direct statement aliases |
| Excess cash | Partial | `cash` | Cash is extracted; operating versus excess cash requires analyst/engine policy |
| Gross debt | Implemented | `total_debt` | Direct aliases or `_derive_total_debt` from current + noncurrent debt |
| Current debt | Implemented | `current_debt` | Direct statement aliases |
| Noncurrent debt | Implemented | `noncurrent_debt` | Direct statement aliases |
| Net debt | Implemented | `net_debt` | `_append_derived_facts`: total debt - cash |
| Lease liabilities | Implemented | `lease_liabilities` | Direct statement/note aliases |
| Preferred equity | Implemented | `preferred_equity` | Direct statement aliases |
| Non-controlling interests | Implemented | `nci` | Direct statement aliases |
| Non-operating investments | Implemented | `nonoperating_investments`, `investments_associates_jv` | Direct statement/note aliases |
| Total assets | Implemented | `total_assets` | Direct statement aliases |
| Total liabilities | Implemented | `total_liabilities` | Direct statement aliases |
| Total equity | Implemented | `total_equity` | Direct statement aliases |
| Parent/common equity | Implemented | `parent_equity`, `common_equity` | Direct statement aliases |
| Beginning/ending book equity | Implemented | `parent_equity`, `common_equity` with period hints | Parser retains comparative columns; valuation engine selects beginning and ending periods |
| Retained earnings | Implemented | `retained_earnings` | Direct statement aliases |
| Other comprehensive income / clean-surplus adjustment | Implemented | `other_comprehensive_income` | Direct income/equity aliases |
| Common equity issuance | Implemented | `common_equity_issuance` | Direct cash-flow/equity aliases |
| Share repurchases | Implemented | `share_repurchases`, `treasury_stock` | Direct cash-flow and balance-sheet aliases |
| Intangible assets | Implemented | `intangible_assets` | Direct statement aliases |
| Goodwill | Implemented | `goodwill` | Direct statement aliases |
| Tangible common equity | Implemented | `tangible_book_value`, `tangible_common_equity` | Direct field preferred; derived parent equity - intangibles fallback |
| PPE / operating fixed assets | Implemented | `ppe` | Direct statement aliases |
| Right-of-use assets | Implemented | `right_of_use_assets` | Direct statement aliases |
| Concession assets | Implemented | `concession_assets` | Direct statement aliases |
| Regulatory assets / liabilities | Implemented | `regulatory_assets`, `regulatory_liabilities` | Direct statement aliases |
| Rehabilitation/decommissioning liability | Implemented | `closure_provision` | Direct statement/note aliases |
| Debt proceeds | Implemented | `debt_proceeds` | Direct cash-flow aliases |
| Debt repayments | Implemented | `debt_repayments` | Direct cash-flow aliases |
| Net borrowing | Implemented | `net_borrowing` | `_append_derived_facts`: proceeds less absolute repayments |
| Interest expense | Implemented | `interest_expense` | Direct income-statement aliases |
| Disclosed borrowing rate | Implemented | `weighted_average_borrowing_rate` | Direct note/prose aliases |
| Current marginal cost of debt | Partial | `weighted_average_borrowing_rate`, `interest_expense`, `total_debt` | Filing proxies are available; current market spread/yield is external |

## 2. Per-share, dividend, and equity-model inputs

| Required input or variable | Status | Mapped field(s) | Evidence / implementation note |
|---|---|---|---|
| Current basic shares outstanding | Implemented | `shares_outstanding` | Ambiguous weighted-average alias removed; current/outstanding aliases retained |
| Fully diluted current shares | Partial | `fully_diluted_shares` | Direct aliases added; options/convertibles still require instrument-level dilution if not reported |
| Weighted-average basic shares | Implemented | `weighted_average_basic_shares` | Direct EPS-note aliases |
| Weighted-average diluted shares | Implemented | `weighted_average_diluted_shares` | Direct EPS-note aliases |
| Basic EPS | Implemented | `eps_basic` | Direct per-share aliases |
| Diluted EPS | Implemented | `eps_diluted` | Direct per-share aliases |
| Book value per share | Implemented | `book_value_per_share` | Direct per-share aliases |
| Tangible book value per share | Implemented | `tangible_book_value_per_share` | Direct per-share aliases |
| Cash flow per share | Implemented | `cash_flow_per_share` | Direct per-share aliases |
| Free cash flow per share | Implemented | `free_cash_flow_per_share` | Direct per-share aliases |
| Dividends paid | Implemented | `dividends_paid` | Direct cash-flow aliases |
| Common dividends declared | Implemented | `common_dividends_declared` | Direct equity-statement aliases |
| Dividend per share | Implemented | `dividends_per_share` | Direct per-share aliases |
| REIT distribution per unit | Implemented | `distribution_per_unit` | Direct per-unit aliases |
| Dividend payout ratio | Implemented | `dividend_payout_ratio` | Direct metric aliases |
| Sustainable payout policy | Partial | Dividend fields plus earnings history | Historical facts are extracted; sustainable policy is a forecast judgment |
| ROE | Implemented | `return_on_equity` | Direct reported KPI aliases |
| ROA | Implemented | `return_on_assets` | Direct reported KPI aliases |
| ROIC | Implemented | `return_on_invested_capital` | Direct reported KPI aliases |
| Forecast ROE, payout, book growth | Missing | No PDF parser field | Forward assumptions belong in the valuation engine |
| Graham normalized EPS and BVPS | Partial | `eps_basic` / `eps_diluted`, `book_value_per_share` | Reported values are extracted; normalization is analyst/engine logic |

## 3. Banks and other financial institutions

| Required input or variable | Status | Mapped field(s) | Evidence / implementation note |
|---|---|---|---|
| Interest income | Implemented | `interest_income` | Direct income aliases |
| Net interest income | Implemented | `net_interest_income` | Direct income aliases |
| Non-interest / fee income | Implemented | `non_interest_income` | Direct income aliases |
| Earning assets | Implemented | `earning_assets` | Direct balance-sheet/note aliases |
| Net interest margin | Implemented | `net_interest_margin` | Direct KPI aliases |
| Gross loans | Implemented | `gross_loans` | Direct balance-sheet aliases |
| Allowance for credit losses | Implemented | `allowance_credit_losses` | Direct balance-sheet aliases |
| Provision expense | Implemented | `credit_loss_provision` | Direct income aliases |
| Non-performing loans | Implemented | `nonperforming_loans` | Direct statement/note aliases |
| NPL ratio | Implemented | `npl_ratio` | Direct KPI aliases |
| NPL/provision coverage | Implemented | `npl_coverage` | Direct KPI aliases |
| Customer deposits | Implemented | `customer_deposits` | Direct balance-sheet aliases |
| CET1 ratio | Implemented | `cet1_ratio` | Direct regulatory KPI aliases |
| Capital adequacy ratio | Implemented | `capital_adequacy_ratio` | Direct regulatory KPI aliases |
| CET1 capital | Implemented | `cet1_capital` | Direct regulatory table aliases |
| Total regulatory capital | Implemented | `total_regulatory_capital` | Direct regulatory table aliases |
| Risk-weighted assets | Implemented | `risk_weighted_assets` | Direct regulatory table aliases |
| Required increase in common equity | Partial | `cet1_capital`, `risk_weighted_assets`, `parent_equity` | Actual components extracted; forecast growth and target capital buffer are external assumptions |
| Cost-to-income ratio | Implemented | `cost_to_income_ratio` | Direct KPI aliases |
| Loan growth / deposit growth | Implemented | `loan_growth`, `deposit_growth` | Direct KPI aliases; historical growth can also be computed downstream |
| Insurance combined ratio | Implemented | `combined_ratio` | Direct KPI aliases |
| Solvency/RBC ratio | Implemented | `solvency_ratio` | Direct KPI aliases |
| Assets under management | Implemented | `assets_under_management` | Direct KPI aliases |
| Take/commission rate | Implemented | `take_rate` | Direct KPI aliases |
| Embedded value / value of new business | Missing | No reliable universal PDF field | Insurer-specific actuarial disclosure; must be added per issuer when explicitly reported |

## 4. NAV, SOTP, property, and REIT inputs

| Required input or variable | Status | Mapped field(s) | Evidence / implementation note |
|---|---|---|---|
| Investment property | Implemented | `investment_property` | Direct balance-sheet aliases |
| Land/development inventory | Implemented | `land_inventory` | Direct balance-sheet aliases |
| Appraised/fair property value | Implemented | `appraised_value` | Direct note/prose aliases |
| Landbank area | Implemented | `landbank_area` | Direct operating-metric aliases |
| Gross development value | Implemented | `gross_development_value` | Direct operating-metric aliases |
| Pre-sales/reservation sales | Implemented | `presales` | Direct operating-metric aliases |
| Remaining project cost | Implemented | `project_cost_to_complete` | Direct note/prose aliases |
| Cap rate | Implemented | `cap_rate` | Property-specific aliases; generic financing capitalization-rate alias removed |
| Rental reversion/escalation | Implemented | `rental_reversion` | Direct KPI aliases |
| Gearing | Implemented | `gearing_ratio` | Direct KPI aliases |
| Occupancy | Implemented | `occupancy_rate` | Direct KPI aliases |
| WALE | Implemented | `wale` | Direct KPI aliases |
| NOI | Implemented | `noi` | Direct metric aliases |
| FFO | Implemented | `funds_from_operations` | Direct reported FFO aliases |
| AFFO | Implemented | `affo` | Direct reported AFFO aliases |
| Real-estate D&A | Implemented | `real_estate_depreciation_amortization` | Direct REIT/property aliases |
| Gain on property sales | Implemented | `gain_on_property_sales` | Direct income aliases |
| Straight-line rent adjustment | Implemented | `straight_line_rent_adjustment` | Direct AFFO-reconciliation aliases |
| Other AFFO adjustments | Partial | `other_affo_adjustments` | Generic explicit reconciliation row only; adjustment appropriateness requires review |
| Distributable income | Implemented | `distributable_income` | Direct REIT reconciliation aliases |
| Official NAV per unit | Implemented | `nav_per_unit` | Direct per-unit aliases |
| Segment revenue / EBIT / EBITDA / assets / CapEx | Implemented | `segment_revenue`, `segment_ebit`, `segment_ebitda`, `segment_assets`, `segment_capex` | Direct segment-note aliases |
| Ownership percentage | Implemented | `ownership_percentage` | Direct ownership-note aliases |
| Parent cash / parent debt | Implemented | `parent_cash`, `parent_gross_debt` | Parent-level aliases; requires a parent-only statement or note |
| Dividends from subsidiaries | Implemented | `dividends_from_subsidiaries` | Direct holdco aliases |
| Corporate overhead | Implemented | `corporate_overhead` | Direct holdco aliases |
| Unfunded parent costs / capitalized overhead | Partial | `corporate_overhead` | Current expense is extracted; capitalization period is an analyst assumption |
| Asset/project probability | Missing | No parser rule | Scenario probability is a valuation assumption, not an accounting fact |
| After-tax project fair value | Partial | Asset values, costs, tax and debt fields | Components may be reported; DCF/fair-value calculation belongs downstream |
| Tax leakage on asset realization | Missing | No reliable universal PDF field | Requires transaction structure and tax judgment |

## 5. Sector operating metrics

| Sector / required input | Status | Mapped field(s) | Evidence / implementation note |
|---|---|---|---|
| Power - installed/attributable MW | Implemented | `capacity_mw` | Direct KPI aliases |
| Power - generation and energy sold | Implemented | `energy_generated`, `energy_sold` | Direct KPI aliases |
| Power - capacity factor | Implemented | `capacity_factor` | Direct KPI aliases |
| Power - PPA tenor | Implemented | `power_purchase_agreement_term`, `concession_life` | Direct contract aliases |
| Power - tariff and allowed return | Implemented | `tariff_rate`, `allowed_return`, `regulated_asset_base` | Direct regulatory aliases |
| Power - fuel and purchased-power cost | Implemented | `fuel_cost`, `purchased_power_cost` | Direct income/note aliases |
| Power - renewal probability / future tariff decision | Missing | No parser rule | Regulatory/scenario assumption |
| Consumer - volume and realized/average price | Implemented | `sales_volume`, `realized_price` | Direct KPI aliases |
| Consumer - market share | Implemented | `market_share` | Direct KPI aliases |
| Consumer - price/mix decomposition | Partial | `sales_volume`, `realized_price`, `segment_revenue` | Explicit reported metrics are captured; decomposition may require analyst calculation |
| Brand strength | Missing | No numeric parser rule | Qualitative analyst assessment |
| Construction - backlog/order book | Implemented | `order_backlog` | Direct KPI aliases |
| Construction - contract assets/liabilities | Implemented | `contract_assets`, `contract_liabilities` | Direct statement aliases |
| Construction/retail - cash conversion cycle | Implemented | `cash_conversion_cycle` | Direct KPI aliases |
| Industrial - utilization | Implemented | `capacity_utilization` | Direct KPI aliases |
| Industrial/electrical - customer concentration | Implemented | `customer_concentration` | Direct KPI aliases |
| Foreign currency revenue and historical FX | Implemented | `foreign_currency_revenue`, `foreign_exchange_rate` | Direct disclosure aliases |
| Forecast FX | Missing | No parser rule | External macro assumption |
| Media - advertising/digital revenue | Implemented | `advertising_revenue`, `digital_revenue` | Direct income/segment aliases |
| Media - audience share | Implemented | `audience_share` | Direct KPI aliases |
| Media - content cost | Implemented | `content_cost` | Direct income/note aliases |
| Telecom - subscribers and ARPU | Implemented | `subscriber_count`, `arpu` | Direct KPI aliases |
| Telecom - churn | Implemented | `churn_rate` | Direct KPI aliases |
| Telecom - spectrum and cell sites | Implemented | `spectrum_assets`, `cell_site_count` | Direct note/KPI aliases |
| Technology - recurring revenue | Implemented | `annual_recurring_revenue` | Direct KPI aliases; ambiguous ARR acronym removed |
| Technology - retention | Implemented | `customer_retention_rate`, `churn_rate` | Direct KPI aliases |
| Technology/SME - cash burn and runway | Implemented | `cash_burn`, `cash_runway_months` | Direct KPI aliases |
| Technology - GMV and active users | Implemented | `gross_merchandise_value`, `active_users` | Direct KPI aliases |
| Transport - TEU throughput | Implemented | `throughput_teu` | Direct KPI aliases |
| Airline - passengers, ASK, RPK, load factor | Implemented | `passengers`, `ask`, `rpk`, `load_factor` | Direct KPI aliases |
| Airline - fleet and passenger yield | Implemented | `fleet_size`, `passenger_yield` | Direct KPI aliases |
| Hotel - occupancy, ADR, RevPAR | Implemented | `occupancy_rate`, `average_daily_rate`, `revpar` | Hotel-specific aliases; ambiguous ADR acronym removed |
| Hotel - GOP margin and room count | Implemented | `gross_operating_profit_margin`, `room_count` | Direct KPI aliases |
| Education - tuition revenue | Implemented | `tuition_revenue` | Direct income aliases |
| Education - enrollment and tuition/student | Implemented | `student_enrollment`, `tuition_per_student` | Direct KPI aliases |
| Education - retention and capacity | Implemented | `customer_retention_rate`, `campus_capacity` | Direct KPI aliases |
| Mining - reserves/resources | Implemented | `ore_reserves`, `coal_reserves`, `mineral_resources` | Direct reserve-report aliases |
| Mining - mine life, grade and recovery | Implemented | `mine_life`, `ore_grade`, `recovery_rate` | Direct technical-report aliases |
| Mining - production/sales volume | Implemented | `production_volume`, `sales_volume` | Direct KPI aliases |
| Mining - realized price, cash cost, AISC | Implemented | `realized_price`, `cash_cost`, `aisc` | Direct KPI aliases |
| Mining - royalties and rehabilitation | Implemented | `royalties`, `closure_provision`, `rehabilitation_cost` | Direct statement/note aliases |
| Mining/oil - permit status | Missing | No reliable numeric field | Permit conditions require text interpretation and legal/regulatory review |
| Oil - reserves/resources and production | Implemented | `oil_gas_reserves`, `oil_gas_resources`, `production_boe` | Direct technical-report aliases |
| Oil - lifting cost | Implemented | `lifting_cost` | Direct KPI aliases |
| Refining - margin, throughput, inventory gain/loss | Implemented | `refining_margin`, `refinery_throughput`, `inventory_gain_loss` | Direct KPI aliases |
| SME - free float and controlling ownership | Implemented | `free_float_percentage`, `promoter_ownership` | Direct ownership/KPI aliases |
| SME - governance quality / disclosure quality | Missing | No numeric parser rule | Requires qualitative governance assessment |
| Gaming - gaming revenue and GGR | Implemented | `gaming_revenue`, `gross_gaming_revenue` | Direct aliases; ambiguous GGR acronym removed |
| Gaming - mass/VIP mix and hold rate | Implemented | `mass_market_mix`, `vip_mix`, `gaming_hold_rate` | Direct KPI aliases |
| Gaming - license tenor and property EBITDA | Implemented | `gaming_license_term`, `property_ebitda` | Direct contract/segment aliases |
| Retail - same-store growth and store count | Implemented | `same_store_sales_growth`, `store_count` | Direct KPI aliases |
| Retail - sales/sqm and inventory turns | Implemented | `sales_per_sqm`, `inventory_turnover` | Direct KPI aliases |

## 6. Market, peer, discount-rate, and forecast variables

These variables are required by the valuation framework but should not be manufactured from company financial-statement PDFs.

| Required input or variable | Status | Mapped field(s) | Reason / required source |
|---|---|---|---|
| Closing stock price and price date | Missing | None | Authorized market-data source |
| Peer stock prices and market capitalizations | Missing | None | Authorized market-data source |
| Selected peer set | Missing | None | Valuation-engine classification and analyst governance |
| Peer P/E, P/B, P/TBV, EV/EBITDA, EV/Sales and other market multiples | Missing | None | Computed from market data plus parser facts |
| Peer median / trimmed mean | Missing | None | Valuation-engine calculation |
| Enterprise value | Missing | None | Valuation-engine calculation from market data and parser bridge fields |
| Philippine risk-free rate | Missing | None | BTr/BSP/authorized yield source |
| Philippine ERP | Missing | None | External methodology dataset |
| Bottom-up beta | Missing | None | External peer beta dataset |
| Company regression beta | Missing | None | Historical market-return dataset |
| Country-risk component | Missing | None | External sovereign/ERP methodology |
| Size/liquidity/governance overlay | Missing | None | Valuation policy and analyst judgment |
| Cost of equity | Missing | None | Valuation-engine calculation |
| Current marginal cost of debt | Partial | `weighted_average_borrowing_rate` | Filing proxy captured; current yield/spread requires external data |
| Cost of preferred equity | Missing | None | Security terms and market assumption |
| Market-value capital weights | Missing | None | Market price plus debt/preferred values |
| WACC | Missing | None | Valuation-engine calculation |
| Terminal growth rate | Missing | None | Forecast/policy assumption |
| Forecast years and forecast financials | Missing | None | Valuation-engine forecast module |
| Exit multiple | Missing | None | Peer/transaction evidence and policy |
| Scenario probabilities | Missing | None | Analyst/engine assumption |
| Long-run commodity-price deck | Missing | None | External forward curve or policy dataset |
| Long-run inflation/GDP growth | Missing | None | BSP/PSA/other macro source |
| Future tariffs, regulation, permits and license outcomes | Missing | None | Regulator disclosures and scenario judgment |
| Holding-company discount | Missing | None | Empirical market analysis; not a financial-statement fact |
| NAV discount/premium | Missing | None | Market price divided by computed NAV |
| ETF daily market price, spread and official current NAV | Partial | `nav_per_unit`, `bid_ask_spread` | Reported figures can be extracted; daily values require authorized market/fund data |
| ETF tracking error and expense ratio | Implemented | `tracking_error`, `expense_ratio` | Direct fund-report aliases |
| Terminal value concentration | Missing | None | Valuation-engine output calculation |
| Low/base/high sensitivity results | Missing | None | Valuation-engine calculation |

## 7. Inputs that remain intentionally outside the PDF parser

The parser should not infer the following:

1. Market prices, peer multiples, beta, ERP, government yields, WACC, cost of equity, terminal growth, and exit multiples.
2. Forecast revenue, margins, reinvestment, regulatory capital, or cash flow.
3. Commodity-price, foreign-exchange, tariff, regulatory, permit, or license scenarios.
4. Qualitative brand strength, governance quality, disclosure quality, or management credibility.
5. Project probabilities, holding-company discounts, NAV discounts, or other valuation haircuts.
6. Whether extracted maintenance CapEx, normalized earnings, excess cash, or non-operating assets are economically appropriate without review.

These are missing by design because treating them as PDF-extracted facts would create false precision.

## 8. Implementation summary

- Catalog expanded from 112 pre-existing canonical entries to **237 total entries**.
- **125 canonical inputs and metrics were added** for the consolidated valuation framework.
- New deterministic derived outputs:
  - `net_borrowing`
  - `effective_tax_rate`
  - `gross_margin`
  - `ebit_margin`
  - `ebitda_margin`
  - `core_operating_working_capital`
  - `tangible_common_equity`
- Current shares, weighted-average shares, and fully diluted shares are now distinct.
- Prose extraction recognizes additional operating units such as boe, barrels, subscribers, students, rooms, stores, sites, hectares, and square meters.
- Catalog matching now uses a token index and precompiled prose patterns.
- Ambiguous short aliases such as ADR, ARR, and GGR were removed after real-filing tests.
- Wave 1 templates now expose the new fields as recommended inputs without weakening existing required-input gates.

## 9. Validation

- `python -m unittest discover -s tests -v`
- Result: **19 tests passed**.
- Added test: `ParserTests.test_consolidated_framework_fields_and_derived_metrics`.
- Real-filing spot checks were performed on BDO, AREIT, Ayala Land, Puregold, OceanaGold Philippines, and PLDT extracted filing text.

## 10. Remaining limitations

- A catalog rule means the parser can recognize a field when it is disclosed; it does not guarantee every issuer reports that field.
- Note tables with multiple assets, segments, units, or commodity types may require row-level structuring beyond a single canonical scalar.
- Text-heavy reserve reports, legal permit conditions, and valuation appraisals can require manual interpretation.
- Fully diluted current shares may require instrument-level option/convertible calculations when the issuer does not report a fully diluted count.
- The parser deliberately retains candidates and provenance instead of silently approving them as model-ready facts.
