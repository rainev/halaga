# Microsoft U.S. Valuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify Microsoft as an enterprise software/cloud issuer, produce a filing-only segment-aware FCFF DCF and EPV result, apply publication gates, and show a public-safe result in FinSight.

**Architecture:** Extend the existing U.S. valuation package with a second explicit segment mode, `segment_operating_income`, while retaining Apple’s `segment_gross_profit` path unchanged. Use the existing SEC client and normalized consolidated facts, add Microsoft filing evidence in configuration, build private and public-safe artifacts through shared code, then render both Apple and Microsoft with data-driven U.S. labels in the existing Valuation view.

**Tech Stack:** Python 3, pytest, SEC submissions and Companyfacts APIs, existing U.S. valuation package, JSON configuration and artifacts, React/TypeScript, Vite.

## Global Constraints

- Use only public SEC submissions, Companyfacts, filing-specific inline XBRL, and governed filing tables.
- Do not use current price, market capitalization, analyst estimates, proprietary data, price-derived beta, price-based upside/downside, or buy/sell labels.
- Preserve accession, URL, filing date, period end, fiscal period, units, fact tag, and extraction status in private audit data.
- Preserve Apple and BDO behavior unless a shared change is required and verified.
- Generic archetype evidence may not exceed 25% of initial-growth weighting when company history exists.
- Only `pass` results are normally publishable; `review_required` must show “Preliminary valuation - requires data review”; `withheld` must not show an intrinsic value.
- Public artifacts must contain derived values, high-level assumptions, warnings, methodology, and source links only; no raw filing tables or raw financial-statement values.
- Keep annual, cumulative YTD, standalone quarterly, and TTM facts separate.

---

## File structure

- `backend/app/us_valuation/config/archetypes.json`: SIC 7372 route, Microsoft override, and enterprise software/cloud policy.
- `backend/app/us_valuation/config/issuer_forecasts.json`: Microsoft annual/YTD segment evidence and SEC source map.
- `backend/app/us_valuation/classification.py`: return explicit `requires_segment_forecast`.
- `backend/app/us_valuation/assumptions.py`: construct a segment-operating-income forecast and reconciliations.
- `backend/app/us_valuation/models.py`: forecast segment revenue and operating income in FCFF DCF.
- `backend/app/us_valuation/pipeline.py`: use explicit segment requirement and preserve the review gate.
- `backend/app/us_valuation/artifacts.py` (new): reusable private/public/frontend artifact transformation functions.
- `scripts/build_us_valuation_pipeline.py` (new): reusable SEC-cache-to-artifact build entrypoint.
- `scripts/build_apple_us_valuation_pipeline.py`: compatibility wrapper or caller of the reusable builder with Apple metadata.
- `backend/tests/test_us_valuation.py`: Microsoft routing, forecast, publication and regression tests.
- `backend/tests/fixtures/us/msft-submissions.json` and `backend/tests/fixtures/us/msft-companyfacts.json`: minimized, versioned fixtures generated from SEC responses.
- `frontend/src/research/generated/microsoft-valuation.js` (generated): public-safe MSFT company artifact.
- `frontend/public/data/microsoft-valuation-pipeline.json` and `backend/app/data/us_valuations/MSFT.json` (generated): matching public-safe artifacts.
- `frontend/src/research/pages/ValuationLab.tsx`: data-driven U.S. segment labels and review messaging.
- `SYSTEM_ARCHITECTURE.md` and `README.md`: Microsoft route, reproduction command, known data limitations.

## Task 1: Add safe SIC routing and policy configuration

**Files:**
- Modify: `backend/app/us_valuation/config/archetypes.json`
- Modify: `backend/app/us_valuation/classification.py`
- Test: `backend/tests/test_us_valuation.py`

**Interfaces:**
- Consumes: `classify_issuer(submissions, config=None) -> dict[str, Any]`.
- Produces: classification dictionaries with `primary_archetype == "enterprise_software_cloud"` and `requires_segment_forecast: bool`.

- [ ] **Step 1: Write the failing classification test**

