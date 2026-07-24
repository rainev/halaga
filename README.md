# FinSight — PSE Valuation App

Value Philippine Stock Exchange (PSE) companies with four classic models — **DCF,
Dividend Discount, Graham, and Multiples** — calibrated for the PH market (PHP,
local risk-free rate & equity risk premium). Users sign in, run valuations
against manually-entered fundamentals, and save runs to their portfolio.

Built on the [`talentNet`](../talentNet) architecture, with the backend ported
from Node/Express to **Python/FastAPI**.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Vite + React + TypeScript |
| Backend | FastAPI (Python), raw SQL via **psycopg** (no ORM) |
| Auth | JWT access token (in-memory) + rotating refresh token (httpOnly cookie), revocable sessions in Postgres |
| Data | Postgres 16 (app data + sessions + rate limits), MinIO (S3-compatible) |
| Orchestration | docker-compose |

## Quick start

```sh
cp .env.example .env            # then edit secrets
./infrastructure/scripts/up.sh  # build + start the whole stack
./infrastructure/scripts/seed.sh  # (in another shell, once up) admin + PH market + companies
```

- Frontend: http://localhost:4000
- API + docs: http://localhost:4001 (OpenAPI UI at `/docs`)
- Sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`, or register a new user.

Other scripts: `down.sh` (stop, keep data), `reset.sh` (wipe volumes and re-init).

## Layout

```
backend/            FastAPI service
  app/
    valuation/      pure valuation engine (dcf, ddm, graham, multiples, assumptions)
    routers/        HTTP boundary  → services → db
    services/       business logic + persistence (raw SQL)
    security/       jwt + password hashing
    seed/           admin, market assumptions, companies
  tests/            engine, jwt, and API tests  (pytest)
frontend/           Vite React app (auth + valuation UI)
infrastructure/     postgres init SQL, minio bucket, dev scripts
docker-compose.yml
```

## The valuation models

All four are ported from the original `Valuation-Models-Test.xlsx`, with the
spreadsheet's bugs fixed and US assumptions swapped for PH ones:

- **DCF** — projects FCF, adds a Gordon-growth terminal value, discounts to an
  intrinsic price per share. CAGR uses the correct interval count (the sheet's
  `^(1/5)` over 5 points was an off-by-one).
- **DDM** — `P = D₁ / (r − g)`.
- **Graham** — `V = EPS · (8.5 + 2g) · 4.4 / Y`. **`g` is whole-number percent**
  (e.g. `9.63`, not `0.0963` — the sheet's bug, which understated value ~3×). `Y`
  is a PHP benchmark yield, not a US AAA yield.
- **Multiples** — peer average/median P/E applied to a target EPS.

### PH calibration

Market-wide inputs live in the `market_assumptions` table (the `PH` row, seeded
from `app/valuation/assumptions.py`) and can be edited without code changes:

| Input | Default | Notes |
|---|---|---|
| Risk-free rate | 6.0% | PHP 10Y govt / BVAL |
| Equity risk premium | 7.5% | for CAPM cost of equity |
| Graham current yield (Y) | 6.0 | PHP benchmark, replaces US AAA |
| Perpetual growth | 3.0% | PH long-run nominal |

Discount rates can be entered directly or derived from a **beta** via CAPM
(`r = risk_free + beta · ERP`).

## Tests

```sh
cd backend && python -m pytest        # engine correctness, jwt, API routes
```

The engine tests verify the models against the original spreadsheet's numbers
(where it was correct) and against hand-computed values (where bugs were fixed).

## Notes / v1 scope

- **Data entry is manual** for v1 (no PSE scraping; `GOOGLEFINANCE` doesn't cover
  the PSE anyway). Company records are seeded from the `PH-Stocks/` folders.
- Seeded **tickers are best-effort** — verify against PSE and correct via
  `POST /api/companies` (admin), which upserts by ticker.
- Frontend/backend types are kept in sync by hand across the Python↔TS boundary
  (`frontend/src/lib/types.ts` ↔ `backend/app/models/*.py`).
