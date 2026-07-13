"""Benjamin Graham's revised intrinsic-value formula.

    V = EPS * (base_pe + 2g) * normalizing_yield / current_yield

IMPORTANT: `g` is the expected growth rate in WHOLE-NUMBER PERCENT (e.g. 9.63 for
9.63%), NOT a decimal. The original spreadsheet passed 0.0963 here, which
collapsed the (8.5 + 2g) term and massively understated value — fixed by taking
`growth_rate_pct` explicitly.

`normalizing_yield` (Graham's 4.4) and `current_yield` are bond yields; for the
PH market `current_yield` is the PHP government benchmark, not a US AAA yield.
"""


def graham_valuation(
    *,
    eps: float,
    growth_rate_pct: float,
    current_yield: float,
    base_pe: float = 8.5,
    normalizing_yield: float = 4.4,
    margin_of_safety: float = 0.35,
    current_price: float | None = None,
) -> dict:
    if current_yield <= 0:
        raise ValueError("current_yield must be positive")

    intrinsic = eps * (base_pe + 2 * growth_rate_pct) * normalizing_yield / current_yield
    acceptable_buy_price = (1 - margin_of_safety) * intrinsic

    # Graham's rule: only buy below the margin-of-safety price.
    verdict = None
    upside = None
    if current_price is not None:
        upside = intrinsic / current_price - 1 if current_price else None
        verdict = "Buy" if current_price < acceptable_buy_price else "Sell"

    return {
        "model": "graham",
        "intrinsic_value": intrinsic,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "detail": {
            "eps": eps,
            "growth_rate_pct": growth_rate_pct,
            "base_pe": base_pe,
            "normalizing_yield": normalizing_yield,
            "current_yield": current_yield,
            "margin_of_safety": margin_of_safety,
            "acceptable_buy_price": acceptable_buy_price,
        },
    }
