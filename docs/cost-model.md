# FinSight — Production Cloud & AI Cost Model

> Status: estimate. Draft 2026-07-25. Figures tagged ▶ are planning assumptions to
> verify. Grounded in `architecture.md`, `insights.md`, and the current stack
> (FastAPI · Postgres 16 + pgvector · MinIO · docker-compose).
> **AI provider: OpenAI** (per `insights.md`). FX: **₱57 = US$1** ▶ (verify at spend time).

---

## 0. The headline

**AI is *not* the cost driver — cloud infrastructure and news feeds are.**

The insights architecture generates each insight **once per `(article, company)`
pair and shares it across all users** (`insights.md`, `architecture.md`). So AI
spend scales with **PH news volume**, which is roughly fixed (~280 PSE-listed
companies, a finite disclosure cadence), **not with user count** — a small
**~$30–90/month** slice on OpenAI. The **news API** is a fixed monthly subscription
(~$100–450), and **Postgres + compute** is what grows with users. Optimize those
three; the LLM bill is a rounding error.

**Once you hire, the biggest cost isn't infrastructure at all — it's people** (~7×
the tech bill at Tier B+). But **at Tier A solo, your whole cash burn is just the
~₱25k tech bill** below — see **§3B** for the "just me" breakdown and the true
monthly burn as you scale.

| Scale ▶ | Registered / MAU | **Cloud infra** | **News API** | **AI (OpenAI)** | **Total / mo** | **₱ / mo** |
|---|---|---|---|---|---|---|
| **A — Early prod** | 10k / ~2k | ~$310 | ~$100 | ~$30 | **~$440** | **~₱25k** |
| **B — Growth** | 50k / ~10k | ~$880 | ~$200 | ~$45 | **~$1,125** | **~₱64k** |
| **C — Scale** | 200k / ~40k | ~$2,200 | ~$450 | ~$90 | **~$2,740** | **~₱156k** |

(Grounded in the PH market: 2.86M PSE accounts, 86% online — see
`docs/marketing/market-research.md`. 40k MAU ≈ ~1.4% of the online market.)

---

## 1. AI cost — the insights engine (OpenAI)

**OpenAI pricing used** (per 1M tokens, mid-2026): **GPT-5** $1.25 in / $10 out ·
**GPT-5 mini** $0.25 / $2 · **GPT-5 nano** $0.05 / $0.40 · **text-embedding-3-small**
$0.02 · **Batch API −50%** · cached input ~90% off. (Sources in §6.)

