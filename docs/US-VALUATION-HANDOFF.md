# US Valuation Engine — Partner Handoff

_Last updated: 2026-08-08. Live on Cloud Run **staging**._

## TL;DR (scan this first)
- There is a new **"US Valuations"** page in the app (left nav) serving **206 filing-only US equity valuations**
  (up from 12). Backend endpoint: `GET /api/us-valuations` (list) and `/api/us-valuations/{ticker}`.
- Every valuation is derived **only from SEC filings** (no market prices, no buy/hold/sell) and is **`review_required`
  (a CANDIDATE)** — none are promoted to final (`pass`). They show badges + "educational, not investment advice."
- **The engine and public-safety are solid; the *assumptions and coverage quality* need your review.** That's the main
  ask below.
- Live staging: backend `https://finsight-backend-staging-788383452933.asia-southeast1.run.app`,
  frontend `https://finsight-frontend-staging-788383452933.asia-southeast1.run.app`.

---

## What was built
A filing-only, multi-model US valuation pipeline, migrated into this repo and deployed:

- **Ingestion** — SEC EDGAR (submissions + companyfacts), replayable from a local cache or live per-issuer
  (`app/us_valuation/sec_client.py`, `scripts/fetch_sec_bulk.py`, `scripts/harvest_us_quarterly.py`). Verified live + offline.
- **Classification** — SIC code → one of **19 archetypes** (`config/archetypes.json`), each with calibrated policy.
- **Multi-model valuation**, dispatched by the archetype's `primary_model`:
  | Model | Used for | Notes |
  |---|---|---|
  | **FCFF DCF + EPV** | tech, industrials, pharma, chemicals, staples, semis, med-devices, retail, transport, telecom | the original engine |
  | **Residual income** | banks, insurance, securities/brokers, nondepository credit | equity-level (book + excess return) |
  | **DDM** | utilities | dividend-based |
  | **FFO × P/FFO** | REITs | FFO = net income + real-estate depreciation − property-sale gains (filing-derived, approximate) |
  | **Equity-level fallback** | any FCFF issuer whose enterprise bridge can't complete | falls back to residual income / DDM instead of withholding |
- **Public-safety** — every served artifact passes a **fail-closed assertion** (`assert_public_artifact_is_safe`):
  no raw statement amounts, no prices, no recommendations. Sanitised again at the serving boundary.
- **Guards** — non-positive and implausible (>$50k/share, <1M shares) values are **withheld**, not published.
- Full backend suite **107 passed**; frontend `tsc + vite` build clean; 4 deploys, all green.

### Current funnel (500-issuer working universe, 477 with full data)
`classified 351 · publishable 206 (served) · withheld ~86 · unsupported ~126`. Served model mix ≈ residual-income 100+,
DDM 70, FCFF 14, FFO ~11.

---

## ⚠️ Honest quality caveats (please read before trusting any number)
1. **All 206 are CANDIDATES (`review_required`), not final.** Nothing is `pass`. The UI badges them.
2. **Archetype policy assumptions are calibrated-not-ratified.** Growth/margin/ROE/multiple ranges come from SEC
   comparables + judgment, **not analyst sign-off**. Some cohorts are contaminated (e.g. "retail" mixes discount +
   franchise; "internet" is META/GOOGL-heavy).
3. **88 of ~91 per-issuer bridge overrides are MACHINE-attested** ("automated bridge-absence check"), not human-reviewed.
   They were conservatively verified (0 balance-sheet conflicts found), but a human hasn't signed them.
4. **Many large-caps show CONSERVATIVE fallback values.** FCFF withholds without per-issuer overrides, so names fall
   back to residual income / DDM, which **undervalue low-payout growth companies** (e.g. WMT, HD conservative).
5. **FFO (REITs) is a filing approximation** — it omits company-specific addbacks, so several REITs are conservative
   (O ≈ market, but PLD/WELL/VTR low). Absurd extractions are guarded (SPG withheld).

---

