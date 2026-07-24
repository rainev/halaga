"""Redis-backed rate limiting — a fixed-window counter per key (IP or user).

Because the counter lives in Redis, the limit holds across multiple backend
instances. This blunts abuse, brute-force, and credential stuffing. It does NOT
stop a volumetric DDoS — that needs an edge layer (Cloudflare / a load balancer).

Used as a FastAPI dependency so a route (or a whole router) can opt into a limit:

    strict = RateLimiter("auth", window_sec=900, max_hits=15)

    @router.post("/login", dependencies=[Depends(strict)])
    def login(...): ...

If Redis is briefly unavailable we fail OPEN (a rate-limit backend hiccup
shouldn't take the API down).
"""

import logging

from fastapi import Request, Response

from ..env import env
from ..errors import AppError
from ..redis_client import client

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
            count = client.incr(key)
            if count == 1:
                client.expire(key, self.window_sec)

            response.headers["X-RateLimit-Limit"] = str(self.max_hits)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_hits - count))

            if count > self.max_hits:
                ttl = client.ttl(key)
                if ttl > 0:
                    response.headers["Retry-After"] = str(ttl)
                raise AppError(
                    "Too many requests — please slow down and try again.", 429
                )
        except AppError:
            raise
        except Exception as exc:  # Redis blip: fail open, don't take the API down.
            log.warning("Rate limiter unavailable, allowing request: %s", exc)
