# Microsoft U.S. Valuation Design

## Goal

Add Microsoft Corporation (MSFT, CIK `0000789019`) as the second supported U.S. issuer in FinSight. Classify it as an enterprise software and cloud company, calculate a filing-only intrinsic-value range, apply existing publication gates, and expose only a public-safe result in the Valuation experience.

## Scope and constraints

- Use only public SEC submissions, Companyfacts, and filing-specific inline XBRL or filing tables.
- Do not use price, market capitalization, analyst estimates, proprietary data, price-derived beta, or any price-tuned assumption.
- Preserve source URLs, accession numbers, dates, units, tags, period coverage, and extraction status in the private audit output.
- Preserve Apple behavior and artifacts unless a shared fix is required and tested.
- Publish a value only through the existing `pass`, `review_required`, and `withheld` policy.
- A `review_required` result is permitted only in the controlled app with a prominent provisional label. A `withheld` result must not display an intrinsic value.

## Classification design

Microsoft has SEC SIC `7372` (Services-Prepackaged Software) and fiscal year-end June 30.

`backend/app/us_valuation/config/archetypes.json` will add:

- A SIC `7372` mapping to `enterprise_software_cloud` in Technology.
- A valuation policy for `enterprise_software_cloud`.
- A Microsoft CIK override only for issuer-specific multi-segment requirements and verified bridge facts, not for the fundamental SIC mapping.

The policy will use FCFF DCF as the primary model and EPV as an unblended support model. It will use bounded archetype assumptions only when Microsoft-specific historical evidence is unavailable.

## Forecast design

Apple continues to use `segment_gross_profit`. Microsoft will introduce a reusable `segment_operating_income` forecast mode.

Microsoft segments are:

1. Productivity and Business Processes.
2. Intelligent Cloud.
3. More Personal Computing.

Each segment record contains annual revenue, operating income, latest YTD and comparable prior-year YTD revenue, a bounded archetype growth anchor, and exact private field provenance. Microsoft uses the direct `segment_operating_income` design intentionally: reported segment operating income is the margin driver, so separately forecasting cost of revenue and operating expenses would double-count segment economics without a governed allocation policy. The engine forecasts segment revenue and segment operating income, then reconciles their totals with the consolidated filing facts before it produces FCFF.

The route uses a 7-to-10-year fade because Microsoft is a durable, multi-business issuer. Company evidence must account for at least 75% of growth weighting when sufficient history exists; the archetype anchor may never exceed 25%.

## Shared engine changes

The shared forecast layer will accept two explicit modes:

- `segment_gross_profit`: existing Apple route.
- `segment_operating_income`: Microsoft and future mature software/cloud issuers.

Classification will expose an explicit `requires_segment_forecast` field. The quality gate must use that field rather than infer segment materiality from `secondary_archetypes` alone.

The core FCFF DCF, EPV, scenario, sensitivity, source-manifest, and public-artifact equations remain shared. No special Microsoft-only DCF equation will be introduced.

## Data and evidence handling

The pipeline will retrieve the latest available Microsoft 10-K and 10-Q through the existing SEC client. Standardized Companyfacts will provide consolidated facts. Filing-specific inline XBRL or governed source-table extraction will provide segment facts where Companyfacts does not retain issuer dimensions.

Required private evidence includes revenue, operating income, tax rate, depreciation and amortization, capital expenditures, operating working capital, cash, short-term investments, debt, lease liabilities where material, diluted shares, and the enterprise-to-equity bridge. Every governed Microsoft segment input is retained in the private audit result with one exact field path, source accession(s), period/context, duration, unit, table line, status, and derivation; that map is never copied to public artifacts. Segment revenue and operating income must reconcile to consolidated facts.

If issuer-specific segment data are governed transcriptions rather than automated extraction, the forecast-quality result must be `review_required`.

## Public output and UI

The pipeline will create a private audit result under the U.S. valuation output area and a public-safe artifact mirrored in the frontend and backend public-data locations. The public artifact may contain only the valuation range, model labels, assumptions expressed at a high level, filing period and source links, drivers, warnings, review status, and methodology references.

The Valuation view must render Apple and Microsoft through company-specific public assumptions rather than hard-coded Apple segment labels. Microsoft must show its archetype, FCFF DCF and EPV results, bear/base/bull range, confidence, financial period, source links, and a provisional label when required.

## Validation and testing

Tests will cover SIC/CIK routing, policy loading, issuer evidence loading, period handling, segment reconciliation, FCFF DCF and EPV execution, scenarios, sensitivities, enterprise-to-equity bridge, diluted shares, source provenance, deterministic output, prohibited price-input flags, and publication-state behavior.

The release process will run Microsoft tests, existing Apple and BDO tests, the backend suite, frontend tests, production build, Python compilation, public-artifact safety scan, and `git diff --check`.

## Publication rule

Only `pass` is eligible for normal automatic publication. `review_required` must be visibly labelled “Preliminary valuation - requires data review.” `withheld` displays the reason without a valuation.

## Out of scope

- A universal arbitrary-segment engine.
- Current-price comparisons, upside/downside calculations, or buy/sell signals.
- New specialist models beyond FCFF DCF, EPV, scenarios, and sensitivity analysis.
- Full-market automated U.S. coverage.
