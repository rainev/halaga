# FinSight (Halaga) — Worklog

**Project:** PSE (Philippine Stock Exchange) valuation workbench
**Stack:** Vite + React + TypeScript · **FastAPI** (Python, raw SQL via psycopg, no ORM) · Postgres 16 + MinIO · docker-compose
**Auth:** JWT access token (in-memory) + rotating refresh token (httpOnly cookie), revocable sessions in Postgres (staging consolidated off Redis)
**Version control:** git · branch `main`

---

## What this is

Value PSE-listed companies with four classic models — **DCF, Dividend Discount, Graham,
and Multiples** — calibrated for the PH market (PHP, local risk-free rate & equity risk
premium). Users sign in, run valuations against manually-entered fundamentals, and save
runs to a portfolio.

Architecturally ported from **`talentNet`**, with the backend rewritten Node/Express →
Python/FastAPI. Models ported from `Valuation-Models-Test.xlsx` with the spreadsheet's
bugs fixed and US assumptions swapped for PH ones (e.g. DCF CAGR off-by-one corrected;
Graham `g` treated as whole-number percent).

## Timeline (git history)

| Date | Milestone |
|---|---|
| **Jul 13** | Initial commit — "Halaga, PSE valuation workbench" |
| ongoing | Substantial **uncommitted** work on the auth stack (see below) |

## Current state — uncommitted work in progress

Working tree has a broad set of modifications concentrated on **auth**:
- Backend: `db.py`, `env.py`, `main.py`, `models/auth.py`, `routers/{auth,admin,__init__}.py`, `services/{auth_service,user_service}.py`, `requirements.txt`, `tests/conftest.py`
- Frontend: `App.tsx`, `AuthShell.tsx`, `Layout.tsx`, `AuthContext.tsx`
- Infra/config: `docker-compose.yml`, `frontend/Dockerfile`, `.env.example`, `README.md`

## Layout
```
backend/app/
  valuation/   pure engine (dcf, ddm, graham, multiples, assumptions)
  routers/     HTTP boundary → services → db
  services/    business logic + persistence (raw SQL)
  security/    jwt + password hashing
  seed/        admin, market assumptions, companies
  tests/       engine, jwt, API tests (pytest)
frontend/      Vite React app (auth + valuation UI)
infrastructure/  postgres init SQL, minio bucket, dev scripts
```
Reference data in repo: `PH-Stocks/`, `JFC FS Reports/`, `Refinitiv Interface/`, valuation/model test spreadsheets.

## How to run
```bash
cp .env.example .env
./infrastructure/scripts/up.sh     # build + start stack
./infrastructure/scripts/seed.sh   # admin + PH market + companies
```
- Frontend http://localhost:4000 · API + docs http://localhost:4001/docs
- Other scripts: `down.sh` (keep data), `reset.sh` (wipe volumes)

## Next steps
- Finish and commit the in-progress auth stack changes
- Run the pytest suite (engine, jwt, API) to confirm nothing regressed
- Verify seed → sign-in → run valuation → save-to-portfolio end to end

---
_Last updated: 2026-07-24_
