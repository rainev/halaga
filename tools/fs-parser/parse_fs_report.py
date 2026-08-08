#!/usr/bin/env python3
"""
parse_fs_report.py — Financial-statement report parser for FinSight.

Pipeline:  extract (text-first, OCR fallback)  ->  locate (find the statements)
           ->  analyze (OpenAI structured extraction + narrative)

Most PSE annual reports / 17-Qs are DIGITAL PDFs — their text is already embedded,
so we extract it directly with `pdftotext` (fast, free, accurate). OCR is only a
*fallback* for image-only pages (scanned signatures, chart images), rendered with
`pdftoppm` and read by an OpenAI vision model. Don't OCR 600 pages you don't need to.

Stages
------
  extract   PDF -> per-page text files + manifest.json (flags low-text pages)
  ocr       (optional) OCR only the flagged low-text pages, fill them in
  locate    find the consolidated statement pages by anchor phrases
  analyze   send the located pages to OpenAI -> financials.json + analysis.md
  all       extract -> locate -> analyze (the usual path)

Usage
-----
  # OPENAI_API_KEY is read from finsight/.env automatically (or export it yourself).
  python parse_fs_report.py all "../../JFC FS Reports/Annual Report - 2024 ....pdf"
  python parse_fs_report.py extract "<pdf>"            # just pull text
  python parse_fs_report.py analyze  --workdir out/<name>   # re-run analysis only

Requires: pdftotext + pdftoppm (poppler), openai (pip install openai).
Models default to GPT-5 mini for extraction and GPT-5 for synthesis (override with
--extract-model / --synth-model). Nothing is sent to OpenAI until the `analyze`/`ocr`
stage, and only the located pages are sent — not the whole 600-page book.
"""
from __future__ import annotations
import argparse, base64, json, os, re, subprocess, sys, textwrap
from dataclasses import dataclass, asdict
from pathlib import Path


def _load_dotenv() -> None:
    """Load finsight/.env so OPENAI_API_KEY (and model overrides) work without an
    explicit `export`. This is a standalone tool that may run outside the backend
    venv, so python-dotenv is optional and real exported vars win (override=False)."""
    try:
        from dotenv import load_dotenv, find_dotenv
    except ModuleNotFoundError:
        return
    repo_env = Path(__file__).resolve().parents[2] / ".env"   # finsight/.env
    env_path = str(repo_env) if repo_env.is_file() else find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=False)


_load_dotenv()

# ----------------------------- config ---------------------------------------

LOW_TEXT_CHARS = 120          # a page with fewer real chars than this is "image-only"
MAX_ANALYZE_CHARS = 380_000   # cap on text sent to the model in one analyze call
EXTRACT_MODEL_DEFAULT = "gpt-5-mini"
SYNTH_MODEL_DEFAULT = "gpt-5"
OCR_MODEL_DEFAULT = "gpt-5-mini"   # vision-capable

# Anchor phrases that mark the consolidated financial statements. Case-insensitive.
STATEMENT_ANCHORS = [
    "consolidated statements of income",
    "consolidated statements of comprehensive income",
    "consolidated statements of financial position",
    "consolidated balance sheet",
    "consolidated statements of cash flows",
    "consolidated statements of changes in equity",
    "statements of income",
    "statements of financial position",
    "statements of cash flows",
]

# ----------------------------- helpers --------------------------------------

def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

def which_or_die(binname: str):
    from shutil import which
    if which(binname) is None:
        sys.exit(f"ERROR: `{binname}` not found on PATH. Install poppler (brew install poppler).")

def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()[:60]

# ----------------------------- extract --------------------------------------

@dataclass
class PageMeta:
    page: int          # 1-indexed
    chars: int
    needs_ocr: bool

