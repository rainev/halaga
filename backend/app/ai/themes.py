"""Macro/thematic taxonomy: theme -> the PSE sectors it typically moves.

Kept in code (not a table) for v1 — it's small, reviewable, and versioned with
the analyzer. Detection is keyword-based now; the pgvector embedding on
news_items is stored so this can become semantic later without a schema change.

Sector strings must match the values seeded into companies.sector
(PH-Stocks folder names): ETF, Financial, Holding, Industrial, Mining and Oil,
Property, SME-B, Services.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    keywords: tuple[str, ...]
    sectors: tuple[str, ...]


THEMES: tuple[Theme, ...] = (
    Theme(
        key="interest_rates",
        keywords=("interest rate", "rate hike", "rate cut", "bsp", "monetary policy",
                  "policy rate", "benchmark rate", "rrp", "basis points", "bps"),
        # Rates move banks (margins) and property (mortgage/financing) most.
        sectors=("Financial", "Property", "Holding"),
    ),
    Theme(
        key="inflation",
        keywords=("inflation", "cpi", "consumer prices", "cost of living"),
        sectors=("Financial", "Services", "SME-B"),
    ),
    Theme(
        key="oil_energy",
        keywords=("oil price", "crude", "brent", "fuel", "gasoline", "diesel",
                  "power rate", "electricity", "coal"),
        sectors=("Industrial", "Mining and Oil"),
    ),
    Theme(
        key="fx_peso",
        keywords=("peso", "exchange rate", "forex", "fx", "dollar", "remittance"),
        sectors=("Financial", "Holding", "Services"),
    ),
    Theme(
        key="commodities_mining",
        keywords=("nickel", "gold", "copper", "mineral", "mining", "ore", "metal price"),
        sectors=("Mining and Oil",),
    ),
    Theme(
        key="property_market",
        keywords=("real estate", "property market", "housing", "office space",
                  "condominium", "vacancy", "reit"),
        sectors=("Property",),
    ),
)


def detect_themes(text: str) -> list[Theme]:
    """Themes whose keywords appear in the (lowercased) article text."""
    lowered = text.lower()
    return [t for t in THEMES if any(kw in lowered for kw in t.keywords)]
