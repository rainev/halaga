# Gabay Markets

Gabay Markets is a responsive, dependency-free mockup for beginner Philippine retail investors. It evaluates four Industrial-sector companies using FY2025 filing data, Philippine-adjusted valuation inputs, and risk-sensitive financial-health screens. It intentionally omits current and historical market prices.

## Run it

Node.js 20 or newer is recommended.

```bash
npm run dev
```

Then open `http://127.0.0.1:4173`.

Run the calculation checks with:

```bash
npm test
```

## Cost and data model

- No paid API, API key, database, framework, or cloud service is required.
- The Smart Brief is a local rules-based explainer, not a generative-AI call.
- Portfolios and risk settings stay in the browser's local storage.
- News cards are filing-derived demo briefs, not a live news feed.
- Current value and portfolio P/L are intentionally not estimated without licensed/current price data.

## Sources and limitations

Financial values were transcribed from the supplied FY2025 company filings. The methodology begins with `Valuation-Models.xlsx` and `Financial Health Metrics.pdf`. The U.S. AAA-yield term in the Graham-style model is replaced by a Philippine long-government-bond proxy: a 7.052% accepted average yield at the Bureau of the Treasury's 23 June 2026 auction, paired with an explicit 6.0% through-cycle normalizer.

This is an educational mockup, not investment advice. Production use requires source-data validation, security review, proper authentication, privacy controls, and appropriately licensed feeds.
