"""Golden and control tests for the Apple-first U.S. valuation lane."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.routers.us_valuations import load_generated_result
from app.us_valuation.assumptions import US_BASE
from app.us_valuation.classification import classify_issuer
from app.us_valuation.pipeline import build_us_valuation
from app.us_valuation.sec_client import SecClient
from app.us_valuation.xbrl import CompanyFactsNormalizer


FIXTURES = Path(__file__).parent / "fixtures" / "us"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="module")
def submissions() -> dict:
    return json.loads((FIXTURES / "aapl-submissions.json").read_text())


@pytest.fixture(scope="module")
def companyfacts() -> dict:
    return json.loads((FIXTURES / "aapl-companyfacts.json").read_text())


@pytest.fixture(scope="module")
def result(submissions: dict, companyfacts: dict) -> dict:
    return build_us_valuation(
        submissions=submissions,
        companyfacts=companyfacts,
        valuation_date="2026-07-31",
    )


def test_apple_classification_and_model_route(result: dict, submissions: dict):
    assert result["issuer"]["ticker"] == "AAPL"
    assert result["issuer"]["primary_archetype"] == "hardware_electronic_equipment"
    assert result["model_policy"]["primary"] == "fcff_dcf"
    assert result["model_policy"]["supporting"] == ["epv"]
    assert result["model_policy"]["blend_models"] is False
    assert classify_issuer(submissions)["requires_segment_forecast"] is False


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


def test_segment_operating_income_evidence_reconciles_to_consolidated_ttm() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
    )
    segment = result["forecast_assumptions"]["segment_forecast"]
    assert segment["mode"] == "segment_operating_income"
    assert segment["reconciliation"]["segment_revenue_to_consolidated"] == "pass"
    assert (
        segment["reconciliation"]["segment_operating_income_to_consolidated"]
        == "pass"
    )


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


def test_complete_override_routes_without_matching_sic() -> None:
    config = {
        "version": "test",
        "sic_ranges": [],
        "issuer_overrides": {
            "0000123456": {
                "ticker": "TEST",
                "sector": "Test sector",
                "archetype": "test_archetype",
                "confidence": 1.0,
                "reason": "Complete issuer override for a controlled test.",
            }
        },
        "valuation_policies": {"test_archetype": {"primary_model": "fcff_dcf"}},
    }
    submission = {
        "cik": "123456",
        "tickers": ["TEST"],
        "name": "TEST CORP",
        "sic": "9999",
        "filings": {"recent": {"accessionNumber": [], "form": []}},
    }

    result = classify_issuer(submission, config)

    assert result["finsight_sector"] == "Test sector"
    assert result["primary_archetype"] == "test_archetype"


def test_partial_override_without_matching_sic_is_rejected() -> None:
    config = {
        "version": "test",
        "sic_ranges": [],
        "issuer_overrides": {"0000123456": {"requires_segment_forecast": True}},
        "valuation_policies": {},
    }
    submission = {
        "cik": "123456",
        "sic": "9999",
        "filings": {"recent": {"accessionNumber": [], "form": []}},
    }

    with pytest.raises(
        ValueError,
        match="Incomplete issuer override for CIK 0000123456 without a SIC route",
    ):
        classify_issuer(submission, config)


def test_apple_ttm_reconciliation_and_history(result: dict):
    ttm = result["financials"]["ttm"]
    assert ttm["period_end"] == "2026-03-28"
    assert ttm["method"] == "latest_fy_plus_current_ytd_minus_prior_ytd"
    assert ttm["values"]["revenue"] == pytest.approx(451_442_000_000)
    assert ttm["values"]["operating_income"] == pytest.approx(147_366_000_000)
    assert ttm["values"]["capital_expenditures"] == pytest.approx(11_048_000_000)
    assert len(result["financials"]["annual"]) == 5
    assert len(result["financials"]["quarterly"]["revenue"]) == 8


def test_quarter_reconstruction_is_consecutive_and_reconciles_fy2025(result: dict):
    quarters = result["financials"]["quarterly"]["revenue"]
    indexes = [
        row["fiscal_year"] * 4 + row["fiscal_quarter"] - 1
        for row in quarters
    ]
    assert indexes == list(range(indexes[0], indexes[0] + 8))
    fy2025 = [
        row["value"] for row in quarters if row["fiscal_year"] == 2025
    ]
    assert sum(fy2025) == pytest.approx(416_161_000_000)


def test_q1_bridge_does_not_fall_back_to_stale_fy(
    submissions: dict,
    companyfacts: dict,
):
    cutoff = "2026-01-30"
    pruned = deepcopy(companyfacts)
    for namespace in pruned["facts"].values():
        for concept in namespace.values():
            for unit, facts in concept.get("units", {}).items():
                concept["units"][unit] = [
                    fact for fact in facts if fact.get("filed", "") <= cutoff
                ]
    normalized = CompanyFactsNormalizer(
        pruned,
        fiscal_year_end=submissions["fiscalYearEnd"],
    ).normalize(
        annual_count=5,
        verified_zero_bridge_fields={
            "preferred_equity",
            "noncontrolling_interests",
        },
    )
    assert normalized["ttm"]["period_end"] == "2025-12-27"
    assert normalized["ttm"]["values"]["revenue"] == pytest.approx(
        416_161_000_000 + 143_756_000_000 - 124_300_000_000
    )


def test_discount_rate_is_explicitly_policy_calibrated(result: dict):
    rate = result["discount_rate"]
    assert rate["calibration_type"] == "policy_calibrated"
    assert rate["market_observed"] is False
    assert rate["market_assumptions"]["risk_free_rate"] == 0.0468
    assert rate["market_assumptions"]["equity_risk_premium"] == 0.045
    assert rate["wacc"] == pytest.approx(0.0911806438)


def test_terminal_state_is_continuous(result: dict):
    final_year = result["models"]["fcff_dcf"]["detail"]["forecast_schedule"][-1]
    assumptions = result["forecast_assumptions"]
    assert final_year["revenue_growth"] == pytest.approx(
        assumptions["terminal_growth"]
    )
    assert final_year["operating_margin"] == pytest.approx(
        assumptions["target_operating_margin"]
    )
    assert final_year["marginal_roic"] == pytest.approx(
        assumptions["terminal_marginal_roic"]
    )


def test_apple_golden_values_and_scenario_order(result: dict):
    assert result["models"]["fcff_dcf"]["intrinsic_value_per_share"] == pytest.approx(
        137.8839487,
        abs=0.001,
    )
    assert result["models"]["epv"]["intrinsic_value_per_share"] == pytest.approx(
        91.3648524,
        abs=0.001,
    )
    scenario_range = result["scenario_range"]
    assert scenario_range["low"] < scenario_range["base"] < scenario_range["high"]


def test_sensitivities_move_in_the_expected_direction(result: dict):
    rows = {
        (row["field"], row["delta"]): row["intrinsic_value_per_share"]
        for row in result["sensitivities"]
    }
    base = result["scenario_range"]["base"]
    assert rows[("wacc", -0.01)] > base > rows[("wacc", 0.01)]
    assert (
        rows[("terminal_growth", -0.005)]
        < base
        < rows[("terminal_growth", 0.005)]
    )
    assert (
        rows[("initial_revenue_growth", -0.02)]
        < base
        < rows[("initial_revenue_growth", 0.02)]
    )
    assert (
        rows[("target_operating_margin", -0.02)]
        < base
        < rows[("target_operating_margin", 0.02)]
    )


def test_identity_mismatch_is_blocked(submissions: dict, companyfacts: dict):
    mismatched = deepcopy(companyfacts)
    mismatched["cik"] = 1234567
    with pytest.raises(ValueError, match="CIK values do not match"):
        build_us_valuation(
            submissions=submissions,
            companyfacts=mismatched,
        )


def test_public_api_artifact_excludes_raw_financials():
    public = load_generated_result("AAPL")
    assert public["data_boundary"]["raw_financial_statement_values_included"] is False
    assert "financials" not in public
    assert "discount_rate" not in public
    assert "forecast_assumptions" not in public
    assert public["models"]["fcff_dcf"]["intrinsic_value_per_share"] == pytest.approx(
        137.8839487,
        abs=0.001,
    )


def test_apple_uses_segment_aware_ten_year_forecast(result: dict):
    assumptions = result["forecast_assumptions"]
    segments = assumptions["segment_forecast"]["segments"]
    assert assumptions["forecast_policy_version"] == "AAPL-HARDWARE-SERVICES-1.0"
    assert assumptions["forecast_years"] == 10
    assert segments["services"]["initial_revenue_growth"] > segments["products"][
        "initial_revenue_growth"
    ]
    assert segments["products"]["evidence"]["growth_weights"][
        "archetype_anchor"
    ] == pytest.approx(0.20)
    assert assumptions["segment_forecast"]["reconciliation"] == {
        "segment_revenue_to_consolidated": "pass",
        "gross_profit_less_opex_to_operating_income": "pass",
    }
    assert result["forecast_quality"]["status"] == "review_required"
    assert result["forecast_quality"]["errors"] == []


def test_cached_sec_json_does_not_require_user_agent(tmp_path: Path):
    cached = tmp_path / "CIK0000320193-submissions.json"
    cached.write_text('{"cik":"0000320193"}')
    client = SecClient(user_agent=None, cache_dir=tmp_path)
    assert client.submissions("320193")["cik"] == "0000320193"
    metadata = json.loads(
        (tmp_path / "CIK0000320193-submissions.json.meta.json").read_text()
    )
    assert metadata["sha256"]
    assert metadata["provenance_status"] == "existing_cache_hashed_on_replay"


def test_cached_sec_json_rejects_hash_mismatch(tmp_path: Path):
    cached = tmp_path / "CIK0000320193-submissions.json"
    cached.write_text('{"cik":"0000320193"}')
    client = SecClient(user_agent=None, cache_dir=tmp_path)
    client.submissions("320193")
    cached.write_text('{"cik":"0000320194"}')
    with pytest.raises(RuntimeError, match="cache hash mismatch"):
        client.submissions("320193")


def test_amended_filing_supersedes_original_context():
    original = (
        "us-gaap",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "USD",
        {
            "start": "2025-01-01",
            "end": "2025-12-31",
            "form": "10-K",
            "filed": "2026-02-01",
            "accn": "original",
            "val": 100,
        },
    )
    amendment = (
        "us-gaap",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "USD",
        {
            "start": "2025-01-01",
            "end": "2025-12-31",
            "form": "10-K/A",
            "filed": "2026-03-01",
            "accn": "amendment",
            "val": 110,
        },
    )
    selected = CompanyFactsNormalizer._select_latest_duplicate(
        [original, amendment]
    )
    assert len(selected) == 1
    assert selected[0][3]["accn"] == "amendment"


def test_fiscal_year_label_uses_declared_fiscal_year_end(companyfacts: dict):
    normalizer = CompanyFactsNormalizer(
        companyfacts,
        fiscal_year_end="0531",
    )
    assert normalizer._fiscal_year_for_start("2024-06-01") == 2025
    assert normalizer._fiscal_year_for_start("2025-01-01") == 2025


def test_assumption_source_is_dated():
    assert US_BASE.risk_free_effective_date == "2026-07-30"
    assert US_BASE.erp_effective_date == "2026-07-01"
