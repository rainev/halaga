"""Pure FCFF DCF, EPV, scenarios, and sensitivities for the U.S. pilot."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _validate_inputs(
    assumptions: dict[str, Any],
    discount_rate: dict[str, Any],
    financials: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    wacc = float(discount_rate["wacc"])
    terminal_growth = float(assumptions["terminal_growth"])
    if wacc <= terminal_growth:
        errors.append("WACC must exceed terminal growth.")
    if wacc - terminal_growth < 0.025:
        errors.append(
            "U.S. policy requires WACC to exceed terminal growth by at least 2.5 percentage points."
        )
    if terminal_growth > 0.025:
        errors.append("Terminal growth above 2.5% requires manual approval.")
    if assumptions["terminal_marginal_roic"] <= terminal_growth:
        errors.append("Terminal marginal ROIC must exceed terminal growth.")
    if financials["balance_sheet"]["fully_diluted_shares_proxy"] <= 0:
        errors.append("Share count must be positive.")
    return errors


def _fade_weight(persistence: float, year: int, years: int) -> float:
    """Persistence-shaped fade that lands exactly on the terminal state."""
    if years <= 1 or year >= years:
        return 0.0
    denominator = persistence - persistence**years
    if abs(denominator) < 1e-12:
        return (years - year) / (years - 1)
    return (persistence**year - persistence**years) / denominator


def fcff_dcf(
    *,
    assumptions: dict[str, Any],
    discount_rate: dict[str, Any],
    financials: dict[str, Any],
) -> dict[str, Any]:
    errors = _validate_inputs(assumptions, discount_rate, financials)
    if errors:
        return {
            "model": "fcff_dcf",
            "output_type": "intrinsic_value_per_share",
            "publication_state": "blocked",
            "errors": errors,
            "warnings": [],
        }

    years = int(assumptions["forecast_years"])
    wacc = float(discount_rate["wacc"])
    tax_rate = float(assumptions["normalized_tax_rate"])
    growth = float(assumptions["initial_revenue_growth"])
    target_margin = float(assumptions["target_operating_margin"])
    revenue = float(assumptions["starting_revenue"])
    starting_margin = float(assumptions["starting_operating_margin"])
    terminal_growth = float(assumptions["terminal_growth"])
    initial_roic = float(assumptions["initial_marginal_roic"])
    terminal_roic = float(assumptions["terminal_marginal_roic"])
    growth_persistence = float(assumptions["growth_persistence"])
    margin_persistence = float(assumptions["margin_persistence"])
    segment_forecast = assumptions.get("segment_forecast")
    segment_states = (
        {
            key: {
                **segment,
                "revenue": float(segment["starting_revenue"]),
            }
            for key, segment in segment_forecast["segments"].items()
        }
        if segment_forecast
        else None
    )
    starting_opex_ratio = (
        float(segment_forecast["starting_operating_expense_ratio"])
        if segment_forecast
        else None
    )
    target_opex_ratio = (
        float(segment_forecast["target_operating_expense_ratio"])
        if segment_forecast
        else None
    )

    schedule = []
    pv_explicit = 0.0
    for year in range(1, years + 1):
        growth_weight = _fade_weight(growth_persistence, year, years)
        margin_weight = _fade_weight(margin_persistence, year, years)
        prior_revenue = revenue
        segment_detail = None
        if segment_states:
            segment_detail = {}
            revenue = 0.0
            gross_profit = 0.0
            for key, segment in segment_states.items():
                segment_growth = terminal_growth + (
                    float(segment["initial_revenue_growth"])
                    - terminal_growth
                ) * growth_weight
                segment_margin = float(segment["target_gross_margin"]) + (
                    float(segment["starting_gross_margin"])
                    - float(segment["target_gross_margin"])
                ) * margin_weight
                segment["revenue"] *= 1 + segment_growth
                segment_gross_profit = segment["revenue"] * segment_margin
                revenue += segment["revenue"]
                gross_profit += segment_gross_profit
                segment_detail[key] = {
                    "revenue_growth": segment_growth,
                    "revenue": segment["revenue"],
                    "gross_margin": segment_margin,
                    "gross_profit": segment_gross_profit,
                }
            opex_ratio = target_opex_ratio + (
                starting_opex_ratio - target_opex_ratio
            ) * margin_weight
            operating_expense = revenue * opex_ratio
            ebit = gross_profit - operating_expense
            margin = ebit / revenue
            year_growth = revenue / prior_revenue - 1
        else:
            year_growth = terminal_growth + (
                growth - terminal_growth
            ) * growth_weight
            margin = target_margin + (
                starting_margin - target_margin
            ) * margin_weight
            revenue *= 1 + year_growth
            ebit = revenue * margin
            opex_ratio = None
            operating_expense = None
        nopat = ebit * (1 - tax_rate)
        fade_fraction = year / years
        marginal_roic = initial_roic + (
            terminal_roic - initial_roic
        ) * fade_fraction
        reinvestment_rate = (
            max(year_growth, 0.0) / marginal_roic if marginal_roic > 0 else 1.0
        )
        reinvestment_rate = min(reinvestment_rate, 0.95)
        reinvestment = nopat * reinvestment_rate
        fcff = nopat - reinvestment
        present_value = fcff / (1 + wacc) ** year
        pv_explicit += present_value
        schedule.append(
            {
                "year": year,
                "revenue_growth": year_growth,
                "revenue": revenue,
                "operating_margin": margin,
                "operating_expense_ratio": opex_ratio,
                "operating_expense": operating_expense,
                "segments": segment_detail,
                "ebit": ebit,
                "nopat": nopat,
                "marginal_roic": marginal_roic,
                "reinvestment_rate": reinvestment_rate,
                "reinvestment": reinvestment,
                "fcff": fcff,
                "present_value": present_value,
            }
        )

    terminal_reinvestment_rate = terminal_growth / terminal_roic
    if segment_states:
        terminal_segment_revenue = {
            key: segment["revenue"] * (1 + terminal_growth)
            for key, segment in segment_states.items()
        }
        terminal_revenue = sum(terminal_segment_revenue.values())
        terminal_gross_profit = sum(
            terminal_segment_revenue[key]
            * float(segment["target_gross_margin"])
            for key, segment in segment_states.items()
        )
        terminal_ebit = (
            terminal_gross_profit - terminal_revenue * target_opex_ratio
        )
        terminal_nopat = terminal_ebit * (1 - tax_rate)
    else:
        terminal_nopat = (
            revenue * (1 + terminal_growth) * target_margin * (1 - tax_rate)
        )
    terminal_fcff = terminal_nopat * (1 - terminal_reinvestment_rate)
    terminal_value = terminal_fcff / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** years
    enterprise_value = pv_explicit + pv_terminal
    cash_and_investments = financials["balance_sheet"][
        "cash_and_nonoperating_investments"
    ]
    debt = financials["balance_sheet"]["total_interest_bearing_debt"]
    preferred_equity = financials["balance_sheet"]["preferred_equity"]
    noncontrolling_interests = financials["balance_sheet"][
        "noncontrolling_interests"
    ]
    equity_value = (
        enterprise_value
        + cash_and_investments
        - debt
        - preferred_equity
        - noncontrolling_interests
    )
    shares = financials["balance_sheet"]["fully_diluted_shares_proxy"]
    per_share = equity_value / shares
    terminal_share = pv_terminal / enterprise_value

    warnings = []
    if wacc - terminal_growth < 0.035:
        warnings.append(
            "WACC minus terminal growth is below the 3.5-point warning threshold."
        )
    if terminal_share > 0.75:
        warnings.append("Present value of terminal value exceeds 75% of enterprise value.")
    if terminal_share > 0.85:
        warnings.append("Present value of terminal value exceeds 85%; manual review is required.")

    return {
        "model": "fcff_dcf",
        "output_type": "intrinsic_value_per_share",
        "currency": "USD",
        "intrinsic_value_per_share": per_share,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "publication_state": "review" if warnings else "pass",
        "errors": [],
        "warnings": warnings,
        "detail": {
            "forecast_schedule": schedule,
            "pv_explicit_fcff": pv_explicit,
            "terminal_nopat": terminal_nopat,
            "terminal_reinvestment_rate": terminal_reinvestment_rate,
            "terminal_fcff": terminal_fcff,
            "terminal_value": terminal_value,
            "pv_terminal_value": pv_terminal,
            "terminal_value_share": terminal_share,
            "cash_and_nonoperating_investments": cash_and_investments,
            "interest_bearing_debt": debt,
            "preferred_equity": preferred_equity,
            "noncontrolling_interests": noncontrolling_interests,
            "shares_proxy": shares,
            "wacc": wacc,
            "terminal_growth": terminal_growth,
        },
    }


def earnings_power_value(
    *,
    assumptions: dict[str, Any],
    discount_rate: dict[str, Any],
    financials: dict[str, Any],
) -> dict[str, Any]:
    wacc = float(discount_rate["wacc"])
    tax_rate = float(assumptions["normalized_tax_rate"])
    normalized_ebit = (
        float(assumptions["starting_revenue"])
        * float(
            assumptions.get(
                "normalized_operating_margin",
                assumptions["target_operating_margin"],
            )
        )
    )
    normalized_nopat = normalized_ebit * (1 - tax_rate)
    enterprise_value = normalized_nopat / wacc
    equity_value = (
        enterprise_value
        + financials["balance_sheet"]["cash_and_nonoperating_investments"]
        - financials["balance_sheet"]["total_interest_bearing_debt"]
        - financials["balance_sheet"]["preferred_equity"]
        - financials["balance_sheet"]["noncontrolling_interests"]
    )
    shares = financials["balance_sheet"]["fully_diluted_shares_proxy"]
    return {
        "model": "epv",
        "output_type": "intrinsic_value_per_share",
        "currency": "USD",
        "intrinsic_value_per_share": equity_value / shares,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "publication_state": "review",
        "errors": [],
        "warnings": [
            "EPV is a no-growth support value, not an independent growth forecast.",
            "It assumes normalized D&A approximates maintenance CapEx and normalized working capital is stable.",
        ],
        "detail": {
            "normalized_ebit": normalized_ebit,
            "normalized_nopat": normalized_nopat,
            "wacc": wacc,
            "shares_proxy": shares,
        },
    }


def _apply_forecast_delta(
    assumptions: dict[str, Any],
    *,
    growth_delta: float = 0.0,
    margin_delta: float = 0.0,
) -> None:
    assumptions["initial_revenue_growth"] += growth_delta
    assumptions["target_operating_margin"] += margin_delta
    segment_forecast = assumptions.get("segment_forecast")
    if not segment_forecast:
        return
    for segment in segment_forecast["segments"].values():
        segment["initial_revenue_growth"] += growth_delta
        segment["target_gross_margin"] += margin_delta


def scenario_set(
    *,
    assumptions: dict[str, Any],
    discount_rate: dict[str, Any],
    financials: dict[str, Any],
) -> dict[str, Any]:
    definitions = {
        "bear": {
            "growth_delta": -0.02,
            "margin_delta": -0.02,
            "wacc_delta": 0.01,
            "terminal_growth_delta": -0.005,
        },
        "base": {
            "growth_delta": 0.0,
            "margin_delta": 0.0,
            "wacc_delta": 0.0,
            "terminal_growth_delta": 0.0,
        },
        "bull": {
            "growth_delta": 0.02,
            "margin_delta": 0.02,
            "wacc_delta": -0.01,
            "terminal_growth_delta": 0.005,
        },
    }
    results = {}
    for name, deltas in definitions.items():
        scenario_assumptions = deepcopy(assumptions)
        scenario_rate = deepcopy(discount_rate)
        _apply_forecast_delta(
            scenario_assumptions,
            growth_delta=deltas["growth_delta"],
            margin_delta=deltas["margin_delta"],
        )
        scenario_assumptions["terminal_growth"] += deltas["terminal_growth_delta"]
        scenario_rate["wacc"] += deltas["wacc_delta"]
        scenario_assumptions["terminal_marginal_roic"] = (
            scenario_rate["wacc"]
            + (
                assumptions["terminal_marginal_roic"]
                - discount_rate["wacc"]
            )
        )
        results[name] = {
            "assumption_changes": deltas,
            "fcff_dcf": fcff_dcf(
                assumptions=scenario_assumptions,
                discount_rate=scenario_rate,
                financials=financials,
            ),
        }
    return results


def one_way_sensitivities(
    *,
    assumptions: dict[str, Any],
    discount_rate: dict[str, Any],
    financials: dict[str, Any],
) -> list[dict[str, Any]]:
    tests = [
        ("wacc", -0.01),
        ("wacc", 0.01),
        ("terminal_growth", -0.005),
        ("terminal_growth", 0.005),
        ("initial_revenue_growth", -0.02),
        ("initial_revenue_growth", 0.02),
        ("target_operating_margin", -0.02),
        ("target_operating_margin", 0.02),
    ]
    rows = []
    for field, delta in tests:
        scenario_assumptions = deepcopy(assumptions)
        scenario_rate = deepcopy(discount_rate)
        if field == "wacc":
            scenario_rate["wacc"] += delta
        elif field == "initial_revenue_growth":
            _apply_forecast_delta(
                scenario_assumptions,
                growth_delta=delta,
            )
        elif field == "target_operating_margin":
            _apply_forecast_delta(
                scenario_assumptions,
                margin_delta=delta,
            )
        else:
            scenario_assumptions[field] += delta
        result = fcff_dcf(
            assumptions=scenario_assumptions,
            discount_rate=scenario_rate,
            financials=financials,
        )
        rows.append(
            {
                "field": field,
                "delta": delta,
                "intrinsic_value_per_share": result.get(
                    "intrinsic_value_per_share"
                ),
                "publication_state": result["publication_state"],
            }
        )
    return rows
