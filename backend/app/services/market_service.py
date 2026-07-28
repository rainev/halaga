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
        local_government_yield=float(
            row.get("local_government_yield") or row["risk_free_rate"]
        ),
        sovereign_default_spread=float(
            row.get("sovereign_default_spread") or PH.sovereign_default_spread
        ),
        risk_free_rate=float(row["risk_free_rate"]),
        equity_risk_premium=float(row["equity_risk_premium"]),
        country_risk_premium=float(
            row.get("country_risk_premium") or PH.country_risk_premium
        ),
        assumptions_as_of=str(row.get("assumptions_as_of") or "legacy"),
        assumptions_source=str(
            row.get("assumptions_source") or "legacy database row"
        ),
        assumptions_source_url=str(
            row.get("assumptions_source_url") or PH.assumptions_source_url
        ),
        graham_current_yield=float(row["graham_current_yield"]),
        graham_normalizing_yield=float(row["graham_normalizing_yield"]),
        graham_base_pe=float(row["graham_base_pe"]),
        default_perpetual_growth=float(row["default_perpetual_growth"]),
    )
