"""Saved valuation runs. inputs/assumptions/result are persisted as JSONB so a
run is fully reproducible even if the engine defaults later change."""

from typing import Any

from psycopg.types.json import Json

from ..db import query, query_one


def save(
    *,
    user_id: int,
    company_id: int | None,
    model: str,
    inputs: dict,
    assumptions: dict,
    result: dict,
) -> dict[str, Any]:
    return query_one(
        """
        INSERT INTO valuations (user_id, company_id, model, inputs, assumptions, result)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, company_id, model, inputs, assumptions, result, created_at
        """,
        (user_id, company_id, model, Json(inputs), Json(assumptions), Json(result)),
    )


def list_for_user(user_id: int) -> list[dict[str, Any]]:
    return query(
        """
        SELECT id, company_id, model, inputs, assumptions, result, created_at
        FROM valuations WHERE user_id = %s ORDER BY created_at DESC
        """,
        (user_id,),
    )


def get(user_id: int, valuation_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT id, company_id, model, inputs, assumptions, result, created_at
        FROM valuations WHERE id = %s AND user_id = %s
        """,
        (valuation_id, user_id),
    )


def delete(user_id: int, valuation_id: int) -> bool:
    row = query_one(
        "DELETE FROM valuations WHERE id = %s AND user_id = %s RETURNING id",
        (valuation_id, user_id),
    )
    return row is not None
