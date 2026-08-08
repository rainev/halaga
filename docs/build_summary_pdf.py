#!/usr/bin/env python3
"""Render the FinSight business summary as a landscape slide PDF (mirrors the PPTX).
Writes finsight-summary-slides.html; print to PDF with Chrome (see command in the runner).
"""
from pathlib import Path
HERE = Path(__file__).parent

CSS = """
@page { size: 13.333in 7.5in; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #1a2230; }
.slide { width: 13.333in; height: 7.5in; page-break-after: always; position: relative; overflow: hidden; padding: 0; }
.band { background: #0b3d2e; height: 1.55in; padding: 0.28in 0.7in; position: relative; }
.kicker { color: #7cf0c0; font-size: 12pt; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; }
.htitle { color: #fff; font-size: 30pt; font-weight: 800; margin-top: 6px; }
.rule { width: 1.4in; height: 5px; background: #7cf0c0; position: absolute; left: 0.7in; bottom: 0.18in; }
.body { padding: 0.5in 0.7in; }
.big { color: #1f7a58; font-size: 40pt; font-weight: 800; }
.biglbl { color: #5b6b63; font-size: 14pt; margin-top: 4px; }
.cols { display: flex; gap: 0.5in; }
ul { list-style: none; }
li { font-size: 17pt; margin-bottom: 12px; line-height: 1.35; }
li:before { content: "•"; color: #1f7a58; font-weight: 800; margin-right: 10px; }
li.b { font-weight: 700; color: #0b3d2e; }
table { border-collapse: collapse; font-size: 13pt; margin-top: 6px; }
th { background: #10553f; color: #fff; text-align: left; padding: 7px 12px; font-weight: 700; }
td { padding: 7px 12px; border-bottom: 1px solid #e2e8e4; }
tr:nth-child(even) td { background: #f1f7f3; }
td.n { text-align: right; }
.foot { position: absolute; right: 0.6in; bottom: 0.35in; color: #9fb0a8; font-size: 9pt; }
/* cover */
.cover { background: #0b3d2e; width: 13.333in; height: 7.5in; padding: 2.35in 0.9in; page-break-after: always; }
.cover .k { color: #7cf0c0; font-size: 16pt; font-weight: 700; letter-spacing: 2px; }
.cover h1 { color: #fff; font-size: 52pt; font-weight: 800; margin: 8px 0; }
.cover .cr { width: 2.2in; height: 6px; background: #7cf0c0; margin: 14px 0; }
.cover .sub { color: #eafff6; font-size: 18pt; }
.cover .dt { color: #9fc8b8; font-size: 13pt; margin-top: 2.4in; }
/* summary */
.sum { background: #0b3d2e; width: 13.333in; height: 7.5in; padding: 0.7in 0.9in; }
.sum .k { color: #7cf0c0; font-size: 14pt; font-weight: 700; letter-spacing: 2px; }
.sum h2 { color: #fff; font-size: 30pt; font-weight: 800; margin: 10px 0 24px; }
.sum p { color: #eafff6; font-size: 17pt; margin-bottom: 11px; }
.sum p:before { content: "→  "; color: #7cf0c0; }
"""

def slide(kicker, title, body_html, n):
    return f'''<div class="slide">
      <div class="band"><div class="kicker">{kicker}</div><div class="htitle">{title}</div><div class="rule"></div></div>
      <div class="body">{body_html}</div><div class="foot">FinSight · {n}</div></div>'''

def bignum(num, lbl):
    return f'<div style="display:inline-block;margin-right:0.5in;vertical-align:top;"><div class="big">{num}</div><div class="biglbl">{lbl}</div></div>'

def ul(items):
    lis = "".join(f'<li class="{"b" if b else ""}">{t}</li>' for t, b in items)
    return f"<ul>{lis}</ul>"

slides = []

