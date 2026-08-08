# U.S. Valuation V2 Core Design

## Status and approval

This design narrows the approved recommendations in `docs/US-VALUATION-METHODOLOGY-REBUILD-RESEARCH.md` into the first deployable core revision. The user approved implementation on 2026-08-08 by requesting that the recommendations be applied to the U.S. valuation pipeline.

## Objective

Make the current U.S. valuation pipeline fail closed when a company is not eligible for its configured model, and correct the FCFF reinvestment and terminal-return mechanics that can create economically inconsistent cash flows.

## Scope

This revision will:

1. Keep archetypes as routing priors.
2. Add an explicit model-eligibility boundary.
3. Permit residual income only for governed financial archetypes, DDM only for utilities, FFO only for REITs, and FCFF only for governed operating archetypes.
4. Stop substituting residual income or DDM when an FCFF bridge is incomplete.
5. Return a transparent withheld FCFF result listing the missing bridge fields.
6. Remove the 95% reinvestment-rate ceiling so investment-heavy growth can produce negative FCFF.
7. Remove the `WACC + 3%` initial marginal-ROIC floor.
8. Fade terminal marginal ROIC to WACC unless a future, separately governed durable-moat evidence contract is implemented.
9. Keep scenario and sensitivity calculations internally consistent when WACC changes.

This revision will not pretend to complete company-specific bank, insurer, REIT, utility, commodity, relative-value, analyst-estimate, or historical-backtest modules. Those require separate specs and evidence sources.

## Architecture

`eligibility.py` will own the pure model/archetype eligibility rules. `pipeline.py` will ask that boundary whether the configured primary model is eligible and will fail closed when the answer is no. An incomplete FCFF bridge will remain FCFF and become withheld; it will never silently change economic model.

`assumptions.py` will derive marginal returns from operating economics without a WACC-based floor and will set terminal marginal ROIC to WACC under the competitive-fade policy. `models.py` will allow reinvestment rates above 100%, reject non-positive marginal ROIC when positive growth is forecast, and keep WACC scenarios aligned with terminal ROIC.

## Data flow

```text
SEC submissions + Companyfacts
    -> archetype classification (routing prior)
    -> explicit model eligibility
    -> normalized company financials
    -> bridge completeness gate
    -> company forecast assumptions
    -> eligible valuation model
    -> pass / review_required / withheld artifact
```

## Failure behavior

- Ineligible archetype/model pair: withheld with an eligibility error.
- Incomplete FCFF bridge: withheld as FCFF with exact missing fields.
- Positive forecast growth with non-positive marginal ROIC: withheld.
- No generic RI/DDM fallback is permitted.
- Existing public-artifact scrubbing remains fail closed.

## Test strategy

Tests must prove the prior unsafe behavior fails before implementation and passes afterward:

- An operating company with an incomplete bridge remains `fcff_dcf` and is withheld.
- A nonfinancial archetype cannot use residual income or DDM.
- A governed financial/utility/REIT archetype remains eligible for its intended model.
- High-growth/low-ROIC FCFF can have reinvestment above 100% and negative explicit-period FCFF.
- Generic initial marginal ROIC is not floored at WACC plus 3%.
- Terminal marginal ROIC equals WACC in base, scenario, and WACC-sensitivity calculations.

## Acceptance criteria

- Focused U.S. valuation tests pass.
- The full backend test suite passes or any unrelated pre-existing failure is documented with evidence.
- Generated valuation code no longer references or invokes the generic FCFF-to-equity fallback.
- Existing uncommitted user work outside the touched files is preserved.

