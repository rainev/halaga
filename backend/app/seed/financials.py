"""Seed per-company filing financials for the research workbench.

Reads financials_data.json (extracted from the FinSight FY2025 dataset) and, for
each company, ensures the company row exists (upsert by ticker) then stores the
full filing + valuation snapshot in company_financials.data (JSONB). Idempotent.
"""

import json
from pathlib import Path

from ..db import pool, query
from ..services import company_service

DATA_FILE = Path(__file__).with_name("financials_data.json")


def main() -> None:
    payload = json.loads(DATA_FILE.read_text())
    companies = payload["companies"]

    pool.open()
    count = 0
    for c in companies:
        company = company_service.upsert(c["symbol"], c["name"], c.get("sector"))
        query(
            """
            INSERT INTO company_financials (company_id, period, data)
            VALUES (%s, %s, %s)
            ON CONFLICT (company_id) DO UPDATE
              SET period = EXCLUDED.period, data = EXCLUDED.data, updated_at = now()
            """,
            (company["id"], c.get("financials", {}).get("period"), json.dumps(c)),
        )
        count += 1
    print(f"Seeded financials for {count} companies from {DATA_FILE.name}")
    pool.close()


if __name__ == "__main__":
    main()
