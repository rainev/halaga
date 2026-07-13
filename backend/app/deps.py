"""FastAPI dependencies for authentication and authorization.

`current_user` protects a route: it requires a valid `Authorization: Bearer
<accessToken>` header and returns the decoded payload. `require_admin` builds on
it to gate admin-only routes.
"""

from typing import Annotated

from fastapi import Depends, Header

from .errors import AppError
from .security.jwt import TokenError, verify_access_token


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("Missing or invalid Authorization header", 401)
    token = authorization[len("Bearer ") :]
    try:
        return verify_access_token(token)
    except TokenError as exc:
        raise AppError("Invalid or expired access token", 401) from exc


CurrentUser = Annotated[dict, Depends(current_user)]


def require_admin(user: CurrentUser) -> dict:
    if user.get("role") != "admin":
        raise AppError("Insufficient permissions", 403)
    return user


AdminUser = Annotated[dict, Depends(require_admin)]