```python
def test_microsoft_sic_routes_to_enterprise_software_cloud() -> None:
    submission = {
        "cik": "789019",
        "tickers": ["MSFT"],
        "name": "MICROSOFT CORP",
        "sic": "7372",
        "sicDescription": "Services-Prepackaged Software",
        "filings": {"recent": {"accessionNumber": [], "form": []}},
    }
    result = classify_issuer(submission)
    assert result["primary_archetype"] == "enterprise_software_cloud"
    assert result["requires_segment_forecast"] is True
    assert result["valuation_policy"]["primary_model"] == "fcff_dcf"
```

- [ ] **Step 2: Run the test and confirm it fails because SIC 7372 has no policy**

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k microsoft_sic_routes`

Expected: `ValueError: No supported U.S. valuation archetype for SEC SIC 7372`.

- [ ] **Step 3: Add the smallest configuration and classification change**

Add this SIC mapping and policy fields, preserving the existing Apple policy:

```json
{
  "start": 7372,
  "end": 7372,
  "sector": "Technology",
  "archetype": "enterprise_software_cloud",
  "confidence": 0.9
}
```

```json
"enterprise_software_cloud": {
  "primary_model": "fcff_dcf",
  "supporting_models": ["epv"],
  "forecast_years": 8,
  "archetype_median_growth": 0.07,
  "archetype_target_operating_margin": 0.35,
  "growth_persistence": 0.78,
  "margin_persistence": 0.78,
  "sales_to_capital": 3.0,
  "unlevered_policy_beta": 0.9,
  "target_debt_weight": 0.05,
  "default_debt_spread": 0.01,
  "terminal_roic_premium": 0.05,
  "normal_company_overlay": 0.0
}
```

In `classify_issuer`, return `requires_segment_forecast` from a CIK override, defaulting to `False`. Add the Microsoft override with `requires_segment_forecast: true`; it must not replace the base SIC route.

- [ ] **Step 4: Run focused tests and then the U.S. test module**

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k microsoft_sic_routes`

Expected: PASS.

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py`

Expected: PASS with Apple regression tests unchanged.

- [ ] **Step 5: Commit only the routing task files**

```bash
git add backend/app/us_valuation/config/archetypes.json backend/app/us_valuation/classification.py backend/tests/test_us_valuation.py
git commit -m "feat: route Microsoft to software cloud archetype"
```

## Task 2: Add the reusable segment-operating-income forecast path

**Files:**
- Modify: `backend/app/us_valuation/config/issuer_forecasts.json`
- Modify: `backend/app/us_valuation/assumptions.py`
- Modify: `backend/app/us_valuation/models.py`
- Modify: `backend/app/us_valuation/pipeline.py`
- Test: `backend/tests/test_us_valuation.py`

**Interfaces:**
- Consumes: issuer evidence with `forecast_mode: "segment_operating_income"` and three segment entries.
- Produces: `assumptions["segment_forecast"]` with mode, segments, reconciliation states, `starting_operating_margin`, and `target_operating_margin`.
- Produces: FCFF schedule rows whose `segments` contain revenue, revenue growth, operating margin, operating income, and no raw filing table data.

- [ ] **Step 1: Write failing assumptions and model tests**

```python
def test_segment_operating_income_evidence_reconciles_to_consolidated_ttm() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
    )
    segment = result["assumptions"]["segment_forecast"]
    assert segment["mode"] == "segment_operating_income"
    assert segment["reconciliation"]["segment_revenue_to_consolidated"] == "pass"
    assert segment["reconciliation"]["segment_operating_income_to_consolidated"] == "pass"


def test_segment_operating_income_dcf_schedule_contains_segment_ebit() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
    )
    first_year = result["models"]["fcff_dcf"]["detail"]["forecast_schedule"][0]
    assert first_year["segments"]["intelligent_cloud"]["operating_income"] > 0
    assert first_year["ebit"] == pytest.approx(
        sum(row["operating_income"] for row in first_year["segments"].values())
    )
```

- [ ] **Step 2: Run the new tests and confirm they fail because Microsoft evidence and the new mode do not exist**

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k segment_operating_income`

Expected: FAIL because the Microsoft fixture/evidence or forecast mode is absent.

- [ ] **Step 3: Add Microsoft governed filing evidence**

