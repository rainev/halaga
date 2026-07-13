"""Valuation request/response schemas.

Each model has its own input shape. Fields that can be derived (growth from a
history, a discount rate from beta via CAPM, Graham's current yield from the PH
market assumptions) are optional — the router resolves them before calling the
pure engine.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SaveOptions(BaseModel):
    """Common to every compute request: which company (optional) and whether to
    persist the run to the user's saved valuations."""

    company_id: int | None = None
    save: bool = False


class DcfInput(SaveOptions):
    # method: 'simple'/'fcff' use the enterprise bridge (FCFF + WACC);
    # 'fcfe' discounts equity cash flows at cost of equity with no debt bridge.
    method: Literal["simple", "fcff", "fcfe"] = "simple"
    # Provide an explicit projection, OR a base + growth + horizon to build one.
    projected_fcf: list[float] | None = None
    base_fcf: float | None = None
    growth_rate: float | None = None  # decimal, e.g. 0.09
    years: int | None = Field(default=None, ge=1, le=30)
    # Provide a discount rate directly, OR a beta to derive it via CAPM.
    discount_rate: float | None = None
    beta: float | None = None
    # FCFF WACC builder (used when method='fcff' and discount_rate is blank):
    # WACC weights equity (market cap = price * shares) vs debt (total_debt).
    cost_of_debt: float | None = None
    tax_rate: float = 0.25  # PH corporate income tax
    perpetual_growth_rate: float | None = None  # defaults to PH long-run growth
    cash: float = 0.0
    total_debt: float = 0.0
    shares_outstanding: float = Field(gt=0)
    current_price: float | None = None


class DdmInput(SaveOptions):
    method: Literal["gordon", "two_stage"] = "gordon"
    last_dividend: float | None = None
    dividend_history: list[float] | None = None  # derive last_dividend + growth
    growth_rate: float | None = None
    discount_rate: float | None = None
    beta: float | None = None
    # Two-stage only:
    high_growth: float | None = None
    high_growth_years: int | None = Field(default=None, ge=1, le=30)
    terminal_growth: float | None = None
    current_price: float | None = None


class GrahamInput(SaveOptions):
    eps: float
    growth_rate_pct: float  # WHOLE-NUMBER percent, e.g. 9.63
    current_yield: float | None = None  # defaults to PH benchmark yield
    base_pe: float | None = None
    normalizing_yield: float | None = None
    margin_of_safety: float = Field(default=0.35, ge=0, lt=1)
    current_price: float | None = None


class PeerInput(BaseModel):
    ticker: str | None = None
    # Fields used depend on the chosen metric (P/E, P/B, or EV/EBITDA).
    price: float | None = None
    eps: float | None = None
    book_value_per_share: float | None = None
    ev: float | None = None
    ebitda: float | None = None


class MultiplesInput(SaveOptions):
    metric: Literal["pe", "pb", "ev_ebitda"] = "pe"
    peers: list[PeerInput] = Field(min_length=1)
    # Target figure matching the metric:
    target_eps: float | None = None
    target_book_value_per_share: float | None = None
    target_ebitda: float | None = None
    # EV/EBITDA needs these to bridge enterprise value -> per share:
    cash: float = 0.0
    total_debt: float = 0.0
    shares_outstanding: float | None = None
    current_price: float | None = None


class SavedValuation(BaseModel):
    id: int
    company_id: int | None
    model: Literal["dcf", "ddm", "graham", "multiples"]
    inputs: dict
    assumptions: dict
    result: dict
    created_at: datetime
