# US Valuation — Review Decisions

Companion to the **US Valuation Review Queue**. This records the reviewer analysis and a
**recommended disposition** for each investigated name. These are **recommendations for human
ratification, not approvals** — nothing here changes an artifact's `publication_state`. Publishing
still requires a human sign-off.

_Last updated: 2026-08-08. Artifacts: 206. All live on GCP staging._

---

## 0. Systemic fix shipped: SEC provenance repaired (queue item #2)

The queue's biggest approval gate — "Weak SEC information" (192) and "Missing SEC information"
(`NET`, `XYZ`) — is **closed** for all 206 artifacts, repaired once systemically rather than 192×.

| Gate | Before | After |
| --- | --- | --- |
| Missing SEC URL | 2 (`NET`, `XYZ`) | **0** |
| Generic browse-EDGAR link | 192 | **0** |
| Missing `filed_date` | 192 | **0** |
| Ambiguous `10-K / 10-Q` form | 192 | **0** |
| Precise `Archives/` URL | 12 | **206** |

**How:** `backend/app/us_valuation/repair_provenance.py` reads each artifact's `issuer.cik` +
`source_financial_statement.accession`, looks the accession up in SEC's submissions JSON, and writes
back the precise Archives URL, real `filed_date`, and actual `form`. It touches **only** provenance
fields — never valuation numbers — so it cannot regress a curated result the way re-running the
engine would.

**Validation:** AAPL's reconstruction reproduced its existing curated URL exactly; every rebuilt URL
returns HTTP 200; verified live on staging. Shipped in commit `097d230`.

---

## 1. Immediate-investigation set — DCF/EPV dispersion >40% (queue item #1)

Sizing across all 206 shows the acute problems are **contained, not systemic**:

| Signal | Count | Names |
| --- | --- | --- |
| DCF/EPV dispersion >40% | 9 | ADSK, CRM, DELL, MSFT, NET, NOW, STX, WDC, XYZ |
| EPV negative | **1** | NET |
| Terminal value >85% | **1** | NET |
| Terminal value >75% | **2** | NET, DELL |
| Share-count proxied | 14 | FCFF-model names (bounded; inherent to filing-only extraction) |

**Key insight:** every one of the 9 has **DCF > EPV**, because DCF prices growth and EPV is a
deliberate *no-growth floor*. A 40–70% premium for a growing software/cloud or cyclical-hardware name
is the growth premium — expected, not an error. The `>40%` rule is a **triage trigger, not a
verdict**. On inspection, **7 of the 9 resolve benign**; only NET and DELL need action.

### Dispositions

| Ticker | DCF | EPV | Disp. | Recommended disposition | Rationale |
| --- | ---: | ---: | ---: | --- | --- |
| **NET** | 4.11 | **−4.59** | 212% | **Reject / keep withheld** | Unprofitable hyper-growth (Cloudflare). No-growth EPV is structurally negative → cross-check uninformative; terminal >85% → value is almost entirely terminal. No defensible single value. |
| **DELL** | 267.37 | 91.35 | 66% | **Investigate — recalibrate growth** | `initial_revenue_growth` clamped at the 20% policy ceiling; carrying 20% for a largely-mature, ~6%-margin hardware business drives terminal >75% and the high base. Taper near-term growth before sign-off. |
| ADSK | 130.89 | 73.40 | 44% | Approve-with-caveat | Expected growth premium; share-proxy caveat. |
| CRM | 116.86 | 49.94 | 57% | Approve-with-caveat | Expected growth premium; share-proxy caveat. |
| MSFT | 316.78 | 189.17 | 40% | Approve-with-caveat | Expected growth premium; share-proxy caveat. |
| NOW | 33.37 | 10.43 | 69% | Approve-with-caveat | Expected growth premium; share-proxy caveat. |
| XYZ | 48.65 | 9.25 | 81% | Approve-with-caveat | Expected growth premium; share-proxy caveat. Provenance now repaired. |
| STX | 120.04 | 65.97 | 45% | Approve-with-caveat | Cyclical hardware; premium reflects up-cycle. Share-proxy caveat. |
| WDC | 64.97 | 30.87 | 52% | Approve-with-caveat | Cyclical hardware; `initial_revenue_growth` also at 20% ceiling — sanity-check like DELL. |

**Sources (repaired):**
- NET — 10-Q filed 2026-05-08 — https://www.sec.gov/Archives/edgar/data/1477333/000147733326000038/cloud-20260331.htm
- DELL — 10-Q filed 2026-06-09 — https://www.sec.gov/Archives/edgar/data/1571996/000157199626000030/dell-20260501.htm

---

## 2. Remaining buckets (not yet worked)

| Bucket | Size | Status | Next |
| --- | --- | --- | --- |
| Fallback model (FCFF → residual income / DDM) | 107 | not reviewed | Reconcile missing bridge fields by model family. |
| Manual override | 63 | not reviewed | Confirm each override still matches current economics. |
| Low classification confidence (<0.80) | 182 | triage signal only | Review archetype + model selection first. |
| High value | 15 | not reviewed | Recheck units, shares, terminal assumptions. |
| FFO (non-GAAP approximation) | 12 | not reviewed | Focused manual set: reconcile filing FFO, AFFO/maintenance capex. |

---

## 3. Notes for the human reviewer

- **Nothing here is auto-approved.** All 206 remain at their engine-assigned `publication_state`
  (mostly `review_required`). Ratification is yours.
- **NET** is the one clear reject in the urgent set; **DELL** (and secondarily **WDC**) need a growth
  recalibration; the rest of the urgent set is working as intended.
- The **share-count proxy** (14 names) is a bounded, disclosed data-quality caveat inherent to
  filing-only extraction — not a blocking defect, but note it on any FCFF sign-off.
