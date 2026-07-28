"""Shared helpers for the valuation models."""

MIN_TERMINAL_SPREAD = 0.03
MAX_TERMINAL_GROWTH = 0.04


def validate_terminal_spread(
    discount_rate: float,
    growth_rate: float,
    *,
    minimum_spread: float = MIN_TERMINAL_SPREAD,
) -> None:
    """Reject mathematically invalid or governance-fragile perpetuities."""
    if discount_rate <= growth_rate:
        raise ValueError("discount_rate must exceed growth_rate")
    if discount_rate - growth_rate + 1e-12 < minimum_spread:
        raise ValueError(
            "discount_rate must exceed growth_rate by at least "
            f"{minimum_spread:.0%}"
        )
    if growth_rate > MAX_TERMINAL_GROWTH:
        raise ValueError(
            f"growth_rate must not exceed {MAX_TERMINAL_GROWTH:.0%} "
            "without a separately approved scenario"
        )


def summarize(intrinsic_value: float, current_price: float | None, band: float = 0.05):
    """Compute price/model variance and a descriptive, non-recommendation label.

    `band` is only a display tolerance. The label describes where the observed
    price sits relative to this model run; it does not claim market mispricing.
    """
    if current_price is None or current_price == 0:
        return None, None
    upside = intrinsic_value / current_price - 1
    if upside > band:
        verdict = "Below model estimate"
    elif upside < -band:
        verdict = "Above model estimate"
    else:
        verdict = "Near model estimate"
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
