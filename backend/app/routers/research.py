"""Research workbench routes: rankings, financial health, valuation, smart brief.

All filing-based and deterministic (no OpenAI). `risk` is 1-5 (screening
thresholds); `sentiment` is bear|base|bull (valuation scenario). Responses are
plain dicts — the engine output is deeply nested, so we skip strict response
models and let FastAPI serialize.
"""

from typing import Literal

from fastapi import APIRouter, Query

from ..deps import CurrentUser
from ..services import research_service

router = APIRouter(prefix="/research", tags=["research"])

Risk = Query(default=3, ge=1, le=5)
Sentiment = Literal["bear", "base", "bull"]


@router.get("/companies")
def list_companies(_user: CurrentUser) -> list[dict]:
    return research_service.companies()


@router.get("/rankings")
def rankings(_user: CurrentUser, risk: int = Risk) -> dict:
    return research_service.rankings(risk)


@router.get("/health/{ticker}")
def health(ticker: str, _user: CurrentUser, risk: int = Risk) -> dict:
    return research_service.health(ticker, risk)


@router.get("/valuation/{ticker}")
def valuation(ticker: str, _user: CurrentUser, sentiment: Sentiment = "base") -> dict:
    return research_service.valuation(ticker, sentiment)


@router.get("/brief/{ticker}")
def brief(ticker: str, _user: CurrentUser, risk: int = Risk, sentiment: Sentiment = "base") -> dict:
    return research_service.brief(ticker, risk, sentiment)
