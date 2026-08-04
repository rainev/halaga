"""Combines every feature's router under a single /api router (see main.py)."""

from fastapi import APIRouter, Depends

from ..security.rate_limit import RateLimiter
from . import (
    admin,
    auth,
    companies,
    health,
    holdings,
    insights,
    news,
    research,
    us_valuations,
    valuations,
)

# Baseline per-IP ceiling across the API. Applied to every feature router; the
# auth router layers a tighter limit on top of it (see auth.py). Health/status
# are left out so load balancers and the Docker healthcheck can poll freely.
_general = RateLimiter("general", window_sec=60, max_hits=120)
_limited = [Depends(_general)]

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router, dependencies=_limited)
api_router.include_router(admin.router, dependencies=_limited)
api_router.include_router(companies.router, dependencies=_limited)
api_router.include_router(holdings.router, dependencies=_limited)
api_router.include_router(insights.router, dependencies=_limited)
api_router.include_router(news.router, dependencies=_limited)
api_router.include_router(research.router, dependencies=_limited)
api_router.include_router(us_valuations.router, dependencies=_limited)
api_router.include_router(valuations.router, dependencies=_limited)
