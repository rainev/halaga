# FinSight Financial Report Parser

This parser is local-first and costs nothing to run. It extracts PDF text with
Poppler, optionally uses local Tesseract OCR, locates the primary statements,
identifies the issuer and its configured PSE subsector, prioritizes the relevant
valuation inputs, runs accounting controls, and produces a human-review report.

It does **not** use an OpenAI API key or approve a valuation automatically.

## Quick start

```bash
# Automatic issuer/subsector routing from the filing
python parse_fs_report.py all "/path/to/report.pdf"

# Explicit ticker override when identity cannot be read reliably
python parse_fs_report.py all "/path/to/report.pdf" --symbol AREIT
```

The default output directory includes a document hash, preventing two similarly
named filings from silently sharing data.

To index the complete `Archetype-testing` collection and refresh the web-app
dataset:

```bash
python ingest_archetype_testing.py \
  --source ../Archetype-testing \
  --output ../output/archetype-testing \
  --frontend-json ../frontend/public/data/archetype-testing.json \
  --workers 4 \
  --ocr-mode auto
```

The batch importer reads comparative periods from the columns inside each
statement. It preserves standalone-quarter and year-to-date values separately,
deduplicates identical PDFs, rejects entity mismatches, and excludes parent-only
filings from consolidated-company coverage. Every result shown in the app is a
review candidate with page-level source evidence; it is not an approved model
input.

Important outputs:

- `manifest.json` — source hash, page count, extraction method, and OCR state.
- `located.json` — scored statement headings and selected statement pages.
- `facts.json` / `facts.csv` — every matched line item with raw text, page, line,
  period clues, unit context, and confidence.
- `routing.json` — detected issuer, PSE subsector, selected model family,
  routing confidence, and the exact prioritized input keys.
- `requirements.json` — found and missing inputs for the selected issuer and
  subsector valuation profile.
- `validation.json` — accounting, provenance, ambiguity, and completeness gates.
- `analysis.md` — concise human-review handoff.

## Commands

```bash
# Extract text and create a clean, hashed manifest
python parse_fs_report.py extract report.pdf

# Free local Tesseract OCR for pages flagged as image-only.
python parse_fs_report.py ocr report.pdf --workdir out/<document> --pages 4-7 --workers 4

# Locate the primary statements
python parse_fs_report.py locate --workdir out/<document>

# Index every page, including notes and operating metrics
python parse_fs_report.py index --workdir out/<document>

# Automatically identify and check the issuer
python parse_fs_report.py requirements --workdir out/<document>

# Check with an explicit ticker override
python parse_fs_report.py requirements --workdir out/<document> --symbol AP

# Search for any future line item without changing code
python parse_fs_report.py query --workdir out/<document> "reserve replacement ratio"
python parse_fs_report.py query --workdir out/<document> "MW|GWh" --regex

# Combine annual, quarterly, and operating disclosures without losing provenance
python parse_fs_report.py merge out/AP-annual out/AP-q1 out/AP-q2 \
  --output out/AP-corpus --symbol AP
```

## Extending the parser

Add new canonical line items and aliases to:

`config/line_item_catalog.json`

Add or revise company/model requirements in:

`config/wave1_requirements.json`

That file contains:

- reusable financial-input templates;
- the 23 PSE subsector defaults;
- a curated issuer-to-subsector directory; and
- company-specific business-model overrides.

Company overrides take priority over subsector defaults. For example, a REIT can
use the REIT template even though its PSE subsector is Property. An unresolved or
ambiguous issuer receives only the conservative common-equity fallback and is
blocked pending classification review.

The configurations are validated at startup. Unknown requirement keys,
subsectors, duplicate catalog keys, and template-inheritance cycles cause an
immediate error.

The issuer directory is a maintained application reference, not a permanent
copy of the PSE directory. Refresh classifications periodically, store the
classification date/source in production, and use `--symbol` only as an audited
override.

## Valuation-framework coverage

The canonical catalog and requirement templates are aligned with
`../PSE_VALUATION_ENGINE_FRAMEWORK_CONSOLIDATED.md`. The field-by-field coverage
matrix is documented in:

`VALUATION_INPUT_COVERAGE.md`

The parser extracts reported accounting facts and operating KPIs. Market prices,
peer multiples, beta, Philippine risk-free rates, ERP, WACC, terminal growth,
forecast assumptions, and scenario probabilities remain valuation-engine inputs
and are intentionally not inferred from company PDFs.

Subsector routing prioritizes relevant keys in the extraction profile but retains
the full catalog and all other detected facts. This avoids discarding evidence
needed for conglomerates, mixed businesses, or later model changes.

## Safety model

The parser distinguishes three states:

1. `blocked` — required inputs or accounting controls failed.
2. `validated` — automated calculations and provenance checks passed.
3. `human_review_required` — publication still needs a reviewer to confirm
   consolidation scope, periods, units, signs, and company-specific assumptions.

Structured output guarantees organization, not truth. For that reason, the
parser retains raw evidence and never turns a successful calculation into an
automatic publication approval.

## Local dependencies

- Poppler: `pdftotext`, with `pdfinfo` recommended.
- Scanned-page OCR: `pdftoppm` and Tesseract.

There are no required Python packages outside the standard library.

## Tests

```bash
python -m unittest discover -s tests -v
```
