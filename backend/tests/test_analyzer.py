"""Analyzer matching logic — direct entity match + thematic sector tagging.

Persistence and embeddings are stubbed so these run without DB/OpenAI; we assert
on the (company_id, link_type, relevance) links the analyzer decides to write.
"""

import pytest

from app.ai import analyzer
from app.services import article_service, news_service

COMPANIES = [
    {"id": 1, "ticker": "BDO", "name": "BDO Unibank", "sector": "Financial"},
    {"id": 2, "ticker": "MEG", "name": "Megaworld Corp", "sector": "Property"},
    {"id": 3, "ticker": "SCC", "name": "Semirara Mining and Power Corp", "sector": "Mining and Oil"},
]


@pytest.fixture
def captured(monkeypatch):
    stocks, sectors = [], []
    monkeypatch.setattr(article_service, "upsert_stock",
                        lambda nid, cid, lt, rel: stocks.append((cid, lt, rel)))
    monkeypatch.setattr(article_service, "upsert_sector",
                        lambda nid, s, lt, rel: sectors.append((s, lt, rel)))
    monkeypatch.setattr(news_service, "set_status", lambda nid, st: None)
    return {"stocks": stocks, "sectors": sectors}


def test_direct_ticker_match(captured):
    article = {"id": 10, "title": "BDO reports record profit", "body": "BDO Unibank earnings rose."}
    analyzer.analyze(article, COMPANIES)
    # BDO matched directly at full relevance; its sector tagged direct.
    assert (1, "direct", 1.0) in captured["stocks"]
    assert any(s == "Financial" and lt == "direct" for s, lt, _ in captured["sectors"])
    # Unrelated companies not linked.
    assert not any(cid == 3 for cid, _, _ in captured["stocks"])


def test_rate_hike_reaches_property_holder_thematically(captured):
    # No company named — a MEG holder should still get a thematic link because
    # rate news maps to the Property sector.
    article = {"id": 11, "title": "BSP raises policy rate by 25 basis points",
               "body": "The central bank hiked its benchmark rate to tame inflation."}
    analyzer.analyze(article, COMPANIES)
    meg = [row for row in captured["stocks"] if row[0] == 2]
    assert meg and meg[0][1] == "thematic"
    # Property sector tagged (thematic), driven by the interest_rates theme.
    assert any(s == "Property" for s, _, _ in captured["sectors"])


def test_no_match_leaves_no_links(captured):
    article = {"id": 12, "title": "Local barangay holds fun run", "body": "A community event."}
    analyzer.analyze(article, COMPANIES)
    assert captured["stocks"] == []
