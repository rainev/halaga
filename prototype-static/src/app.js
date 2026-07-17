import {
  FILING_NEWS,
  INDUSTRIAL_COMPANIES,
  PHILIPPINE_ASSUMPTIONS,
  SOURCE_LINKS,
} from "./data/industrial.js";
import {
  RISK_PROFILES,
  SENTIMENTS,
  buildSmartBrief,
  calculateValuation,
  getHealthMetrics,
  portfolioCostBasis,
  scoreCompany,
} from "./engine.js";

const app = document.querySelector("#app");
const toast = document.querySelector("#toast");

const icons = {
  rank: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19V9m7 10V5m7 14v-7"/></svg>',
  value: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18M17 7.5c0-1.9-1.8-3-5-3s-5 1.3-5 3 1.5 2.7 5 3.5 5 1.8 5 3.7-1.8 3.3-5 3.3-5-1.2-5-3.3"/></svg>',
  health: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13h4l2-7 4 12 2-5h4M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/></svg>',
  news: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/></svg>',
  portfolio: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h16v11H4zM8 8V5h8v3M4 12h16M10 15h4"/></svg>',
  brief: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3ZM19 15l.7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7L19 15Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>',
  alert: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5M12 17h.01M10.3 4.4 2.7 18a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 4.4a2 2 0 0 0-3.4 0Z"/></svg>',
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
  trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
};

const navItems = [
  ["rankings", "Rankings", icons.rank],
  ["valuation", "Valuation", icons.value],
  ["health", "Health", icons.health],
  ["news", "Briefings", icons.news],
  ["portfolio", "Portfolio", icons.portfolio],
  ["brief", "Smart Brief", icons.brief],
];

const safeJson = (key, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
};

