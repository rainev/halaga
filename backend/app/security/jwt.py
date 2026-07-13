"""Access and refresh JWTs.

- The access token carries {sub, email, role} and is sent in the Authorization
  header on every request.
- The refresh token additionally carries a `jti` (a unique session id). The
  server tracks live jtis in Redis, which is what makes refresh tokens revocable
  (see services/session_service.py).

verify_* checks the signature/expiry AND the payload shape, so a token with a
missing/renamed claim is rejected even if its signature is valid.
"""

from datetime import datetime, timedelta, timezone

import jwt

from ..env import env


class TokenError(Exception):
    """Raised when a token is invalid, expired, or malformed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def sign_access_token(sub: int, email: str, role: str) -> str:
    payload = {
        # JWT spec (enforced by PyJWT >= 2.10) requires `sub` to be a string.
        "sub": str(sub),
        "email": email,
        "role": role,
        "iat": _now(),
        "exp": _now() + timedelta(minutes=env.JWT_ACCESS_EXPIRES_MIN),
    }
    return jwt.encode(payload, env.JWT_ACCESS_SECRET, algorithm="HS256")


def sign_refresh_token(sub: int, email: str, role: str, jti: str) -> str:
    payload = {
        "sub": str(sub),
        "email": email,
        "role": role,
        "jti": jti,
        "iat": _now(),
        "exp": _now() + timedelta(days=env.JWT_REFRESH_EXPIRES_DAYS),
    }
    return jwt.encode(payload, env.JWT_REFRESH_SECRET, algorithm="HS256")


def _decode(token: str, secret: str, require: tuple[str, ...]) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if not all(claim in payload for claim in require):
        raise TokenError("Malformed token payload")
    # Convert `sub` back to the int user-id the rest of the app expects.
    payload["sub"] = int(payload["sub"])
    return payload


def verify_access_token(token: str) -> dict:
    return _decode(token, env.JWT_ACCESS_SECRET, ("sub", "email", "role"))


def verify_refresh_token(token: str) -> dict:
    return _decode(token, env.JWT_REFRESH_SECRET, ("sub", "email", "role", "jti"))
