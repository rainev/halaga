from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .catalog import select_document_requirements


PARSER_VERSION = "2.4.8"
LOW_TEXT_CHARS = 120
DEFAULT_PAD = 2
SCHEMA_VERSION = "2.0"

STATEMENT_HEADINGS = {
    "balance_sheet": (
        "consolidated statements of financial position",
        "consolidated statement of financial position",
        "statements of financial position",
        "statement of financial position",
        "condensed statements of financial position",
        "condensed statement of financial position",
        "consolidated balance sheets",
        "consolidated balance sheet",
        "balance sheets",
        "balance sheet",
    ),
    "income": (
        "consolidated statements of comprehensive income",
        "consolidated statement of comprehensive income",
        "statements of comprehensive income",
        "statement of comprehensive income",
        "condensed statements of comprehensive income",
        "condensed statement of comprehensive income",
        "consolidated statements of income",
        "consolidated statement of income",
        "statements of income",
        "statement of income",
        "condensed statements of income",
        "condensed statement of income",
        "consolidated income statements",
        "consolidated income statement",
    ),
    "cash_flow": (
        "consolidated statements of cash flows",
        "consolidated statement of cash flows",
        "statements of cash flows",
        "statement of cash flows",
        "condensed statements of cash flows",
        "condensed statement of cash flows",
        "consolidated cash flow statements",
        "consolidated cash flow statement",
        "cash flow statements",
        "cash flow statement",
    ),
    "equity": (
        "consolidated statements of changes in equity",
        "consolidated statement of changes in equity",
        "statements of changes in equity",
        "statement of changes in equity",
        "consolidated statements of changes in stockholders equity",
        "consolidated statement of changes in stockholders equity",
    ),
}

MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|"
    "november|december"
)
MONTH_NUMBER = {
    month.lower(): index
    for index, month in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}
NUMBER_RE = re.compile(
    r"(?<![A-Za-z])(?:(?:₱|[Pp]\s*=?|=?\s*[Pp]|\$|€|£)\s*)?"
    r"(?:\(\s*\d[\d,]*(?:\.\d+)?\s*\)|-?\d[\d,]*(?:\.\d+)?|[-—–])%?"
)
YEAR_RE = re.compile(r"(?<![\d,])(?:19|20)\d{2}(?![\d,])")
DATE_RE = re.compile(
    rf"\b(?:{MONTHS})\s+\d{{1,2}},?\s+(?:19|20)\d{{2}}\b",
    re.IGNORECASE,
)


class ParserError(RuntimeError):
    """A user-actionable parser failure."""