const hashPage = window.location.hash.replace("#", "");
const state = {
  risk: Number(localStorage.getItem("gabay-risk")) || null,
  pendingRisk: Number(localStorage.getItem("gabay-risk")) || 3,
  page: navItems.some(([id]) => id === hashPage) ? hashPage : "rankings",
  selectedSymbol: "SCC",
  sentiment: "base",
  rankingScope: "industrial",
  healthTab: "pnl",
  newsFilter: "ALL",
  directoryQuery: "",
  directorySector: "All sectors",
  lots: safeJson("gabay-portfolio", []),
  listedCompanies: [],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const companyBySymbol = (symbol = state.selectedSymbol) =>
  INDUSTRIAL_COMPANIES.find((company) => company.symbol === symbol) || INDUSTRIAL_COMPANIES[0];

const peso = (value, digits = 2) =>
  Number.isFinite(value)
    ? new Intl.NumberFormat("en-PH", {
        style: "currency",
        currency: "PHP",
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(value)
    : "Not available";

const compactPeso = (value) => {
  if (!Number.isFinite(value)) return "Not available";
  const abs = Math.abs(value);
  if (abs >= 1e9) return `₱${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `₱${(value / 1e6).toFixed(1)}M`;
  return peso(value, 0);
};

const percent = (value, digits = 1) =>
  Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "Not reported";

function formatMetric(metric, target = false) {
  const value = target ? metric.target : metric.value;
  if (!Number.isFinite(value)) return target ? "Context only" : "Not reported";
  if (metric.format === "percent") return percent(value);
  if (metric.format === "multiple") return `${value.toFixed(2)}×`;
  if (metric.format === "currency") return compactPeso(value);
  return value.toFixed(2);
}

function thresholdText(metric) {
  if (metric.direction === "context") return "Review in context";
  if (metric.direction === "range") {
    return `${percent(metric.target - metric.tolerance, 0)}–${percent(metric.target + metric.tolerance, 0)}`;
  }
  return `${metric.direction === "min" ? "At least" : "At most"} ${formatMetric(metric, true)}`;
}

function scoreTone(score) {
  if (score >= 78) return ["Strong", "good"];
  if (score >= 65) return ["Mixed", "mid"];
  return ["Watch", "watch"];
}

function companyOptions(selected = state.selectedSymbol) {
  return INDUSTRIAL_COMPANIES.map(
    (company) =>
      `<option value="${company.symbol}" ${company.symbol === selected ? "selected" : ""}>${company.symbol} · ${escapeHtml(company.shortName)}</option>`,
  ).join("");
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

function renderOnboarding() {
  const cards = Object.entries(RISK_PROFILES)
    .map(
      ([level, profile]) => `
        <button class="risk-card ${Number(level) === state.pendingRisk ? "selected" : ""}" data-risk-pick="${level}" aria-pressed="${Number(level) === state.pendingRisk}">
          <span class="risk-level">${level}</span>
          <span class="risk-copy"><strong>${profile.label}</strong><small>${profile.tone}</small></span>
          <span class="risk-check">${icons.check}</span>
        </button>`,
    )
    .join("");

  app.innerHTML = `
    <main class="onboarding">
      <section class="onboard-brand" aria-label="Gabay Markets introduction">
        <div class="brand-mark large">G</div>
        <div>
          <p class="eyebrow light">Gabay Markets</p>
          <h1>Know what fits<br />your comfort zone.</h1>
          <p>We turn company filings into beginner-friendly screens—without live quotes, noise, or paid APIs.</p>
        </div>
        <div class="onboard-note"><span>01</span><p>Your risk level adjusts every health threshold. You can change it anytime.</p></div>
      </section>
      <section class="onboard-form">
        <div class="onboard-step">Step 1 of 1</div>
        <p class="eyebrow">Your investing style</p>
        <h2>How much uncertainty can you comfortably accept?</h2>
        <p class="muted">Choose the closest fit. This changes screening thresholds—not your money and not a recommendation.</p>
        <div class="risk-grid">${cards}</div>
        <button class="primary wide" data-risk-start>Build my view ${icons.arrow}</button>
        <p class="privacy-line">Saved only in this browser · No account required</p>
      </section>
    </main>`;
}

function navMarkup(className = "side-nav") {
  return `<nav class="${className}" aria-label="Main navigation">${navItems
    .map(
      ([id, label, icon]) => `
        <button data-nav="${id}" class="${state.page === id ? "active" : ""}" aria-current="${state.page === id ? "page" : "false"}">
          ${icon}<span>${label}</span>
        </button>`,
    )
    .join("")}</nav>`;
}

function renderShell() {
  const profile = RISK_PROFILES[state.risk];
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <a class="brand" href="#rankings" data-nav="rankings" aria-label="Gabay Markets home">
          <span class="brand-mark">G</span><span>Gabay<small>MARKETS</small></span>
        </a>
        ${navMarkup()}
        <div class="sidebar-card">
          <span class="live-dot"></span><small>NO-COST MODE</small>
          <strong>Local & private</strong>
          <p>No API key or paid data feed.</p>
        </div>
        <p class="sidebar-disclaimer">Educational mockup<br />Not investment advice</p>
      </aside>
      <div class="workspace">
        <header class="topbar">
          <a class="mobile-brand" href="#rankings" data-nav="rankings"><span class="brand-mark">G</span> Gabay</a>
          <div class="as-of"><span></span> Filing data · FY2025</div>
          <button class="profile-pill" data-change-risk title="Change risk profile">
            <span class="profile-number">${state.risk}</span>
            <span><small>RISK PROFILE</small><strong>${profile.label}</strong></span>
            ${icons.arrow}
          </button>
        </header>
        <main class="page" id="main-content">${renderPage()}</main>
        <footer class="footer">Filing-based educational estimates · No live quotes · Not investment advice</footer>
      </div>
      ${navMarkup("mobile-nav")}
    </div>`;
}

function renderPage() {
  if (state.page === "valuation") return renderValuation();
  if (state.page === "health") return renderHealth();
  if (state.page === "news") return renderNews();
  if (state.page === "portfolio") return renderPortfolio();
  if (state.page === "brief") return renderBrief();
  return renderRankings();
}

function pageHeading(eyebrow, title, description, action = "") {
  return `<header class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p>${description}</p></div>${action}</header>`;
}

function renderRankings() {
  const ranked = [...INDUSTRIAL_COMPANIES]
    .map((company) => ({ company, score: scoreCompany(company, state.risk) }))
    .sort((a, b) => b.score - a.score);
  const top = ranked[0];
  const profile = RISK_PROFILES[state.risk];
  const action = `<div class="scope-switch" role="group" aria-label="Ranking scope">
    <button data-ranking-scope="industrial" class="${state.rankingScope === "industrial" ? "active" : ""}">Industrial scored</button>
    <button data-ranking-scope="all" class="${state.rankingScope === "all" ? "active" : ""}">All PSE directory</button>
  </div>`;

  const hero = `<section class="ranking-hero">
    <div>
      <span class="soft-label">YOUR FUNDAMENTALS LENS</span>
      <h2>Rank quality.<br /><em>Leave price out.</em></h2>
      <p>Scores compare available filing metrics against your level ${state.risk} thresholds. They are research prompts, not buy or sell calls.</p>
    </div>
    <div class="hero-score">
      <div class="score-ring" style="--score:${top.score}"><span><strong>${top.score}</strong><small>/ 100</small></span></div>
      <div><small>TOP FIT TODAY</small><strong>${top.company.symbol} · ${top.company.shortName}</strong><p>${top.company.insight}</p></div>
    </div>
  </section>`;

  return `${pageHeading("Rankings", "Fundamentals, ranked—not priced.", `Tailored for a ${profile.short.toLowerCase()} investor.`, action)}${hero}${
    state.rankingScope === "industrial" ? renderIndustrialRanking(ranked) : renderDirectory()
  }`;
}

function renderIndustrialRanking(ranked) {
  const rows = ranked
    .map(({ company, score }, index) => {
      const [label, tone] = scoreTone(score);
      const health = getHealthMetrics(company, state.risk);
      const checks = [...health.pnl, ...health.balance].filter(
        (metric) => metric.status === "pass" || metric.status === "watch",
      );
      const passed = checks.filter((metric) => metric.status === "pass").length;
      return `<article class="rank-row">
        <div class="rank-position">${String(index + 1).padStart(2, "0")}</div>
        <div class="company-cell"><span class="ticker-logo" style="--company:${company.color}">${company.symbol.slice(0, 2)}</span><span><strong>${company.symbol}</strong><small>${escapeHtml(company.shortName)}</small></span></div>
        <div class="rank-stat"><small>SCREEN SCORE</small><strong>${score}<span>/100</span></strong></div>
        <div class="rank-stat desktop-only"><small>CHECKS CLEARED</small><strong>${passed}<span>/${checks.length}</span></strong></div>
        <div class="rank-summary desktop-only"><small>QUICK READ</small><p>${escapeHtml(company.insight)}</p></div>
        <span class="status ${tone}">${label}</span>
        <button class="icon-button" data-open-company="${company.symbol}" aria-label="Open ${company.shortName} valuation">${icons.arrow}</button>
      </article>`;
    })
    .join("");
  return `<section class="content-section">
    <div class="section-title"><div><p class="eyebrow">Industrial test set</p><h2>Four filing-backed companies</h2></div><span class="data-chip">Updated from FY2025 filings</span></div>
    <div class="rank-list">${rows}</div>
    <div class="method-note">${icons.alert}<p><strong>How this works:</strong> Metrics are availability-adjusted so a missing line item is not treated as zero. Scores change with your risk profile and should start—not finish—your research.</p></div>
  </section>`;
}

function renderDirectory() {
  const sectors = ["All sectors", ...new Set(state.listedCompanies.map((company) => company.sector).filter(Boolean))].sort();
  const query = state.directoryQuery.toLowerCase();
  const filtered = state.listedCompanies.filter((company) => {
    const matchesSearch = !query || `${company.name} ${company.symbol}`.toLowerCase().includes(query);
    return matchesSearch && (state.directorySector === "All sectors" || company.sector === state.directorySector);
  });
  const rows = filtered.slice(0, 80).map((company) => {
    const scored = INDUSTRIAL_COMPANIES.some((item) => item.symbol === company.symbol);
    return `<tr><td><strong>${escapeHtml(company.symbol)}</strong></td><td>${escapeHtml(company.name)}</td><td>${escapeHtml(company.sector || "—")}</td><td>${escapeHtml(company.subsector || "—")}</td><td><span class="status ${scored ? "good" : "neutral"}">${scored ? "Scored" : "Queued"}</span></td></tr>`;
  }).join("");
  return `<section class="content-section">
    <div class="directory-banner">${icons.alert}<div><strong>Directory view only</strong><p>Per the current project scope, only the four Industrial companies are scored. The rest are listed without quotes or invented fundamentals.</p></div></div>
    <form class="filter-row" id="directory-filter">
      <label class="search-box">${icons.search}<input name="query" value="${escapeHtml(state.directoryQuery)}" placeholder="Search company or ticker" /></label>
      <select name="sector" aria-label="Filter by sector">${sectors.map((sector) => `<option ${sector === state.directorySector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}</select>
      <button class="secondary" type="submit">Apply</button>
      <span class="result-count">${filtered.length} companies</span>
    </form>
    <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Company</th><th>Sector</th><th>Subsector</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="5">No companies match this filter.</td></tr>'}</tbody></table></div>
    ${filtered.length > 80 ? '<p class="table-foot">Showing the first 80 matches. Refine your search to narrow the directory.</p>' : ""}
  </section>`;
}

function renderValuation() {
  const company = companyBySymbol();
  const valuation = calculateValuation(company, state.sentiment);
  const modelMeta = [
    ["dcf", "DCF", "Cash the business could generate", "5-year forecast + terminal value"],
    ["graham", "Graham", "Earnings, growth and PH bond yield", "EPS × (8.5 + 2g) × 6.0% / 7.052%"],
    ["multiples", "Multiples", "Earnings at a peer-style P/E", "EPS × adjusted peer P/E"],
    ["ddm", "Dividend", "Value of a growing dividend stream", "Next dividend / (return − growth)"],
  ];
  const cards = modelMeta.map(([key, label, explanation, formula]) => {
    const model = valuation.models[key];
    return `<article class="model-card ${model ? "" : "disabled"}">
      <div class="model-top"><span>${label}</span><span class="model-weight">${Math.round((company.valuation.weights[key] || 0) * 100)}% weight</span></div>
      <strong>${model ? peso(model.perShare) : "Not applicable"}</strong>
      <p>${explanation}</p><small>${formula}</small>
    </article>`;
  }).join("");
  const modelValues = Object.values(valuation.models).filter(Boolean).map((model) => model.perShare);
  const range = Math.max(...modelValues) - Math.min(...modelValues);
  const rangePosition = range ? ((valuation.blended - valuation.low) / range) * 100 : 50;
  const dcf = valuation.models.dcf;
  const action = `<label class="select-label"><span>Company</span><select data-company-select>${companyOptions()}</select></label>`;
  return `${pageHeading("Valuation lab", "Estimate value, then challenge it.", "Bear, base, and bull cases alter assumptions—not reported filing data.", action)}
    <section class="valuation-hero">
      <div class="valuation-main">
        <div class="sentiment-switch" role="group" aria-label="Market sentiment">${Object.entries(SENTIMENTS).map(([key, item]) => `<button data-sentiment="${key}" class="${state.sentiment === key ? "active" : ""}">${item.label}</button>`).join("")}</div>
        <p class="eyebrow">BLENDED INTRINSIC VALUE</p>
        <div class="big-value">${peso(valuation.blended)}</div>
        <p class="muted">per share · ${SENTIMENTS[state.sentiment].label} case · filing-based estimate</p>
        <div class="range-line"><span style="left:${Math.max(2, Math.min(98, rangePosition))}%"></span></div>
        <div class="range-labels"><span><small>MODEL LOW</small>${peso(valuation.low)}</span><span><small>MODEL HIGH</small>${peso(valuation.high)}</span></div>
      </div>
      <aside class="valuation-warning"><span>${icons.alert}</span><div><strong>No current-price comparison</strong><p>This app does not publish a market quote. Treat the estimate as a model output, not an upside or downside signal.</p></div></aside>
    </section>
    <section class="content-section">
      <div class="section-title"><div><p class="eyebrow">Model mix</p><h2>Four ways to frame value</h2></div><a class="text-link" href="${SOURCE_LINKS.valuation.href}" target="_blank">Open source workbook ${icons.arrow}</a></div>
      <div class="model-grid">${cards}</div>
    </section>
    <section class="assumption-panel">
      <div><p class="eyebrow">PHILIPPINE ADJUSTMENT</p><h2>Local rates replace the U.S. AAA yield.</h2><p>${PHILIPPINE_ASSUMPTIONS.note}</p><a href="${PHILIPPINE_ASSUMPTIONS.sourceUrl}" target="_blank" rel="noreferrer">${PHILIPPINE_ASSUMPTIONS.sourceLabel} ${icons.arrow}</a></div>
      <dl class="assumption-grid">
        <div><dt>Current long-bond proxy</dt><dd>${percent(PHILIPPINE_ASSUMPTIONS.riskFreeRate, 3)}</dd></div>
        <div><dt>Through-cycle normalizer</dt><dd>${percent(PHILIPPINE_ASSUMPTIONS.grahamBaselineYield, 1)}</dd></div>
        <div><dt>DCF discount rate</dt><dd>${percent(dcf.discountRate, 1)}</dd></div>
        <div><dt>DCF terminal growth</dt><dd>${percent(dcf.terminalGrowth, 1)}</dd></div>
        <div><dt>Normalized annual FCF</dt><dd>${compactPeso(dcf.normalizedFcf)}</dd></div>
        <div><dt>Adjusted peer P/E</dt><dd>${valuation.models.multiples.peerPe.toFixed(1)}×</dd></div>
      </dl>
    </section>`;
}

function renderHealth() {
  const company = companyBySymbol();
  const health = getHealthMetrics(company, state.risk);
  const metrics = health[state.healthTab];
  const available = metrics.filter((metric) => metric.status !== "unavailable");
  const passCount = available.filter((metric) => metric.status === "pass").length;
  const action = `<label class="select-label"><span>Company</span><select data-company-select>${companyOptions()}</select></label>`;
  const cards = metrics.map((metric) => {
    const progress = metric.direction === "context" ? 70 : Math.max(5, Math.min(100, metric.score * 100));
    const statusLabel = { pass: "Clears screen", watch: "Needs a look", unavailable: "Not reported", context: "Context" }[metric.status];
    const icon = metric.status === "pass" ? icons.check : icons.alert;
    return `<article class="metric-card ${metric.status}">
      <div class="metric-heading"><span class="metric-icon">${icon}</span><div><strong>${metric.label}</strong><p>${metric.description}</p></div><span class="status ${metric.status === "pass" ? "good" : metric.status === "watch" ? "watch" : "neutral"}">${statusLabel}</span></div>
      <div class="metric-values"><div><small>ACTUAL · FY2025</small><strong>${formatMetric(metric)}</strong></div><div><small>YOUR LEVEL ${state.risk} SCREEN</small><strong>${thresholdText(metric)}</strong></div></div>
      <div class="metric-track"><span style="width:${progress}%"></span></div>
    </article>`;
  }).join("");
  return `${pageHeading("Financial health", "See the number—and the bar.", "Thresholds adapt to your risk comfort while reported values stay fixed.", action)}
    <section class="health-summary">
      <div class="health-score"><span>${passCount}</span><p><strong>of ${available.length}</strong> available checks cleared</p></div>
      <div><p class="eyebrow">YOUR LENS</p><h2>Level ${state.risk} · ${RISK_PROFILES[state.risk].label}</h2><p>${RISK_PROFILES[state.risk].tone}. These are screening guardrails, not universal accounting rules.</p></div>
      <button class="secondary" data-change-risk>Adjust profile</button>
    </section>
    <section class="content-section">
      <div class="section-title"><div class="tab-switch" role="group" aria-label="Financial statement view"><button data-health-tab="pnl" class="${state.healthTab === "pnl" ? "active" : ""}">Profit & loss</button><button data-health-tab="balance" class="${state.healthTab === "balance" ? "active" : ""}">Balance sheet</button></div><a class="text-link" href="${company.source.href}" target="_blank">Open company filing ${icons.arrow}</a></div>
      <div class="metric-grid">${cards}</div>
      <div class="method-note">${icons.alert}<p><strong>Interpret carefully:</strong> Grouping and line-item labels differ by issuer. “Not reported” remains neutral, while treasury stock is context—not an automatic pass or fail. <a href="${SOURCE_LINKS.health.href}" target="_blank">View supplied methodology</a>.</p></div>
    </section>`;
}

function renderNews() {
  const items = FILING_NEWS.filter((item) => state.newsFilter === "ALL" || item.symbol === state.newsFilter);
  const cards = items.map((item, index) => {
    const company = item.symbol === "ALL" ? null : companyBySymbol(item.symbol);
    return `<article class="news-card ${index === 0 ? "featured" : ""}">
      <div class="news-meta"><span class="tag">${item.tag}</span><span>${item.date}</span></div>
      <h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.summary)}</p>
      <div class="news-source"><span class="ticker-logo small" style="--company:${company?.color || "#375f53"}">${item.symbol === "ALL" ? "PH" : item.symbol.slice(0, 2)}</span><span><strong>${item.scope} briefing</strong><small>${company ? company.shortName : "Industrial sector"}</small></span></div>
    </article>`;
  }).join("");
  const action = `<label class="select-label"><span>Show</span><select data-news-filter><option value="ALL">All briefings</option>${companyOptions(state.newsFilter)}</select></label>`;
  return `${pageHeading("Briefings", "What changed—and why it matters.", "Plain-language briefs derived from the supplied filings and valuation context.", action)}
    <div class="demo-banner"><span class="live-dot amber"></span><p><strong>Demo briefing feed</strong> · These are not live news articles. A production launch would need a properly licensed news source.</p></div>
    <section class="news-grid">${cards}</section>`;
}

function allocationRows() {
  const totals = INDUSTRIAL_COMPANIES.map((company) => {
    const lots = state.lots.filter((lot) => lot.symbol === company.symbol);
    return { company, total: portfolioCostBasis(lots) };
  }).filter((item) => item.total > 0);
  const grandTotal = totals.reduce((sum, item) => sum + item.total, 0);
  return { totals, grandTotal };
}

function renderPortfolio() {
  const { totals, grandTotal } = allocationRows();
  const lots = state.lots.map((lot) => {
    const company = companyBySymbol(lot.symbol);
    const cost = Number(lot.quantity) * Number(lot.purchasePrice);
    return `<article class="lot-row">
      <div class="company-cell"><span class="ticker-logo" style="--company:${company.color}">${company.symbol.slice(0, 2)}</span><span><strong>${company.symbol}</strong><small>${company.shortName}</small></span></div>
      <div><small>QUANTITY</small><strong>${Number(lot.quantity).toLocaleString("en-PH")}</strong></div>
      <div><small>PURCHASE PRICE</small><strong>${peso(Number(lot.purchasePrice))}</strong></div>
      <div><small>COST BASIS</small><strong>${peso(cost, 0)}</strong></div>
      <div><small>CURRENT VALUE / P&amp;L</small><strong class="muted-value">Not calculated</strong></div>
      <button class="icon-button danger" data-remove-lot="${lot.id}" aria-label="Remove lot">${icons.trash}</button>
    </article>`;
  }).join("");
  const allocation = totals.map(({ company, total }) => `<div class="allocation-row"><div><span style="--company:${company.color}"></span><strong>${company.symbol}</strong></div><div class="allocation-bar"><span style="width:${(total / grandTotal) * 100}%;--company:${company.color}"></span></div><strong>${((total / grandTotal) * 100).toFixed(1)}%</strong></div>`).join("");
  return `${pageHeading("Portfolio organizer", "Remember what you bought.", "Track quantities and purchase cost without publishing or guessing a current price.")}
    <section class="portfolio-overview">
      <div class="cost-card"><p class="eyebrow">TOTAL INVESTED AT COST</p><strong>${peso(grandTotal, 0)}</strong><p>${state.lots.length} lot${state.lots.length === 1 ? "" : "s"} · saved in this browser</p></div>
      <div class="allocation-card"><div class="section-title compact"><h2>Cost allocation</h2><span>${totals.length} holding${totals.length === 1 ? "" : "s"}</span></div>${allocation || '<p class="empty-small">Add your first lot to see cost allocation.</p>'}</div>
    </section>
    <section class="content-section portfolio-section">
      <div class="section-title"><div><p class="eyebrow">Your lots</p><h2>Purchase organizer</h2></div><button class="primary" data-open-lot-form>${icons.plus} Add a stock</button></div>
      <form id="lot-form" class="lot-form ${state.showLotForm ? "open" : ""}">
        <label><span>Stock</span><select name="symbol">${companyOptions()}</select></label>
        <label><span>Quantity</span><input name="quantity" type="number" min="0.0001" step="any" placeholder="e.g. 100" required /></label>
        <label><span>Purchase price (PHP)</span><input name="purchasePrice" type="number" min="0.01" step="0.01" placeholder="e.g. 32.50" required /></label>
        <button class="primary" type="submit">Save lot</button>
      </form>
      <div class="lot-list">${lots || `<div class="empty-state">${icons.portfolio}<h2>No stocks added yet</h2><p>Add a quantity and purchase price to organize your cost basis.</p></div>`}</div>
      <div class="method-note">${icons.alert}<p><strong>Why P&amp;L is blank:</strong> Profit or loss requires a current market price. This no-cost mockup intentionally avoids unlicensed or stale quotes.</p></div>
    </section>`;
}

function renderBrief() {
  const company = companyBySymbol();
  const brief = buildSmartBrief(company, state.risk, state.sentiment, state.lots);
  const action = `<label class="select-label"><span>Company</span><select data-company-select>${companyOptions()}</select></label>`;
  return `${pageHeading("Smart Brief", "A clear read in under a minute.", "A transparent rules-based summary—written for people, not finance terminals.", action)}
    <section class="brief-shell">
      <div class="brief-top">
        <div class="smart-badge">${icons.brief}<span><strong>LOCAL SMART BRIEF</strong><small>No API fees · Runs in your browser</small></span></div>
        <button class="secondary compact-button" data-copy-brief>${icons.copy} Copy summary</button>
      </div>
      <div class="brief-company"><span class="ticker-logo large" style="--company:${company.color}">${company.symbol.slice(0, 2)}</span><div><p>${company.subsector}</p><h1>${company.name}</h1></div><div class="brief-score"><strong>${brief.score}</strong><span>/100<br />screen score</span></div></div>
      <div class="brief-headline"><span></span><p>For your level ${state.risk} profile</p><h2>${brief.headline}</h2></div>
      <div class="brief-copy">${brief.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}</div>
      <div class="brief-signals">
        <div><small>WHAT CLEARS YOUR SCREEN</small><div>${brief.passLabels.length ? brief.passLabels.map((label) => `<span class="signal-pass">${icons.check}${label}</span>`).join("") : '<span class="signal-neutral">No leading pass available</span>'}</div></div>
        <div><small>WHAT TO INVESTIGATE</small><div>${brief.watchLabels.length ? brief.watchLabels.map((label) => `<span class="signal-watch">${icons.alert}${label}</span>`).join("") : '<span class="signal-neutral">No leading watch available</span>'}</div></div>
      </div>
      <div class="brief-controls"><span>Valuation lens:</span>${Object.entries(SENTIMENTS).map(([key, item]) => `<button data-sentiment="${key}" class="${state.sentiment === key ? "active" : ""}">${item.label}</button>`).join("")}</div>
    </section>
    <div class="rules-note">${icons.brief}<div><strong>Why this has no extra cost</strong><p>The brief selects facts and sentences from deterministic rules in the app. It sends nothing to OpenAI or any other AI provider and makes no hidden recommendation.</p></div></div>`;
}

function persistLots() {
  localStorage.setItem("gabay-portfolio", JSON.stringify(state.lots));
}

function navigate(page) {
  state.page = page;
  window.history.replaceState(null, "", `#${page}`);
  renderShell();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("button, a");
  if (!target) return;
  if (target.dataset.nav) {
    event.preventDefault();
    navigate(target.dataset.nav);
  } else if (target.dataset.riskPick) {
    state.pendingRisk = Number(target.dataset.riskPick);
    renderOnboarding();
  } else if (target.hasAttribute("data-risk-start")) {
    state.risk = state.pendingRisk;
    localStorage.setItem("gabay-risk", String(state.risk));
    renderShell();
  } else if (target.hasAttribute("data-change-risk")) {
    state.pendingRisk = state.risk;
    state.risk = null;
    renderOnboarding();
  } else if (target.dataset.rankingScope) {
    state.rankingScope = target.dataset.rankingScope;
    renderShell();
  } else if (target.dataset.openCompany) {
    state.selectedSymbol = target.dataset.openCompany;
    navigate("valuation");
  } else if (target.dataset.sentiment) {
    state.sentiment = target.dataset.sentiment;
    renderShell();
  } else if (target.dataset.healthTab) {
    state.healthTab = target.dataset.healthTab;
    renderShell();
  } else if (target.hasAttribute("data-open-lot-form")) {
    state.showLotForm = !state.showLotForm;
    renderShell();
  } else if (target.dataset.removeLot) {
    state.lots = state.lots.filter((lot) => lot.id !== target.dataset.removeLot);
    persistLots();
    renderShell();
    showToast("Lot removed");
  } else if (target.hasAttribute("data-copy-brief")) {
    const company = companyBySymbol();
    const brief = buildSmartBrief(company, state.risk, state.sentiment, state.lots);
    const text = `${company.name}\n${brief.headline}\n\n${brief.paragraphs.join("\n\n")}\n\nEducational filing-based estimate; not investment advice.`;
    try {
      await navigator.clipboard.writeText(text);
      showToast("Summary copied");
    } catch {
      showToast("Copy is unavailable in this browser");
    }
  }
});

