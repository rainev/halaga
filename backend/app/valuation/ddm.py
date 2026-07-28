"""Dividend Discount Model (Gordon growth).

Intrinsic value P = D1 / (r - g), where D1 = last_dividend * (1 + g).
"""

from .common import summarize, validate_terminal_spread


def ddm_valuation(
    *,
    last_dividend: float,
    growth_rate: float,
    discount_rate: float,
    current_price: float | None = None,
) -> dict:
    validate_terminal_spread(discount_rate, growth_rate)

    d1 = last_dividend * (1 + growth_rate)
    intrinsic = d1 / (discount_rate - growth_rate)

    upside, verdict = summarize(intrinsic, current_price)
    return {
        "model": "ddm",
        "intrinsic_value": intrinsic,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {
            "status": "pass",
            "warnings": [],
            "minimum_rate_growth_spread": 0.03,
        },
        "detail": {
            "method": "gordon",
            "last_dividend": last_dividend,
            "next_dividend": d1,
            "growth_rate": growth_rate,
            "discount_rate": discount_rate,
        },
    }


def two_stage_ddm(
    *,
    last_dividend: float,
    high_growth: float,
    high_growth_years: int,
    terminal_growth: float,
    discount_rate: float,
    current_price: float | None = None,
) -> dict:
    """Two-stage DDM: dividends grow at `high_growth` for `high_growth_years`,
    then settle to `terminal_growth` forever.

    Value = PV of the high-growth dividends + PV of the terminal (Gordon) value.
    Only the terminal rate must be below the discount rate; the high-growth rate
    may exceed it during the finite first stage. This fixes single-stage DDM's
    understatement of fast-growing / low-payout payers.
    """
    if high_growth_years < 1:
        raise ValueError("high_growth_years must be at least 1")
    try:
        validate_terminal_spread(discount_rate, terminal_growth)
    except ValueError as exc:
        raise ValueError(str(exc).replace("growth_rate", "terminal_growth")) from exc

    dividends: list[float] = []
    pv_stage1 = 0.0
    d = last_dividend
    for t in range(1, high_growth_years + 1):
        d = d * (1 + high_growth)
        pv_stage1 += d / (1 + discount_rate) ** t
        dividends.append(d)

    # Terminal value at the end of the high-growth stage (Gordon on the next div).
    d_terminal_next = dividends[-1] * (1 + terminal_growth)
    terminal_value = d_terminal_next / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / (1 + discount_rate) ** high_growth_years

    intrinsic = pv_stage1 + pv_terminal
    upside, verdict = summarize(intrinsic, current_price)
    return {
        "model": "ddm",
        "intrinsic_value": intrinsic,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {
            "status": "pass",
            "warnings": [],
            "minimum_rate_growth_spread": 0.03,
        },
        "detail": {
            "method": "two_stage",
            "last_dividend": last_dividend,
            "high_growth": high_growth,
            "high_growth_years": high_growth_years,
            "terminal_growth": terminal_growth,
            "discount_rate": discount_rate,
            "pv_high_growth": pv_stage1,
            "terminal_value": terminal_value,
            "pv_terminal": pv_terminal,
        },
    }
