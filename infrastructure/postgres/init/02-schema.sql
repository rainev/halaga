-- Initial database schema. Runs once, after 01-extensions.sql, on first DB init.
-- Plain SQL is the source of truth for now; switch to a migration tool once the
-- schema changes regularly and you have data you can't wipe.

-- ---------------------------------------------------------------------------
-- Auth
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user',
  is_verified   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tracks files stored in MinIO / Spaces (e.g. uploaded filings, future use).
CREATE TABLE IF NOT EXISTS files (
  id           SERIAL PRIMARY KEY,
  object_key   TEXT NOT NULL,
  filename     TEXT NOT NULL,
  content_type TEXT,
  size_bytes   BIGINT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Valuation domain
-- ---------------------------------------------------------------------------

-- PSE-listed companies. Seeded from the PH-Stocks/ sector folders.
CREATE TABLE IF NOT EXISTS companies (
  id         SERIAL PRIMARY KEY,
  ticker     TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  sector     TEXT,
  currency   TEXT NOT NULL DEFAULT 'PHP',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies (sector);

-- Market-wide valuation assumptions (PH defaults). Keyed so multiple regimes can
-- coexist; the app reads the 'PH' row. Editable by an admin later.
CREATE TABLE IF NOT EXISTS market_assumptions (
  id                       SERIAL PRIMARY KEY,
  key                      TEXT NOT NULL UNIQUE,
  risk_free_rate           NUMERIC NOT NULL,          -- decimal, e.g. 0.06 (PHP 10Y govt / BVAL)
  equity_risk_premium      NUMERIC NOT NULL,          -- decimal, e.g. 0.075
  graham_current_yield     NUMERIC NOT NULL,          -- PERCENT, e.g. 6.0 (Graham's "Y")
  graham_normalizing_yield NUMERIC NOT NULL DEFAULT 4.4, -- Graham's original AAA yield constant
  graham_base_pe           NUMERIC NOT NULL DEFAULT 8.5, -- P/E for a no-growth company
  default_perpetual_growth NUMERIC NOT NULL DEFAULT 0.03, -- PH long-run nominal growth
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Saved valuation runs. inputs/assumptions/result are stored verbatim as JSON so
-- a run is fully reproducible even if the engine's defaults change later.
CREATE TABLE IF NOT EXISTS valuations (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  company_id  INTEGER REFERENCES companies (id) ON DELETE SET NULL,
  model       TEXT NOT NULL,          -- 'dcf' | 'ddm' | 'graham' | 'multiples'
  inputs      JSONB NOT NULL,
  assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
  result      JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_valuations_user ON valuations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_valuations_company ON valuations (company_id);
