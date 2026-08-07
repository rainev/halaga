"""Equity-level valuation dispatch for archetypes FCFF cannot value.

Banks and regulated utilities are not enterprise-to-equity FCFF cases: for banks
deposits are operating funding (leverage IS the business), and utilities are
dividend/regulated. This module extracts the model-specific inputs from SEC
facts and runs the EXISTING models (``app.valuation.bank.residual_income_valuation``
for banks, ``app.valuation.ddm.two_stage_ddm`` for utilities), returning the same
result contract as the FCFF path so the pipeline/harvest/artifacts are unchanged.

Price-free (no ``current_price`` passed) and default ``review_required``.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.valuation.bank import residual_income_valuation
from app.valuation.ddm import two_stage_ddm

_ISSUER_KEYS = (
    "cik", "ticker", "issuer_name", "filing_regime", "accounting_standard",
    "sec_sic_code", "sec_sic_label", "finsight_sector", "primary_archetype",
    "secondary_archetypes", "classification_confidence", "mapping_version",
    "override_applied", "classification_reason", "source_accessions",
)

_METHODOLOGY = {
    "forecast_policy": "docs/methodology/united-states/forecast-discount-validation-policy.md",
    "sector_framework": "docs/methodology/united-states/equity-valuation-engine-framework.md",
    "source_policy": "SEC Companyfacts and submissions; no exchange prices",
}


class EquityInputsUnavailable(ValueError):
    """Raised when a bank/utility cannot be valued from the filing."""


def _cost_of_equity(policy: dict[str, Any]) -> float:
    return policy["risk_free_rate"] + policy["policy_beta"] * policy["equity_risk_premium"]


def _annual_10k(gaap: dict, names: list[str], cutoff: str | None) -> dict[int, float]:
    for name in names:
        c = gaap.get(name)
        if not c:
            continue
        out = {}
        for u in c.get("units", {}).get("USD", []):
            if u.get("fp") == "FY" and u.get("form") in ("10-K", "10-K/A"):
                if cutoff and (u.get("end") or "") > cutoff:
                    continue
                out[u["fy"]] = u["val"]
        if out:
            return out
    return {}


def _latest_instant(gaap: dict, names: list[str], unit: str, cutoff: str | None):
    for name in names:
        c = gaap.get(name)
        if not c:
            continue
        pts = [
            (u.get("end"), u.get("val"))
            for u in c.get("units", {}).get(unit, [])
            if u.get("end") and not (cutoff and u["end"] > cutoff)
        ]
        if pts:
            return max(pts)  # (end_date, value)
    return None


def extract_bank_inputs(gaap: dict, cutoff: str | None) -> dict[str, Any]:
    ni = _annual_10k(gaap, ["NetIncomeLoss"], cutoff)
    eq = _latest_instant(gaap, ["StockholdersEquity"], "USD", cutoff)
    sh = _latest_instant(
        gaap, ["CommonStockSharesOutstanding", "CommonStockSharesIssued"], "shares", cutoff
    )
    if not ni or not eq or not sh:
        raise EquityInputsUnavailable("missing net income, common equity, or share count")
    period_end, equity = eq
    net_income = ni[max(ni)]
    if equity <= 0 or net_income <= 0 or sh[1] <= 0:
        raise EquityInputsUnavailable("non-positive equity, net income (loss year), or shares")
    div = _annual_10k(gaap, ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"], cutoff)
    payout = min(max(div[max(div)] / net_income, 0.0), 1.0) if div else None
    return {
        "book_value_per_share": equity / sh[1],
        "current_roe": net_income / equity,
        "current_payout_ratio": payout,
        "period_end": period_end,
    }


def _annual_pershare(gaap: dict, names: list[str], cutoff: str | None) -> dict[int, float]:
    """Full-year per-share facts live under the ``USD/shares`` unit."""
    for name in names:
        c = gaap.get(name)
        if not c:
            continue
        out = {}
        for u in c.get("units", {}).get("USD/shares", []):
            if u.get("fp") == "FY" and u.get("form") in ("10-K", "10-K/A"):
                if cutoff and (u.get("end") or "") > cutoff:
                    continue
                out[u["fy"]] = u["val"]
        if out:
            return out
    return {}


def extract_utility_inputs(gaap: dict, cutoff: str | None) -> dict[str, Any]:
    dps_series = _annual_pershare(
        gaap,
        ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
        cutoff,
    )
    # Fallback: total common dividends / shares.
    if not dps_series:
        div = _annual_10k(gaap, ["PaymentsOfDividendsCommonStock"], cutoff)
        sh = _latest_instant(gaap, ["CommonStockSharesOutstanding"], "shares", cutoff)
        if div and sh:
            last = div[max(div)] / sh[1]
            dps_series = {max(div): last}
    eq = _latest_instant(gaap, ["StockholdersEquity"], "USD", cutoff)
    if not dps_series or not eq:
        raise EquityInputsUnavailable("missing per-share dividend history or equity")
    last_dividend = dps_series[max(dps_series)]
    if last_dividend <= 0:
        raise EquityInputsUnavailable("non-positive latest dividend (not a DDM candidate)")
    return {"last_dividend": last_dividend, "period_end": eq[0]}


def _shell(classification, valuation_date, source_manifest, period_end):
    return {
        "schema_version": "US-VALUATION-RESULT-1.0",
        "valuation_date": valuation_date or date.today().isoformat(),
        "market": "US",
        "currency": "USD",
        "issuer": {k: classification[k] for k in _ISSUER_KEYS},
        "financial_period_end": period_end,
        "source_manifest": source_manifest or {"status": "not_supplied"},
        "model_policy": {
            "primary": classification["valuation_policy"]["primary_model"],
            "supporting": classification["valuation_policy"]["supporting_models"],
            "blend_models": False,
            "reason": classification["valuation_policy"].get("model_policy_reason", ""),
        },
        "methodology": _METHODOLOGY,
    }


def _withheld(classification, valuation_date, source_manifest, model_name, message):
    result = _shell(classification, valuation_date, source_manifest, None)
    model = {
        "model": model_name, "output_type": "intrinsic_value_per_share", "currency": "USD",
        "intrinsic_value_per_share": None, "publication_state": "withheld",
        "errors": [message], "warnings": [],
    }
    result.update({
        "models": {model_name: model},
        "scenarios": {},
        "scenario_range": {"low": None, "base": None, "high": None,
                           "label": "assumption range, not a statistical confidence interval"},
        "review": {"publication_state": "withheld", "confidence_grade": "insufficient",
                   "errors": [message], "warnings": [],
                   "prohibited_output_check": {"current_price": False, "upside_downside": False,
                                               "buy_hold_sell": False, "trading_multiples": False}},
    })
    return result


def _finalize(classification, valuation_date, source_manifest, period_end, model_name,
              scenarios: dict[str, float], public_assumptions: dict, warnings: list[str]):
    base = scenarios["base"]
    errors: list[str] = []
    if base is None:
        return _withheld(classification, valuation_date, source_manifest, model_name,
                         "Model did not produce a base value.")
    if base <= 0:
        errors.append(f"Non-positive {model_name} intrinsic value; equity model does not apply.")
    state = "withheld" if errors else "review_required"
    model = {
        "model": model_name, "output_type": "intrinsic_value_per_share", "currency": "USD",
        "intrinsic_value_per_share": base, "publication_state": state,
        "errors": errors, "warnings": warnings,
    }
    result = _shell(classification, valuation_date, source_manifest, period_end)
    result.update({
        "public_assumptions": public_assumptions,
        "models": {model_name: model},
        "scenarios": {k: {model_name: {"intrinsic_value_per_share": v}} for k, v in scenarios.items()},
        "scenario_range": {
            "low": min(scenarios.values()), "base": base, "high": max(scenarios.values()),
            "label": "assumption range, not a statistical confidence interval",
        },
        "review": {"publication_state": state, "confidence_grade": "insufficient" if errors else "medium",
                   "errors": errors, "warnings": warnings,
                   "prohibited_output_check": {"current_price": False, "upside_downside": False,
                                               "buy_hold_sell": False, "trading_multiples": False}},
    })
    return result


def build_equity_level_result(*, classification, companyfacts, valuation_date, source_manifest):
    """Dispatch a bank (residual income) or utility (DDM) valuation, price-free."""
    policy = classification["valuation_policy"]
    model_name = policy["primary_model"]
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    ce = _cost_of_equity(policy)

    if model_name == "residual_income":
        try:
            inp = extract_bank_inputs(gaap, valuation_date)
        except EquityInputsUnavailable as exc:
            return _withheld(classification, valuation_date, source_manifest, model_name, str(exc))
        payout = inp["current_payout_ratio"]
        payout = policy["default_payout_ratio"] if payout is None else payout
        roe = inp["current_roe"]

        def val(mult, terminal_roe):
            return residual_income_valuation(
                book_value_per_share=inp["book_value_per_share"], current_roe=roe * mult,
                cost_of_equity=ce, current_payout_ratio=payout, terminal_roe=terminal_roe,
                terminal_growth=policy["terminal_growth"], years=policy["forecast_years"],
                current_price=None,
            )["intrinsic_value"]
        try:
            scenarios = {
                "bear": val(0.85, max(policy["terminal_roe"] - 0.02, ce + 0.01)),
                "base": val(1.00, policy["terminal_roe"]),
                "bull": val(1.15, policy["terminal_roe"] + 0.02),
            }
        except ValueError as exc:
            return _withheld(classification, valuation_date, source_manifest, model_name, str(exc))
        pa = {"cost_of_equity": ce, "risk_free_rate": policy["risk_free_rate"],
              "equity_risk_premium": policy["equity_risk_premium"], "policy_beta": policy["policy_beta"],
              "book_value_per_share": inp["book_value_per_share"], "current_roe": roe,
              "current_payout_ratio": payout, "terminal_roe": policy["terminal_roe"],
              "terminal_growth": policy["terminal_growth"]}
        warnings = ["Single-period book/ROE snapshot; average-equity and preferred-stock refinements pending."]
        return _finalize(classification, valuation_date, source_manifest, inp["period_end"],
                         model_name, scenarios, pa, warnings)

    if model_name == "ddm":
        try:
            inp = extract_utility_inputs(gaap, valuation_date)
        except EquityInputsUnavailable as exc:
            return _withheld(classification, valuation_date, source_manifest, model_name, str(exc))

        def val(high_growth):
            return two_stage_ddm(
                last_dividend=inp["last_dividend"], high_growth=high_growth,
                high_growth_years=policy["high_growth_years"], terminal_growth=policy["terminal_growth"],
                discount_rate=ce, current_price=None,
            )["intrinsic_value"]
        try:
            scenarios = {"bear": val(policy["high_dividend_growth"] - 0.02),
                         "base": val(policy["high_dividend_growth"]),
                         "bull": val(policy["high_dividend_growth"] + 0.02)}
        except ValueError as exc:
            return _withheld(classification, valuation_date, source_manifest, model_name, str(exc))
        pa = {"cost_of_equity": ce, "risk_free_rate": policy["risk_free_rate"],
              "equity_risk_premium": policy["equity_risk_premium"], "policy_beta": policy["policy_beta"],
              "last_dividend": inp["last_dividend"], "high_dividend_growth": policy["high_dividend_growth"],
              "terminal_growth": policy["terminal_growth"], "high_growth_years": policy["high_growth_years"]}
        warnings = ["Dividend growth is a governed policy assumption, not a per-issuer forecast."]
        return _finalize(classification, valuation_date, source_manifest, inp["period_end"],
                         model_name, scenarios, pa, warnings)

    raise ValueError(f"build_equity_level_result cannot handle primary_model={model_name!r}")
