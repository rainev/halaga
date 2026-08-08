# U.S. Valuation V2 Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make U.S. valuation model selection fail closed and correct FCFF reinvestment and terminal-ROIC mechanics.

**Architecture:** A pure eligibility module governs archetype/model compatibility before valuation. FCFF bridge failure remains an unavailable FCFF result instead of switching models. Forecast assumptions and DCF calculations use economically derived marginal returns, uncapped reinvestment, and competitive terminal ROIC convergence.

**Tech Stack:** Python 3.11, pytest 8.3.4, SEC Companyfacts fixtures, JSON valuation policies.

## Global Constraints

- Preserve SEC ingestion, provenance, artifact safety, and all unrelated user changes.
- Archetypes are routing priors; they do not justify an economically unrelated fallback.
- No FCFF-to-residual-income or FCFF-to-DDM substitution is allowed.
- Missing material bridge data must produce `withheld`, never a fabricated zero.
- Terminal marginal ROIC equals WACC until a separately governed durable-moat evidence contract exists.
- Reinvestment rates may exceed 100%; explicit-period FCFF may be negative.
- Production changes follow a demonstrated RED-GREEN test cycle.

---

### Task 1: Model eligibility and fail-closed routing

**Files:**
- Create: `backend/app/us_valuation/eligibility.py`
- Modify: `backend/app/us_valuation/pipeline.py`
- Modify: `backend/app/us_valuation/equity_models.py`
- Create: `backend/tests/test_us_valuation_v2_routing.py`

**Interfaces:**
- Consumes: classification dictionaries containing `primary_archetype` and `valuation_policy.primary_model`; normalized balance sheets containing `bridge_complete` and `bridge_missing_fields`.
- Produces: `model_eligibility(classification: dict) -> dict` with `eligible: bool`, `model: str`, and `reason: str`; a withheld FCFF artifact when the bridge is incomplete.

- [ ] **Step 1: Write failing eligibility tests**

Add literal table-driven tests proving `us_bank/residual_income`, `us_utility/ddm`, `us_reit/ffo`, and an operating archetype/`fcff_dcf` are eligible, while operating archetype/residual-income and operating archetype/DDM pairs are not.

- [ ] **Step 2: Write a failing pipeline regression test**

Use a real reduced SEC fixture or a narrowly patched normalizer result to prove an FCFF-classified operating company with `bridge_complete=False` currently changes model. Assert the required behavior: primary model remains `fcff_dcf`, publication state is `withheld`, intrinsic value is absent, and the error names each missing bridge field.

- [ ] **Step 3: Run the routing tests and verify RED**

Run:

```bash
cd backend && python3 -m pytest tests/test_us_valuation_v2_routing.py -q
```

Expected: failures caused by the missing eligibility module and current fallback behavior.

- [ ] **Step 4: Implement the eligibility boundary**

Create a pure eligibility map for the governed financial, utility, REIT, and operating archetypes. Reject incompatible primary-model pairs with a deterministic reason.

- [ ] **Step 5: Remove generic fallback routing**

Remove the fallback import and invocation from `pipeline.py`. Reuse or generalize the existing withheld-result constructor so incomplete FCFF bridge results preserve the FCFF model identity and list the missing fields. Remove dead fallback constants/functions from `equity_models.py` when no callers remain.

- [ ] **Step 6: Run focused routing tests and verify GREEN**

Run:

