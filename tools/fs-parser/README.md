# FinSight — Financial-Statement Report Parser

Parse large PSE reports (annual reports, 17-Qs) into **structured financials + a
narrative brief**, to feed FinSight's valuation models.

## The key decision: text-first, not OCR-first

The JFC reports (and most PSE filings) are **digital PDFs — the text is already
embedded**. Verified on the real files:

| Report | Pages | Text? | Image-only pages |
|---|---|---|---|
| Annual Report 2024 | 659 | ✅ clean | 27 (charts/photos) → optional OCR |
| Q1 2025 17-Q | 153 | ✅ clean | — |

So we **extract text directly with `pdftotext`** (fast, free, accurate) and use
**OCR only as a fallback** for the handful of image-only pages. OCRing all 600+
pages would be slower, lossier, and needlessly expensive.

## Pipeline

```
extract   PDF → per-page text + manifest.json  (flags low-text pages)   [free, local]
ocr       OCR only the flagged pages via OpenAI vision (optional)       [OpenAI]
locate    find the consolidated-statement pages by anchor phrases       [free, local]
analyze   send located pages → OpenAI → financials.json + analysis.md   [OpenAI]
```

`financials.json` — structured income / balance-sheet / cash-flow line items across
all reported periods, plus per-share data (EPS, DPS, shares, book value).
`analysis.md` — a grounded brief that lists the exact inputs each FinSight model
needs (DCF: FCF/growth/capex · DDM: DPS/payout · Graham: EPS/growth · Multiples:
EPS/peer P/E), and flags anything missing. *Informational only — never "buy/sell".*

## Requirements

- **poppler** (`pdftotext`, `pdftoppm`): `brew install poppler`
- **openai**: `pip install openai` — only needed for `ocr` / `analyze`
- `export OPENAI_API_KEY=sk-...`

Models default to **GPT-5 mini** (extraction/OCR) and **GPT-5** (synthesis); override
with `--extract-model` / `--synth-model`. Only the *located* statement pages are sent
to OpenAI — not the whole book — so a full analysis costs roughly **$0.05–0.10** per
report. (OCR of a low-text page is ~$0.02 each.)

## Usage

```bash
cd tools/fs-parser

# one-shot: extract → locate → analyze
python parse_fs_report.py all "../../JFC FS Reports/Annual Report - 2024 ....pdf"

# or stage by stage
python parse_fs_report.py extract "<pdf>"                 # local, free
python parse_fs_report.py ocr     "<pdf>" --workdir out/<name>   # optional, fills image pages
python parse_fs_report.py locate  --workdir out/<name>
python parse_fs_report.py analyze --workdir out/<name>
# override auto-locate with a manual page range:
python parse_fs_report.py analyze --workdir out/<name> --pages 427-445
```

Output lands in `out/<report-slug>/` (`pages/`, `manifest.json`, `located.json`,
`financials.json`, `analysis.md`).

## Verified

`extract` + `locate` run clean on the real 659-page JFC 2024 report: located the
consolidated statements at **pp. 427–445**, extracted columnar figures correctly
(e.g. 2024 net income ₱10,795,840 thousand), and flagged 27 image-only pages for
optional OCR. The `analyze` stage needs your `OPENAI_API_KEY`.

## Tuning

- If a report uses different statement headings, edit `STATEMENT_ANCHORS` in the
  script (or pass `--pages` manually).
- `LOW_TEXT_CHARS` controls the OCR trigger threshold; `MAX_ANALYZE_CHARS` caps how
  much text goes to the model in one call.
