"""Postgres-backed rate limiting — a fixed-window counter per key (IP or user).

Because the counter lives in Postgres (shared by every backend instance), the
limit holds across instances. This blunts abuse, brute-force, and credential
stuffing. It does NOT stop a volumetric DDoS — that needs an edge layer
(Cloudflare / a load balancer). Consolidated here from Redis so staging needs
only one datastore — see docs/DEPLOY-staging.md.

Used as a FastAPI dependency so a route (or a whole router) can opt into a limit:

    strict = RateLimiter("auth", window_sec=900, max_hits=15)

    @router.post("/login", dependencies=[Depends(strict)])
    def login(...): ...

If the store is briefly unavailable we fail OPEN (a rate-limit backend hiccup
shouldn't take the API down).
"""

import logging

from fastapi import Request, Response

from ..db import query_one
from ..env import env
from ..errors import AppError

log = logging.getLogger("uvicorn.error")


def _client_ip(request: Request) -> str:
    """The client's IP. Honors X-Forwarded-For when present (behind Cloudflare /
    a load balancer); otherwise the socket peer. We take the first hop in the
    XFF list, which the trusted proxy sets to the real client."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """A configured limiter. Instances are FastAPI dependencies (callable)."""

    def __init__(
        self,
        key_prefix: str,
        *,
        window_sec: int,
        max_hits: int,
        by: str = "ip",  # "ip" or "user" (falls back to IP when unauthenticated)
    ) -> None:
        self.key_prefix = key_prefix
        self.window_sec = window_sec
        self.max_hits = max_hits
        self.by = by

    def _who(self, request: Request) -> str:
        # `by="user"` keys on the authenticated user id when the access token is
        # present and valid; otherwise it degrades to per-IP.
        if self.by == "user":
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                # Import here to avoid a cycle (deps -> security -> deps).
                from .jwt import TokenError, verify_access_token

                try:
                    payload = verify_access_token(auth[len("Bearer ") :])
                    return f"u:{payload['sub']}"
                except TokenError:
                    pass
        return f"ip:{_client_ip(request)}"

    async def __call__(self, request: Request, response: Response) -> None:
        if not env.RATE_LIMIT_ENABLED:
            return

        key = f"rl:{self.key_prefix}:{self._who(request)}"
        try:
            # One atomic upsert = the whole fixed-window step: start a new window
            # (count=1) when the row is absent or its window has elapsed,
            # otherwise increment. RETURNING gives the new count and the seconds
            # left in the window (for Retry-After).
            row = query_one(
                """
                INSERT INTO rate_limits (key, count, reset_at)
                VALUES (%s, 1, now() + make_interval(secs => %s))
                ON CONFLICT (key) DO UPDATE SET
                  count = CASE WHEN rate_limits.reset_at <= now()
                               THEN 1 ELSE rate_limits.count + 1 END,
                  reset_at = CASE WHEN rate_limits.reset_at <= now()
                                  THEN now() + make_interval(secs => %s)
                                  ELSE rate_limits.reset_at END
                RETURNING count,
                          GREATEST(0, CEIL(EXTRACT(EPOCH FROM (reset_at - now()))))::int AS ttl
                """,
                (key, self.window_sec, self.window_sec),
            )
            count = row["count"]
            ttl = row["ttl"]

            response.headers["X-RateLimit-Limit"] = str(self.max_hits)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_hits - count))

            if count > self.max_hits:
                if ttl > 0:
                    response.headers["Retry-After"] = str(ttl)
                raise AppError(
                    "Too many requests — please slow down and try again.", 429
                )
        except AppError:
            raise
        except Exception as exc:  # store blip: fail open, don't take the API down.
            log.warning("Rate limiter unavailable, allowing request: %s", exc)
