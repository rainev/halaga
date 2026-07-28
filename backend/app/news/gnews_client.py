"""Client for GNews (gnews.io) — a hosted news search / headlines API.

Unlike the PSE EDGE scraper (pse/edge_client.py) this is a first-class JSON API:
authenticate with an `apikey` query parameter and read back an `articles` array.
The free tier is tightly rate-limited (~100 requests/day, <=10 articles per
request, truncated `content`), so callers must cache and refresh sparingly — see
services/news_service.refresh_gnews, which guards calls behind a TTL.

The client only talks HTTP + JSON; mapping the vendor payload into the
source-agnostic RawArticle lives in news/sources.py (GNewsSource) to keep this
module free of pipeline concerns and avoid an import cycle.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from ..env import env

log = logging.getLogger("uvicorn.error")

BASE = "https://gnews.io/api/v4"
UA = "FinSight/1.0 (+https://finsight.app)"


class GNewsClient:
    """A thin, retrying wrapper over the GNews REST API.

    Construct with no args to read the key/timeouts from env. `is_enabled()`
    reports whether a key is configured so callers can no-op cleanly.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        throttle: float = 1.0,
        timeout: float = 15.0,
        retries: int = 3,
    ):
        self.api_key = env.GNEWS_API_KEY if api_key is None else api_key
        self.throttle = throttle
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept": "application/json"})

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    # -- low-level request plumbing -----------------------------------------
    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET a GNews endpoint and return the decoded JSON body. Retries on
        transient failures (5xx / 429 / network) with exponential backoff; a
        4xx like 401 (bad key) or 403 (quota exhausted) raises immediately."""
        if not self.api_key:
            raise RuntimeError("GNEWS_API_KEY is not configured")
        url = f"{BASE}{path}"
        query = {**params, "apikey": self.api_key}
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, params=query, timeout=self.timeout)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise requests.HTTPError(f"{resp.status_code} from GNews {path}")
                resp.raise_for_status()  # surfaces 401/403/400 without retrying
                return resp.json()
            except requests.HTTPError as exc:
                # Non-retryable client errors (bad key, quota, bad query): stop now.
                status = exc.response.status_code if exc.response is not None else None
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
                last_exc = exc
            except requests.RequestException as exc:  # timeout / connection reset
                last_exc = exc
            backoff = self.throttle * (2 ** (attempt - 1))
            log.warning(
                "GNews GET %s failed (attempt %d/%d): %s", path, attempt, self.retries, exc
            )
            if attempt < self.retries:
                time.sleep(backoff)
        raise RuntimeError(f"GNews request failed after {self.retries} tries: {path}") from last_exc

    # -- public endpoints ---------------------------------------------------
    def search(
        self, query: str, *, lang: str, country: str, max_articles: int
    ) -> list[dict[str, Any]]:
        """Full-text search, newest first. Returns the raw `articles` array."""
        data = self._get(
            "/search",
            {
                "q": query,
                "lang": lang,
                "country": country,
                "max": max_articles,
                "sortby": "publishedAt",  # freshest first, not relevance-ranked
            },
        )
        return data.get("articles") or []

    def top_headlines(
        self, *, category: str, lang: str, country: str, max_articles: int
    ) -> list[dict[str, Any]]:
        """Category top headlines (e.g. `business`). Returns the raw `articles`."""
        data = self._get(
            "/top-headlines",
            {"category": category, "lang": lang, "country": country, "max": max_articles},
        )
        return data.get("articles") or []
