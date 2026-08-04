#!/usr/bin/env python3
"""Build private and public SEC valuation artifacts for one U.S. issuer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.us_valuation import build_us_valuation  # noqa: E402
from app.us_valuation.artifacts import (  # noqa: E402
    frontend_company,
    public_result,
    sec_cache_manifest,
    slim_companyfacts,
    slim_submissions,
    write_javascript_module,
    write_json,
)
from app.us_valuation.sec_client import SecClient, normalize_cik  # noqa: E402


def _source_fixture_candidates(
    ticker: str, valuation_date: str
) -> list[tuple[str, Path, Path]]:
    normalized = ticker.lower()
    local_capture = ROOT / "archive" / "local-audit" / "us" / normalized / "controlled-capture"
    hermetic = ROOT / "backend" / "tests" / "fixtures" / "us"
    return [
        (
            "local_controlled_capture",
            local_capture / "submissions.json",
            local_capture / "companyfacts.json",
        ),
        (
            "reduced_hermetic_fixture",
            hermetic / f"{normalized}-submissions.json",
            hermetic / f"{normalized}-companyfacts.json",
        ),
    ]


def _capture_manifest(
    submissions_path: Path, companyfacts_path: Path, *, status: str
) -> dict:
    return {
        "status": status,
        "records": [
            {
                "fixture": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in (submissions_path, companyfacts_path)
        ],
    }


def build_issuer_artifacts(
    cik: str,
    ticker: str,
    short_name: str,
    subsector: str,
    output_root: Path,
    valuation_date: str,
    refresh: bool,
    *,
    issuer_metadata: dict | None = None,
    capture_private_fixture: bool = False,
) -> dict[str, Path]:
    """Fetch SEC data and write private, public, frontend, and fixture artifacts."""
    normalized_cik = normalize_cik(cik)
    normalized_ticker = ticker.upper()
    artifact_name = short_name.lower().replace(" ", "-")
    cache = output_root / "sec-cache"
    fixture_candidates = _source_fixture_candidates(normalized_ticker, valuation_date)
    available_fixture = next(
        (
            (status, submissions_path, companyfacts_path)
            for status, submissions_path, companyfacts_path in fixture_candidates
            if submissions_path.exists() and companyfacts_path.exists()
        ),
        None,
    )
    if available_fixture is not None and not refresh:
        fixture_status, capture_submissions, capture_companyfacts = available_fixture
        submissions = json.loads(capture_submissions.read_text(encoding="utf-8"))
        companyfacts = json.loads(capture_companyfacts.read_text(encoding="utf-8"))
        source_manifest = _capture_manifest(
            capture_submissions,
            capture_companyfacts,
            status=fixture_status,
        )
    else:
        client = SecClient(user_agent=os.environ.get("SEC_USER_AGENT"), cache_dir=cache)
        submissions = client.submissions(normalized_cik, refresh=refresh)
        companyfacts = client.companyfacts(normalized_cik, refresh=refresh)
        source_manifest = sec_cache_manifest(cache, normalized_cik)
        if capture_private_fixture:
            _, capture_submissions, capture_companyfacts = fixture_candidates[0]
            write_json(capture_submissions, slim_submissions(submissions))
            write_json(capture_companyfacts, slim_companyfacts(companyfacts))
            source_manifest = _capture_manifest(
                capture_submissions,
                capture_companyfacts,
                status="local_controlled_capture",
            )
    result = build_us_valuation(
        submissions=submissions,
        companyfacts=companyfacts,
        valuation_date=valuation_date,
        source_manifest=source_manifest,
    )
    public = public_result(result, submissions)
    frontend = frontend_company(
        result,
        public,
        {
            "ticker": normalized_ticker,
            "short_name": short_name,
            "subsector": subsector,
            "insight": (
                f"{short_name} is valued from SEC filings with a governed, "
                "price-free FCFF and EPV framework."
            ),
            **(issuer_metadata or {}),
        },
    )
    frontend_audit = ROOT / "frontend" / "public" / "data" / f"{artifact_name}-valuation-pipeline.json"
    frontend_module = ROOT / "frontend" / "src" / "research" / "generated" / f"{artifact_name}-valuation.js"
    backend_result = ROOT / "backend" / "app" / "data" / "us_valuations" / f"{normalized_ticker}.json"
    fixture_root = ROOT / "backend" / "tests" / "fixtures" / "us"
    fixture_submissions = fixture_root / f"{normalized_ticker.lower()}-submissions.json"
    fixture_companyfacts = fixture_root / f"{normalized_ticker.lower()}-companyfacts.json"
    paths = {
        "private": output_root / "valuation-result.json",
        "frontend_audit": frontend_audit,
        "backend_public": backend_result,
        "frontend_module": frontend_module,
        "submissions_fixture": fixture_submissions,
        "companyfacts_fixture": fixture_companyfacts,
    }
    write_json(paths["private"], result)
    write_json(paths["frontend_audit"], public)
    write_json(paths["backend_public"], public)
    write_javascript_module(
        paths["frontend_module"], frontend, generator="scripts/build_us_valuation_pipeline.py"
    )
    # Controlled fixtures are owned by the source-capture task. Do not overwrite
    # them during artifact regeneration, but create reproducible fixtures for a
    # new issuer when no controlled capture has been supplied.
    if not fixture_submissions.exists():
        write_json(fixture_submissions, slim_submissions(submissions))
    if not fixture_companyfacts.exists():
        write_json(fixture_companyfacts, slim_companyfacts(companyfacts))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cik", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--short-name", required=True)
    parser.add_argument("--subsector", required=True)
    parser.add_argument("--output-root")
    parser.add_argument("--valuation-date", default="2026-07-31")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--capture-private-fixture", action="store_true")
    args = parser.parse_args()
    output_root = (
        Path(args.output_root)
        if args.output_root
        else ROOT / "archive" / "local-audit" / "us" / args.ticker.lower()
    )
    paths = build_issuer_artifacts(
        args.cik,
        args.ticker,
        args.short_name,
        args.subsector,
        output_root,
        args.valuation_date,
        args.refresh,
        capture_private_fixture=args.capture_private_fixture,
    )
    print("\n".join(str(path) for path in paths.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
