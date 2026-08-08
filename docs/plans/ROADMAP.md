# FinSight US valuation — roadmap

Source of truth for what's next on the US SEC filing-only valuation pipeline. Ordered by **leverage**, not by when
it was raised. Supersedes the ad-hoc gap notes; the detailed gap analysis lives in
`docs/us-coverage-gap.md` (from the pipeline repo) — this is the sequenced, gated version.

**Definition of done (every item):** the real thing works per the project's profile — for the *engine*, the valuation
computes and is **correct on real filings** (spot-checked, not just "script ran"); for the *app*, it renders when driven
like a user — **and you've confirmed it**. `review_required`/CANDIDATE ≠ done; `pass` needs human sign-off.

## ✅ SHIPPED (2026-08-08 — merged to `main`, deployed to Cloud Run staging)
- **195 US valuations live** (up from 12): FCFF + banks (residual income) + utilities (DDM) + insurance/securities/credit
  (residual income) + large-cap equity-level fallbacks. Confirmed live: `GET /api/us-valuations` → 195.
- Phase NOW **N1/N2/N3 done & deployed**; Phase 3 **M1 (insurance) + M3 (securities/credit) done**; F3 API-level
  live-verified.
- Funnel now: **classified 336 · publishable 195 · withheld 82 · unsupported 141** (of 477). Goldens 55 / full suite 107 pass.

## Original state (start of this phase)
- Pipeline migrated (backend package + `/api/us-valuations` + frontend page); 7 commits.
- **15 archetypes** (FCFF tech/industrials/pharma/chem/staples/internet/machinery/retail/transport/telecom; equity-level
  banks/utilities); model **dispatch** on `primary_model`; **equity-level fallback** (FCFF→residual-income/DDM).
- Funnel across the 500-issuer universe (477 with data): **classified 289 · publishable 160 · withheld 70 · errors 59 ·
  unsupported 188**.
- **BUT only 12 valuations are curated + served by the app.** The 160 are computed, mostly CANDIDATE/`review_required`
  (candidate archetypes + 88 machine-attested overrides + conservative fallbacks) — **not yet human-ratified, not served.**

---

## Phase NOW — ship it & make the coverage visible (cheap, high-visibility)
The loudest gap: we tripled computable coverage but users still see 12, and nothing is pushed.

| ID | What | Source gap | Sev | Status |
|---|---|---|---|---|
| **N1** | Push `feature/...` / open a PR | 10 commits stranded locally | High | **⏸ PAUSED — awaiting go-ahead** (outward-facing push; branch push doesn't deploy, only merge to `main` does). |
| **N2** | Fix fallback edge-case misses (CAT-style equity-fallback extraction) | this session | Med | **✔ DONE** (`e3d916c`) — CAT→$99.9 (DDM), DE $145 (RI), ITW $105; harvest publishable 160→163; goldens 54. |
| **N3** | **Curate + serve more than 12** valuations + wire the picker | 160 computed / 12 served | High | **✔ DONE** (`9b7af1f`) — **served 12→26** (banks/utilities/fallbacks); project public-safety assertion passes; router 26→200, 0 forbidden keys; frontend builds. Browser render = F3 (Phase 2). |

## Phase 2 — trust & verification (foundational)
| ID | What | Status |
|---|---|---|
| **F1** | Ratify the 88 machine overrides before any `pass` | **⚠ machine-verified** (audited: 0 balance-sheet conflicts) — human sign-off is the remaining *formal* step; all stay `review_required`, none `pass`. Owner: analyst. |
| **F2** | Main's own bulk SEC cache | **deferred** — 3 GB `fetch_sec_bulk download`; low urgency (live per-issuer path already works from main; sweep references the pipeline-repo cache). |
| **F3** | Verify the page against the live stack | **✔ API-level done** (deployed staging serves 195, spot-checked live). Full browser login→render still worth a manual pass. |

## Phase 3 — model coverage for the remaining sectors (per-area; the 188 unsupported)
| ID | What | Status |
|---|---|---|
| **M1** | Insurance (SIC 6300-6411) → residual income | **✔ DONE** — AIG $88, PGR $70, TRV $222 (review_required, live) |
| **M3** | Securities/credit (6200-6299 / 6100-6199) → residual income | **✔ DONE** — GS $543, MS $95, AXP $83 (live) |
| **M2** | **REIT FFO/NAV model** (65/67xx, ~15: O/PLD/WELL) | **remaining — LARGE** (genuinely new model; FCFF/RI don't fit REITs) |
| **M4** | Commodity/energy reserve-aware (~40: CVX/OXY/FCX) | **remaining — LARGE** (FCFF runs but reserves/cycle distort; needs care before publish) |
| **M5** | Remaining tail archetypes (agriculture, misc) | remaining — small |

## Phase 4 — normalization, data & cleanup (last)
| ID | What | Source | Sev | Verify |
|---|---|---|---|---|
| **D1** | `operating_income` derivation (8, pharma) — careful per-issuer opex mapping (naive derivation was unsafe → deferred) | engine_errors | Med | LLY/PFE derived operating income reconciles vs a known year; no overstatement. |
| **D2** | capex alias for EA/RPRX (stale/unmapped tag) | engine_errors | Low | EA capex resolves; value sane. |
| **D3** | `docs/` cleanup — split generator scripts vs generated PDFs/HTML (or gitignore outputs) | folder tidiness | Low | `docs/` scannable; generators separated. |
| **D4** | Reconcile / retire the source repo (`finsight-pipeline`) now the work lives in main | two-repo divergence | Low | One source of truth; memories/gap-doc migrated or pointed. |

---

## Sizing & right-sizing notes
- **M1/M2 (insurance, REIT) are large** (genuine new models) but high-value — keep them their own phase, don't let them
  block the cheap NOW wins.
- **IFRS/20-F foreign filers (20 errors: UL/NVO/AZN/SAP…) → backlogged**, not scheduled: it's a separate ingestion path
  (20-F on IFRS), out of scope for the US-GAAP engine. See backlog.
- **Full 500 publishable-and-credible is NOT a milestone here** — it needs sustained analyst review of assumptions +
  overrides; scheduled as ongoing (F1), not a one-shot.

→ Hand **Phase NOW (N1–N3)** to `/gate-build-goodbehavior`.
