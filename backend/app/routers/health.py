"""Liveness + dependency status. No auth."""

from fastapi import APIRouter

from ..db import query_one

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/status")
def status() -> dict:
    # Postgres is the only stateful dependency now (sessions + rate limits live
    # there too, alongside the app data).
    checks = {"db": False}
    try:
        query_one("SELECT 1 AS ok")
        checks["db"] = True
    except Exception:
        pass
    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
