#!/usr/bin/env python3
"""Parse the Archetype-testing filing corpus into a review-first web dataset.

This pipeline is deliberately conservative:

- hashes and deduplicates PDFs before parsing;
- rejects wrong-entity and non-financial documents;
- labels parent-only statements and keeps them out of consolidated coverage;
- preserves annual, standalone-quarter, and YTD columns separately;
- exposes candidate evidence, never an automatically approved valuation input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finsight_parser.catalog import load_line_item_catalog, load_wave1_requirements
from finsight_parser.core import (
    PARSER_VERSION,
    build_fact_index,
    evaluate_requirements,
    extract_pdf,
    file_sha256,
    local_ocr,
    locate_statements,
    merge_fact_indexes,
    read_json,
    resolve_binary,
    run_command,
    validate_index,
    write_json,
)


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "config" / "line_item_catalog.json"
REQUIREMENTS_PATH = ROOT / "config" / "wave1_requirements.json"
IDENTITY_OVERRIDES_PATH = ROOT / "config" / "identity_overrides.json"

FOLDERS = {
    "AREIT": "AREIT",
    "Aboitiz Power Corp": "AP",
    "Ayala Corp": "AC",
    "Ayala Land": "ALI",
    "BDO Unibank": "BDO",
    "Century Pacific Food": "CNPF",
    "D&L Industries": "DNL",
    "FMETF": "FMETF",
    "International Container Terminal Services": "ICT",
    "Manila Electric Company": "MER",
    "OceanaGold": "OGP",
    "PLDT": "TEL",
    "Puregold": "PGOLD",
    "Semirara": "SCC",
}

ENTITY_ALIASES = {
    "AREIT": ("areit",),
    "AP": ("aboitiz power", "aboitizpower"),
    "AC": ("ayala corporation",),
    "ALI": ("ayala land",),
    "BDO": ("bdo unibank",),
    "CNPF": ("century pacific food",),
    "DNL": ("d&l industries", "d and l industries"),
    "FMETF": ("first metro philippine equity exchange traded fund",),
    "ICT": ("international container terminal services", "ictsi"),
    "MER": ("manila electric company", "meralco"),
    "OGP": ("oceanagold philippines", "oceanagold (philippines)"),
    "TEL": ("pldt inc", "philippine long distance telephone"),
    "PGOLD": ("puregold price club",),
    "SCC": ("semirara mining and power",),
}

MODEL_EXPLANATIONS = {
    "residual_income": "Values the bank from common equity plus future profit above its required return.",
    "sotp": "Values each major subsidiary or investment separately, then subtracts parent debt and overhead.",
    "rnav": "Revalues land, developments, and investment properties, then subtracts liabilities.",
    "nav_ddm_affo": "Cross-checks property NAV, recurring cash earnings, and sustainable distributions.",
    "fcff_dcf": "Values operating cash flow after reinvestment using a WACC-based enterprise-value bridge.",
    "regulated_dcf": "Values regulated distribution cash flow using rate-base, tariff, volume, and allowed-return drivers.",
    "asset_segment_dcf_sotp": "Values generation and distribution assets or segments separately, then combines them.",
    "concession_dcf": "Discounts cash flow only over each port concession's remaining contractual life.",
    "finite_life_nav": "Forecasts mine production, commodity prices, costs, royalties, capex, and closure through reserve depletion.",
    "mine_nav_plus_power_dcf": "Adds a finite-life coal-mine NAV to a separate power-business DCF.",
    "nav_per_unit": "Uses the marked value of portfolio holdings less liabilities, divided by units outstanding.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_text(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"([a-z])(\d)", r"\1 \2", value)
    value = re.sub(r"(\d)([a-z])", r"\1 \2", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def classify_document_type(filename: str, head_text: str = "") -> str:
    name = normalized_text(filename)
    if re.search(r"\b17\s*q\b|quarterly report|first quarter|second quarter|third quarter", name):
        return "quarterly"
    if re.search(
        r"\b17\s*a\b|annual report|audited financial statements|"
        r"\bafs\b|statements for the year ended",
        name,
    ):
        return "annual"
    text = normalized_text(head_text[:12000])
    if re.search(r"\b17\s*q\b|quarterly report|first quarter|second quarter|third quarter", text):
        return "quarterly"
    if re.search(
        r"\b17\s*a\b|annual report|audited financial statements|"
        r"\bafs\b|statements for the year ended",
        text,
    ):
        return "annual"
    return "non_financial"


def detect_scope(filename: str, head_text: str) -> str:
    filename_text = normalized_text(filename)
    text = normalized_text(head_text[:16000])
    if (
        "parent company" in filename_text
        or "parent financial statements" in filename_text
        or re.search(r"(?:^|\s)parent(?:\s|$)", filename_text)
    ):
        return "parent_only"
    if (
        "separate financial statements" in text
        or "separate statement of financial position" in text
    ):
        return "parent_only"
    if "consolidated financial statements" in text or "consolidated statements" in text:
        return "consolidated"
    if (
        "consolidated statement" in text
        or re.search(r"\bcompany and subsidiaries\b", text)
    ):
        return "consolidated"
    if (
        "parent company financial statements" in text
        or "parent company statements of financial position" in text
    ):
        return "parent_only"
    return "scope_unverified"


def identity_match_basis(
    symbol: str,
    filename: str,
    head_text: str,
    sha256: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> str | None:
    text = normalized_text(f"{filename} {head_text[:20000]}")
    if any(normalized_text(alias) in text for alias in ENTITY_ALIASES[symbol]):
        return "filename_or_text"
    override = (overrides or {}).get(sha256 or "")
    if override and override.get("expectedSymbol") == symbol:
        return "reviewed_sha256_override"
    return None


def identity_matches(
    symbol: str,
    filename: str,
    head_text: str,
    sha256: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> bool:
    return identity_match_basis(symbol, filename, head_text, sha256, overrides) is not None


def filing_period(filename: str, document_type: str, head_text: str = "") -> str:
    filename_text = normalized_text(filename)
    text = normalized_text(f"{filename} {head_text[:8000]}")
    years = [int(year) for year in re.findall(r"\b20(?:2[3-9]|3\d)\b", text)]
    year = max(years) if years else None
    if document_type == "annual":
        explicit = re.search(
            r"(?:year ended|as of|as at|for the year ended|annual report)"
            r"[^.]{0,80}?\b(20\d{2})\b",
            text,
        )
        direct_17a = re.search(r"\b17\s*a\s+(20\d{2})\b", text)
        if direct_17a:
            year = int(direct_17a.group(1))
        elif explicit:
            year = int(explicit.group(1))
        elif year and re.search(
            r"(?:\d{1,2}\s+)?(?:january|february|march|april|may)"
            r"(?:\s+\d{1,2})?\s+20\d{2}",
            text,
        ):
            year -= 1
        return f"FY{year}" if year else "Annual period unverified"

    quarter = None
    quarter_patterns = (
        (1, r"\bq\s*1\b|first quarter|march 31"),
        (2, r"\bq\s*2\b|second quarter|june 30|first half"),
        (3, r"\bq\s*3\b|third quarter|september 30|nine months|9\s*m"),
    )
    # Filename labels are more authoritative than comparative periods or
    # references to other quarters inside the filing's opening pages.
    for candidate_text in (filename_text, text):
        for number, pattern in quarter_patterns:
            if re.search(pattern, candidate_text):
                quarter = number
                break
        if quarter is not None:
            break
    if quarter is None:
        if re.search(r"\bmay\b", text):
            quarter = 1
        elif re.search(r"\baug(?:ust)?\b", text):
            quarter = 2
        elif re.search(r"\bnov(?:ember)?\b", text):
            quarter = 3
    if quarter and year:
        return f"Q{quarter} {year}"
    return f"Quarterly {year}" if year else "Quarterly period unverified"


def head_text(pdf: Path) -> str:
    return run_command(
        [
            resolve_binary("pdftotext"),
            "-f",
            "1",
            "-l",
            "6",
            "-layout",
            str(pdf),
            "-",
        ]
    )


def safe_key_label(key: str) -> str:
    replacements = {"ebit": "EBIT", "ebitda": "EBITDA", "eps": "EPS", "nav": "NAV", "affo": "AFFO"}
    words = [replacements.get(word, word.capitalize()) for word in key.split("_")]
    return " ".join(words)


def _reported_years(fact: dict[str, Any]) -> set[int]:
    years: set[int] = set()
    for value in fact.get("values", []):
        hint = str(value.get("period_hint") or "")
        match = re.search(r"\b(20\d{2})\b", hint)
        if match:
            years.add(int(match.group(1)))
    return years


def candidate_is_statement_safe(
    fact: dict[str, Any],
    document: dict[str, Any] | None = None,
) -> bool:
    catalog_statement = fact.get("catalog_statement")
    statement_context = fact.get("statement_context")
    if catalog_statement in {
        "income",
        "balance_sheet",
        "cash_flow",
        "equity",
        "per_share",
    }:
        if re.search(
            r"\b(increased|decreased|due to|compared with|as compared|"
            r"was primarily|was mainly)\b",
            str(fact.get("raw_text", "")),
            re.IGNORECASE,
        ):
            return False
        numeric_values = [
            value.get("reported_value")
            for value in fact.get("values", [])
            if isinstance(value.get("reported_value"), (int, float))
        ]
        if numeric_values and all(
            float(value).is_integer() and 1900 <= int(value) <= 2100
            for value in numeric_values
        ):
            return False
    if document:
        filing_year_match = re.search(r"\b(20\d{2})\b", document.get("period", ""))
        reported_years = _reported_years(fact)
        if filing_year_match and reported_years:
            filing_year = int(filing_year_match.group(1))
            allowed_years = (
                {filing_year, filing_year - 1, filing_year - 2}
                if document["document_type"] == "annual"
                else {filing_year, filing_year - 1}
            )
            if not reported_years.issubset(allowed_years):
                return False
        if (
            document["document_type"] == "quarterly"
            and catalog_statement in {"income", "cash_flow", "equity", "per_share"}
        ):
            period_kinds = {
                value.get("period_kind")
                for value in fact.get("values", [])
                if value.get("reported_value") is not None
            }
            dated_interim_cash_flow = (
                catalog_statement in {"cash_flow", "equity"}
                and period_kinds == {"period"}
                and bool(re.fullmatch(r"Q[1-3] 20\d{2}", document.get("period", "")))
            )
            if (
                not dated_interim_cash_flow
                and not period_kinds.issubset({"quarter", "year_to_date"})
            ):
                return False
    if catalog_statement in {"income", "balance_sheet", "cash_flow", "equity"}:
        return (
            statement_context == catalog_statement
            and fact.get("candidate_kind") == "table_row"
            and fact.get("period_alignment") == "exact"
        )
    if catalog_statement == "per_share":
        return (
            statement_context in {"income", "balance_sheet", "equity"}
            and fact.get("candidate_kind") == "table_row"
            and fact.get("period_alignment") == "exact"
        )
    if catalog_statement == "metric":
        return (
            fact.get("candidate_kind") == "table_row"
            and fact.get("period_alignment") == "exact"
            and bool(normalized_text(str(fact.get("raw_label", ""))))
            and normalized_text(str(fact.get("raw_label", "")))
            == normalized_text(str(fact.get("matched_alias", "")))
        )
    return statement_context == "derived" and fact.get("period_alignment") == "exact"


def fact_rank(fact: dict[str, Any], document: dict[str, Any]) -> tuple[Any, ...]:
    values = fact.get("values", [])
    numeric = sum(isinstance(value.get("reported_value"), (int, float)) for value in values)
    return (
        int(candidate_is_statement_safe(fact, document)),
        int(fact.get("period_alignment") == "exact"),
        int(fact.get("candidate_kind") == "table_row"),
        float(fact.get("confidence", 0)),
        numeric,
        document.get("period", ""),
        -int(fact.get("source", {}).get("page", 0)),
    )


def compact_fact(fact: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    values = []
    for value in fact.get("values", []):
        period = value.get("period_hint")
        period_kind = value.get("period_kind")
        if (
            document.get("document_type") == "quarterly"
            and fact.get("catalog_statement") in {"cash_flow", "equity"}
            and period_kind == "period"
        ):
            quarter_match = re.fullmatch(r"Q([1-3]) 20\d{2}", document.get("period", ""))
            year_match = re.search(r"\b(20\d{2})\b", str(period or ""))
            if quarter_match and year_match:
                quarter = int(quarter_match.group(1))
                year = year_match.group(1)
                if quarter == 1:
                    period, period_kind = f"Q1 {year}", "quarter"
                else:
                    period, period_kind = f"{quarter * 3}M {year} YTD", "year_to_date"
        values.append(
            {
                "period": period,
                "kind": period_kind,
                "reportedValue": value.get("reported_value"),
                "normalizedValue": value.get("normalized_value"),
                "raw": value.get("raw"),
            }
        )
    return {
        "document": document["filename"],
        "documentHash": document["sha256"],
        "filingType": document["document_type"],
        "filingPeriod": document["period"],
        "scope": document["scope"],
        "page": fact.get("source", {}).get("page"),
        "line": fact.get("source", {}).get("line"),
        "rawLabel": fact.get("raw_label"),
        "rawText": re.sub(r"\s+", " ", str(fact.get("raw_text", ""))).strip()[:500],
        "noteReference": fact.get("note_reference"),
        "unit": fact.get("unit_context"),
        "periodAlignment": fact.get("period_alignment"),
        "confidence": fact.get("confidence"),
        "candidateKind": fact.get("candidate_kind"),
        "reviewRequired": True,
        "values": values,
    }


def process_document(
    document: dict[str, Any],
    output_root: Path,
    catalog: list[dict[str, Any]],
    company_profile: dict[str, Any],
    ocr_mode: str,
) -> dict[str, Any]:
    pdf = Path(document["path"])
    workdir = output_root / "documents" / document["sha256"][:16]
    manifest_path = workdir / "manifest.json"
    facts_path = workdir / "facts.json"
    priority_keys = [
        *company_profile["required"],
        *company_profile["recommended"],
    ]
    extraction_profile = {
        "routing_status": "resolved",
        "symbol": company_profile["symbol"],
        "subsector": company_profile.get("subsector"),
        "archetype": company_profile["archetype"],
        "primary_model": company_profile["primary_model"],
    }

    def index_document() -> dict[str, Any]:
        return build_fact_index(
            workdir,
            catalog,
            priority_keys=priority_keys,
            extraction_profile=extraction_profile,
        )

    extracted_reuse = False
    facts_reuse = False
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        extracted_reuse = manifest.get("source_sha256") == document["sha256"]
        facts_reuse = (
            extracted_reuse
            and facts_path.is_file()
            and read_json(facts_path).get("parser_version") == PARSER_VERSION
        )
    if not extracted_reuse:
        manifest = extract_pdf(pdf, workdir)
        located = locate_statements(workdir)
        facts = index_document()
    elif not facts_reuse:
        manifest = read_json(manifest_path)
        located = locate_statements(workdir)
        facts = index_document()
    else:
        manifest = read_json(manifest_path)
        located = read_json(workdir / "located.json")
        facts = read_json(facts_path)
    statement_ocr_pages: set[int] = set()
    page_meta = {
        int(item["page"]): item for item in manifest.get("pages", [])
    }
    for hit in located.get("anchor_hits", []):
        page = int(hit["page"])
        page_path = workdir / "pages" / f"page-{page:04d}.txt"
        page_text = page_path.read_text(encoding="utf-8") if page_path.is_file() else ""
        number_count = len(re.findall(r"\d[\d,]*(?:\.\d+)?", page_text))
        if int(page_meta.get(page, {}).get("chars", 0)) < 700 or number_count < 8:
            statement_ocr_pages.add(page)
    if (
        ocr_mode == "auto"
        and (
            statement_ocr_pages
            or (
                manifest.get("low_text_pages")
                and len(facts.get("facts", [])) < 30
            )
        )
    ):
        ocr_pages = set(statement_ocr_pages)
        if len(facts.get("facts", [])) < 30:
            ocr_pages.update(int(page) for page in manifest.get("low_text_pages", []))
        local_ocr(
            pdf,
            workdir,
            sorted(ocr_pages),
            180,
            "tesseract",
            4,
        )
        located = locate_statements(workdir)
        facts = index_document()
    statement_text = "\n".join(
        (workdir / "pages" / f"page-{int(page):04d}.txt").read_text(
            encoding="utf-8", errors="replace"
        )
        for page in located.get("selected_pages", [])
        if (workdir / "pages" / f"page-{int(page):04d}.txt").is_file()
    )
    resolved_scope = detect_scope(document["filename"], statement_text)
    if resolved_scope == "scope_unverified":
        statement_identity = normalized_text(statement_text[:12000])
        if statement_text and any(
            normalized_text(alias) in statement_identity
            for alias in ENTITY_ALIASES[document["symbol"]]
        ):
            resolved_scope = "issuer_reported"
        elif document.get("identity_basis") in {
            "filename_or_text",
            "reviewed_sha256_override",
        } and document.get("scope") != "parent_only":
            # Identity was already verified from the filing cover/opening pages.
            # If neither the opening pages nor statement pages contain explicit
            # parent-only language, retain the issuer filing for review instead
            # of silently dropping annual reports whose statement headings were
            # not located by layout heuristics.
            resolved_scope = "issuer_reported"
        else:
            resolved_scope = document["scope"]
    return {
        **document,
        "scope": resolved_scope,
        "workdir": str(workdir.resolve()),
        "page_count": int(read_json(manifest_path)["page_count"]),
        "fact_count": len(facts.get("facts", [])),
        "low_text_pages": len(read_json(manifest_path).get("low_text_pages", [])),
    }


def build_company_payload(
    symbol: str,
    company: dict[str, Any],
    documents: list[dict[str, Any]],
    output_root: Path,
    requirements: dict[str, Any],
) -> dict[str, Any]:
    valuation_docs = [
        document
        for document in documents
        if document.get("processed")
        and document["scope"] in {"consolidated", "issuer_reported"}
    ]
    parent_docs = [
        document
        for document in documents
        if document.get("processed") and document["scope"] == "parent_only"
    ]
    corpus_dir = output_root / "corpora" / symbol
    requirement_result = None
    validation_result = None
    corpus_facts: list[dict[str, Any]] = []
    if valuation_docs:
        merge_fact_indexes(
            [Path(document["workdir"]) for document in valuation_docs],
            corpus_dir,
        )
        requirement_result = evaluate_requirements(corpus_dir, requirements, symbol)
        validation_result = validate_index(corpus_dir, requirement_result)
        corpus_facts = read_json(corpus_dir / "facts.json").get("facts", [])

    document_by_hash = {document["sha256"]: document for document in valuation_docs}
    required_keys = list(company["required"])
    recommended_keys = list(company["recommended"])
    rows = []
    for role, keys in (("required", required_keys), ("recommended", recommended_keys)):
        for key in keys:
            all_candidates = [
                fact for fact in corpus_facts if fact.get("canonical_key") == key
            ]
            safe_candidates = []
            for fact in all_candidates:
                document_hash = str(fact.get("source", {}).get("document_sha256", ""))
                document = document_by_hash.get(document_hash)
                if document and candidate_is_statement_safe(fact, document):
                    safe_candidates.append(fact)
            best_by_document: dict[str, dict[str, Any]] = {}
            for fact in safe_candidates:
                document_hash = str(fact.get("source", {}).get("document_sha256", ""))
                document = document_by_hash.get(document_hash)
                if not document:
                    continue
                existing = best_by_document.get(document_hash)
                if existing is None or fact_rank(fact, document) > fact_rank(existing, document):
                    best_by_document[document_hash] = fact
            evidence = [
                compact_fact(fact, document_by_hash[document_hash])
                for document_hash, fact in sorted(
                    best_by_document.items(),
                    key=lambda item: fact_rank(item[1], document_by_hash[item[0]]),
                    reverse=True,
                )[:8]
            ]
            status = (
                "candidate_found"
                if evidence
                else ("review_required" if all_candidates else "missing")
            )
            period_labels = sorted(
                {
                    str(value.get("period"))
                    for item in evidence
                    for value in item.get("values", [])
                    if value.get("period")
                }
            )
            rows.append(
                {
                    "key": key,
                    "label": safe_key_label(key),
                    "role": role,
                    "status": status,
                    "periods": period_labels,
                    "candidateCount": len(all_candidates),
                    "safeEvidenceCount": len(evidence),
                    "evidence": evidence,
                }
            )

    required_rows = [row for row in rows if row["role"] == "required"]
    required_found = sum(row["status"] == "candidate_found" for row in required_rows)
    return {
        "symbol": symbol,
        "name": company["name"],
        "archetype": company["archetype"],
        "primaryModel": company["primary_model"],
        "modelExplanation": MODEL_EXPLANATIONS.get(
            company["primary_model"],
            "Company-specific valuation schedule requiring human review.",
        ),
        "status": "blocked_pending_human_review",
        "statusReason": (
            "Candidate line items are displayed with provenance, but no value is "
            "automatically approved or fed into a valuation."
        ),
        "coverage": {
            "requiredCandidates": required_found,
            "requiredTotal": len(required_rows),
            "requiredCandidateRatio": (
                required_found / len(required_rows) if required_rows else 1
            ),
            "annualFilings": sum(
                document.get("processed")
                and document["document_type"] == "annual"
                and document["scope"] in {"consolidated", "issuer_reported"}
                for document in documents
            ),
            "quarterlyFilings": sum(
                document.get("processed")
                and document["document_type"] == "quarterly"
                and document["scope"] in {"consolidated", "issuer_reported"}
                for document in documents
            ),
            "parentOnlyFilings": len(parent_docs),
            "resolvedAnnualPeriods": sorted(
                {
                    str(value.get("period"))
                    for row in rows
                    for evidence in row["evidence"]
                    if evidence["filingType"] == "annual"
                    for value in evidence["values"]
                    if str(value.get("period") or "").startswith("FY")
                }
            ),
            "resolvedQuarterPeriods": sorted(
                {
                    str(value.get("period"))
                    for row in rows
                    for evidence in row["evidence"]
                    if evidence["filingType"] == "quarterly"
                    for value in evidence["values"]
                    if str(value.get("period") or "").startswith("Q")
                }
            ),
            "resolvedYtdPeriods": sorted(
                {
                    str(value.get("period"))
                    for row in rows
                    for evidence in row["evidence"]
                    if evidence["filingType"] == "quarterly"
                    for value in evidence["values"]
                    if "YTD" in str(value.get("period") or "")
                }
            ),
        },
        "requirements": rows,
        "filings": [
            {
                key: document.get(key)
                for key in (
                    "filename",
                    "sha256",
                    "document_type",
                    "period",
                    "scope",
                    "identity_basis",
                    "page_count",
                    "fact_count",
                    "low_text_pages",
                    "processed",
                    "exclusion_reason",
                )
            }
            for document in sorted(
                documents,
                key=lambda item: (
                    item.get("processed", False),
                    item.get("document_type", ""),
                    item.get("period", ""),
                    item["filename"],
                ),
                reverse=True,
            )
        ],
        "pipelineValidation": (
            validation_result.get("summary") if validation_result else {
                "calculation_status": "blocked",
                "publication_status": "blocked",
            }
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frontend-json", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--ocr-mode", choices=["never", "auto"], default="never")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    output_root = args.output.expanduser().resolve()
    frontend_json = args.frontend_json.expanduser().resolve()
    catalog = load_line_item_catalog(CATALOG_PATH)
    requirements = load_wave1_requirements(
        REQUIREMENTS_PATH,
        {item["key"] for item in catalog},
    )
    identity_overrides = (
        read_json(IDENTITY_OVERRIDES_PATH).get("overrides", {})
        if IDENTITY_OVERRIDES_PATH.is_file()
        else {}
    )
    if not source.is_dir():
        raise SystemExit(f"Source folder not found: {source}")

    received: list[dict[str, Any]] = []
    for folder, symbol in FOLDERS.items():
        company_dir = source / folder
        if not company_dir.is_dir():
            continue
        for pdf in sorted(company_dir.glob("*")):
            if pdf.is_file() and pdf.suffix.lower() == ".pdf":
                received.append(
                    {
                        "symbol": symbol,
                        "folder": folder,
                        "path": str(pdf.resolve()),
                        "filename": pdf.name,
                        "sha256": file_sha256(pdf),
                    }
                )
    hash_groups: dict[str, list[dict[str, Any]]] = {}
    for document in received:
        hash_groups.setdefault(document["sha256"], []).append(document)

    canonical: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    for sha256, group in sorted(hash_groups.items()):
        primary = sorted(group, key=lambda item: item["path"])[0]
        canonical.append(primary)
        for duplicate in sorted(group, key=lambda item: item["path"])[1:]:
            duplicate_records.append(
                {
                    **duplicate,
                    "document_type": "duplicate",
                    "period": "Duplicate",
                    "scope": "not_applicable",
                    "processed": False,
                    "exclusion_reason": (
                        f"Exact duplicate of {primary['filename']} "
                        f"({primary['symbol']}, SHA-256 {sha256[:12]})."
                    ),
                }
            )

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for document in canonical:
        try:
            text = head_text(Path(document["path"]))
        except Exception as exc:  # keep inventory even when text extraction fails
            text = ""
            document["head_error"] = str(exc)
        document_type = classify_document_type(document["filename"], text)
        scope = detect_scope(document["filename"], text)
        period = filing_period(document["filename"], document_type, text)
        enriched = {
            **document,
            "document_type": document_type,
            "period": period,
            "scope": scope,
        }
        if document_type == "non_financial":
            excluded.append(
                {
                    **enriched,
                    "processed": False,
                    "exclusion_reason": "Not identified as a 17-A, 17-Q, annual report, or audited financial statement.",
                }
            )
        elif not (
            identity_basis := identity_match_basis(
                document["symbol"],
                document["filename"],
                text,
                document["sha256"],
                identity_overrides,
            )
        ):
            excluded.append(
                {
                    **enriched,
                    "processed": False,
                    "exclusion_reason": "Entity identity did not match the folder's expected listed company.",
                }
            )
        else:
            eligible.append({**enriched, "identity_basis": identity_basis})

    # Prefer explicitly marked updated versions for the same company, filing
    # type, and filing period. The superseded file remains in the audit trail.
    updated_keys = {
        (document["symbol"], document["document_type"], document["period"])
        for document in eligible
        if re.search(r"\bupdated\b", normalized_text(document["filename"]))
    }
    retained: list[dict[str, Any]] = []
    for document in eligible:
        key = (document["symbol"], document["document_type"], document["period"])
        if (
            key in updated_keys
            and not re.search(r"\bupdated\b", normalized_text(document["filename"]))
        ):
            excluded.append(
                {
                    **document,
                    "processed": False,
                    "exclusion_reason": "Superseded by an explicitly marked updated filing for the same period.",
                }
            )
        else:
            retained.append(document)
    eligible = retained

    print(
        f"[inventory] {len(received)} PDFs; {len(canonical)} unique; "
        f"{len(duplicate_records)} duplicate copies; {len(eligible)} eligible.",
        flush=True,
    )
    processed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, min(args.workers, 8))) as executor:
        futures = {
            executor.submit(
                process_document,
                document,
                output_root,
                catalog,
                requirements["companies"][document["symbol"]],
                args.ocr_mode,
            ): document
            for document in eligible
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            document = futures[future]
            try:
                result = future.result()
                if result["fact_count"] == 0:
                    excluded.append(
                        {
                            **result,
                            "processed": False,
                            "exclusion_reason": (
                                "No cataloged financial-statement rows were found; "
                                "the file may be a filing letter rather than the statements."
                            ),
                        }
                    )
                    print(
                        f"[parse {completed}/{len(futures)}] EXCLUDED "
                        f"{result['filename']} - no financial rows",
                        flush=True,
                    )
                    continue
                processed.append({**result, "processed": True})
                print(
                    f"[parse {completed}/{len(futures)}] {result['symbol']} "
                    f"{result['period']} - {result['fact_count']} candidates",
                    flush=True,
                )
            except Exception as exc:
                failures.append(
                    {
                        **document,
                        "processed": False,
                        "exclusion_reason": f"Parser failure: {exc}",
                    }
                )
                print(
                    f"[parse {completed}/{len(futures)}] FAILED "
                    f"{document['filename']}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

    all_documents = processed + excluded + duplicate_records + failures
    company_payloads = []
    for symbol, company in requirements["companies"].items():
        company_documents = [
            document for document in all_documents if document["symbol"] == symbol
        ]
        company_payloads.append(
            build_company_payload(
                symbol,
                company,
                company_documents,
                output_root,
                requirements,
            )
        )

    payload = {
        "schemaVersion": "1.0",
        "generatedAt": utc_now(),
        "parserVersion": PARSER_VERSION,
        "sourceFolder": str(source),
        "reviewPolicy": (
            "Every displayed number is a source candidate requiring human review. "
            "No candidate is automatically used in a published valuation."
        ),
        "totals": {
            "receivedPdfs": len(received),
            "uniqueDocuments": len(canonical),
            "duplicateCopies": len(duplicate_records),
            "processedFinancialStatements": len(processed),
            "excludedDocuments": len(excluded) + len(failures),
            "companiesInUpload": len({item["symbol"] for item in received}),
            "wave1Companies": len(requirements["companies"]),
        },
        "warnings": [
            "Three-year annual and two-year quarterly comparisons are taken from statement columns, not inferred from the number of PDF files.",
            "Standalone quarter and year-to-date columns remain separate.",
            "Parent-only statements are parsed but excluded from consolidated-company requirement coverage.",
            "Only consolidated or clearly issuer-reported statements count toward model-input coverage; unresolved scope remains audit-trail only.",
            "The upload has no Cebu Air (CEB) folder.",
            "Model-ready status remains blocked until a human confirms entity, scope, units, signs, periods, and model-specific assumptions.",
        ],
        "companies": company_payloads,
    }
    write_json(output_root / "archetype-testing-web.json", payload)
    write_json(frontend_json, payload)
    write_json(
        output_root / "inventory.json",
        {
            "createdAt": utc_now(),
            "received": received,
            "documents": all_documents,
        },
    )
    print(f"[output] {frontend_json}", flush=True)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
