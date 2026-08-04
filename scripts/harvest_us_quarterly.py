#!/usr/bin/env python3
"""Batch quarterly-data harvest + coverage triage for a US issuer universe.

Runs a list of CIKs through the same classification and Companyfacts
normalization the single-issuer pipeline uses, but tuned for scale: it never
raises on a bad issuer, it records *why* an issuer is not publishable, and it
stamps each one with its latest reported period and filing recency so a weekly
re-run shows the earnings-season completeness curve.

Source of SEC data:
  --source api    per-company data.sec.gov API via the throttled SecClient
                  (good for a small smoke test, no big download).
  --source bulk   read CIK*.json extracted from the nightly bulk ZIPs with
                  scripts/fetch_sec_bulk.py (the way to run the full 500).
  --source auto   use bulk files when present in --bulk-dir, else the API.

Outputs (under --out, which must stay in the git-ignored archive tree):
  coverage.csv     one row per issuer (the triage report)
  coverage.json    same data plus run metadata

Usage:
  SEC_USER_AGENT='FinSight contact@example.com' \
    python3 scripts/harvest_us_quarterly.py --sample --as-of 2026-08-01 \
      --out archive/local-audit/us/_harvest
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.us_valuation import build_us_valuation  # noqa: E402
from app.us_valuation.classification import classify_issuer  # noqa: E402
from app.us_valuation.sec_client import SecClient, normalize_cik  # noqa: E402
from app.us_valuation.xbrl import CompanyFactsNormalizer  # noqa: E402


# A sector-diverse smoke sample: some route to supported archetypes today,
# most deliberately do not, so the triage report shows the real coverage gap.
SAMPLE = [
    ("AAPL", "0000320193"), ("MSFT", "0000789019"), ("ANET", "0001596532"),
    ("ORCL", "0001341439"), ("ADBE", "0000796343"), ("NVDA", "0001045810"),
    ("JPM", "0000019617"),  ("XOM", "0000034088"),  ("WMT", "0000104169"),
    ("KO", "0000021344"),   ("JNJ", "0000200406"),  ("TSLA", "0001318605"),
    ("AMZN", "0001018724"), ("PG", "0000080424"),   ("DIS", "0001744489"),
]

CSV_FIELDS = [
    "ticker", "cik", "name", "sic", "sic_desc",
    "classified", "sector", "archetype", "confidence",
    "latest_period_end", "latest_form", "latest_filed", "days_since_filed",
    "quarterly_revenue_points", "ttm_revenue_points",
    "valuation_state", "note",
]


def _load_pair(source: str, bulk_dir: Path, client: SecClient | None, cik: str):
    """Return (submissions, companyfacts) from bulk files or the API."""
    if source in {"bulk", "auto"}:
        sub_path = bulk_dir / f"CIK{cik}-submissions.json"
        facts_path = bulk_dir / f"CIK{cik}-companyfacts.json"
        if sub_path.exists() and facts_path.exists():
            return (
                json.loads(sub_path.read_text(encoding="utf-8")),
                json.loads(facts_path.read_text(encoding="utf-8")),
            )
        if source == "bulk":
            raise FileNotFoundError(f"bulk files missing for CIK {cik}")
    if client is None:
        raise RuntimeError("API source requires SEC_USER_AGENT / SecClient")
    return client.submissions(cik), client.companyfacts(cik)


def _latest_filing(submissions: dict, as_of: str) -> dict:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    rows = []
    for i, form in enumerate(forms):
        if form in {"10-Q", "10-Q/A", "10-K", "10-K/A"}:
            filed = recent.get("filingDate", [None] * len(forms))[i]
            if filed and filed <= as_of:
                rows.append(
                    {
                        "form": form,
                        "filed": filed,
                        "period_end": recent.get("reportDate", [None] * len(forms))[i],
                    }
                )
    return max(rows, key=lambda r: (r["filed"], r["period_end"] or "")) if rows else {}


def _days_between(earlier: str, later: str) -> int | None:
    try:
        return (date.fromisoformat(later) - date.fromisoformat(earlier)).days
    except (TypeError, ValueError):
        return None


def harvest_one(source, bulk_dir, client, ticker, raw_cik, as_of) -> dict:
    cik = normalize_cik(raw_cik)
    row = {field: "" for field in CSV_FIELDS}
    row.update({"ticker": ticker, "cik": cik})
    try:
        submissions, companyfacts = _load_pair(source, bulk_dir, client, cik)
    except Exception as error:  # network / missing / parse
        row["valuation_state"] = "fetch_error"
        row["note"] = f"{type(error).__name__}: {error}"[:160]
        return row

    row["name"] = submissions.get("name", "")
    row["sic"] = str(submissions.get("sic") or "")
    row["sic_desc"] = submissions.get("sicDescription", "")
    if not row["ticker"]:
        row["ticker"] = (submissions.get("tickers") or [""])[0]

    latest = _latest_filing(submissions, as_of)
    row["latest_period_end"] = latest.get("period_end", "") or ""
    row["latest_form"] = latest.get("form", "") or ""
    row["latest_filed"] = latest.get("filed", "") or ""
    row["days_since_filed"] = (
        _days_between(latest["filed"], as_of) if latest.get("filed") else ""
    )

    # Classification triage (never fatal).
    try:
        classification = classify_issuer(submissions)
        row["classified"] = "yes"
        row["sector"] = classification["finsight_sector"]
        row["archetype"] = classification["primary_archetype"]
        row["confidence"] = classification["classification_confidence"]
    except Exception as error:
        row["classified"] = "no"
        row["note"] = f"classify: {error}"[:160]

    # Quarterly data extraction (works off Companyfacts even when a full
    # valuation is not yet possible).
    try:
        recent = submissions.get("filings", {}).get("recent", {})
        records = [
            {k: v[i] for k, v in recent.items() if isinstance(v, list) and i < len(v)}
            for i in range(len(recent.get("accessionNumber", [])))
        ]
        normalizer = CompanyFactsNormalizer(
            companyfacts,
            fiscal_year_end=submissions.get("fiscalYearEnd"),
            as_of_date=as_of,
            filing_records=records,
        )
        row["quarterly_revenue_points"] = len(
            normalizer.standalone_quarters("revenue", 8)
        )
        row["ttm_revenue_points"] = len(normalizer.ttm_history("revenue", 4))
    except Exception as error:
        if not row["note"]:
            row["note"] = f"quarterly: {error}"[:160]

    # Full valuation attempt (captures publish state or the first blocker).
    if row["classified"] == "yes":
        try:
            result = build_us_valuation(
                submissions=submissions,
                companyfacts=companyfacts,
                valuation_date=as_of,
            )
            row["valuation_state"] = result["review"]["publication_state"]
            errors = result["review"].get("errors") or []
            if errors and not row["note"]:
                row["note"] = "; ".join(errors)[:160]
        except Exception as error:
            row["valuation_state"] = "engine_error"
            if not row["note"]:
                row["note"] = f"{type(error).__name__}: {error}"[:160]
    else:
        row["valuation_state"] = "unsupported_archetype"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use the built-in sample.")
    parser.add_argument("--cik-file", help="One 'TICKER,CIK' or CIK per line.")
    parser.add_argument("--source", choices=["api", "bulk", "auto"], default="auto")
    parser.add_argument("--bulk-dir", default="archive/local-cache/sec-bulk/extracted")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--out", default="archive/local-audit/us/_harvest")
    args = parser.parse_args()

    universe: list[tuple[str, str]] = []
    if args.sample:
        universe.extend(SAMPLE)
    if args.cik_file:
        for line in Path(args.cik_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                universe.append((parts[0], parts[1]))
            else:
                universe.append(("", parts[0]))
    if not universe:
        raise SystemExit("Provide --sample and/or --cik-file.")

    client = None
    if args.source in {"api", "auto"}:
        agent = os.environ.get("SEC_USER_AGENT")
        if agent:
            client = SecClient(
                user_agent=agent,
                cache_dir=ROOT / "archive" / "local-cache" / "sec-api",
            )
        elif args.source == "api":
            raise SystemExit("SEC_USER_AGENT is required for --source api.")

    bulk_dir = Path(args.bulk_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for ticker, cik in universe:
        row = harvest_one(args.source, bulk_dir, client, ticker, cik, args.as_of)
        rows.append(row)
        print(
            f"{row['ticker']:6} {row['sic']:>4} "
            f"cls={row['classified'] or '-':3} "
            f"period={row['latest_period_end'] or '-':10} "
            f"d+{row['days_since_filed']!s:>4} "
            f"q={row['quarterly_revenue_points']!s:>2} "
            f"state={row['valuation_state']}"
        )

    csv_path = out_dir / "coverage.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "as_of": args.as_of,
        "source": args.source,
        "count": len(rows),
        "classified": sum(1 for r in rows if r["classified"] == "yes"),
        "publishable_review_required": sum(
            1 for r in rows if r["valuation_state"] == "review_required"
        ),
        "withheld": sum(1 for r in rows if r["valuation_state"] == "withheld"),
        "unsupported_archetype": sum(
            1 for r in rows if r["valuation_state"] == "unsupported_archetype"
        ),
        "errors": sum(
            1 for r in rows if r["valuation_state"].endswith("error")
        ),
    }
    (out_dir / "coverage.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8"
    )
    print("\n=== summary ===")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"\nwrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
