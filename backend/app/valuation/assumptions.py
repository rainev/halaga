"""Market-wide assumptions, defaulted for the Philippines (PSE / PHP).

These replace the US-centric constants baked into the original spreadsheet:
- Graham's `4.4` / `Y` were US AAA corporate-bond yields; for PH we normalize
  against a PHP government benchmark (BVAL 10Y ~6%).
- Discount rates / cost of equity should be built from a PHP risk-free rate and
  a PH equity risk premium, not a flat US-style 9.5%.

Values are editable at runtime via the `market_assumptions` DB table (the 'PH'
row); these dataclass defaults are the fallback when nothing is seeded.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketAssumptions:
    # CAPM building blocks (decimals).
    risk_free_rate: float = 0.06  # PHP 10Y govt / BVAL benchmark
    equity_risk_premium: float = 0.075  # PH equity risk premium

    # Graham formula inputs.
    graham_current_yield: float = 6.0  # PERCENT — current PHP benchmark yield ("Y")
    graham_normalizing_yield: float = 4.4  # Graham's original AAA constant
    graham_base_pe: float = 8.5  # P/E for a no-growth company

    # Long-run terminal growth (PH nominal GDP/inflation ballpark).
    default_perpetual_growth: float = 0.03


PH = MarketAssumptions()


def cost_of_equity(beta: float, a: MarketAssumptions = PH) -> float:
    """CAPM: r_e = risk_free + beta * equity_risk_premium."""
    return a.risk_free_rate + beta * a.equity_risk_premium


def wacc(
    *,
    cost_of_equity: float,
    cost_of_debt: float,
    equity_value: float,
    debt_value: float,
    tax_rate: float,
) -> float:
    """Weighted Average Cost of Capital — the correct discount rate for FCFF.

        WACC = (E/V)·Re + (D/V)·Rd·(1 − tax)

    E/V and D/V weight equity vs debt by their values; the (1 − tax) term
    captures the tax-deductibility of interest. Debt is cheaper than equity, so a
    levered firm's WACC is below its cost of equity — which is exactly why
    discounting firm cash flows (FCFF) at cost of equity understates value.
    """
    total = equity_value + debt_value
    if total <= 0:
        raise ValueError("equity_value + debt_value must be positive")
    we = equity_value / total
    wd = debt_value / total
    return we * cost_of_equity + wd * cost_of_debt * (1 - tax_rate)
