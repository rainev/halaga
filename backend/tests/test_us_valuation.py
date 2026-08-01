"""Golden and control tests for the Apple-first U.S. valuation lane."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.routers.us_valuations import load_generated_result
from app.us_valuation.assumptions import (
    US_BASE,
    build_discount_rate,
    derive_forecast_assumptions,
    load_issuer_forecast_evidence,
)
from app.us_valuation.classification import classify_issuer
from app.us_valuation.artifacts import (
    frontend_company,
    public_result,
    sec_cache_manifest,
)
import app.us_valuation.pipeline as valuation_pipeline
from app.us_valuation.pipeline import build_us_valuation
from app.us_valuation.sec_client import SecClient
from app.us_valuation.xbrl import CompanyFactsNormalizer


FIXTURES = Path(__file__).parent / "fixtures" / "us"
MICROSOFT_PUBLIC_ARTIFACTS = (
    Path("backend/app/data/us_valuations/MSFT.json"),
    Path("frontend/public/data/microsoft-valuation-pipeline.json"),
)


def reported_statement_amounts(financials: dict[str, Any]) -> set[int | float]:
    """Collect only non-zero reported source-fact amounts, not derived metadata."""
    amounts: set[int | float] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            amount = value.get("value")
            if (
                value.get("value_status") == "reported"
                and isinstance(amount, (int, float))
                and not isinstance(amount, bool)
                and amount != 0
            ):
                amounts.add(amount)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(financials)
    return amounts


def is_permitted_public_numeric_path(path: tuple[str, ...]) -> bool:
    """Allow only the public contract's governed rates and derived outputs."""
    public_assumption_fields = {
        "forecast_years",
        "initial_revenue_growth",
        "target_operating_margin",
        "sales_to_capital",
        "terminal_growth",
        "policy_wacc",
        "risk_free_rate",
        "equity_risk_premium",
    }
    if path[:1] == ("public_assumptions",):
        return (
            len(path) == 2 and path[1] in public_assumption_fields
        ) or (
            len(path) == 4
            and path[1] == "segment_assumptions"
            and path[3]
            in {
                "initial_revenue_growth",
                "target_operating_margin",
                "target_gross_margin",
            }
        )
    return (
        len(path) == 3
        and path[0] == "models"
        and path[2] == "intrinsic_value_per_share"
    ) or (
        len(path) == 4
        and path[0] == "scenarios"
        and path[2:] == ("fcff_dcf", "intrinsic_value_per_share")
    ) or (
        path[:1] == ("scenario_range",)
        and path[1:] in {("low",), ("base",), ("high",)}
    )


