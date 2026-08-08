#!/usr/bin/env python3
"""Render PSE-Valuation-Framework.md to a print-quality PDF via markdown + WeasyPrint."""
from pathlib import Path
import markdown

HERE = Path(__file__).parent
SRC = HERE / "PSE-Valuation-Framework.md"
OUT_HTML = HERE / "PSE-Valuation-Framework.html"
OUT_PDF = HERE / "PSE-Valuation-Framework.pdf"

CSS = """
@page {
  size: A4; margin: 20mm 16mm 18mm 16mm;
  @bottom-center { content: "FinSight · PSE Sector-Aware Valuation Framework"; font-size: 8pt; color: #9fb0a8; }
  @bottom-right  { content: counter(page) " / " counter(pages); font-size: 8pt; color: #9fb0a8; }
}
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Helvetica Neue", Arial, sans-serif; color: #1a2230; font-size: 9.5pt; line-height: 1.5; }
h1 { color: #0b3d2e; font-size: 22pt; font-weight: 800; margin: 0 0 4px; line-height: 1.15; }
h2 { color: #0b3d2e; font-size: 15pt; font-weight: 800; margin: 22px 0 8px; padding-bottom: 5px;
     border-bottom: 3px solid #7cf0c0; page-break-after: avoid; }
h3 { color: #10553f; font-size: 12pt; font-weight: 700; margin: 16px 0 6px; page-break-after: avoid; }
h4 { color: #1f7a58; font-size: 10.5pt; font-weight: 700; margin: 12px 0 4px; }
p { margin: 6px 0; }
a { color: #1f7a58; text-decoration: none; }
strong { color: #0b3d2e; }
em { color: #5b6b63; }
ul, ol { margin: 6px 0 6px 18px; padding-left: 6px; }
li { margin-bottom: 3px; }
hr { border: none; border-top: 1px solid #d7e2db; margin: 18px 0; }
blockquote { margin: 10px 0; padding: 8px 14px; background: #f1f7f3; border-left: 4px solid #1f7a58; color: #33463d; }
code { font-family: "SF Mono", "Menlo", Consolas, monospace; font-size: 8.6pt; background: #eef4f0;
       padding: 1px 4px; border-radius: 3px; color: #0b3d2e; }
pre { background: #0b3d2e; color: #eafff6; padding: 12px 14px; border-radius: 6px; overflow-x: auto;
      font-size: 8.4pt; line-height: 1.45; page-break-inside: avoid; }
pre code { background: none; color: #eafff6; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 8.4pt; page-break-inside: auto; }
thead { display: table-header-group; }
th { background: #10553f; color: #fff; text-align: left; padding: 6px 8px; font-weight: 700;
     vertical-align: top; border: 1px solid #10553f; }
td { padding: 5px 8px; border: 1px solid #dce6e0; vertical-align: top; }
tr:nth-child(even) td { background: #f4f9f6; }
tr { page-break-inside: avoid; }
h1 + p em, body > p:first-of-type { color: #5b6b63; }
"""

md_text = SRC.read_text(encoding="utf-8")
html_body = markdown.markdown(
    md_text,
    extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
)
html_doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"
OUT_HTML.write_text(html_doc, encoding="utf-8")
print(f"wrote {OUT_HTML}")