Add a CIK `0000789019` record to `issuer_forecasts.json` with:

```json
{
  "forecast_mode": "segment_operating_income",
  "forecast_policy_version": "MSFT-ENTERPRISE-CLOUD-1.0",
  "forecast_years": 8,
  "growth_persistence": 0.8,
  "margin_persistence": 0.8,
  "terminal_roic_premium": 0.05,
  "evidence_status": "governed_filing_table_transcription",
  "growth_weights": {
    "recent_ytd": 0.4,
    "company_history": 0.4,
    "archetype_anchor": 0.2
  }
}
```

Include the three disclosed segments, the three latest annual periods, latest and comparable prior-year YTD values, segment operating-income values, consolidated reconciliation totals, and dated source metadata for the controlling 10-K and 10-Q. This plan is amended to the intentional direct `segment_operating_income` approach: publicly disclosed cost of revenue and operating expenses are not separate model inputs because reported segment operating income is the governed margin driver and separately projecting those lines would double-count economics without a governed allocation policy. Each governed value must have one exact private field-provenance path with source accession(s), fiscal period, duration, unit, table line, status, and derivation; no provenance values may enter public artifacts.

- [ ] **Step 4: Implement segment-operating-income evidence normalization**

In `derive_forecast_assumptions`, branch on `forecast_mode == "segment_operating_income"`. For each segment:

```python
segment_growth = min(max(
    weights["recent_ytd"] * recent_ytd_growth
    + weights["company_history"] * annual_cagr
    + weights["archetype_anchor"] * archetype_growth_anchor,
    -0.10,
), 0.20)
starting_margin = ttm_operating_income / ttm_revenue
target_margin = median([*annual_operating_margins, starting_margin])
```

Reject evidence if growth weights do not sum to one, archetype weight exceeds 0.25, segment revenue does not reconcile to consolidated TTM revenue within 0.1%, or segment operating income does not reconcile to consolidated TTM operating income within 0.1%.

In `fcff_dcf`, branch by `segment_forecast["mode"]`. For `segment_operating_income`, project each segment revenue and operating margin, calculate `segment_operating_income`, sum it to consolidated EBIT, and calculate FCFF using the existing tax, ROIC, reinvestment, terminal-value, and enterprise-to-equity bridge code.

In `_forecast_quality_review`, use `classification["requires_segment_forecast"]` and preserve a review warning when evidence is not `automated_filing_extraction`.

- [ ] **Step 5: Run focused tests and Apple regression tests**

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k segment_operating_income`

Expected: PASS.

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k 'apple or segment_operating_income'`

Expected: PASS; Apple remains `segment_gross_profit`.

- [ ] **Step 6: Commit only the forecast-path task files**

```bash
git add backend/app/us_valuation/config/issuer_forecasts.json backend/app/us_valuation/assumptions.py backend/app/us_valuation/models.py backend/app/us_valuation/pipeline.py backend/tests/test_us_valuation.py
git commit -m "feat: add segment operating income forecast route"
```

## Task 3: Build shared private/public valuation artifacts and Microsoft SEC fixture

**Files:**
- Create: `backend/app/us_valuation/artifacts.py`
- Create: `scripts/build_us_valuation_pipeline.py`
- Modify: `scripts/build_apple_us_valuation_pipeline.py`
- Create: `backend/tests/fixtures/us/msft-submissions.json`
- Create: `backend/tests/fixtures/us/msft-companyfacts.json`
- Test: `backend/tests/test_us_valuation.py`

**Interfaces:**
- Produces: `public_result(result, submissions) -> dict[str, Any]` with no raw statement values.
- Produces: `frontend_company(result, public, issuer_metadata) -> dict[str, Any]` for a ticker-specific frontend record.
- Produces: `build_issuer_artifacts(cik, ticker, short_name, subsector, output_root, valuation_date, refresh) -> dict[str, Path]`.

- [ ] **Step 1: Write failing artifact and safety tests**

```python
def test_microsoft_public_artifact_contains_no_raw_financial_amounts() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
    )
    public = public_result(result, load_fixture("msft-submissions.json"))
    serialized = json.dumps(public)
    assert public["ticker"] == "MSFT"
    assert public["data_boundary"]["stock_prices_used"] is False
    assert "revenue_ttm" not in serialized
    assert "cash_and_nonoperating_investments" not in serialized
```

