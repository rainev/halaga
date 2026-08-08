"""FCFF reinvestment and competitive terminal economics tests."""

from __future__ import annotations

import pytest

from app.us_valuation.assumptions import US_BASE, derive_forecast_assumptions
from app.us_valuation.models import fcff_dcf, one_way_sensitivities, scenario_set


def financials() -> dict:
    return {
        "balance_sheet": {
            "cash_and_nonoperating_investments": 0.0,
            "total_interest_bearing_debt": 0.0,
            "preferred_equity": 0.0,
            "noncontrolling_interests": 0.0,
            "fully_diluted_shares_proxy": 1.0,
        }
    }


def fcff_assumptions(**overrides: float) -> dict:
    assumptions = {
        "forecast_years": 5,
        "normalized_tax_rate": 0.20,
        "initial_revenue_growth": 0.20,
        "target_operating_margin": 0.20,
        "sales_to_capital": 3.0,
        "starting_revenue": 100.0,
        "starting_operating_margin": 0.20,
        "terminal_growth": 0.02,
        "initial_marginal_roic": 0.48,
        "terminal_marginal_roic": 0.10,
        "growth_persistence": 0.78,
        "margin_persistence": 0.78,
        "segment_forecast": None,
        "terminal_roic_basis": "competitive_fade_to_wacc",
    }
    assumptions.update(overrides)
    return assumptions


def test_high_growth_can_reinvest_above_100_percent_and_produce_negative_fcff() -> None:
    result = fcff_dcf(
        assumptions=fcff_assumptions(initial_marginal_roic=0.05),
        discount_rate={"wacc": 0.10},
        financials=financials(),
    )

    first_year = result["detail"]["forecast_schedule"][0]
    assert first_year["revenue_growth"] == pytest.approx(0.20)
    assert first_year["nopat"] == pytest.approx(19.20)
    assert first_year["marginal_roic"] == pytest.approx(0.06)
    assert first_year["reinvestment_rate"] == pytest.approx(10 / 3)
    assert first_year["fcff"] == pytest.approx(-44.80)


def test_positive_growth_with_nonpositive_initial_marginal_roic_is_withheld() -> None:
    result = fcff_dcf(
        assumptions=fcff_assumptions(initial_marginal_roic=0.0),
        discount_rate={"wacc": 0.10},
        financials=financials(),
    )

    assert result["publication_state"] == "withheld"
    assert result["errors"]
    assert "marginal ROIC" in " ".join(result["errors"])


@pytest.mark.parametrize(
    "assumptions",
    [
        fcff_assumptions(
            initial_revenue_growth=0.0,
            terminal_growth=0.02,
            initial_marginal_roic=0.0,
        ),
        fcff_assumptions(
            initial_revenue_growth=0.0,
            terminal_growth=0.0,
            initial_marginal_roic=0.0,
            segment_forecast={
                "mode": "segment_operating_income",
                "segments": {
                    "growth_segment": {
                        "starting_revenue": 100.0,
                        "initial_revenue_growth": 0.05,
                        "starting_operating_margin": 0.20,
                        "target_operating_margin": 0.20,
                    }
                },
            },
        ),
    ],
)
def test_positive_explicit_growth_with_nonpositive_initial_roic_is_withheld(
    assumptions: dict,
) -> None:
    result = fcff_dcf(
        assumptions=assumptions,
        discount_rate={"wacc": 0.10},
        financials=financials(),
    )

    assert result["publication_state"] == "withheld"
    assert "marginal ROIC" in " ".join(result["errors"])


def normalized_financials() -> dict:
    return {
        "annual": [
            {"values": {"revenue": 100.0, "operating_income": 10.0}},
            {"values": {"revenue": 110.0, "operating_income": 11.0}},
            {"values": {"revenue": 121.0, "operating_income": 12.1}},
        ],
        "ttm": {
            "period_end": "2026-06-30",
            "values": {"revenue": 121.0, "operating_income": 12.1},
        },
        "normalized": {"tax_rate": 0.25, "revenue_ttm_history": []},
    }


def operating_policy() -> dict:
    return {
        "forecast_years": 5,
        "archetype_median_growth": 0.07,
        "archetype_target_operating_margin": 0.10,
        "growth_persistence": 0.78,
        "margin_persistence": 0.78,
        "sales_to_capital": 3.0,
        "terminal_roic_premium": 0.05,
    }


def test_initial_roic_uses_operating_economics_and_terminal_roic_fades_to_wacc() -> None:
    discount_rate = {"wacc": 0.25}
    result = derive_forecast_assumptions(
        normalized_financials(),
        policy=operating_policy(),
        discount_rate=discount_rate,
        market=US_BASE,
    )

    expected_initial_roic = (
        result["target_operating_margin"]
        * (1 - 0.25)
        * operating_policy()["sales_to_capital"]
    )
    assert result["initial_marginal_roic"] == pytest.approx(expected_initial_roic)
    assert result["initial_marginal_roic"] < discount_rate["wacc"] + 0.03
    assert result["terminal_marginal_roic"] == pytest.approx(discount_rate["wacc"])
    assert result["terminal_roic_basis"] == "competitive_fade_to_wacc"


def test_scenarios_and_wacc_sensitivities_fade_terminal_roic_to_each_wacc() -> None:
    # Intentionally seed a stale terminal ROIC to prove synchronization repairs it.
    assumptions = fcff_assumptions(terminal_marginal_roic=0.15)
    discount_rate = {"wacc": 0.10}

    scenarios = scenario_set(
        assumptions=assumptions,
        discount_rate=discount_rate,
        financials=financials(),
    )
    expected_scenario_wacc = {"bear": 0.11, "base": 0.10, "bull": 0.09}
    for name, expected_wacc in expected_scenario_wacc.items():
        assert scenarios[name]["fcff_dcf"]["detail"]["terminal_marginal_roic"] == pytest.approx(
            expected_wacc
        )

    sensitivities = one_way_sensitivities(
        assumptions=assumptions,
        discount_rate=discount_rate,
        financials=financials(),
    )
    wacc_rows = [row for row in sensitivities if row["field"] == "wacc"]
    assert [row["terminal_marginal_roic"] for row in wacc_rows] == pytest.approx(
        [0.09, 0.11]
    )


def test_margin_scenarios_and_sensitivities_recompute_initial_roic() -> None:
    assumptions = fcff_assumptions()
    discount_rate = {"wacc": 0.10}

    scenarios = scenario_set(
        assumptions=assumptions,
        discount_rate=discount_rate,
        financials=financials(),
    )
    expected_by_scenario = {"bear": 0.432, "base": 0.48, "bull": 0.528}
    for name, expected_roic in expected_by_scenario.items():
        assert scenarios[name]["fcff_dcf"]["detail"]["initial_marginal_roic"] == pytest.approx(
            expected_roic
        )

    sensitivities = one_way_sensitivities(
        assumptions=assumptions,
        discount_rate=discount_rate,
        financials=financials(),
    )
    margin_rows = {
        row["delta"]: row["initial_marginal_roic"]
        for row in sensitivities
        if row["field"] == "target_operating_margin"
    }
    assert margin_rows == pytest.approx({-0.02: 0.432, 0.02: 0.528})
