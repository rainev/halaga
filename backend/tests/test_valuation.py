"""Verifies the valuation engine against the original spreadsheet's numbers
(where the spreadsheet was correct) and against hand-computed values (where we
fixed its bugs)."""

import pytest

from app.valuation.assumptions import wacc
from app.valuation.common import average_growth, cagr
from app.valuation.dcf import dcf_valuation, fcfe_valuation, project_fcf
from app.valuation.ddm import ddm_valuation, two_stage_ddm
from app.valuation.graham import graham_valuation
from app.valuation.multiples import ev_ebitda_valuation, multiples_valuation, pb_valuation


def test_ddm_matches_spreadsheet():
    # Dividend-Discount-Model sheet: D0=1.68, g=avg growth, r=6%.
    g = average_growth([1.48, 1.56, 1.60, 1.64, 1.68])
    result = ddm_valuation(last_dividend=1.68, growth_rate=g, discount_rate=0.06, current_price=55.99)
    assert result["intrinsic_value"] == pytest.approx(62.54, abs=0.05)
    assert result["verdict"] == "Undervalued"


def test_ddm_requires_rate_above_growth():
    with pytest.raises(ValueError):
        ddm_valuation(last_dividend=1.0, growth_rate=0.08, discount_rate=0.06)


def test_multiples_matches_spreadsheet():
    peers = [
        {"ticker": "META", "price": 669.21, "eps": 27.52},
        {"ticker": "AAPL", "price": 315.32, "eps": 8.27},
        {"ticker": "GOOG", "price": 355.03, "eps": 13.11},
        {"ticker": "MSFT", "price": 385.10, "eps": 16.79},
    ]
    result = multiples_valuation(peers=peers, target_eps=25.0)
    assert result["detail"]["average_pe"] == pytest.approx(28.1156, abs=0.01)
    assert result["detail"]["median_pe"] == pytest.approx(25.699, abs=0.01)
    # Spreadsheet's headline used the average P/E * EPS.
    assert result["detail"]["value_on_average"] == pytest.approx(702.89, abs=0.5)


def test_multiples_skips_nonpositive_eps():
    peers = [
        {"ticker": "A", "price": 100.0, "eps": 10.0},
        {"ticker": "B", "price": 50.0, "eps": 0.0},  # skipped
        {"ticker": "C", "price": 200.0, "eps": -5.0},  # skipped
    ]
    result = multiples_valuation(peers=peers, target_eps=5.0)
    assert len(result["detail"]["peers"]) == 1
    assert result["detail"]["average_pe"] == pytest.approx(10.0)


def test_graham_growth_units_fixed():
    # eps 8.27, g 9.63% (whole number!), current PH yield 6.0.
    result = graham_valuation(
        eps=8.27, growth_rate_pct=9.63, current_yield=6.0, current_price=315.32
    )
    assert result["intrinsic_value"] == pytest.approx(168.36, abs=0.1)
    assert result["verdict"] == "Sell"  # price 315 >> acceptable buy price
    assert result["detail"]["acceptable_buy_price"] == pytest.approx(0.65 * 168.36, abs=0.1)


def test_graham_decimal_growth_would_understate():
    # Demonstrates the original spreadsheet bug: passing the decimal 0.0963
    # instead of 9.63 collapses the growth term and understates value ~3x.
    fixed = graham_valuation(eps=8.27, growth_rate_pct=9.63, current_yield=6.0)
    buggy = graham_valuation(eps=8.27, growth_rate_pct=0.0963, current_yield=6.0)
    assert buggy["intrinsic_value"] < 0.5 * fixed["intrinsic_value"]


def test_dcf_basic_present_value():
    projected = [100.0, 110.0, 121.0]
    result = dcf_valuation(
        projected_fcf=projected,
        discount_rate=0.10,
        perpetual_growth_rate=0.02,
        shares_outstanding=10.0,
    )
    # 3 * 90.909 (PV of FCF) + PV of terminal 1542.75 / 1.331.
    assert result["detail"]["enterprise_value"] == pytest.approx(1431.82, abs=0.1)
    assert result["intrinsic_value"] == pytest.approx(143.18, abs=0.05)


def test_dcf_equity_bridge():
    result = dcf_valuation(
        projected_fcf=[100.0],
        discount_rate=0.10,
        perpetual_growth_rate=0.02,
        shares_outstanding=10.0,
        cash=50.0,
        total_debt=30.0,
    )
    ev = result["detail"]["enterprise_value"]
    assert result["detail"]["equity_value"] == pytest.approx(ev + 50.0 - 30.0)


