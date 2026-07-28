#!/usr/bin/env python3
"""FinSight local-first financial-report parser.

The default pipeline is free to run:

    PDF -> Poppler text -> issuer/subsector routing -> prioritized fact index
        -> valuation requirements -> accounting controls -> human-review report

OpenAI is not required. Local Tesseract OCR can be used for scanned pages. Every
matched fact retains its raw text, page, line, units, period clues, extraction
method, and document hash. Validation can block a result; it never approves
publication without a human reviewer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from finsight_parser.catalog import (
    CatalogError,
    load_line_item_catalog,
    load_wave1_requirements,
)
from finsight_parser.core import (
    PARSER_VERSION,
    ParserError,
    build_fact_index,
    evaluate_requirements,
    extract_pdf,
    file_sha256,
    local_ocr,
    locate_statements,
    merge_fact_indexes,
    read_json,
    resolve_requirements_route,
    search_pages,
    validate_index,
    write_review_report,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = SCRIPT_DIR / "config" / "line_item_catalog.json"
DEFAULT_REQUIREMENTS = SCRIPT_DIR / "config" / "wave1_requirements.json"


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()[:60] or "report"


def parse_page_range(value: str | None) -> list[int] | None:
    if not value:
        return None
    pages: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = (item.strip() for item in part.split("-", 1))
            start, end = int(start_text), int(end_text)
            if start <= 0 or end < start:
                raise argparse.ArgumentTypeError(f"Invalid page range: {part}")
            pages.update(range(start, end + 1))
        else:
            page = int(part)
            if page <= 0:
                raise argparse.ArgumentTypeError(f"Invalid page: {part}")
            pages.add(page)
    return sorted(pages)


def default_workdir(pdf: Path | None) -> Path:
    if pdf is None:
        return Path("out") / "report"
    resolved = pdf.expanduser().resolve()
    digest = file_sha256(resolved)[:12] if resolved.is_file() else "missing"
    return Path("out") / f"{slug(pdf.stem)}-{digest}"


def load_configuration(
    catalog_path: Path,
    requirements_path: Path,
) -> tuple[list[dict], dict]:
    catalog = load_line_item_catalog(catalog_path)
    requirements = load_wave1_requirements(
        requirements_path,
        {item["key"] for item in catalog},
    )
    return catalog, requirements


def print_extract_summary(manifest: dict) -> None:
    print(
        f"[extract] {manifest['page_count']} pages; "
        f"sha256={manifest['source_sha256'][:12]}..."
    )
    if manifest["low_text_pages"]:
        print(
            "[extract] local OCR candidates: "
            + ", ".join(str(page) for page in manifest["low_text_pages"])
        )


def print_locate_summary(located: dict) -> None:
    print(
        f"[locate] {len(located['anchor_hits'])} statement heading(s); "
        f"{len(located['selected_pages'])} selected page(s)."
    )
    for hit in located["anchor_hits"]:
        print(
            f"         p.{hit['page']}: {hit['statement']} "
            f"(score={hit['score']})"
        )


def run_local_analysis(
    workdir: Path,
    catalog: list[dict],
    requirements: dict,
    symbol: str | None,
    pages: list[int] | None = None,
) -> tuple[dict | None, dict]:
    if not (workdir / "located.json").is_file():
        print_locate_summary(locate_statements(workdir))
    route = resolve_requirements_route(workdir, requirements, symbol)
    company = route["company"]
    priority_keys = [*company["required"], *company["recommended"]]
    facts = build_fact_index(
        workdir,
        catalog,
        pages,
        priority_keys=priority_keys,
        extraction_profile={
            "routing_status": route["status"],
            "symbol": route["symbol"],
            "subsector": route["subsector"],
            "archetype": route["archetype"],
            "primary_model": route["primary_model"],
        },
    )
    print(
        f"[index] {len(facts['facts'])} matched facts; "
        f"{len(facts['unmatched_numeric_rows'])} unmatched numeric rows retained."
    )
    print(
        f"[route] {route['status']}: {route['symbol']} / "
        f"{route['subsector'] or 'unclassified'} via {route['method']}."
    )
    requirement_result = evaluate_requirements(
        workdir,
        requirements,
        symbol,
        route=route,
    )
    summary = requirement_result["summary"]
    print(
        f"[requirements] {company['symbol']}: "
        f"{summary['required_found']}/{summary['required_total']} located; "
        f"{summary['required_validated']}/{summary['required_total']} validated; "
        f"{summary['recommended_found']}/{summary['recommended_total']} recommended located."
    )
    validation = validate_index(workdir, requirement_result)
    report_path = write_review_report(workdir, requirement_result, validation)
    print(
        f"[validate] calculation={validation['summary']['calculation_status']}; "
        f"publication={validation['summary']['publication_status']}."
    )
    print(f"[report] {report_path}")
    return requirement_result, validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FinSight local-first, source-traceable financial-report parser."
    )
    parser.add_argument("--version", action="version", version=PARSER_VERSION)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--requirements-config",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_pdf(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("pdf", type=Path)

    def add_workdir(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--workdir", type=Path)

    extract_command = subparsers.add_parser("extract", help="Extract page text and provenance.")
    add_pdf(extract_command)
    add_workdir(extract_command)

    ocr_command = subparsers.add_parser("ocr", help="Run free local Tesseract OCR.")
    add_pdf(ocr_command)
    add_workdir(ocr_command)
    ocr_command.add_argument("--pages", help="Pages such as 4-7,12; defaults to low-text pages.")
    ocr_command.add_argument("--dpi", type=int, default=220)
    ocr_command.add_argument("--workers", type=int, default=4)
    ocr_command.add_argument(
        "--engine",
        choices=["auto", "tesseract"],
        default="auto",
    )

    locate_command = subparsers.add_parser("locate", help="Locate primary financial statements.")
    add_workdir(locate_command)
    locate_command.add_argument("--pad", type=int, default=2)

    index_command = subparsers.add_parser("index", help="Build the source-traceable fact index.")
    add_workdir(index_command)
    index_command.add_argument("--pages", help="Optional page range; default indexes all pages.")

    requirements_command = subparsers.add_parser(
        "requirements",
        help="Identify the issuer/subsector and check its model-input requirements.",
    )
    add_workdir(requirements_command)
    requirements_command.add_argument(
        "--symbol",
        help="Optional PSE symbol override; otherwise identify the issuer from the filing.",
    )

    validate_command = subparsers.add_parser(
        "validate",
        help="Run accounting, provenance, and completeness controls.",
    )
    add_workdir(validate_command)
    validate_command.add_argument("--symbol")

    query_command = subparsers.add_parser(
        "query",
        help="Find any present or future line item in the extracted report.",
    )
    add_workdir(query_command)
    query_command.add_argument("query")
    query_command.add_argument("--regex", action="store_true")
    query_command.add_argument("--case-sensitive", action="store_true")

    merge_command = subparsers.add_parser(
        "merge",
        help="Combine multiple filing workdirs into one source-traceable corpus.",
    )
    merge_command.add_argument("workdirs", nargs="+", type=Path)
    merge_command.add_argument("--output", type=Path, required=True)
    merge_command.add_argument("--symbol")

    analyze_command = subparsers.add_parser(
        "analyze",
        help="Index, check requirements, validate, and create a review report.",
    )
    add_workdir(analyze_command)
    analyze_command.add_argument("--symbol")
    analyze_command.add_argument("--pages")

    all_command = subparsers.add_parser(
        "all",
        help="Run the complete free local pipeline.",
    )
    add_pdf(all_command)
    add_workdir(all_command)
    all_command.add_argument("--symbol")
    all_command.add_argument("--pad", type=int, default=2)
    all_command.add_argument(
        "--ocr-mode",
        choices=["auto", "never", "required"],
        default="auto",
        help="Local OCR behavior; never calls a paid API.",
    )
    all_command.add_argument("--dpi", type=int, default=220)
    all_command.add_argument("--ocr-workers", type=int, default=4)
    all_command.add_argument(
        "--ocr-engine",
        choices=["auto", "tesseract"],
        default="auto",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    pdf: Path | None = getattr(args, "pdf", None)
    workdir: Path | None = getattr(args, "workdir", None)
    workdir = workdir or default_workdir(pdf)
    workdir.mkdir(parents=True, exist_ok=True)
    catalog, requirements = load_configuration(
        args.catalog.resolve(),
        args.requirements_config.resolve(),
    )

    if args.command == "extract":
        print_extract_summary(extract_pdf(args.pdf, workdir))
    elif args.command == "ocr":
        manifest = local_ocr(
            args.pdf,
            workdir,
            parse_page_range(args.pages),
            args.dpi,
            args.engine,
            args.workers,
        )
        print(f"[ocr] remaining low-text pages: {manifest['low_text_pages']}")
    elif args.command == "locate":
        print_locate_summary(locate_statements(workdir, args.pad))
    elif args.command == "index":
        route = resolve_requirements_route(workdir, requirements)
        company = route["company"]
        facts = build_fact_index(
            workdir,
            catalog,
            parse_page_range(args.pages),
            priority_keys=[*company["required"], *company["recommended"]],
            extraction_profile={
                "routing_status": route["status"],
                "symbol": route["symbol"],
                "subsector": route["subsector"],
                "archetype": route["archetype"],
                "primary_model": route["primary_model"],
            },
        )
        print(
            f"[index] {len(facts['facts'])} matched facts; "
            f"{len(facts['unmatched_numeric_rows'])} unmatched numeric rows retained."
        )
    elif args.command == "requirements":
        result = evaluate_requirements(workdir, requirements, args.symbol)
        print(json.dumps(result["summary"], indent=2))
    elif args.command == "validate":
        requirement_result = evaluate_requirements(workdir, requirements, args.symbol)
        validation = validate_index(workdir, requirement_result)
        write_review_report(workdir, requirement_result, validation)
        print(json.dumps(validation["summary"], indent=2))
    elif args.command == "query":
        result = search_pages(
            workdir,
            args.query,
            regex=args.regex,
            ignore_case=not args.case_sensitive,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "merge":
        corpus = merge_fact_indexes(args.workdirs, args.output)
        print(
            f"[merge] {len(corpus['documents'])} documents; "
            f"{len(corpus['facts'])} matched facts."
        )
        requirement_result = evaluate_requirements(
            args.output,
            requirements,
            args.symbol,
        )
        validation = validate_index(args.output, requirement_result)
        write_review_report(args.output, requirement_result, validation)
        print(
            f"[validate] calculation={validation['summary']['calculation_status']}; "
            f"publication={validation['summary']['publication_status']}."
        )
    elif args.command == "analyze":
        run_local_analysis(
            workdir,
            catalog,
            requirements,
            args.symbol,
            parse_page_range(args.pages),
        )
    elif args.command == "all":
        manifest = extract_pdf(args.pdf, workdir)
        print_extract_summary(manifest)
        if manifest["low_text_pages"] and args.ocr_mode != "never":
            try:
                manifest = local_ocr(
                    args.pdf,
                    workdir,
                    manifest["low_text_pages"],
                    args.dpi,
                    args.ocr_engine,
                    args.ocr_workers,
                )
                print(f"[ocr] remaining low-text pages: {manifest['low_text_pages']}")
            except ParserError as exc:
                if args.ocr_mode == "required":
                    raise
                print(f"[ocr] warning: {exc}", file=sys.stderr)
        print_locate_summary(locate_statements(workdir, args.pad))
        run_local_analysis(workdir, catalog, requirements, args.symbol)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ParserError, CatalogError, argparse.ArgumentTypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
