"""User persistence. Raw SQL over the shared pool."""

from typing import Any

from ..db import query, query_one


def find_by_email(email: str) -> dict[str, Any] | None:
    return query_one("SELECT * FROM users WHERE email = %s", (email,))


def find_by_id(user_id: int) -> dict[str, Any] | None:
    return query_one("SELECT * FROM users WHERE id = %s", (user_id,))


def create(email: str, password_hash: str) -> dict[str, Any]:
    return query_one(
        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING *",
        (email, password_hash),
    )


def find_by_google_sub(google_sub: str) -> dict[str, Any] | None:
    return query_one("SELECT * FROM users WHERE google_sub = %s", (google_sub,))


def create_with_google(email: str, google_sub: str) -> dict[str, Any]:
    """A Google-only account: no password_hash. Email is trusted (Google verified
    it), so the account starts verified."""
    return query_one(
        "INSERT INTO users (email, google_sub, is_verified) VALUES (%s, %s, TRUE) "
        "RETURNING *",
        (email, google_sub),
    )


def link_google_sub(user_id: int, google_sub: str) -> dict[str, Any]:
    """Attach a Google identity to an existing (password) account with the same
    verified email, and mark it verified."""
    return query_one(
        "UPDATE users SET google_sub = %s, is_verified = TRUE, updated_at = now() "
        "WHERE id = %s RETURNING *",
        (google_sub, user_id),
    )


def list_public() -> list[dict[str, Any]]:
    """Safe columns only (no password hash) — used by the admin users listing."""
    return query("SELECT id, email, role, is_verified FROM users ORDER BY id")


def to_public(user: dict[str, Any]) -> dict[str, Any]:
    """The safe, client-facing shape of a user (never includes the hash)."""
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "is_verified": user["is_verified"],
    }
