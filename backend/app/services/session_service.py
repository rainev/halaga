"""Refresh-token sessions, stored in Redis.

This is what makes refresh tokens revocable: a token is only honored while its
jti still has a live key here.

Two key shapes:
    session:<jti>          -> userId   (source of truth; a valid session)
    user_sessions:<userId> -> Set<jti> (index, so we can log a user out everywhere)

Both carry a TTL matching the refresh token's lifetime, so expired sessions
evict themselves — no cleanup job needed.
"""

from ..env import env
from ..redis_client import client

REFRESH_TTL_SECONDS = env.JWT_REFRESH_EXPIRES_DAYS * 24 * 60 * 60


def _session_key(jti: str) -> str:
    return f"session:{jti}"


def _user_key(user_id: int) -> str:
    return f"user_sessions:{user_id}"


def create(user_id: int, jti: str) -> None:
    """Record a live session for a freshly-issued refresh token."""
    client.set(_session_key(jti), str(user_id), ex=REFRESH_TTL_SECONDS)
    client.sadd(_user_key(user_id), jti)
    client.expire(_user_key(user_id), REFRESH_TTL_SECONDS)


def is_valid(jti: str) -> bool:
    """True only if the jti is still a live session (not rotated away or revoked)."""
    return client.exists(_session_key(jti)) == 1


def revoke(user_id: int, jti: str) -> None:
    """Kill one session (used on rotation and on logout)."""
    client.delete(_session_key(jti))
    client.srem(_user_key(user_id), jti)


def revoke_all(user_id: int) -> None:
    """Kill every session a user has (logout-all + reuse-detection tripwire)."""
    jtis = client.smembers(_user_key(user_id))
    if jtis:
        client.delete(*[_session_key(j) for j in jtis])
    client.delete(_user_key(user_id))
