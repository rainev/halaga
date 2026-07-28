"""Pipeline orchestration: ingest -> analyze -> generate insights.

Each stage is a plain function so it's testable and can be driven three ways:
  - the admin endpoint POST /api/admin/pipeline/run
  - this module as a CLI:  python -m app.pipeline.run
  - automatically on submit, when PIPELINE_AUTO is enabled (see routers/admin.py)

analyze/matching is deterministic and runs without an API key; insight
generation needs OpenAI, so without a key articles stop at status 'analyzed'
and a later run (with a key) produces the insights.
"""

import logging
from typing import Any

from ..ai import analyzer, insight_generator
from ..env import env
from ..news.sources import GNewsSource, ManualSource, NewsSource, RawArticle
from ..services import article_service, company_service, insight_service, news_service

log = logging.getLogger("uvicorn.error")

# The default source: articles submitted via the admin API are queued here and
# drained by ingest(). GNewsSource pulls PSE-relevant headlines from gnews.io and
# is a no-op when GNEWS_API_KEY is unset, so it's safe to include unconditionally.
manual_source = ManualSource()
SOURCES: list[NewsSource] = [manual_source, GNewsSource()]


def submit(article: RawArticle) -> dict[str, Any]:
    """Ingest a single article immediately (used by the admin submit endpoint).
    Returns the stored news_items row."""
    return news_service.ingest(article)


def ingest() -> list[dict[str, Any]]:
    """Drain every source into news_items. Returns the stored rows."""
    stored: list[dict[str, Any]] = []
    for source in SOURCES:
        for raw in source.fetch():
            stored.append(news_service.ingest(raw))
    return stored


def generate_for_article(article: dict[str, Any]) -> int:
    """Generate insights for an already-analyzed article's stock links that clear
    the confidence threshold. Idempotent (skips links that already have one)."""
    made = 0
    for link in article_service.stocks_for_article(article["id"]):
        if (link.get("relevance") or 0) < env.INSIGHT_CONFIDENCE_THRESHOLD:
            continue
        if article_service.has_insight(article["id"], link["company_id"]):
            continue
        data = insight_generator.generate(article, link)
        if data is None:
            continue
        insight_service.upsert(
            article["id"], link["company_id"], data["summary"], data["possible_impact"],
            data.get("direction"), data.get("confidence"), data["sources"],
        )
        made += 1
    return made


def process_article(article: dict[str, Any], companies: list[dict] | None = None) -> dict[str, int]:
    """Analyze one article, then generate its insights. Marks it 'done' once
    insights are attempted (only when OpenAI is configured — otherwise it stays
    'analyzed' for a later pass)."""
    analyzer.analyze(article, companies)
    fresh = news_service.get(article["id"]) or article
    insights = generate_for_article(fresh)
    if insight_generator.openai_client.is_enabled():
        news_service.set_status(article["id"], "done")
    return {"insights": insights}


def process_pending(limit: int = 100) -> dict[str, int]:
    """Analyze + generate for every pending article."""
    companies = company_service.list_all()
    pending = news_service.list_pending(limit)
    total_insights = 0
    for article in pending:
        total_insights += process_article(article, companies)["insights"]
    return {"articles": len(pending), "insights": total_insights}


def run(limit: int = 100) -> dict[str, int]:
    """Full cycle: pull from sources, then analyze + generate for everything
    pending. Returns a summary for logging / the admin response."""
    ingested = ingest()
    result = process_pending(limit)
    result["ingested"] = len(ingested)
    log.info("Pipeline run: %s", result)
    return result


if __name__ == "__main__":  # CLI / cron target
    logging.basicConfig(level=logging.INFO)
    # env.py reads config from the process env; load .env via your shell/compose.
    from ..db import pool

    pool.open()
    try:
        print(run())
    finally:
        pool.close()
