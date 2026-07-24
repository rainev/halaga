"""The personalized insights feed — the fan-in at read time.

Isolation is structural: every row is gated by `holdings.user_id = :user_id`, so
the query can only ever return insights for companies the requesting user holds
(covering both direct and thematic links, since a thematic macro article creates
an insight for the held company itself). There is no surface that returns another
user's data.
"""

from typing import Any

from ..db import query

_FEED_SQL = """
  SELECT i.id, i.company_id, c.ticker, c.name, c.sector,
         i.summary, i.possible_impact, i.direction, i.confidence, i.sources,
         COALESCE(s.link_type, 'direct') AS link_type,
         n.title AS article_title, n.url AS article_url,
         n.published_at, i.created_at
  FROM insights i
  JOIN holdings   h ON h.company_id = i.company_id AND h.user_id = %s
  JOIN companies  c ON c.id = i.company_id
  JOIN news_items n ON n.id = i.news_item_id
  LEFT JOIN article_stocks s
         ON s.news_item_id = i.news_item_id AND s.company_id = i.company_id
  ORDER BY n.published_at DESC NULLS LAST, i.created_at DESC
  LIMIT %s
"""


def feed_for_user(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    return query(_FEED_SQL, (user_id, limit))
