#!/usr/bin/env python3
"""Merge proposed verified-zero bridge overrides into the archetype config.

Reads the proposals emitted by analyze_us_issuers.py and adds them to
``issuer_overrides`` in archetypes.json. CIKs that already carry a hand-reviewed
override are left untouched (never clobber a human-attested entry); only brand
new issuers are added. Prints what changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHETYPES = ROOT / "backend" / "app" / "us_valuation" / "config" / "archetypes.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proposals",
        default="archive/local-audit/us/_overrides/proposed_overrides.json",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes.")
    args = parser.parse_args()

    proposals = json.loads(Path(args.proposals).read_text(encoding="utf-8"))
    config = json.loads(ARCHETYPES.read_text(encoding="utf-8"))
    existing = config.setdefault("issuer_overrides", {})

    added, skipped = [], []
    for cik, block in proposals.items():
        if cik in existing:
            skipped.append((cik, block.get("ticker", "")))
            continue
        added.append((cik, block.get("ticker", "")))
        if args.apply:
            existing[cik] = {
                "ticker": block["ticker"],
                "reason": (
                    f"{block['ticker']} routes via SEC SIC to a supported archetype; "
                    "issuer-level economic review is still required. Bridge overrides "
                    "record fields absent from the controlling filing."
                ),
                "verified_zero_bridge_fields": block["verified_zero_bridge_fields"],
            }

    print(f"added ({len(added)}):", ", ".join(t for _, t in added))
    print(f"skipped existing ({len(skipped)}):", ", ".join(t for _, t in skipped))
    if args.apply:
        ARCHETYPES.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {ARCHETYPES}")
    else:
        print("\ndry run — pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
