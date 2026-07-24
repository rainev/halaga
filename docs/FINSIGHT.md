# What is FinSight?

**FinSight** is an investment platform for **Philippine Stock Exchange (PSE)**
investors. It started as a **valuation workbench** — value a PH-listed company
with four classic models — and is evolving into a **portfolio-aware insights
platform** that makes sure an investor is never blindsided by news that touches
what they own.

---

## The two halves of the product

### 1. Valuation workbench (built)

Value any PSE company using four classic models, calibrated for the PH market
(PHP, local risk-free rate, and equity risk premium):

| Model | What it does |
|---|---|
| **DCF** | Projects free cash flow, adds a Gordon-growth terminal value, discounts to an intrinsic price per share. |
| **DDM** | Dividend discount: `P = D₁ / (r − g)`. |
| **Graham** | `V = EPS · (8.5 + 2g) · 4.4 / Y`, with a PHP benchmark yield. |
| **Multiples** | Peer average/median P/E applied to a target EPS. |

Users sign in, run valuations against **manually-entered fundamentals**, and save
runs to their portfolio. Discount rates can be entered directly or derived from a
**beta** via CAPM (`r = risk_free + beta · ERP`).

**PH calibration** lives in a `market_assumptions` table (editable without code
changes): risk-free rate ~6.0%, equity risk premium ~7.5%, Graham yield 6.0,
perpetual growth ~3.0%. All four models were ported from an original
`Valuation-Models-Test.xlsx`, with the spreadsheet's bugs fixed and US
assumptions swapped for PH ones.

### 2. Portfolio-aware insights (spec / in progress)

The next direction: an **investment awareness platform**. The core loop:

```
Your holdings  ─▶  We watch the news  ─▶  We connect it to you  ─▶  "Here's what's happening
(what you own)     (PSE + PH market)      (which holdings it hits)     and how it could affect
                                                                        your positions"
```

- **Portfolio** is the personalization key — everything is scoped to what you own
  (manual holdings for v1: ticker + optional shares/cost).
- **News ingestion** from PSE EDGE disclosures, PH business media, and
  macro/policy sources (BSP, PSA).
- **AI-generated insights** (via Claude) grounded in the actual article, with
  guardrails, connecting direct company news and macro/thematic events to
  holdings.
- The valuation models become **one supporting lens** ("here's what your holding
  is worth in light of this news"), not the whole product.

**The "not advice" contract:** the platform surfaces, connects, and explains
*possible* impact and cites the primary source — it never says "buy" or "sell."
Every insight describes a possible effect, links to the source, carries a
disclaimer, and uses non-imperative language.

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Vite + React + TypeScript, Tailwind, Radix UI |
| Backend | FastAPI (Python), raw SQL via **psycopg** (no ORM) |
| Auth | JWT access token + rotating refresh token (httpOnly cookie), revocable sessions in Redis; Google Sign-In |
| Data | Postgres 16, Redis 7, MinIO (S3-compatible) |
| Orchestration | docker-compose |

## Layout

```
backend/            FastAPI service
  app/
    valuation/      pure valuation engine (dcf, ddm, graham, multiples, assumptions)
    routers/        HTTP boundary → services → db
    services/       business logic + persistence (raw SQL)
    security/       jwt, password hashing, Google auth, rate limiting, headers
    seed/           admin, market assumptions, companies
  tests/            engine, jwt, and API tests (pytest)
frontend/           Vite React app (auth + valuation UI)
infrastructure/     postgres init SQL, redis.conf, minio bucket, dev scripts
docs/               product specs (e.g. portfolio-aware insights)
design/             HTML mockups
docker-compose.yml
```

## Quick start

```sh
cp .env.example .env              # then edit secrets
./infrastructure/scripts/up.sh    # build + start the whole stack
./infrastructure/scripts/seed.sh  # (once up) admin + PH market + companies
```

- Frontend: http://localhost:4000
- API + docs: http://localhost:4001 (OpenAPI UI at `/docs`)

## v1 scope / notes

- **Data entry is manual** for v1 — no PSE scraping (`GOOGLEFINANCE` doesn't cover
  the PSE). Company records are seeded from the `PH-Stocks/` folders.
- Seeded tickers are best-effort — verify against PSE and correct via
  `POST /api/companies` (admin).
- Frontend/backend types are kept in sync by hand across the Python↔TS boundary.
</content>
</invoke>
