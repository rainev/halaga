"""Pure valuation engine.

Every function here is a pure calculation: numbers in, a result dict out. No DB,
no HTTP, no globals — which is what makes the models straightforward to unit-test
against the original spreadsheet. Market-wide inputs (PH risk-free rate, ERP,
Graham yields) are passed in explicitly via `assumptions.MarketAssumptions`.
"""