# cover
slides.append(f'''<div class="cover"><div class="k">FINSIGHT</div>
  <h1>Business Summary</h1><div class="cr"></div>
  <div class="sub">PSE valuation + portfolio-aware insights — unit economics, pricing &amp; scaling</div>
  <div class="dt">Draft · July 2026</div></div>''')

# 2 what it is
slides.append(slide("The product", "What FinSight is", ul([
    ("An investment-awareness platform for PSE investors — a live app.", True),
    ("Pillar 1 — Valuation workbench: value any PSE stock with 4 classic models (DCF, DDM, Graham, Multiples), PH-calibrated.", False),
    ("Pillar 2 — Portfolio-aware insights: “never be blindsided by news that touches what you own.”", False),
    ("The contract: awareness, not advice — surface, connect, cite the source; never “buy/sell.”", False),
    ("Insights are generated once per (article, company) and shared across all users — so AI cost is ~flat.", False),
]), 2))

# 3 market
slides.append(slide("The market", "A market in a land-grab moment",
    bignum("2.86M", "PSE accounts, 2024 — +50% YoY") + bignum("86%", "online / mobile") + bignum("53%", "aware of investing")
    + '<div style="margin-top:0.5in">' + ul([
        ("18–29 is the fastest-growing cohort (26.5%) — learns to invest on TikTok.", False),
        ("New, mobile-first, socially-taught, under-equipped — exactly FinSight's customer.", True),
        ("Source: PSE 2024 · DataReportal 2025 · BSP CFIS (see market-research.md).", False),
    ]) + "</div>", 3))

# 4 pricing
pricing = '''<div style="color:#1f7a58;font-weight:700;font-size:15pt;margin-bottom:10px">Two tiers · four billing terms · everyone pays after the free trial</div>
<div class="cols">
<table><tr><th>Standard — ₱99/mo</th><th>Price</th><th>/mo</th></tr>
<tr><td>Monthly</td><td class="n">₱99</td><td class="n">₱99</td></tr>
<tr><td>3 months</td><td class="n">₱279</td><td class="n">₱93</td></tr>
<tr><td>6 months</td><td class="n">₱534</td><td class="n">₱89</td></tr>
<tr><td>Annual (2 mo free)</td><td class="n">₱990</td><td class="n">₱82.50</td></tr></table>
<table><tr><th>Pro — ₱299/mo</th><th>Price</th><th>/mo</th></tr>
<tr><td>Monthly</td><td class="n">₱299</td><td class="n">₱299</td></tr>
<tr><td>3 months</td><td class="n">₱849</td><td class="n">₱283</td></tr>
<tr><td>6 months</td><td class="n">₱1,614</td><td class="n">₱269</td></tr>
<tr><td>Annual (2 mo free)</td><td class="n">₱2,990</td><td class="n">₱249</td></tr></table>
</div>
<div style="margin-top:16px">''' + ul([
    ("Longer terms pull cash forward and cut churn; Pro lifts ARPU without raising the ₱99 entry.", True),
    ("Pro adds: unlimited holdings, real-time alerts, sector/peer insights, history/export, priority.", False),
]) + "</div>"
slides.append(slide("The model", "How we charge — 3 months free, then pay", pricing, 4))

# 5 unit economics
slides.append(slide("Unit economics", "Everyone pays ₱99 — the model that works",
    bignum("₱99", "revenue / user / mo (vs ~₱15 freemium)") + bignum("~20", "users to break even") + bignum("~₱13", "tech cost / user / mo")
    + '<div style="margin-top:0.5in">' + ul([
        ("Everyone pays → revenue/user ~6.6× a 5%-conversion freemium. Lower price, but all pay.", True),
        ("Tech cost/user falls with scale (₱13 → ₱7); AI is a rounding error (shared insights).", False),
        ("Cost is never the constraint — acquisition, trial conversion and churn are.", False),
    ]) + "</div>", 5))

