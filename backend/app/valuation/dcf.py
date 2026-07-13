"""Discounted Cash Flow model.

Projects free cash flow, adds a Gordon-growth terminal value, discounts
everything to present value, then bridges from enterprise value to an intrinsic
price per share.
"""

from .common import summarize


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
    if discount_rate <= perpetual_growth_rate:
        raise ValueError("discount_rate must exceed perpetual_growth_rate")

    n = len(projected_fcf)
    pv_fcf = [fcf / (1 + discount_rate) ** (t + 1) for t, fcf in enumerate(projected_fcf)]

    # Terminal value off the final forecast year, discounted back from year n.
    last = projected_fcf[-1]
    terminal_value = last * (1 + perpetual_growth_rate) / (discount_rate - perpetual_growth_rate)
    pv_terminal = terminal_value / (1 + discount_rate) ** n

    enterprise_value = sum(pv_fcf) + pv_terminal
    equity_value = enterprise_value + cash - total_debt
    intrinsic_per_share = equity_value / shares_outstanding

    upside, verdict = summarize(intrinsic_per_share, current_price)
    return {
        "model": "dcf",
        "intrinsic_value": intrinsic_per_share,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "detail": {
            "method": method,
            "pv_fcf": pv_fcf,
            "terminal_value": terminal_value,
            "pv_terminal": pv_terminal,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "cash": cash,
            "total_debt": total_debt,
            "shares_outstanding": shares_outstanding,
            "discount_rate": discount_rate,
            "perpetual_growth_rate": perpetual_growth_rate,
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
    if cost_of_equity <= perpetual_growth_rate:
        raise ValueError("cost_of_equity must exceed perpetual_growth_rate")

    r = cost_of_equity
    n = len(projected_fcfe)
    pv_fcfe = [f / (1 + r) ** (t + 1) for t, f in enumerate(projected_fcfe)]

    last = projected_fcfe[-1]
    terminal_value = last * (1 + perpetual_growth_rate) / (r - perpetual_growth_rate)
    pv_terminal = terminal_value / (1 + r) ** n

    equity_value = sum(pv_fcfe) + pv_terminal  # already equity — no bridge
    intrinsic_per_share = equity_value / shares_outstanding

    upside, verdict = summarize(intrinsic_per_share, current_price)
    return {
        "model": "dcf",
        "intrinsic_value": intrinsic_per_share,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "detail": {
            "method": "fcfe",
            "pv_fcfe": pv_fcfe,
            "terminal_value": terminal_value,
            "pv_terminal": pv_terminal,
            "equity_value": equity_value,
            "shares_outstanding": shares_outstanding,
            "cost_of_equity": r,
            "perpetual_growth_rate": perpetual_growth_rate,
        },
    }
