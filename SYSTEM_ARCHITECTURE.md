# FinSight System Architecture

This document is the working reference for the repository. It summarizes the end-to-end system as it exists in the current workspace so future prompts can reuse the same map without re-deriving it.

## 1. What This System Is

FinSight is an equity research and valuation application with an implemented
Philippine-market path and controlled Apple/Microsoft U.S. filing pilots. The
broader multi-archetype U.S. expansion remains a target architecture; these two
issuer routes do not represent production-scale U.S. coverage. The repo contains
two related runtimes:

- A browser-local research app in `frontend/src/research/` that runs entirely on embedded data and local UI logic.
- An optional full-stack app built around FastAPI, Postgres, Redis, and object storage under `backend/`, `infrastructure/`, and `docker-compose.yml`.

The repository also includes a local PDF parser / ingest pipeline that extracts financial statement data from filings and feeds reviewable outputs into the research layer.

## 2. High-Level Architecture

The system is organized into four layers:

1. Presentation layer
   - React / TypeScript UI
   - Local research views
   - Optional authenticated valuation views

2. Application layer
   - Frontend valuation engine for browser-local demo flows
   - FastAPI service for authenticated company, valuation, and session operations

3. Data layer
   - Embedded research datasets in the frontend
   - Parsed filing outputs in `output/`
   - Optional Postgres persistence for users, companies, valuations, and market assumptions
   - Jurisdiction-specific source facts and assumptions, normalized into shared canonical financial fields

4. Ingestion and tooling layer
   - PDF statement parser
   - SEC submissions/Companyfacts ingestion and generic artifact builder for
     the controlled Apple/Microsoft filing pilots
   - Planned filing-specific inline-XBRL support for issuer extensions and segments
   - Batch ingest scripts
   - Validation and report generation scripts
   - Docker-based infrastructure for local backend services

## 3. Main Runtime Paths

### 3.1 Browser-Local Research App

This is the default no-cost experience described in `README.md`.

Entry point:

- `frontend/src/main.tsx`

App shell:

- `frontend/src/App.tsx`

Primary local research modules:

- `frontend/src/research/pages/ResearchDesk.tsx`
- `frontend/src/research/pages/Rankings.tsx`
- `frontend/src/research/pages/ValuationLab.tsx`
- `frontend/src/research/pages/FinancialHealth.tsx`
- `frontend/src/research/pages/Briefings.tsx`
- `frontend/src/research/pages/Portfolio.tsx`
- `frontend/src/research/pages/SmartBrief.tsx`
- `frontend/src/research/pages/FilingData.tsx`

This path uses:

- `frontend/src/research/data.js`
- `frontend/src/research/history.js`
- `frontend/src/research/engine.js`
- `frontend/src/research/format.tsx`
- `frontend/src/research/generated/bdo-valuation.js` for the generated BDO bank valuation snapshot
- `frontend/src/research/generated/apple-valuation.js` for the public-safe Apple valuation snapshot
- `frontend/src/research/generated/microsoft-valuation.js` for the public-safe,
  currently withheld Microsoft valuation snapshot

It is designed to run without:

- login
- API calls
- live quote feeds
- external AI calls

### 3.2 Optional Full Stack

The full stack is available when the backend and infrastructure are started.

Backend entry point:

- `backend/app/main.py`

Supporting services:

- `backend/app/routers/*`
- `backend/app/services/*`
- `backend/app/models/*`
- `backend/app/valuation/*`

Infrastructure:

- `docker-compose.yml`
- `infrastructure/scripts/*`
- `infrastructure/postgres/init/*`
- `infrastructure/redis/redis.conf`
- `infrastructure/minio/create-buckets.sh`

### 3.3 Apple/Microsoft U.S. filing path

The controlled U.S. runtime supports Apple and Microsoft from SEC filing data
rather than the Philippine PDF-first pipeline. Apple uses a
`segment_gross_profit` forecast; Microsoft requires
`segment_operating_income` evidence and is withheld when the normalized period
has no governed segment evidence:

```text
SEC submissions + Companyfacts
        |
        v
Fair-access client, frozen cache and SHA-256 source manifest
        |
        v
CIK identity gate + SIC/issuer override classification
        |
        v
US-GAAP alias mapping + annual/quarter/TTM normalization
        |
        v
Issuer-specific archetype and segment forecast mode
        |
        v
Governed forecast and U.S. discount-rate policy
        |
        v
FCFF DCF primary + EPV support + scenarios/sensitivities
        |
        v
Validation and publication review
        |
        +--> Private audit result with normalized facts and provenance
        |
        +--> Public DTO with derived values, assumptions and filing attribution
                    |
                    +--> GET /api/us-valuations/{ticker}
                    +--> browser-local Valuation tab
```

Implemented modules:

- `backend/app/us_valuation/sec_client.py`
- `backend/app/us_valuation/classification.py`
- `backend/app/us_valuation/xbrl.py`
- `backend/app/us_valuation/assumptions.py`
- `backend/app/us_valuation/models.py`
- `backend/app/us_valuation/pipeline.py`
- `backend/app/us_valuation/artifacts.py`
- `scripts/build_us_valuation_pipeline.py`
- `scripts/build_apple_us_valuation_pipeline.py`
- `backend/app/routers/us_valuations.py`

