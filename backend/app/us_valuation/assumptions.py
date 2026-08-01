"""Versioned, filing-only U.S. forecast and discount-rate policy."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from importlib.resources import files
from statistics import median
from typing import Any


@dataclass(frozen=True)
class USMarketAssumptions:
    policy_version: str = "US-RATES-1.0"
    risk_free_rate: float = 0.0468
    risk_free_tenor: str = "10-year U.S. Treasury CMT"
    risk_free_effective_date: str = "2026-07-30"
    risk_free_source: str = "U.S. Department of the Treasury"
    risk_free_source_url: str = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/TextView?field_tdr_date_value_month=202607"
        "&type=daily_treasury_yield_curve"
    )
    equity_risk_premium: float = 0.045
    erp_effective_date: str = "2026-07-01"
    erp_method: str = "FinSight governed U.S. ERP policy"
    erp_note: str = (
        "Provisional annual policy assumption; it is not an official government rate "
        "or a company-specific observed premium."
    )
    terminal_growth: float = 0.02

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


US_BASE = USMarketAssumptions()


class ForecastEvidenceUnavailable(ValueError):
    """Raised when governed segment evidence has no matching normalized period."""

    def __init__(
        self,
        *,
        period_end: str,
        available_periods: list[str],
        reason: str | None = None,
    ) -> None:
        self.period_end = period_end
        self.available_periods = available_periods
        self.reason = reason
        super().__init__(
            (f"{reason}. " if reason else "")
            + "No governed segment forecast evidence is available for normalized "
            f"period {period_end}; configured periods: "
            f"{', '.join(available_periods) or 'none'}"
        )


def load_issuer_forecast_evidence(cik: str) -> dict[str, Any] | None:
    path = files(__package__).joinpath("config/issuer_forecasts.json")
    config = json.loads(path.read_text(encoding="utf-8"))
    evidence = config.get("issuers", {}).get(str(cik).zfill(10))
    if evidence is None:
        return None
    return {
        "registry_version": config["version"],
        **evidence,
    }


def _validated_field_provenance(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve exact private provenance for every governed segment input."""
    expected = {
        "consolidated_ttm.revenue",
        "consolidated_ttm.operating_income",
    }
    for segment in evidence["segments"]:
        expected.update(
            f"segments.{segment}.{field}"
            for field in (
                *(f"annual_revenue[{index}]" for index in range(3)),
                *(f"annual_operating_income[{index}]" for index in range(3)),
                "latest_ytd_revenue",
                "prior_ytd_revenue",
                "latest_ytd_operating_income",
                "prior_ytd_operating_income",
                "ttm_revenue",
                "ttm_operating_income",
                "archetype_growth_anchor",
            )
        )
    mapped = evidence.get("field_provenance", {})
    if set(mapped) != expected:
        raise ValueError("Governed segment field provenance must cover each input exactly once")
    contexts = evidence.get("provenance_contexts", {})
    resolved: dict[str, dict[str, Any]] = {}
    required = {
        "fiscal_year",
        "fiscal_period",
        "duration_basis",
        "unit",
        "table_line",
        "status",
        "derivation",
    }
    for path, context_id in mapped.items():
        context = contexts.get(context_id)
        if not isinstance(context, dict) or not required <= set(context):
            raise ValueError(f"Governed provenance context is incomplete for {path}")
        source_ids = context.get("source_ids", [])
        sources = [
            source for source in evidence["sources"] if source.get("id") in source_ids
        ]
        if len(sources) != len(source_ids):
            raise ValueError(f"Governed provenance source is missing for {path}")
        resolved[path] = {
            **context,
            "source_accessions": [source["accession"] for source in sources],
            "sources": sources,
        }
    return resolved


def _cagr(values: list[float]) -> float:
    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        raise ValueError("CAGR needs at least two positive values")
    return (values[-1] / values[0]) ** (1 / (len(values) - 1)) - 1


