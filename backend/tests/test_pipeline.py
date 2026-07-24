"""Pipeline orchestration — analyze then generate, with all I/O stubbed.

Verifies the confidence-threshold gate and the idempotency skip, without a DB or
OpenAI.
"""

import pytest

from app.ai import analyzer, insight_generator, openai_client
from app.pipeline import run as pipeline
from app.services import article_service, insight_service, news_service

ARTICLE = {"id": 5, "title": "BSP hikes rates", "url": "https://ex.com/a", "body": "..."}
LINKS = [
    {"company_id": 2, "ticker": "MEG", "name": "Megaworld", "sector": "Property",
     "link_type": "thematic", "relevance": 0.6},   # above threshold -> generate
    {"company_id": 9, "ticker": "XYZ", "name": "Lowsig", "sector": "Services",
     "link_type": "thematic", "relevance": 0.3},    # below threshold -> skip
]


@pytest.fixture
def stubbed(monkeypatch):
    made = []
    monkeypatch.setattr(analyzer, "analyze", lambda a, c=None: {})
    monkeypatch.setattr(news_service, "get", lambda nid: ARTICLE)
    monkeypatch.setattr(news_service, "set_status", lambda nid, st: None)
    monkeypatch.setattr(article_service, "stocks_for_article", lambda nid: LINKS)
    monkeypatch.setattr(article_service, "has_insight", lambda nid, cid: False)
    monkeypatch.setattr(openai_client, "is_enabled", lambda: True)
    monkeypatch.setattr(insight_generator, "generate", lambda art, link: {
        "summary": "s", "possible_impact": "p", "direction": "headwind",
        "confidence": 0.6, "sources": [{"title": art["title"], "url": art["url"]}],
    })
    monkeypatch.setattr(
        insight_service, "upsert",
        lambda *a, **k: made.append(a[1]) or {"id": len(made)},  # a[1] = company_id
    )
    return made


def test_only_above_threshold_generates(stubbed):
    result = pipeline.process_article(ARTICLE, companies=[])
    assert result["insights"] == 1     # only MEG (0.6), not XYZ (0.3)
    assert stubbed == [2]


def test_skips_existing_insight(stubbed, monkeypatch):
    monkeypatch.setattr(article_service, "has_insight", lambda nid, cid: True)
    result = pipeline.process_article(ARTICLE, companies=[])
    assert result["insights"] == 0
    assert stubbed == []
