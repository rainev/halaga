# U.S. valuation fixtures

Core tests use only reviewed, reduced SEC fixtures:

| Fixture | Type | Purpose |
|---|---|---|
| `aapl-companyfacts.json` | Reduced | 33 valuation-relevant concepts and their public SEC history for Apple normalization tests. |
| `aapl-submissions.json` | Reduced | Filing metadata needed for Apple fiscal-period and provenance tests. |
| `msft-companyfacts.json` | Reduced | Small Microsoft concept set used by hermetic model and period tests. |
| `msft-submissions.json` | Reduced | Small Microsoft filing identity and period fixture. |
| `msft-2026-public-safety-source-map.json` | Synthetic negative fixture | Proves raw statement amounts and private source details are rejected from public artifacts. |

Full or controlled filing captures are local-only under
`archive/local-audit/us/<ticker>/controlled-capture/`. Tests that require those
captures skip cleanly when the archive is unavailable. The normal core suite
must pass from a clean clone without any local archive.

These fixtures are excluded from the production backend Docker context.
