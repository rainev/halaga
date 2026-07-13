"""Auth business logic: register, login, refresh (with rotation + reuse
detection), logout. Controllers stay thin and just wire HTTP to these.
"""

import uuid
from typing import Any, TypedDict

from ..errors import AppError
from ..security.jwt import (
    TokenError,
    sign_access_token,
    sign_refresh_token,
    verify_refresh_token,
)
from ..security.password import hash_password, verify_password
from . import session_service, user_service


class AuthResult(TypedDict):
    user: dict[str, Any]
    access_token: str
    refresh_token: str


def _issue_tokens(user: dict[str, Any]) -> tuple[str, str]:
    """Issue an access/refresh pair and record the refresh token's session in
    Redis (keyed by a fresh jti) so it can later be revoked."""
    jti = str(uuid.uuid4())
    session_service.create(user["id"], jti)
    access = sign_access_token(user["id"], user["email"], user["role"])
    refresh = sign_refresh_token(user["id"], user["email"], user["role"], jti)
    return access, refresh


def _result(user: dict[str, Any]) -> AuthResult:
    access, refresh = _issue_tokens(user)
    return {
        "user": user_service.to_public(user),
        "access_token": access,
        "refresh_token": refresh,
    }


def register(email: str, password: str) -> AuthResult:
    if user_service.find_by_email(email):
        raise AppError("Email already registered", 409)
    user = user_service.create(email, hash_password(password))
    return _result(user)


def login(email: str, password: str) -> AuthResult:
    user = user_service.find_by_email(email)
    # Same error whether the email or the password is wrong — don't leak which.
    if not user or not verify_password(password, user["password_hash"]):
        raise AppError("Invalid credentials", 401)
    return _result(user)


def refresh(refresh_token: str) -> AuthResult:
    """Verify the refresh token, then rotate it: kill the old session, issue a
    new one. A validly-signed token whose session is no longer live was already
    rotated away (or revoked) — a sign of theft/replay, so revoke everything."""
    try:
        payload = verify_refresh_token(refresh_token)
    except TokenError as exc:
        raise AppError("Invalid or expired refresh token", 401) from exc

    if not session_service.is_valid(payload["jti"]):
        session_service.revoke_all(payload["sub"])  # reuse detection: assume compromise
        raise AppError("Refresh token has been revoked", 401)

    user = user_service.find_by_id(payload["sub"])
    if not user:
        raise AppError("User no longer exists", 401)

    session_service.revoke(payload["sub"], payload["jti"])  # rotate: retire old session
    return _result(user)


def logout(refresh_token: str | None) -> None:
    """Revoke just the current session. Best-effort: an invalid/expired token
    has no live session to revoke, so we simply do nothing."""
    if not refresh_token:
        return
    try:
        payload = verify_refresh_token(refresh_token)
    except TokenError:
        return
    session_service.revoke(payload["sub"], payload["jti"])


def logout_all(user_id: int) -> None:
    session_service.revoke_all(user_id)


def get_current_user(user_id: int) -> dict[str, Any]:
    user = user_service.find_by_id(user_id)
    if not user:
        raise AppError("User not found", 404)
    return user_service.to_public(user)
