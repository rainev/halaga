#!/usr/bin/env python3
"""Render docs/cost-model.md into a styled PDF (same theme as the marketing deck).
Run with a Python that has `markdown` (e.g. anaconda). Then print to PDF with Chrome.
"""
from pathlib import Path
import markdown

HERE = Path(__file__).parent
SRC = HERE / "cost-model.md"

md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
body = md.convert(SRC.read_text(encoding="utf-8"))

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #1a2230; font-size: 10.5pt; line-height: 1.5; margin: 0; }
.cover { height: 247mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always; padding: 0 6mm;
  background: linear-gradient(135deg, #0b3d2e 0%, #10553f 55%, #1f7a58 100%); color: #eafff6; border-radius: 2mm; }
.cover .brand { font-size: 13pt; letter-spacing: 3px; text-transform: uppercase; opacity: .8; }
.cover h1 { font-size: 32pt; line-height: 1.1; margin: 6mm 0 4mm; color: #ffffff; font-weight: 800; }
.cover .sub { font-size: 12.5pt; opacity: .9; max-width: 150mm; }
.cover .meta { margin-top: 14mm; font-size: 9.5pt; opacity: .75; }
.cover .rule { width: 40mm; height: 3px; background: #7cf0c0; margin: 5mm 0; border: 0; }
h1 { font-size: 19pt; color: #0b3d2e; margin: 8mm 0 3mm; font-weight: 800; }
h2 { font-size: 14pt; color: #10553f; margin: 7mm 0 2mm; padding-top: 1mm; border-top: 1px solid #e2e8e4; }
h3 { font-size: 11.5pt; color: #1f7a58; margin: 5mm 0 1.5mm; }
p { margin: 0 0 2.5mm; }
a { color: #1f7a58; text-decoration: none; word-break: break-all; }
strong { color: #0b3d2e; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin: 0 0 1mm; }
code { background: #eef4f0; padding: 0.5mm 1.5mm; border-radius: 1mm; font-family: "SF Mono", Menlo, monospace; font-size: 8.8pt; color: #0b3d2e; }
blockquote { margin: 3mm 0; padding: 3mm 5mm; background: #f2f8f4; border-left: 3px solid #1f7a58; border-radius: 0 2mm 2mm 0; font-size: 9.8pt; }
blockquote p:last-child { margin-bottom: 0; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm; font-size: 9pt; page-break-inside: avoid; }
th { background: #10553f; color: #fff; text-align: left; padding: 2mm 2.5mm; font-weight: 600; font-size: 8.8pt; }
td { padding: 2mm 2.5mm; border-bottom: 1px solid #e2e8e4; vertical-align: top; }
tr:nth-child(even) td { background: #f6faf8; }
hr { border: 0; border-top: 1px solid #dde5e0; margin: 6mm 0; }
h2, h3, table, blockquote { page-break-inside: avoid; }
"""

cover = """
<div class="cover">
  <div class="brand">FinSight</div>
  <h1>Production Cloud &amp; AI Cost Model</h1>
  <hr class="rule"/>
  <div class="sub">What it costs to run FinSight at scale — cloud, news feeds, and OpenAI — with per-user economics</div>
  <div class="meta">Draft &middot; July 2026 &middot; AI provider: OpenAI</div>
</div>
"""

html_doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{cover}{body}</body></html>"""
out = HERE / "finsight-cost-model.html"
out.write_text(html_doc, encoding="utf-8")
print(f"wrote {out}")
