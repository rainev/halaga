"""The research engine — a faithful Python port of the FinSight engine.js.

Pure, deterministic functions over a `company` dict shaped like the seeded
financials record: it carries `financials`, `valuation`, `dataConfidence`, plus
presentation fields (symbol, shortName, sector, color, insight, source). Nothing
here touches the DB, the network, or OpenAI — it's filing math only, so it's
fully testable and (like the original) sends nothing to any AI provider.
"""

import math
from typing import Any

# Philippine market assumptions (from the dataset). The workbook's U.S. AAA-bond
# input is replaced with a PH 10-year government-bond proxy.
ASSUMPTIONS: dict[str, Any] = {
    "valuationDate": "17 Jul 2026",
    "riskFreeRate": 0.07052,
    "grahamBaselineYield": 0.06,
    "corporateTaxReference": 0.25,
    "sourceLabel": "Bureau of the Treasury - 10-year T-bond auction, 23 Jun 2026",
    "sourceUrl": "https://www.treasury.gov.ph/wp-content/uploads/2026/06/"
    "Treasury-Bonds-Auction-Result-on-23-June-2026-.pdf",
    "note": "The workbook's U.S. AAA-bond input is replaced with a Philippine "
    "10-year government-bond proxy. The 6.0% normalizer is a transparent "
    "through-cycle assumption; 7.052% is the latest accepted 9.7-year average "
    "auction yield reviewed.",
}

RISK_PROFILES: dict[int, dict[str, str]] = {
    1: {"label": "Capital Keeper", "short": "Very cautious", "tone": "Protect first"},
    2: {"label": "Steady Builder", "short": "Cautious", "tone": "Prefer resilience"},
    3: {"label": "Balanced Explorer", "short": "Balanced", "tone": "Balance quality and growth"},
    4: {"label": "Growth Seeker", "short": "Adventurous", "tone": "Accept more variability"},
    5: {"label": "High-Conviction", "short": "Very adventurous", "tone": "Accept substantial risk"},
}

SENTIMENTS: dict[str, dict[str, Any]] = {
    "bear": {"label": "Bear", "fcfGrowth": -0.015, "discountRate": 0.015, "terminalGrowth": -0.005,
             "multipleFactor": 0.85, "epsGrowthPoints": -1, "dividendGrowth": -0.005},
    "base": {"label": "Base", "fcfGrowth": 0, "discountRate": 0, "terminalGrowth": 0,
             "multipleFactor": 1, "epsGrowthPoints": 0, "dividendGrowth": 0},
    "bull": {"label": "Bull", "fcfGrowth": 0.015, "discountRate": -0.01, "terminalGrowth": 0.005,
             "multipleFactor": 1.15, "epsGrowthPoints": 1, "dividendGrowth": 0.005},
}

_THRESHOLDS: dict[int, dict[str, float]] = {
    1: {"cashToDebt": 1, "debtToEquity": 0.6, "grossMargin": 0.45, "sgnaToGrossProfit": 0.25,
        "interestToOperatingIncome": 0.1, "netMargin": 0.2, "epsGrowth": 0.05,
        "retainedGrowth": 0.03, "taxTolerance": 0.04},
    2: {"cashToDebt": 0.75, "debtToEquity": 0.8, "grossMargin": 0.42, "sgnaToGrossProfit": 0.28,
        "interestToOperatingIncome": 0.15, "netMargin": 0.18, "epsGrowth": 0.02,
        "retainedGrowth": 0.02, "taxTolerance": 0.055},
    3: {"cashToDebt": 0.5, "debtToEquity": 1, "grossMargin": 0.4, "sgnaToGrossProfit": 0.3,
        "interestToOperatingIncome": 0.2, "netMargin": 0.15, "epsGrowth": 0,
        "retainedGrowth": 0.01, "taxTolerance": 0.07},
    4: {"cashToDebt": 0.3, "debtToEquity": 1.3, "grossMargin": 0.35, "sgnaToGrossProfit": 0.35,
        "interestToOperatingIncome": 0.3, "netMargin": 0.12, "epsGrowth": -0.1,
        "retainedGrowth": 0, "taxTolerance": 0.09},
    5: {"cashToDebt": 0.15, "debtToEquity": 1.8, "grossMargin": 0.3, "sgnaToGrossProfit": 0.4,
        "interestToOperatingIncome": 0.45, "netMargin": 0.08, "epsGrowth": -0.2,
        "retainedGrowth": -0.05, "taxTolerance": 0.12},
}

