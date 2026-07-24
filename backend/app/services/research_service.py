"""Research workbench service: load seeded filing data and run the engine.

The engine is pure (see app/research/engine.py); this layer loads the company
record from company_financials and shapes API responses (rankings, health,
valuation, smart brief).
"""

from typing import Any

from ..db import query, query_one
from ..errors import AppError
from ..research import engine


def _record(ticker: str) -> dict[str, Any]:
    row = query_one(
        """
        SELECT f.data
        FROM company_financials f
        JOIN companies c ON c.id = f.company_id
        WHERE c.ticker = %s
        """,
        (ticker.upper(),),
    )
    if not row:
        raise AppError(f"No filing data for '{ticker}'. Only scored companies are available.", 404)
    return row["data"]


def _all_records() -> list[dict[str, Any]]:
    rows = query(
        "SELECT f.data FROM company_financials f "
        "JOIN companies c ON c.id = f.company_id ORDER BY c.ticker"
    )
    return [r["data"] for r in rows]


def _meta(c: dict[str, Any]) -> dict[str, Any]:
    """The presentation fields the UI shows for a company."""
    return {
        "symbol": c["symbol"], "name": c["name"], "shortName": c.get("shortName"),
        "sector": c.get("sector"), "subsector": c.get("subsector"),
        "color": c.get("color"), "insight": c.get("insight"),
        "source": c.get("source"), "period": c.get("financials", {}).get("period"),
    }


def companies() -> list[dict[str, Any]]:
    """The scored companies, for page selectors."""
    return [_meta(c) for c in _all_records()]


def rankings(risk: int = 3) -> dict[str, Any]:
    ranked = []
    for c in _all_records():
        health = engine.get_health_metrics(c, risk)
        checks = [m for m in [*health["pnl"], *health["balance"]]
                  if m["status"] in ("pass", "watch")]
        passes = sum(1 for m in checks if m["status"] == "pass")
        ranked.append({
            **_meta(c),
            "score": engine.score_company(c, risk),
            "checks": {"passes": passes, "total": len(checks)},
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {"risk": risk, "profile": engine.RISK_PROFILES.get(risk), "ranked": ranked}


def health(ticker: str, risk: int = 3) -> dict[str, Any]:
    c = _record(ticker)
    return {
        "company": _meta(c),
        "risk": risk,
        "profile": engine.RISK_PROFILES.get(risk),
        **engine.get_health_metrics(c, risk),
    }


def valuation(ticker: str, sentiment: str = "base") -> dict[str, Any]:
    c = _record(ticker)
    return {
        "company": _meta(c),
        "sentiment": sentiment,
        "weights": c["valuation"]["weights"],
        "valuationNote": c["valuation"].get("note"),
        "assumptions": engine.ASSUMPTIONS,
        **engine.calculate_valuation(c, sentiment),
    }


def brief(ticker: str, risk: int = 3, sentiment: str = "base") -> dict[str, Any]:
    c = _record(ticker)
    return {
        "company": _meta(c),
        "risk": risk,
        "sentiment": sentiment,
        **engine.build_smart_brief(c, risk, sentiment),
    }