def extract(pdf: Path, workdir: Path) -> dict:
    """pdftotext -layout the whole file, split on form-feed into per-page text."""
    which_or_die("pdftotext")
    pages_dir = workdir / "pages"; pages_dir.mkdir(parents=True, exist_ok=True)
    raw = sh(["pdftotext", "-layout", str(pdf), "-"])
    pages = raw.split("\f")
    # pdftotext emits a trailing empty chunk after the last form-feed
    if pages and pages[-1].strip() == "":
        pages = pages[:-1]
    meta: list[PageMeta] = []
    for i, text in enumerate(pages, start=1):
        real = len(re.sub(r"\s", "", text))
        (pages_dir / f"page-{i:04d}.txt").write_text(text, encoding="utf-8")
        meta.append(PageMeta(page=i, chars=real, needs_ocr=real < LOW_TEXT_CHARS))
    manifest = {
        "source_pdf": str(pdf),
        "page_count": len(pages),
        "low_text_pages": [m.page for m in meta if m.needs_ocr],
        "pages": [asdict(m) for m in meta],
    }
    (workdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[extract] {len(pages)} pages -> {pages_dir}")
    n_low = len(manifest["low_text_pages"])
    if n_low:
        print(f"[extract] {n_low} low-text page(s) flagged for OCR: "
              f"{manifest['low_text_pages'][:20]}{' ...' if n_low > 20 else ''}")
        print("[extract] run the `ocr` stage (needs OPENAI_API_KEY) to fill these in.")
    else:
        print("[extract] no image-only pages — OCR not needed. Text is fully embedded. ✅")
    return manifest

# ----------------------------- ocr (fallback) -------------------------------

def _openai():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("ERROR: `openai` not installed. pip install openai")
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("ERROR: set OPENAI_API_KEY in the environment.")
    return OpenAI()

def ocr(pdf: Path, workdir: Path, model: str):
    """OCR only the pages flagged low-text in manifest.json, via pdftoppm + OpenAI vision."""
    which_or_die("pdftoppm")
    client = _openai()
    manifest = json.loads((workdir / "manifest.json").read_text())
    low = manifest["low_text_pages"]
    if not low:
        print("[ocr] nothing to do — no low-text pages."); return
    pages_dir = workdir / "pages"; img_dir = workdir / "ocr-img"; img_dir.mkdir(exist_ok=True)
    for p in low:
        png = img_dir / f"page-{p:04d}.png"
        if not png.exists():
            sh(["pdftoppm", "-png", "-r", "200", "-f", str(p), "-l", str(p),
                str(pdf), str(img_dir / f"page-{p:04d}")])
            # pdftoppm names it page-XXXX-<n>.png; normalize
            for cand in img_dir.glob(f"page-{p:04d}*"):
                cand.rename(png); break
        b64 = base64.b64encode(png.read_bytes()).decode()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Transcribe ALL text and tabular figures from this "
                                         "financial-report page verbatim. Preserve numbers and "
                                         "table structure. Output plain text only."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
        )
        text = resp.choices[0].message.content or ""
        (pages_dir / f"page-{p:04d}.txt").write_text(text, encoding="utf-8")
        print(f"[ocr] page {p}: {len(text)} chars")
    print("[ocr] done. Re-run `locate`/`analyze`.")

# ----------------------------- locate ---------------------------------------

def locate(workdir: Path, pad: int = 2) -> list[int]:
    """Find pages whose text contains a statement anchor; include `pad` pages after each."""
    pages_dir = workdir / "pages"
    hits: dict[int, list[str]] = {}
    files = sorted(pages_dir.glob("page-*.txt"))
    for f in files:
        p = int(f.stem.split("-")[1])
        low = f.read_text(encoding="utf-8").lower()
        found = [a for a in STATEMENT_ANCHORS if a in low]
        if found:
            hits[p] = found
    selected: set[int] = set()
    for p in hits:
        for q in range(p, p + pad + 1):
            selected.add(q)
    pages = sorted(x for x in selected if (pages_dir / f"page-{x:04d}.txt").exists())
    result = {"anchor_hits": {str(k): v for k, v in sorted(hits.items())},
              "selected_pages": pages}
    (workdir / "located.json").write_text(json.dumps(result, indent=2))
    print(f"[locate] {len(hits)} anchor page(s); selected {len(pages)} pages of statements.")
    for k, v in sorted(hits.items()):
        print(f"         p.{k}: {', '.join(v)}")
    if not pages:
        print("[locate] No anchors matched — the report may use different headings. "
              "Edit STATEMENT_ANCHORS, or run `analyze --pages A-B` with a manual range.")
    return pages