def assert_public_artifact_is_safe(
    public: dict[str, Any], raw_statement_amounts: set[int | float]
) -> None:
    """Reject private statement fields and their numeric values in public DTOs."""
    private_fields = {
        "financials",
        "financial_period_end",
        "revenue",
        "revenue_ttm",
        "operating_income",
        "cash",
        "debt",
        "shares",
        "cash_and_nonoperating_investments",
        "annual",
        "quarterly",
        "current_ytd",
        "prior_ytd",
        "sources",
        "values",
        "source_manifest",
        "forecast_assumptions",
        "discount_rate",
        "source_pdf",
        "source_pdf_text",
        "raw_statement_table",
        "current_price",
        "historical_price",
        "stock_price",
        "price",
        "upside_pct",
        "upside_downside",
        "buy_hold_sell",
        "recommendation",
    }
    forbidden_recommendations = {"buy", "hold", "sell", "buy/hold/sell"}
    source_pdf_markers = {
        "consolidated statements of income",
        "consolidated statements of operations",
        "three months ended",
        "nine months ended",
    }

    def visit(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            if set(value) == {
                "current_price",
                "upside_downside",
                "buy_hold_sell",
                "trading_multiples",
            }:
                assert value == {
                    "current_price": False,
                    "upside_downside": False,
                    "buy_hold_sell": False,
                    "trading_multiples": False,
                }
                return
            assert not (private_fields & value.keys())
            for key, child in value.items():
                visit(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            assert value not in raw_statement_amounts or is_permitted_public_numeric_path(path), (
                "Public artifact contains a raw financial-statement numeric value"
            )
        elif isinstance(value, str):
            normalized = value.lower()
            assert normalized not in forbidden_recommendations
            assert not any(marker in normalized for marker in source_pdf_markers)

    visit(public)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def microsoft_source_manifest() -> dict:
    return {
        "status": "fixture_capture",
        "fixtures": {
            name: load_fixture(name)["capture_metadata"]
            for name in ("msft-submissions.json", "msft-companyfacts.json")
        },
    }


def microsoft_financials_and_policy() -> tuple[dict, dict, dict]:
    submission = load_fixture("msft-submissions.json")
    classification = classify_issuer(submission)
    financials = CompanyFactsNormalizer(
        load_fixture("msft-companyfacts.json"),
        fiscal_year_end=submission["fiscalYearEnd"],
    ).normalize(
        annual_count=5,
        verified_zero_bridge_fields=classification["verified_zero_bridge_fields"],
    )
    discount_rate = build_discount_rate(
        policy=classification["valuation_policy"],
        tax_rate=financials["normalized"]["tax_rate"],
    )
    return financials, classification["valuation_policy"], discount_rate


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


def test_microsoft_public_artifact_contains_no_raw_financial_amounts() -> None:
    """Catch public payloads that expose private SEC statement inputs or values."""
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
    )

    public = public_result(result, load_fixture("msft-submissions.json"))
    assert public["ticker"] == "MSFT"
    assert public["source_financial_statement"] == {
        "form": "10-Q",
        "period_end": "2025-03-31",
        "filed_date": "2025-04-30",
        "accession": "0000950170-25-061046",
        "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025061046/msft-20250331.htm",
        "note": "Latest financial statement used; this does not claim to be the issuer's latest disclosure of every type.",
    }
    assert public["data_boundary"]["stock_prices_used"] is False
    assert set(public) == {
        "schema_version",
        "valuation_date",
        "market",
        "currency",
        "ticker",
        "issuer",
        "source_financial_statement",
        "model_policy",
        "public_assumptions",
        "models",
        "scenarios",
        "scenario_range",
        "forecast_quality",
        "review",
        "methodology",
        "data_boundary",
    }

    raw_statement_amounts = reported_statement_amounts(result["financials"])
    assert_public_artifact_is_safe(public, raw_statement_amounts)

    # Governed assumptions and derived values may be numeric. A raw statement
    # amount must still be rejected even when hidden under an otherwise allowed
    # nested key.
    permitted = deepcopy(public)
    permitted["forecast_quality"]["derived_indicator"] = public[
        "public_assumptions"
    ]["policy_wacc"]
    assert_public_artifact_is_safe(permitted, raw_statement_amounts)

    leaked = deepcopy(permitted)
    leaked["forecast_quality"]["derived_indicator"] = result["financials"][
        "annual"
    ][-1]["sources"]["revenue"]["value"]
    with pytest.raises(AssertionError, match="raw financial-statement numeric"):
        assert_public_artifact_is_safe(leaked, raw_statement_amounts)


def test_microsoft_artifact_preserves_provenance_and_no_price_input() -> None:
    """Keep the checked-in MSFT artifact attributable and price-free."""
    artifact = json.loads(
        Path("backend/app/data/us_valuations/MSFT.json").read_text(encoding="utf-8")
    )
    assert artifact["source_financial_statement"]["accession"]
    assert artifact["data_boundary"]["stock_prices_used"] is False
    assert artifact["review"]["publication_state"] in {
        "pass",
        "review_required",
        "withheld",
    }


def test_public_artifact_allows_governed_rates_and_derived_value_paths() -> None:
    """Allow high-level public values even when their numbers occur privately."""
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
    )
    public = public_result(result, load_fixture("msft-submissions.json"))
    permitted = deepcopy(public)
    permitted["public_assumptions"]["policy_wacc"] = result["financials"][
        "normalized"
    ]["tax_rate"]
    permitted["models"]["fcff_dcf"]["intrinsic_value_per_share"] = result[
        "financials"
    ]["annual"][-1]["sources"]["revenue"]["value"]
    permitted["forecast_quality"]["metadata"] = {
        "normalized_tax_rate": result["financials"]["normalized"]["tax_rate"],
        "zero": 0,
        "fiscal_year": result["financials"]["annual"][-1]["fiscal_year"],
        "fiscal_quarter": 3,
    }

    assert_public_artifact_is_safe(
        permitted, reported_statement_amounts(result["financials"])
    )


