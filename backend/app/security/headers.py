"""Secure HTTP response headers — the FastAPI equivalent of Express's Helmet.

Sets the hardening headers that apply to a JSON API: stop MIME sniffing, deny
framing (clickjacking), quiet the referrer, and — in production, over HTTPS —
turn on HSTS. We skip a Content-Security-Policy: this service returns JSON, not
HTML the browser renders, so a CSP has nothing to constrain here.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from ..env import env

# One year, and cover subdomains — the usual HSTS baseline. Only ever sent over
# HTTPS (a browser ignores it on plain HTTP), and only in production so local
# http://localhost dev isn't pinned to HTTPS.
_HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        # Don't advertise the server implementation.
        headers["Server"] = "finsight"
        if env.is_production:
            headers.setdefault("Strict-Transport-Security", _HSTS)
        return response


def add_security_headers(app: ASGIApp) -> None:
    """Register the middleware on the FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)  # type: ignore[arg-type]
