"""Analyze step: work out what an article affects (stocks + sectors).

This is a property of the article, shared by all users — no user data involved.
Deterministic first (ticker + company-name matching, plus a macro theme -> sector
map), with an optional OpenAI embedding stored for future semantic matching. The
whole step runs without an API key; only the embedding is skipped when absent.
"""

import logging
import re
from typing import Any

from ..env import env
from ..services import article_service, company_service, news_service
from . import openai_client
from .themes import detect_themes

log = logging.getLogger("uvicorn.error")

# Relevance scores for each kind of link (0..1).
_R_TICKER = 1.0     # article names the ticker outright
_R_NAME = 0.9       # article names the company
_R_THEMATIC = 0.55  # company only implicated via a macro theme -> its sector

# Bound thematic fan-out (and thus OpenAI cost) per article. Companies beyond
# this are dropped with a log line — never silently.
_MAX_THEMATIC_STOCKS = 15


def _article_text(article: dict[str, Any]) -> str:
    return f"{article.get('title') or ''}\n{article.get('body') or ''}".strip()


def _direct_matches(text: str, companies: list[dict]) -> dict[int, float]:
    """company_id -> relevance for companies the article names directly."""
    matches: dict[int, float] = {}
    for c in companies:
        ticker = (c["ticker"] or "").strip()
        # Ticker: whole-word, case-sensitive (avoids 'AB' matching 'about').
        if ticker and re.search(rf"\b{re.escape(ticker)}\b", text):
            matches[c["id"]] = _R_TICKER
            continue
        # Company name: case-insensitive, but only for names distinctive enough
        # not to false-positive (>= 5 chars).
        name = (c["name"] or "").strip()
        if len(name) >= 5 and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            matches[c["id"]] = _R_NAME
    return matches


def analyze(article: dict[str, Any], companies: list[dict] | None = None) -> dict[str, int]:
    """Tag one article. Writes article_stocks / article_sectors and marks the
    article 'analyzed'. Returns counts for logging/tests."""
    news_item_id = article["id"]
    if companies is None:
        companies = company_service.list_all()
    by_id = {c["id"]: c for c in companies}
    text = _article_text(article)

    # 1) Direct stock matches + their sectors.
    direct = _direct_matches(text, companies)
    sectors_hit: dict[str, tuple[str, float]] = {}  # sector -> (link_type, relevance)
    for company_id, relevance in direct.items():
        article_service.upsert_stock(news_item_id, company_id, "direct", relevance)
        sector = by_id[company_id]["sector"]
        if sector:
            sectors_hit[sector] = ("direct", max(sectors_hit.get(sector, ("", 0))[1], relevance))

    # 2) Thematic: macro themes -> affected sectors -> companies in them.
    themes = detect_themes(text)
    thematic_sectors = {s for t in themes for s in t.sectors}
    for sector in thematic_sectors:
        # Don't downgrade a sector already hit directly.
        if sector not in sectors_hit:
            sectors_hit[sector] = ("thematic", _R_THEMATIC)

    thematic_company_ids = [
        c["id"]
        for c in companies
        if c["sector"] in thematic_sectors and c["id"] not in direct
    ]
    if len(thematic_company_ids) > _MAX_THEMATIC_STOCKS:
        log.info(
            "Article %s: capping thematic stocks %d -> %d",
            news_item_id, len(thematic_company_ids), _MAX_THEMATIC_STOCKS,
        )
        thematic_company_ids = thematic_company_ids[:_MAX_THEMATIC_STOCKS]
    for company_id in thematic_company_ids:
        article_service.upsert_stock(news_item_id, company_id, "thematic", _R_THEMATIC)

    # 3) Persist sector links.
    for sector, (link_type, relevance) in sectors_hit.items():
        article_service.upsert_sector(news_item_id, sector, link_type, relevance)

    # 4) Optional embedding for future semantic matching (skipped without a key).
    _maybe_embed(news_item_id, text)

    news_service.set_status(news_item_id, "analyzed")
    counts = {
        "direct_stocks": len(direct),
        "thematic_stocks": len(thematic_company_ids),
        "sectors": len(sectors_hit),
    }
    log.info("Analyzed article %s: %s", news_item_id, counts)
    return counts


def _maybe_embed(news_item_id: int, text: str) -> None:
    oa = openai_client.client()
    if oa is None or not text:
        return
    try:
        resp = oa.embeddings.create(model=env.OPENAI_EMBED_MODEL, input=text[:8000])
        news_service.set_embedding(news_item_id, resp.data[0].embedding)
    except Exception as exc:  # embedding is best-effort — never fail the analyze
        log.warning("Embedding failed for article %s: %s", news_item_id, exc)
