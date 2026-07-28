# FinSight System Architecture

This document is the working reference for the repository. It summarizes the end-to-end system as it exists in the current workspace so future prompts can reuse the same map without re-deriving it.

## 1. What This System Is

FinSight is a Philippine equity research and valuation application. The repo contains two related runtimes:

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

4. Ingestion and tooling layer
   - PDF statement parser
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

- company identity: id, ticker, name, sector, currency
- valuation input payloads: model-specific schemas
- valuation result payloads: intrinsic value, upside, verdict, validation, detail
- saved valuations: persisted input, assumption snapshot, and result snapshot

These contracts are defined in:

- `backend/app/models/*`
- `frontend/src/lib/types.ts`

## 14. Practical Working Rules

The current repo follows these rules:

- Annual and quarterly histories are not mixed together as raw values.
- DCF must keep terminal growth below the discount rate.
- DDM is mainly for stable dividend payers.
- P/B is the natural financial-sector multiple.
- EV/EBITDA is used when leverage should be normalized.
- Mining and other finite-life businesses need special treatment rather than a generic perpetual-growth assumption.
- Saved runs should always carry the assumptions used at the time of valuation.

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

That document is the source of truth for PSE subsector model selection, equations, public-data fallbacks, Philippine discount-rate policy, blending rules, model-validity gates, update frequencies, and the valuation output contract. This architecture document describes where the code runs; the valuation framework describes what the valuation engine should calculate.

## 16. Current Scope Notes

- The browser-local research experience is the default user-facing path.
- The FastAPI/Postgres/Redis stack is present and functional, but optional for the local demo.
- The parser and ingest pipeline are local tooling, not a hosted service.
- The repo contains generated artifacts under `output/`; these are outputs, not source of truth.
- Source PDFs are not required by the browser-local UI after the generated BDO
  snapshot has been built, but they remain necessary to reproduce the parser
  and transformation run.