def _fade_weight(persistence: float, year: int, years: int) -> float:
    if years <= 1 or year >= years:
        return 0.0
    denominator = persistence - persistence**years
    if abs(denominator) < 1e-12:
        return (years - year) / (years - 1)
    return (persistence**year - persistence**years) / denominator


def build_discount_rate(
    *,
    policy: dict[str, Any],
    tax_rate: float,
    market: USMarketAssumptions = US_BASE,
    company_overlay: float | None = None,
) -> dict[str, Any]:
    debt_weight = float(policy["target_debt_weight"])
    if not 0 <= debt_weight < 1:
        raise ValueError("target_debt_weight must be in [0, 1)")
    equity_weight = 1 - debt_weight
    debt_to_equity = debt_weight / equity_weight if equity_weight else 0.0
    unlevered_beta = float(policy["unlevered_policy_beta"])
    levered_policy_beta = unlevered_beta * (
        1 + (1 - tax_rate) * debt_to_equity
    )
    overlay = (
        float(policy.get("normal_company_overlay", 0.0))
        if company_overlay is None
        else company_overlay
    )
    if overlay not in {0.0, 0.005, 0.01}:
        raise ValueError("company_overlay must be 0.0%, 0.5%, or 1.0%")
    cost_of_equity = (
        market.risk_free_rate
        + levered_policy_beta * market.equity_risk_premium
        + overlay
    )
    debt_spread = float(policy["default_debt_spread"])
    pre_tax_cost_of_debt = market.risk_free_rate + debt_spread
    wacc = (
        equity_weight * cost_of_equity
        + debt_weight * pre_tax_cost_of_debt * (1 - tax_rate)
    )
    return {
        "calibration_type": "policy_calibrated",
        "market_observed": False,
        "unlevered_policy_beta": unlevered_beta,
        "levered_policy_beta": levered_policy_beta,
        "company_risk_overlay": overlay,
        "target_equity_weight": equity_weight,
        "target_debt_weight": debt_weight,
        "pre_tax_cost_of_debt": pre_tax_cost_of_debt,
        "default_debt_spread": debt_spread,
        "cost_of_equity": cost_of_equity,
        "wacc": wacc,
        "tax_rate": tax_rate,
        "market_assumptions": market.snapshot(),
        "limitations": [
            "No stock-price-derived beta is used.",
            "Capital weights are governed archetype targets, not observed market-value weights.",
            "The debt spread is an archetype fallback because a current issuer borrowing yield was not available from standardized Apple Companyfacts.",
        ],
    }


