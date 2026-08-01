# Microsoft valuation final remediation report

## Finding-to-fix mapping

| Review finding | Exact remediation | Regression evidence |
| --- | --- | --- |
| Withheld results could expose post-model values | `public_result` now centrally scrubs model, scenario, range, and future sensitivity outputs whenever the overall review is `withheld`; segment-required issuers without a registry entry return withheld before model execution. | `test_withheld_public_artifact_scrubs_post_model_values`; `test_segment_required_issuer_without_registry_evidence_fails_before_models` |
| Unsupported publication states | U.S. model, scenario, review, artifact, generated frontend record, adapter, type, and documentation use only `pass`, `review_required`, and `withheld`. Invalid model inputs map to `withheld`; warnings map to `review_required`. | `test_us_publication_state_uses_only_binding_vocabulary`; frontend publication-presentation test |
| MSFT segment provenance incomplete | The private MSFT registry now contains a governed field-source map with accession, SEC URL, filing date, period, FY/FP, duration, unit, table line, status, and derivation. The documented operating-income design intentionally uses reported segment operating income directly rather than separately forecasting cost and opex. | `test_microsoft_governed_segment_fields_have_complete_private_provenance` |
| Stale bridge zeroes / silent finance leases | Policy zeroes require both a matching normalized period and a source accession in the controlling TTM filing. Finance leases are explicit bridge fields and require a current governed-zero record or reported fact. An incomplete bridge returns a withheld result before model execution. | `test_stale_verified_zero_cannot_clear_current_bridge` |
| Dated rebuild was not as-of / reproducible | `valuation_date` filters submission rows and every Companyfacts candidate by filing date. The documented build replays `backend/tests/fixtures/us/private_captures/msft-2026-08-01/`, a minimized controlled source capture. | `test_valuation_date_excludes_later_filed_facts` |
| Generic anchor exceeded 25% | Common generic growth weighting is now 37.5% TTM history, 37.5% annual history, and 25% archetype anchor. | `test_generic_growth_anchor_is_capped_when_company_history_exists` |
| Apple-specific reason on MSFT route | Policy reasons are archetype-owned and used by both normal and withheld paths. | `test_microsoft_model_policy_reason_comes_from_software_archetype` |

## Commands and results

- `PYTHONPATH=backend pytest -q backend/tests` — passed (77 tests; one unrelated Python deprecation warning).
- `cd frontend && npm test` — passed (19 tests).
- `cd frontend && npm run build` — passed.
- `PYTHONPATH=backend python3 -m compileall -q backend` — passed.
- `git diff --check && git diff --cached --check` — passed.
- Raw-value scan over backend public, frontend public, and generated artifacts — passed.
- `PYTHONPATH=backend python3 scripts/build_us_valuation_pipeline.py --cik 0000789019 --ticker MSFT --short-name Microsoft --subsector 'Enterprise software & cloud' --valuation-date 2026-08-01` — regenerated MSFT public/API/frontend artifacts from the controlled private fixture.
- The same command with an empty temporary `--output-root` replayed the controlled fixture without creating a SEC cache and produced a withheld/null MSFT artifact.

Apple’s golden backend route and the BDO frontend route both remain covered by the passing full suites.

## Current MSFT release state

MSFT remains `withheld`. The controlled 2026 normalized period does not have current governed segment evidence or current bridge-zero confirmation, so no intrinsic value, scenario value, range, or sensitivity is publicly released. The private source capture is not included in frontend public assets.

### Capture trade-off

The release fixture contains public SEC facts, but keeps only issuer identity and
the concepts required by the normalizer (rather than the original multi-megabyte
SEC responses). It is tracked for deterministic auditability and deliberately
located under backend test fixtures, never under frontend public or generated
frontend assets. If this repository is distributed publicly, the underlying
facts are already public SEC disclosures; nevertheless, release governance
should continue to review the fixture because it is a controlled source input.