```bash
cd backend && python3 -m pytest tests/test_us_valuation_v2_routing.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Run existing valuation tests**

Run:

```bash
cd backend && python3 -m pytest tests/test_us_valuation.py tests/test_automated_review.py -q
```

Expected: all tests pass after updating only assertions that intentionally described the removed fallback behavior.

### Task 2: FCFF reinvestment and competitive terminal economics

**Files:**
- Modify: `backend/app/us_valuation/assumptions.py`
- Modify: `backend/app/us_valuation/models.py`
- Create: `backend/tests/test_us_valuation_v2_fcff.py`

**Interfaces:**
- Consumes: forecast assumptions produced by `derive_forecast_assumptions`; discount dictionaries containing `wacc`; normalized FCFF financials.
- Produces: forecast assumptions with `terminal_roic_basis="competitive_fade_to_wacc"`; FCFF schedules that permit reinvestment rates above 1.0 and negative FCFF.

- [ ] **Step 1: Write failing FCFF behavior tests**

Construct hand-checked FCFF inputs proving that positive high growth with low positive marginal ROIC requires reinvestment above 100% and produces negative explicit-period FCFF. Add a validation test proving positive growth with non-positive initial marginal ROIC is withheld.

- [ ] **Step 2: Write failing assumption tests**

Use a minimal normalized financial fixture to assert initial marginal ROIC equals `target_margin * (1-tax_rate) * sales_to_capital` without a WACC floor, and terminal marginal ROIC equals WACC with basis `competitive_fade_to_wacc`.

- [ ] **Step 3: Write failing scenario-consistency tests**

Assert bear/base/bull scenario terminal marginal ROIC follows each scenario WACC. Assert one-way WACC sensitivities also update terminal marginal ROIC under the competitive-fade policy.

- [ ] **Step 4: Run FCFF tests and verify RED**

Run:

```bash
cd backend && python3 -m pytest tests/test_us_valuation_v2_fcff.py -q
```

Expected: failures caused by the 95% cap, WACC-plus initial floor, terminal premium, and inconsistent one-way WACC sensitivity.

- [ ] **Step 5: Implement minimal FCFF corrections**

Remove the 95% reinvestment cap. Validate non-positive initial marginal ROIC when positive growth is forecast. Derive generic initial marginal ROIC without a WACC floor. Set terminal marginal ROIC to WACC and record the competitive-fade basis. Make scenario and one-way WACC changes update terminal marginal ROIC consistently.

- [ ] **Step 6: Run focused FCFF tests and verify GREEN**

Run:

```bash
cd backend && python3 -m pytest tests/test_us_valuation_v2_fcff.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Run the complete U.S. valuation test set**

Run:

```bash
cd backend && python3 -m pytest tests/test_us_valuation.py tests/test_automated_review.py tests/test_us_valuation_v2_routing.py tests/test_us_valuation_v2_fcff.py -q
```

Expected: all tests pass. Update golden intrinsic values only after manually checking the changed calculation trace and scenario ordering.

### Task 3: Integration audit and artifact impact report

**Files:**
- Modify only if required by verified integration failures: `backend/app/us_valuation/artifacts.py`, `scripts/build_us_valuation_pipeline.py`
- No generated valuation artifacts are overwritten unless their source SEC fixture is present and replayable.

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: verified test output and a before/after model-routing impact count; no claim that withheld companies have been fully valued.

- [ ] **Step 1: Confirm fallback removal mechanically**

Run:

```bash
rg -n "build_fallback_valuation|fallback_from" backend/app/us_valuation backend/tests
```

Expected: no production fallback route remains; historical fixture assertions may remain only if clearly labelled legacy.

- [ ] **Step 2: Replay available controlled fixtures**

Run the Apple and Microsoft controlled valuation fixtures through the updated pipeline without refreshing network data. Record model, base value, scenario range, terminal-value share, and review state.

- [ ] **Step 3: Run the full backend suite**

Run:

```bash
cd backend && python3 -m pytest -q
```

Expected: zero failures.

- [ ] **Step 4: Run syntax validation**

Run:

```bash
python3 -m compileall -q backend/app/us_valuation scripts
```

Expected: exit code 0.

- [ ] **Step 5: Document remaining coverage limits**

Report the companies that would now be withheld because their FCFF bridge remains unresolved. Do not characterize those names as properly valued until company-specific bridge evidence or an eligible specialist model exists.