# 6 headcount
slides.append(slide("Staying lean", "Headcount grows far slower than users",
    '<div class="cols"><table><tr><th>Users</th><th>People</th><th>Who</th></tr>'
    '<tr><td>10 – 2,000</td><td class="n">1</td><td>just you (solo founder)</td></tr>'
    '<tr><td>3,000 – 5,000</td><td class="n">2</td><td>you + support</td></tr>'
    '<tr><td>10,000</td><td class="n">3</td><td>you + support + engineer</td></tr></table>'
    '<div style="max-width:4in">' + ul([
        ("Solo to ~2,000 users.", True),
        ("Hire only when revenue already pays for it.", False),
        ("Users grow 500×; people grow 1 → 3 — that gap is the business.", True),
    ]) + "</div></div>", 6))

# 7 profitability
slides.append(slide("Profitability", "Profit at ₱99, everyone pays",
    '<div class="cols"><table><tr><th>Users</th><th>Revenue/mo</th><th>Burn/mo</th><th>Profit/mo</th></tr>'
    '<tr><td>500</td><td class="n">₱49,500</td><td class="n">₱4,000</td><td class="n">+₱45,500</td></tr>'
    '<tr><td>1,000</td><td class="n">₱99,000</td><td class="n">₱5,000</td><td class="n">+₱94,000</td></tr>'
    '<tr><td>2,000</td><td class="n">₱198,000</td><td class="n">₱7,000</td><td class="n">+₱191,000</td></tr>'
    '<tr><td>5,000</td><td class="n">₱495,000</td><td class="n">₱43,000</td><td class="n">+₱452,000</td></tr>'
    '<tr><td>10,000</td><td class="n">₱990,000</td><td class="n">₱134,000</td><td class="n">+₱856,000</td></tr></table>'
    '<div style="max-width:3.3in;color:#5b6b63;font-size:14pt">Steady-state, everyone-pays view. At a realistic 50% trial→paid, halve it — still ~₱361k/mo profit at 10k users.</div></div>', 7))

# 8 annual cash
slides.append(slide("Cash flow", "Annual plans fund the whole business",
    bignum("₱9.9M", "cash upfront at 10,000 annual subs") + bignum("~₱8.3M", "annual profit at 10k")
    + '<div style="margin-top:0.5in">' + ul([
        ("Annual (₱990, “2 months free”) collects a full year at signup — self-funds growth &amp; hiring.", True),
        ("Cuts churn to one renewal a year; boosts lifetime value.", False),
        ("Offer both monthly and annual; 30–50% annual take-up is common.", False),
    ]) + "</div>", 8))

# 9 gtm
slides.append(slide("Go-to-market", "The only real constraint: getting users", ul([
    ("Organic-first social: TikTok (lead), Facebook, Instagram — where PH's 18–29 investors are.", True),
    ("Pillars: “Halaga check” valuation series, “blindsided” awareness, street/vox-pop interviews.", False),
    ("Message = awareness, not advice — the compliant alternative to “hot tip” finfluencers.", False),
    ("Paid amplification later — boost the organic posts that already win (social-campaigns.md).", False),
    ("Cost is trivial; the entire game is acquisition → trial conversion → retention.", True),
]), 9))

# 10 summary
sums = [
    "₱99/mo, everyone pays after a 3-month free trial — plus 3/6/12-month terms and a ₱299 Pro tier.",
    "Break even at ~20 paying users; solo and profitable to ~2,000 users.",
    "10,000 users → ~₱990k/mo revenue, ~₱856k/mo profit — with a 3-person team.",
    "Annual plans collect ~₱9.9M upfront at 10k subs — self-funds growth.",
    "Tech (cloud + news + AI) is a rounding error; people are the cost, hired behind revenue.",
    "The only constraint is acquisition — which the organic campaign plan targets directly.",
]
slides.append('<div class="sum"><div class="k">THE PUNCHLINE</div>'
    '<h2>Cheap to run, profitable early, cash-rich at scale</h2>'
    + "".join(f"<p>{t}</p>" for t in sums) + "</div>")

html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(slides)}</body></html>"
out = HERE / "finsight-summary-slides.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out}")