_WEIGHTS = {
    "grossMargin": 1.1, "sgnaToGrossProfit": 0.7, "interestToOperatingIncome": 1.15,
    "effectiveTaxRate": 0.35, "netMargin": 1.2, "epsGrowth": 1, "cashToDebt": 1.1,
    "debtToEquity": 1.2, "preferredStock": 0.25, "retainedGrowth": 0.7, "treasuryStock": 0.2,
}


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _safe_divide(num: Any, den: Any) -> float | None:
    return num / den if _finite(num) and _finite(den) and den != 0 else None


def get_thresholds(risk: int = 3) -> dict[str, float]:
    normalized = min(5, max(1, int(risk) if risk else 3))
    return dict(_THRESHOLDS[normalized])


def get_derived_metrics(company: dict) -> dict[str, float | None]:
    f = company["financials"]
    re_now, re_prev = f.get("retainedEarnings"), f.get("retainedEarningsPrevious")
    return {
        "cashToDebt": _safe_divide(f.get("cash"), f.get("debt")),
        "debtToEquity": _safe_divide(f.get("liabilities"), f.get("equity")),
        "grossMargin": _safe_divide(f.get("grossProfit"), f.get("revenue")),
        "operatingMargin": _safe_divide(f.get("operatingIncome"), f.get("revenue")),
        "sgnaToGrossProfit": _safe_divide(f.get("generalAdmin"), f.get("grossProfit")),
        "interestToOperatingIncome": _safe_divide(f.get("interestExpense"), f.get("operatingIncome")),
        "effectiveTaxRate": _safe_divide(f.get("taxExpense"), f.get("pretaxIncome")),
        "netMargin": _safe_divide(f.get("netIncome"), f.get("revenue")),
        "epsGrowth": _safe_divide(
            (f["eps"] - f["epsPrevious"]) if _finite(f.get("eps")) and _finite(f.get("epsPrevious")) else None,
            abs(f["epsPrevious"]) if _finite(f.get("epsPrevious")) else None,
        ),
        "retainedGrowth": None if re_now is None or re_prev is None
        else _safe_divide(re_now - re_prev, abs(re_prev)),
    }


def compare_metric(value: Any, target: Any, direction: str, tolerance: float = 0) -> dict[str, Any]:
    if value is None or not _finite(value):
        return {"status": "unavailable", "score": 0.55}
    if direction == "range":
        distance = abs(value - target)
        return {"status": "pass" if distance <= tolerance else "watch",
                "score": max(0.0, 1 - distance / max(tolerance * 2.5, 0.01))}
    if direction == "context":
        return {"status": "context", "score": 0.7}
    passed = value >= target if direction == "min" else value <= target
    if target == 0:
        score = 1.0 if passed else 0.0
    elif direction == "min" and target < 0:
        score = 1.0 if passed else max(0.0, 1 - (target - value) * 3)
    elif direction == "min":
        score = min(1.1, max(0.0, value / target))
    else:
        score = 1.1 if value == 0 else min(1.1, max(0.0, target / value))
    return {"status": "pass" if passed else "watch", "score": score}


def _eps_fmt(v: float) -> str:
    return f"{v:.3f}" if v < 1 else f"{v:.2f}"


