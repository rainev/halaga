-- Initial database schema. Runs once, after 01-extensions.sql, on first DB init.
-- Plain SQL is the source of truth for now; switch to a migration tool once the
-- schema changes regularly and you have data you can't wipe.

-- ---------------------------------------------------------------------------
-- Auth
-- ---------------------------------------------------------------------------
-- password_hash is nullable: Google-only accounts sign in with Google and never
-- set a password. google_sub is the stable Google user id, set when an account
-- links / is created via "Sign in with Google".
CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT,
  role          TEXT NOT NULL DEFAULT 'user',
  is_verified   BOOLEAN NOT NULL DEFAULT FALSE,
  google_sub    TEXT UNIQUE,
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

-- ---------------------------------------------------------------------------
-- Portfolio-aware insights (see docs/architecture.md)
-- ---------------------------------------------------------------------------

-- What a user owns — the personalization key. The insights feed is scoped to
-- these rows (holdings.user_id), so a user only ever sees news touching what
-- they hold.
CREATE TABLE IF NOT EXISTS holdings (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  company_id INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, company_id)
);
CREATE INDEX IF NOT EXISTS idx_holdings_user ON holdings (user_id);

-- Raw articles from the news source(s). Global. embedding is for future
-- pgvector thematic matching (dim matches OPENAI_EMBED_MODEL: 1536).
CREATE TABLE IF NOT EXISTS news_items (
  id           SERIAL PRIMARY KEY,
  source       TEXT NOT NULL,
  url          TEXT NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  body         TEXT,
  published_at TIMESTAMPTZ,
  status       TEXT NOT NULL DEFAULT 'pending',  -- pending|analyzed|failed
  embedding    vector(1536),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_news_items_status ON news_items (status);

-- Article -> affected stocks. A property of the article, shared by all users.
CREATE TABLE IF NOT EXISTS article_stocks (
  news_item_id INTEGER NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
  company_id   INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
  link_type    TEXT NOT NULL DEFAULT 'direct',   -- direct|thematic
  relevance    NUMERIC,                           -- 0..1 confidence
  PRIMARY KEY (news_item_id, company_id)
);
CREATE INDEX IF NOT EXISTS idx_article_stocks_company ON article_stocks (company_id);

-- Article -> affected sectors/themes. Also a property of the article.
CREATE TABLE IF NOT EXISTS article_sectors (
  news_item_id INTEGER NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
  sector       TEXT NOT NULL,
  link_type    TEXT NOT NULL DEFAULT 'direct',   -- direct|thematic
  relevance    NUMERIC,
  PRIMARY KEY (news_item_id, sector)
);
CREATE INDEX IF NOT EXISTS idx_article_sectors_sector ON article_sectors (sector);

-- The generated insight, one per (article, company). Shared, auditable.
-- direction is informational (headwind|tailwind|mixed) — NOT advice.
CREATE TABLE IF NOT EXISTS insights (
  id              SERIAL PRIMARY KEY,
  news_item_id    INTEGER NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
  company_id      INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
  summary         TEXT NOT NULL,
  possible_impact TEXT NOT NULL,
  direction       TEXT,
  confidence      NUMERIC,
  sources         JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (news_item_id, company_id)
);
CREATE INDEX IF NOT EXISTS idx_insights_company ON insights (company_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Research workbench: per-company filing financials
-- ---------------------------------------------------------------------------
-- One row per scored company; `data` holds the full filing snapshot + the
-- valuation inputs the engine reads (seeded by app/seed/financials.py).
CREATE TABLE IF NOT EXISTS company_financials (
  company_id INTEGER PRIMARY KEY REFERENCES companies (id) ON DELETE CASCADE,
  period     TEXT,
  data       JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
