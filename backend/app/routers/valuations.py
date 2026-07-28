"""Valuation routes: one compute endpoint per model, plus CRUD for saved runs.

Each compute endpoint resolves any derivable inputs (growth from history, a
discount rate from beta via CAPM, Graham's yield from the PH market assumptions),
calls the pure engine, and optionally persists the run for the current user.
"""

from fastapi import APIRouter, status

from ..deps import CurrentUser
from ..errors import AppError
from ..models.valuation import (
    BankResidualIncomeInput,
    DcfInput,
    DdmInput,
    GrahamInput,
    MultiplesInput,
    SavedValuation,
)
from ..services import market_service, valuation_service
from ..valuation import bank, dcf, ddm, graham, multiples
from ..valuation.assumptions import MarketAssumptions, cost_of_equity, wacc
from ..valuation.common import average_growth

router = APIRouter(prefix="/valuations", tags=["valuations"])


def _market_assumption_snapshot(a: MarketAssumptions) -> dict:
    """Persist enough provenance to reproduce a dated discount-rate build."""
    return {
        "local_government_yield": a.local_government_yield,
        "sovereign_default_spread": a.sovereign_default_spread,
        "risk_free_rate": a.risk_free_rate,
        "mature_market_erp": a.equity_risk_premium,
        "country_risk_premium": a.country_risk_premium,
        "assumptions_as_of": a.assumptions_as_of,
        "assumptions_source": a.assumptions_source,
        "assumptions_source_url": a.assumptions_source_url,
    }


def _resolve_discount_rate(
    discount_rate: float | None,
    beta: float | None,
    assumptions: MarketAssumptions,
    country_risk_exposure: float = 1.0,
) -> float:
    if discount_rate is not None:
        return discount_rate
    if beta is not None:
        return cost_of_equity(beta, assumptions, country_risk_exposure)
    raise AppError("Provide either discount_rate or beta", 400)


def _persist_if_requested(user_id: int, body, model: str, result: dict, assumptions: dict) -> dict:
    if not body.save:
        return result
    saved = valuation_service.save(
        user_id=user_id,
        company_id=body.company_id,
        model=model,
        inputs=body.model_dump(exclude={"save"}),
        assumptions=assumptions,
        result=result,
    )
    return {**result, "saved_id": saved["id"]}


@router.post("/dcf")
def run_dcf(body: DcfInput, user: CurrentUser) -> dict:
    a = market_service.get_assumptions()

    if body.projected_fcf:
        projected = body.projected_fcf
    elif body.base_fcf is not None and body.growth_rate is not None and body.years is not None:
        projected = dcf.project_fcf(body.base_fcf, body.growth_rate, body.years)
    else:
        raise AppError("Provide projected_fcf, or base_fcf + growth_rate + years", 400)

    perpetual = (
        body.perpetual_growth_rate
        if body.perpetual_growth_rate is not None
        else a.default_perpetual_growth
    )

    try:
        if body.method == "fcfe":
            # Equity-level: discount FCFE at cost of equity, no cash/debt bridge.
            if body.discount_rate is not None:
                coe = body.discount_rate
            elif body.beta is not None:
                coe = cost_of_equity(body.beta, a, body.country_risk_exposure)
            else:
                raise AppError("FCFE needs a cost of equity — provide discount_rate or beta", 400)
            result = dcf.fcfe_valuation(
                projected_fcfe=projected,
                cost_of_equity=coe,
                perpetual_growth_rate=perpetual,
                shares_outstanding=body.shares_outstanding,
                current_price=body.current_price,
            )
            used = {
                "cost_of_equity": coe,
                "country_risk_exposure": body.country_risk_exposure,
                "market_assumptions": _market_assumption_snapshot(a),
            }
        else:
            # Firm-level (simple/fcff): discount FCFF, then EV -> equity bridge.
            rate = _resolve_dcf_rate(body, a)
            result = dcf.dcf_valuation(
                projected_fcf=projected,
                discount_rate=rate,
                perpetual_growth_rate=perpetual,
                shares_outstanding=body.shares_outstanding,
                cash=body.cash,
                total_debt=body.total_debt,
                preferred_stock=body.preferred_stock,
                non_controlling_interest=body.non_controlling_interest,
                current_price=body.current_price,
                method=body.method,
            )
            used = {
                "discount_rate": rate,
                "rate_type": "wacc",
                "market_assumptions": _market_assumption_snapshot(a),
            }
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    return _persist_if_requested(user["sub"], body, "dcf", result, used)


