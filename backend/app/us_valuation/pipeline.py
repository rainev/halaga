"""End-to-end U.S. filing normalization, routing, valuation, and publication gates."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from .assumptions import (
    ForecastEvidenceUnavailable,
    US_BASE,
    USMarketAssumptions,
    build_discount_rate,
    derive_forecast_assumptions,
    load_issuer_forecast_evidence,
)
from .classification import classify_issuer
from .models import (
    earnings_power_value,
    fcff_dcf,
    one_way_sensitivities,
    scenario_set,
)
from .xbrl import CompanyFactsNormalizer


def _forecast_quality_review(
    *,
    classification: dict[str, Any],
    assumptions: dict[str, Any],
    base: dict[str, Any],
    epv: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, dict[str, Any]] = {}
    segment_forecast = assumptions.get("segment_forecast")
    schedule = base.get("detail", {}).get("forecast_schedule", [])

    segment_required = bool(classification["requires_segment_forecast"])
    if segment_required and not segment_forecast:
        errors.append(
            "A material secondary business is classified but no segment forecast is available."
        )
    checks["segment_forecast_required"] = {
        "status": "pass" if not segment_required or segment_forecast else "fail",
        "value": segment_required,
    }

    if segment_forecast:
        reconciliations = segment_forecast["reconciliation"]
        reconciliation_passed = all(
            status == "pass" for status in reconciliations.values()
        )
        if not reconciliation_passed:
            errors.append("Segment evidence does not reconcile to consolidated facts.")
        checks["segment_reconciliation"] = {
            "status": "pass" if reconciliation_passed else "fail",
            "value": reconciliations,
        }
        max_archetype_weight = max(
            segment["evidence"]["growth_weights"]["archetype_anchor"]
            for segment in segment_forecast["segments"].values()
        )
        if max_archetype_weight > 0.25:
            errors.append("Archetype growth weight exceeds the 25% policy limit.")
        checks["archetype_growth_weight"] = {
            "status": "pass" if max_archetype_weight <= 0.25 else "fail",
            "value": max_archetype_weight,
            "limit": 0.25,
        }

    forecast_years = int(assumptions["forecast_years"])
    durable_horizon_passed = not segment_required or 7 <= forecast_years <= 10
    if not durable_horizon_passed:
        errors.append(
            "Durable multi-business issuers require a seven-to-ten-year fade horizon."
        )
    checks["forecast_horizon"] = {
        "status": "pass" if durable_horizon_passed else "fail",
        "value": forecast_years,
    }

    if schedule:
        last_year = schedule[-1]
        terminal_growth_landed = abs(
            float(last_year["revenue_growth"])
            - float(assumptions["terminal_growth"])
        ) < 1e-9
        if not terminal_growth_landed:
            errors.append("Forecast growth does not land on the terminal rate.")
        checks["terminal_growth_continuity"] = {
            "status": "pass" if terminal_growth_landed else "fail",
            "value": last_year["revenue_growth"],
            "target": assumptions["terminal_growth"],
        }
        revenue_cagr = (
            float(last_year["revenue"])
            / float(assumptions["starting_revenue"])
        ) ** (1 / forecast_years) - 1
        fcff_values = [float(row["fcff"]) for row in schedule]
        fcff_cagr = (
            (fcff_values[-1] / fcff_values[0]) ** (1 / (forecast_years - 1))
            - 1
            if len(fcff_values) > 1 and fcff_values[0] > 0
            else None
        )
        inconsistent_cash_flow = (
            fcff_cagr is not None
            and revenue_cagr > 0.03
            and fcff_cagr < revenue_cagr - 0.05
        )
        if inconsistent_cash_flow:
            warnings.append(
                "Revenue and FCFF growth tell materially different forecast stories."
            )
        checks["revenue_fcff_consistency"] = {
            "status": "review_required" if inconsistent_cash_flow else "pass",
            "revenue_cagr": revenue_cagr,
            "fcff_cagr": fcff_cagr,
        }

    base_value = base.get("intrinsic_value_per_share")
    epv_value = epv.get("intrinsic_value_per_share")
    dispersion = (
        abs(float(base_value) - float(epv_value)) / abs(float(base_value))
        if base_value not in {None, 0} and epv_value is not None
        else None
    )
    if dispersion is not None and dispersion > 0.40:
        warnings.append(
            "DCF and EPV differ by more than 40%; the growth thesis requires review."
        )
    checks["dcf_epv_dispersion"] = {
        "status": "review_required" if dispersion is not None and dispersion > 0.40 else "pass",
        "value": dispersion,
        "review_threshold": 0.40,
    }

    if assumptions.get("forecast_evidence_status") != "automated_filing_extraction":
        warnings.append(
            "Segment evidence is governed filing-table transcription; automated filing-specific inline-XBRL extraction is not yet implemented."
        )
        checks["segment_evidence_automation"] = {
            "status": "review_required",
            "value": assumptions.get("forecast_evidence_status"),
        }
    else:
        checks["segment_evidence_automation"] = {
            "status": "pass",
            "value": assumptions.get("forecast_evidence_status"),
        }

    return {
        "policy_version": "US-FORECAST-QUALITY-1.0",
        "status": "withheld" if errors else "review_required" if warnings else "pass",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def _publication_review(
    *,
    classification: dict[str, Any],
    financials: dict[str, Any],
    base: dict[str, Any],
    scenarios: dict[str, Any],
    forecast_quality: dict[str, Any],
) -> dict[str, Any]:
    errors = [
        *base.get("errors", []),
        *forecast_quality.get("errors", []),
    ]
    warnings = [
        *financials.get("warnings", []),
        *base.get("warnings", []),
        *forecast_quality.get("warnings", []),
    ]
    if classification["classification_confidence"] < 0.8:
        errors.append("Classification confidence is below the publication floor.")
    annual_count = len(financials["annual"])
    if annual_count < 3:
        errors.append("Fewer than three annual periods were normalized.")
    if annual_count < 5:
        warnings.append("Fewer than five annual periods limits cycle evidence.")
    scenario_values = [
        scenario["fcff_dcf"].get("intrinsic_value_per_share")
        for scenario in scenarios.values()
        if scenario["fcff_dcf"].get("intrinsic_value_per_share") is not None
    ]
    if len(scenario_values) != 3:
        errors.append("All three standard valuation scenarios must complete.")

    if errors:
        state = "withheld"
        grade = "insufficient"
    else:
        # Basic-share and narrow-NWC proxies deliberately prevent a high grade
        # until filing-specific dilution and broader accrual mapping are added.
        state = "review_required"
        grade = "medium"
    return {
        "publication_state": state,
        "confidence_grade": grade,
        "errors": errors,
        "warnings": list(dict.fromkeys(warnings)),
        "price_dependent_inputs_used": False,
        "prohibited_output_check": {
            "current_price": False,
            "upside_downside": False,
            "buy_hold_sell": False,
            "trading_multiples": False,
        },
    }


def _withheld_segment_evidence_result(
    *,
    classification: dict[str, Any],
    financials: dict[str, Any],
    discount_rate: dict[str, Any],
    valuation_date: str | None,
    source_manifest: dict[str, Any] | None,
    error: ForecastEvidenceUnavailable,
) -> dict[str, Any]:
    message = str(error)
    withheld_model = {
        "model": "fcff_dcf",
        "output_type": "intrinsic_value_per_share",
        "currency": "USD",
        "intrinsic_value_per_share": None,
        "publication_state": "withheld",
        "errors": [message],
        "warnings": [],
    }
    return {
        "schema_version": "US-VALUATION-RESULT-1.0",
        "valuation_date": valuation_date or date.today().isoformat(),
        "market": "US",
        "currency": "USD",
        "issuer": {
            key: classification[key]
            for key in (
                "cik",
                "ticker",
                "issuer_name",
                "filing_regime",
                "accounting_standard",
                "sec_sic_code",
                "sec_sic_label",
                "finsight_sector",
                "primary_archetype",
                "secondary_archetypes",
                "classification_confidence",
                "mapping_version",
                "override_applied",
                "classification_reason",
                "source_accessions",
            )
        },
        "financial_period_end": financials["ttm"]["period_end"],
        "source_manifest": source_manifest or {
            "status": "not_supplied",
            "note": "The caller did not attach SEC cache hashes to this run.",
        },
        "model_policy": {
            "primary": classification["valuation_policy"]["primary_model"],
            "supporting": classification["valuation_policy"]["supporting_models"],
            "blend_models": False,
            "reason": classification["valuation_policy"].get(
                "model_policy_reason",
                "FCFF is the primary governed model; EPV is a separate no-growth support value.",
            ),
        },
        "financials": financials,
        "forecast_assumptions": {
            "forecast_evidence_status": "unavailable_for_normalized_period",
            "segment_forecast": None,
        },
        "discount_rate": discount_rate,
        "models": {
            "fcff_dcf": withheld_model,
            "epv": {
                **withheld_model,
                "model": "epv",
            },
        },
        "scenarios": {},
        "scenario_range": {
            "low": None,
            "base": None,
            "high": None,
            "label": "assumption range, not a statistical confidence interval",
        },
        "sensitivities": [],
        "forecast_quality": {
            "policy_version": "US-FORECAST-QUALITY-1.0",
            "status": "withheld",
            "errors": [message],
            "warnings": [],
            "checks": {
                "segment_evidence_as_of": {
                    "status": "fail",
                    "normalized_period_end": error.period_end,
                    "available_periods": error.available_periods,
                }
            },
        },
        "review": {
            "publication_state": "withheld",
            "confidence_grade": "insufficient",
            "errors": [message],
            "warnings": [],
            "price_dependent_inputs_used": False,
            "prohibited_output_check": {
                "current_price": False,
                "upside_downside": False,
                "buy_hold_sell": False,
                "trading_multiples": False,
            },
        },
        "methodology": {
            "forecast_policy": "FINSIGHT_US_FORECAST_DISCOUNT_VALIDATION_POLICY.md",
            "sector_framework": "US_EQUITY_VALUATION_ENGINE_FRAMEWORK.md",
            "source_policy": "SEC Companyfacts, submissions and governed filing-specific Products/Services tables; no exchange prices",
        },
    }


def build_us_valuation(
    *,
    submissions: dict[str, Any],
    companyfacts: dict[str, Any],
    market_assumptions: USMarketAssumptions = US_BASE,
    valuation_date: str | None = None,
    source_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if valuation_date:
        cutoff_submissions = deepcopy(submissions)
        recent = cutoff_submissions.get("filings", {}).get("recent", {})
        filing_dates = recent.get("filingDate", [])
        allowed_indexes = [
            index for index, filed in enumerate(filing_dates) if filed <= valuation_date
        ]
        for key, values in list(recent.items()):
            if isinstance(values, list) and len(values) == len(filing_dates):
                recent[key] = [values[index] for index in allowed_indexes]
        submissions = cutoff_submissions
    classification = classify_issuer(submissions)
    if str(companyfacts.get("cik", "")).zfill(10) != classification["cik"]:
        raise ValueError("SEC submissions and Companyfacts CIK values do not match")
    financials = CompanyFactsNormalizer(
        companyfacts,
        fiscal_year_end=submissions.get("fiscalYearEnd"),
        as_of_date=valuation_date,
    ).normalize(
        annual_count=5,
        verified_zero_bridge_fields=classification[
            "verified_zero_bridge_fields"
        ],
    )
    policy = classification["valuation_policy"]
    discount_rate = build_discount_rate(
        policy=policy,
        tax_rate=financials["normalized"]["tax_rate"],
        market=market_assumptions,
    )
    if not financials["balance_sheet"]["bridge_complete"]:
        missing = ", ".join(financials["balance_sheet"]["bridge_missing_fields"])
        return _withheld_segment_evidence_result(
            classification=classification,
            financials=financials,
            discount_rate=discount_rate,
            valuation_date=valuation_date,
            source_manifest=source_manifest,
            error=ForecastEvidenceUnavailable(
                period_end=financials["ttm"]["period_end"],
                available_periods=[],
                reason=(
                    "Enterprise-to-equity bridge requires current filing evidence for "
                    + missing
                ),
            ),
        )
    issuer_evidence = load_issuer_forecast_evidence(classification["cik"])
    if classification["requires_segment_forecast"] and not issuer_evidence:
        return _withheld_segment_evidence_result(
            classification=classification,
            financials=financials,
            discount_rate=discount_rate,
            valuation_date=valuation_date,
            source_manifest=source_manifest,
            error=ForecastEvidenceUnavailable(
                period_end=financials["ttm"]["period_end"],
                available_periods=[],
                reason="A segment forecast is required but no governed issuer evidence is registered",
            ),
        )
    try:
        forecast_assumptions = derive_forecast_assumptions(
            financials,
            policy=policy,
            discount_rate=discount_rate,
            market=market_assumptions,
            issuer_evidence=issuer_evidence,
        )
    except ForecastEvidenceUnavailable as error:
        return _withheld_segment_evidence_result(
            classification=classification,
            financials=financials,
            discount_rate=discount_rate,
            valuation_date=valuation_date,
            source_manifest=source_manifest,
            error=error,
        )
    base = fcff_dcf(
        assumptions=forecast_assumptions,
        discount_rate=discount_rate,
        financials=financials,
    )
    epv = earnings_power_value(
        assumptions=forecast_assumptions,
        discount_rate=discount_rate,
        financials=financials,
    )
    scenarios = scenario_set(
        assumptions=forecast_assumptions,
        discount_rate=discount_rate,
        financials=financials,
    )
    sensitivities = one_way_sensitivities(
        assumptions=forecast_assumptions,
        discount_rate=discount_rate,
        financials=financials,
    )
    forecast_quality = _forecast_quality_review(
        classification=classification,
        assumptions=forecast_assumptions,
        base=base,
        epv=epv,
    )
    review = _publication_review(
        classification=classification,
        financials=financials,
        base=base,
        scenarios=scenarios,
        forecast_quality=forecast_quality,
    )
    scenario_values = [
        scenario["fcff_dcf"]["intrinsic_value_per_share"]
        for scenario in scenarios.values()
        if scenario["fcff_dcf"].get("intrinsic_value_per_share") is not None
    ]
    return {
        "schema_version": "US-VALUATION-RESULT-1.0",
        "valuation_date": valuation_date or date.today().isoformat(),
        "market": "US",
        "currency": "USD",
        "issuer": {
            key: classification[key]
            for key in (
                "cik",
                "ticker",
                "issuer_name",
                "filing_regime",
                "accounting_standard",
                "sec_sic_code",
                "sec_sic_label",
                "finsight_sector",
                "primary_archetype",
                "secondary_archetypes",
                "classification_confidence",
                "mapping_version",
                "override_applied",
                "classification_reason",
                "source_accessions",
            )
        },
        "financial_period_end": financials["ttm"]["period_end"],
        "source_manifest": source_manifest or {
            "status": "not_supplied",
            "note": "The caller did not attach SEC cache hashes to this run.",
        },
        "model_policy": {
            "primary": policy["primary_model"],
            "supporting": policy["supporting_models"],
            "blend_models": False,
            "reason": policy.get(
                "model_policy_reason",
                "FCFF is the primary governed model; EPV is a separate no-growth support value.",
            ),
        },
        "financials": financials,
        "forecast_assumptions": forecast_assumptions,
        "discount_rate": discount_rate,
        "models": {
            "fcff_dcf": base,
            "epv": epv,
        },
        "scenarios": scenarios,
        "scenario_range": {
            "low": min(scenario_values) if scenario_values else None,
            "base": base.get("intrinsic_value_per_share"),
            "high": max(scenario_values) if scenario_values else None,
            "label": "assumption range, not a statistical confidence interval",
        },
        "sensitivities": sensitivities,
        "forecast_quality": forecast_quality,
        "review": review,
        "methodology": {
            "forecast_policy": "FINSIGHT_US_FORECAST_DISCOUNT_VALIDATION_POLICY.md",
            "sector_framework": "US_EQUITY_VALUATION_ENGINE_FRAMEWORK.md",
            "source_policy": "SEC Companyfacts, submissions and governed filing-specific Products/Services tables; no exchange prices",
        },
    }
