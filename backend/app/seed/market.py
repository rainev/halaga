"""Seed the default PH market assumptions row. Idempotent."""

from ..db import pool, query_one
from ..valuation.assumptions import PH


def main() -> None:
    pool.open()
    row = query_one(
        """
        INSERT INTO market_assumptions (
            key, risk_free_rate, equity_risk_premium, graham_current_yield,
            graham_normalizing_yield, graham_base_pe, default_perpetual_growth
        )
        VALUES ('PH', %s, %s, %s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE
          SET risk_free_rate = EXCLUDED.risk_free_rate,
              equity_risk_premium = EXCLUDED.equity_risk_premium,
              graham_current_yield = EXCLUDED.graham_current_yield,
              graham_normalizing_yield = EXCLUDED.graham_normalizing_yield,
              graham_base_pe = EXCLUDED.graham_base_pe,
              default_perpetual_growth = EXCLUDED.default_perpetual_growth,
              updated_at = now()
        RETURNING key
        """,
        (
            PH.risk_free_rate,
            PH.equity_risk_premium,
            PH.graham_current_yield,
            PH.graham_normalizing_yield,
            PH.graham_base_pe,
            PH.default_perpetual_growth,
        ),
    )
    print(f"Seeded market assumptions: {row['key']}")
    pool.close()


if __name__ == "__main__":
    main()
