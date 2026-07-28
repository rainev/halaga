"""Market-wide assumptions, defaulted for the Philippines (PSE / PHP).

The CAPM inputs explicitly separate a local government yield, sovereign default
spread, mature-market ERP, and Philippine country-risk premium. This prevents a
PHP government yield (which contains default risk) from being mislabeled as a
default-free rate and prevents country risk from being beta-scaled by accident.

Values are editable at runtime via the `market_assumptions` DB table (the 'PH'
row); these dataclass defaults are the fallback when nothing is seeded.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketAssumptions:
    # CAPM building blocks (decimals). Fallbacks are a dated working set and
    # should be refreshed through the assumptions table before live reliance.
    local_government_yield: float = 0.0600
    sovereign_default_spread: float = 0.0162
    risk_free_rate: float = 0.0438
    equity_risk_premium: float = 0.0423  # mature-market ERP; beta-scaled
    country_risk_premium: float = 0.0246  # PH CRP; exposure-scaled separately
    assumptions_as_of: str = "2026-01"
    assumptions_source: str = "Damodaran country risk dataset (January 2026)"
    assumptions_source_url: str = (
        "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ctryprem.html"
    )

    # Graham formula inputs.
    graham_current_yield: float = 6.0  # PERCENT — current PHP benchmark yield ("Y")
    graham_normalizing_yield: float = 4.4  # Graham's original AAA constant
    graham_base_pe: float = 8.5  # P/E for a no-growth company

    # Long-run terminal growth (PH nominal GDP/inflation ballpark).
    default_perpetual_growth: float = 0.03


PH = MarketAssumptions()


def cost_of_equity(
    beta: float,
    a: MarketAssumptions = PH,
    country_risk_exposure: float = 1.0,
) -> float:
    """PH cost of equity with country risk separated from beta.

    r_e = default-free PHP rate + beta * mature ERP + lambda * PH CRP
    """
    if beta < 0:
        raise ValueError("beta must be non-negative")
    if country_risk_exposure < 0:
        raise ValueError("country_risk_exposure must be non-negative")
    return (
        a.risk_free_rate
        + beta * a.equity_risk_premium
        + country_risk_exposure * a.country_risk_premium
    )


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
