# PSE Valuation Engine — Implementation Plan

**Spec:** `PSE_VALUATION_ENGINE_FRAMEWORK.pdf` (11 pages)
**Scope:** Bring the codebase up to the framework's methodology — a subsector-aware,
public-data screening valuation engine for PSE issuers.
**Status date:** 2026-07-28

The PDF is the design spec for our valuation models. The individual model math is
largely built; the missing piece is the **engine layer** — subsector routing,
validity gates, blending, and a standard output contract — that turns standalone
model functions into "the PSE Valuation Engine."

---

## 1. Where we are today

### Implemented (`backend/app/valuation/`)

| Framework model | Code | Notes |
|---|---|---|
| **M1 FCFF DCF** | `dcf.py::dcf_valuation` | EV DCF + Gordon terminal + EV→equity bridge |
| **M2 FCFE DCF** | `dcf.py::fcfe_valuation` | equity-level variant, no debt bridge |
| **M3 DDM** | `ddm.py::ddm_valuation`, `two_stage_ddm` | single + two-stage |
| **M6 Trading comps** | `multiples.py` | P/E, P/B, EV/EBITDA |
| **M10 Graham screen** | `graham.py` | PHP govt yield instead of US AAA |
| **§4 Discount-rate policy** | `assumptions.py` | PH CAPM `Ke`, WACC, ~3% terminal `g` |

Supporting: `common.py` (summarize/verdict, CAGR, avg growth), `assumptions.py`
`MarketAssumptions` (PH defaults, DB-overridable via `market_assumptions` table).

**API:** `routers/valuations.py` exposes `POST /dcf`, `/ddm`, `/graham`, `/multiples`;
save/list/get/delete of `SavedValuation`. Pydantic inputs in `models/valuation.py`.

**Tests:** `backend/tests/test_valuation.py` — 18 tests covering each model's math,
guard rails, and the spreadsheet-parity fixes.

### Not yet built (framework gaps)

**Models:** M4 Residual income · M5 Financial-institution excess-return ·
M7 NAV/RNAV · M8 SOTP · M9 EPV.

**Engine layer (the core gap):**
- **§5** subsector routing table (PSE subsector → primary/supporting models)
- **§7.1** `if/elif` classification + business-mix override logic
- **§7.2** model validity gates + machine-readable failure reasons
- **§7.3** blending weight ranges + convergence policy
- **§7.4** standard JSON output contract
- **§2.2** annual/quarterly consolidation + TTM construction
- **§6** required-inputs → public-source mapping
- **§9** refresh cadence / staleness triggers
- **§10** governance surface (raw-vs-normalized, confidence grade, warnings)

---

## 2. Target architecture

```
backend/app/valuation/
  models/                 # pure math, one file per M#  (existing files move here)
    fcff.py  fcfe.py  ddm.py  residual_income.py  fin_excess_return.py
    comps.py  nav_rnav.py  sotp.py  epv.py  graham.py
  engine/
    classify.py           # §7.1 subsector -> model routing (the if/elif ladder)
    subsectors.py         # §5 master table as data (dict/enum config)
    gates.py              # §7.2 validity gates + reason codes
    blend.py              # §7.3 weighted median/avg + convergence tests
    contract.py           # §7.4 output schema (Pydantic) + builder
    periods.py            # §2.2 TTM construction, annual/quarterly consolidation
  assumptions.py          # §4 (exists)
  common.py               # (exists)
```

Design principles from the framework:
- Every result carries **method, period, assumptions, source IDs, confidence, warnings**.
- Never overwrite a raw fact with a proxy without labeling it.
- Blend only when models are decision-useful and within tolerance; else publish a range.
- Financial institutions use equity models (`Ke`, not WACC).

---

## 3. Phased work plan

### Phase 0 — Gap analysis & scaffolding (no behavior change)
- [ ] Move existing model files under `valuation/models/`, keep import shims.
- [ ] Add `engine/` package skeleton with typed stubs.
- [ ] Encode §5 master table as `subsectors.py` data (subsector → primary,
      supporting, key multiples, required inputs, exceptions).
- **Exit:** existing tests still green; subsector table importable.