document.addEventListener("change", (event) => {
  if (event.target.matches("[data-company-select]")) {
    state.selectedSymbol = event.target.value;
    renderShell();
  } else if (event.target.matches("[data-news-filter]")) {
    state.newsFilter = event.target.value;
    renderShell();
  }
});

document.addEventListener("submit", (event) => {
  if (event.target.id === "lot-form") {
    event.preventDefault();
    const form = new FormData(event.target);
    const quantity = Number(form.get("quantity"));
    const purchasePrice = Number(form.get("purchasePrice"));
    if (!(quantity > 0) || !(purchasePrice > 0)) return;
    state.lots.push({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      symbol: form.get("symbol"),
      quantity,
      purchasePrice,
    });
    state.showLotForm = false;
    persistLots();
    renderShell();
    showToast("Lot saved locally");
  } else if (event.target.id === "directory-filter") {
    event.preventDefault();
    const form = new FormData(event.target);
    state.directoryQuery = String(form.get("query") || "").trim();
    state.directorySector = String(form.get("sector") || "All sectors");
    renderShell();
  }
});

async function init() {
  try {
    const response = await fetch("./src/data/listed-companies.json");
    if (!response.ok) throw new Error("Directory unavailable");
    state.listedCompanies = await response.json();
  } catch {
    state.listedCompanies = [];
  }
  if (state.risk) renderShell();
  else renderOnboarding();
}

init();
