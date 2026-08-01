"""Combines every feature's router under a single /api router (see main.py)."""

from fastapi import APIRouter

from . import admin, auth, companies, health, us_valuations, valuations

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(companies.router)
api_router.include_router(valuations.router)
api_router.include_router(us_valuations.router)
