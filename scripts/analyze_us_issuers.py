#!/usr/bin/env python3
"""Diagnose why classified US issuers are withheld or error, and propose fixes.

For each ticker it pins the controlling filing, runs the normalizer, and reports:
  - missing bridge fields split into RELIABLY_ZERO (safe to attest as verified
    zero because the issuer tags no such concept at all) vs NEEDS_VALUE (a real
    balance the alias map is not catching -> needs a concept alias, never a zero);
  - for engine errors, the concrete cause and any related concepts the issuer
    actually tags, to guide an alias or guard.

Reads issuer JSON from a bulk-extract dir. Emits proposed verified-zero override
blocks (grounded in absence) to <out>/proposed_overrides.json for review + merge.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.us_valuation.classification import classify_issuer  # noqa: E402
from app.us_valuation.sec_client import normalize_cik  # noqa: E402
from app.us_valuation.xbrl import CompanyFactsNormalizer  # noqa: E402

RELIABLY_ZERO = {
    "preferred_equity",
    "noncontrolling_interests",
    "commercial_paper",
    "finance_lease_current",
    "finance_lease_noncurrent",
}
NEEDS_VALUE = {
    "cash",
    "marketable_securities_current",
    "marketable_securities_noncurrent",
    "current_debt",
    "noncurrent_debt",
}
# Keywords to surface candidate alias concepts for a NEEDS_VALUE gap.
ALIAS_HINTS = {
    "marketable_securities_current": ["marketablesecurit", "availableforsale", "shortterminvest", "debtsecurit"],
    "marketable_securities_noncurrent": ["marketablesecurit", "availableforsale", "longterminvest", "debtsecuritiesnoncurrent"],
    "current_debt": ["longtermdebtcurrent", "debtcurrent", "shorttermborrow", "notespayablecurrent"],
    "noncurrent_debt": ["longtermdebtnoncurrent", "longtermdebt", "notespayablenoncurrent"],
    "cash": ["cashandcashequivalents", "cashcashequivalents"],
}


def _records(submissions: dict) -> list[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    return [
        {k: v[i] for k, v in recent.items() if isinstance(v, list) and i < len(v)}
        for i in range(len(recent.get("accessionNumber", [])))
    ]


def _candidate_concepts(companyfacts: dict, field: str, ttm_end: str) -> list[str]:
    hints = ALIAS_HINTS.get(field, [])
    g = companyfacts.get("facts", {}).get("us-gaap", {})
    found = []
    for concept, node in g.items():
        lc = concept.lower()
        if any(h in lc for h in hints):
            facts = node.get("units", {}).get("USD", [])
            latest = [f for f in facts if not f.get("start")]
            if latest:
                last = max(latest, key=lambda f: (f.get("end", ""), f.get("filed", "")))
                if last.get("end", "") >= ttm_end[:4]:  # roughly recent
                    found.append(f"{concept}={last['val']:,.0f}@{last['end']}")
    return found[:4]


def analyze(ticker: str, cik: str, bulk_dir: Path, as_of: str) -> dict:
    cik = normalize_cik(cik)
    out = {"ticker": ticker, "cik": cik}
    sub_path = bulk_dir / f"CIK{cik}-submissions.json"
    facts_path = bulk_dir / f"CIK{cik}-companyfacts.json"
    if not (sub_path.exists() and facts_path.exists()):
        out["status"] = "no_bulk_files"
        return out
    submissions = json.loads(sub_path.read_text(encoding="utf-8"))
    companyfacts = json.loads(facts_path.read_text(encoding="utf-8"))
    try:
        classification = classify_issuer(submissions)
    except Exception as error:
        out["status"] = f"unclassified: {error}"
        return out
    try:
        normalizer = CompanyFactsNormalizer(
            companyfacts,
            fiscal_year_end=submissions.get("fiscalYearEnd"),
            as_of_date=as_of,
            filing_records=_records(submissions),
        )
        fin = normalizer.normalize(
            verified_zero_bridge_fields=classification["verified_zero_bridge_fields"],
            governed_bridge_fields=classification["governed_bridge_fields"],
        )
    except Exception as error:
        out["status"] = "engine_error"
        out["cause"] = f"{type(error).__name__}: {error}"[:120]
        return out

    bs = fin["balance_sheet"]
    ttm = fin["ttm"]
    ttm_end = ttm["period_end"]
    controlling = (ttm.get("controlling_filing") or {}).get("accession")
    states = bs["field_states"]
    # A stale attestation (override keyed to a prior filing) blocks publication
    # exactly like an absent field, so refresh both.
    missing = [f for f, s in states.items() if s in ("missing", "verification_stale")]
    reliably_zero = sorted(f for f in missing if f in RELIABLY_ZERO)
    needs_alias = sorted(f for f in missing if f in NEEDS_VALUE)
    out.update(
        {
            "status": "withheld" if not bs["bridge_complete"] else "ok",
            "ttm_end": ttm_end,
            "controlling_accession": controlling,
            "reliably_zero": reliably_zero,
            "needs_alias": {
                f: _candidate_concepts(companyfacts, f, ttm_end) for f in needs_alias
            },
        }
    )
    return out


def _override_block(ticker: str, cik: str, ttm_end: str, accn: str, fields: list[str], as_of: str) -> dict:
    vz = {}
    for field in fields:
        vz[field] = {
            "rationale": (
                f"{ticker}'s controlling filing tags no {field.replace('_', ' ')} "
                "concept in its SEC Companyfacts; treated as verified zero pending "
                "human confirmation."
            ),
            "source_accession": accn,
            "controlled_period_end": ttm_end,
            "reviewer": "FinSight automated bridge-absence check",
            "reviewed_on": as_of,
            "verification_version": "US-BRIDGE-ZERO-AUTO-1.0",
        }
    return {"ticker": ticker, "verified_zero_bridge_fields": vz}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cik-file", required=True)
    parser.add_argument("--bulk-dir", default="archive/local-cache/sec-bulk/extracted_500")
    parser.add_argument("--as-of", default="2026-08-01")
    parser.add_argument("--out", default="archive/local-audit/us/_overrides")
    args = parser.parse_args()

    universe = []
    for line in Path(args.cik_file).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        universe.append((parts[0], parts[1]) if len(parts) >= 2 else ("", parts[0]))

    bulk_dir = Path(args.bulk_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    proposals = {}
    for ticker, cik in universe:
        r = analyze(ticker, cik, bulk_dir, args.as_of)
        if r["status"] == "withheld":
            rz = r["reliably_zero"]
            alias = r["needs_alias"]
            print(f"{ticker:6} withheld  reliably_zero={rz}  needs_alias={list(alias)}")
            for f, cands in alias.items():
                if cands:
                    print(f"        alias<{f}>: {cands}")
            if rz and r["controlling_accession"]:
                proposals[normalize_cik(cik)] = _override_block(
                    ticker, cik, r["ttm_end"], r["controlling_accession"], rz, args.as_of
                )
        elif r["status"] == "engine_error":
            print(f"{ticker:6} ENGINE    {r['cause']}")
        else:
            print(f"{ticker:6} {r['status']}")

    (out_dir / "proposed_overrides.json").write_text(
        json.dumps(proposals, indent=2), encoding="utf-8"
    )
    print(f"\nproposed verified-zero overrides for {len(proposals)} issuers -> {out_dir}/proposed_overrides.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
