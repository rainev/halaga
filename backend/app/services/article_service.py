"""Persistence for an article's analysis: which stocks and sectors it affects.

These are properties of the article, shared across all users (see
docs/architecture.md). Upserts so re-analyzing an article is idempotent.
"""

from typing import Any

from ..db import query, query_one


def upsert_stock(news_item_id: int, company_id: int, link_type: str, relevance: float) -> None:
    query(
        """
        INSERT INTO article_stocks (news_item_id, company_id, link_type, relevance)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (news_item_id, company_id) DO UPDATE
          -- Keep the strongest link if an article matches both directly and
          -- thematically: a direct hit should win over a thematic one.
          SET relevance = GREATEST(article_stocks.relevance, EXCLUDED.relevance),
              link_type = CASE
                WHEN article_stocks.link_type = 'direct' OR EXCLUDED.link_type = 'direct'
                THEN 'direct' ELSE 'thematic' END
        """,
        (news_item_id, company_id, link_type, relevance),
    )


def upsert_sector(news_item_id: int, sector: str, link_type: str, relevance: float) -> None:
    query(
        """
        INSERT INTO article_sectors (news_item_id, sector, link_type, relevance)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (news_item_id, sector) DO UPDATE
          SET relevance = GREATEST(article_sectors.relevance, EXCLUDED.relevance)
        """,
        (news_item_id, sector, link_type, relevance),
    )


def stocks_for_article(news_item_id: int) -> list[dict[str, Any]]:
    """The affected companies for an article, with company context, ordered by
    relevance — the input to insight generation."""
    return query(
        """
        SELECT s.company_id, s.link_type, s.relevance,
               c.ticker, c.name, c.sector
        FROM article_stocks s
        JOIN companies c ON c.id = s.company_id
        WHERE s.news_item_id = %s
        ORDER BY s.relevance DESC
        """,
        (news_item_id,),
    )


def has_insight(news_item_id: int, company_id: int) -> bool:
    row = query_one(
        "SELECT 1 FROM insights WHERE news_item_id = %s AND company_id = %s",
        (news_item_id, company_id),
    )
    return row is not None
