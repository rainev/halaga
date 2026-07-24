"""News source adapters.

A `NewsSource` knows how to `fetch()` a batch of raw articles from somewhere.
The rest of the pipeline (dedupe, analyze, generate) is source-agnostic, so
adding a real feed later means implementing one class — nothing downstream
changes.

For now only `ManualSource` is wired (articles submitted via the admin API).
`PseEdgeSource` and vendor adapters are placeholders to fill in later.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


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


@dataclass
class NewsApiSource:
    """A third-party news API (e.g. NewsAPI.org / GNews). TODO: call the vendor
    with an API key and map its response into RawArticle rows."""

    name: str = "news_api"

    def fetch(self) -> list[RawArticle]:  # pragma: no cover - placeholder
        raise NotImplementedError("News API ingestion not implemented yet.")
