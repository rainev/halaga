"""News source adapters.

A `NewsSource` knows how to `fetch()` a batch of raw articles from somewhere.
The rest of the pipeline (dedupe, analyze, generate) is source-agnostic, so
adding a real feed later means implementing one class — nothing downstream
changes.

For now only `ManualSource` is wired (articles submitted via the admin API).
`PseEdgeSource` and vendor adapters are placeholders to fill in later.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from ..env import env

log = logging.getLogger("uvicorn.error")


@dataclass
class RawArticle:
    """A source-agnostic article, before it's stored or analyzed."""

    source: str
    url: str
    title: str
    body: str | None = None
    published_at: datetime | None = None


class NewsSource(Protocol):
    """Anything that can supply articles. `name` labels stored rows."""

    name: str

    def fetch(self) -> list[RawArticle]:
        ...


@dataclass
class ManualSource:
    """Articles handed in explicitly (via the admin submit endpoint). `fetch()`
    just drains whatever was queued into this instance."""

    name: str = "manual"
    _queued: list[RawArticle] = field(default_factory=list)

    def add(self, article: RawArticle) -> None:
        self._queued.append(article)

    def fetch(self) -> list[RawArticle]:
        drained, self._queued = self._queued, []
        return drained


# --- Placeholders — implement when a real feed is chosen -------------------
# Each just needs a `fetch()` that returns list[RawArticle]; the pipeline does
# the rest. Kept as stubs so the interface is nailed down now.


@dataclass
class PseEdgeSource:
    """Official PSE EDGE disclosures — highest-signal source. TODO: scrape/parse
    the disclosure feed into RawArticle rows."""

    name: str = "pse_edge"

    def fetch(self) -> list[RawArticle]:  # pragma: no cover - placeholder
        raise NotImplementedError("PSE EDGE ingestion not implemented yet.")


def _parse_published(value: str | None) -> datetime | None:
    """GNews stamps articles as ISO-8601 with a 'Z' suffix; normalize to an
    aware datetime (or None if absent/unparseable)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_raw(article: dict) -> RawArticle | None:
    """Map one GNews article into a RawArticle, or None if it lacks the url/title
    the pipeline needs. `content` (truncated on the free tier) is preferred over
    `description` as the body since it gives the analyzer more to match on."""
    url = (article.get("url") or "").strip()
    title = (article.get("title") or "").strip()
    if not url or not title:
        return None
    body = article.get("content") or article.get("description")
    return RawArticle(
        source="gnews",
        url=url,
        title=title,
        body=body,
        published_at=_parse_published(article.get("publishedAt")),
    )


@dataclass
class GNewsSource:
    """Pulls PSE-relevant headlines from GNews (gnews.io). Search parameters
    default to the GNEWS_* env config but can be overridden per instance.

    `fetch()` is a safe no-op when no API key is configured, so this source can
    sit in the pipeline's SOURCES list unconditionally.
    """

    name: str = "gnews"
    query: str | None = None
    lang: str | None = None
    country: str | None = None
    max_articles: int | None = None

    def fetch(self) -> list[RawArticle]:
        # Imported lazily so this module has no import-time dependency on the
        # HTTP client (and no cycle: gnews_client does not import sources).
        from .gnews_client import GNewsClient

        client = GNewsClient()
        if not client.is_enabled():
            return []
        raw = client.search(
            self.query or env.GNEWS_QUERY,
            lang=self.lang or env.GNEWS_LANG,
            country=self.country or env.GNEWS_COUNTRY,
            max_articles=self.max_articles or env.GNEWS_MAX,
        )
        articles = [a for a in (_to_raw(x) for x in raw) if a is not None]
        log.info("GNews fetch: %d articles", len(articles))
        return articles
