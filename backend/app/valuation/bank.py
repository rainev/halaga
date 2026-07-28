"""Bank valuation models.

Banks are valued at the equity level because deposits and other funding
liabilities are operating inputs, not an ordinary EV-to-equity debt bridge.
The primary model is residual income; a clean-surplus DDM and stable justified
P/B are returned as linked cross-checks.
"""

from .common import summarize


MIN_RATE_GROWTH_SPREAD = 0.03


def residual_income_valuation(
    *,
    book_value_per_share: float,
    current_roe: float,
    cost_of_equity: float,
    current_payout_ratio: float,
    terminal_roe: float,
    terminal_growth: float,
    years: int = 5,
    current_price: float | None = None,
) -> dict:
    if book_value_per_share <= 0:
        raise ValueError("book_value_per_share must be positive")
    if not 0 <= current_payout_ratio <= 1:
        raise ValueError("current_payout_ratio must be between 0 and 1")
    if years < 1 or years > 30:
        raise ValueError("years must be between 1 and 30")
    if min(current_roe, terminal_roe, cost_of_equity) <= 0:
        raise ValueError("ROE and cost_of_equity must be positive")
    if terminal_growth < 0 or terminal_growth > 0.04:
        raise ValueError("terminal_growth must be between 0% and 4%")
    if cost_of_equity - terminal_growth < MIN_RATE_GROWTH_SPREAD:
        raise ValueError(
            "cost_of_equity must exceed terminal_growth by at least 3%"
        )
    if terminal_growth >= terminal_roe:
        raise ValueError("terminal_growth must be below terminal_roe")

    terminal_payout = 1 - terminal_growth / terminal_roe
    opening_book = book_value_per_share
    pv_residual_income = 0.0
    pv_dividends = 0.0
    schedule: list[dict] = []

    for year in range(1, years + 1):
        progress = year / years
        roe = current_roe + (terminal_roe - current_roe) * progress
        payout = current_payout_ratio + (
            terminal_payout - current_payout_ratio
        ) * progress
        net_income = opening_book * roe
        dividends = net_income * payout
        residual_income = net_income - cost_of_equity * opening_book
        discount_factor = (1 + cost_of_equity) ** year
        pv_residual_income += residual_income / discount_factor
        pv_dividends += dividends / discount_factor
        closing_book = opening_book + net_income - dividends
        schedule.append(
            {
                "year": year,
                "opening_book_value_per_share": opening_book,
                "roe": roe,
                "payout_ratio": payout,
                "earnings_per_share": net_income,
                "dividends_per_share": dividends,
                "residual_income_per_share": residual_income,
                "closing_book_value_per_share": closing_book,
            }
        )
        opening_book = closing_book

    next_residual_income = (terminal_roe - cost_of_equity) * opening_book
    continuing_residual_income = next_residual_income / (
        cost_of_equity - terminal_growth
    )
    pv_continuing_residual_income = continuing_residual_income / (
        1 + cost_of_equity
    ) ** years
    intrinsic = (
        book_value_per_share
        + pv_residual_income
        + pv_continuing_residual_income
    )

    # Under clean-surplus accounting, the DDM using the same earnings,
    # reinvestment, and payout path should reconcile with residual income.
    next_dividend = opening_book * terminal_roe * terminal_payout
    continuing_dividends = next_dividend / (
        cost_of_equity - terminal_growth
    )
    ddm_value = pv_dividends + continuing_dividends / (
        1 + cost_of_equity
    ) ** years
    justified_pb = (terminal_roe - terminal_growth) / (
        cost_of_equity - terminal_growth
    )
    justified_pb_value = justified_pb * book_value_per_share
    upside, verdict = summarize(intrinsic, current_price)
    reconciliation_difference = intrinsic - ddm_value
    warnings = [
        "The DDM cross-check uses the same clean-surplus forecast as residual income and is not independent evidence.",
        "Justified P/B is a stable-state cross-check, not a peer-market multiple.",
    ]
    if abs(reconciliation_difference) > 0.01:
        warnings.append("Residual income and clean-surplus DDM did not fully reconcile.")

    return {
        "model": "residual_income",
        "intrinsic_value": intrinsic,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {
            "status": "review",
            "warnings": warnings,
            "clean_surplus_reconciliation_difference": reconciliation_difference,
        },
        "detail": {
            "book_value_per_share": book_value_per_share,
            "current_roe": current_roe,
            "cost_of_equity": cost_of_equity,
            "current_payout_ratio": current_payout_ratio,
            "terminal_roe": terminal_roe,
            "terminal_growth": terminal_growth,
            "terminal_payout_ratio": terminal_payout,
            "forecast_years": years,
            "pv_forecast_residual_income": pv_residual_income,
            "pv_continuing_residual_income": pv_continuing_residual_income,
            "ddm_cross_check": ddm_value,
            "justified_pb_multiple": justified_pb,
            "justified_pb_value": justified_pb_value,
            "schedule": schedule,
        },
    }