def test_dcf_rejects_discount_below_growth():
    with pytest.raises(ValueError):
        dcf_valuation(
            projected_fcf=[100.0],
            discount_rate=0.02,
            perpetual_growth_rate=0.05,
            shares_outstanding=10.0,
        )


def test_project_fcf_grows_geometrically():
    assert project_fcf(100.0, 0.10, 3) == pytest.approx([110.0, 121.0, 133.1])


def test_cagr_uses_interval_count_not_point_count():
    # 3 data points = 2 intervals. 121 = 100 * 1.1**2, so CAGR is exactly 10%.
    assert cagr([100.0, 110.0, 121.0]) == pytest.approx(0.10)


# --- Variants -------------------------------------------------------------

def test_wacc_below_cost_of_equity_when_levered():
    # 50/50 capital, Re 12%, Rd 6%, tax 25% -> 0.5*0.12 + 0.5*0.06*0.75 = 0.0825.
    w = wacc(cost_of_equity=0.12, cost_of_debt=0.06, equity_value=100, debt_value=100, tax_rate=0.25)
    assert w == pytest.approx(0.0825)
    assert w < 0.12  # cheaper debt pulls WACC below cost of equity


def test_fcfe_has_no_debt_bridge():
    # Same cash flows: FCFE (no bridge) must equal FCFF with zero cash and debt.
    fcfe = fcfe_valuation(
        projected_fcfe=[100.0, 110.0],
        cost_of_equity=0.10,
        perpetual_growth_rate=0.02,
        shares_outstanding=10.0,
    )
    fcff = dcf_valuation(
        projected_fcf=[100.0, 110.0],
        discount_rate=0.10,
        perpetual_growth_rate=0.02,
        shares_outstanding=10.0,
        cash=0.0,
        total_debt=0.0,
    )
    assert fcfe["intrinsic_value"] == pytest.approx(fcff["intrinsic_value"])
    assert fcfe["detail"]["method"] == "fcfe"
    assert "total_debt" not in fcfe["detail"]  # no bridge


def test_fcfe_rejects_rate_below_growth():
    with pytest.raises(ValueError):
        fcfe_valuation(
            projected_fcfe=[100.0], cost_of_equity=0.02, perpetual_growth_rate=0.05, shares_outstanding=10.0
        )


def test_two_stage_ddm_exceeds_single_stage_for_fast_growth():
    # A fast near-term grower is worth more under two-stage than flat Gordon.
    single = ddm_valuation(last_dividend=4.40, growth_rate=0.06, discount_rate=0.135)
    two = two_stage_ddm(
        last_dividend=4.40,
        high_growth=0.12,
        high_growth_years=5,
        terminal_growth=0.06,
        discount_rate=0.135,
    )
    assert two["intrinsic_value"] > single["intrinsic_value"]
    assert two["detail"]["method"] == "two_stage"


def test_two_stage_allows_high_growth_above_discount_rate():
    # High-growth stage may exceed the discount rate; only terminal must be below.
    res = two_stage_ddm(
        last_dividend=1.0,
        high_growth=0.20,
        high_growth_years=3,
        terminal_growth=0.04,
        discount_rate=0.10,
    )
    assert res["intrinsic_value"] > 0


def test_pb_valuation_uses_median_price_to_book():
    peers = [
        {"ticker": "BPI", "price": 102.0, "bvps": 85.0},
        {"ticker": "MBT", "price": 65.15, "book_value_per_share": 90.0},
    ]
    res = pb_valuation(peers=peers, target_book_value_per_share=100.0, current_price=123.0)
    assert res["detail"]["metric"] == "pb"
    # Only MBT has book_value_per_share (BPI used the wrong key 'bvps'), so 1 peer.
    assert len(res["detail"]["peers"]) == 1


def test_ev_ebitda_bridges_to_equity():
    peers = [
        {"ticker": "A", "ev": 1000.0, "ebitda": 100.0},  # 10x
        {"ticker": "B", "ev": 1200.0, "ebitda": 100.0},  # 12x
    ]
    res = ev_ebitda_valuation(
        peers=peers, target_ebitda=50.0, cash=100.0, total_debt=200.0, shares_outstanding=10.0
    )
    # median multiple 11 -> EV 550; equity 550 + 100 - 200 = 450; /10 = 45.
    assert res["detail"]["median_ev_ebitda"] == pytest.approx(11.0)
    assert res["intrinsic_value"] == pytest.approx(45.0)
