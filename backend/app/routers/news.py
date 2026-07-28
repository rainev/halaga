"""Reader-facing news feed, backed by GNews (gnews.io).

GET /api/news returns the most recent stored articles. When `refresh` is on
(the default) it first asks news_service to pull a fresh batch — that call is
TTL-guarded, so in practice it only hits GNews once per GNEWS_REFRESH_TTL_SEC
window and otherwise serves cache. POST /api/news/refresh forces a pull and is
admin-only (it spends against the daily quota).
"""

from fastapi import APIRouter

from ..deps import CronOrAdmin, CurrentUser
from ..models.news import NewsArticle
from ..services import news_service

router = APIRouter(prefix="/news", tags=["news"])

_SNIPPET_LEN = 280


def _to_article(row: dict) -> dict:
    body = (row.get("body") or "").strip()
    snippet = body[:_SNIPPET_LEN].rstrip()
    if len(body) > _SNIPPET_LEN:
        snippet += "…"
    return {
        "id": row["id"],
        "source": row["source"],
        "url": row["url"],
        "title": row["title"],
        "snippet": snippet or None,
        "published_at": row.get("published_at"),
    }


@router.get("", response_model=list[NewsArticle])
def list_news(user: CurrentUser, limit: int = 50, refresh: bool = True) -> list[dict]:
    """Recent articles, newest first. `refresh=false` skips the freshness check
    and returns cache immediately."""
    if refresh:
        news_service.refresh_gnews()  # TTL-guarded; usually a no-op
    return [_to_article(r) for r in news_service.list_recent(min(limit, 100))]


@router.post("/refresh")
def refresh_news(_caller: CronOrAdmin) -> dict:
    """Force a GNews pull now, bypassing the TTL. Returns the count stored.
    Callable by an admin (from the UI) or by Cloud Scheduler via X-Cron-Key."""
    return {"ingested": news_service.refresh_gnews(force=True)}