- [ ] **Step 2: Run the test and confirm it fails because shared artifact functions do not exist**

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k microsoft_public_artifact`

Expected: FAIL with an import error for `app.us_valuation.artifacts`.

- [ ] **Step 3: Extract artifact functions without changing output shape**

Move `public_result`, public model conversion, source-manifest handling, and `frontend_company` logic out of the Apple script into `artifacts.py`. Parameterize ticker, short name, subsector, color, insight, source label, and valuation note. Use a generic `segment_assumptions` schema:

```python
{
    key: {
        "label": segment["label"],
        "initial_revenue_growth": segment["initial_revenue_growth"],
        "target_operating_margin": segment.get("target_operating_margin"),
        "target_gross_margin": segment.get("target_gross_margin"),
    }
}
```

Keep Apple’s artifact fields backward-compatible. Add a generic builder script that fetches SEC data, writes private audit JSON, public frontend JSON, backend public JSON, a generated JavaScript module, and minimized SEC fixtures. Turn the Apple script into a thin caller of the generic builder or preserve it as a wrapper with identical output locations.

- [ ] **Step 4: Generate and inspect Microsoft artifacts**

Run: `SEC_USER_AGENT='FinSight contact@example.com' PYTHONPATH=backend python3 scripts/build_us_valuation_pipeline.py --cik 0000789019 --ticker MSFT --short-name Microsoft --subsector 'Enterprise software & cloud' --valuation-date 2026-08-01 --refresh`

Expected: private audit output under `output/us-testing/msft/`, public-safe output under `frontend/public/data/` and `backend/app/data/us_valuations/`, generated frontend module, plus minimized SEC fixtures.

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k 'microsoft_public_artifact or apple'`

Expected: PASS.

- [ ] **Step 5: Commit only artifact builder files and generated Microsoft artifacts**

```bash
git add backend/app/us_valuation/artifacts.py scripts/build_us_valuation_pipeline.py scripts/build_apple_us_valuation_pipeline.py backend/tests/fixtures/us/msft-submissions.json backend/tests/fixtures/us/msft-companyfacts.json backend/tests/test_us_valuation.py frontend/public/data/microsoft-valuation-pipeline.json frontend/src/research/generated/microsoft-valuation.js backend/app/data/us_valuations/MSFT.json
git commit -m "feat: generate Microsoft valuation artifacts"
```

## Task 4: Integrate Microsoft in the Valuation interface

**Files:**
- Modify: `frontend/src/research/data.js`
- Modify: `frontend/src/research/data.d.ts`
- Modify: `frontend/src/research/pages/ValuationLab.tsx`
- Modify: `frontend/src/research/engine.test.js`
- Test: `frontend/src/research/engine.test.js`

**Interfaces:**
- Consumes: generated Apple and Microsoft public frontend modules with common `valuation.us.public_assumptions.segment_assumptions`.
- Produces: a Microsoft company route and a U.S. valuation panel that derives labels and descriptive copy from the company artifact.

- [ ] **Step 1: Write the failing frontend test**

```javascript
it('exposes Microsoft as a U.S. filing-only valuation company', () => {
  const microsoft = findCompany('MSFT')
  expect(microsoft.valuation.us.ticker).toBe('MSFT')
  expect(microsoft.valuation.us.public_assumptions.forecast_mode)
    .toBe('segment_operating_income')
  expect(microsoft.valuation.us.review.publication_state)
    .toMatch(/pass|review|required|withheld/)
})
```

- [ ] **Step 2: Run the frontend test and confirm it fails because MSFT is absent**

Run: `npm test -- --run frontend/src/research/engine.test.js`

Expected: FAIL because `findCompany('MSFT')` returns no company.

- [ ] **Step 3: Register Microsoft and remove Apple-specific U.S. panel text**

Import the Microsoft generated module into the data registry. Extend the U.S. data type with optional `segment_assumptions` values for both operating and gross-margin routes. In `ValuationLab.tsx`, derive the U.S. panel title, segment cards, and descriptive copy from `forecast_mode` and the artifact labels:

