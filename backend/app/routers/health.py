"""Liveness + dependency status. No auth."""

from fastapi import APIRouter

from ..db import query_one
from ..redis_client import client

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/status")
def status() -> dict:
    checks = {"db": False, "redis": False}
    try:
        query_one("SELECT 1 AS ok")
        checks["db"] = True
    except Exception:
        pass
    try:
        checks["redis"] = client.ping()
    except Exception:
        pass
    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
