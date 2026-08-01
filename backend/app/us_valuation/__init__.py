"""Filing-only U.S. valuation pipeline.

This package is intentionally separate from the Philippine PDF parser and
Philippine market assumptions.  It normalizes SEC facts into a small canonical
contract, routes issuers by valuation archetype, and returns price-free
intrinsic-value ranges.
"""

from .pipeline import build_us_valuation

__all__ = ["build_us_valuation"]
