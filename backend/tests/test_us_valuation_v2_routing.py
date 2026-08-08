"""Routing-safety tests for the U.S. valuation V2 lane."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

import app.us_valuation.pipeline as valuation_pipeline
from app.us_valuation.eligibility import model_eligibility


FIXTURES = Path(__file__).parent / "fixtures" / "us"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def classification_for(archetype: str, model: str) -> dict:
    return {
        "primary_archetype": archetype,
        "valuation_policy": {"primary_model": model},
    }


@pytest.mark.parametrize(
    ("archetype", "model", "expected"),
    [
        ("us_bank", "residual_income", True),
        ("us_utility", "ddm", True),
        ("us_reit", "ffo", True),
        ("enterprise_software_cloud", "fcff_dcf", True),
        ("enterprise_software_cloud", "residual_income", False),
        ("enterprise_software_cloud", "ddm", False),
    ],
)
def test_model_eligibility_matches_archetype_model_pair(
    archetype: str, model: str, expected: bool
) -> None:
    result = model_eligibility(classification_for(archetype, model))

    assert result["eligible"] is expected
    assert result["model"] == model
    assert result["reason"]


@pytest.mark.parametrize(
    "classification",
    [
        classification_for("unknown_archetype", "fcff_dcf"),
        {"valuation_policy": {"primary_model": "fcff_dcf"}},
        classification_for(["enterprise_software_cloud"], "fcff_dcf"),
    ],
)
def test_model_eligibility_rejects_unknown_missing_and_malformed_archetypes(
    classification: dict,
) -> None:
    result = model_eligibility(classification)

    assert result["eligible"] is False
    assert result["reason"]


def test_ineligible_model_pair_returns_withheld_artifact(monkeypatch) -> None:
    submissions = load_fixture("msft-submissions.json")
    classification = {
        **valuation_pipeline.classify_issuer(submissions),
        "valuation_policy": {
            **valuation_pipeline.classify_issuer(submissions)["valuation_policy"],
            "primary_model": "residual_income",
        },
    }
    monkeypatch.setattr(valuation_pipeline, "classify_issuer", lambda _: classification)

    result = valuation_pipeline.build_us_valuation(
        submissions=submissions,
        companyfacts={"cik": submissions["cik"]},
        valuation_date="2026-08-01",
    )

    assert result["model_policy"]["primary"] == "residual_income"
    assert result["models"]["residual_income"]["intrinsic_value_per_share"] is None
    assert result["models"]["residual_income"]["publication_state"] == "withheld"
    assert result["review"]["publication_state"] == "withheld"
    assert "eligibility" in " ".join(result["review"]["errors"]).lower()


def test_incomplete_fcff_bridge_is_withheld_without_model_fallback(monkeypatch) -> None:
    submissions = load_fixture("msft-submissions.json")
    companyfacts = {
        "cik": submissions["cik"],
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "end": "2025-06-30",
                                "val": 100_000_000,
                            }
                        ]
                    }
                },
                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            {"end": "2025-06-30", "val": 1_000_000_000}
                        ]
                    }
                },
                "CommonStockSharesOutstanding": {
                    "units": {"shares": [{"end": "2025-06-30", "val": 100_000_000}]}
                },
            }
        },
    }
    normalized = {
        "normalized": {"tax_rate": 0.21},
        "balance_sheet": {
            "bridge_complete": False,
            "bridge_missing_fields": [
                "preferred_equity",
                "noncontrolling_interests",
            ],
        },
        "ttm": {"period_end": "2025-06-30"},
    }
    monkeypatch.setattr(
        valuation_pipeline.CompanyFactsNormalizer,
        "normalize",
        lambda self, **kwargs: deepcopy(normalized),
    )

    result = valuation_pipeline.build_us_valuation(
        submissions=submissions,
        companyfacts=companyfacts,
        valuation_date="2026-08-01",
    )

    assert result["model_policy"]["primary"] == "fcff_dcf"
    assert result["review"]["publication_state"] == "withheld"
    assert result["models"]["fcff_dcf"]["intrinsic_value_per_share"] is None
    errors = " ".join(result["review"]["errors"])
    assert "preferred_equity" in errors
    assert "noncontrolling_interests" in errors