def _resolve_dcf_rate(body: DcfInput, a: MarketAssumptions) -> float:
    """Resolve a firm-level discount rate without substituting cost of equity.

    `simple` and `fcff` both value enterprise cash flow, so both require WACC.
    """
    if body.discount_rate is not None:
        return body.discount_rate
    if body.beta is not None and body.cost_of_debt is not None:
        equity_value = (body.current_price or 0) * body.shares_outstanding
        if equity_value <= 0:
            raise AppError(
                "Building WACC needs a current_price (for equity market value), "
                "or enter a discount_rate directly",
                400,
            )
        return wacc(
            cost_of_equity=cost_of_equity(
                body.beta, a, body.country_risk_exposure
            ),
            cost_of_debt=body.cost_of_debt,
            equity_value=equity_value,
            debt_value=body.total_debt,
            tax_rate=body.tax_rate,
        )
    raise AppError(
        "Firm-level DCF needs an explicit WACC (discount_rate), or beta + "
        "cost_of_debt + current_price + total_debt to build WACC",
        400,
    )


@router.post("/ddm")
def run_ddm(body: DdmInput, user: CurrentUser) -> dict:
    a = market_service.get_assumptions()

    last_dividend = body.last_dividend
    growth_rate = body.growth_rate
    if body.dividend_history:
        if last_dividend is None:
            last_dividend = body.dividend_history[-1]
        if growth_rate is None:
            try:
                growth_rate = average_growth(body.dividend_history)
            except ValueError as exc:
                raise AppError(str(exc), 400) from exc
    if last_dividend is None:
        raise AppError("Provide last_dividend, or a dividend_history to derive it", 400)

    discount_rate = _resolve_discount_rate(
        body.discount_rate,
        body.beta,
        a,
        body.country_risk_exposure,
    )
    try:
        if body.method == "two_stage":
            if body.high_growth is None or body.high_growth_years is None or body.terminal_growth is None:
                raise AppError(
                    "Two-stage DDM needs high_growth, high_growth_years, and terminal_growth", 400
                )
            result = ddm.two_stage_ddm(
                last_dividend=last_dividend,
                high_growth=body.high_growth,
                high_growth_years=body.high_growth_years,
                terminal_growth=body.terminal_growth,
                discount_rate=discount_rate,
                current_price=body.current_price,
            )
        else:
            if growth_rate is None:
                raise AppError(
                    "Single-stage DDM needs growth_rate, or a dividend_history to derive it", 400
                )
            result = ddm.ddm_valuation(
                last_dividend=last_dividend,
                growth_rate=growth_rate,
                discount_rate=discount_rate,
                current_price=body.current_price,
            )
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    return _persist_if_requested(
        user["sub"],
        body,
        "ddm",
        result,
        {
            "discount_rate": discount_rate,
            "rate_type": "cost_of_equity",
            "country_risk_exposure": body.country_risk_exposure,
            "market_assumptions": _market_assumption_snapshot(a),
        },
    )