def test_checked_in_microsoft_public_artifacts_exclude_prohibited_content() -> None:
    """Scan 2026 artifacts against the same-period minimized private source map."""
    source_map = load_fixture("msft-2026-public-safety-source-map.json")
    raw_statement_amounts = set(source_map["reported_statement_amounts"])
    assert 331_839_000_000.0 in raw_statement_amounts

    for path in MICROSOFT_PUBLIC_ARTIFACTS:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        assert artifact["source_financial_statement"] == source_map[
            "source_financial_statement"
        ]
        assert artifact["data_boundary"]["stock_prices_used"] is False
        assert artifact["data_boundary"]["raw_financial_statement_values_included"] is False
        assert_public_artifact_is_safe(artifact, raw_statement_amounts)

        leaked = deepcopy(artifact)
        leaked["forecast_quality"]["checks"]["segment_evidence_as_of"][
            "available_periods"
        ][0] = 331_839_000_000.0
        with pytest.raises(AssertionError, match="raw financial-statement numeric"):
            assert_public_artifact_is_safe(leaked, raw_statement_amounts)


def test_sec_refresh_cache_replay_preserves_bytes_hash_and_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch metadata hashes recorded for response bytes not written to cache."""
    payloads = {
        "https://data.sec.gov/submissions/CIK0000789019.json": json.dumps(
            load_fixture("msft-submissions.json"), indent=2
        ).encode("utf-8"),
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json": json.dumps(
            load_fixture("msft-companyfacts.json"), indent=2
        ).encode("utf-8"),
    }

    class Response:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self.body

    def fake_urlopen(request: Any, *, timeout: int) -> Response:
        return Response(payloads[request.full_url])

    monkeypatch.setattr("app.us_valuation.sec_client.urlopen", fake_urlopen)
    captured_client = SecClient(
        user_agent="FinSight contact@example.com",
        cache_dir=tmp_path,
        requests_per_second=5,
    )
    captured_client.submissions("0000789019", refresh=True)
    captured_client.companyfacts("0000789019", refresh=True)
    captured_manifest = sec_cache_manifest(tmp_path, "0000789019")

    replay_client = SecClient(user_agent=None, cache_dir=tmp_path)
    replay_client.submissions("0000789019")
    replay_client.companyfacts("0000789019")

    assert sec_cache_manifest(tmp_path, "0000789019") == captured_manifest


def test_apple_frontend_artifact_retains_form_in_source_label(result: dict) -> None:
    """Catch a generic source label that loses Apple's existing filing wording."""
    public = public_result(result, load_fixture("aapl-submissions.json"))
    frontend = frontend_company(
        result,
        public,
        {
            "ticker": "AAPL",
            "short_name": "Apple",
            "subsector": "Hardware & electronic equipment",
            "insight": "Apple filing-only valuation.",
        },
    )

    assert frontend["source"]["label"] == (
        "Latest financial statement used: Apple Form 10-Q for 2026-03-28, "
        "filed 2026-05-01"
    )


def test_segment_operating_income_evidence_reconciles_to_consolidated_ttm() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
        source_manifest=microsoft_source_manifest(),
    )
    segment = result["forecast_assumptions"]["segment_forecast"]
    assert segment["mode"] == "segment_operating_income"
    assert segment["reconciliation"]["segment_revenue_to_consolidated"] == "pass"
    assert (
        segment["reconciliation"]["segment_operating_income_to_consolidated"]
        == "pass"
    )
    assert result["forecast_quality"]["status"] == "review_required"
    assert result["source_manifest"]["fixtures"]["msft-companyfacts.json"][
        "sha256"
    ]


def test_segment_operating_income_dcf_schedule_contains_segment_ebit() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        valuation_date="2026-08-01",
        source_manifest=microsoft_source_manifest(),
    )
    first_year = result["models"]["fcff_dcf"]["detail"]["forecast_schedule"][0]
    assert first_year["segments"]["intelligent_cloud"]["operating_income"] > 0
    assert first_year["ebit"] == pytest.approx(
        sum(row["operating_income"] for row in first_year["segments"].values())
    )


