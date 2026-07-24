"""News article persistence + ingestion.

Articles are global (not user-scoped). Dedupe is by URL (the table has a UNIQUE
constraint); re-ingesting the same URL is a no-op that returns the existing row.
Status moves pending -> analyzed (or failed) as the pipeline processes it.
"""

from typing import Any

from ..db import query, query_one
from ..news.sources import RawArticle


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