# ----------------------------- analyze --------------------------------------

FINANCIALS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["company", "currency", "periods", "line_items", "per_share",
                 "notes", "source_pages"],
    "properties": {
        "company": {"type": "string"},
        "currency": {"type": "string", "description": "e.g. PHP thousands / millions"},
        "periods": {"type": "array", "items": {"type": "string"},
                    "description": "reporting periods across the columns, e.g. ['2024','2023']"},
        "line_items": {
            "type": "array",
            "description": "one row per financial line, values aligned to `periods`",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["statement", "label", "values"],
                "properties": {
                    "statement": {"type": "string",
                        "enum": ["income", "balance_sheet", "cash_flow", "equity", "other"]},
                    "label": {"type": "string"},
                    "values": {"type": "array", "items": {"type": ["number", "null"]}},
                },
            },
        },
        "per_share": {
            "type": "object", "additionalProperties": False,
            "required": ["eps_basic", "eps_diluted", "dividends_per_share",
                         "shares_outstanding", "book_value_per_share"],
            "properties": {
                "eps_basic": {"type": ["number", "null"]},
                "eps_diluted": {"type": ["number", "null"]},
                "dividends_per_share": {"type": ["number", "null"]},
                "shares_outstanding": {"type": ["number", "null"]},
                "book_value_per_share": {"type": ["number", "null"]},
            },
        },
        "notes": {"type": "array", "items": {"type": "string"},
                  "description": "material facts: segment mix, one-offs, debt, going-concern, etc."},
        "source_pages": {"type": "array", "items": {"type": "integer"}},
    },
}

EXTRACT_SYS = (
    "You are a financial-statement extraction engine for a PSE (Philippine Stock Exchange) "
    "valuation app. From the provided report text, extract the CONSOLIDATED figures into the "
    "given schema. Rules: copy numbers exactly as printed (keep the report's units — do not "
    "rescale); use null when a value is not present; align every row's `values` to `periods` "
    "left-to-right; prefer consolidated over parent-only statements. Do not invent figures."
)

ANALYZE_SYS = (
    "You are an equity analyst writing a concise brief for a PSE valuation tool. Using ONLY the "
    "extracted financials JSON provided, write Markdown covering: (1) headline performance "
    "(revenue, net income, margins, YoY growth), (2) balance-sheet health (debt, cash, equity), "
    "(3) cash flow & dividends, (4) the exact inputs FinSight's models need — for DCF (FCF, "
    "growth, capex), DDM (DPS, payout), Graham (EPS, growth), Multiples (EPS, peer P/E) — listing "
    "each value or flagging it as missing, and (5) red flags / one-offs to watch. This is "
    "informational analysis, not investment advice; never say buy or sell. Be specific and cite "
    "the figures."
)

def _collect_text(workdir: Path, pages: list[int]) -> tuple[str, list[int]]:
    pages_dir = workdir / "pages"
    parts, used = [], []
    total = 0
    for p in pages:
        f = pages_dir / f"page-{p:04d}.txt"
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        if total + len(t) > MAX_ANALYZE_CHARS:
            print(f"[analyze] truncating at page {p} (hit {MAX_ANALYZE_CHARS} char cap).")
            break
        parts.append(f"\n===== PAGE {p} =====\n{t}")
        used.append(p); total += len(t)
    return "".join(parts), used

