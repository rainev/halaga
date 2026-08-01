"""Versioned SEC-SIC to FinSight valuation-archetype routing."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .sec_client import normalize_cik


def load_archetype_config() -> dict[str, Any]:
    path = files(__package__).joinpath("config/archetypes.json")
    return json.loads(path.read_text(encoding="utf-8"))


def classify_issuer(
    submissions: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_archetype_config()
    cik = normalize_cik(submissions.get("cik", ""))
    override = config.get("issuer_overrides", {}).get(cik)
    raw_sic = str(submissions.get("sic") or "").zfill(4)
    match = next(
        (
            row
            for row in config.get("sic_ranges", [])
            if raw_sic.isdigit() and row["start"] <= int(raw_sic) <= row["end"]
        ),
        None,
    )
    if not match and not override:
        raise ValueError(
            f"No supported U.S. valuation archetype for SEC SIC {raw_sic}"
        )

    if override:
        sector = override.get("sector", match["sector"])
        archetype = override.get("archetype", match["archetype"])
        confidence = override.get("confidence", match["confidence"])
        reason = override.get(
            "reason",
            "Mapped from SEC SIC; issuer-level economic review is still required.",
        )
        secondary = list(override.get("secondary_archetypes", []))
        verified_zero_bridge_fields = dict(
            override.get("verified_zero_bridge_fields", {})
        )
        override_applied = True
    else:
        sector = match["sector"]
        archetype = match["archetype"]
        confidence = match["confidence"]
        reason = "Mapped from SEC SIC; issuer-level economic review is still required."
        secondary = []
        verified_zero_bridge_fields = {}
        override_applied = False

    policy = config.get("valuation_policies", {}).get(archetype)
    if not policy:
        raise ValueError(f"No valuation policy configured for archetype {archetype}")

    recent = submissions.get("filings", {}).get("recent", {})
    accessions = [
        accession
        for accession, form in zip(
            recent.get("accessionNumber", []),
            recent.get("form", []),
        )
        if form in {"10-K", "10-K/A", "10-Q", "10-Q/A"}
    ][:8]

    return {
        "cik": cik,
        "ticker": (submissions.get("tickers") or [override.get("ticker") if override else None])[0],
        "issuer_name": submissions.get("name"),
        "filing_regime": "10-K_10-Q",
        "accounting_standard": "US-GAAP",
        "sec_sic_code": raw_sic,
        "sec_sic_label": submissions.get("sicDescription"),
        "finsight_sector": sector,
        "primary_archetype": archetype,
        "secondary_archetypes": secondary,
        "classification_confidence": confidence,
        "mapping_version": config["version"],
        "override_applied": override_applied,
        "override_reason": reason if override_applied else None,
        "classification_reason": reason,
        "source_accessions": accessions,
        "valuation_policy": policy,
        "verified_zero_bridge_fields": verified_zero_bridge_fields,
        "requires_segment_forecast": bool(
            override and override.get("requires_segment_forecast", False)
        ),
    }
