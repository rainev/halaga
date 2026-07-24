"""Admin-only routes. Gated by the require_admin dependency."""

from fastapi import APIRouter, BackgroundTasks, status

from ..deps import AdminUser
from ..env import env
from ..models.news import NewsItem, NewsSubmit
from ..news.sources import RawArticle
from ..pipeline import run as pipeline
from ..services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(_admin: AdminUser) -> dict:
    return {"users": user_service.list_public()}


@router.post("/news", response_model=NewsItem, status_code=status.HTTP_201_CREATED)
def submit_news(body: NewsSubmit, _admin: AdminUser, background: BackgroundTasks) -> dict:
    """Ingest one article (the ManualSource path). When PIPELINE_AUTO is on, the
    article is analyzed + turned into insights in the background so it shows up
    in feeds without a manual pipeline run."""
    stored = pipeline.submit(
        RawArticle(
            source=body.source, url=body.url, title=body.title,
            body=body.body, published_at=body.published_at,
        )
    )
    if env.PIPELINE_AUTO and stored["status"] == "pending":
        background.add_task(pipeline.process_article, stored)
    return stored


@router.post("/pipeline/run")
def run_pipeline(_admin: AdminUser, limit: int = 100) -> dict:
    """Manually run ingest -> analyze -> generate for all pending articles."""
    return pipeline.run(limit)