@router.post("/graham")
def run_graham(body: GrahamInput, user: CurrentUser) -> dict:
    a = market_service.get_assumptions()
    current_yield = body.current_yield if body.current_yield is not None else a.graham_current_yield
    base_pe = body.base_pe if body.base_pe is not None else a.graham_base_pe
    normalizing_yield = (
        body.normalizing_yield if body.normalizing_yield is not None else a.graham_normalizing_yield
    )
    try:
        result = graham.graham_valuation(
            eps=body.eps,
            growth_rate_pct=body.growth_rate_pct,
            current_yield=current_yield,
            base_pe=base_pe,
            normalizing_yield=normalizing_yield,
            margin_of_safety=body.margin_of_safety,
            current_price=body.current_price,
        )
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    assumptions = {
        "current_yield": current_yield,
        "base_pe": base_pe,
        "normalizing_yield": normalizing_yield,
        "market_assumptions": _market_assumption_snapshot(a),
    }
    return _persist_if_requested(user["sub"], body, "graham", result, assumptions)


@router.post("/multiples")
def run_multiples(body: MultiplesInput, user: CurrentUser) -> dict:
    peers = [p.model_dump() for p in body.peers]
    try:
        if body.metric == "pb":
            if body.target_book_value_per_share is None:
                raise AppError("P/B needs target_book_value_per_share", 400)
            result = multiples.pb_valuation(
                peers=peers,
                target_book_value_per_share=body.target_book_value_per_share,
                current_price=body.current_price,
            )
        elif body.metric == "ev_ebitda":
            if body.target_ebitda is None or body.shares_outstanding is None:
                raise AppError("EV/EBITDA needs target_ebitda and shares_outstanding", 400)
            result = multiples.ev_ebitda_valuation(
                peers=peers,
                target_ebitda=body.target_ebitda,
                cash=body.cash,
                total_debt=body.total_debt,
                shares_outstanding=body.shares_outstanding,
                current_price=body.current_price,
            )
        else:  # pe
            if body.target_eps is None:
                raise AppError("P/E needs target_eps", 400)
            result = multiples.multiples_valuation(
                peers=peers,
                target_eps=body.target_eps,
                current_price=body.current_price,
            )
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    return _persist_if_requested(user["sub"], body, "multiples", result, {})


@router.post("/residual-income")
def run_bank_residual_income(
    body: BankResidualIncomeInput,
    user: CurrentUser,
) -> dict:
    assumptions = market_service.get_assumptions()
    if body.cost_of_equity is not None:
        resolved_cost_of_equity = body.cost_of_equity
        rate_source = "explicit"
    elif body.beta is not None:
        resolved_cost_of_equity = cost_of_equity(
            body.beta,
            assumptions,
            body.country_risk_exposure,
        )
        rate_source = "capm"
    else:
        raise AppError(
            "Residual income needs cost_of_equity or beta",
            400,
        )
    try:
        result = bank.residual_income_valuation(
            book_value_per_share=body.book_value_per_share,
            current_roe=body.current_roe,
            cost_of_equity=resolved_cost_of_equity,
            current_payout_ratio=body.current_payout_ratio,
            terminal_roe=body.terminal_roe,
            terminal_growth=body.terminal_growth,
            years=body.years,
            current_price=body.current_price,
        )
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    return _persist_if_requested(
        user["sub"],
        body,
        "residual_income",
        result,
        {
            "cost_of_equity": resolved_cost_of_equity,
            "rate_type": "cost_of_equity",
            "rate_source": rate_source,
            "country_risk_exposure": body.country_risk_exposure,
            "market_assumptions": _market_assumption_snapshot(assumptions),
        },
    )


@router.get("", response_model=list[SavedValuation])
def list_valuations(user: CurrentUser) -> list[dict]:
    return valuation_service.list_for_user(user["sub"])


@router.get("/{valuation_id}", response_model=SavedValuation)
def get_valuation(valuation_id: int, user: CurrentUser) -> dict:
    row = valuation_service.get(user["sub"], valuation_id)
    if not row:
        raise AppError("Valuation not found", 404)
    return row


@router.delete("/{valuation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_valuation(valuation_id: int, user: CurrentUser):
    if not valuation_service.delete(user["sub"], valuation_id):
        raise AppError("Valuation not found", 404)
