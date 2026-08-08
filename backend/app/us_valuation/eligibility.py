"""Fail-closed model eligibility for U.S. valuation routing."""

from __future__ import annotations

from typing import Any


_EQUITY_LEVEL_MODELS = {
    "us_bank": "residual_income",
    "us_insurance": "residual_income",
    "us_securities": "residual_income",
    "us_credit": "residual_income",
    "us_utility": "ddm",
    "us_reit": "ffo",
}


def model_eligibility(classification: dict[str, Any]) -> dict[str, Any]:
    """Return whether the classified issuer may use its configured primary model."""
    archetype = str(classification.get("primary_archetype") or "")
    policy = classification.get("valuation_policy") or {}
    model = str(policy.get("primary_model") or "")
    expected_model = _EQUITY_LEVEL_MODELS.get(archetype, "fcff_dcf")
    if model == expected_model:
        return {
            "eligible": True,
            "model": model,
            "reason": f"{archetype or 'unknown'} is eligible for {model or 'unknown'}.",
        }
    return {
        "eligible": False,
        "model": model,
        "reason": (
            f"{archetype or 'unknown'} is not eligible for {model or 'unknown'}; "
            f"expected {expected_model}."
        ),
    }
