"""Auth routes. Controllers are the HTTP boundary: read the request, call the
service, shape the response. The refresh token lives in an httpOnly cookie."""

from fastapi import APIRouter, Request, Response, status

from ..deps import CurrentUser
from ..env import env
from ..errors import AppError
from ..models.auth import AuthResponse, Credentials
from ..services import auth_service, session_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
_REFRESH_MAX_AGE = env.JWT_REFRESH_EXPIRES_DAYS * 24 * 60 * 60
# Scope the cookie to the auth routes so it isn't sent on every request.
_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=env.is_production,  # HTTPS-only in prod
        samesite="lax",
        path=_COOKIE_PATH,
        max_age=_REFRESH_MAX_AGE,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, response: Response) -> AuthResponse:
    result = auth_service.register(body.email, body.password)
    _set_refresh_cookie(response, result["refresh_token"])
    return AuthResponse(user=result["user"], access_token=result["access_token"])


@router.post("/login", response_model=AuthResponse)
def login(body: Credentials, response: Response) -> AuthResponse:
    result = auth_service.login(body.email, body.password)
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
