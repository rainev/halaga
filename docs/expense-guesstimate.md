# FinSight — Expense Guesstimate (Lean Stack)

> Status: guesstimate. Draft 2026-08-07. A quick, decision-oriented cost sheet for
> the **lean beta/early stack** (Supabase + Tiingo + GNews + Cloud Run). For the
> fuller Tier A/B/C model, salaries, and unit economics, see [`cost-model.md`](./cost-model.md).
> FX: **₱57 = US$1** (verify at spend time).

---

## 0. The headline

- **GCP and AI API are shared infrastructure.** Running web *and* mobile does **not**
  double them — one backend serves both clients.
- **AI scales with content, not users.** Insights are generated once per
  `(article, company)` and shared, so the AI line barely moves as users grow.
- **Beta savings** come almost entirely from Cloudflare ($0) and domain ($0).
- **Production all-in (either platform): ~$195–217/mo** (~₱11–12.5k), plus one-time
  app-store fees for mobile.

---

## 1. One-time / annual (upfront)

| Item | Cost | Applies to |
|---|---:|---|
| Apple Developer | $100 / yr | Mobile |
| Google Play | $25 one-time | Mobile |
| Domain name | $20 / yr | Website ($0 during beta) |

---

## 2. Monthly — WEBSITE

| Line | Beta | Production |
|---|---:|---:|
| GNews.io | $60 | $60 |
| Supabase | $25 | $25 |
| Tiingo EOD | $50 | $50 |
| Cloudflare | $0 | $20 |
| Domain (amortized) | $0 | ~$2 |
| **GCP** (Cloud Run backend) | **$15** | **$30** |
| **AI API** | **$15** | **$30** |
| **Total / mo** | **≈ $165** | **≈ $217** |

## 3. Monthly — MOBILE

| Line | Beta | Production |
|---|---:|---:|
| GNews.io | $60 | $60 |
| Supabase | $25 | $25 |
| Tiingo EOD | $50 | $50 |
| **GCP** (Cloud Run backend) ⚠️ | **$15** | **$30** |
| **AI API** | **$15** | **$30** |
| **Total / mo** | **≈ $165** | **≈ $195** |
| Upfront (Apple $100 + Play $25) | $125 | $125 |

> ⚠️ **Mobile still needs GCP.** A mobile app calls the same FastAPI backend on
> Cloud Run (valuations, news, insights). The GCP line only disappears if the app
> talks *directly* to Supabase + the AI API with no custom backend — which is not
> how FinSight's valuation/insights pipeline is built.

## 4. Monthly — BOTH (shared backend)

| Line | Beta | Production |
|---|---:|---:|
| GNews.io | $60 | $60 |
| Supabase | $25 | $25 |
| Tiingo EOD | $50 | $50 |
| Cloudflare | $0 | $20 |
| Domain (amortized) | $0 | ~$2 |
| **GCP** (shared, not doubled) | $15 | $30 |
| **AI API** (shared, not doubled) | $15 | $30 |
| **Total / mo** | **≈ $165** | **≈ $217** |
| Upfront (Apple $100 + Play $25 + domain $20) | $145 | $145 |

---

## 5. How the billable lines were computed

### AI API
Grounded in `cost-model.md`'s workload — insights generated **once per
`(article, company)` and shared**, so cost tracks *news/filing volume*, not users.

| Task | Volume / mo | Cost |
|---|---:|---:|
| Insight writing (cheap tier + hard ~20% on top model) | ~9,000 | ~$27 |
| Classification / relevance (nano tier) | ~6,000 | ~$1 |
| Embeddings | ~6,000 | ~$1 |
| **Recommended mix** | | **~$29/mo** |
| Batched (−50%) + cached system prompt | | **~$17/mo** |

Plus the **filing-only US SEC valuation pipeline** — batch work per company per
filing (quarterly cadence), ~$2–5/mo incremental.

**→ ~$15/mo at beta (thin coverage), ~$30/mo at early production.**

### GCP (FastAPI backend on Cloud Run)

| Component | Beta | Early prod |
|---|---:|---:|
| Cloud Run (API + workers; scales to zero at beta) | ~$8 | ~$22 |
| Cloud Functions (budget guard) | ~$0 | ~$1 |
| Cloud Scheduler (≤3 jobs) | $0 (free) | $0 (free) |
| Secret Manager + Artifact Registry | ~$1 | ~$2 |
| Egress + logging | ~$2 | ~$5 |
| **GCP total** | **~$15/mo** | **~$30/mo** |

---

## 6. Notes & caveats

- **Shared, not doubled.** Web + mobile pay **one** GCP + AI backend. Combined
  production ≈ website cost (~$217/mo) + the $125 upfront app-store fees.
- **Cloud Scheduler is ~$0** (first 3 jobs free) — it's the *trigger* for the
  Tiingo EOD pull, GNews refresh, and insight cron. Tiingo is a data *source*, not
  a scheduler; the two are unrelated. Alternative: Supabase `pg_cron` (already paid
  for) can replace Cloud Scheduler entirely.
- **GNews freshness caveat.** GNews indexes fast globally, but the PSE/PH-markets
  beat is *sparse* — a broad market query returns thin/stale results, and
  company-specific news (e.g. "Apple Pay + PH banks") is missed unless queried by
  company name. Core same-day freshness comes from **PSE EDGE scraping** (free),
  not GNews.
- **Tiingo is US-market EOD** — it does not cover PSE/PH-media news; GNews + EDGE
  carry that.
- **Not included:** payroll (see `cost-model.md` §3B), transactional email/SMS,
  and any paid PH-media news API (NewsData.io ~$100/mo) if the media angle is added.
- **FX:** ~$217/mo ≈ **~₱12.4k/mo** at ₱57/$.

## 7. Sources

- Assumptions and workload volumes: [`docs/cost-model.md`](./cost-model.md)
- GCP pricing: Cloud Run, Cloud Scheduler (3 free jobs), Secret Manager, Artifact
  Registry — Google Cloud pricing pages (verify at spend time).
