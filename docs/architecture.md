# FinSight — News → Insights Architecture

How a news article becomes a personalized, holdings-scoped insight in a user's
dashboard. This is the technical companion to [`insights.md`](./insights.md).

## The core principle: analyze once, personalize by query

The expensive work (reading, analyzing, and writing an insight about an article)
is **global** — it depends only on the article and the companies it touches, not
on any individual user. The **per-user** part is just *filtering*: showing a user
the articles that touch stocks they own.

```
GLOBAL (compute once per article)                 PER-USER (cheap, at read time)
─────────────────────────────────                ──────────────────────────────
News API ─▶ Analyze ─▶ affected_sectors[]         Your holdings ┐
                       affected_stocks[]                         ├─▶ feed = articles
                            │                                    │   whose affected
                            ▼                                    │   stocks/sectors ∩
                    Insight per (article, company) ──────────────┘   your holdings
                    (shared by everyone who owns it)
```

Consequences:

- **No fan-out storage explosion.** An article that affects 5 stocks produces 5
  insights total — not 5 × (number of users who own them).
- **No duplicated LLM cost.** The insight "rate hike pressures property developers
  like MEG" is identical for every MEG holder, so we generate it once and reuse.
- **Isolation is a `WHERE` clause.** A user's query only ever returns rows for
  tickers/sectors they own. One user can never see another user's holdings; the
  feed is scoped by join, not by any per-user copy of the data.

## The pipeline

### 1. Ingest
A worker polls the **news API** (plus PSE EDGE disclosures) on a schedule, stores
each raw article in `news_items`, and dedupes by URL/hash. New rows are marked
`status = 'pending'`.

### 2. Analyze (the tagging step)
For each pending article, an analyzer determines **what it affects**:

- **Affected stocks** — direct entity matching (ticker + company-name lookup
  against `companies`), plus LLM extraction for names/aliases the matcher misses.
- **Affected sectors** — from the matched companies' `sector`, plus macro/thematic
  mapping (rates → banks & property; oil → utilities & mining) via a `themes`
  taxonomy and semantic matching (**pgvector**, already enabled).

The result is written as the article's properties: rows in `article_stocks` and
`article_sectors`, each with a `relevance`/`confidence` score and whether the link
is `direct` or `thematic`. After this step the article's `status = 'analyzed'`.

> These are properties **of the article**, shared by all users — exactly as you
> described. Nothing here is user-specific yet.

### 3. Generate insight (per affected company)
For each `(article, company)` link above a confidence threshold, the **OpenAI API**
reads the **actual article text + that company's context** and writes the grounded
"how this could affect the position" note, under the non-advice guardrails from
`insights.md`. Use **structured outputs** (`response_format` with a JSON schema, or
the SDK's `parse()` helper) so each insight comes back as validated fields —
`summary`, `possible_impact`, `direction`, `confidence`, `sources` — never
free-form prose to parse. Stored once in `insights`, keyed by
`(news_item_id, company_id)` — **not** by user.

### 4. Personalize (fan-in at read time)
When a user opens their dashboard, the feed is a query:

> give me the insights whose `company_id` is in *my* holdings — or whose
> `sector`/theme matches a sector I hold — newest first.

No per-user precomputation required. (If we later want push notifications or a
daily digest, a lightweight fan-out job writes `user_id → insight_id` rows to a
`user_feed` table so we can deliver without scanning; the analysis/insight above
is still shared.)

## Data model (additions to the current schema)

Builds on the existing `users`, `companies` (has `sector`), and `valuations`.

```sql
-- What a user owns — the personalization key.
CREATE TABLE holdings (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  company_id INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
  shares     NUMERIC,            -- optional
  avg_cost   NUMERIC,            -- optional
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, company_id)
);
CREATE INDEX idx_holdings_user ON holdings (user_id);

-- Raw articles from the news API / PSE EDGE. Global.
CREATE TABLE news_items (
  id           SERIAL PRIMARY KEY,
  source       TEXT NOT NULL,
  url          TEXT NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  body         TEXT,
  published_at TIMESTAMPTZ,
  status       TEXT NOT NULL DEFAULT 'pending',  -- pending|analyzed|failed
  embedding    vector(1024),                     -- pgvector, for thematic matching
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Article → affected stocks. A property of the article, shared by all users.
CREATE TABLE article_stocks (
  news_item_id INTEGER NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
  company_id   INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
  link_type    TEXT NOT NULL DEFAULT 'direct',   -- direct|thematic
  relevance    NUMERIC,                           -- 0..1 confidence
  PRIMARY KEY (news_item_id, company_id)
);
CREATE INDEX idx_article_stocks_company ON article_stocks (company_id);

-- Article → affected sectors/themes. Also a property of the article.
CREATE TABLE article_sectors (
  news_item_id INTEGER NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
  sector       TEXT NOT NULL,
  relevance    NUMERIC,
  PRIMARY KEY (news_item_id, sector)
);
CREATE INDEX idx_article_sectors_sector ON article_sectors (sector);

-- The generated insight, one per (article, company). Shared, auditable.
CREATE TABLE insights (
  id               SERIAL PRIMARY KEY,
  news_item_id     INTEGER NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
  company_id       INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
  summary          TEXT NOT NULL,
  possible_impact  TEXT NOT NULL,
  direction        TEXT,          -- informational only (e.g. headwind/tailwind/mixed) — NOT advice
  confidence       NUMERIC,
  sources          JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (news_item_id, company_id)
);
CREATE INDEX idx_insights_company ON insights (company_id, created_at DESC);
```

## The isolation query (the personalized feed)

A user's dashboard is exactly this — they can only ever see insights for tickers
(or sectors) they hold:

```sql
-- Direct: insights for companies the user owns.
SELECT i.*, n.title, n.url, n.published_at, c.ticker
FROM insights i
JOIN news_items n ON n.id = i.news_item_id
JOIN companies  c ON c.id = i.company_id
JOIN holdings   h ON h.company_id = i.company_id AND h.user_id = :user_id
ORDER BY n.published_at DESC
LIMIT 50;
```

Sector/thematic exposure is the same shape, joining `article_sectors` to the
distinct sectors the user holds. Because every path is gated by
`holdings.user_id = :user_id`, isolation is structural: there is no query surface
that returns another user's data, and the dashboard is automatically organized to
"only news that affects your investments."

## Where each piece runs

| Stage | Component | Trigger |
|---|---|---|
| Ingest | background worker | scheduled poll of news API + PSE EDGE |
| Analyze | analyzer service (entity match + pgvector + OpenAI) | on new `news_items` |
| Insight | OpenAI API, structured outputs | on new `article_stocks` link |
| Personalize | FastAPI route → the isolation query | user opens dashboard |

The valuation engine plugs in as **one lens** on any insight: "here's what your
holding is worth in light of this news," reusing the existing DCF/DDM/Graham/
Multiples models.

## Open questions

- News API choice + polling cadence; real-time-per-disclosure vs daily digest.
- Confidence threshold for generating an insight (avoid low-signal noise).
- OpenAI model tiers: which model for insight generation vs. cheaper bulk
  classification/relevance, and the `text-embedding-3-*` variant + dimension for
  the pgvector column (OpenAI covers both LLM and embeddings — no separate
  provider needed).
- Whether to add the `user_feed` fan-out table now (needed only for push/digest
  delivery) or stay purely read-time until then.
</content>
