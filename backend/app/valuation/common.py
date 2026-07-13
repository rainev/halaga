"""Shared helpers for the valuation models."""


def summarize(intrinsic_value: float, current_price: float | None, band: float = 0.05):
    """Compute upside and a plain-language verdict.

    `band` is a tolerance around fair value: within +/- band the stock is
    "Fairly valued", above it "Undervalued" (intrinsic > price), below
    "Overvalued". Returns (upside_pct, verdict) with None when no price is given.
    """
    if current_price is None or current_price == 0:
        return None, None
    upside = intrinsic_value / current_price - 1
    if upside > band:
        verdict = "Undervalued"
    elif upside < -band:
        verdict = "Overvalued"
    else:
        verdict = "Fairly valued"
    return upside, verdict


def average_growth(series: list[float]) -> float:
    """Mean of period-over-period growth rates across a value series."""
    if len(series) < 2:
        raise ValueError("Need at least two values to compute growth")
    rates = [series[i] / series[i - 1] - 1 for i in range(1, len(series))]
    return sum(rates) / len(rates)


def cagr(series: list[float]) -> float:
    """Compound annual growth rate across a value series.

    Note: the exponent is 1 / (number of *intervals*) = len(series) - 1. The
    original spreadsheet used 1/5 for five data points (four intervals) — an
    off-by-one that overstated growth; this uses the correct count.
    """
    if len(series) < 2:
        raise ValueError("Need at least two values to compute CAGR")
    periods = len(series) - 1
    return (series[-1] / series[0]) ** (1 / periods) - 1