```tsx
const segmentEntries = Object.entries(
  company.valuation.us.public_assumptions.segment_assumptions ?? {},
)
const isOperatingIncomeRoute =
  company.valuation.us.public_assumptions.forecast_mode === 'segment_operating_income'
```

Show “Preliminary valuation - requires data review” for `review_required`; do not show a per-share intrinsic value if the publication state is `withheld`.

- [ ] **Step 4: Run frontend tests and production build**

Run: `npm test -- --run`

Expected: PASS.

Run: `npm run build`

Expected: exit code 0.

- [ ] **Step 5: Commit only UI registration and tests**

```bash
git add frontend/src/research/data.js frontend/src/research/data.d.ts frontend/src/research/pages/ValuationLab.tsx frontend/src/research/engine.test.js
git commit -m "feat: show Microsoft valuation in FinSight"
```

## Task 5: Document and verify release readiness

**Files:**
- Modify: `SYSTEM_ARCHITECTURE.md`
- Modify: `README.md`
- Test: `backend/tests/test_us_valuation.py`, `backend/tests`, `frontend` test suite and build.

**Interfaces:**
- Consumes: verified Microsoft private/public artifacts and test outputs.
- Produces: documented reproduction command, mapping and publication status.

- [ ] **Step 1: Write a documentation presence test or checklist assertion**

```python
def test_microsoft_artifact_preserves_provenance_and_no_price_input() -> None:
    artifact = json.loads(Path("backend/app/data/us_valuations/MSFT.json").read_text())
    assert artifact["source_financial_statement"]["accession"]
    assert artifact["data_boundary"]["stock_prices_used"] is False
    assert artifact["review"]["publication_state"] in {"pass", "review_required", "withheld"}
```

- [ ] **Step 2: Run the test and confirm the artifact is present and valid**

Run: `PYTHONPATH=backend pytest -q backend/tests/test_us_valuation.py -k microsoft_artifact_preserves`

Expected: PASS after Task 3 artifacts are generated.

- [ ] **Step 3: Document Microsoft in the architecture and README**

Add Microsoft’s SIC 7372 route, `enterprise_software_cloud` policy, `segment_operating_income` mode, evidence status, source boundaries, and publication state to `SYSTEM_ARCHITECTURE.md`. Add a reproducible command to `README.md`:

```bash
SEC_USER_AGENT='FinSight contact@example.com' PYTHONPATH=backend python3 scripts/build_us_valuation_pipeline.py --cik 0000789019 --ticker MSFT --short-name Microsoft --subsector 'Enterprise software & cloud' --valuation-date 2026-08-01
```

- [ ] **Step 4: Run the complete verification suite**

Run: `PYTHONPATH=backend pytest -q backend/tests`

Expected: all backend tests pass.

Run: `npm test -- --run`

Expected: all frontend tests pass.

Run: `npm run build`

Expected: exit code 0.

Run: `python3 -m compileall -q backend scripts`

Expected: exit code 0.

Run: `git diff --check`

Expected: no whitespace errors.

Run a public-artifact scan that fails if `microsoft-valuation-pipeline.json` or `MSFT.json` includes source-PDF text, raw statement table keys, current price, upside/downside, or buy/hold/sell labels.

- [ ] **Step 5: Commit documentation and verified release artifacts**

```bash
git add SYSTEM_ARCHITECTURE.md README.md backend/tests/test_us_valuation.py
git commit -m "docs: document Microsoft valuation pipeline"
```

## Plan self-review

- Spec coverage: Tasks 1-2 cover routing, policy, source evidence, segment forecast, quality gate, and model execution. Task 3 covers SEC retrieval, provenance, private/public outputs, and fixtures. Task 4 covers controlled UI publication. Task 5 covers documentation, full regression checks, and public-artifact safety.
- Placeholder scan: no placeholder implementation steps are used; all required interfaces, source files, expected test failures, and verification commands are named.
- Type consistency: `requires_segment_forecast`, `segment_operating_income`, `public_result`, `frontend_company`, and `build_issuer_artifacts` use the same names throughout the plan.
