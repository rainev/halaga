"""News article persistence + ingestion.

Articles are global (not user-scoped). Dedupe is by URL (the table has a UNIQUE
constraint); re-ingesting the same URL is a no-op that returns the existing row.
Status moves pending -> analyzed (or failed) as the pipeline processes it.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from ..db import query, query_one
from ..env import env
from ..news.sources import GNewsSource, RawArticle

log = logging.getLogger("uvicorn.error")


def ingest(article: RawArticle) -> dict[str, Any]:
    """Store a raw article, or return the existing row if the URL is already
    known. New rows start as status='pending'."""
    return query_one(
        """
        INSERT INTO news_items (source, url, title, body, published_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (url) DO UPDATE SET url = EXCLUDED.url
        RETURNING id, source, url, title, body, published_at, status
        """,
        (article.source, article.url, article.title, article.body, article.published_at),
    )


def get(news_item_id: int) -> dict[str, Any] | None:
    return query_one("SELECT * FROM news_items WHERE id = %s", (news_item_id,))


def list_pending(limit: int = 100) -> list[dict[str, Any]]:
    return query(
        "SELECT * FROM news_items WHERE status = 'pending' "
        "ORDER BY created_at ASC LIMIT %s",
        (limit,),
    )


def set_status(news_item_id: int, status: str) -> None:
    query("UPDATE news_items SET status = %s WHERE id = %s", (status, news_item_id))


def set_embedding(news_item_id: int, embedding: list[float]) -> None:
    # pgvector accepts the text form '[0.1,0.2,...]'.
    literal = "[" + ",".join(str(x) for x in embedding) + "]"
    query("UPDATE news_items SET embedding = %s WHERE id = %s", (literal, news_item_id))


# --- Retrieval + external refresh (the /api/news feed) ---------------------


def list_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Most recent articles for the reader-facing feed, newest first. Orders by
    the article's own publish time, falling back to when we ingested it."""
    return query(
        """
        SELECT id, source, url, title, body, published_at, status, created_at
        FROM news_items
        ORDER BY COALESCE(published_at, created_at) DESC
        LIMIT %s
        """,
        (limit,),
    )


def last_ingested_at(source: str) -> datetime | None:
    """When we last stored an article from `source` (created_at is TIMESTAMPTZ,
    so this comes back timezone-aware). None if we've never pulled from it."""
    row = query_one(
        "SELECT MAX(created_at) AS ts FROM news_items WHERE source = %s", (source,)
    )
    return row["ts"] if row else None


def refresh_gnews(*, force: bool = False) -> int:
    """Pull a fresh batch from GNews into news_items, deduped by URL.

    Guarded by GNEWS_REFRESH_TTL_SEC so we don't burn the (small) daily request
    quota: unless `force`, this is a no-op if we pulled within the TTL window.
    Network/vendor errors are logged and swallowed — a GNews outage must never
    break the feed, which can always fall back to whatever's already cached.

    Returns the number of articles stored (new + refreshed); 0 when skipped or
    when GNews isn't configured.
    """
    if not env.GNEWS_API_KEY:
        return 0
    if not force:
        last = last_ingested_at("gnews")
        if last is not None:
            age = (datetime.now(timezone.utc) - last).total_seconds()
            if age < env.GNEWS_REFRESH_TTL_SEC:
                return 0
    try:
        articles = GNewsSource().fetch()
    except Exception:  # network, bad key, quota — keep serving cache
        log.warning("GNews refresh failed; serving cached articles", exc_info=True)
        return 0
    stored = 0
    for raw in articles:
        try:
            ingest(raw)
            stored += 1
        except Exception:
            log.warning("Failed to store GNews article %s", raw.url, exc_info=True)
    return stored