def get_health_metrics(company: dict, risk: int = 3) -> dict[str, Any]:
    t = get_thresholds(risk)
    d = get_derived_metrics(company)
    f = company["financials"]

    pnl = [
        {"key": "grossMargin", "label": "Gross margin",
         "description": "Gross profit kept from each peso of revenue",
         "value": d["grossMargin"], "target": t["grossMargin"], "direction": "min", "format": "percent"},
        {"key": "sgnaToGrossProfit", "label": "G&A load",
         "description": "General and administrative cost as a share of gross profit",
         "value": d["sgnaToGrossProfit"], "target": t["sgnaToGrossProfit"], "direction": "max", "format": "percent"},
        {"key": "interestToOperatingIncome", "label": "Interest burden",
         "description": "Financing cost compared with operating income",
         "value": d["interestToOperatingIncome"], "target": t["interestToOperatingIncome"],
         "direction": "max", "format": "percent"},
        {"key": "effectiveTaxRate", "label": "Effective tax rate",
         "description": "Compared with the 25% Philippine corporate-tax reference",
         "value": d["effectiveTaxRate"], "target": ASSUMPTIONS["corporateTaxReference"],
         "direction": "range", "tolerance": t["taxTolerance"], "format": "percent"},
        {"key": "netMargin", "label": "Net margin",
         "description": "Profit left from each peso of revenue",
         "value": d["netMargin"], "target": t["netMargin"], "direction": "min", "format": "percent"},
        {"key": "epsGrowth", "label": "EPS direction",
         "description": f"PHP{_eps_fmt(f['eps'])} in 2025 vs PHP{_eps_fmt(f['epsPrevious'])} in 2024",
         "value": d["epsGrowth"], "target": t["epsGrowth"], "direction": "min", "format": "percent"},
    ]

    balance = [
        {"key": "cashToDebt", "label": "Cash coverage",
         "description": "Cash and equivalents compared with interest-bearing debt",
         "value": d["cashToDebt"], "target": t["cashToDebt"], "direction": "min", "format": "multiple"},
        {"key": "debtToEquity", "label": "Liabilities to equity",
         "description": "Total liabilities compared with total equity",
         "value": d["debtToEquity"], "target": t["debtToEquity"], "direction": "max", "format": "multiple"},
        {"key": "preferredStock", "label": "Preferred stock",
         "description": "No preferred stock separately reported in the reviewed balance sheet",
         "value": f.get("preferredStock"), "target": 0, "direction": "max", "format": "currency"},
        {"key": "retainedGrowth", "label": "Retained earnings growth",
         "description": "Change in accumulated earnings available to support the business",
         "value": d["retainedGrowth"], "target": t["retainedGrowth"], "direction": "min", "format": "percent"},
        {"key": "treasuryStock", "label": "Treasury stock",
         "description": "Repurchased shares are present" if (f.get("treasuryStock") or 0) > 0
         else "No treasury stock reported",
         "value": f.get("treasuryStock"), "target": None, "direction": "context", "format": "currency"},
    ]

    for metric in [*pnl, *balance]:
        metric.update(compare_metric(metric["value"], metric["target"],
                                     metric["direction"], metric.get("tolerance", 0)))

    return {"pnl": pnl, "balance": balance, "thresholds": t, "derived": d}


def score_company(company: dict, risk: int = 3) -> int:
    h = get_health_metrics(company, risk)
    metrics = [*h["pnl"], *h["balance"]]
    total_weight = sum(_WEIGHTS[m["key"]] for m in metrics)
    health = sum(min(1, m["score"]) * _WEIGHTS[m["key"]] for m in metrics)
    return round((health / total_weight) * 88 + company["dataConfidence"] * 12)


