"""Central configuration, read from the environment once at import.

Missing a required variable throws here, at startup, with a clear message —
instead of failing later with a cryptic DB/S3 error. The rest of the app can
therefore trust `env` to be complete.
"""

import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Env:
    # Server
    APP_ENV: str = os.environ.get("APP_ENV", "development")
    PORT: int = int(os.environ.get("PORT", "8000"))
    # Where the React app runs — needed for CORS + cookie handling.
    CLIENT_URL: str = os.environ.get("CLIENT_URL", "http://localhost:4000")

    # Refresh-cookie SameSite policy. Default "lax" for same-site local dev.
    # In staging/prod the frontend and backend live on different Cloud Run
    # domains, so the cross-site refresh cookie must be "none" (browsers then
    # also require Secure — enforced in routers/auth.py:_set_refresh_cookie).
    COOKIE_SAMESITE: str = os.environ.get("COOKIE_SAMESITE", "lax").lower()

    # Auth / JWT
    JWT_ACCESS_SECRET: str = _required("JWT_ACCESS_SECRET")
    JWT_REFRESH_SECRET: str = _required("JWT_REFRESH_SECRET")
    JWT_ACCESS_EXPIRES_MIN: int = int(os.environ.get("JWT_ACCESS_EXPIRES_MIN", "15"))
    JWT_REFRESH_EXPIRES_DAYS: int = int(os.environ.get("JWT_REFRESH_EXPIRES_DAYS", "7"))

    # Where Google Identity Services sends the browser back / the audience we
    # verify ID tokens against. Optional so the app boots without it; the
    # /auth/google endpoint returns a clear error until it's set. Must match the
    # frontend's VITE_GOOGLE_CLIENT_ID (the OAuth 2.0 Web client ID).
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")

    # Rate limiting. Disabled automatically under tests (no DB there).
    RATE_LIMIT_ENABLED: bool = (
        os.environ.get(
            "RATE_LIMIT_ENABLED",
            "false" if os.environ.get("APP_ENV") == "test" else "true",
        )
        == "true"
    )

    # PostgreSQL
    PGHOST: str = _required("PGHOST")
    PGPORT: int = int(_required("PGPORT"))
    PGUSER: str = _required("PGUSER")
    PGPASSWORD: str = _required("PGPASSWORD")
    PGDATABASE: str = _required("PGDATABASE")
    # Enable TLS for managed Postgres (Supabase, Neon, RDS, …). Off for the local
    # `db` container, which speaks plaintext on the compose network.
    PGSSL: bool = os.environ.get("PGSSL", "false") == "true"

    # OpenAI — powers the news→insight analysis (see docs/architecture.md).
    # Optional: with no key the deterministic parts of the pipeline still run
    # (ticker matching, sector tagging); the LLM steps are skipped.
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    # Insight writing: employer-facing reasoning under guardrails — strong model.
    OPENAI_INSIGHT_MODEL: str = os.environ.get("OPENAI_INSIGHT_MODEL", "gpt-4o")
    # Bulk classification / entity extraction — a cheap model is plenty.
    OPENAI_EXTRACT_MODEL: str = os.environ.get("OPENAI_EXTRACT_MODEL", "gpt-4o-mini")
    # Embeddings for pgvector thematic matching. text-embedding-3-small -> 1536,
    # which must match the news_items.embedding column dimension.
    OPENAI_EMBED_MODEL: str = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    # GNews (gnews.io) — hosted news search that feeds the /api/news feed and the
    # insights pipeline. Optional: with no key GNews ingestion is skipped and the
    # manual submit path still works.
    # `or default` (not get's default) so a present-but-empty value — how
    # docker-compose passes an unset optional var — still falls back to the default.
    GNEWS_API_KEY: str = os.environ.get("GNEWS_API_KEY", "")
    # Search query for PSE-relevant headlines. GNews supports quoted phrases and
    # AND/OR operators; the default targets the Philippine market.
    # Broader beats a narrow query: a term like just "Philippine Stock Exchange"
    # misses same-day market stories (peso/PSEi moves, earnings) that never name
    # the exchange in full. GNews still sorts these newest-first for us.
    GNEWS_QUERY: str = os.environ.get("GNEWS_QUERY") or (
        '"Philippine Stock Exchange" OR PSEi OR "Philippine stocks" '
        'OR "Philippine economy" OR "Philippine peso"'
    )
    GNEWS_LANG: str = os.environ.get("GNEWS_LANG") or "en"
    GNEWS_COUNTRY: str = os.environ.get("GNEWS_COUNTRY") or "ph"
    # Articles per pull. The free tier caps a request at 10.
    GNEWS_MAX: int = int(os.environ.get("GNEWS_MAX") or "10")
    # Don't re-hit GNews more often than this many seconds — the free tier allows
    # only ~100 requests/day, so /api/news serves cache and refreshes sparingly.
    GNEWS_REFRESH_TTL_SEC: int = int(os.environ.get("GNEWS_REFRESH_TTL_SEC") or "900")
    # Shared secret that lets an automated caller (Cloud Scheduler) trigger
    # POST /api/news/refresh via an `X-Cron-Key` header instead of an admin login.
    # Blank (dev default) disables that path entirely — the endpoint stays
    # admin-JWT-only. Set to a long random string in production.
    NEWS_CRON_SECRET: str = os.environ.get("NEWS_CRON_SECRET", "")

    # Insights pipeline.
    # Only generate an insight for an (article, company) link at/above this
    # confidence, so low-signal matches don't create noise.
    INSIGHT_CONFIDENCE_THRESHOLD: float = float(
        os.environ.get("INSIGHT_CONFIDENCE_THRESHOLD", "0.5")
    )
    # When true, submitting an article (admin /news) immediately analyzes it and
    # generates insights in the background. When false (default), the pipeline is
    # run explicitly via POST /admin/pipeline/run or the CLI.
    PIPELINE_AUTO: bool = os.environ.get("PIPELINE_AUTO", "false") == "true"

    # Object storage (MinIO in dev, S3/Spaces in prod)
    MINIO_ENDPOINT: str = _required("MINIO_ENDPOINT")
    MINIO_ROOT_USER: str = _required("MINIO_ROOT_USER")
    MINIO_ROOT_PASSWORD: str = _required("MINIO_ROOT_PASSWORD")
    MINIO_BUCKET: str = _required("MINIO_BUCKET")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


env = Env()
