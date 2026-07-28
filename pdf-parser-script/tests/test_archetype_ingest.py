from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingest_archetype_testing import (  # noqa: E402
    candidate_is_statement_safe,
    classify_document_type,
    compact_fact,
    detect_scope,
    filing_period,
    identity_matches,
)


class ArchetypeIngestTests(unittest.TestCase):
    def test_wrong_entity_in_ayala_land_folder_is_rejected(self):
        self.assertFalse(
            identity_matches(
                "ALI",
                "2025 Ayala Corporation_SEC Form 17-A.pdf",
                "AYALA CORPORATION CONSOLIDATED FINANCIAL STATEMENTS",
            )
        )
        self.assertTrue(
            identity_matches(
                "ALI",
                "ALI SEC17-A 2025.pdf",
                "AYALA LAND, INC. CONSOLIDATED FINANCIAL STATEMENTS",
            )
        )

    def test_document_type_and_parent_scope(self):
        self.assertEqual(
            classify_document_type("PLDT INC (PARENT COMPANY) 2025 AUDITED FINANCIAL STATEMENTS.pdf"),
            "annual",
        )
        self.assertEqual(
            detect_scope(
                "PLDT INC (PARENT COMPANY) 2025 AUDITED FINANCIAL STATEMENTS.pdf",
                "",
            ),
            "parent_only",
        )
        self.assertEqual(
            detect_scope(
                "2024 Audited Financial Statement - Parent.pdf",
                "INDEPENDENT AUDITOR\nSEPARATE FINANCIAL STATEMENTS\n"
                "Reference to consolidated statements in an explanatory paragraph.",
            ),
            "parent_only",
        )
        self.assertEqual(
            classify_document_type("ACP Consent Form - Q1 Summary of Exploration Report.pdf"),
            "non_financial",
        )

    def test_reviewed_hash_override_is_explicit_and_symbol_specific(self):
        overrides = {
            "abc123": {
                "expectedSymbol": "OGP",
                "reason": "Reviewed image-only filing.",
            }
        }
        self.assertTrue(identity_matches("OGP", "generic-redacted.pdf", "", "abc123", overrides))
        self.assertFalse(identity_matches("ALI", "generic-redacted.pdf", "", "abc123", overrides))

    def test_interim_cash_flow_dates_are_labeled_as_ytd_from_filing_period(self):
        document = {
            "filename": "CNPF Q2 2025.pdf",
            "sha256": "abc123",
            "document_type": "quarterly",
            "period": "Q2 2025",
            "scope": "consolidated",
        }
        fact = {
            "canonical_key": "operating_cash_flow",
            "catalog_statement": "cash_flow",
            "statement_context": "cash_flow",
            "candidate_kind": "table_row",
            "period_alignment": "exact",
            "confidence": 1.0,
            "raw_label": "Net cash from operating activities",
            "raw_text": "Net cash from operating activities 1,842 2,574",
            "values": [
                {
                    "period_hint": "June 30, 2025",
                    "period_kind": "period",
                    "reported_value": 1842,
                    "normalized_value": 1842,
                    "raw": "1,842",
                },
                {
                    "period_hint": "June 30, 2024",
                    "period_kind": "period",
                    "reported_value": 2574,
                    "normalized_value": 2574,
                    "raw": "2,574",
                },
            ],
            "source": {"page": 11, "line": 30, "document_sha256": "abc123"},
            "unit_context": {"currency": "PHP", "scale": "units", "scale_multiplier": 1},
        }
        self.assertTrue(candidate_is_statement_safe(fact, document))
        compact = compact_fact(fact, document)
        self.assertEqual(
            [(value["period"], value["kind"]) for value in compact["values"]],
            [("6M 2025 YTD", "year_to_date"), ("6M 2024 YTD", "year_to_date")],
        )

    def test_metric_rows_require_an_exact_normalized_alias(self):
        document = {
            "document_type": "annual",
            "period": "FY2025",
            "scope": "issuer_reported",
        }
        fact = {
            "catalog_statement": "metric",
            "statement_context": "balance_sheet",
            "candidate_kind": "table_row",
            "period_alignment": "exact",
            "confidence": 1.0,
            "raw_label": "Other reserves",
            "matched_alias": "ore reserves",
            "values": [
                {
                    "period_hint": "FY2025",
                    "period_kind": "annual",
                    "reported_value": 2.1,
                }
            ],
        }
        self.assertFalse(candidate_is_statement_safe(fact, document))
        fact["raw_label"] = "Ore reserves"
        self.assertTrue(candidate_is_statement_safe(fact, document))

    def test_filing_period_from_common_names(self):
        self.assertEqual(
            filing_period(
                "MSRD_AREIT, Inc._SEC Form 17-A_14April2026.pdf",
                "annual",
            ),
            "FY2025",
        )
        self.assertEqual(
            filing_period(
                "MSRD_AREIT, Inc._SEC Form 17-Q_14November2025.pdf",
                "quarterly",
            ),
            "Q3 2025",
        )
        self.assertEqual(
            filing_period(
                "BDO Unibank, Inc. - Quarterly_17Q_March 31, 2026.pdf",
                "quarterly",
            ),
            "Q1 2026",
        )
        self.assertEqual(
            filing_period(
                "Q3 2025 Ayala Corporation_SEC Form 17-Q_13November2025.pdf",
                "quarterly",
                "The filing also compares results with Q1 and Q2.",
            ),
            "Q3 2025",
        )
        self.assertEqual(
            filing_period(
                "OGP Q2 2024 Report - SEC Form 17Q_signed.pdf",
                "quarterly",
            ),
            "Q2 2024",
        )


if __name__ == "__main__":
    unittest.main()
