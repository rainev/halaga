"""Fail-closed model eligibility for U.S. valuation routing."""

from __future__ import annotations

from typing import Any


_GOVERNED_MODELS = {
    "hardware_electronic_equipment": "fcff_dcf",
    "enterprise_software_cloud": "fcff_dcf",
    "semiconductors_and_components": "fcff_dcf",
    "medical_devices_instruments": "fcff_dcf",
    "diversified_industrials": "fcff_dcf",
    "pharmaceuticals": "fcff_dcf",
    "specialty_chemicals": "fcff_dcf",
    "consumer_staples": "fcff_dcf",
    "internet_digital_services": "fcff_dcf",
    "us_bank": "residual_income",
    "us_utility": "ddm",
    "capital_goods_machinery": "fcff_dcf",
    "retail": "fcff_dcf",
    "transportation": "fcff_dcf",
    "telecom": "fcff_dcf",
    "us_insurance": "residual_income",
    "us_securities": "residual_income",
    "us_credit": "residual_income",
    "us_reit": "ffo",
}


def model_eligibility(classification: dict[str, Any]) -> dict[str, Any]:
    """Return whether the classified issuer may use its configured primary model."""
    if not isinstance(classification, dict):
        return {
            "eligible": False,
            "model": "unknown",
            "reason": "Classification must be a mapping with a governed archetype.",
        }
    raw_archetype = classification.get("primary_archetype")
    policy = classification.get("valuation_policy")
    raw_model = policy.get("primary_model") if isinstance(policy, dict) else None
    archetype = raw_archetype if isinstance(raw_archetype, str) else ""
    model = raw_model if isinstance(raw_model, str) and raw_model else "unknown"
    expected_model = _GOVERNED_MODELS.get(archetype)
    if expected_model is None:
        return {
            "eligible": False,
            "model": model,
            "reason": (
                f"{archetype or 'unknown'} is not a governed U.S. valuation archetype; "
                f"{model} is ineligible."
            ),
        }
    if model == expected_model:
        return {
            "eligible": True,
            "model": model,
            "reason": f"{archetype} is eligible for {model}.",
        }
    return {
        "eligible": False,
        "model": model,
        "reason": (
            f"{archetype} is not eligible for {model}; "
            f"expected {expected_model}."
        ),
    }