The SEC connector is server-side, uses an identifying `User-Agent` for network
fetches, rate limits within a process, caches responses, retries with backoff,
and records source URLs and hashes. Browser and mobile clients do not query
EDGAR directly. Centralized cross-process throttling and SEC bulk archives are
still required before large-universe production refreshes. The generic builder
creates private local audit output plus reduced public artifacts; it is a
controlled two-issuer workflow, not a production refresh service.

## 4. Frontend Architecture

## 4.1 Two Frontend Modes

The frontend contains two distinct experiences:

### A. Local research experience

This is the main app in `frontend/src/research/`.

It provides:

- onboarding and risk profiling
- company coverage and rankings
- valuation lab
- filing-based financial views
- financial health checks
- portfolio organization
- briefing summaries
- smart brief generation

The research engine is data-driven and uses the embedded company snapshots in:

- `frontend/src/research/data.js`
- `frontend/src/research/listed-companies.json`

### B. Authenticated app shell

This is the app shell in `frontend/src/App.tsx` and `frontend/src/pages/*`.

It uses:

- React Router
- theme and auth context providers
- lazily loaded filing data pages
- shared UI components under `frontend/src/components/`

## 4.2 Frontend Data Flow

Typical flow in the browser-local app:

1. User selects a company or valuation view.
2. The research engine reads local financial snapshots and history.
3. The engine computes thresholds, derived ratios, valuation outputs, and confidence flags.
4. UI components render the result cards, charts, and health summaries.

For BDO, the Valuation Lab routes by `subsector: "Banks"`. It displays residual
income as the primary estimate, with clean-surplus DDM and justified P/B as
separate cross-checks. BDO is included in `VALUATION_COMPANIES` and can be
selected without a live quote or API request.

### 4.3 Filing-to-valuation data flow

The BDO reference path is:

```text
FS-Testing/BDO Unibank/*.pdf
        |
        v
pdf-parser-script/ingest_archetype_testing.py
        |
        +--> output/fs-testing/bdo/corpora/BDO/{facts,requirements,validation}.json
        |
        v
scripts/build_bdo_valuation_pipeline.py
        |
        +--> output/fs-testing/bdo/valuation-result.json  (audit output)
        +--> frontend/src/research/generated/bdo-valuation.js
        |
        v
frontend/src/research/pages/ValuationLab.tsx
```

The transformation selects facts by filing period, page, label, alias, and
period hint. It never uses a global latest-fact selection for valuation-period
inputs. Annual and interim YTD values are consolidated into TTM figures only
after overlap is removed.

Typical flow in the authenticated app:

1. UI calls `frontend/src/lib/api.ts`.
2. The client sends requests to the FastAPI backend with `credentials: 'include'`.
3. Access token stays in memory.
4. Refresh token is stored in an `httpOnly` cookie.
5. The UI retries once on `401` by attempting refresh.

### 4.4 User assumption scenarios

The Valuation Lab may provide a controlled **What-if Scenario** mode. This is
separate from the official FinSight valuation:

1. The user opens the official valuation and sees the governed base assumptions.
2. The user selects a plain-language preset such as Conservative, Base case or
   Optimistic, or adjusts a small set of permitted assumptions.
3. The frontend sends the scenario to the valuation service.
4. The service validates the values, reruns the applicable model, and returns a
   separate user-scenario range.
5. The UI compares the scenario with the unchanged FinSight base valuation.

Initial editable assumptions may include revenue or earnings growth, operating
margin, discount rate, terminal growth, payout, and other archetype-specific
drivers. The allowed fields, bounds, dependencies, and defaults must be defined
by model and sector. Users must not be able to bypass terminal-growth,
discount-rate, accounting, or model-validity controls.

The interface should explain each assumption in everyday language—for example,
“How quickly do you think the company can grow?”—while showing the technical
variable and formula behind an optional detail view. A concise warning should
state: “If you are unfamiliar with this model, keep the Base case or use the
presets. Large changes can produce unrealistic results.” Extreme values should
trigger an explanation and may require an explicit confirmation.

The user scenario must never overwrite the base valuation, change the published
official result, or be presented as a recommendation. It should be labeled
`user_scenario`, retain the complete changed-assumption snapshot, and remain
reproducible when saved or shared.

## 5. Frontend Key Modules

### 5.1 Research Engine

Core logic:

- `frontend/src/research/engine.js`

Responsibilities:

- derive risk thresholds from the selected profile
- compute health metrics from financial snapshots
- validate annual and quarterly history
- decide whether a valuation is publishable, reviewable, or blocked
- apply valuation controls such as spread checks and terminal-value warnings

History handling:

- `frontend/src/research/history.js`

Important behavior:

- annual and quarterly records are stored separately
- current snapshot can be merged with filing history
- quarterly values are treated as standalone quarters, not mixed with annual values
- trailing-four-quarter totals are only used when the latest four quarters are complete and consecutive

### 5.2 Research Data

Embedded data:

- `frontend/src/research/data.js`

This file contains:

- Philippine assumptions
- sector/company datasets
- valuation defaults
- source links for supporting documents

### 5.3 Authenticated UI

Shared UI building blocks:

- `frontend/src/components/*`
- `frontend/src/components/ui/*`

Shared context:

- `frontend/src/context/AuthContext.tsx`
- `frontend/src/context/ThemeContext.tsx`

API access:

- `frontend/src/lib/api.ts`

Routes and pages:

- `frontend/src/pages/Companies.tsx`
- `frontend/src/pages/Valuation.tsx`
- `frontend/src/pages/Login.tsx`
- `frontend/src/pages/Register.tsx`
- `frontend/src/pages/Saved.tsx`

## 6. Backend Architecture

## 6.1 FastAPI Application

Backend entry point:

- `backend/app/main.py`

The backend is a FastAPI app with:

- CORS configured for the client origin
- a shared error handler for application errors
- a generic fallback handler for unexpected exceptions
- lifespan hooks that open the DB pool and ensure storage buckets exist

## 6.2 Router Layer

Routers live in:

- `backend/app/routers/auth.py`
- `backend/app/routers/companies.py`
- `backend/app/routers/valuations.py`
- `backend/app/routers/health.py`
- `backend/app/routers/admin.py`

Router responsibilities:

- accept and validate request payloads
- resolve derived inputs when possible
- call service functions
- shape responses for the frontend

Important valuation routes:

- `POST /api/valuations/dcf`
- `POST /api/valuations/ddm`
- `POST /api/valuations/graham`
- `POST /api/valuations/multiples`
- `POST /api/valuations/residual-income` (bank residual-income valuation)
- `GET /api/valuations`
- `DELETE /api/valuations/{id}`

