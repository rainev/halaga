"""Reads the active (PH) market assumptions from the DB, falling back to the
engine's built-in defaults when nothing is seeded."""

from ..db import query_one
from ..valuation.assumptions import PH, MarketAssumptions

ACTIVE_KEY = "PH"


def get_assumptions() -> MarketAssumptions:
    row = query_one("SELECT * FROM market_assumptions WHERE key = %s", (ACTIVE_KEY,))
    if not row:
        return PH
    # Postgres NUMERIC comes back as Decimal — coerce to float for the engine.
    return MarketAssumptions(
        risk_free_rate=float(row["risk_free_rate"]),
        equity_risk_premium=float(row["equity_risk_premium"]),
        graham_current_yield=float(row["graham_current_yield"]),
        graham_normalizing_yield=float(row["graham_normalizing_yield"]),
        graham_base_pe=float(row["graham_base_pe"]),
        default_perpetual_growth=float(row["default_perpetual_growth"]),
    )
