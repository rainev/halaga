# FinSight

FinSight is a beginner-focused Philippine company research app built on [rainev/halaga](https://github.com/rainev/halaga). It retains the React/TypeScript + FastAPI architecture and Philippine-adjusted valuation foundation.

The default experience is a no-cost, browser-local mockup for four Industrial-sector companies. It requires no account, API key, database, live quote feed, or generative-AI call.

## Included in this branch

- Risk-appetite onboarding from 1 to 5
- Filing-based Industrial rankings plus a 282-company PSE directory
- DCF, DDM, Graham, and multiples valuation views
- Bear, base, and bull assumption cases
- Risk-adjusted P&L and balance-sheet screens
- Filing-derived company and sector briefings
- Browser-local portfolio cost organizer
- Transparent rules-based Smart Brief
- Responsive desktop and mobile navigation

Current and historical market prices are intentionally excluded. Portfolio current value and P/L are therefore not calculated.

## Run the no-cost frontend

```sh
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

To verify the build and calculation engine:

```sh
cd frontend
npm test
npm run build
```

## Optional full stack

The original FastAPI, Postgres, Redis, MinIO, authentication, and manual valuation services remain under `backend/`, `infrastructure/`, and `docker-compose.yml`. They are not required for the local research app.

```sh
cp .env.example .env
./infrastructure/scripts/up.sh
./infrastructure/scripts/seed.sh
```

## Data and methodology

The derived demo dataset in `frontend/src/research/` was transcribed from the supplied FY2025 Industrial-company filings. User-supplied PDFs and workbooks remain local and are intentionally excluded from Git.

The Graham-style model replaces the original U.S. AAA-yield term with a Philippine long-government-bond proxy. It uses the 7.052% accepted average yield from the Bureau of the Treasury's 23 June 2026 auction and an explicit 6.0% through-cycle normalizer.

Health thresholds start from the supplied `Financial Health Metrics.pdf` and become stricter or more permissive according to the user's risk profile. They are investor screens, not universal accounting rules.

## Repository notes

- Active feature branch: `feature/gabay-industrial-investor-app`
- The earlier dependency-free mockup is preserved in `prototype-static/` for reference.
- This is an educational prototype, not investment advice.
- Production use requires validated ingestion, licensed news/data feeds where applicable, security review, privacy controls, and legal/compliance review.