@dataclass
class PageMeta:
    page: int
    chars: int
    needs_ocr: bool
    extraction_method: str = "pdftotext"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False))


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParserError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ParserError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ParserError(f"Expected a JSON object in {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    home = Path.home()
    candidates = [
        home / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/bin" / name,
        home / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
        Path("/usr/bin") / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise ParserError(
        f"`{name}` was not found. Install the required local tool or add it to PATH."
    )


def run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ParserError(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise ParserError(f"Command failed ({command[0]}): {detail}") from exc
    return result.stdout


def _clear_generated_pages(pages_dir: Path) -> None:
    if pages_dir.name != "pages":
        raise ParserError(f"Refusing to clear unexpected directory: {pages_dir}")
    pages_dir.mkdir(parents=True, exist_ok=True)
    for page_file in pages_dir.glob("page-*.txt"):
        if page_file.is_file():
            page_file.unlink()


def _pdf_page_count(pdf: Path) -> int | None:
    try:
        output = run_command([resolve_binary("pdfinfo"), str(pdf)])
    except ParserError:
        return None
    match = re.search(r"^Pages:\s+(\d+)\s*$", output, re.MULTILINE)
    return int(match.group(1)) if match else None


def extract_pdf(pdf: Path, workdir: Path) -> dict[str, Any]:
    pdf = pdf.expanduser().resolve()
    if not pdf.is_file():
        raise ParserError(f"PDF not found: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise ParserError(f"Expected a PDF file: {pdf}")

    pages_dir = workdir / "pages"
    _clear_generated_pages(pages_dir)
    raw = run_command([resolve_binary("pdftotext"), "-layout", str(pdf), "-"])
    pages = raw.split("\f")
    if pages and pages[-1].strip() == "":
        pages.pop()
    reported_page_count = _pdf_page_count(pdf)
    if reported_page_count is not None and len(pages) != reported_page_count:
        raise ParserError(
            f"Page-count mismatch: pdfinfo={reported_page_count}, pdftotext={len(pages)}"
        )

    page_meta: list[PageMeta] = []
    for page_number, text in enumerate(pages, start=1):
        real_chars = len(re.sub(r"\s", "", text))
        atomic_write_text(pages_dir / f"page-{page_number:04d}.txt", text)
        page_meta.append(
            PageMeta(
                page=page_number,
                chars=real_chars,
                needs_ocr=real_chars < LOW_TEXT_CHARS,
            )
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "created_at": utc_now(),
        "source_pdf": str(pdf),
        "source_sha256": file_sha256(pdf),
        "source_bytes": pdf.stat().st_size,
        "page_count": len(pages),
        "low_text_pages": [item.page for item in page_meta if item.needs_ocr],
        "pages": [asdict(item) for item in page_meta],
    }
    write_json(workdir / "manifest.json", manifest)
    return manifest


def _page_text(workdir: Path, page: int) -> str:
    path = workdir / "pages" / f"page-{page:04d}.txt"
    if not path.is_file():
        raise ParserError(f"Missing extracted page: {path}")
    return path.read_text(encoding="utf-8")


def _statement_heading(text: str) -> tuple[str | None, str | None]:
    allowed_prefixes = {"unaudited", "interim", "condensed", "audited"}
    first_lines = text.splitlines()[:18]
    for statement, headings in STATEMENT_HEADINGS.items():
        for heading in headings:
            normalized_heading = re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip()
            for line in first_lines:
                normalized_line = re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    line.lower(),
                ).strip()
                if normalized_line == normalized_heading:
                    return statement, heading
                if normalized_line.endswith(normalized_heading):
                    prefix = normalized_line[: -len(normalized_heading)].strip()
                    if prefix and set(prefix.split()).issubset(allowed_prefixes):
                        return statement, heading
    return None, None


def _statement_page_score(text: str) -> tuple[int, str | None, list[str]]:
    low = text.lower()
    first_lines = "\n".join(low.splitlines()[:18])
    if "table of contents" in first_lines or "page no." in first_lines:
        return -20, None, ["table_of_contents"]

    statement, heading = _statement_heading(text)
    score = 0
    reasons: list[str] = []
    if statement and heading:
        score += 8
        reasons.append(f"heading:{heading}")
    if "consolidated" in first_lines:
        score += 2
        reasons.append("consolidated")
    if "unaudited" in first_lines or "audited" in first_lines:
        score += 1
        reasons.append("audit_scope")
    if re.search(r"(amounts|figures)\s+in\s+(thousands|millions|billions)", first_lines):
        score += 1
        reasons.append("unit_heading")
    discriminators = {
        "balance_sheet": ("total assets", "total liabilities", "total equity"),
        "income": ("revenue", "income before income tax", "net income"),
        "cash_flow": ("operating activities", "investing activities", "financing activities"),
        "equity": ("retained earnings", "non-controlling interests", "total equity"),
    }
    if statement:
        hits = sum(1 for phrase in discriminators[statement] if phrase in low)
        score += hits
        if hits:
            reasons.append(f"financial_rows:{hits}")
    return score, statement, reasons


def locate_statements(workdir: Path, pad: int = DEFAULT_PAD) -> dict[str, Any]:
    manifest = read_json(workdir / "manifest.json")
    page_count = int(manifest["page_count"])
    hits: list[dict[str, Any]] = []
    selected: set[int] = set()
    for page in range(1, page_count + 1):
        text = _page_text(workdir, page)
        score, statement, reasons = _statement_page_score(text)
        if score >= 8 and statement:
            hits.append(
                {
                    "page": page,
                    "statement": statement,
                    "score": score,
                    "reasons": reasons,
                }
            )
            for candidate in range(page, min(page_count, page + pad) + 1):
                selected.add(candidate)

    result = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "anchor_hits": hits,
        "selected_pages": sorted(selected),
        "warnings": [] if hits else ["No high-confidence statement headings were located."],
    }
    write_json(workdir / "located.json", result)
    return result


def _normalize_label(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _match_catalog(
    label: str,
    catalog: list[dict[str, Any]],
    token_index: dict[str, list[dict[str, Any]]] | None = None,
    statement_context: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, float]:
    normalized_label = _normalize_label(label)
    if not normalized_label:
        return None, None, 0.0
    label_tokens = set(normalized_label.split())
    candidate_catalog = catalog
    if token_index is not None:
        indexed_candidates: dict[str, dict[str, Any]] = {}
        for token in label_tokens:
            for item in token_index.get(token, []):
                indexed_candidates[item["key"]] = item
        candidate_catalog = list(indexed_candidates.values())
    best: tuple[dict[str, Any] | None, str | None, float] = (None, None, 0.0)
    best_effective_score = 0.0
    for item in candidate_catalog:
        prepared_aliases = item.get("_prepared_aliases")
        if prepared_aliases is None:
            prepared_aliases = [
                (alias, _normalize_label(alias), set(_normalize_label(alias).split()))
                for alias in item["aliases"]
            ]
            item["_prepared_aliases"] = prepared_aliases
        for alias, normalized_alias, alias_tokens in prepared_aliases:
            if not (alias_tokens & label_tokens):
                continue
            if normalized_label == normalized_alias:
                score = 1.0
            elif len(alias_tokens) > 1 and normalized_alias in normalized_label:
                score = 0.96
            elif len(label_tokens) > 1 and normalized_label in normalized_alias:
                score = 0.9
            elif len(alias_tokens) > 1 and alias_tokens.issubset(label_tokens):
                score = 0.91
            else:
                ratio = SequenceMatcher(None, normalized_label, normalized_alias).ratio()
                score = ratio * 0.9 if ratio >= 0.84 else 0.0
            effective_score = score + (
                0.015 if statement_context == item["statement"] else 0.0
            )
            if effective_score > best_effective_score:
                best = (item, alias, score)
                best_effective_score = effective_score
    return best if best[2] >= 0.75 else (None, None, 0.0)


def _catalog_token_index(
    catalog: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for item in catalog:
        prepared_aliases = item.get("_prepared_aliases")
        if prepared_aliases is None:
            prepared_aliases = [
                (alias, _normalize_label(alias), set(_normalize_label(alias).split()))
                for alias in item["aliases"]
            ]
            item["_prepared_aliases"] = prepared_aliases
        item_tokens = set().union(
            *(alias_tokens for _, _, alias_tokens in prepared_aliases)
        )
        for token in item_tokens:
            index.setdefault(token, []).append(item)
    return index


def _parse_number(raw: str) -> dict[str, Any]:
    token = raw.strip()
    if token in {"-", "—", "–"}:
        return {"raw": raw, "reported_value": None, "kind": "null"}
    currency = None
    for symbol, code in (("₱", "PHP"), ("$", "USD"), ("€", "EUR"), ("£", "GBP")):
        if symbol in token:
            currency = code
            token = token.replace(symbol, "")
    if re.search(r"(^|=)\s*[Pp]\s*=?", token):
        currency = "PHP"
        token = re.sub(r"(^|=)\s*[Pp]\s*=?", "", token)
    token = token.replace("=", "")
    is_percent = token.endswith("%")
    if is_percent:
        token = token[:-1]
    negative = token.strip().startswith("(") and token.strip().endswith(")")
    token = token.replace("(", "").replace(")", "").replace(",", "").strip()
    try:
        number = float(token)
    except ValueError:
        return {"raw": raw, "reported_value": None, "kind": "unparsed"}
    if negative:
        number = -number
    if number.is_integer():
        number = int(number)
    return {
        "raw": raw,
        "reported_value": number,
        "kind": "percent" if is_percent else "number",
        "currency": currency,
    }


def _page_unit_context(text: str) -> dict[str, Any]:
    low = text.lower()
    scale_name = "units"
    multiplier = 1
    explicit_scale = False
    for name, value in (("billions", 1_000_000_000), ("millions", 1_000_000), ("thousands", 1_000)):
        if re.search(rf"(amounts|figures|expressed)\s+in\s+{name}", low):
            scale_name = name
            multiplier = value
            explicit_scale = True
            break
    currency = (
        "PHP"
        if "philippine peso" in low or "₱" in text or re.search(r"\bp\s*=", low)
        else None
    )
    return {
        "currency": currency,
        "scale": scale_name,
        "scale_multiplier": multiplier,
        "explicit_scale": explicit_scale,
    }


def _inline_unit_context(text: str, page_context: dict[str, Any]) -> dict[str, Any]:
    context = dict(page_context)
    low = text.lower()
    for singular, plural, multiplier in (
        ("billion", "billions", 1_000_000_000),
        ("million", "millions", 1_000_000),
        ("thousand", "thousands", 1_000),
    ):
        if re.search(rf"\b{singular}s?\b", low):
            context["scale"] = plural
            context["scale_multiplier"] = multiplier
            context["explicit_scale"] = True
            break
    return context


def _normalize_values(
    values: list[dict[str, Any]],
    unit_context: dict[str, Any],
    catalog_statement: str | None,
) -> None:
    multiplier = int(unit_context.get("scale_multiplier", 1))
    for value in values:
        reported = value.get("reported_value")
        if not isinstance(reported, (int, float)):
            value["normalized_value"] = None
        elif value.get("kind") == "percent":
            value["normalized_value"] = reported / 100
        elif catalog_statement == "per_share":
            value["normalized_value"] = reported
        else:
            value["normalized_value"] = reported * multiplier


def _assign_period_hints(
    values: list[dict[str, Any]],
    period_context: dict[str, Any],
) -> str:
    columns = list(period_context.get("columns", []))
    labels = list(period_context.get("column_labels", []))
    if not values:
        return "none"
    if not labels:
        for value in values:
            value["period_hint"] = None
            value["period_kind"] = period_context.get("kind", "unknown")
        return "unknown"
    assigned = 0
    ordered_columns = sorted(columns, key=lambda item: int(item["position"]))
    for index, value in enumerate(values):
        position = value.get("column_position")
        column = None
        if ordered_columns and len(ordered_columns) == len(values):
            column = ordered_columns[index]
        elif columns and isinstance(position, int):
            column = min(
                columns,
                key=lambda item: abs(int(item["position"]) - position),
            )
        if column is not None:
            value["period_hint"] = column["label"]
            value["period_kind"] = column["kind"]
            assigned += 1
        else:
            value["period_hint"] = labels[index] if index < len(labels) else None
            value["period_kind"] = period_context.get("kind", "unknown")
            assigned += int(index < len(labels))
    if assigned == len(values) and len(labels) == len(values):
        return "exact"
    if assigned == len(values):
        return "partial"
    return "ambiguous"


def _balance_section(line: str, current: str | None) -> str | None:
    normalized = _normalize_label(line)
    headings = {
        "current assets": "current_assets",
        "noncurrent assets": "noncurrent_assets",
        "non current assets": "noncurrent_assets",
        "current liabilities": "current_liabilities",
        "noncurrent liabilities": "noncurrent_liabilities",
        "non current liabilities": "noncurrent_liabilities",
        "equity": "equity",
        "stockholders equity": "equity",
        "shareholders equity": "equity",
    }
    if normalized in headings:
        return headings[normalized]
    return current


def _period_label(
    start_month: str,
    start_day: int,
    end_month: str,
    end_day: int,
    year: str,
) -> tuple[str, str]:
    start = MONTH_NUMBER[start_month.lower()]
    end = MONTH_NUMBER[end_month.lower()]
    if start == 1 and start_day == 1:
        if end == 3:
            return f"Q1 {year}", "quarter"
        if end in {6, 9, 12}:
            return f"{end}M {year} YTD", "year_to_date"
    if (start, end) in {(1, 3), (4, 6), (7, 9), (10, 12)}:
        return f"Q{(end + 2) // 3} {year}", "quarter"
    return (
        f"{start_month.title()} {start_day} to {end_month.title()} {end_day}, {year}",
        "period",
    )


def _page_period_context(text: str, statement: str | None) -> dict[str, Any]:
    lines = text.splitlines()[:25]
    heading = "\n".join(lines)
    low = heading.lower()
    columns: list[dict[str, Any]] = []

    # First preference: full dates printed over the numeric columns.
    ending_group_re = re.compile(
        r"(?:for\s+the\s+)?(three|six|nine)[- ]months?(?:\s+periods?)?"
        r"|(?:for\s+the\s+)?quarter\s+end(?:ed|ing)",
        re.IGNORECASE,
    )
    for line_index, line in enumerate(lines):
        date_matches = list(DATE_RE.finditer(line))
        if len(date_matches) >= 2:
            group_matches: list[re.Match[str]] = []
            for prior_index in range(max(0, line_index - 2), line_index + 1):
                group_matches.extend(ending_group_re.finditer(lines[prior_index]))
            dated_columns = []
            for match in date_matches:
                label = match.group(0).replace("\n", " ")
                column_kind = "instant" if statement == "balance_sheet" else "period"
                if group_matches and statement != "balance_sheet":
                    group = min(
                        group_matches,
                        key=lambda item: abs(item.start() - match.start()),
                    )
                    year_match = YEAR_RE.search(label)
                    month_match = re.match(rf"({MONTHS})", label, re.IGNORECASE)
                    if year_match and month_match:
                        year = year_match.group(0)
                        end_month = MONTH_NUMBER[month_match.group(1).lower()]
                        duration = (group.group(1) or "quarter").lower()
                        if duration == "nine":
                            label, column_kind = f"9M {year} YTD", "year_to_date"
                        elif duration == "six":
                            label, column_kind = f"6M {year} YTD", "year_to_date"
                        else:
                            label, column_kind = (
                                f"Q{max(1, min(4, (end_month + 2) // 3))} {year}",
                                "quarter",
                            )
                dated_columns.append(
                    {
                        "position": match.start(),
                        "label": label,
                        "kind": column_kind,
                    }
                )
            columns = dated_columns
            break

    year_line_index = None
    year_matches: list[re.Match[str]] = []
    year_line_score: tuple[int, int, int] = (0, 0, 0)
    for index, line in enumerate(lines):
        matches = list(YEAR_RE.finditer(line))
        score = (
            len(matches),
            int(bool(re.search(r"\bnotes?\b", line, re.IGNORECASE))),
            matches[-1].start() - matches[0].start() if len(matches) >= 2 else 0,
        )
        if score > year_line_score:
            year_line_index = index
            year_matches = matches
            year_line_score = score

    # Interim income/cash-flow statements often use two header rows:
    # "2025 / 2024", then "July 1 to / January 1 to", then "September 30".
    range_re = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})\s+to\b", re.IGNORECASE)
    month_day_re = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})\b", re.IGNORECASE)
    if year_line_index is not None and year_matches:
        range_matches: list[tuple[re.Match[str], int]] = []
        for index in range(year_line_index + 1, min(len(lines), year_line_index + 5)):
            for match in range_re.finditer(lines[index]):
                range_matches.append((match, index))
        if range_matches:
            interim_columns: list[dict[str, Any]] = []
            ordered_year_matches = sorted(year_matches, key=lambda item: item.start())
            group_size = (
                len(range_matches) // len(ordered_year_matches)
                if ordered_year_matches
                and len(range_matches) % len(ordered_year_matches) == 0
                else 0
            )
            for range_index, (start_match, line_index) in enumerate(range_matches):
                end_match = None
                for next_index in range(line_index + 1, min(len(lines), line_index + 3)):
                    candidates = list(month_day_re.finditer(lines[next_index]))
                    if candidates:
                        end_match = min(
                            candidates,
                            key=lambda item: abs(item.start() - start_match.start()),
                        )
                        break
                if end_match is None:
                    continue
                year_match = (
                    ordered_year_matches[
                        min(len(ordered_year_matches) - 1, range_index // group_size)
                    ]
                    if group_size
                    else min(
                        year_matches,
                        key=lambda item: abs(item.start() - start_match.start()),
                    )
                )
                label, kind = _period_label(
                    start_match.group(1),
                    int(start_match.group(2)),
                    end_match.group(1),
                    int(end_match.group(2)),
                    year_match.group(0),
                )
                interim_columns.append(
                    {
                        "position": start_match.start(),
                        "label": label,
                        "kind": kind,
                    }
                )
            if interim_columns:
                columns = interim_columns

    # A second common interim layout groups current/prior YTD columns first and
    # current/prior standalone-quarter columns second, with the durations on a
    # separate header row. Map each printed year to its nearest duration group.
    if (
        not columns
        and statement != "balance_sheet"
        and year_line_index is not None
        and len(year_matches) >= 2
    ):
        duration_re = re.compile(
            r"(?:for\s+the\s+)?(three|six|nine)[- ]month(?:\s+period)?s?",
            re.IGNORECASE,
        )
        duration_groups: list[re.Match[str]] = []
        for index in range(max(0, year_line_index - 3), year_line_index + 1):
            duration_groups.extend(duration_re.finditer(lines[index]))
        duration_kinds = {match.group(1).lower() for match in duration_groups}
        if len(duration_groups) >= 2 and len(duration_kinds) >= 2:
            date_months = [
                MONTH_NUMBER[match.group(1).lower()]
                for match in re.finditer(rf"\b({MONTHS})\s+\d{{1,2}}\b", heading, re.IGNORECASE)
            ]
            end_month = max(date_months) if date_months else 3
            mixed_columns = []
            ordered_groups = sorted(duration_groups, key=lambda match: match.start())
            group_size = (
                len(year_matches) // len(ordered_groups)
                if len(year_matches) % len(ordered_groups) == 0
                else 0
            )
            for year_index, year_match in enumerate(year_matches):
                duration_match = (
                    ordered_groups[min(len(ordered_groups) - 1, year_index // group_size)]
                    if group_size
                    else min(
                        ordered_groups,
                        key=lambda match: abs(match.start() - year_match.start()),
                    )
                )
                duration = duration_match.group(1).lower()
                year = year_match.group(0)
                if duration == "nine":
                    label, column_kind = f"9M {year} YTD", "year_to_date"
                elif duration == "six":
                    label, column_kind = f"6M {year} YTD", "year_to_date"
                else:
                    quarter = max(1, min(4, (end_month + 2) // 3))
                    label, column_kind = f"Q{quarter} {year}", "quarter"
                mixed_columns.append(
                    {
                        "position": year_match.start(),
                        "label": label,
                        "kind": column_kind,
                    }
                )
            columns = mixed_columns

    # Annual statements usually print a "Notes / 2025 / 2024 / 2023" row.
    if not columns and len(year_matches) >= 2:
        first_date = DATE_RE.search(heading)
        end_month = None
        if first_date:
            month_match = re.match(rf"({MONTHS})", first_date.group(0), re.IGNORECASE)
            if month_match:
                end_month = MONTH_NUMBER[month_match.group(1).lower()]
        if statement == "balance_sheet":
            label_for = lambda year: year
            column_kind = "instant"
        elif re.search(r"\bnine[- ]months?\b|\b9m\b", low):
            label_for = lambda year: f"9M {year} YTD"
            column_kind = "year_to_date"
        elif re.search(r"\bsix[- ]months?\b|\b6m\b|first half", low):
            label_for = lambda year: f"6M {year} YTD"
            column_kind = "year_to_date"
        elif re.search(r"\bthree[- ]months?\b|\bquarter\b", low):
            quarter = max(1, min(4, ((end_month or 3) + 2) // 3))
            label_for = lambda year: f"Q{quarter} {year}"
            column_kind = "quarter"
        elif re.search(r"year ended|for each of the .*years|annual", low):
            label_for = lambda year: f"FY{year}"
            column_kind = "annual"
        else:
            label_for = lambda year: year
            column_kind = "unknown"
        columns = [
            {
                "position": match.start(),
                "label": label_for(match.group(0)),
                "kind": column_kind,
            }
            for match in year_matches
        ]

    kinds = {column["kind"] for column in columns}
    if statement == "balance_sheet":
        kind = "instant"
    elif len(kinds) == 1:
        kind = next(iter(kinds))
    elif columns:
        kind = "mixed"
    elif "three months" in low or "quarter" in low:
        kind = "quarter"
    elif "six months" in low or "nine months" in low or "year to date" in low:
        kind = "year_to_date"
    elif "year ended" in low or "for the year" in low:
        kind = "annual"
    else:
        kind = "unknown"
    dates = [match.group(0) for match in DATE_RE.finditer(heading)]
    years = list(dict.fromkeys(YEAR_RE.findall(heading)))
    note_column = None
    for line in lines:
        match = re.search(r"\bnotes?\b", line, re.IGNORECASE)
        if match and year_matches:
            note_column = match.start()
            break
    return {
        "kind": kind,
        "dates": dates,
        "years": years,
        "columns": columns,
        "column_labels": [column["label"] for column in columns],
        "note_column_position": note_column,
    }


def _numeric_row_parts(line: str) -> tuple[str, list[re.Match[str]]]:
    matches = list(NUMBER_RE.finditer(line))
    if not matches:
        return line.strip(), []
    return line[: matches[0].start()].strip(" .:\t"), matches


def _is_probable_note_reference(
    values: list[dict[str, Any]],
    label: str = "",
) -> bool:
    if len(values) < 2:
        return False
    first = values[0]
    second = values[1]
    first_value = first.get("reported_value")
    second_value = second.get("reported_value")
    return (
        first.get("kind") == "number"
        and isinstance(first_value, int)
        and 0 < first_value <= 999
        and isinstance(second_value, (int, float))
        and abs(second_value) >= 100
        and (len(values) >= 3 or "note" in label.lower())
    )


def _parse_row_values(matches: list[re.Match[str]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for match in matches:
        value = _parse_number(match.group(0))
        value["column_position"] = match.start()
        values.append(value)
    return values


def _remove_note_column_values(
    values: list[dict[str, Any]],
    period_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    note_position = period_context.get("note_column_position")
    columns = list(period_context.get("columns", []))
    if not isinstance(note_position, int) or not columns:
        return values, None
    column_positions = [int(column["position"]) for column in columns]
    note_values = [
        value
        for value in values
        if isinstance(value.get("column_position"), int)
        and abs(int(value["column_position"]) - note_position) <= 5
        and abs(int(value["column_position"]) - note_position)
        < min(
            abs(int(value["column_position"]) - position)
            for position in column_positions
        )
    ]
    retained = [value for value in values if value not in note_values]
    reference = ", ".join(str(value.get("raw", "")).strip() for value in note_values)
    return retained, reference or None


def build_fact_index(
    workdir: Path,
    catalog: list[dict[str, Any]],
    pages: Iterable[int] | None = None,
    priority_keys: Iterable[str] | None = None,
    extraction_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = read_json(workdir / "manifest.json")
    located_path = workdir / "located.json"
    located = read_json(located_path) if located_path.is_file() else {"selected_pages": []}
    located_pages = set(int(page) for page in located.get("selected_pages", []))
    if pages is None:
        selected_pages = range(1, int(manifest["page_count"]) + 1)
    else:
        selected_pages = sorted(set(int(page) for page in pages))

    page_methods = {
        int(item["page"]): str(item.get("extraction_method", "pdftotext"))
        for item in manifest.get("pages", [])
    }
    priority = list(dict.fromkeys(priority_keys or []))
    priority_set = set(priority)
    if priority:
        catalog = sorted(
            catalog,
            key=lambda item: (
                0 if item["key"] in priority_set else 1,
                priority.index(item["key"]) if item["key"] in priority_set else 0,
            ),
        )
    catalog_by_key = {item["key"]: item for item in catalog}
    catalog_token_index = _catalog_token_index(catalog)
    anchor_hits = list(located.get("anchor_hits", []))
    anchor_by_page = {
        int(item["page"]): str(item["statement"])
        for item in anchor_hits
    }
    anchor_units = {
        page: _page_unit_context(_page_text(workdir, page))
        for page in anchor_by_page
    }
    facts: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []
    row_id = 0

    for page in selected_pages:
        text = _page_text(workdir, page)
        statement, _ = _statement_heading(text)
        unit_context = _page_unit_context(text)
        if statement is None and page in located_pages:
            prior_anchors = [
                anchor_page
                for anchor_page in anchor_by_page
                if anchor_page <= page
            ]
            if prior_anchors:
                nearest = max(prior_anchors)
                if page - nearest <= DEFAULT_PAD:
                    statement = anchor_by_page[nearest]
                    if not unit_context["explicit_scale"]:
                        unit_context = dict(anchor_units[nearest])
        period_context = _page_period_context(text, statement)
        lines = text.splitlines()
        pending_label: tuple[int, str, dict[str, Any] | None, str | None, float] | None = None
        section_context: str | None = None
        last_numeric_target: dict[str, Any] | None = None
        last_numeric_line = 0

        for line_number, original_line in enumerate(lines, start=1):
            line = original_line.rstrip()
            if not line.strip():
                continue
            if statement == "balance_sheet":
                section_context = _balance_section(line, section_context)
            label, matches = _numeric_row_parts(line)
            catalog_item, alias, match_score = _match_catalog(
                label,
                catalog,
                catalog_token_index,
                statement,
            )
            if matches and catalog_item is None:
                full_item, full_alias, full_score = _match_catalog(
                    line,
                    catalog,
                    catalog_token_index,
                    statement,
                )
                if full_item and full_alias:
                    alias_pattern = r"\W+".join(
                        re.escape(token)
                        for token in _normalize_label(full_alias).split()
                    )
                    alias_match = re.search(alias_pattern, line, re.IGNORECASE)
                    if alias_match:
                        trailing_matches = [
                            match for match in matches if match.start() >= alias_match.end()
                        ]
                        if trailing_matches:
                            catalog_item, alias, match_score = (
                                full_item,
                                full_alias,
                                full_score,
                            )
                            matches = trailing_matches
                            label = line[: trailing_matches[0].start()].strip(" .:\t")

            if not matches:
                pending_item, pending_alias, pending_score = _match_catalog(
                    line,
                    catalog,
                    catalog_token_index,
                    statement,
                )
                pending_label = (
                    line_number,
                    line,
                    pending_item,
                    pending_alias,
                    pending_score,
                ) if pending_item else None
                continue

            if not label and pending_label:
                pending_line, label, catalog_item, alias, match_score = pending_label
                line_number_for_source = pending_line
                raw_text = f"{label} {line}"
            else:
                line_number_for_source = line_number
                raw_text = original_line
            pending_label = None

            if not re.search(r"[A-Za-z]", label):
                if last_numeric_target and line_number - last_numeric_line <= 3:
                    continued = _parse_row_values(matches)
                    _normalize_values(
                        continued,
                        last_numeric_target["unit_context"],
                        last_numeric_target.get("catalog_statement"),
                    )
                    last_numeric_target["values"].extend(continued)
                    last_numeric_target["period_alignment"] = _assign_period_hints(
                        last_numeric_target["values"],
                        last_numeric_target["period_context"],
                    )
                    last_numeric_target["raw_text"] += f"\n{original_line}"
                    last_numeric_line = line_number
                continue
            parsed_values = _parse_row_values(matches)
            candidate_kind = "table_row"
            note_reference = None
            parsed_values, note_reference = _remove_note_column_values(
                parsed_values,
                period_context,
            )
            if not note_reference and _is_probable_note_reference(parsed_values, label):
                note_reference = str(parsed_values.pop(0).get("raw", "")).strip()
            if statement is None and len(parsed_values) > 1:
                currency_values = [
                    value for value in parsed_values if value.get("currency")
                ]
                percentage_values = [
                    value
                    for value in parsed_values
                    if "%" in str(value.get("raw", ""))
                ]
                if (
                    catalog_item
                    and catalog_item["statement"] == "ratio"
                    and percentage_values
                ):
                    parsed_values = percentage_values
                    candidate_kind = "narrative_percentage"
                elif (
                    (
                        catalog_item is None
                        or catalog_item["statement"] in {"income", "cash_flow"}
                    )
                    and currency_values
                ):
                    parsed_values = currency_values
                    candidate_kind = "narrative_currency"
            if not parsed_values:
                continue
            if (
                catalog_item
                and catalog_item["key"] == "noncurrent_debt"
                and section_context == "current_liabilities"
            ):
                catalog_item = catalog_by_key["current_debt"]
                alias = "current portion of long-term debt"
                match_score = max(match_score, 0.95)
            row_unit_context = _inline_unit_context(raw_text, unit_context)
            _normalize_values(
                parsed_values,
                row_unit_context,
                catalog_item["statement"] if catalog_item else None,
            )
            period_alignment = _assign_period_hints(parsed_values, period_context)

            row_id += 1
            row = {
                "row_id": f"p{page:04d}-l{line_number_for_source:04d}-r{row_id:05d}",
                "raw_label": label,
                "raw_text": raw_text,
                "statement_context": statement or "note_or_other",
                "values": parsed_values,
                "note_reference": note_reference,
                "unit_context": row_unit_context,
                "period_context": period_context,
                "period_alignment": period_alignment,
                "section_context": section_context,
                "candidate_kind": candidate_kind,
                "source": {
                    "page": page,
                    "line": line_number_for_source,
                    "method": page_methods.get(page, "pdftotext"),
                    "document_sha256": manifest["source_sha256"],
                },
            }
            if catalog_item:
                confidence = match_score
                if statement == catalog_item["statement"]:
                    confidence = min(1.0, confidence + 0.03)
                if page in located_pages:
                    confidence = min(1.0, confidence + 0.02)
                if page_methods.get(page) != "pdftotext":
                    confidence *= 0.85
                row.update(
                    {
                        "canonical_key": catalog_item["key"],
                        "catalog_statement": catalog_item["statement"],
                        "tags": catalog_item["tags"],
                        "matched_alias": alias,
                        "match_score": round(match_score, 4),
                        "confidence": round(confidence, 4),
                    }
                )
                facts.append(row)
                last_numeric_target = row
                last_numeric_line = line_number
            else:
                unmatched_rows.append(row)
                last_numeric_target = None

        _append_prose_window_facts(
            facts=facts,
            text=text,
            page=page,
            statement=statement,
            page_unit_context=unit_context,
            period_context=period_context,
            extraction_method=page_methods.get(page, "pdftotext"),
            document_sha256=manifest["source_sha256"],
            catalog=catalog,
        )

    _append_derived_facts(facts, manifest)
    result = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "created_at": utc_now(),
        "document": {
            "path": manifest["source_pdf"],
            "sha256": manifest["source_sha256"],
            "page_count": manifest["page_count"],
        },
        "catalog_items": len(catalog),
        "extraction_profile": {
            "mode": "subsector_prioritized" if priority else "full_catalog",
            "priority_keys": priority,
            "priority_key_count": len(priority),
            "full_catalog_retained": True,
            **(extraction_profile or {}),
        },
        "facts": facts,
        "unmatched_numeric_rows": unmatched_rows,
    }
    write_json(workdir / "facts.json", result)
    _write_facts_csv(workdir / "facts.csv", facts)
    return result


def _append_prose_window_facts(
    *,
    facts: list[dict[str, Any]],
    text: str,
    page: int,
    statement: str | None,
    page_unit_context: dict[str, Any],
    period_context: dict[str, Any],
    extraction_method: str,
    document_sha256: str,
    catalog: list[dict[str, Any]],
) -> None:
    existing: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = {}
    for fact in facts:
        identity = (
            fact.get("canonical_key"),
            fact.get("source", {}).get("page"),
            fact.get("matched_alias"),
        )
        existing.setdefault(identity, []).append(fact)
    for item in catalog:
        prepared_patterns = item.get("_prepared_prose_patterns")
        if prepared_patterns is None:
            prepared_patterns = []
            for prepared_alias in item["aliases"]:
                alias_pattern = r"\W+".join(
                    re.escape(token)
                    for token in _normalize_label(prepared_alias).split()
                )
                prepared_patterns.append(
                    (
                        prepared_alias,
                        re.compile(
                            rf"(?<!\w){alias_pattern}(?!\w)",
                            re.IGNORECASE,
                        ),
                    )
                )
            item["_prepared_prose_patterns"] = prepared_patterns
        for alias, alias_regex in prepared_patterns:
            identity = (item["key"], page, alias)
            prior_facts = existing.get(identity, [])
            if prior_facts:
                if item["statement"] == "ratio":
                    prior_is_usable = any(
                        "%" in str(value.get("raw", ""))
                        for fact in prior_facts
                        for value in fact.get("values", [])
                    )
                elif item["statement"] in {"income", "cash_flow"}:
                    prior_is_usable = any(
                        value.get("currency")
                        for fact in prior_facts
                        for value in fact.get("values", [])
                    )
                else:
                    prior_is_usable = True
                if prior_is_usable:
                    continue
            for alias_match in alias_regex.finditer(text):
                tail = text[alias_match.end() : alias_match.end() + 240]
                tail = tail.split("\n\n", 1)[0]
                tail = "\n".join(tail.splitlines()[:4])
                numeric_matches = list(NUMBER_RE.finditer(tail))
                if not numeric_matches:
                    continue
                # Narrative labels can be followed by incidental percentages
                # before a monetary result ("NII rose 9% to P203.1bn"), or by
                # another metric name containing a number ("Common Equity Tier
                # 1 ... CAR stood at 15.2%"). Prefer the explicit token whose
                # unit matches the catalog item's statement type.
                currency_numeric_index = next(
                    (
                        index
                        for index, match in enumerate(numeric_matches)
                        if re.search(
                            r"[₱$€£]|\b[Pp](?=\s*\d)",
                            match.group(0),
                        )
                    ),
                    None,
                )
                percentage_numeric_index = next(
                    (
                        index
                        for index, match in enumerate(numeric_matches)
                        if "%" in match.group(0)
                    ),
                    None,
                )
                if item["statement"] == "ratio":
                    explicit_numeric_index = percentage_numeric_index
                else:
                    explicit_numeric_index = (
                        currency_numeric_index
                        if currency_numeric_index is not None
                        else percentage_numeric_index
                    )
                if explicit_numeric_index is not None:
                    numeric_matches = numeric_matches[explicit_numeric_index:]
                first_numeric = numeric_matches[0]
                bridge = tail[: first_numeric.start()]
                evidence = f"{bridge}{first_numeric.group(0)}"
                explicit_value = bool(
                    re.search(r"[₱$€£]|\b[Pp](?=\s*\d)|%", evidence)
                )
                amount_phrase = bool(
                    re.search(
                        r"\b(amounted|totaled|reached|stood)\b",
                        bridge,
                        re.IGNORECASE,
                    )
                )
                operating_unit = bool(
                    re.search(
                        r"\b("
                        r"mw|gwh|mwh|teu|tons?|tonnes?|ounces?|oz|boe|barrels?|"
                        r"years?|months?|aircraft|passengers?|subscribers?|customers?|"
                        r"shares?|units?|users?|students?|rooms?|keys?|stores?|sites?|"
                        r"hectares?|sqm|square\s+meters?|square\s+metres?"
                        r")\b",
                        tail,
                        re.IGNORECASE,
                    )
                )
                direct_table_value = (
                    first_numeric.start() <= 20
                    and item["statement"]
                    in {"income", "balance_sheet", "cash_flow", "per_share"}
                )
                if not (
                    explicit_value
                    or amount_phrase
                    or operating_unit
                    or direct_table_value
                ):
                    continue
                values = [_parse_number(match.group(0)) for match in numeric_matches]
                if not any(
                    isinstance(value.get("reported_value"), (int, float))
                    for value in values
                ):
                    continue
                raw_start = max(0, alias_match.start() - 80)
                raw_end = min(len(text), alias_match.end() + 200)
                raw_text = re.sub(r"\s+", " ", text[raw_start:raw_end]).strip()
                unit_context = _inline_unit_context(raw_text, page_unit_context)
                _normalize_values(values, unit_context, item["statement"])
                period_alignment = _assign_period_hints(values, period_context)
                line_number = text[: alias_match.start()].count("\n") + 1
                if direct_table_value:
                    confidence = 0.92
                elif explicit_value:
                    confidence = 0.9
                elif operating_unit:
                    confidence = 0.86
                else:
                    confidence = 0.83
                if len(values) > 4:
                    confidence -= 0.08
                if extraction_method != "pdftotext":
                    confidence *= 0.85
                facts.append(
                    {
                        "row_id": f"p{page:04d}-l{line_number:04d}-prose-{item['key']}",
                        "canonical_key": item["key"],
                        "catalog_statement": item["statement"],
                        "raw_label": alias,
                        "raw_text": raw_text,
                        "statement_context": statement or "note_or_other",
                        "section_context": None,
                        "values": values,
                        "note_reference": None,
                        "unit_context": unit_context,
                        "period_context": period_context,
                        "period_alignment": period_alignment,
                        "tags": item["tags"],
                        "matched_alias": alias,
                        "match_score": round(confidence, 4),
                        "confidence": round(confidence, 4),
                        "candidate_kind": "prose_window",
                        "source": {
                            "page": page,
                            "line": line_number,
                            "method": extraction_method,
                            "document_sha256": document_sha256,
                        },
                    }
                )
                existing.setdefault(identity, []).append(facts[-1])
                break


def _append_derived_facts(
    facts: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    def compatible_periods(*components: dict[str, Any]) -> bool:
        signatures = []
        for component in components:
            signatures.append(
                [
                    (value.get("period_hint"), value.get("period_kind"))
                    for value in component.get("values", [])
                ]
            )
        populated = [signature for signature in signatures if any(hint for hint, _ in signature)]
        return not populated or all(signature == populated[0] for signature in populated)

    def append_derived(
        *,
        key: str,
        values: list[dict[str, Any]],
        components: list[dict[str, Any]],
        raw_text: str,
        unit_context: dict[str, Any],
        tags: list[str] | None = None,
    ) -> None:
        confidence = max(
            0.0,
            min(float(component.get("confidence", 0)) for component in components) - 0.05,
        )
        facts.append(
            {
                "row_id": f"derived-{key}",
                "canonical_key": key,
                "catalog_statement": "derived",
                "raw_label": key.replace("_", " ").title(),
                "raw_text": raw_text,
                "statement_context": "derived",
                "section_context": None,
                "values": values,
                "note_reference": None,
                "unit_context": unit_context,
                "period_context": dict(components[0]["period_context"]),
                "period_alignment": components[0].get("period_alignment", "unknown"),
                "tags": tags or ["derived"],
                "matched_alias": None,
                "match_score": 1.0,
                "confidence": round(confidence, 4),
                "source": {
                    "page": components[0]["source"]["page"],
                    "line": components[0]["source"]["line"],
                    "method": "derived",
                    "document_sha256": manifest["source_sha256"],
                    "component_rows": [component["row_id"] for component in components],
                },
            }
        )

    def create_binary(
        key: str,
        left_key: str,
        right_key: str,
        operation: str,
    ) -> None:
        if any(fact.get("canonical_key") == key for fact in facts):
            return
        left = best_fact(facts, left_key)
        right = best_fact(facts, right_key)
        if not left or not right:
            return
        if not compatible_periods(left, right):
            return
        left_values = left.get("values", [])
        right_values = right.get("values", [])
        if not left_values or len(left_values) != len(right_values):
            return
        if (
            operation != "divide"
            and left["unit_context"]["scale_multiplier"]
            != right["unit_context"]["scale_multiplier"]
        ):
            return
        values: list[dict[str, Any]] = []
        for left_value, right_value in zip(left_values, right_values):
            a = left_value.get("reported_value")
            b = right_value.get("reported_value")
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                values.append(
                    {
                        "raw": None,
                        "reported_value": None,
                        "normalized_value": None,
                        "kind": "null",
                        "period_hint": left_value.get("period_hint"),
                        "period_kind": left_value.get("period_kind"),
                    }
                )
                continue
            if operation == "add":
                reported = a + b
            elif operation == "subtract":
                reported = a - b
            elif operation == "subtract_abs":
                reported = a - abs(b)
            elif operation == "divide":
                left_normalized = left_value.get("normalized_value")
                right_normalized = right_value.get("normalized_value")
                if (
                    not isinstance(left_normalized, (int, float))
                    or not isinstance(right_normalized, (int, float))
                    or right_normalized == 0
                ):
                    reported = None
                else:
                    reported = left_normalized / right_normalized
            else:
                raise ParserError(f"Unsupported derived operation: {operation}")
            multiplier = (
                1 if operation == "divide" else left["unit_context"]["scale_multiplier"]
            )
            values.append(
                {
                    "raw": None,
                    "reported_value": reported,
                    "normalized_value": (
                        reported * multiplier
                        if isinstance(reported, (int, float))
                        else None
                    ),
                    "kind": "ratio" if operation == "divide" else "number",
                    "period_hint": left_value.get("period_hint"),
                    "period_kind": left_value.get("period_kind"),
                }
            )
        result_context = dict(left["unit_context"])
        if operation == "divide":
            result_context.update(
                {
                    "currency": None,
                    "scale": "ratio",
                    "scale_multiplier": 1,
                    "explicit_scale": True,
                }
            )
        append_derived(
            key=key,
            values=values,
            components=[left, right],
            raw_text=f"Derived as {left_key} {operation} {right_key}.",
            unit_context=result_context,
        )

    def create_linear_combination(
        key: str,
        terms: list[tuple[str, int]],
        *,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> None:
        if any(fact.get("canonical_key") == key for fact in facts):
            return
        components = [best_fact(facts, component_key) for component_key, _ in terms]
        if any(component is None for component in components):
            return
        typed_components = [component for component in components if component is not None]
        if not compatible_periods(*typed_components):
            return
        scales = {
            component["unit_context"]["scale_multiplier"]
            for component in typed_components
        }
        lengths = {len(component.get("values", [])) for component in typed_components}
        if len(scales) != 1 or len(lengths) != 1 or not lengths or 0 in lengths:
            return
        values: list[dict[str, Any]] = []
        multiplier = typed_components[0]["unit_context"]["scale_multiplier"]
        for index in range(next(iter(lengths))):
            amounts = []
            for component, (_, coefficient) in zip(typed_components, terms):
                amount = component["values"][index].get("reported_value")
                if not isinstance(amount, (int, float)):
                    amounts = []
                    break
                amounts.append(coefficient * amount)
            reported = sum(amounts) if amounts else None
            anchor = typed_components[0]["values"][index]
            values.append(
                {
                    "raw": None,
                    "reported_value": reported,
                    "normalized_value": (
                        reported * multiplier
                        if isinstance(reported, (int, float))
                        else None
                    ),
                    "kind": "number" if reported is not None else "null",
                    "period_hint": anchor.get("period_hint"),
                    "period_kind": anchor.get("period_kind"),
                }
            )
        expression = " ".join(
            f"{'+' if coefficient > 0 else '-'} {component_key}"
            for component_key, coefficient in terms
        ).lstrip("+ ")
        append_derived(
            key=key,
            values=values,
            components=typed_components,
            raw_text=description or f"Derived as {expression}.",
            unit_context=dict(typed_components[0]["unit_context"]),
            tags=tags,
        )

    _derive_total_debt(facts, manifest)
    create_binary("net_debt", "total_debt", "cash", "subtract")
    create_binary("working_capital", "current_assets", "current_liabilities", "subtract")
    create_binary("free_cash_flow", "operating_cash_flow", "capital_expenditure", "subtract_abs")
    create_binary("net_borrowing", "debt_proceeds", "debt_repayments", "subtract_abs")
    create_binary("effective_tax_rate", "tax_expense", "pretax_income", "divide")
    create_binary("gross_margin", "gross_profit", "revenue", "divide")
    create_binary("ebit_margin", "ebit", "revenue", "divide")
    create_binary("ebitda_margin", "ebitda", "revenue", "divide")
    create_linear_combination(
        "core_operating_working_capital",
        [("receivables", 1), ("inventory", 1), ("accounts_payable", -1)],
        tags=["derived", "derived_proxy", "dcf", "working_capital"],
        description=(
            "Core operating working-capital proxy derived as receivables plus "
            "inventory less accounts payable. It excludes other operating "
            "current assets and liabilities unless separately modeled downstream."
        ),
    )
    if not any(
        fact.get("canonical_key") in {"tangible_book_value", "tangible_common_equity"}
        for fact in facts
    ):
        create_binary(
            "tangible_common_equity",
            "parent_equity",
            "intangible_assets",
            "subtract_abs",
        )


def _derive_total_debt(
    facts: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    if any(fact.get("canonical_key") == "total_debt" for fact in facts):
        return
    balance_debt = [
        fact
        for fact in facts
        if fact.get("canonical_key") in {"current_debt", "noncurrent_debt"}
        and fact.get("statement_context") == "balance_sheet"
    ]
    pages = sorted({fact["source"]["page"] for fact in balance_debt})
    chosen_page = None
    for page in pages:
        keys = {
            fact["canonical_key"]
            for fact in balance_debt
            if fact["source"]["page"] == page
        }
        if keys == {"current_debt", "noncurrent_debt"}:
            chosen_page = page
            break
    if chosen_page is None:
        return
    components = [
        fact for fact in balance_debt if fact["source"]["page"] == chosen_page
    ]
    scales = {fact["unit_context"]["scale_multiplier"] for fact in components}
    if len(scales) != 1:
        return
    value_count = max(len(fact.get("values", [])) for fact in components)
    values: list[dict[str, Any]] = []
    multiplier = components[0]["unit_context"]["scale_multiplier"]
    for index in range(value_count):
        amounts = []
        for fact in components:
            if index >= len(fact.get("values", [])):
                continue
            amount = fact["values"][index].get("reported_value")
            if isinstance(amount, (int, float)):
                amounts.append(amount)
        if not amounts:
            values.append(
                {
                    "raw": None,
                    "reported_value": None,
                    "normalized_value": None,
                    "kind": "null",
                    "period_hint": None,
                    "period_kind": components[0]["period_context"].get("kind"),
                }
            )
            continue
        reported = sum(amounts)
        values.append(
            {
                "raw": None,
                "reported_value": reported,
                "normalized_value": reported * multiplier,
                "kind": "number",
                "period_hint": (
                    components[0]["values"][index].get("period_hint")
                    if index < len(components[0].get("values", []))
                    else None
                ),
                "period_kind": components[0]["period_context"].get("kind"),
            }
        )
    confidence = max(
        0.0,
        min(float(fact.get("confidence", 0)) for fact in components) - 0.05,
    )
    facts.append(
        {
            "row_id": "derived-total_debt",
            "canonical_key": "total_debt",
            "catalog_statement": "derived",
            "raw_label": "Total Debt",
            "raw_text": "Derived by summing current and noncurrent debt rows on the balance sheet.",
            "statement_context": "derived",
            "section_context": None,
            "values": values,
            "note_reference": None,
            "unit_context": dict(components[0]["unit_context"]),
            "period_context": dict(components[0]["period_context"]),
            "period_alignment": components[0].get("period_alignment", "unknown"),
            "tags": ["derived", "equity_bridge"],
            "matched_alias": None,
            "match_score": 1.0,
            "confidence": round(confidence, 4),
            "source": {
                "page": chosen_page,
                "line": min(fact["source"]["line"] for fact in components),
                "method": "derived",
                "document_sha256": manifest["source_sha256"],
                "component_rows": [fact["row_id"] for fact in components],
            },
        }
    )


def _write_facts_csv(path: Path, facts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    fields = [
        "canonical_key",
        "raw_label",
        "reported_values",
        "normalized_values",
        "page",
        "line",
        "statement_context",
        "currency",
        "scale",
        "period_kind",
        "period_alignment",
        "confidence",
        "raw_text",
    ]
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for fact in facts:
            writer.writerow(
                {
                    "canonical_key": fact["canonical_key"],
                    "raw_label": fact["raw_label"],
                    "reported_values": json.dumps(
                        [value.get("reported_value") for value in fact["values"]]
                    ),
                    "normalized_values": json.dumps(
                        [value.get("normalized_value") for value in fact["values"]]
                    ),
                    "page": fact["source"]["page"],
                    "line": fact["source"]["line"],
                    "statement_context": fact["statement_context"],
                    "currency": fact["unit_context"].get("currency"),
                    "scale": fact["unit_context"].get("scale"),
                    "period_kind": fact["period_context"].get("kind"),
                    "period_alignment": fact.get("period_alignment"),
                    "confidence": fact["confidence"],
                    "raw_text": fact["raw_text"],
                }
            )
    temporary.replace(path)


def merge_fact_indexes(
    input_workdirs: Iterable[Path],
    output_workdir: Path,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    for input_workdir in input_workdirs:
        source_dir = input_workdir.expanduser().resolve()
        index = read_json(source_dir / "facts.json")
        if index.get("document_type") == "corpus":
            raise ParserError("Nested corpus merges are not supported; pass document workdirs.")
        document = dict(index.get("document", {}))
        document_hash = str(document.get("sha256", ""))
        if not document_hash:
            raise ParserError(f"Missing document hash in {source_dir / 'facts.json'}")
        if document_hash in seen_hashes:
            continue
        seen_hashes.add(document_hash)
        document["source_workdir"] = str(source_dir)
        documents.append(document)
        prefix = document_hash[:12]
        for raw_fact in index.get("facts", []):
            fact = json.loads(json.dumps(raw_fact))
            old_row_id = str(fact.get("row_id", "row"))
            fact["row_id"] = f"{prefix}:{old_row_id}"
            fact["source"]["source_workdir"] = str(source_dir)
            components = fact["source"].get("component_rows")
            if isinstance(components, list):
                fact["source"]["component_rows"] = [
                    f"{prefix}:{component}" for component in components
                ]
            facts.append(fact)
        for raw_row in index.get("unmatched_numeric_rows", []):
            row = json.loads(json.dumps(raw_row))
            row["row_id"] = f"{prefix}:{row.get('row_id', 'row')}"
            row["source"]["source_workdir"] = str(source_dir)
            unmatched_rows.append(row)

    if not documents:
        raise ParserError("No document fact indexes were provided for the corpus.")
    result = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "document_type": "corpus",
        "created_at": utc_now(),
        "documents": documents,
        "facts": facts,
        "unmatched_numeric_rows": unmatched_rows,
    }
    output_workdir.mkdir(parents=True, exist_ok=True)
    write_json(output_workdir / "facts.json", result)
    _write_facts_csv(output_workdir / "facts.csv", facts)
    write_json(
        output_workdir / "manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
            "document_type": "corpus",
            "created_at": utc_now(),
            "document_count": len(documents),
            "page_count": sum(int(document.get("page_count", 0)) for document in documents),
            "documents": documents,
        },
    )
    return result


def _fact_rank(fact: dict[str, Any]) -> tuple[int, float, int, int]:
    statement_match = int(fact["statement_context"] == fact["catalog_statement"])
    parsed_values = sum(
        value.get("reported_value") is not None for value in fact.get("values", [])
    )
    return (
        statement_match,
        float(fact.get("confidence", 0)),
        parsed_values,
        -int(fact["source"]["page"]),
    )


def best_fact(facts: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    candidates = [fact for fact in facts if fact.get("canonical_key") == key]
    return max(candidates, key=_fact_rank) if candidates else None


def resolve_requirements_route(
    workdir: Path,
    requirements: dict[str, Any],
    symbol: str | None = None,
) -> dict[str, Any]:
    """Identify the issuer, resolve its subsector, and persist the audit trail."""
    manifest = read_json(workdir / "manifest.json")
    filename_parts: list[str] = []
    document_text_parts: list[str] = []
    if manifest.get("document_type") == "corpus":
        for document in manifest.get("documents", []):
            filename_parts.append(str(document.get("path", "")))
    else:
        filename_parts.append(str(manifest.get("source_pdf", "")))
        page_count = min(int(manifest.get("page_count", 0)), 6)
        for page in range(1, page_count + 1):
            page_path = workdir / "pages" / f"page-{page:04d}.txt"
            if page_path.is_file():
                document_text_parts.append(page_path.read_text(encoding="utf-8"))
    route = select_document_requirements(
        requirements,
        symbol=symbol,
        filename=" ".join(filename_parts),
        document_text="\n".join(document_text_parts),
    )
    company = route["company"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "status": route["status"],
        "method": route["method"],
        "confidence": route["confidence"],
        "review_required": route["review_required"],
        "matched_alias": route.get("matched_alias"),
        "candidate_symbols": route.get("candidate_symbols", []),
        "symbol": company["symbol"],
        "company_name": company["name"],
        "subsector": company.get("subsector"),
        "archetype": company["archetype"],
        "primary_model": company["primary_model"],
        "supporting_models": company.get("supporting_models", []),
        "templates": company["templates"],
        "required_keys": company["required"],
        "recommended_keys": company["recommended"],
        "policy": (
            "Explicit company overrides take precedence over subsector defaults. "
            "Unresolved or ambiguous issuers use only the conservative common-equity "
            "fallback and require human classification review."
        ),
        "company": company,
    }
    write_json(workdir / "routing.json", result)
    return result


def evaluate_requirements(
    workdir: Path,
    requirements: dict[str, Any],
    symbol: str | None = None,
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts_index = read_json(workdir / "facts.json")
    facts = list(facts_index.get("facts", []))
    route = route or resolve_requirements_route(workdir, requirements, symbol)
    company = route["company"]

    def candidate_status(best: dict[str, Any] | None) -> str:
        if best is None:
            return "missing"
        if not any(
            isinstance(value.get("reported_value"), (int, float))
            for value in best.get("values", [])
        ):
            return "review_required"
        if float(best.get("confidence", 0)) < 0.8:
            return "review_required"
        catalog_statement = best.get("catalog_statement")
        statement_context = best.get("statement_context")
        if statement_context == "derived":
            return "validated"
        if catalog_statement in {"income", "balance_sheet", "cash_flow", "equity"}:
            return (
                "validated"
                if (
                    statement_context == catalog_statement
                    and best.get("candidate_kind") == "table_row"
                    and best.get("period_alignment") == "exact"
                )
                else "review_required"
            )
        if catalog_statement == "per_share":
            return (
                "validated"
                if (
                    statement_context in {"income", "equity", "balance_sheet"}
                    and best.get("candidate_kind") == "table_row"
                    and best.get("period_alignment") == "exact"
                    and float(best.get("confidence", 0)) >= 0.9
                )
                else "review_required"
            )
        if catalog_statement == "metric":
            return (
                "validated"
                if float(best.get("confidence", 0)) >= 0.85
                else "review_required"
            )
        return "review_required"

    def evaluate(keys: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in keys:
            candidates = [fact for fact in facts if fact.get("canonical_key") == key]
            candidate_rows = [
                (fact, candidate_status(fact)) for fact in candidates
            ]
            validated_candidates = [
                fact for fact, status in candidate_rows if status == "validated"
            ]
            if validated_candidates:
                status = "validated"
                best = max(validated_candidates, key=_fact_rank)
            elif candidates:
                status = "review_required"
                best = max(candidates, key=_fact_rank)
            else:
                status = "missing"
                best = None
            rows.append(
                {
                    "key": key,
                    "status": status,
                    "located": best is not None,
                    "candidate_count": len(candidates),
                    "validated_candidate_count": len(validated_candidates),
                    "best_candidate": {
                        "page": best["source"]["page"],
                        "line": best["source"]["line"],
                        "raw_label": best["raw_label"],
                        "values": best["values"],
                        "unit_context": best["unit_context"],
                        "period_context": best["period_context"],
                        "period_alignment": best.get("period_alignment", "unknown"),
                        "confidence": best["confidence"],
                        "document_sha256": best["source"]["document_sha256"],
                    } if best else None,
                    "candidate_periods": [
                        {
                            "document_sha256": fact["source"]["document_sha256"],
                            "page": fact["source"]["page"],
                            "period_context": fact.get("period_context", {}),
                            "period_alignment": fact.get("period_alignment", "unknown"),
                            "confidence": fact.get("confidence"),
                            "status": candidate_status(fact),
                        }
                        for fact in sorted(candidates, key=_fact_rank, reverse=True)[:20]
                    ],
                }
            )
        return rows

    required = evaluate(company["required"])
    recommended = evaluate(company["recommended"])
    required_found = sum(row["located"] for row in required)
    required_validated = sum(row["status"] == "validated" for row in required)
    recommended_found = sum(row["located"] for row in recommended)
    recommended_validated = sum(
        row["status"] == "validated" for row in recommended
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "company": company,
        "routing": {
            key: route.get(key)
            for key in (
                "status",
                "method",
                "confidence",
                "review_required",
                "matched_alias",
                "candidate_symbols",
                "subsector",
            )
        },
        "selection_policy": (
            "Coverage check only. Multiple periods are retained; valuation-period "
            "selection must be explicit and must not infer 'latest' from page order."
        ),
        "required": required,
        "recommended": recommended,
        "summary": {
            "required_found": required_found,
            "required_validated": required_validated,
            "required_total": len(required),
            "required_completeness": (
                required_validated / len(required) if required else 1.0
            ),
            "recommended_found": recommended_found,
            "recommended_validated": recommended_validated,
            "recommended_total": len(recommended),
            "missing_required": [
                row["key"] for row in required if row["status"] == "missing"
            ],
            "review_required": [
                row["key"]
                for row in required
                if row["status"] == "review_required"
            ],
        },
    }
    write_json(workdir / "requirements.json", result)
    return result


def _first_numeric(fact: dict[str, Any] | None) -> float | None:
    if not fact:
        return None
    for value in fact.get("values", []):
        reported = value.get("reported_value")
        if isinstance(reported, (int, float)) and math.isfinite(reported):
            return float(reported)
    return None


def validate_index(
    workdir: Path,
    requirement_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = read_json(workdir / "manifest.json")
    facts_index = read_json(workdir / "facts.json")
    facts = list(facts_index.get("facts", []))
    checks: list[dict[str, Any]] = []

    if facts_index.get("document_type") == "corpus":
        documents = list(facts_index.get("documents", []))
        hashes = [str(document.get("sha256", "")) for document in documents]
        checks.extend(
            [
                {
                    "id": "corpus_documents",
                    "status": "pass" if documents else "fail",
                    "message": f"Corpus contains {len(documents)} unique document(s).",
                },
                {
                    "id": "corpus_unique_hashes",
                    "status": "pass"
                    if len(hashes) == len(set(hashes)) and all(hashes)
                    else "fail",
                    "message": "Every corpus document must have a unique SHA-256 hash.",
                },
                {
                    "id": "fact_provenance",
                    "status": "pass"
                    if all(
                        fact.get("source", {}).get("page")
                        and fact.get("source", {}).get("line")
                        and fact.get("source", {}).get("document_sha256")
                        and fact.get("source", {}).get("source_workdir")
                        and fact.get("raw_text")
                        for fact in facts
                    )
                    else "fail",
                    "message": "Every corpus fact retains document, page, line, workdir, and raw text.",
                },
                {
                    "id": "fact_index_nonempty",
                    "status": "pass" if facts else "fail",
                    "message": f"Corpus contains {len(facts)} matched fact candidates.",
                },
            ]
        )
        if requirement_result:
            routing = requirement_result.get("routing", {})
            checks.append(
                {
                    "id": "issuer_subsector_routing",
                    "status": (
                        "fail" if routing.get("review_required", True) else "pass"
                    ),
                    "message": (
                        f"Resolved {requirement_result['company']['symbol']} to "
                        f"{routing.get('subsector')} via {routing.get('method')}."
                        if not routing.get("review_required", True)
                        else "Issuer/subsector classification is unresolved or ambiguous."
                    ),
                }
            )
            completeness = float(
                requirement_result.get("summary", {}).get("required_completeness", 0)
            )
            missing = requirement_result.get("summary", {}).get("missing_required", [])
            review_required = requirement_result.get("summary", {}).get(
                "review_required", []
            )
            checks.append(
                {
                    "id": "wave1_required_inputs",
                    "status": "pass" if completeness == 1.0 else "fail",
                    "message": (
                        "All required Wave 1 inputs were located across the corpus."
                        if completeness == 1.0
                        else (
                            f"Missing: {', '.join(missing) or 'none'}; "
                            f"needs review: {', '.join(review_required) or 'none'}."
                        )
                    ),
                }
            )
        failures = [check for check in checks if check["status"] == "fail"]
        result = {
            "schema_version": SCHEMA_VERSION,
            "created_at": utc_now(),
            "checks": checks,
            "summary": {
                "passed": sum(check["status"] == "pass" for check in checks),
                "failed": len(failures),
                "warnings": sum(check["status"] == "warning" for check in checks),
                "calculation_status": "validated" if not failures else "blocked",
                "publication_status": "human_review_required" if not failures else "blocked",
                "human_review_required": True,
            },
        }
        write_json(workdir / "validation.json", result)
        return result

    page_files = list((workdir / "pages").glob("page-*.txt"))
    expected = int(manifest["page_count"])
    checks.append(
        {
            "id": "page_file_count",
            "status": "pass" if len(page_files) == expected else "fail",
            "message": f"Expected {expected} extracted pages; found {len(page_files)}.",
        }
    )
    checks.append(
        {
            "id": "fact_provenance",
            "status": "pass" if all(
                fact.get("source", {}).get("page")
                and fact.get("source", {}).get("line")
                and fact.get("source", {}).get("document_sha256")
                and fact.get("raw_text")
                for fact in facts
            ) else "fail",
            "message": "Every matched fact must retain page, line, document hash, and raw text.",
        }
    )
    checks.append(
        {
            "id": "fact_index_nonempty",
            "status": "pass" if facts else "fail",
            "message": f"Matched {len(facts)} catalog fact candidates.",
        }
    )

    assets_fact = best_fact(facts, "total_assets")
    liabilities_fact = best_fact(facts, "total_liabilities")
    equity_fact = best_fact(facts, "total_equity")
    assets = _first_numeric(assets_fact)
    liabilities = _first_numeric(liabilities_fact)
    equity = _first_numeric(equity_fact)
    if all(value is not None for value in (assets, liabilities, equity)):
        scales = {
            assets_fact["unit_context"]["scale_multiplier"],
            liabilities_fact["unit_context"]["scale_multiplier"],
            equity_fact["unit_context"]["scale_multiplier"],
        }
        if len(scales) == 1:
            difference = assets - liabilities - equity
            tolerance = max(abs(assets) * 0.001, 1.0)
            checks.append(
                {
                    "id": "balance_sheet_equation",
                    "status": "pass" if abs(difference) <= tolerance else "fail",
                    "message": (
                        f"Assets minus liabilities and equity = {difference:,.2f} "
                        f"(tolerance {tolerance:,.2f})."
                    ),
                    "source_pages": [
                        assets_fact["source"]["page"],
                        liabilities_fact["source"]["page"],
                        equity_fact["source"]["page"],
                    ],
                }
            )
        else:
            checks.append(
                {
                    "id": "balance_sheet_equation",
                    "status": "warning",
                    "message": "Balance-sheet facts use inconsistent scale contexts.",
                }
            )
    else:
        checks.append(
            {
                "id": "balance_sheet_equation",
                "status": "warning",
                "message": "Could not identify all of total assets, total liabilities, and total equity.",
            }
        )

    duplicate_keys = {}
    for fact in facts:
        duplicate_keys.setdefault(fact["canonical_key"], 0)
        duplicate_keys[fact["canonical_key"]] += 1
    ambiguous = sorted(key for key, count in duplicate_keys.items() if count >= 8)
    checks.append(
        {
            "id": "candidate_ambiguity",
            "status": "warning" if ambiguous else "pass",
            "message": (
                f"High candidate ambiguity for: {', '.join(ambiguous)}."
                if ambiguous
                else "No excessive duplicate candidates."
            ),
        }
    )

    if requirement_result:
        routing = requirement_result.get("routing", {})
        checks.append(
            {
                "id": "issuer_subsector_routing",
                "status": "fail" if routing.get("review_required", True) else "pass",
                "message": (
                    f"Resolved {requirement_result['company']['symbol']} to "
                    f"{routing.get('subsector')} via {routing.get('method')}."
                    if not routing.get("review_required", True)
                    else "Issuer/subsector classification is unresolved or ambiguous."
                ),
            }
        )
        completeness = float(
            requirement_result.get("summary", {}).get("required_completeness", 0)
        )
        missing = requirement_result.get("summary", {}).get("missing_required", [])
        review_required = requirement_result.get("summary", {}).get(
            "review_required", []
        )
        checks.append(
            {
                "id": "wave1_required_inputs",
                "status": "pass" if completeness == 1.0 else "fail",
                "message": (
                    "All required Wave 1 inputs were located."
                    if completeness == 1.0
                    else (
                        f"Missing: {', '.join(missing) or 'none'}; "
                        f"needs review: {', '.join(review_required) or 'none'}."
                    )
                ),
            }
        )

    failures = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warning"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "checks": checks,
        "summary": {
            "passed": sum(check["status"] == "pass" for check in checks),
            "failed": len(failures),
            "warnings": len(warnings),
            "calculation_status": "validated" if not failures else "blocked",
            "publication_status": "human_review_required" if not failures else "blocked",
            "human_review_required": True,
        },
    }
    write_json(workdir / "validation.json", result)
    return result


def search_pages(
    workdir: Path,
    query: str,
    *,
    regex: bool = False,
    ignore_case: bool = True,
) -> dict[str, Any]:
    manifest = read_json(workdir / "manifest.json")
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(query, flags | re.MULTILINE) if regex else None
    normalized_query = _normalize_label(query) if ignore_case else query
    hits: list[dict[str, Any]] = []
    for page in range(1, int(manifest["page_count"]) + 1):
        text = _page_text(workdir, page)
        if pattern:
            for match in pattern.finditer(text):
                line_number = text[: match.start()].count("\n") + 1
                snippet = re.sub(r"\s+", " ", text[match.start() : match.end()]).strip()
                hits.append(
                    {
                        "page": page,
                        "line": line_number,
                        "line_end": text[: match.end()].count("\n") + 1,
                        "text": snippet,
                    }
                )
            continue
        lines = text.splitlines()
        normalized_lines = [
            _normalize_label(line) if ignore_case else re.sub(r"\s+", " ", line).strip()
            for line in lines
        ]
        offsets: list[tuple[int, int, int]] = []
        chunks: list[str] = []
        cursor = 0
        for line_number, normalized_line in enumerate(normalized_lines, start=1):
            if chunks:
                cursor += 1
            start = cursor
            chunks.append(normalized_line)
            cursor += len(normalized_line)
            offsets.append((start, cursor, line_number))
        searchable_page = " ".join(chunks)
        search_from = 0
        while normalized_query:
            position = searchable_page.find(normalized_query, search_from)
            if position < 0:
                break
            end_position = position + len(normalized_query)
            start_line = next(
                line_number
                for start, end, line_number in offsets
                if start <= position <= end
            )
            end_line = next(
                line_number
                for start, end, line_number in offsets
                if start <= max(position, end_position - 1) <= end
            )
            hits.append(
                {
                    "page": page,
                    "line": start_line,
                    "line_end": end_line,
                    "text": re.sub(
                        r"\s+",
                        " ",
                        "\n".join(lines[start_line - 1 : end_line]),
                    ).strip(),
                }
            )
            search_from = end_position
    result = {
        "query": query,
        "regex": regex,
        "ignore_case": ignore_case,
        "hits": hits,
        "hit_count": len(hits),
    }
    query_slug = re.sub(r"[^a-zA-Z0-9]+", "-", query).strip("-").lower()[:60] or "query"
    write_json(workdir / "queries" / f"{query_slug}.json", result)
    return result


def write_review_report(
    workdir: Path,
    requirement_result: dict[str, Any] | None,
    validation_result: dict[str, Any],
) -> Path:
    manifest = read_json(workdir / "manifest.json")
    facts = read_json(workdir / "facts.json")
    if manifest.get("document_type") == "corpus":
        source_lines = [
            f"- Corpus documents: {manifest['document_count']}",
            f"- Combined pages: {manifest['page_count']}",
        ]
    else:
        source_lines = [
            f"- Source: `{manifest['source_pdf']}`",
            f"- Document SHA-256: `{manifest['source_sha256']}`",
            f"- Pages: {manifest['page_count']}",
        ]
    lines = [
        "# FinSight Financial Report Parsing Review",
        "",
        *source_lines,
        f"- Matched fact candidates: {len(facts.get('facts', []))}",
        f"- Unmatched numeric rows retained: {len(facts.get('unmatched_numeric_rows', []))}",
        f"- Calculation status: **{validation_result['summary']['calculation_status']}**",
        f"- Publication status: **{validation_result['summary']['publication_status']}**",
        "",
        "## Accounting and pipeline checks",
        "",
    ]
    for check in validation_result["checks"]:
        marker = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}[check["status"]]
        lines.append(f"- **{marker} — {check['id']}:** {check['message']}")
    if requirement_result:
        company = requirement_result["company"]
        summary = requirement_result["summary"]
        routing = requirement_result.get("routing", {})
        lines.extend(
            [
                "",
                f"## Valuation requirements: {company['symbol']} — {company['name']}",
                "",
                f"- Routing status: `{routing.get('status', 'unknown')}`",
                f"- Routing method: `{routing.get('method', 'unknown')}`",
                f"- PSE subsector: `{company.get('subsector') or 'unclassified'}`",
                f"- Archetype: `{company['archetype']}`",
                f"- Primary model: `{company['primary_model']}`",
                (
                    "- Supporting models: "
                    + ", ".join(
                        f"`{model}`" for model in company.get("supporting_models", [])
                    )
                ),
                f"- Required inputs located: {summary['required_found']} / {summary['required_total']}",
                f"- Required inputs validated: {summary['required_validated']} / {summary['required_total']}",
                f"- Recommended inputs located: {summary['recommended_found']} / {summary['recommended_total']}",
                "",
                "### Missing required inputs",
                "",
            ]
        )
        missing = summary["missing_required"]
        lines.extend([f"- `{key}`" for key in missing] or ["- None"])
        lines.extend(["", "### Located but still requiring review", ""])
        lines.extend(
            [f"- `{key}`" for key in summary["review_required"]] or ["- None"]
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The parser never approves publication automatically. A human reviewer must confirm "
            "scope, periods, units, signs, and company-specific model inputs.",
            "",
        ]
    )
    output = workdir / "analysis.md"
    atomic_write_text(output, "\n".join(lines))
    return output


def local_ocr(
    pdf: Path,
    workdir: Path,
    pages: Iterable[int] | None = None,
    dpi: int = 220,
    engine: str = "auto",
    workers: int = 4,
) -> dict[str, Any]:
    manifest = read_json(workdir / "manifest.json")
    pdf = pdf.expanduser().resolve()
    if file_sha256(pdf) != manifest.get("source_sha256"):
        raise ParserError("OCR PDF does not match the extracted manifest.")
    pdftoppm = resolve_binary("pdftoppm")
    if engine not in {"auto", "tesseract"}:
        raise ParserError(f"Unsupported OCR engine: {engine}")
    tesseract = resolve_binary("tesseract")
    ocr_engine = "tesseract"
    requested = (
        sorted(set(int(page) for page in pages))
        if pages is not None
        else list(manifest.get("low_text_pages", []))
    )
    if not requested:
        return manifest

    page_map = {int(item["page"]): item for item in manifest["pages"]}
    with tempfile.TemporaryDirectory(prefix="finsight-ocr-") as temporary:
        temporary_path = Path(temporary)

        def process_page(page: int) -> tuple[int, str, str, int]:
            if page < 1 or page > int(manifest["page_count"]):
                raise ParserError(f"OCR page out of range: {page}")
            prefix = temporary_path / f"page-{page:04d}"
            run_command(
                [
                    pdftoppm,
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-r",
                    str(dpi),
                    "-png",
                    "-singlefile",
                    str(pdf),
                    str(prefix),
                ]
            )
            image = prefix.with_suffix(".png")
            text = run_command(
                [tesseract, str(image), "stdout", "--psm", "6"]
            )
            existing = _page_text(workdir, page)
            chosen = (
                text
                if len(re.sub(r"\s", "", text))
                > len(re.sub(r"\s", "", existing))
                else existing
            )
            real_chars = len(re.sub(r"\s", "", chosen))
            method = ocr_engine if chosen == text else "pdftotext"
            return page, chosen, method, real_chars

        max_workers = max(1, min(int(workers), len(requested), 8))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_page, page): page for page in requested
            }
            for future in as_completed(futures):
                page, chosen, method, real_chars = future.result()
                atomic_write_text(
                    workdir / "pages" / f"page-{page:04d}.txt",
                    chosen,
                )
                page_map[page]["chars"] = real_chars
                page_map[page]["needs_ocr"] = real_chars < LOW_TEXT_CHARS
                page_map[page]["extraction_method"] = method

    manifest["pages"] = [page_map[index] for index in sorted(page_map)]
    manifest["low_text_pages"] = [
        item["page"] for item in manifest["pages"] if item["needs_ocr"]
    ]
    manifest["ocr_updated_at"] = utc_now()
    write_json(workdir / "manifest.json", manifest)
    return manifest
