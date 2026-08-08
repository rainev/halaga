"""FastAPI application factory + wiring.

Mirrors the talentNet Express app: CORS (credentialed, single origin for the
refresh cookie), feature routers under /api, and a central error handler that
turns thrown AppErrors into consistent JSON. Infra (DB pool, storage bucket) is
opened in the lifespan so importing this module never touches the network.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import pool
from .db_migrate import run_migrations
from .env import env
from .errors import AppError
from .routers import api_router
from .security.headers import add_security_headers
from .storage import ensure_bucket

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    pool.open()
    # Ensure the schema exists before serving. Essential for a managed DB
    # (Supabase, Neon, …) that never runs infrastructure/postgres/init/*.sql.
    # Skipped under tests, which run hermetically without a real database.
    if env.APP_ENV != "test":
        run_migrations()
    try:
        ensure_bucket()
    except Exception as exc:  # storage not ready shouldn't stop the API booting
        log.warning("Could not ensure storage bucket: %s", exc)
    yield
    pool.close()


app = FastAPI(title="PSE Valuation API", lifespan=lifespan)

# Secure response headers (Helmet-equivalent). Added first so it wraps every
# response, including CORS preflights and error responses.
add_security_headers(app)

# credentials=True + a specific origin is required for the refresh cookie to be
# sent/received cross-origin (Vite dev server -> API).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[env.CLIENT_URL],
    # Cloud Run exposes each service on two URL forms (project-number and hash);
    # accept either for the finsight staging/prod frontend so the app isn't
    # blocked depending on which URL the user opens.
    allow_origin_regex=r"https://finsight-frontend-(staging|prod)-[a-z0-9.-]+\.run\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


@app.exception_handler(Exception)
async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
    # Log the full error but return a generic message so we don't leak internals.
    log.exception("Unhandled request error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "Internal Server Error"})


app.include_router(api_router)