def calculate_dcf(company: dict, sentiment: str = "base") -> dict[str, Any]:
    v = company["valuation"]
    adj = SENTIMENTS.get(sentiment, SENTIMENTS["base"])
    growth = max(-0.05, min(0.15, v["fcfGrowth"] + adj["fcfGrowth"]))
    terminal_growth = max(0, v["terminalGrowth"] + adj["terminalGrowth"])
    discount_rate = max(terminal_growth + 0.025, v["discountRate"] + adj["discountRate"])
    present_value = 0.0
    future_fcf = v["normalizedFcf"]
    for year in range(1, 6):
        future_fcf *= 1 + growth
        present_value += future_fcf / (1 + discount_rate) ** year
    terminal_value = (future_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    enterprise_value = present_value + terminal_value / (1 + discount_rate) ** 5
    net_debt = company["financials"]["debt"] - company["financials"]["cash"]
    equity_value = enterprise_value - net_debt
    return {
        "perShare": max(0.0, equity_value / company["financials"]["shares"]),
        "enterpriseValue": enterprise_value, "equityValue": equity_value,
        "growth": growth, "terminalGrowth": terminal_growth, "discountRate": discount_rate,
        "normalizedFcf": v["normalizedFcf"],
    }


def calculate_graham(company: dict, sentiment: str = "base") -> dict[str, Any]:
    adj = SENTIMENTS.get(sentiment, SENTIMENTS["base"])
    growth_percent = max(0, company["valuation"]["epsGrowthPercent"] + adj["epsGrowthPoints"])
    value = (company["financials"]["eps"] * (8.5 + 2 * growth_percent)
             * (ASSUMPTIONS["grahamBaselineYield"] / ASSUMPTIONS["riskFreeRate"]))
    return {"perShare": max(0.0, value), "growthPercent": growth_percent}


def calculate_multiples(company: dict, sentiment: str = "base") -> dict[str, Any]:
    adj = SENTIMENTS.get(sentiment, SENTIMENTS["base"])
    peer_pe = company["valuation"]["peerPe"] * adj["multipleFactor"]
    return {"perShare": company["financials"]["eps"] * peer_pe, "peerPe": peer_pe}


def calculate_ddm(company: dict, sentiment: str = "base") -> dict[str, Any] | None:
    v = company["valuation"]
    if not _finite(v.get("dividendPerShare")):
        return None
    adj = SENTIMENTS.get(sentiment, SENTIMENTS["base"])
    growth = max(0, v["dividendGrowth"] + adj["dividendGrowth"])
    discount_rate = max(growth + 0.02, v["dividendDiscountRate"] + adj["discountRate"])
    next_dividend = v["dividendPerShare"] * (1 + growth)
    return {"perShare": next_dividend / (discount_rate - growth),
            "growth": growth, "discountRate": discount_rate}


def calculate_valuation(company: dict, sentiment: str = "base") -> dict[str, Any]:
    models = {
        "dcf": calculate_dcf(company, sentiment),
        "graham": calculate_graham(company, sentiment),
        "multiples": calculate_multiples(company, sentiment),
        "ddm": calculate_ddm(company, sentiment),
    }
    weights = company["valuation"]["weights"]
    weighted_value = 0.0
    active_weight = 0.0
    for key, result in models.items():
        weight = weights.get(key, 0)
        if result and _finite(result.get("perShare")) and weight > 0:
            weighted_value += result["perShare"] * weight
            active_weight += weight
    values = [m["perShare"] for m in models.values() if m]
    return {
        "blended": weighted_value / active_weight if active_weight else 0.0,
        "low": min(values), "high": max(values), "models": models,
    }


def build_smart_brief(company: dict, risk: int = 3, sentiment: str = "base") -> dict[str, Any]:
    profile = RISK_PROFILES.get(risk, RISK_PROFILES[3])
    health = get_health_metrics(company, risk)
    metrics = [m for m in [*health["pnl"], *health["balance"]]
               if m["status"] not in ("context", "unavailable")]
    passes = sorted([m for m in metrics if m["status"] == "pass"], key=lambda m: m["score"], reverse=True)
    watches = sorted([m for m in metrics if m["status"] == "watch"], key=lambda m: m["score"])
    valuation = calculate_valuation(company, sentiment)
    score = score_company(company, risk)
    top_pass = passes[0] if passes else None
    top_watch = watches[0] if watches else None

    stance = "Needs a closer look"
    if score >= 78:
        stance = "Stronger fundamentals in this test group"
    elif score >= 65:
        stance = "Mixed, with investable strengths"

    paragraphs = [
        f"{company['shortName']} clears {len(passes)} of {len(metrics)} available checks "
        f"for a {profile['short'].lower()} investor. "
        + (f"{top_pass['label']} is a relative strength. " if top_pass
           else "No single metric leads the case. ")
        + (f"{top_watch['label']} is the first item to investigate."
           if top_watch else "No major threshold miss appears in the available set."),
        f"Under the {SENTIMENTS[sentiment]['label'].lower()} case, the filing-based models center "
        f"on PHP{valuation['blended']:.2f} per share, with a PHP{valuation['low']:.2f}-"
        f"PHP{valuation['high']:.2f} range. This is an intrinsic-value estimate, not a market quote.",
    ]

    return {
        "headline": stance, "score": score, "paragraphs": paragraphs,
        "passLabels": [m["label"] for m in passes[:3]],
        "watchLabels": [m["label"] for m in watches[:3]],
    }
