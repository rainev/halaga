"""Insights feed. Holdings-scoped to the authenticated user (see feed_service)."""

from fastapi import APIRouter

from ..deps import CurrentUser
from ..models.news import FeedInsight
from ..services import feed_service

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=list[FeedInsight])
def my_feed(user: CurrentUser, limit: int = 50) -> list[dict]:
    return feed_service.feed_for_user(user["sub"], min(limit, 100))
