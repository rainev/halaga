"""Read-only access to reviewed, precomputed filing-only U.S. valuations."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter

from ..errors import AppError


router = APIRouter(prefix="/us-valuations", tags=["us-valuations"])
DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "us_valuations"
TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def load_generated_result(ticker: str) -> dict:
    normalized = ticker.upper()
    if not TICKER.fullmatch(normalized):
        raise AppError("Invalid ticker", 400)
    path = DATA_ROOT / f"{normalized}.json"
    if not path.exists():
        raise AppError("U.S. valuation not available", 404)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError("U.S. valuation artifact is invalid", 500) from exc
    if result.get("issuer", {}).get("ticker") != normalized:
        raise AppError("U.S. valuation artifact identity mismatch", 500)
    return result


@router.get("/{ticker}")
def get_us_valuation(ticker: str) -> dict:
    return load_generated_result(ticker)
