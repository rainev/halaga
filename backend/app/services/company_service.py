"""Company persistence."""

from typing import Any

from ..db import query, query_one


def list_all(sector: str | None = None) -> list[dict[str, Any]]:
    if sector:
        return query(
            "SELECT id, ticker, name, sector, currency FROM companies "
            "WHERE sector = %s ORDER BY ticker",
            (sector,),
        )
    return query("SELECT id, ticker, name, sector, currency FROM companies ORDER BY ticker")


def get(company_id: int) -> dict[str, Any] | None:
    return query_one(
        "SELECT id, ticker, name, sector, currency FROM companies WHERE id = %s",
        (company_id,),
    )


def get_by_ticker(ticker: str) -> dict[str, Any] | None:
    return query_one(
        "SELECT id, ticker, name, sector, currency FROM companies WHERE ticker = %s",
        (ticker,),
    )


def upsert(ticker: str, name: str, sector: str | None, currency: str = "PHP") -> dict[str, Any]:
    """Insert or update by ticker. Used by the create route and the seed."""
    return query_one(
        """
        INSERT INTO companies (ticker, name, sector, currency)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ticker) DO UPDATE
          SET name = EXCLUDED.name,
              sector = EXCLUDED.sector,
              currency = EXCLUDED.currency
        RETURNING id, ticker, name, sector, currency
        """,
        (ticker, name, sector, currency),
    )
