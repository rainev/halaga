#!/usr/bin/env python3
"""Backward-compatible Apple wrapper for the generic U.S. artifact builder."""

from __future__ import annotations

import argparse
from pathlib import Path

from build_us_valuation_pipeline import ROOT, build_issuer_artifacts


CIK = "0000320193"
OUTPUT_ROOT = ROOT / "output" / "us-testing" / "aapl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--valuation-date", default="2026-07-31")
    args = parser.parse_args()
    paths = build_issuer_artifacts(
        CIK,
        "AAPL",
        "Apple",
        "Hardware & electronic equipment",
        Path(OUTPUT_ROOT),
        args.valuation_date,
        args.refresh,
        issuer_metadata={
            "color": "#555555",
            "data_confidence": 0.82,
            "insight": (
                "Apple is routed to a mature hardware-and-services FCFF model. "
                "The value is filing-only and does not use a stock price."
            ),
        },
    )
    print("\n".join(str(path) for path in paths.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