Model mapping (from `insights.md`: "a capable model writes insights; a cheaper tier
handles bulk classification; `text-embedding-3-*` for embeddings"):
- **Insight writer → GPT-5 mini** (capable + structured outputs, very cheap);
  escalate the hard/ambiguous ~20% to **GPT-5**.
- **Classification / relevance → GPT-5 nano.**
- **Embeddings → text-embedding-3-small.**

### Workload assumptions ▶ (the biggest lever — verify these first)

| Input | Assumption ▶ | Note |
|---|---|---|
| Articles ingested / day | **~200** | PSE EDGE disclosures (~150) + PH biz media + macro (~50) |
| → relevant / day | ~120 | after classification |
| Insight generations / day | **~300** | direct company news (~100 × 1 co.) + macro/thematic (~20 × ~10 co.) |
| Insight gens / month | **~9,000** | **shared across all users** — independent of user count |
| Classifications / month | ~6,000 | one per ingested article (nano) |
| Embeddings / month | ~6,000 | one per article, for pgvector |

**Per-call token sizes ▶:** insight = ~3.5k input (system prompt + article + company
context) / ~0.4k output · classification = ~1.5k in / ~50 out · embedding = ~1k.

### Monthly AI cost (list price, recommended model mix)

| Task | Model | Volume | Input $ | Output $ | **$/mo** |
|---|---|---|---|---|---|
| Insight writing — bulk 80% | **GPT-5 mini** ($0.25/$2) | 7,200 | 25.2M → $6.30 | 2.88M → $5.76 | **~$12** |
| Insight writing — hard 20% | **GPT-5** ($1.25/$10) | 1,800 | 6.3M → $7.88 | 0.72M → $7.20 | **~$15** |
| Classification / relevance | **GPT-5 nano** ($0.05/$0.40) | 6,000 | 9M → $0.45 | 0.3M → $0.12 | **~$1** |
| Embeddings | text-embedding-3-small ($0.02/1M) | 6,000 | 6M → $0.12 | — | **~$1** |
| | | | | | **≈ $29 / mo** |

**Bounds:** all-GPT-5-mini writer ≈ **$16/mo** · all-GPT-5 writer ≈ **$77/mo**.
Batch API (−50%) and cached-input (the stable guardrail system prompt) push the
recommended mix toward **~$17–20/mo**.

### How AI scales with users → it (mostly) doesn't

Insights are generated **once per `(article, company)` and shared** across all
users → AI spend tracks **PH news volume**, not user count.

| Scale | AI driver | Est. AI $/mo (OpenAI) |
|---|---|---|
| A (10k) | ~9k insights/mo | ~$30 (mix) / ~$17 (batched) |
| B (50k) | same news; slightly wider coverage | ~$45 |
| C (200k) | + sector/peer news added later; more macro mapping | ~$90 |

**The one thing that would blow this up:** a **per-user LLM call** — e.g. an
LLM-written personalized daily digest for every user. At 40k MAU × 30 days that's
1.2M calls/mo (~$1,000s). **Assemble the digest from pre-generated shared insights
with a template — no per-user LLM.** Reserve per-user model calls for opt-in
interactive Q&A, and meter it.

### Optimization levers (OpenAI)
- **Batch API (−50%)** — insights run on a cron, not the request path → batchable.
- **Cached input (~90% off)** — the guardrail system prompt is stable across calls.
- **Structured outputs** (`response_format` JSON schema) — no retry waste on
  malformed insights (already in the `insights.md` plan).
- **Generate-once-share-many** — the design already does this; it's *the* reason AI
  is a rounding error. Never regenerate per user.

### Provider note
Modeled entirely on **OpenAI** per `insights.md`. Note `FINSIGHT.md` still says
"Claude" for insight generation — **reconcile the docs to OpenAI** so the two agree.
Embeddings stay on OpenAI `text-embedding-3-small`; ▶ verify the model + vector
dimension match the pgvector column.

---

## 1B. News ingestion & data feeds (the news API line)

FinSight pulls from three source types (`insights.md`). They cost very differently:

| Source | How | Cost |
|---|---|---|
| **PSE EDGE disclosures** — official, structured, highest signal | **Scrape / ingest directly** — not on any third-party news API | **~$0** (infra only; counted in Compute) |
| **PH business media** (BusinessWorld, Inquirer, Philstar) | **Paid news API** with a PH/country filter, or targeted scraping | **the news-API line below** |
| **Macro / policy** (BSP, PSA) | Scrape official pages / releases | ~$0 (infra only) |

**So the news API mainly buys PH-media coverage** — the constraint is *commercial
license + PH coverage + history*, not volume (~6k articles/mo is trivial for any
tier).

### News-API options (commercial, PH-capable) ▶

| Provider | Entry commercial tier | Notes |
|---|---|---|
| **NewsData.io** | ~$100/mo (Basic: 20k credits, PH country filter, 6-mo history, full content, sentiment) | Best fit for PH-media breadth + country filter |
| **Marketaux** | free 100 req/day → paid tiers | Ticker/entity-tagged financial news; PH/PSE ticker coverage is **partial** — verify |
| **GNews** | cheaper, but per-request article caps inflate effective cost | Thin metadata |
| **NewsAPI.org** | **$449/mo** Business (free tier is **non-commercial only**) | Expensive; patchy PH coverage |
| **Finnhub** | ~$50/mo+ market news | Mostly US; weak PH coverage |

> ⚠️ **Licensing gotcha:** NewsAPI.org's Developer tier and GNews' free tier are
> **non-commercial only** — you cannot run production on them. Budget for a paid tier.

### News-API cost by tier ▶

| | Tier A | Tier B | Tier C |
|---|---|---|---|
| Plan shape | NewsData.io Basic (PH filter, commercial) | higher tier: more history/filters, + ticker-tagged feed (Marketaux) | Professional tier + a financial/sentiment feed, multi-source |
| **News API $/mo** | **~$100** | **~$200** | **~$450** |

**Read:** this is a **fixed subscription**, not usage-scaled — it barely moves with
user count (like AI). It's most painful at **Tier A**, where ~$100/mo is spread over
few users. **Cheapest path early:** lean on **free PSE EDGE scraping** for the core
loop and defer the paid media API until the media angle proves it earns its keep.

---

## 2. Cloud infrastructure cost

Priced on a managed cloud (AWS ap-southeast-1 / equivalent) ▶. A PaaS (Render,
Railway, Fly, DigitalOcean) can be 20–40% cheaper at Tier A but less so at Tier C.

| Component | Tier A (10k) | Tier B (50k) | Tier C (200k) |
|---|---|---|---|
| **Compute** — FastAPI API + background workers (ingestion, insight cron) | 2 app + 1 worker → ~$100 | 3–4 app + workers → ~$300 | autoscaling fleet + dedicated workers → ~$800 |
| **Postgres 16 + pgvector** (managed) — app data, sessions, rate limits, news, embeddings | 2 vCPU/8GB, 100GB → ~$150 | 4 vCPU/16GB + read replica → ~$400 | 8 vCPU/32GB + replica(s) → ~$900 |
| **Object storage** (MinIO/S3) — reports, assets | ~$10 | ~$40 | ~$150 |
| **CDN + egress/bandwidth** — API + static frontend | ~$20 | ~$60 | ~$150 |
| **Monitoring / logs / backups** | ~$30 | ~$80 | ~$200 |
| **Infra subtotal** | **~$310** | **~$880** | **~$2,200** |

**Notes**
- Sessions/rate-limits are in **Postgres** (Redis was consolidated off — `WORKLOG`).
  Postgres is therefore the load-bearing, most-scaled component — **it dominates
  the bill**. Right-size and add read replicas before scaling app compute.
- **pgvector** grows with the news corpus, not users; embeddings storage is modest
  but index memory matters — size Postgres RAM for the vector index at Tier C.
- Frontend is static (Vite) → cheap on any CDN; near-$0 at Tier A.
- Google Sign-In / auth: free; transactional email (verification) is small (~$0–20).

---

## 3. Blended totals & unit economics

| | Tier A | Tier B | Tier C |
|---|---|---|---|
| Cloud | ~$310 | ~$880 | ~$2,200 |
| News API | ~$100 | ~$200 | ~$450 |
| AI (OpenAI) | ~$30 | ~$45 | ~$90 |
| **Total / mo (USD)** | **~$440** | **~$1,125** | **~$2,740** |
| **Total / mo (₱, ×57)** ▶ | **~₱25k** | **~₱64k** | **~₱156k** |
| **Cost / MAU / mo** | ~$0.22 (~₱13) | ~$0.11 (~₱6) | ~$0.07 (~₱4) |
| **AI as % of total** | ~7% | ~4% | ~3% |

**Read:** cost per active user **falls** with scale (fixed AI + news cost amortizes)
— healthy unit economics. Even at Tier A, a paid tier of ~₱150–300/mo covers an
active user many times over; the constraint is conversion, not infra cost.

---

## 3B. People — the real burn

The tech bill (cloud + news + AI) is a rounding error next to **payroll**. Priced at
**PH market salaries**, fully loaded with **+18%** for statutory contributions (SSS,
PhilHealth, Pag-IBIG) and 13th-month pay. ▶ Founders who defer/underpay their own
salaries early can run Tier A for far less cash — these are *market-rate* costs.

**Salary basis ▶** (PH monthly, mid-level; sources in §6):

| Role | ₱ / mo (base) |
|---|---|
| Full-stack / backend engineer | ~₱70k (junior ~₱55k · senior ~₱95k) |
| Data / ML / pipeline engineer | ~₱90–110k |
| DevOps / infra engineer | ~₱80–90k |
| Product manager | ~₱80–90k |
| Ops / data-QA / compliance | ~₱40–60k |
| Customer support | ~₱25–35k |
| Marketing / content | ~₱45–55k |

### Headcount & cost by tier ▶

| Tier | Team | Base ₱/mo | **Loaded ₱/mo (×1.18)** | **≈ $/mo** |
|---|---|---|---|---|
| **A — Early** (10k/2k) | **Just you** — solo founder (eng + ops + support + content) | ₱0 draw ▶ | **~₱0 cash** | **~$0** |
| **B — Growth** (50k/10k) | You + 2 engineers + 1 ops/QA + 1 support | ~₱325k | **~₱384k** | **~$6,730** |
| **C — Scale** (200k/40k) | 5 eng + 1 data/ML + 1 DevOps + 1 PM + 1 ops/compliance + 3 support + 1 marketing | ~₱934k | **~₱1,102k** | **~$19,330** |

### Tier A, solo (the "just me" case) ▶

If Tier A is only you, the person cost splits three ways — be honest about which one
you're looking at:

| View | ₱ / mo | What it means |
|---|---|---|
| **Cash, no salary** | **₱0** | You draw nothing → Tier A burn is **tech only** (~₱25k/mo). Lowest possible. |
| **+ living draw** | ~₱50–80k | A modest amount to live on → burn ~₱75–105k/mo. |
| **Opportunity cost** | ~₱82k | What a senior full-stack role would pay you (loaded) — the salary you're forgoing. Uncosted, but real when comparing to just taking a job. |

**Solo is viable at Tier A** (stable product, low support volume) but it's a ceiling:
you're doing engineering + news/data QA + support + content at once. The first hire
(usually **ops/support** or a **2nd engineer**) lands as you push toward Tier B —
which is why B below starts with **you + hires**, not a fresh team.

**People vs. tech (once you hire):** at Tier B–C, payroll is **~7× the entire
cloud+news+AI bill**. Cost discipline lives in **headcount**, not the LLM or the
server. At Tier A solo, though, your **whole cash burn is the ~₱25k tech bill.**

### Fully-loaded monthly burn (tech + people)

| | Tier A (solo, no draw) | Tier B | Tier C |
|---|---|---|---|
| Tech (cloud + news + AI) | ~$440 | ~$1,125 | ~$2,740 |
| People (loaded) | ~$0 | ~$6,730 | ~$19,330 |
| **Total burn / mo (USD)** | **~$440** | **~$7,855** | **~$22,070** |
| **Total burn / mo (₱)** ▶ | **~₱25k** | **~₱448k** | **~₱1.26M** |
| **All-in cost / MAU / mo** | ~$0.22 (~₱13) | ~$0.79 (~₱45) | ~$0.55 (~₱31) |

**This is the number that matters for pricing.** Solo at Tier A, your true burn is
just the **~₱25k tech bill** — a single paying customer at ~₱199/mo covers a chunk
of it, and a few hundred cover it entirely. Once you hire (Tier B+), people dominate
and the true cost per active user jumps to **~₱30–45/mo**. A paid tier of
~₱150–300/mo still covers it, but the margin only opens up as MAU scales — **the
business case is a race to grow (and convert) MAU faster than you add headcount.**

---

## 4. Cost levers (in priority order)

1. **Keep insights shared, never per-user** — the whole reason AI is cheap. Guard this.
2. **Template the digest** — assemble from pre-generated insights; no per-user LLM.
3. **Scrape PSE EDGE + BSP/PSA (free); defer the paid news API** until the PH-media
   angle proves it earns its keep — this removes the ~$100/mo Tier-A line entirely.
4. **Batch API (−50%)** + **cached input** on the guardrail system prompt.
5. **GPT-5 nano for classification, GPT-5 mini for writing** — reserve GPT-5 for the
   hard ~20%; don't route everything to GPT-5.
6. **Right-size Postgres first** (read replicas, connection pooling) — it's the bill.
7. **Cache news/insight reads** (app-level) to cut Postgres load before scaling it.

---

## 4B. Staying profitable as you scale

> **Note:** FinSight's chosen model is a **3-month free trial, then ₱99/mo where
> every active user pays** (see §4C — that's the real revenue picture). The table
> just below is a *freemium* sensitivity (higher price, low % paying) kept only to
> show the general shape. Your paid model earns far more per user than any row here.

Profit does **not** hold automatically as you grow — it's a **U-shape**. Break-even
paying users = burn ÷ price; required conversion = that ÷ MAU:

| Tier (MAU · burn) | @ ₱199/mo | @ ₱299/mo | @ ₱499/mo |
|---|---|---|---|
| **A** (2k · ₱25k, solo) | 126 — **6.3%** | 84 — **4.2%** | 50 — **2.5%** |
| **B** (10k · ₱448k) | 2,251 — **22.5%** | 1,499 — **15.0%** | 898 — **9.0%** |
| **C** (40k · ₱1.26M) | 6,322 — **15.8%** | 4,209 — **10.5%** | 2,521 — **6.3%** |

**Read this table as a *snapshot of a chosen staffing level*, not a forced path.**
Two costs behave very differently as you scale:

- **Variable cost per user (cloud + AI + news) — falls with volume.** Tech cost /
  MAU drops **$0.22 → $0.11 → $0.07** (A → B → C). More users = *lower* unit cost.
  This is the economies-of-scale you'd expect, and it's real.
- **Fixed/step cost (a team hired as a lump) — only breaks profit if added *ahead*
  of the volume.** The scary 15–22% conversion at Tier B isn't a property of *being*
  at B; it's the artifact of staffing the full team the instant you hit 10k MAU,
  before revenue arrives.

**So the healthy trajectory scales profitably throughout.** Bottom → A is pure
variable cost (no team) → profitable by default. A → B → C stays profitable **as
long as revenue leads and hiring lags** — arrive at each volume level first, then
add the role its revenue already pays for. Do that and you're never in the loss
state the snapshot implies; you're always slightly ahead, and unit economics only
improve. The Tier-B "cliff" is entirely avoidable — it's a *timing* choice, not a
law. **Freemium conversion is typically 2–5%**, which is exactly why you let volume
(and MRR) lead the hire, rather than betting a full payroll on conversion catching up.

### The five rules that keep you in the black at scale

1. **Hire behind revenue, never ahead.** Headcount is the *only* step-cost that
   breaks profitability. Don't staff the "Tier B team" at 10k MAU on faith — add
   each role only when recurring revenue already clears its salary. This is the
   single most important discipline; it turns the Tier-B cliff into a gentle ramp.
2. **Price for value — don't anchor at ₱199.** A serious PSE valuation + portfolio-
   insights tool supports **₱299–599**. At ₱499 every tier breaks even under ~9%
   conversion; at ₱199 it's impossible above Tier A. Add **annual plans** and a
   **premium tier** to lift ARPU.
3. **Add non-subscription revenue.** Broker referral/affiliate, premium data, and
   **B2B licensing** (the valuation engine or the insights feed) carry near-zero
   marginal cost and can fund the team without needing consumer conversion to be high.
4. **Keep the team lean and automate.** Because tech marginal cost is ~zero,
   profitability is *entirely* a headcount-vs-revenue question. The AI already does
   the insight labor — question every hire; a 7-person Tier C beats a 12-person one.
5. **Ride the near-zero marginal cost.** Each *additional* user costs ~₱13–31 (mostly
   cloud); AI and news don't move. So once you clear the team's fixed cost, **every
   new paying user is almost pure margin** — growth compounds profit. The whole game
   is clearing that fixed hump, then scaling paying users on top of it.

**Bottom line:** you stay profitable at scale by (a) gating hiring on cleared MRR,
(b) pricing at ₱299–599 not ₱199, and (c) layering in B2B/referral revenue — not by
hoping consumer conversion hits 20%.

---

## 4C. Headcount by user count (the concrete ladder)

**Model: 3-month free trial, then ₱99/mo — every active user pays** (paid product,
not freemium). Assumptions ▶: revenue = paying users × ₱99 · **you draw ₱0** · **news
scraped (₱0)** · support ≈ ₱30k/mo loaded, engineer ≈ ₱82k/mo loaded · hire behind
revenue. (The table treats "users" as *paying* users past the trial — see the
trial/churn caveat below.)

| Users | People | Who | People ₱/mo | Tech ₱/mo | Burn ₱/mo | Revenue ₱/mo | Profit ₱/mo |
|---:|:--:|---|---:|---:|---:|---:|---:|
| 10 | **1** | you | 0 | 2,000 | 2,000 | 990 | −1,010 |
| 20 | **1** | you | 0 | 2,000 | 2,000 | 1,980 | ~0 |
| 30 | **1** | you | 0 | 2,000 | 2,000 | 2,970 | **+970** |
| 40 | **1** | you | 0 | 2,000 | 2,000 | 3,960 | **+1,960** |
| 50 | **1** | you | 0 | 2,000 | 2,000 | 4,950 | **+2,950** |
| 100 | **1** | you | 0 | 2,500 | 2,500 | 9,900 | **+7,400** |
| 200 | **1** | you | 0 | 3,000 | 3,000 | 19,800 | **+16,800** |
| 300 | **1** | you | 0 | 3,000 | 3,000 | 29,700 | **+26,700** |
| 400 | **1** | you | 0 | 3,500 | 3,500 | 39,600 | **+36,100** |
| 500 | **1** | you | 0 | 4,000 | 4,000 | 49,500 | **+45,500** |
| 1,000 | **1** | you | 0 | 5,000 | 5,000 | 99,000 | **+94,000** |
| 2,000 | **1** | you | 0 | 7,000 | 7,000 | 198,000 | **+191,000** |
| 3,000 | **2** | you + support | 30,000 | 9,000 | 39,000 | 297,000 | **+258,000** |
| 4,000 | **2** | you + support | 30,000 | 11,000 | 41,000 | 396,000 | **+355,000** |
| 5,000 | **2** | you + support | 30,000 | 13,000 | 43,000 | 495,000 | **+452,000** |
| 10,000 | **3** | you + support + engineer | 112,000 | 22,000 | 134,000 | 990,000 | **+856,000** |

### How to read this
- **Because everyone pays ₱99, revenue is ~6.6× the freemium case** — ₱99/user vs
  the ~₱15/user a 5%-conversion freemium would give. Lower price, but *everyone* pays.
- **You break even at ~20 paying users** and it's pure profit after that. By 1,000
  users (still solo) you bank **~₱94k/mo**; by 2,000, **~₱191k/mo**.
- **Headcount still grows in steps, far slower than users** (1 → 3 while users go
  500×). With this much revenue you *could* hire earlier — but staying lean just
  means more profit. At 10,000 users you're making **~₱856k/mo**.
- The profit is so strong you're not constrained by cost at all — you're constrained
  by **getting and keeping paying users** (acquisition + trial conversion + churn).

> ⚠️ **The honest caveats on "everyone pays":**
> 1. **Trial → paid conversion isn't 100%.** After a 3-month free trial, expect
>    ~**40–70%** to actually start paying. Even at **50%**, revenue halves — 10,000
>    users → ~₱495k/mo revenue, ~₱361k/mo profit. Still excellent.
> 2. **Monthly churn.** Some paying users cancel each month; at ₱99 you need steady
>    acquisition to keep the base growing. Track it.
> 3. **The 3-month free window delays revenue.** While you're growing fast, a big
>    slice of your user base is still inside its free period earning ₱0 — so *cash*
>    revenue lags the user count until growth steadies. The table shows the
>    **steady-state** (post-trial) picture.
> 4. **₱99 is very accessible** for PH new investors (a strength for adoption) but
>    leaves room to add a higher tier later (e.g. ₱299 "Pro" with deeper features).

---

## 4D. If you sell a 1-year plan

Annual pricing off the ₱99/mo base — usually with a small discount to pull people in:

| Plan | Price / year | Effective / mo | vs monthly |
|---|---|---|---|
| Monthly | ₱1,188 (₱99×12) | ₱99 | trickles in, easier to cancel |
| **Annual — "2 months free"** ✅ | **₱990** | ₱82.50 | **all cash upfront, locked 12 mo** |
| Annual — no discount | ₱1,188 | ₱99 | all upfront, locked 12 mo |

It barely changes yearly revenue per user, but it does **three powerful things:**

1. **Cash upfront.** You collect a full year at signup instead of ₱99 dribbling in.
   That cash self-funds your growth and hiring — you may never need outside money.
2. **Churn collapses.** Monthly churn (say ~5%/mo) locks to a *single* annual renewal
   decision — far higher retention and lifetime value.
3. **Predictable revenue** you can plan hiring against.

### Cash collected upfront (annual @ ₱990) ▶

| Annual subscribers | Cash in, upfront |
|---:|---:|
| 100 | ₱99,000 |
| 500 | ₱495,000 |
| 1,000 | **₱990,000** |
| 2,000 | ₱1,980,000 |
| 5,000 | ₱4,950,000 |
| 10,000 | **₱9,900,000** |

At **10,000 annual subs you collect ~₱9.9M upfront**; against a ~₱1.6M/yr burn
(₱134k × 12), that's **~₱8.3M/yr profit** — and you're holding a year of cash from
day one of each signup.

**The catch (be honest):** the ₱990 discount means ~17% less per user than 12× ₱99,
*if* they'd otherwise have stayed a full year on monthly (many wouldn't — they'd
churn first, so annual usually wins on net). And a 3-month free trial + annual means
the first real payment lands at month 4.

**Recommendation:** offer **both** at the paywall — **Monthly ₱99** (low barrier) and
**Annual ₱990 "2 months free"** (nudged as the best deal). You capture cash-rich
annual buyers *and* commitment-shy monthly ones. Annual take-up of 30–50% is common.

---

## 4E. The full paywall — plans & tiers

**3-month free trial → then pick a plan.** Two tiers, four billing durations
(longer = cheaper per month; longer terms pull cash forward and cut churn).

### Standard — ₱99/mo base

| Term | Price | Effective /mo | Discount |
|---|---|---|---|
| Monthly | ₱99 | ₱99 | — |
| 3 months | ₱279 | ₱93 | ~6% |
| 6 months | ₱534 | ₱89 | ~10% |
| **Annual** ✅ | **₱990** | ₱82.50 | ~17% (2 mo free) |

### Pro — ₱299/mo base (deeper features)

| Term | Price | Effective /mo | Discount |
|---|---|---|---|
| Monthly | ₱299 | ₱299 | — |
| 3 months | ₱849 | ₱283 | ~5% |
| 6 months | ₱1,614 | ₱269 | ~10% |
| **Annual** ✅ | **₱2,990** | ₱249 | ~17% (2 mo free) |

**What separates the tiers ▶** (grounded in `insights.md` features):

| | Standard (₱99) | Pro (₱299) |
|---|---|---|
| Valuation workbench (DCF/DDM/Graham/Multiples) | ✅ | ✅ |
| Portfolio holdings | up to ~10 | unlimited |
| News awareness | **daily digest** | **real-time alerts** |
| Insight scope | direct company + macro | + sector/peer + thematic |
| Valuation history / export | — | ✅ |
| Support | standard | priority |

**Why a Pro tier matters:** it lifts ARPU without touching your accessible ₱99 entry
point. Even a **10–20% mix upgrading to Pro** meaningfully raises blended revenue per
user — e.g. at 10,000 users, 15% on Pro ≈ blended **~₱129/user** vs ₱99, ~+30%
revenue for zero extra acquisition. The ladder numbers stay conservative (all-₱99);
Pro is upside on top.

---

## 5. Assumptions to verify before trusting the numbers

- ▶ **News/insight volume** (~200 articles/day → ~9k insight-gens/mo) — the single
  biggest driver. Measure actual PSE EDGE + media cadence and the avg # of
  companies a macro event maps to.
- ▶ **Per-call token sizes** — run `count_tokens` on a real article + system prompt.
- ▶ **Embedding model + vector dimension** — `text-embedding-3-small` vs `-large`;
  must match the pgvector column.
- ▶ **OpenAI model choice** — GPT-5 mini vs GPT-5 for the insight writer (5× cost gap);
  validate insight quality on real PSE articles before locking the mix.
- ▶ **News API provider, PH coverage & commercial license** — confirm the chosen API
  actually covers PH business media / PSE tickers, and that the tier is commercial-use
  (NewsAPI.org dev / GNews free are non-commercial). Confirm whether PSE EDGE is
  scraped (free) or via a paid feed.
- ▶ **Cloud provider & region** — AWS vs Render/DO/Fly changes Tier-A total 20–40%.
- ▶ **MAU / registered ratio** (assumed ~20%) and the MAU→paid conversion, which
  drives revenue, not cost.
- ▶ **FX ₱57/$** — set at spend time.
- ▶ **Doc reconciliation** — update `FINSIGHT.md` (says "Claude") to OpenAI to match
  `insights.md` and this model.

## 6. Sources (pricing)

- OpenAI API pricing 2026 — GPT-5 $1.25/$10, GPT-5 mini $0.25/$2, GPT-5 nano
  $0.05/$0.40, batch −50%: https://pecollective.com/tools/openai-api-pricing/ ·
  https://www.cloudzero.com/blog/openai-pricing/
- text-embedding-3-small ($0.02/1M): https://costgoat.com/pricing/openai-embeddings
- News API pricing 2026 — NewsData.io tiers ($0–$599.99), NewsAPI.org ($449/mo
  Business; dev tier non-commercial), Finnhub (~$50/mo+): https://newsdata.io/blog/news-api-comparison/ ·
  https://apitube.io/blog/post/best-financial-news-api-trading
- Marketaux (financial news, ticker-tagged; free 100 req/day): https://www.marketaux.com/pricing
- PH salaries 2026 — software engineer ₱55–75k/mo (Jobstreet/Glassdoor); support
  ₱20–38k; data analyst ₱40k+; DevOps ~₱78k/mo; +15–20% statutory + 13th month:
  https://ph.jobstreet.com/career-advice/role/software-engineer/salary ·
  https://hellopebl.com/resources/blog/average-salary-in-philippines/
