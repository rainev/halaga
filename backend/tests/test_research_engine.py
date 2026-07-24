"""Research engine tests — ported from the FinSight engine.test.js.

Loads the seeded dataset directly from the JSON (no DB), so these stay hermetic.
"""

import json
from pathlib import Path

import pytest

from app.research import engine

DATA = json.loads((Path(__file__).parent.parent / "app/seed/financials_data.json").read_text())
COMPANIES = {c["symbol"]: c for c in DATA["companies"]}
ALL = list(COMPANIES.values())


@pytest.mark.parametrize("company", ALL, ids=[c["symbol"] for c in ALL])
def test_sentiment_cases_are_ordered(company):
    bear = engine.calculate_valuation(company, "bear")["blended"]
    base = engine.calculate_valuation(company, "base")["blended"]
    bull = engine.calculate_valuation(company, "bull")["blended"]
    assert bear < base, f"{company['symbol']}: bear must be below base"
    assert base < bull, f"{company['symbol']}: base must be below bull"


def test_risk_tolerance_changes_screen_not_filing_data():
    acr = COMPANIES["ACR"]
    revenue = acr["financials"]["revenue"]
    assert engine.score_company(acr, 5) >= engine.score_company(acr, 1)
    assert acr["financials"]["revenue"] == revenue  # engine never mutates the data


def test_health_engine_returns_both_statement_groups():
    health = engine.get_health_metrics(ALL[0], 3)
    assert len(health["pnl"]) == 6
    assert len(health["balance"]) == 5


def test_smart_brief_calls_intrinsic_value_not_a_market_quote():
    brief = engine.build_smart_brief(ALL[1], 3, "base")
    assert "not a market quote" in " ".join(brief["paragraphs"]).lower()


def test_score_is_bounded():
    for c in ALL:
        s = engine.score_company(c, 3)
        assert 0 <= s <= 100
