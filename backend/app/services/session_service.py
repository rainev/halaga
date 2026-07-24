"""Refresh-token sessions, stored in Postgres.

This is what makes refresh tokens revocable: a token is only honored while its
jti still has a live row here.

    sessions(jti PK, user_id, expires_at)

`expires_at` carries the refresh token's lifetime; is_valid() ignores expired
rows, and create() opportunistically prunes a user's expired rows so the table
doesn't grow unbounded (a periodic sweep can prune the rest later). Consolidated
here from Redis so staging needs only one datastore — see docs/DEPLOY-staging.md.
"""

from ..db import query, query_one
from ..env import env

REFRESH_TTL_SECONDS = env.JWT_REFRESH_EXPIRES_DAYS * 24 * 60 * 60


def create(user_id: int, jti: str) -> None:
    """Record a live session for a freshly-issued refresh token."""
    query(
        """
        INSERT INTO sessions (jti, user_id, expires_at)
        VALUES (%s, %s, now() + make_interval(secs => %s))
        ON CONFLICT (jti) DO UPDATE
          SET user_id = EXCLUDED.user_id, expires_at = EXCLUDED.expires_at
        """,
        (jti, int(user_id), REFRESH_TTL_SECONDS),
    )
    # Opportunistic cleanup: retire this user's already-expired sessions.
    query(
        "DELETE FROM sessions WHERE user_id = %s AND expires_at <= now()",
        (int(user_id),),
    )


def is_valid(jti: str) -> bool:
    """True only if the jti is still a live session (not rotated away, revoked,
    or expired)."""
    row = query_one(
        "SELECT 1 AS ok FROM sessions WHERE jti = %s AND expires_at > now()",
        (jti,),
    )
    return row is not None


def revoke(user_id: int, jti: str) -> None:
    """Kill one session (used on rotation and on logout)."""
    query("DELETE FROM sessions WHERE jti = %s", (jti,))


def revoke_all(user_id: int) -> None:
    """Kill every session a user has (logout-all + reuse-detection tripwire)."""
    query("DELETE FROM sessions WHERE user_id = %s", (int(user_id),))