### Phase 1 — Output contract + gates (§7.2, §7.4)
- [ ] `contract.py`: Pydantic `ValuationRecord` matching the §7.4 JSON
      (`ticker`, `pse_subsector`, `valuation_date`, `price_source`, `period_basis`,
      `models[]`, `blended_value_per_share`, `range_low/high`, `confidence`,
      `assumptions`, `source_ids`, `warnings`).
- [ ] `gates.py`: reason codes (`NEGATIVE_EBITDA`, `MISSING_DILUTED_SHARES`,
      `STALE_NAV`, `UNAVAILABLE_RESERVE_DATA`, `FINANCIAL_INSTITUTION_USE_EQUITY_MODEL`)
      + a `run_model_if_valid()` wrapper.
- [ ] Wrap existing DCF/DDM/comps/Graham outputs into `ValuationRecord`.
- **Exit:** each existing endpoint returns a contract-shaped record; gate failures
      are reported, not thrown.

### Phase 2 — Classifier + blending (§7.1, §7.3)
- [ ] `classify.py`: the `if/elif` ladder (ETF→NAV, financials→M5+P/B,
      holding→M8, property/mining/oil→M7, profitable op co→M1, …) + business-mix override.
- [ ] `blend.py`: weighted median/average after dropping failed models,
      1.5× convergence check, "insufficient convergence" path, sensitivity range.
- [ ] New endpoint `POST /valuation/auto` — ticker in, full `ValuationRecord` out.
- **Exit:** a ticker routes to the right primary/supporting models and blends per §7.3.

### Phase 3 — Missing models
Priority by coverage of PSE market cap:
- [ ] **M5 Financial-institution excess-return** (Banks — BDO/BPI/MBT; largest weight).
- [ ] **M4 Residual income** (supporting for banks / noisy-FCF names).
- [ ] **M7 NAV/RNAV** (Property + Mining/Oil — ALI/SMPH/Nickel Asia).
- [ ] **M8 SOTP** (Holding firms — SM/Ayala/JG Summit).
- [ ] **M9 EPV** (supporting/fallback for mature cyclicals).
- Each: pure-math module + unit tests + wire into classifier/subsector table.
- **Exit:** every §5 subsector has its primary model available.

### Phase 4 — Period & data plumbing (§2.2, §6, §9)
- [ ] `periods.py`: TTM = Q1+Q2+Q3+Q4 (non-overlapping), balance-sheet latest,
      double-count guard for restatements.
- [ ] Required-inputs → source mapping wired to the ingest/parser outputs
      (`pse/financials_mapper.py`, `tools/fs-parser`).
- [ ] Staleness triggers + confidence downgrade per §9.
- **Exit:** engine consumes parsed filings and self-labels period basis + freshness.

### Phase 5 — Governance & UI surface (§10)
- [ ] Persist raw-vs-normalized inputs alongside results.
- [ ] Surface confidence grade, assumptions, source IDs, warnings in
      `frontend/src/pages/ValuationLab.tsx` / `Valuation.tsx`.
- **Exit:** no automated value shown without its provenance and confidence.

---

## 4. Guardrails carried from the framework
- Screening tool, **not** a fairness opinion / recommendation.
- Data-licensing: stay in the light PSE tier — EOD inputs, derived-only display
  (see memory: data-licensing-strategy).
- Financial institutions: `Ke`, not WACC; regulatory-capital reinvestment.
- Holding firms: SOTP, apply ownership % before parent-debt subtraction; no cross-holding double-count.
- Property/mining: NAV/RNAV preferred where asset values are observable; reserve NAV over perpetual terminal.
- SME/thin data: screening-grade only, cap automated output, widen ranges.

---

## 5. Open questions
- [ ] Where does subsector classification data come from at ingest — PSE EDGE
      field, or a maintained mapping table? (§5 assumes official PSE subsector.)
- [ ] Peer sets for M6 comps — hand-curated per subsector, or derived?
- [ ] `ERP_PH` source — fixed assumption vs. periodically refreshed (§9).
- [ ] Do we persist `ValuationRecord` as JSONB, or normalize `models[]` into rows?
