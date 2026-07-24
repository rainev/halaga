"""Auth routes. Controllers are the HTTP boundary: read the request, call the
service, shape the response. The refresh token lives in an httpOnly cookie."""

from fastapi import APIRouter, Depends, Request, Response, status

from ..deps import CurrentUser
from ..env import env
from ..errors import AppError
from ..models.auth import AuthResponse, Credentials, GoogleCredential
from ..security.rate_limit import RateLimiter
from ..services import auth_service, session_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Credential endpoints: strict per-IP to blunt brute-force / credential stuffing.
# Layered on top of the general limiter applied in routers/__init__.py.
_auth_limit = [Depends(RateLimiter("auth", window_sec=15 * 60, max_hits=15))]

REFRESH_COOKIE = "refresh_token"
_REFRESH_MAX_AGE = env.JWT_REFRESH_EXPIRES_DAYS * 24 * 60 * 60
# Scope the cookie to the auth routes so it isn't sent on every request.
_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        # SameSite=None requires Secure; also Secure whenever running prod-like.
        secure=env.is_production or env.COOKIE_SAMESITE == "none",
        samesite=env.COOKIE_SAMESITE,
        path=_COOKIE_PATH,
        max_age=_REFRESH_MAX_AGE,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=_auth_limit,
)
def register(body: Credentials, response: Response) -> AuthResponse:
    result = auth_service.register(body.email, body.password)
    _set_refresh_cookie(response, result["refresh_token"])
    return AuthResponse(user=result["user"], access_token=result["access_token"])


@router.post("/login", response_model=AuthResponse, dependencies=_auth_limit)
def login(body: Credentials, response: Response) -> AuthResponse:
    result = auth_service.login(body.email, body.password)
    _set_refresh_cookie(response, result["refresh_token"])
    return AuthResponse(user=result["user"], access_token=result["access_token"])


@router.post("/google", response_model=AuthResponse, dependencies=_auth_limit)
def google(body: GoogleCredential, response: Response) -> AuthResponse:
    """"Sign in with Google": verify the Google ID token, then find-or-create the
    user and issue OUR tokens — so Google plugs into our own session system."""
    result = auth_service.google_auth(body.credential)
    _set_refresh_cookie(response, result["refresh_token"])
    return AuthResponse(user=result["user"], access_token=result["access_token"])


@router.post("/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response) -> AuthResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise AppError("Missing refresh token", 401)
    result = auth_service.refresh(token)
    _set_refresh_cookie(response, result["refresh_token"])
    return AuthResponse(user=result["user"], access_token=result["access_token"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    auth_service.logout(request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUser) -> Response:
    auth_service.logout_all(user["sub"])
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
    return response


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return {"user": auth_service.get_current_user(user["sub"])}