def derive_forecast_assumptions(
    financials: dict[str, Any],
    *,
    policy: dict[str, Any],
    discount_rate: dict[str, Any],
    market: USMarketAssumptions = US_BASE,
    issuer_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        issuer_evidence
        and issuer_evidence.get("forecast_mode") == "segment_operating_income"
    ):
        period_end = financials["ttm"]["period_end"]
        available_periods = sorted(issuer_evidence.get("periods", {}))
        period_evidence = issuer_evidence.get("periods", {}).get(period_end)
        if period_evidence is None:
            raise ForecastEvidenceUnavailable(
                period_end=period_end,
                available_periods=available_periods,
            )
        evidence_period_end = period_evidence.get("evidence_period_end")
        as_of_filed_date = period_evidence.get("as_of_filed_date")
        if evidence_period_end != period_end or not as_of_filed_date:
            raise ForecastEvidenceUnavailable(
                period_end=period_end,
                available_periods=available_periods,
                reason="Governed evidence period metadata is incomplete or mismatched",
            )
        invalid_sources = [
            source
            for source in period_evidence.get("sources", [])
            if (
                not source.get("period_end")
                or not source.get("filing_date")
                or source["period_end"] > evidence_period_end
                or source["filing_date"] > as_of_filed_date
            )
        ]
        if not period_evidence.get("sources") or invalid_sources:
            raise ForecastEvidenceUnavailable(
                period_end=period_end,
                available_periods=available_periods,
                reason="Governed evidence includes source periods or filing dates after its as-of cutoff",
            )
        issuer_evidence = {**issuer_evidence, **period_evidence}
        issuer_evidence["validated_field_provenance"] = _validated_field_provenance(
            issuer_evidence
        )

    annual = financials["annual"]
    latest_three = annual[-3:]
    revenues = [float(row["values"]["revenue"]) for row in latest_three]
    annual_cagr = _cagr(revenues)

    ttm_history = financials["normalized"].get("revenue_ttm_history", [])
    latest_ttm = float(financials["ttm"]["values"]["revenue"])
    ttm_yoy_growth = None
    if ttm_history:
        latest_end = financials["ttm"]["period_end"]
        comparable = [
            row
            for row in ttm_history
            if 350
            <= abs(
                (
                    date.fromisoformat(latest_end)
                    - date.fromisoformat(row["period_end"])
                ).days
            )
            <= 380
        ]
        if comparable and comparable[-1]["value"] > 0:
            ttm_yoy_growth = latest_ttm / comparable[-1]["value"] - 1
    if ttm_yoy_growth is None:
        ttm_yoy_growth = annual_cagr

    # When issuer history exists, the generic archetype anchor is capped at
    # 25%; the remaining weight stays with observed company history.
    generic_growth_weights = {
        "ttm_history": 0.375,
        "annual_history": 0.375,
        "archetype_anchor": 0.25,
    }
    initial_growth = (
        generic_growth_weights["ttm_history"] * ttm_yoy_growth
        + generic_growth_weights["annual_history"] * annual_cagr
        + generic_growth_weights["archetype_anchor"]
        * float(policy["archetype_median_growth"])
    )
    initial_growth = min(max(initial_growth, -0.10), 0.20)

    margins = [
        row["values"]["operating_income"] / row["values"]["revenue"]
        for row in annual[-5:]
        if row["values"]["operating_income"] is not None
        and row["values"]["revenue"] > 0
    ]
    ttm_margin = (
        financials["ttm"]["values"]["operating_income"]
        / financials["ttm"]["values"]["revenue"]
    )
    normalized_company_margin = median([ttm_margin, *margins])
    company_weight = 0.70 if len(margins) >= 5 else 0.50
    target_margin = (
        company_weight * normalized_company_margin
        + (1 - company_weight)
        * float(policy["archetype_target_operating_margin"])
    )
    normalized_operating_margin = normalized_company_margin

    wacc = float(discount_rate["wacc"])
    segment_forecast = None
    forecast_years = int(policy["forecast_years"])
    growth_persistence = float(policy["growth_persistence"])
    margin_persistence = float(policy["margin_persistence"])
    terminal_roic_premium = float(policy["terminal_roic_premium"])
    target_opex_ratio = None
    evidence_status = "standardized_consolidated_facts"
    evidence_sources: list[dict[str, Any]] = []
    forecast_policy_version = "US-FORECAST-1.0"

    if issuer_evidence and issuer_evidence.get("forecast_mode") == "segment_gross_profit":
        weights = issuer_evidence["growth_weights"]
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
            raise ValueError("Issuer growth weights must sum to 1.0")
        if float(weights["archetype_anchor"]) > 0.25:
            raise ValueError("Archetype growth weight exceeds the 25% policy limit")

        segments = {}
        total_segment_revenue = 0.0
        total_segment_gross_profit = 0.0
        for key, segment in issuer_evidence["segments"].items():
            annual_segment_revenue = [
                float(value) for value in segment["annual_revenue"]
            ]
            annual_segment_gross_profit = [
                float(value) for value in segment["annual_gross_profit"]
            ]
            segment_cagr = _cagr(annual_segment_revenue)
            recent_ytd_growth = (
                float(segment["latest_ytd_revenue"])
                / float(segment["prior_ytd_revenue"])
                - 1
            )
            segment_growth = (
                float(weights["recent_ytd"]) * recent_ytd_growth
                + float(weights["company_history"]) * segment_cagr
                + float(weights["archetype_anchor"])
                * float(segment["archetype_growth_anchor"])
            )
            segment_growth = min(max(segment_growth, -0.10), 0.20)
            ttm_segment_revenue = float(segment["ttm_revenue"])
            ttm_segment_gross_profit = float(segment["ttm_gross_profit"])
            gross_margins = [
                gross_profit / revenue
                for gross_profit, revenue in zip(
                    annual_segment_gross_profit,
                    annual_segment_revenue,
                )
                if revenue > 0
            ]
            starting_gross_margin = (
                ttm_segment_gross_profit / ttm_segment_revenue
            )
            target_gross_margin = median(
                [*gross_margins, starting_gross_margin]
            )
            segments[key] = {
                "label": segment["label"],
                "starting_revenue": ttm_segment_revenue,
                "initial_revenue_growth": segment_growth,
                "starting_gross_margin": starting_gross_margin,
                "target_gross_margin": target_gross_margin,
                "evidence": {
                    "recent_ytd_growth": recent_ytd_growth,
                    "company_history_cagr": segment_cagr,
                    "archetype_growth_anchor": float(
                        segment["archetype_growth_anchor"]
                    ),
                    "growth_weights": {
                        name: float(value) for name, value in weights.items()
                    },
                },
            }
            total_segment_revenue += ttm_segment_revenue
            total_segment_gross_profit += ttm_segment_gross_profit

        if abs(total_segment_revenue - latest_ttm) / latest_ttm > 0.001:
            raise ValueError("Segment revenue does not reconcile to consolidated TTM revenue")
        ttm_opex = float(issuer_evidence["ttm_operating_expense"])
        if (
            abs(
                total_segment_gross_profit
                - ttm_opex
                - float(financials["ttm"]["values"]["operating_income"])
            )
            / total_segment_gross_profit
            > 0.001
        ):
            raise ValueError(
                "Segment gross profit and operating expense do not reconcile to TTM operating income"
            )
        annual_opex_ratios = [
            float(expense) / float(revenue)
            for expense, revenue in zip(
                issuer_evidence["annual_operating_expense"],
                issuer_evidence["annual_total_revenue"],
            )
            if float(revenue) > 0
        ]
        starting_opex_ratio = ttm_opex / latest_ttm
        target_opex_ratio = median(
            [*annual_opex_ratios, starting_opex_ratio]
        )
        segment_forecast_years = int(issuer_evidence["forecast_years"])
        segment_growth_persistence = float(
            issuer_evidence["growth_persistence"]
        )
        projected_segment_revenues = {
            key: segment["starting_revenue"]
            for key, segment in segments.items()
        }
        for year in range(1, segment_forecast_years + 1):
            weight = _fade_weight(
                segment_growth_persistence,
                year,
                segment_forecast_years,
            )
            for key, segment in segments.items():
                projected_growth = market.terminal_growth + (
                    segment["initial_revenue_growth"]
                    - market.terminal_growth
                ) * weight
                projected_segment_revenues[key] *= 1 + projected_growth
        projected_total_revenue = sum(projected_segment_revenues.values())
        target_margin = (
            sum(
                projected_segment_revenues[key]
                / projected_total_revenue
                * segment["target_gross_margin"]
                for key, segment in segments.items()
            )
            - target_opex_ratio
        )
        initial_growth = sum(
            segment["starting_revenue"]
            / latest_ttm
            * segment["initial_revenue_growth"]
            for segment in segments.values()
        )
        segment_forecast = {
            "mode": "segment_gross_profit",
            "segments": segments,
            "starting_operating_expense_ratio": starting_opex_ratio,
            "target_operating_expense_ratio": target_opex_ratio,
            "reconciliation": {
                "segment_revenue_to_consolidated": "pass",
                "gross_profit_less_opex_to_operating_income": "pass",
            },
        }
        forecast_years = int(issuer_evidence["forecast_years"])
        growth_persistence = float(issuer_evidence["growth_persistence"])
        margin_persistence = float(issuer_evidence["margin_persistence"])
        terminal_roic_premium = float(
            issuer_evidence["terminal_roic_premium"]
        )
        evidence_status = issuer_evidence["evidence_status"]
        evidence_sources = list(issuer_evidence["sources"])
        forecast_policy_version = issuer_evidence[
            "forecast_policy_version"
        ]

    if issuer_evidence and issuer_evidence.get("forecast_mode") == "segment_operating_income":
        weights = issuer_evidence["growth_weights"]
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
            raise ValueError("Issuer growth weights must sum to 1.0")
        if float(weights["archetype_anchor"]) > 0.25:
            raise ValueError("Archetype growth weight exceeds the 25% policy limit")

        segments = {}
        total_segment_revenue = 0.0
        total_segment_operating_income = 0.0
        for key, segment in issuer_evidence["segments"].items():
            annual_segment_revenue = [
                float(value) for value in segment["annual_revenue"]
            ]
            annual_segment_operating_income = [
                float(value) for value in segment["annual_operating_income"]
            ]
            segment_cagr = _cagr(annual_segment_revenue)
            recent_ytd_growth = (
                float(segment["latest_ytd_revenue"])
                / float(segment["prior_ytd_revenue"])
                - 1
            )
            segment_growth = (
                float(weights["recent_ytd"]) * recent_ytd_growth
                + float(weights["company_history"]) * segment_cagr
                + float(weights["archetype_anchor"])
                * float(segment["archetype_growth_anchor"])
            )
            segment_growth = min(max(segment_growth, -0.10), 0.20)
            ttm_segment_revenue = float(segment["ttm_revenue"])
            ttm_segment_operating_income = float(
                segment["ttm_operating_income"]
            )
            operating_margins = [
                operating_income / revenue
                for operating_income, revenue in zip(
                    annual_segment_operating_income,
                    annual_segment_revenue,
                )
                if revenue > 0
            ]
            starting_operating_margin = (
                ttm_segment_operating_income / ttm_segment_revenue
            )
            target_operating_margin = median(
                [*operating_margins, starting_operating_margin]
            )
            segments[key] = {
                "label": segment["label"],
                "starting_revenue": ttm_segment_revenue,
                "initial_revenue_growth": segment_growth,
                "starting_operating_margin": starting_operating_margin,
                "target_operating_margin": target_operating_margin,
                "evidence": {
                    "recent_ytd_growth": recent_ytd_growth,
                    "company_history_cagr": segment_cagr,
                    "archetype_growth_anchor": float(
                        segment["archetype_growth_anchor"]
                    ),
                    "growth_weights": {
                        name: float(value) for name, value in weights.items()
                    },
                },
            }
            total_segment_revenue += ttm_segment_revenue
            total_segment_operating_income += ttm_segment_operating_income

        consolidated_operating_income = float(
            financials["ttm"]["values"]["operating_income"]
        )
        consolidated_ttm = issuer_evidence["consolidated_ttm"]
        evidence_revenue = float(consolidated_ttm["revenue"])
        evidence_operating_income = float(consolidated_ttm["operating_income"])
        if abs(evidence_revenue - latest_ttm) / latest_ttm > 0.001:
            raise ValueError(
                "Governed consolidated TTM revenue does not reconcile to normalized TTM revenue"
            )
        if (
            abs(evidence_operating_income - consolidated_operating_income)
            / abs(consolidated_operating_income)
            > 0.001
        ):
            raise ValueError(
                "Governed consolidated TTM operating income does not reconcile to normalized TTM operating income"
            )
        if abs(total_segment_revenue - evidence_revenue) / evidence_revenue > 0.001:
            raise ValueError("Segment revenue does not reconcile to consolidated TTM revenue")
        if (
            abs(total_segment_operating_income - evidence_operating_income)
            / abs(evidence_operating_income)
            > 0.001
        ):
            raise ValueError(
                "Segment operating income does not reconcile to consolidated TTM operating income"
            )

        segment_forecast_years = int(issuer_evidence["forecast_years"])
        segment_growth_persistence = float(
            issuer_evidence["growth_persistence"]
        )
        projected_segment_revenues = {
            key: segment["starting_revenue"]
            for key, segment in segments.items()
        }
        for year in range(1, segment_forecast_years + 1):
            weight = _fade_weight(
                segment_growth_persistence,
                year,
                segment_forecast_years,
            )
            for key, segment in segments.items():
                projected_growth = market.terminal_growth + (
                    segment["initial_revenue_growth"] - market.terminal_growth
                ) * weight
                projected_segment_revenues[key] *= 1 + projected_growth
        projected_total_revenue = sum(projected_segment_revenues.values())
        target_margin = sum(
            projected_segment_revenues[key]
            / projected_total_revenue
            * segment["target_operating_margin"]
            for key, segment in segments.items()
        )
        initial_growth = sum(
            segment["starting_revenue"]
            / latest_ttm
            * segment["initial_revenue_growth"]
            for segment in segments.values()
        )
        segment_forecast = {
            "mode": "segment_operating_income",
            "segments": segments,
            "starting_operating_margin": ttm_margin,
            "target_operating_margin": target_margin,
            "reconciliation": {
                "segment_revenue_to_consolidated": "pass",
                "segment_operating_income_to_consolidated": "pass",
            },
        }
        forecast_years = segment_forecast_years
        growth_persistence = segment_growth_persistence
        margin_persistence = float(issuer_evidence["margin_persistence"])
        terminal_roic_premium = float(
            issuer_evidence["terminal_roic_premium"]
        )
        evidence_status = issuer_evidence["evidence_status"]
        evidence_sources = list(issuer_evidence["sources"])
        forecast_policy_version = issuer_evidence[
            "forecast_policy_version"
        ]

    return {
        "forecast_policy_version": forecast_policy_version,
        "forecast_registry_version": (
            issuer_evidence.get("registry_version")
            if issuer_evidence
            else None
        ),
        "forecast_years": forecast_years,
        "starting_revenue": latest_ttm,
        "starting_operating_margin": ttm_margin,
        "initial_revenue_growth": initial_growth,
        "target_operating_margin": target_margin,
        "normalized_operating_margin": normalized_operating_margin,
        "target_operating_expense_ratio": target_opex_ratio,
        "segment_forecast": segment_forecast,
        "sales_to_capital": float(policy["sales_to_capital"]),
        "terminal_growth": market.terminal_growth,
        "growth_persistence": growth_persistence,
        "margin_persistence": margin_persistence,
        "normalized_tax_rate": float(financials["normalized"]["tax_rate"]),
        "initial_marginal_roic": max(
            target_margin
            * (1 - float(financials["normalized"]["tax_rate"]))
            * float(policy["sales_to_capital"]),
            wacc + 0.03,
        ),
        "terminal_marginal_roic": wacc + terminal_roic_premium,
        "forecast_evidence_status": evidence_status,
        "forecast_evidence_sources": evidence_sources,
        "forecast_evidence_field_provenance": (
            issuer_evidence.get("validated_field_provenance", {})
            if issuer_evidence
            else {}
        ),
        "evidence": {
            "ttm_yoy_growth": ttm_yoy_growth,
            "available_history_cagr": annual_cagr,
            "available_history_observations": len(latest_three),
            "available_history_intervals": len(latest_three) - 1,
            "archetype_median_growth": float(policy["archetype_median_growth"]),
            "normalized_company_margin": normalized_company_margin,
            "archetype_target_margin": float(
                policy["archetype_target_operating_margin"]
            ),
            "company_margin_weight": company_weight,
            "generic_growth_weights": generic_growth_weights,
        },
        "maintained_assumptions": [
            (
                "segment_initial_revenue_growth"
                if segment_forecast
                else "initial_revenue_growth"
            ),
            (
                "segment_target_operating_margin"
                if segment_forecast
                and segment_forecast["mode"] == "segment_operating_income"
                else "segment_target_gross_margin"
                if segment_forecast
                else "target_operating_margin"
            ),
            *(
                ["target_operating_expense_ratio"]
                if segment_forecast
                and segment_forecast["mode"] == "segment_gross_profit"
                else []
            ),
            "sales_to_capital",
            "terminal_growth",
        ],
    }
