# FinSight — Portfolio-Aware Insights

> Status: spec / not yet built. This documents the direction agreed on 2026-07-15.

## What we're building

FinSight is an **investment awareness platform** for Philippine (PSE) investors. Its
job is to make sure a user is **never blindsided by news that touches what they
own** — surfacing developments connected to their holdings and explaining how
those developments *could* affect their positions.

**This is not investment advice.** We never say "buy" or "sell." We surface
connected information, explain the possible impact, cite the source, and leave
the decision to the user. The user stays on top of their own portfolio; the user
stays in control of their decisions.

The valuation models (DCF / DDM / Graham / Multiples) become **one supporting
lens** — "here's what your holding is worth in light of this news" — not the whole
product.

## The core loop

```
Your holdings  ─▶  We watch the news  ─▶  We connect it to you  ─▶  "Here's what's happening
(what you own)     (PSE + PH market)      (which holdings it hits)     and how it could affect
                                                                        your positions"
```

## v1 scope (decided)

| Decision | Choice |
|---|---|
| Audience | Real product — accounts, saved portfolios, multi-user |
| Portfolio input | **Manual holdings** (ticker + optional shares/cost). No broker import yet. |
| Connection types | **Direct company news** + **macro/thematic** (rates, inflation, oil, FX, policy). *Sector/peer news is later.* |
| Insight generation | **AI-generated with Claude**, grounded in the actual article, with guardrails |
| Data entry (fundamentals) | Still manual for the valuation lens |

## The "not advice" contract

Both a legal stance and a UX/design principle. Enforced in copy, prompts, and disclaimers.

| ✅ Awareness (what we do) | ❌ Advice (never) |
|---|---|
| "BSP raised rates 25bp — this typically pressures property developers like your **MEG**." | "Sell MEG." |
| "SCC reported a coal-price drop; here's the disclosure." | "SCC is a buy." |
| Surface · connect · explain *potential* impact · cite the source | Recommend · predict a price · tell them to act |

Every insight: describes a **possible** effect, links to the **primary source**,
carries a **disclaimer**, and uses non-imperative language (no "should / buy / sell").

## Building blocks

1. **Portfolio / holdings** — the personalization key. Everything is scoped to
   "what you own." Manual entry for v1: ticker, optional shares, optional cost basis.

2. **News ingestion** — pull and store articles from:
   - **PSE EDGE disclosures** — official, structured, highest signal (start here).
   - PH business media (BusinessWorld, Inquirer, Philstar) and company IR.
   - Macro/policy sources (BSP, PSA) for rates/inflation/FX.

3. **The connection engine** (the hard, valuable part) — link each news item to
   the holdings it affects:
   - **Direct:** ticker / company-name matching.
   - **Macro/thematic:** theme → holdings mapping (rates → banks & property; oil →
     utilities & mining), assisted by **semantic matching**.
   - **pgvector is already enabled** in the DB for the semantic side.

4. **Insight generation** — Claude reads the article + the holding's context and
   writes the grounded "how this could affect your position" note, under guardrails.

5. **Guardrails & compliance** — non-advice framing enforced in prompts, output
   validation, and UI disclaimers. Human stays in the driver's seat.

## Data model (additions to the current schema)

- `holdings` — `user_id`, `company_id`, optional `shares`, optional `avg_cost`, timestamps.
- `news_items` — `source`, `url`, `title`, `body`, `published_at`, `entities` (tickers), optional `embedding vector(...)` for semantic search.
- `themes` — macro/thematic tags (e.g. `interest_rates`, `oil`, `fx`) and the sectors/tickers each typically moves.
- `insights` — `user_id`, `news_item_id`, `company_id`, generated `body`, `impact_direction` (informational, not advice), `sources`, `created_at`. Stored so an insight is reproducible and auditable.

## The AI approach (high level — no code yet)

- **Provider:** the **OpenAI API** does the analysis and insight generation. A
  capable model handles insight writing; a cheaper tier can handle bulk
  classification/relevance if needed.
- **Grounded generation (RAG):** the prompt carries the *actual article text* +
  the company's context; the model explains the connection from that, and
  **cites the source**. It does not free-associate.
- **Structured output:** use OpenAI **structured outputs** (`response_format` with
  a JSON schema, or the SDK's `parse()` helper) so each insight comes back as
  validated fields — `summary`, `possible_impact`, `direction`, `confidence`,
  `sources` — never free-form prose we have to parse.
- **Guardrail prompting:** system prompt forbids imperatives (buy/sell/should),
  requires "*may / could / historically*" hedging, and requires a cited source;
  we also validate the output and reject/rewrite anything that reads as advice.
- **Cost control:** the stable system prompt + guardrails are reused across calls;
  only the per-article + per-company content varies. Insights are generated once
  per `(article, company)` and shared across users (see `architecture.md`).
- **Embeddings:** OpenAI's `text-embedding-3-*` populates `news_items.embedding`
  for pgvector semantic matching — same provider, no separate embeddings vendor.

## Open questions / next up

- Which PSE-EDGE ingestion method (scrape vs feed) and cadence.
- Theme taxonomy: the starting set of macro themes and their sector/ticker maps.
- Insight cadence: real-time on new disclosure vs a daily digest.
- OpenAI model tiers (insight vs. bulk classification) and `text-embedding-3-*`
  variant + vector dimension.

---

**Next:** design the Portfolio + Insights (feed) screens before writing any of the
above. The valuation UI already exists; these are the new surfaces.
