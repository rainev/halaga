"""News + insight API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NewsSubmit(BaseModel):
    """Admin-submitted article (the ManualSource path)."""

    source: str = Field(default="manual", min_length=1, max_length=60)
    url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str | None = None
    published_at: datetime | None = None


class NewsItem(BaseModel):
    id: int
    source: str
    url: str
    title: str
    published_at: datetime | None = None
    status: str


class NewsArticle(BaseModel):
    """One row of the reader-facing /api/news feed: a stored article trimmed to
    what the UI shows (a snippet rather than the full body)."""

    id: int
    source: str
    url: str
    title: str
    snippet: str | None = None
    published_at: datetime | None = None


class FeedInsight(BaseModel):
    """One row of a user's holdings-scoped feed: the insight + its article and
    the company it concerns."""

    id: int
    company_id: int
    ticker: str
    name: str
    sector: str | None
    summary: str
    possible_impact: str
    direction: str | None
    confidence: float | None
    sources: list[dict[str, Any]]
    link_type: str
    article_title: str
    article_url: str
    published_at: datetime | None = None
    created_at: datetime