Important auth routes:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/logout-all`
- `GET /api/auth/me`

Important company routes:

- `GET /api/companies`
- `GET /api/companies/{company_id}`
- `POST /api/companies`

## 6.3 Service Layer

Services live in:

- `backend/app/services/auth_service.py`
- `backend/app/services/session_service.py`
- `backend/app/services/company_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/valuation_service.py`
- `backend/app/services/user_service.py`

Responsibilities:

- auth logic and token rotation
- session revocation and reuse detection
- company persistence
- valuation persistence
- market assumption lookup

## 6.4 Persistence Layer

Database access:

- `backend/app/db.py`
- `backend/app/storage.py`
- `backend/app/redis_client.py`

Data models:

- `backend/app/models/auth.py`
- `backend/app/models/company.py`
- `backend/app/models/valuation.py`

Storage responsibilities:

- Postgres stores users, companies, valuations, and market assumptions
- Redis stores refresh-session state
- object storage is used when the backend needs bucket-backed artifacts

The valuation table stores:

- user id
- company id
- model name
- input payload
- assumptions snapshot
- result snapshot
- created timestamp

This makes saved runs reproducible even if future defaults change.

## 7. Valuation Engine

Pure valuation logic lives in:

- `backend/app/valuation/dcf.py`
- `backend/app/valuation/ddm.py`
- `backend/app/valuation/graham.py`
- `backend/app/valuation/multiples.py`
- `backend/app/valuation/bank.py`
- `backend/app/valuation/common.py`
- `backend/app/valuation/assumptions.py`

These files describe the original implemented model set. The separate
`backend/app/us_valuation/` package now implements the first U.S. archetype:
Apple's mature hardware/services lane with FCFF DCF as primary and EPV as an
unblended support model. Other archetypes in
`US_EQUITY_VALUATION_ENGINE_FRAMEWORK.md` remain planned until their code,
mapping and tests exist.

## 7.1 Discounted Cash Flow

File:

- `backend/app/valuation/dcf.py`

Supported variants:

- simple enterprise DCF
- FCFF / enterprise DCF
- FCFE / equity DCF

Key logic:

- project free cash flow
- discount projected cash flow
- calculate terminal value with Gordon growth
- bridge enterprise value to equity value when using FCFF
- avoid debt double counting when using FCFE

Controls:

- terminal growth must stay below the discount rate
- terminal value share warning when terminal value dominates the result

## 7.2 Dividend Discount Model

File:

- `backend/app/valuation/ddm.py`

Supported variants:

- Gordon growth single-stage DDM
- two-stage DDM

Key logic:

- derive next dividend from last dividend and growth
- discount each dividend stream
- add terminal value from the final stage

## 7.3 Graham Model

File:

- `backend/app/valuation/graham.py`

Key logic:

- use EPS, growth, and a yield assumption
- provide a fast rule-of-thumb screen rather than a precise intrinsic-value model

## 7.4 Multiples

File:

- `backend/app/valuation/multiples.py`

Supported variants:

- P/E
- P/B
- EV/EBITDA

Key logic:

- compare the target company to peer multiples
- require positive denominators
- use the peer median as the headline output for robustness

Sector fit:

- P/B is the main financial-sector lens
- EV/EBITDA is used where capital structure should be normalized
- P/E is the general-purpose cross-check

## 7.5 Bank Residual-Income Valuation

File:

- `backend/app/valuation/bank.py`

Banks are valued at the equity level because deposits and other funding
liabilities are operating inputs rather than an ordinary enterprise-value debt
bridge. The bank model forecasts book value, ROE, payout, earnings, dividends,
and residual income. It returns:

- residual-income intrinsic value per share as the primary result
- a linked clean-surplus DDM reconciliation
- a stable justified P/B cross-check

The BDO-specific inputs are normalized by
`scripts/build_bdo_valuation_pipeline.py`. Preferred capital, book value per
share, TTM earnings, TTM ROE, and TTM payout are derived with explicit source
maps and warnings. Peer P/B and regulatory-capital FCFE are withheld when the
required public inputs are unavailable.

## 7.6 Market Assumptions

File:

- `backend/app/valuation/assumptions.py`

These assumptions drive:

- cost of equity
- WACC
- perpetual growth defaults
- Graham benchmark values

The active market assumption row is loaded from Postgres when present. If not, the engine falls back to built-in Philippine defaults.

## 7.7 Forecast Quality and Publication Gates

Forecast quality is a separate control layer between normalized financial facts
and the valuation equation. A calculation completing successfully does not mean
that its economic forecast is reasonable.

Core rule:

> The archetype selects the model, but the company's own economics determine
> the forecast.

### Forecast evidence hierarchy

When available, the engine should consider:

1. latest TTM growth and margins;
2. three-year and five-year company history;
3. material segment growth and margins;
4. company-specific structural changes disclosed in filings;
5. the approved archetype benchmark as a bounded fallback.

When sufficient company history exists, the archetype benchmark should normally
receive no more than 20%–25% of the automated starting-growth estimate. No
single unusual quarter should control the forecast. Every forecast must retain
the evidence values, weights, formula, overrides and policy version used.

### Segment and forecast-horizon gate

The classifier must test whether consolidated forecasting hides businesses with
materially different economics. A segment contributing roughly 20% or more of
revenue, profit, assets or cash flow should trigger a segment review when its
growth, margin, capital intensity or risk differs materially from the rest of
the issuer. The threshold is a review trigger, not an automatic conclusion.

The fade horizon must reflect the business rather than use five years for every
company:

- ordinary mature issuer: normally five years;
- durable competitive advantage or material recurring-revenue mix: normally
  seven to ten years;
- cyclical issuer: mid-cycle normalization and scenarios;
- rapidly changing or weakly forecastable issuer: manual review;
- finite-life asset: no perpetual-growth terminal model.

Longer horizons should be generated mechanically from a small number of
governed assumptions. They must not require analysts to enter a separate growth
rate for every year.

### Automated forecast diagnostics

The engine should flag:

- growth fading unusually quickly without filing evidence;
- margin moving materially outside the normalized historical range;
- ROIC collapsing or expanding unusually quickly;
- revenue growth and cash-flow growth telling inconsistent stories;
- a multi-business issuer being forced through one consolidated forecast;
- DCF remaining close to no-growth EPV despite durable historical growth;
- one period having excessive influence on the forecast;
- terminal value exceeding 75% of enterprise value;
- valid models or scenarios differing by more than a governed dispersion limit;
- missing segment, dilution, reinvestment or capital-structure evidence.

Initial thresholds are review triggers. They must be calibrated through
archetype-level backtesting rather than treated as universal accounting truths.

### Release states

Every automated valuation must end in one of three states:

- `pass`: sources, model routing, forecast story and validation checks pass;
- `review_required`: a result was calculated but one or more material
  assumptions or mappings require human confirmation;
- `withheld`: required evidence is missing, contradictory or unsuitable for the
  selected model.

Only `pass` may be automatically published. `review_required` may be shown only
in an explicitly labeled internal or controlled-review experience. `withheld`
must not expose a headline intrinsic value.

### Backtesting and model governance

Before an archetype receives automatic-publication status:

1. run representative companies from older filing dates using only information
   then available;
2. compare forecast revenue, margins and cash flow with later reported values;
3. measure repeated underestimation, overestimation and failure rates;
4. recalibrate forecast weights and diagnostic limits using out-of-sample
   evidence;
5. require human review for the first companies and material exceptions in each
   archetype.

Independent valuation services or a user-supplied market price may be used as a
reasonableness diagnostic, but the engine must never tune assumptions merely to
match an external valuation or current price.

## 8. Market and Discount-Rate Flow

The backend valuation routes resolve discount rates in a controlled way.

Current logic:

1. If the request provides a discount rate, use it directly.
2. Otherwise, if beta is provided, derive cost of equity from market assumptions.
3. For FCFF, build WACC when the request provides enough inputs.
4. Persist the market-assumption snapshot alongside the saved valuation when requested.

For the Philippine fallback, the cost of equity separates the default-free PHP
rate, mature-market ERP, and country-risk premium. BDO uses beta 1.0 as a
disclosed bank-sector fallback, not as a measured regression beta.

This gives each saved run a reproducible rate build, which matters because assumptions can change over time.

The Apple and Microsoft U.S. pilot routes use a separate, versioned U.S.
assumptions snapshot in `backend/app/us_valuation/assumptions.py`. Their
filing-only cost of equity uses a
dated U.S. Treasury risk-free rate, an approved U.S. equity-risk-premium policy,
an archetype risk coefficient, and a bounded filing-supported company risk
overlay. It does not calculate a company-specific regression beta from stock
prices. The pilot WACC uses a governed archetype target debt weight and is
labeled `policy_calibrated`, not market-observed. Future archetypes may use FCFE
or APV when those weights are unreliable.

Philippine and U.S. assumptions must never share an active default row. Every
valuation result must store `market`, currency, policy version, effective date,
and the complete assumption snapshot used for that run.

## 9. Financial Statement Ingestion

The PDF parser lives in:

- `pdf-parser-script/parse_fs_report.py`
- `pdf-parser-script/ingest_archetype_testing.py`
- `pdf-parser-script/finsight_parser/core.py`
- `pdf-parser-script/finsight_parser/catalog.py`
- `pdf-parser-script/config/line_item_catalog.json`
- `pdf-parser-script/config/wave1_requirements.json`
- `scripts/build_bdo_valuation_pipeline.py`

Purpose:

- extract text from financial statement PDFs
- optionally run OCR for image-only pages
- locate the primary statements
- index line items and numeric facts
- validate accounting and provenance rules
- produce reviewable outputs for downstream use

Important behavior:

- local-first
- no OpenAI API key required
- no automatic publication approval
- page-level evidence is retained
- standalone annual and quarterly values are kept separate
- duplicate PDFs are deduplicated
- parent-only filings can be excluded from consolidated coverage
- issuer identity selects the configured PSE subsector and model-input profile
- review-required facts can still be transformed when an explicit source-specific
  reconciliation or proxy is documented

Key outputs:

- `manifest.json`
- `located.json`
- `facts.json`
- `facts.csv`
- `requirements.json`
- `validation.json`
- `analysis.md`

Batch ingestion:

- ingests the `Archetype-testing` corpus
- refreshes the frontend research dataset

BDO batch validation currently routes to `banks`, finds all 15 required bank
inputs, and produces an auditable valuation result through Q2 2026. The raw
source PDFs and raw parser corpus remain local; the generated UI snapshot and
derived audit result are separate outputs.

## 10. Repository Outputs

Generated artifacts are stored in:

- `output/pdf/`
- `output/validation/`
- `output/archetype-testing/`
- `output/fs-testing/bdo/valuation-result.json`

These artifacts include:

- methodology PDFs
- validation reports
- coverage blueprints
- archetype corpus outputs
- parser manifests

## 11. Infrastructure

The optional stack uses:

- Postgres for relational persistence
- Redis for token-session state
- MinIO for object storage
- Docker Compose for local orchestration

Boot scripts:

- `infrastructure/scripts/up.sh`
- `infrastructure/scripts/down.sh`
- `infrastructure/scripts/reset.sh`
- `infrastructure/scripts/seed.sh`

Database bootstrap:

- `infrastructure/postgres/init/01-extensions.sql`
- `infrastructure/postgres/init/02-schema.sql`

## 12. Security Model

Auth design:

- access token is kept in memory in the browser client
- refresh token is stored in an `httpOnly` cookie
- refresh token rotation is used
- reuse detection revokes all sessions on suspected replay

Backend error handling:

- known application errors return consistent JSON
- unexpected exceptions are logged and returned as a generic 500

## 13. Data Contracts

The backend and frontend share a few core contracts:

- company identity: id, ticker, name, market, sector, currency
- valuation input payloads: model-specific schemas
- valuation result payloads: intrinsic value, upside, verdict, validation, detail
- saved valuations: persisted input, assumption snapshot, and result snapshot

These contracts are defined in:

- `backend/app/models/*`
- `frontend/src/lib/types.ts`

The planned cross-market company contract adds:

- jurisdiction and filing regime;
- CIK for U.S. issuers and the applicable Philippine issuer identifier;
- raw public classification code;
- `finsight_sector` and `valuation_archetype`;
- classification version, effective date, confidence and override rationale;
- source accession or filing identifiers;
- accounting standard and fiscal calendar.

The planned valuation-result contract adds:

- financial period and period basis;
- low, base and high intrinsic-value estimates;
- individual model status, weight, confidence and failure code;
- source accessions, extension tags and proxy fields;
- warnings and `human_review_required`;
- jurisdiction-specific assumption snapshot and methodology version.

The scenario contract adds:

- `scenario_id`, `base_valuation_id`, and `scenario_type`;
- only the permitted user-editable assumptions and their bounds;
- original base values and user-adjusted values;
- scenario result range, warnings, sensitivity indicators and validation status;
- plain-language explanation of each changed assumption;
- `is_official: false` and `human_review_required` when a scenario exceeds
  normal policy bounds.

For the initial U.S. filing-only product, `upside`, `verdict`, current price,
market capitalization, trading multiples and buy/hold/sell labels are not
populated. These fields remain part of existing Philippine or future
licensed-data experiences, not the U.S. filing-only contract.

## 14. Practical Working Rules

The current repo follows these rules:

- Annual and quarterly histories are not mixed together as raw values.
- DCF must keep terminal growth below the discount rate.
- DDM is mainly for stable dividend payers.
- P/B is the natural financial-sector multiple.
- EV/EBITDA is used when leverage should be normalized.
- Mining and other finite-life businesses need special treatment rather than a generic perpetual-growth assumption.
- Saved runs should always carry the assumptions used at the time of valuation.
- User-edited assumptions must create a separate scenario run and must never
  mutate the official valuation or its governed assumption snapshot.
- Beginner-facing controls should use presets and short explanations first;
  technical formulas and unrestricted editing belong behind an advanced view.

## 15. What To Read First When Changing the System

If you need to modify the system, read these first:

1. `README.md`
2. `frontend/src/research/engine.js`
3. `backend/app/routers/valuations.py`
4. `backend/app/valuation/dcf.py`
5. `backend/app/valuation/ddm.py`
6. `backend/app/valuation/bank.py`
7. `backend/app/valuation/multiples.py`
8. `scripts/build_bdo_valuation_pipeline.py`
9. `pdf-parser-script/README.md`
10. `pdf-parser-script/finsight_parser/core.py`

### Valuation methodology reference

The sector-aware valuation policy and implementation contract are documented in:

- `PSE_VALUATION_ENGINE_FRAMEWORK_CONSOLIDATED.md`
- `US_EQUITY_VALUATION_ENGINE_FRAMEWORK.md`

The PSE framework is the source of truth for Philippine subsector model
selection, equations, public-data fallbacks, discount-rate policy, blending
rules, model-validity gates, update frequencies, and output contract. The U.S.
framework is the target standard for the filing-only U.S. product, and the
Apple pilot implements its mature non-financial route. This architecture
document describes where code runs and distinguishes implemented components
from planned ones; the valuation frameworks describe what each jurisdiction's
valuation engine should calculate.

## 16. Current Scope Notes

- The browser-local research experience is the default user-facing path.
- The FastAPI/Postgres/Redis stack is present and functional, but optional for the local demo.
- The parser and ingest pipeline are local tooling, not a hosted service.
- Apple SEC submissions/Companyfacts ingestion, classification, normalization,
  FCFF/EPV valuation, review gates, public DTO and Valuation-tab display are
  implemented.
- Filing-specific inline XBRL, issuer extensions/segments, scheduled refreshes,
  full dilution roll-forwards, centralized cross-process SEC throttling and the
  remaining U.S. archetype model library are not yet implemented.
- The repo contains generated artifacts under `output/`; these are outputs, not source of truth.
- Source PDFs are not required by the browser-local UI after the generated BDO
  snapshot has been built, but they remain necessary to reproduce the parser
  and transformation run.

## 17. U.S. Expansion Architecture

### 17.1 Coverage universe

The planned coverage universe is the `FinSight U.S. 500`: a curated set of
approximately 500 widely followed U.S.-listed operating issuers with sufficient
SEC filing history and a supported valuation archetype.

It must not be represented as the S&P 500, Russell 1000, or another proprietary
index. Without licensed current prices, the universe must not claim to be a live
top-500 market-cap ranking. Filing-reported public float, revenue, assets and
filer status may support universe selection, but public-float XBRL must be
reconciled to the 10-K cover page because structured scaling and date errors can
occur.

Launch order:

1. Domestic operating issuers filing Forms 10-K and 10-Q under U.S. GAAP.
2. Banks, insurers, REITs and BDCs after their specialized routes pass tests.
3. Foreign private issuers after IFRS, 20-F/40-F and annual-only controls exist.
4. ETFs and registered funds only through a separate, staleness-aware fund
   module.

### 17.2 Classification hierarchy

U.S. companies must use layered classification:

```text
CIK and issuer type
        |
        v
SEC SIC
        |
        v
FinSight-owned 11-sector taxonomy
        |
        v
FinSight valuation archetype
        |
        v
Company-specific model and inputs
```

The 11 user-facing sectors are:

1. Energy
2. Basic Materials
3. Industrials
4. Consumer Cyclical
5. Consumer Defensive
6. Health Care
7. Financial Services
8. Technology
9. Communication and Media
10. Utilities
11. Real Estate

The broad sector supports navigation and portfolio views. The valuation
archetype controls model selection. SIC is the public starting code, not a
sufficient final economic classification. Segment disclosures, issuer type,
business mix and regulated status may override the default mapping.

GICS must remain optional and license-dependent. The production system must not
require GICS names, codes, mappings or constituent datasets unless FinSight has
appropriate commercial rights.

Each classification record must retain:

- CIK, ticker and legal name;
- raw SIC and optional reliably mapped NAICS;
- FinSight sector and valuation archetype;
- primary and material secondary business;
- filing regime and accounting standard;
- mapping version, effective date and confidence score;
- override flag, rationale and reviewing owner.

Classification should refresh after each annual filing and immediately after a
major acquisition, disposal, reorganization or business-model change.

### 17.3 U.S. source hierarchy

Preferred source order:

1. Audited Form 10-K or 20-F and its notes.
2. Form 10-Q or qualifying 6-K interim statements.
3. Material Form 8-K filings and filed exhibits.
4. SEC Companyfacts and filing XBRL.
5. Proxy and registration statements for dilution and capital instruments.
6. Mapped public regulator data, such as FDIC/FFIEC, FERC, FDA, CMS or BTS.
7. U.S. Treasury, BEA, BLS and governed public economic assumptions.

Companyfacts is useful for standardized entity-level facts, but filing-specific
inline XBRL remains necessary for issuer extensions, dimensions, segments and
facts not represented by a standard taxonomy concept.

Every stored fact must retain:

- CIK and accession number;
- form and filing date;
- period start, period end and fiscal labels;
- unit, scale, dimensions and taxonomy concept;
- whether the concept is standard or an issuer extension;
- source URL and extraction timestamp;
- reported, normalized, forecast or proxy status;
- normalization rule and reviewer status.

### 17.4 Frequency normalization

The shared canonical schema may be reused across markets, but U.S. period
handling must be independently tested.

Rules:

- Keep annual, year-to-date and stand-alone quarterly facts separate.
- Never add a 10-K annual flow to quarters contained in the same fiscal year.
- Derive a stand-alone quarter from cumulative interim values only when period
  coverage and prior cumulative values reconcile.
- Build TTM only from four consecutive, non-overlapping quarters or through a
  documented `latest FY + current YTD - prior-year comparable YTD` bridge.
- Keep balance-sheet facts as point-in-time values.
- Resolve amendments and restatements before selecting a controlling fact.
- Preserve non-calendar fiscal years and 52/53-week calendars.
- Reconcile diluted shares to cover-page, EPS and equity-compensation evidence.

### 17.5 Archetype model routing

The U.S. router must use the archetype matrix in
`US_EQUITY_VALUATION_ENGINE_FRAMEWORK.md`. Principal routes include:

| Archetype | Primary route | Required support when valid |
|---|---|---|
| Mature non-financial company | FCFF DCF | EPV, FCFE or DDM |
| Bank or specialty lender | Residual income | Regulatory-capital FCFE or DDM |
| Insurance or managed care | Excess return/distributable capital | DDM |
| Equity REIT | AFFO/distribution DCF | Property NAV |
| Property developer/homebuilder | RNAV or SOTP | Project DCF or EPV |
| Holding or diversified company | SOTP | Look-through cash-flow model |
| Mining or upstream energy | Finite-life project NAV | RNAV or corporate support |
| Pre-profit biotechnology | Asset rNPV | Cash-runway and dilution scenarios |
| Pre-profit software/platform | Scenario DCF | Survival and dilution scenarios |
| BDC | Adjusted NAV | Income or DDM |
| ETF/registered fund | Separate filing-NAV pass-through | No corporate valuation |

The router must never force a point estimate. Missing regulatory capital,
unreliable reserve data, insufficient pipeline disclosure, unresolved
restatements, unforecastable cash flows, or weak classification confidence must
produce a documented fallback, manual review, or withheld result.

### 17.6 Shared versus jurisdiction-specific components

Reusable shared components:

- canonical fact and provenance schema;
- annual/quarterly/TTM period logic;
- DCF, DDM, residual-income and SOTP primitives;
- sensitivity engine;
- model confidence and failure-code framework;
- assumptions snapshot and reproducible saved-run design;
- publication review gates and frontend range components.

Jurisdiction-specific components:

- source connector and filing parser;
- issuer identifiers and classification mapping;
- accounting taxonomy and extension handling;
- economic and discount-rate assumptions;
- regulator-data adapters;
- bank, insurance, resource, utility and fund disclosure rules;
- licensing and publication controls.

The normalized financial layer may be shared, but raw PSE and SEC facts must
remain in separate jurisdictional source namespaces.

### 17.7 Publication and product boundary

The initial U.S. configuration publishes filing-derived intrinsic-value ranges
and supporting methodology without requiring exchange prices.

It excludes:

- current or historical stock prices;
- market capitalization and price-based upside/downside;
- price-derived company beta;
- peer trading multiples;
- proprietary consensus forecasts;
- buy, hold or sell labels;
- personalized investment recommendations.

Each published result should show its valuation date, financial period, range,
models used, material assumptions and effective dates, confidence grade,
warnings, proxy-derived inputs and source filing identifiers. Legal and
regulatory review remains a launch gate even though the underlying SEC filings
and APIs are publicly accessible.

User scenarios may be displayed alongside the published result, but must be
visibly labeled as hypothetical. They should show the changed assumptions and
their effect on the range, without implying that FinSight endorses the user's
inputs or that the scenario is an official intrinsic value.

### 17.8 Implementation phases and acceptance gates

Phase 1 - foundation:

- create the SEC issuer and submissions connector;
- add EDGAR fair-access controls and a durable filing manifest;
- create SIC-to-sector and sector-to-archetype versioned mappings;
- extend canonical facts with U.S. GAAP concepts, dimensions and accessions;
- add separate U.S. market-assumption records.

Status: implemented for the Apple pilot using SEC Companyfacts and a versioned
Apple override. Generalized filing-specific inline-XBRL and multi-process
ingestion controls remain open.

Phase 2 - pilot:

- select a small, diverse issuer set across mature non-financials, banks, REITs,
  software, semiconductors, energy and biotechnology;
- extract and reconcile at least three annual periods and eight quarters when
  available;
- run archetype-specific models and compare automated results with human-built
  reference valuations;
- calibrate confidence thresholds, risk overlays and failure gates.

Phase 3 - controlled publication:

- publish ranges only for issuers that pass source, model and confidence gates;
- require review for extension-heavy filings, complex segments, restatements,
  going concerns and special assets;
- monitor filing changes, assumption updates and classification drift.

Phase 4 - scale:

- expand toward the FinSight U.S. 500 after archetype-level back-testing meets
  documented accuracy and review standards;
- keep unsupported issuers in an `insufficient` or `manual_review` state;
- add foreign private issuers and funds only after their separate controls pass.

Minimum acceptance criteria:

- no unresolved issuer or filing identity;
- complete provenance for every material input;
- no overlapping annual and interim flow periods;
- reconciled shares, units and enterprise-to-equity bridges;
- model-appropriate discount rate and terminal treatment;
- passing special-archetype checks;
- reproducible result from a frozen source and assumption snapshot;
- no prohibited price-dependent field in the U.S. filing-only output.

### 17.9 Apple pilot artifacts and replay

The full normalized fact set and source map are private audit material:

- `output/us-testing/aapl/valuation-result.json`
- `output/us-testing/aapl/sec-cache/`

The frontend and public API receive a reduced DTO that excludes raw financial
statement values:

- `frontend/public/data/apple-valuation-pipeline.json`
- `frontend/src/research/generated/apple-valuation.js`
- `backend/app/data/us_valuations/AAPL.json`

Replay the frozen cache without network access:

```bash
python3 scripts/build_apple_us_valuation_pipeline.py
```

Refresh from SEC only from a monitored server-side process:

```bash
SEC_USER_AGENT="FinSight monitored-contact@example.com" \
python3 scripts/build_apple_us_valuation_pipeline.py --refresh
```

The revised Apple result remains in `review` state with `medium` confidence.
The deliberate limits are a narrow operating-working-capital definition, a
filing-based diluted-share proxy rather than a full award roll-forward, and
governed transcription of filing-specific Products and Services tables pending
automated inline-XBRL extraction. Those warnings must remain visible until the
mappings are expanded and independently reconciled.

Apple exposed a forecast-policy limitation in the first pilot: recent growth,
short company history and a generic hardware anchor were blended before growth,
margin and marginal ROIC were forced toward mature values within five years.
That produced an internally consistent but overly conservative result.

The revised `AAPL-HARDWARE-SERVICES-1.0` route now:

- forecasts Products and Services separately;
- derives 80% of initial segment growth from recent and historical Apple
  evidence and limits the archetype anchor to 20%;
- reconciles segment revenue and gross profit to consolidated TTM facts;
- uses a mechanically generated ten-year fade to 2% terminal growth;
- models segment gross margins and consolidated operating expenses separately;
- fades marginal ROIC over ten years with a governed durable-advantage premium;
- runs the forecast-quality gates in Section 7.7.

The 31 July 2026 frozen run produces a base FCFF DCF value of approximately
`$137.88` per share, a bear-to-bull range of approximately `$108.07-$183.15`,
and an EPV support value of approximately `$91.36`. These remain internal
`review_required` outputs and were not calibrated to the current stock price or
any third-party valuation. The Apple postmortem remains a required test case for
every future U.S. archetype.

### 17.10 Microsoft enterprise software/cloud route and release state

Microsoft is the second explicit U.S. issuer route. SEC SIC 7372
(`Services-Prepackaged Software`) maps to FinSight's `Technology` sector and
the `enterprise_software_cloud` archetype. That policy uses FCFF DCF as its
primary model, EPV as a separate support value, and an eight-year forecast. The
Microsoft issuer override requires a segment forecast; it does not replace the
underlying SIC route.

Microsoft's governed forecast mode is `segment_operating_income` under
`MSFT-ENTERPRISE-CLOUD-1.0`. It projects disclosed reportable-segment revenue
and operating income, then reconciles the segment totals to normalized
consolidated TTM Companyfacts. The evidence status is
`governed_filing_table_transcription`: SEC Companyfacts provides standardized
consolidated facts but not the dimensions needed for these segment tables. The
transcription remains review-required until filing-specific inline-XBRL
extraction is automated.

The checked-in public MSFT artifact is truthfully `withheld` as of valuation
date 2026-08-01. Its controlling financial statement is the Form 10-K for the
period ended 2026-06-30, filed 2026-07-29, accession
`0001193125-26-323660`. Governed Microsoft segment evidence currently covers
only the normalized period ending 2025-03-31, so the publication gate does not
reuse it for the 2026-06-30 period. Both FCFF DCF and EPV per-share outputs are
therefore null; no intrinsic value is published pending period-matched segment
evidence.

Private SEC response provenance, normalized facts, source hashes, and any raw
filing-table transcriptions remain in the local untracked audit output under
`output/us-testing/msft/`. The public artifacts are limited to filing
attribution, classification, governed public assumptions, derived outputs,
methodology, and review state. They exclude raw financial-statement values and
source-PDF/table text, and they never use or expose current or historical stock
prices, price-based upside/downside, or buy/hold/sell labels.
