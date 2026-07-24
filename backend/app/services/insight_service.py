"""Insight persistence. One row per (article, company), shared across users."""

import json
from typing import Any

from ..db import query, query_one


def upsert(
    news_item_id: int,
    company_id: int,
    summary: str,
    possible_impact: str,
    direction: str | None,
    confidence: float | None,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    return query_one(
        """
        INSERT INTO insights
          (news_item_id, company_id, summary, possible_impact, direction, confidence, sources)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (news_item_id, company_id) DO UPDATE
          SET summary = EXCLUDED.summary,
              possible_impact = EXCLUDED.possible_impact,
              direction = EXCLUDED.direction,
              confidence = EXCLUDED.confidence,
              sources = EXCLUDED.sources
        RETURNING *
        """,
        (news_item_id, company_id, summary, possible_impact, direction, confidence,
         json.dumps(sources)),
    )
