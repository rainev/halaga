"""Holdings persistence — a user's watchlist of owned companies. Raw SQL over the
shared pool. Every query is scoped by user_id so one user can never touch
another's holdings.
"""

from typing import Any

from ..db import query, query_one
from ..errors import AppError
from . import company_service

# The client-facing shape: the holding joined to its company.
_SELECT = """
  SELECT h.id, h.company_id, c.ticker, c.name, c.sector
  FROM holdings h
  JOIN companies c ON c.id = h.company_id
"""


def list_for_user(user_id: int) -> list[dict[str, Any]]:
    return query(_SELECT + " WHERE h.user_id = %s ORDER BY c.ticker", (user_id,))


def _get(user_id: int, holding_id: int) -> dict[str, Any] | None:
    return query_one(_SELECT + " WHERE h.id = %s AND h.user_id = %s", (holding_id, user_id))


def add(user_id: int, ticker: str) -> dict[str, Any]:
    company = company_service.get_by_ticker(ticker.upper())
    if not company:
        raise AppError(f"No PSE company found for ticker '{ticker}'.", 404)

    # Idempotent per (user, company): re-adding a held ticker is a no-op.
    query(
        "INSERT INTO holdings (user_id, company_id) VALUES (%s, %s) "
        "ON CONFLICT (user_id, company_id) DO NOTHING",
        (user_id, company["id"]),
    )
    return query_one(
        _SELECT + " WHERE h.user_id = %s AND h.company_id = %s", (user_id, company["id"])
    )


def remove(user_id: int, holding_id: int) -> None:
    if not _get(user_id, holding_id):
        raise AppError("Holding not found", 404)
    query("DELETE FROM holdings WHERE id = %s AND user_id = %s", (holding_id, user_id))
