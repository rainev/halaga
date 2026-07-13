"""Access/refresh token round-trips and rejection of tampered/malformed tokens."""

import pytest

from app.security.jwt import (
    TokenError,
    sign_access_token,
    sign_refresh_token,
    verify_access_token,
    verify_refresh_token,
)


def test_access_token_roundtrip():
    token = sign_access_token(sub=42, email="a@b.com", role="user")
    payload = verify_access_token(token)
    assert payload["sub"] == 42
    assert payload["email"] == "a@b.com"
    assert payload["role"] == "user"


def test_refresh_token_carries_jti():
    token = sign_refresh_token(sub=1, email="a@b.com", role="admin", jti="sess-123")
    payload = verify_refresh_token(token)
    assert payload["jti"] == "sess-123"


def test_tampered_token_is_rejected():
    token = sign_access_token(sub=1, email="a@b.com", role="user")
    with pytest.raises(TokenError):
        verify_access_token(token + "x")


def test_access_secret_does_not_verify_refresh():
    # A refresh token is signed with a different secret, so the access verifier
    # must reject it.
    token = sign_refresh_token(sub=1, email="a@b.com", role="user", jti="j")
    with pytest.raises(TokenError):
        verify_access_token(token)
