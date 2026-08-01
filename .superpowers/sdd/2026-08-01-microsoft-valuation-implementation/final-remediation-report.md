# Microsoft valuation final remediation report

## Finding-to-fix mapping

| Review finding | Exact remediation | Regression evidence |
| --- | --- | --- |
| Withheld results could expose post-model values | `public_result` now centrally scrubs model, scenario, range, and future sensitivity outputs whenever the overall review is `withheld`; segment-required issuers without a registry entry return withheld before model execution. | `test_withheld_public_artifact_scrubs_post_model_values`; `test_segment_required_issuer_without_registry_evidence_fails_before_models`; `test_low_confidence_post_model_withholding_scrubs_public_values`; `test_model_validation_failure_uses_withheld_vocabulary` |
| Unsupported publication states | U.S. model, scenario, review, artifact, generated frontend record, adapter, type, and documentation use only `pass`, `review_required`, and `withheld`. Invalid model inputs map to `withheld`; warnings map to `review_required`. | `test_us_publication_state_uses_only_binding_vocabulary`; frontend publication-presentation test |
| MSFT segment provenance incomplete | The private MSFT registry now contains a governed field-source map with accession, SEC URL, filing date, period, FY/FP, duration, unit, table line, status, and derivation. The documented operating-income design intentionally uses reported segment operating income directly rather than separately forecasting cost and opex. | `test_microsoft_governed_segment_fields_have_complete_private_provenance` |
| Stale bridge zeroes / silent finance leases | Policy zeroes require both a matching normalized period and a source accession in the controlling TTM filing. Finance leases are explicit bridge fields and require a current governed-zero record or reported fact. An incomplete bridge returns a withheld result before model execution. | `test_stale_verified_zero_cannot_clear_current_bridge` |
| Dated rebuild was not as-of / reproducible | `valuation_date` filters submission rows and every Companyfacts candidate by filing date. The documented build replays `backend/tests/fixtures/us/private_captures/msft-2026-08-01/`, a minimized controlled source capture. | `test_valuation_date_excludes_later_filed_facts` |
| Generic anchor exceeded 25% | Common generic growth weighting is now 37.5% TTM history, 37.5% annual history, and 25% archetype anchor. | `test_generic_growth_anchor_is_capped_when_company_history_exists` |
| Apple-specific reason on MSFT route | Policy reasons are archetype-owned and used by both normal and withheld paths. | `test_microsoft_model_policy_reason_comes_from_software_archetype` |

## Commands and results

- `PYTHONPATH=backend pytest -q backend/tests` — passed (84 tests; one unrelated Python deprecation warning).
- `cd frontend && npm test` — passed (20 tests).
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

## Re-review addendum

| Re-review finding | Additional remediation | Regression evidence |
| --- | --- | --- |
| Stored API artifact could bypass the generation scrub | `sanitize_public_artifact` is the shared state-aware public validator/sanitizer used by both `public_result` and `load_generated_result`. Unsupported overall/model/scenario states become `withheld` and all public values are scrubbed. | `test_api_loader_scrubs_adversarial_withheld_stored_artifact`; `test_api_loader_fails_closed_for_legacy_publication_state` |
| Frontend adapter accepted legacy state values | `normalizeUsPublicationArtifact` runs at adapter entry and converts legacy/unknown state to a null-valued `withheld` result before calculating any display value. The stale architecture Apple wording now says `review_required`. | `legacy and unknown U.S. publication states fail closed at the adapter boundary` |
| Grouped MSFT provenance did not reach private audit | `field_provenance` now maps every one of the 41 governed paths exactly once to a structured provenance context. The assumptions layer validates coverage and source references, resolves the full field-level map into the private result, and public serialization omits it. TTM contexts include both FY2024 10-K and FY2025 Q3 10-Q accessions. The design and plan formally document the intentional direct-operating-income scope. | `test_microsoft_governed_segment_fields_have_complete_private_provenance` |
| Bridge accepted a same-period stale annual accession | Bridge-zero validation now selects only source accessions with report end equal to the normalized TTM end and requires a review date on/before the valuation cutoff. | `test_same_period_stale_annual_zero_accession_cannot_clear_bridge` |

## Post-remediation final-review addendum

| Final-review finding | Additional remediation | Regression evidence |
| --- | --- | --- |
| Six TTM segment values contradicted declared derivations | Corrected each segment revenue and operating-income TTM input to `FY2024 + FY2025 Q3 YTD - FY2024 Q3 YTD`. Exact field source values now cover every governed path; validation rejects any source-value mismatch, recomputes each TTM derivation, and validates consolidated totals. | `test_microsoft_governed_segment_fields_have_complete_private_provenance`; `test_segment_provenance_rejects_compensating_ttm_allocation_error` |
| Any same-end source could authorize bridge zeroes | The normalizer now receives cutoff-filtered submissions and derives one latest controlling filing for the normalized period. Governed zeros must match that exact accession, period, and cutoff-valid review date. | `test_same_period_noncontrolling_accession_cannot_clear_bridge` |
| Verification counts were stale | Counts are refreshed after the final full verification below. | Full-suite record below |

Final verification: `84` backend tests and `20` frontend tests passed; frontend production build, Python compilation, public-data safety scan, and staged/unstaged whitespace checks passed. MSFT remains `withheld` with null public model, scenario, and range values.
