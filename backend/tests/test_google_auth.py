"""Unit tests for the "Sign in with Google" service logic.

The Google token verifier, the user store, and the Postgres session store are
all stubbed, so these run without network/DB and pin the find-or-create-or-link
branching (the security-sensitive part).
"""

import pytest

from app.errors import AppError
from app.services import auth_service, session_service, user_service

VERIFIED = {"sub": "g-123", "email": "a@b.com", "email_verified": True, "name": "A"}


@pytest.fixture(autouse=True)
def _stub_sessions(monkeypatch):
    # Issuing tokens records a session in Postgres — stub it out.
    monkeypatch.setattr(session_service, "create", lambda _uid, _jti: None)


def _stub_verify(monkeypatch, identity):
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda _cred: identity)


def test_rejects_unverified_email(monkeypatch):
    _stub_verify(monkeypatch, {**VERIFIED, "email_verified": False})
    with pytest.raises(AppError) as exc:
        auth_service.google_auth("tok")
    assert exc.value.status == 401


def test_existing_google_user_signs_in(monkeypatch):
    _stub_verify(monkeypatch, VERIFIED)
    user = {"id": 7, "email": "a@b.com", "role": "user", "is_verified": True}
    monkeypatch.setattr(user_service, "find_by_google_sub", lambda _sub: user)
    result = auth_service.google_auth("tok")
    assert result["user"]["id"] == 7
    assert result["access_token"] and result["refresh_token"]


def test_links_google_to_existing_email(monkeypatch):
    _stub_verify(monkeypatch, VERIFIED)
    existing = {"id": 9, "email": "a@b.com", "role": "user", "is_verified": False}
    linked = {**existing, "is_verified": True}
    calls = {}
    monkeypatch.setattr(user_service, "find_by_google_sub", lambda _sub: None)
    monkeypatch.setattr(user_service, "find_by_email", lambda _email: existing)
    monkeypatch.setattr(
        user_service,
        "link_google_sub",
        lambda uid, sub: calls.update(uid=uid, sub=sub) or linked,
    )
    result = auth_service.google_auth("tok")
    assert calls == {"uid": 9, "sub": "g-123"}
    assert result["user"]["id"] == 9


def test_creates_new_google_only_user(monkeypatch):
    _stub_verify(monkeypatch, VERIFIED)
    created = {"id": 11, "email": "a@b.com", "role": "user", "is_verified": True}
    monkeypatch.setattr(user_service, "find_by_google_sub", lambda _sub: None)
    monkeypatch.setattr(user_service, "find_by_email", lambda _email: None)
    monkeypatch.setattr(user_service, "create_with_google", lambda email, sub: created)
    result = auth_service.google_auth("tok")
    assert result["user"]["id"] == 11
