"""Relative (multiples) valuation via peer P/E.

Values a target company by applying its peer group's average/median P/E to the
target's EPS. For the PH market, peers should be same-sector PSE names.
"""

from statistics import mean, median

from .common import summarize

MIN_VALID_PEERS = 4


def multiples_valuation(
    *,
    peers: list[dict],
    target_eps: float,
    current_price: float | None = None,
) -> dict:
    """`peers` is a list of {ticker?, price, eps}. Peers with non-positive EPS
    are skipped (a negative/zero P/E is meaningless)."""
    peer_pes = []
    for p in peers:
        eps = p.get("eps")
        price = p.get("price")
        if eps is None or price is None or eps <= 0:
            continue
        peer_pes.append({"ticker": p.get("ticker"), "price": price, "eps": eps, "pe": price / eps})

    if target_eps <= 0:
        raise ValueError("target_eps must be positive for P/E valuation")
    if len(peer_pes) < MIN_VALID_PEERS:
        raise ValueError("Need at least four valid peers with positive EPS")

    pes = [p["pe"] for p in peer_pes]
    avg_pe = mean(pes)
    med_pe = median(pes)

    value_on_average = avg_pe * target_eps
    value_on_median = med_pe * target_eps

    # Headline intrinsic value uses the median (robust to outlier peers).
    upside, verdict = summarize(value_on_median, current_price)
    return {
        "model": "multiples",
        "intrinsic_value": value_on_median,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {"status": "pass", "warnings": [], "valid_peer_count": len(peer_pes)},
        "detail": {
            "metric": "pe",
            "target_eps": target_eps,
            "average_pe": avg_pe,
            "median_pe": med_pe,
            "value_on_average": value_on_average,
            "value_on_median": value_on_median,
            "peers": peer_pes,
        },
    }


def pb_valuation(
    *,
    peers: list[dict],
    target_book_value_per_share: float,
    current_price: float | None = None,
) -> dict:
    """Price-to-Book multiple — the standard lens for banks/financials, where the
    balance sheet (book equity) is the earning engine and is far steadier than
    swingy reported earnings. `peers` is a list of {ticker?, price,
    book_value_per_share}."""
    rows = []
    for p in peers:
        price = p.get("price")
        bvps = p.get("book_value_per_share")
        if price is None or bvps is None or bvps <= 0:
            continue
        rows.append({"ticker": p.get("ticker"), "price": price, "bvps": bvps, "pb": price / bvps})

    if target_book_value_per_share <= 0:
        raise ValueError("target_book_value_per_share must be positive for P/B valuation")
    if len(rows) < MIN_VALID_PEERS:
        raise ValueError("Need at least four valid peers with positive book value per share")

    pbs = [r["pb"] for r in rows]
    avg_pb = mean(pbs)
    med_pb = median(pbs)
    value = med_pb * target_book_value_per_share

    upside, verdict = summarize(value, current_price)
    return {
        "model": "multiples",
        "intrinsic_value": value,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {"status": "pass", "warnings": [], "valid_peer_count": len(rows)},
        "detail": {
            "metric": "pb",
            "target_book_value_per_share": target_book_value_per_share,
            "average_pb": avg_pb,
            "median_pb": med_pb,
            "value_on_median": value,
            "peers": rows,
        },
    }


def ev_ebitda_valuation(
    *,
    peers: list[dict],
    target_ebitda: float,
    cash: float,
    total_debt: float,
    shares_outstanding: float,
    current_price: float | None = None,
) -> dict:
    """EV/EBITDA multiple — capital-structure-neutral, so it fairly compares firms
    with different debt loads. Applies the peer median EV/EBITDA to the target's
    EBITDA to get enterprise value, then bridges to equity per share. `peers` is a
    list of {ticker?, ev, ebitda}."""
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    if target_ebitda <= 0:
        raise ValueError("target_ebitda must be positive for EV/EBITDA valuation")

    rows = []
    for p in peers:
        ev = p.get("ev")
        ebitda = p.get("ebitda")
        if ev is None or ebitda is None or ebitda <= 0:
            continue
        rows.append({"ticker": p.get("ticker"), "ev": ev, "ebitda": ebitda, "ev_ebitda": ev / ebitda})

    if len(rows) < MIN_VALID_PEERS:
        raise ValueError("Need at least four valid peers with positive EBITDA")

    multiples = [r["ev_ebitda"] for r in rows]
    avg_mult = mean(multiples)
    med_mult = median(multiples)

    enterprise_value = med_mult * target_ebitda
    equity_value = enterprise_value + cash - total_debt
    value_per_share = equity_value / shares_outstanding

    upside, verdict = summarize(value_per_share, current_price)
    return {
        "model": "multiples",
        "intrinsic_value": value_per_share,
        "current_price": current_price,
        "upside_pct": upside,
        "verdict": verdict,
        "validation": {"status": "pass", "warnings": [], "valid_peer_count": len(rows)},
        "detail": {
            "metric": "ev_ebitda",
            "target_ebitda": target_ebitda,
            "average_ev_ebitda": avg_mult,
            "median_ev_ebitda": med_mult,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "cash": cash,
            "total_debt": total_debt,
            "shares_outstanding": shares_outstanding,
            "peers": rows,
        },
    }
