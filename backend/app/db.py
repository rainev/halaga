"""Postgres access via a psycopg connection pool.

Deliberately thin: services write raw SQL and call `query` / `query_one` /
`execute`. No ORM — the SQL is the source of truth, same as the DB schema in
infrastructure/postgres/init. Rows come back as plain dicts (`dict_row`).
"""

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .env import env

_conninfo = (
    f"host={env.PGHOST} port={env.PGPORT} user={env.PGUSER} "
    f"password={env.PGPASSWORD} dbname={env.PGDATABASE}"
    # Managed providers (Supabase, Neon, RDS) require TLS. `require` encrypts
    # without verifying the CA — fine for staging; use verify-full + a CA in prod.
    + (" sslmode=require" if env.PGSSL else "")
)

# open=False so importing this module never blocks on a DB connection (keeps the
# test suite and tooling hermetic). The pool is opened in the app lifespan.
pool = ConnectionPool(
    _conninfo,
    open=False,
    kwargs={"row_factory": dict_row},
    min_size=0,  # connect on demand — no eager connection at startup
    max_size=10,
)


def query(sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    """Run a statement and return all rows (empty list for writes with no RETURNING)."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return []
        return cur.fetchall()


def query_one(sql: str, params: tuple | list | None = None) -> dict[str, Any] | None:
    """Run a statement and return the first row, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None
