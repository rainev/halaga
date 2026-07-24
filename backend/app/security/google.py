"""Verify the Google ID token from "Sign in with Google".

Google Identity Services hands the browser an ID token (a signed JWT) after the
user picks an account. We verify its signature and audience server-side against
our OAuth client id, so the frontend can never forge an identity. On success we
get a trustworthy {sub, email, email_verified, name}.
"""

from typing import TypedDict

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from ..env import env
from ..errors import AppError

# One shared transport for token verification (fetches/caches Google's certs).
_request = google_requests.Request()


class GoogleIdentity(TypedDict):
    sub: str  # stable Google user id
    email: str
    email_verified: bool
    name: str | None


def verify_google_id_token(credential: str) -> GoogleIdentity:
    if not env.GOOGLE_CLIENT_ID:
        raise AppError("Google sign-in is not configured on the server.", 501)

    try:
        payload = id_token.verify_oauth2_token(
            credential, _request, env.GOOGLE_CLIENT_ID
        )
    except ValueError as exc:  # bad signature, wrong audience, expired, …
        raise AppError("Invalid Google credential.", 401) from exc

    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise AppError("Google credential is missing required fields.", 401)

    return {
        "sub": sub,
        "email": email,
        "email_verified": bool(payload.get("email_verified", False)),
        "name": payload.get("name"),
    }