def test_segment_operating_income_governance_rejects_invalid_evidence() -> None:
    financials, policy, discount_rate = microsoft_financials_and_policy()
    original = load_issuer_forecast_evidence("0000789019")
    assert original is not None
    period = financials["ttm"]["period_end"]

    invalid_cases = [
        ("growth_weights", {"recent_ytd": 0.5, "company_history": 0.4, "archetype_anchor": 0.2}, "sum to 1.0"),
        ("growth_weights", {"recent_ytd": 0.4, "company_history": 0.3, "archetype_anchor": 0.3}, "25% policy limit"),
        ("consolidated_ttm", {"revenue": 1, "operating_income": 122_130_000_000}, "revenue"),
        ("consolidated_ttm", {"revenue": 270_010_000_000, "operating_income": 1}, "operating income"),
    ]
    for field, value, error in invalid_cases:
        evidence = deepcopy(original)
        evidence["periods"][period][field] = value
        with pytest.raises(ValueError, match=error):
            derive_forecast_assumptions(
                financials,
                policy=policy,
                discount_rate=discount_rate,
                issuer_evidence=evidence,
            )

    for field, value, error in (
        ("ttm_revenue", 1, "Segment revenue"),
        ("ttm_operating_income", 1, "Segment operating income"),
    ):
        evidence = deepcopy(original)
        evidence["periods"][period]["segments"]["intelligent_cloud"][field] = value
        with pytest.raises(ValueError, match=error):
            derive_forecast_assumptions(
                financials,
                policy=policy,
                discount_rate=discount_rate,
                issuer_evidence=evidence,
            )


def test_segment_operating_income_without_contemporaneous_evidence_is_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = load_issuer_forecast_evidence("0000789019")
    assert evidence is not None
    evidence = deepcopy(evidence)
    evidence["periods"] = {}
    monkeypatch.setattr(
        valuation_pipeline,
        "load_issuer_forecast_evidence",
        lambda _cik: evidence,
    )

    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        source_manifest=microsoft_source_manifest(),
    )

    assert result["review"]["publication_state"] == "withheld"
    assert result["models"]["fcff_dcf"]["intrinsic_value_per_share"] is None
    assert result["models"]["epv"]["intrinsic_value_per_share"] is None
    assert result["forecast_quality"]["checks"]["segment_evidence_as_of"]["status"] == "fail"
    assert "hardware/services" not in result["model_policy"]["reason"].lower()


def test_withheld_segment_forecast_public_mode_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a withheld segment route mislabeled as a consolidated forecast."""
    evidence = deepcopy(load_issuer_forecast_evidence("0000789019"))
    assert evidence is not None
    evidence["periods"] = {}
    monkeypatch.setattr(
        valuation_pipeline,
        "load_issuer_forecast_evidence",
        lambda _cik: evidence,
    )

    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
    )
    public = public_result(result, load_fixture("msft-submissions.json"))

    assert result["review"]["publication_state"] == "withheld"
    assert public["public_assumptions"]["forecast_mode"] == "unavailable"


def test_segment_operating_income_future_dated_source_is_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = load_issuer_forecast_evidence("0000789019")
    assert evidence is not None
    evidence = deepcopy(evidence)
    period = "2025-03-31"
    evidence["periods"][period]["sources"].append(
        {
            "form": "10-K",
            "accession": "0000950170-25-100235",
            "filing_date": "2025-07-30",
            "period_end": "2025-06-30",
            "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm",
            "evidence": "Deliberately future-dated source for a governance test.",
        }
    )
    monkeypatch.setattr(
        valuation_pipeline,
        "load_issuer_forecast_evidence",
        lambda _cik: evidence,
    )

    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        source_manifest=microsoft_source_manifest(),
    )

    assert result["review"]["publication_state"] == "withheld"
    assert result["models"]["fcff_dcf"]["intrinsic_value_per_share"] is None
    assert result["models"]["epv"]["intrinsic_value_per_share"] is None
    assert result["forecast_quality"]["checks"]["segment_evidence_as_of"]["status"] == "fail"


def test_segment_operating_income_outputs_only_derived_values() -> None:
    result = build_us_valuation(
        submissions=load_fixture("msft-submissions.json"),
        companyfacts=load_fixture("msft-companyfacts.json"),
        source_manifest=microsoft_source_manifest(),
    )
    assumptions = result["forecast_assumptions"]
    segment = assumptions["segment_forecast"]
    assert "segment_target_operating_margin" in assumptions["maintained_assumptions"]
    assert all(
        key not in assumptions["maintained_assumptions"]
        for key in (
            "segment_target_gross_margin",
            "target_operating_expense_ratio",
        )
    )
    for row in segment["segments"].values():
        assert not any(key.startswith("annual_") or "ytd" in key for key in row)
    for row in result["models"]["fcff_dcf"]["detail"]["forecast_schedule"]:
        for segment_row in row["segments"].values():
            assert set(segment_row) == {
                "revenue_growth",
                "revenue",
                "operating_margin",
                "operating_income",
            }


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