def analyze(workdir: Path, pages: list[int] | None, extract_model: str, synth_model: str):
    client = _openai()
    if pages is None:
        located = workdir / "located.json"
        if not located.exists():
            sys.exit("[analyze] no located.json — run `locate` first, or pass --pages A-B.")
        pages = json.loads(located.read_text())["selected_pages"]
    if not pages:
        sys.exit("[analyze] no pages to analyze.")
    text, used = _collect_text(workdir, pages)
    print(f"[analyze] sending {len(used)} pages (~{len(text):,} chars) to {extract_model} …")

    # 1) structured extraction
    r1 = client.chat.completions.create(
        model=extract_model,
        messages=[{"role": "system", "content": EXTRACT_SYS},
                  {"role": "user", "content": text}],
        response_format={"type": "json_schema", "json_schema":
            {"name": "financials", "schema": FINANCIALS_SCHEMA, "strict": True}},
    )
    financials = json.loads(r1.choices[0].message.content)
    financials.setdefault("source_pages", used)
    (workdir / "financials.json").write_text(json.dumps(financials, indent=2))
    print(f"[analyze] wrote financials.json "
          f"({len(financials.get('line_items', []))} line items, "
          f"periods={financials.get('periods')})")

    # 2) narrative analysis from the structured data (cheap, grounded)
    r2 = client.chat.completions.create(
        model=synth_model,
        messages=[{"role": "system", "content": ANALYZE_SYS},
                  {"role": "user", "content": json.dumps(financials)}],
    )
    md = r2.choices[0].message.content or ""
    (workdir / "analysis.md").write_text(md, encoding="utf-8")
    print(f"[analyze] wrote analysis.md ({len(md):,} chars)")

# ----------------------------- cli ------------------------------------------

def parse_range(s: str | None) -> list[int] | None:
    if not s:
        return None
    out: list[int] = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out

def main():
    ap = argparse.ArgumentParser(description="FinSight FS-report parser (text-first + OCR fallback).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_pdf(p): p.add_argument("pdf", type=Path, help="path to the report PDF")
    def add_wd(p): p.add_argument("--workdir", type=Path, help="output dir (default: out/<slug>)")

    pe = sub.add_parser("extract"); add_pdf(pe); add_wd(pe)
    po = sub.add_parser("ocr"); add_pdf(po); add_wd(po)
    po.add_argument("--model", default=OCR_MODEL_DEFAULT)
    pl = sub.add_parser("locate"); add_wd(pl); pl.add_argument("--pad", type=int, default=2)
    pa = sub.add_parser("analyze"); add_wd(pa)
    pa.add_argument("--pages", help="manual page range e.g. 120-150,152")
    pa.add_argument("--extract-model", default=EXTRACT_MODEL_DEFAULT)
    pa.add_argument("--synth-model", default=SYNTH_MODEL_DEFAULT)
    pall = sub.add_parser("all"); add_pdf(pall); add_wd(pall)
    pall.add_argument("--pad", type=int, default=2)
    pall.add_argument("--extract-model", default=EXTRACT_MODEL_DEFAULT)
    pall.add_argument("--synth-model", default=SYNTH_MODEL_DEFAULT)

    a = ap.parse_args()
    pdf = getattr(a, "pdf", None)
    wd = getattr(a, "workdir", None)
    if wd is None:
        base = slug(pdf.stem) if pdf else "report"
        wd = Path("out") / base
    wd.mkdir(parents=True, exist_ok=True)

    if a.cmd == "extract":
        extract(pdf, wd)
    elif a.cmd == "ocr":
        ocr(pdf, wd, a.model)
    elif a.cmd == "locate":
        locate(wd, a.pad)
    elif a.cmd == "analyze":
        analyze(wd, parse_range(a.pages), a.extract_model, a.synth_model)
    elif a.cmd == "all":
        extract(pdf, wd)
        pages = locate(wd, a.pad)
        analyze(wd, pages or None, a.extract_model, a.synth_model)

if __name__ == "__main__":
    main()
