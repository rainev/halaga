"""Discounted Cash Flow model.

Projects free cash flow, adds a Gordon-growth terminal value, discounts
everything to present value, then bridges from enterprise value to an intrinsic
price per share.
"""

from .common import summarize, validate_terminal_spread


def project_fcf(base_fcf: float, growth_rate: float, years: int) -> list[float]:
    """Grow a base FCF at a constant rate for `years` periods (year 1..years)."""
    return [base_fcf * (1 + growth_rate) ** t for t in range(1, years + 1)]


def dcf_valuation(
    *,
    projected_fcf: list[float],
    discount_rate: float,
    perpetual_growth_rate: float,
    shares_outstanding: float,
    cash: float = 0.0,
    total_debt: float = 0.0,
    preferred_stock: float = 0.0,
    non_controlling_interest: float = 0.0,
    current_price: float | None = None,
    method: str = "simple",
) -> dict:
    """FCFF / enterprise DCF: discount firm cash flows, add cash, subtract debt.

    Consistent when `projected_fcf` is free cash flow to the FIRM and
    `discount_rate` is the WACC (see fcfe_valuation for the equity-level variant).
    """
    if not projected_fcf:
        raise ValueError("projected_fcf must not be empty")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    try:
        validate_terminal_spread(discount_rate, perpetual_growth_rate)
    except ValueError as exc:
        raise ValueError(str(exc).replace("growth_rate", "perpetual_growth_rate")) from exc

    n = len(projected_fcf)
    pv_fcf = [fcf / (1 + discount_rate) ** (t + 1) for t, fcf in enumerate(projected_fcf)]

    # Terminal value off the final forecast year, discounted back from year n.
    last = projected_fcf[-1]
    terminal_value = last * (1 + perpetual_growth_rate) / (discount_rate - perpetual_growth_rate)
    pv_terminal = terminal_value / (1 + discount_rate) ** n

    enterprise_value = sum(pv_fcf) + pv_terminal
    equity_value = (
        enterprise_value
        + cash
        - total_debt
        - preferred_stock
        - non_controlling_interest
    )
    intrinsic_per_share = equity_value / shares_outstanding
    terminal_value_share = pv_terminal / enterprise_value if enterprise_value else None
    warnings = []
    if terminal_value_share is not None and terminal_value_share > 0.75:
        warnings.append("PV of terminal value exceeds 75% of enterprise value")

    upside, verdict = summarize(intrinsic_per_share, current_price)
    return {
        "model": "dcf",
        "intrinsic_value": intrinsic_per_share,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {
            "status": "review" if warnings else "pass",
            "warnings": warnings,
            "minimum_rate_growth_spread": 0.03,
        },
        "detail": {
            "method": method,
            "pv_fcf": pv_fcf,
            "terminal_value": terminal_value,
            "pv_terminal": pv_terminal,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "cash": cash,
            "total_debt": total_debt,
            "preferred_stock": preferred_stock,
            "non_controlling_interest": non_controlling_interest,
            "shares_outstanding": shares_outstanding,
            "discount_rate": discount_rate,
            "perpetual_growth_rate": perpetual_growth_rate,
            "terminal_value_share": terminal_value_share,
        },
    }


def fcfe_valuation(
    *,
    projected_fcfe: list[float],
    cost_of_equity: float,
    perpetual_growth_rate: float,
    shares_outstanding: float,
    current_price: float | None = None,
) -> dict:
    """FCFE / equity DCF: discount cash flows that already belong to shareholders
    (after debt payments) at the COST OF EQUITY, straight to equity value.

    No cash/debt bridge here — FCFE is post-financing, so subtracting debt again
    would double-count it. This is the consistent partner to entering cost of
    equity (rather than WACC) as the rate.
    """
    if not projected_fcfe:
        raise ValueError("projected_fcfe must not be empty")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    try:
        validate_terminal_spread(cost_of_equity, perpetual_growth_rate)
    except ValueError as exc:
        raise ValueError(
            str(exc)
            .replace("discount_rate", "cost_of_equity")
            .replace("growth_rate", "perpetual_growth_rate")
        ) from exc

    r = cost_of_equity
    n = len(projected_fcfe)
    pv_fcfe = [f / (1 + r) ** (t + 1) for t, f in enumerate(projected_fcfe)]

    last = projected_fcfe[-1]
    terminal_value = last * (1 + perpetual_growth_rate) / (r - perpetual_growth_rate)
    pv_terminal = terminal_value / (1 + r) ** n

    equity_value = sum(pv_fcfe) + pv_terminal  # already equity — no bridge
    intrinsic_per_share = equity_value / shares_outstanding
    terminal_value_share = pv_terminal / equity_value if equity_value else None
    warnings = []
    if terminal_value_share is not None and terminal_value_share > 0.75:
        warnings.append("PV of terminal value exceeds 75% of equity value")

    upside, verdict = summarize(intrinsic_per_share, current_price)
    return {
        "model": "dcf",
        "intrinsic_value": intrinsic_per_share,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {
            "status": "review" if warnings else "pass",
            "warnings": warnings,
            "minimum_rate_growth_spread": 0.03,
        },
        "detail": {
            "method": "fcfe",
            "pv_fcfe": pv_fcfe,
            "terminal_value": terminal_value,
            "pv_terminal": pv_terminal,
            "equity_value": equity_value,
            "shares_outstanding": shares_outstanding,
            "cost_of_equity": r,
            "perpetual_growth_rate": perpetual_growth_rate,
            "terminal_value_share": terminal_value_share,
        },
    }