## ✅ Done  ·  ❌ Remaining  (roadmap: `docs/plans/ROADMAP.md`)
**Done & live:** migration; 19 archetypes; FCFF/RI/DDM/FFO models + dispatch; equity-level fallback; public-safety
gate; 206 served; banks, utilities, insurance, securities/credit, REITs; engine-error fixes; deployed to staging.

**Remaining:**
- ❌ **M4 — commodity/energy** (~40 issuers: CVX/OXY/FCX) — reserve/cycle-aware treatment (real model work).
- ❌ **~126 still unsupported** — agriculture, misc, and the harder financial/energy tails.
- ❌ **D1 — pharma operating-income derivation** (8: LLY/PFE/MRK) — deferred as unsafe (a naive derivation overstates;
  needs careful per-issuer opex mapping).
- ❌ **D2 — capex alias** (EA/RPRX) — low value, unmapped tag.
- ❌ **FFO refinement** — full AFFO/NAV for REITs (needs non-GAAP supplement data not in companyfacts).
- ❌ **59 engine_errors** remain — mostly **IFRS/20-F foreign filers** (UL/NVO/SAP — out of scope for a US-GAAP engine)
  and thin-history issuers.
- ⚠️ **F2 — main's own SEC cache** — the offline 500-sweep currently references the dev repo's ~3 GB cache; live
  per-issuer works from main. Low urgency.
- ⚠️ **F3 — browser render pass** — the API is verified live; a manual login→render walkthrough is still worth doing.

---

## 🙋 What's needed from YOU (partner actions)
1. **Ratification bar (biggest one).** Decide what it takes to promote a valuation from `review_required` → `pass`:
   review the candidate archetype assumptions (`config/archetypes.json` `valuation_policies`) and the 88 machine
   overrides (`issuer_overrides`). Nothing should show as "final" without your sign-off.
2. **Product call: which to surface.** All 206 are served today. Some are rough/conservative. Decide whether to show
   the full set (badged) or a **curated credible subset** to users.
3. **Domain sign-off on the policies.** Correct the growth/margin/ROE/P·FFO/P/FFO assumptions per archetype where your
   judgment differs; flag cohort splits (retail, internet, transport).
4. **Priorities for the remaining models** — is commodity/energy (M4) or FFO-refinement worth building next?
5. **Retire the dev repo?** All work now lives in **this repo (`finsight`)**. The pipeline dev repo
   (`finsight-pipeline`) still holds the SEC caches and this session's memory/notes — decide whether to reconcile +
   retire it (roadmap D4).

---

## How to run / verify
```sh
# Backend tests (full suite)
cd backend && python -m pytest                     # 107 passed
# Serve the app locally
./infrastructure/scripts/up.sh                     # docker stack; then open the US Valuations page
# Re-run the 477-issuer coverage sweep (needs the SEC bulk cache; currently in the finsight-pipeline repo)
PYTHONPATH=backend python scripts/harvest_us_quarterly.py --source bulk --bulk-dir <cache> --as-of 2026-08-01 --out /tmp/h
# Check the deployed API
curl https://finsight-backend-staging-788383452933.asia-southeast1.run.app/api/us-valuations
```

## Key files
- `backend/app/us_valuation/` — the engine: `pipeline.py` (dispatch), `models.py` (FCFF/EPV), `equity_models.py`
  (RI/DDM/FFO + fallback), `xbrl.py` (normalizer), `classification.py`, `artifacts.py` (public-safety), `config/`.
- `backend/app/routers/us_valuations.py` — the API. `backend/app/data/us_valuations/*.json` — the 206 served artifacts.
- `frontend/src/pages/UsValuations.tsx` — the page.
- `backend/tests/test_us_valuation.py` — golden + safety tests.
- `docs/plans/ROADMAP.md` + `PRODUCTION-BACKLOG.md` — the full plan.

> Every published number is filing-derived, price-free, and marked `review_required` — an **educational estimate, not
> investment advice.** Promotion to `pass` is a human decision you own.
