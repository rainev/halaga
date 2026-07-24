"""End-to-end router tests via FastAPI's TestClient.

Auth is overridden and market assumptions / storage are stubbed so these run
without a live DB or MinIO — they exercise input validation, the resolve
logic, and response shaping. (Persistence paths use save=False.)"""

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app import deps
from app.services import market_service
from app.valuation.assumptions import PH

# Any authenticated user.
main_module.app.dependency_overrides[deps.current_user] = lambda: {
    "sub": 1,
    "email": "a@b.com",
    "role": "user",
}


@pytest.fixture(scope="module")
def client():
    # Module-scoped: the DB pool is a global singleton and can't be reopened once
    # closed, so the lifespan (pool.open/close) must run exactly once here.
    orig_bucket = main_module.ensure_bucket
    orig_assumptions = market_service.get_assumptions
    main_module.ensure_bucket = lambda: None
    market_service.get_assumptions = lambda: PH
    try:
        with TestClient(main_module.app) as c:
            yield c
    finally:
        main_module.ensure_bucket = orig_bucket
        market_service.get_assumptions = orig_assumptions


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_dcf_endpoint(client):
    r = client.post(
        "/api/valuations/dcf",
        json={
            "projected_fcf": [100, 110, 121],
            "discount_rate": 0.10,
            "perpetual_growth_rate": 0.02,
            "shares_outstanding": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "dcf"
    assert body["intrinsic_value"] == pytest.approx(143.18, abs=0.05)


def test_dcf_derives_discount_from_beta(client):
    # No discount_rate given, but beta 1.0 -> CAPM = 0.06 + 1*0.075 = 0.135.
    r = client.post(
        "/api/valuations/dcf",
        json={
            "base_fcf": 100,
            "growth_rate": 0.05,
            "years": 5,
            "beta": 1.0,
            "shares_outstanding": 10,
        },
    )
    assert r.status_code == 200


def test_dcf_missing_projection_is_400(client):
    r = client.post(
        "/api/valuations/dcf",
        json={"discount_rate": 0.10, "shares_outstanding": 10},
    )
    assert r.status_code == 400


def test_graham_uses_ph_yield_default(client):
    r = client.post(
        "/api/valuations/graham",
        json={"eps": 8.27, "growth_rate_pct": 9.63, "current_price": 315.32},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intrinsic_value"] == pytest.approx(168.36, abs=0.1)
    assert body["verdict"] == "Sell"


def test_multiples_endpoint(client):
    r = client.post(
        "/api/valuations/multiples",
        json={
            "peers": [
                {"ticker": "META", "price": 669.21, "eps": 27.52},
                {"ticker": "AAPL", "price": 315.32, "eps": 8.27},
            ],
            "target_eps": 25.0,
        },
    )
    assert r.status_code == 200
    assert r.json()["detail"]["average_pe"] == pytest.approx((669.21 / 27.52 + 315.32 / 8.27) / 2)


def test_invalid_shares_is_422(client):
    # shares_outstanding must be > 0 (Pydantic validation -> 422).
    r = client.post(
        "/api/valuations/dcf",
        json={"projected_fcf": [100], "discount_rate": 0.1, "shares_outstanding": 0},
    )
    assert r.status_code == 422
