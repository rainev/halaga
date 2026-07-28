from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finsight_parser.catalog import (  # noqa: E402
    load_line_item_catalog,
    load_wave1_requirements,
    select_document_requirements,
)
from finsight_parser.core import (  # noqa: E402
    _append_prose_window_facts,
    _parse_number,
    best_fact,
    build_fact_index,
    evaluate_requirements,
    extract_pdf,
    locate_statements,
    merge_fact_indexes,
    search_pages,
    validate_index,
    write_json,
)


CATALOG_PATH = ROOT / "config" / "line_item_catalog.json"
REQUIREMENTS_PATH = ROOT / "config" / "wave1_requirements.json"


def configurations():
    catalog = load_line_item_catalog(CATALOG_PATH)
    requirements = load_wave1_requirements(
        REQUIREMENTS_PATH,
        {item["key"] for item in catalog},
    )
    return catalog, requirements


class ParserTests(unittest.TestCase):
    def test_prose_windows_prefer_the_metric_appropriate_explicit_unit(self):
        common = {
            "text": (
                "Net Interest Income rose 9% to P203.1 billion. "
                "Capital Adequacy Ratio and Common Equity Tier 1 stood at 14.9%."
            ),
            "page": 1,
            "statement": None,
            "page_unit_context": {
                "currency": "PHP",
                "scale": "units",
                "scale_multiplier": 1,
                "explicit_scale": False,
            },
            "period_context": {"kind": "unknown", "labels": []},
            "extraction_method": "pdftotext",
            "document_sha256": "test-document",
        }
        facts = []
        _append_prose_window_facts(
            facts=facts,
            catalog=[
                {
                    "key": "net_interest_income",
                    "statement": "income",
                    "aliases": ["net interest income"],
                    "tags": [],
                },
                {
                    "key": "capital_adequacy_ratio",
                    "statement": "ratio",
                    "aliases": ["capital adequacy ratio"],
                    "tags": [],
                },
            ],
            **common,
        )
        by_key = {fact["canonical_key"]: fact for fact in facts}
        self.assertEqual(
            by_key["net_interest_income"]["values"][0]["normalized_value"],
            203_100_000_000,
        )
        self.assertEqual(
            by_key["capital_adequacy_ratio"]["values"][0]["normalized_value"],
            0.149,
        )

    def test_wave1_configuration_is_complete_and_extensible(self):
        catalog, requirements = configurations()
        self.assertEqual(len(requirements["companies"]), 15)
        self.assertEqual(len(requirements["subsectors"]), 23)
        self.assertGreaterEqual(len(requirements["issuer_directory"]), 60)
        self.assertEqual(
            set(requirements["companies"]),
            {
                "BDO",
                "AC",
                "ALI",
                "AREIT",
                "CNPF",
                "DNL",
                "PGOLD",
                "MER",
                "AP",
                "TEL",
                "ICT",
                "CEB",
                "OGP",
                "SCC",
                "FMETF",
            },
        )
        self.assertGreaterEqual(len(catalog), 90)
        for company in requirements["companies"].values():
            self.assertTrue(company["required"])
            self.assertTrue(company["primary_model"])

    def test_issuer_identity_routes_to_subsector_requirements(self):
        _catalog, requirements = configurations()
        route = select_document_requirements(
            requirements,
            filename="JFC 2025 Annual Report.pdf",
            document_text=(
                "Jollibee Foods Corporation\n"
                "Consolidated Financial Statements"
            ),
        )
        self.assertEqual(route["status"], "resolved")
        self.assertEqual(route["company"]["symbol"], "JFC")
        self.assertEqual(
            route["company"]["subsector"],
            "food_beverage_tobacco",
        )
        self.assertIn("revenue", route["company"]["required"])
        self.assertIn("sales_volume", route["company"]["recommended"])

    def test_company_override_replaces_broad_subsector_template(self):
        _catalog, requirements = configurations()
        route = select_document_requirements(requirements, symbol="AREIT")
        self.assertEqual(route["company"]["subsector"], "property")
        self.assertEqual(route["company"]["templates"], ["reit"])
        self.assertIn("affo", route["company"]["required"])
        self.assertNotIn("property_sales", route["company"]["required"])

    def test_unknown_issuer_uses_review_required_safe_fallback(self):
        _catalog, requirements = configurations()
        route = select_document_requirements(
            requirements,
            filename="unknown-company.pdf",
            document_text="Example Corporation Financial Statements",
        )
        self.assertEqual(route["status"], "unresolved")
        self.assertTrue(route["review_required"])
        self.assertEqual(route["company"]["symbol"], "UNKNOWN")
        self.assertEqual(route["company"]["templates"], ["common_equity"])

    def test_number_parser_handles_financial_formats(self):
        self.assertEqual(_parse_number("P =3.63")["reported_value"], 3.63)
        self.assertEqual(_parse_number("₱98,938,466")["reported_value"], 98_938_466)
        self.assertEqual(_parse_number("(1,234.50)")["reported_value"], -1234.5)
        self.assertEqual(_parse_number("24%")["normalized_value"] if "normalized_value" in _parse_number("24%") else 24, 24)
        self.assertIsNone(_parse_number("—")["reported_value"])

    def test_extract_removes_stale_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "sample.pdf"
            pdf.write_bytes(b"%PDF-placeholder")
            workdir = root / "work"
            pages = workdir / "pages"
            pages.mkdir(parents=True)
            (pages / "page-0099.txt").write_text("stale", encoding="utf-8")
            with (
                patch(
                    "finsight_parser.core.run_command",
                    return_value="first page\fsecond page\f",
                ),
                patch("finsight_parser.core._pdf_page_count", return_value=2),
                patch("finsight_parser.core.resolve_binary", return_value="pdftotext"),
            ):
                manifest = extract_pdf(pdf, workdir)
            self.assertEqual(manifest["page_count"], 2)
            self.assertFalse((pages / "page-0099.txt").exists())
            self.assertEqual(len(list(pages.glob("page-*.txt"))), 2)

    def test_locator_rejects_contents_and_balance_sheet_mentions(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            page_texts = {
                1: "TABLE OF CONTENTS\nStatements of Financial Position .... 4\n",
                2: (
                    "The attached report comprises the following:\n"
                    "1.1 Consolidated Balance Sheets as of March 31, 2026\n"
                    "Discussion of changes in balance sheet items during the quarter.\n"
                ),
                3: (
                    "ACME CORPORATION\nCONSOLIDATED STATEMENTS OF FINANCIAL POSITION\n"
                    "(Amounts in Thousands)\nTOTAL ASSETS 1,000\nTOTAL LIABILITIES 400\n"
                    "TOTAL EQUITY 600\n"
                ),
            }
            for page, text in page_texts.items():
                (pages / f"page-{page:04d}.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 3,
                    "source_sha256": "abc",
                    "source_pdf": "sample.pdf",
                    "pages": [
                        {
                            "page": page,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                        for page, text in page_texts.items()
                    ],
                },
            )
            located = locate_statements(workdir, pad=0)
            self.assertEqual([hit["page"] for hit in located["anchor_hits"]], [3])
            self.assertEqual(located["selected_pages"], [3])

    def test_fact_index_reconciles_and_satisfies_standard_opco(self):
        catalog, requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            page_texts = {
                1: (
                    "ACME CORPORATION\nCONSOLIDATED STATEMENTS OF FINANCIAL POSITION\n"
                    "(Amounts in Thousands)\n"
                    "                                      March 31, 2026  December 31, 2025\n"
                    "ASSETS\nCash and cash equivalents 100 90\n"
                    "Receivables 100 90\nInventory 50 45\n"
                    "Current Assets\nTotal current assets 400 350\n"
                    "Total assets 1,000 900\n"
                    "LIABILITIES AND EQUITY\nCurrent Liabilities\n"
                    "Accounts payable 100 90\n"
                    "Short-term loans 100 90\nTotal current liabilities 250 200\n"
                    "Noncurrent Liabilities\nLong-term debt 300 260\n"
                    "Total liabilities 400 350\nEquity\nTotal equity 600 550\n"
                    "Issued and outstanding shares 1,000 1,000\n"
                ),
                2: (
                    "ACME CORPORATION\nCONSOLIDATED STATEMENTS OF INCOME\n"
                    "(Amounts in Thousands)\n"
                    "                                      2026  2025\n"
                    "Three Months Ended March 31\n"
                    "Revenue 800 700\nOperating income 160 130\n"
                    "Depreciation and amortization 20 18\n"
                    "Interest expense 10 9\n"
                    "Income tax expense 40 30\nNet income 120 100\n"
                    "Basic earnings per share 0.12 0.10\n"
                ),
                3: (
                    "ACME CORPORATION\nCONSOLIDATED STATEMENTS OF CASH FLOWS\n"
                    "(Amounts in Thousands)\n"
                    "                                      2026  2025\n"
                    "Three Months Ended March 31\n"
                    "Net cash provided by operating activities 150 130\n"
                    "Acquisition of property plant and equipment (50) (40)\n"
                ),
            }
            for page, text in page_texts.items():
                (pages / f"page-{page:04d}.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 3,
                    "source_sha256": "abc123",
                    "source_pdf": "sample.pdf",
                    "pages": [
                        {
                            "page": page,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                        for page, text in page_texts.items()
                    ],
                },
            )
            locate_statements(workdir, pad=0)
            facts = build_fact_index(workdir, catalog)
            total_debt = best_fact(facts["facts"], "total_debt")
            self.assertIsNotNone(total_debt)
            self.assertEqual(total_debt["values"][0]["reported_value"], 400)
            revenue = best_fact(facts["facts"], "revenue")
            self.assertEqual(revenue["period_alignment"], "exact")
            self.assertEqual(revenue["values"][0]["period_hint"], "Q1 2026")
            requirement_result = evaluate_requirements(workdir, requirements, "CNPF")
            self.assertEqual(requirement_result["summary"]["required_completeness"], 1.0)
            validation = validate_index(workdir, requirement_result)
            self.assertEqual(validation["summary"]["calculation_status"], "validated")
            self.assertEqual(
                validation["summary"]["publication_status"],
                "human_review_required",
            )
            for fact in facts["facts"]:
                self.assertTrue(fact["source"]["page"])
                self.assertTrue(fact["source"]["line"])
                self.assertEqual(fact["source"]["document_sha256"], "abc123")

    def test_consolidated_framework_fields_and_derived_metrics(self):
        catalog, _requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            page_texts = {
                1: (
                    "ACME CORPORATION\n"
                    "CONSOLIDATED STATEMENTS OF FINANCIAL POSITION\n"
                    "(Amounts in Millions of Pesos)\n"
                    "                                      December 31, 2025  December 31, 2024\n"
                    "Cash and cash equivalents 200 180\n"
                    "Receivables 100 90\n"
                    "Inventory 50 45\n"
                    "Intangible assets 50 45\n"
                    "Risk-weighted assets 3,000 2,700\n"
                    "Common equity tier 1 capital 450 405\n"
                    "Total assets 5,000 4,500\n"
                    "Accounts payable 70 60\n"
                    "Total liabilities 4,500 4,050\n"
                    "Equity attributable to owners of the parent 500 450\n"
                    "Total equity 500 450\n"
                    "Issued and outstanding shares 1,000 1,000\n"
                    "Fully diluted shares outstanding 1,050 1,040\n"
                ),
                2: (
                    "ACME CORPORATION\n"
                    "CONSOLIDATED STATEMENTS OF INCOME\n"
                    "(Amounts in Millions of Pesos)\n"
                    "                                      2025  2024\n"
                    "Revenue 1,000 900\n"
                    "Gross profit 400 360\n"
                    "EBITDA 250 225\n"
                    "Operating income 200 180\n"
                    "Income before tax 160 150\n"
                    "Income tax expense 40 37.5\n"
                    "Net income 120 112.5\n"
                ),
                3: (
                    "ACME CORPORATION\n"
                    "CONSOLIDATED STATEMENTS OF CASH FLOWS\n"
                    "(Amounts in Millions of Pesos)\n"
                    "                                      2025  2024\n"
                    "Proceeds from borrowings 100 80\n"
                    "Repayment of borrowings (30) (20)\n"
                    "Net cash from operating activities 180 160\n"
                    "Capital expenditures (60) (50)\n"
                ),
                4: (
                    "OPERATING REVIEW\n"
                    "Annual recurring revenue amounted to P=420 million.\n"
                    "Customer churn rate was 2.5%.\n"
                    "Same-store sales growth reached 4.2%.\n"
                ),
            }
            for page, text in page_texts.items():
                (pages / f"page-{page:04d}.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": len(page_texts),
                    "source_sha256": "framework-fields",
                    "source_pdf": "framework-fields.pdf",
                    "pages": [
                        {
                            "page": page,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                        for page, text in page_texts.items()
                    ],
                },
            )
            locate_statements(workdir, pad=0)
            facts = build_fact_index(workdir, catalog)
            indexed = facts["facts"]

            self.assertEqual(
                best_fact(indexed, "fully_diluted_shares")["values"][0]["reported_value"],
                1050,
            )
            self.assertEqual(
                best_fact(indexed, "risk_weighted_assets")["values"][0]["reported_value"],
                3000,
            )
            self.assertEqual(
                best_fact(indexed, "net_borrowing")["values"][0]["reported_value"],
                70,
            )
            self.assertAlmostEqual(
                best_fact(indexed, "effective_tax_rate")["values"][0]["normalized_value"],
                0.25,
            )
            self.assertAlmostEqual(
                best_fact(indexed, "gross_margin")["values"][0]["normalized_value"],
                0.4,
            )
            self.assertAlmostEqual(
                best_fact(indexed, "ebit_margin")["values"][0]["normalized_value"],
                0.2,
            )
            self.assertAlmostEqual(
                best_fact(indexed, "ebitda_margin")["values"][0]["normalized_value"],
                0.25,
            )
            self.assertEqual(
                best_fact(indexed, "core_operating_working_capital")["values"][0][
                    "reported_value"
                ],
                80,
            )
            self.assertEqual(
                best_fact(indexed, "tangible_common_equity")["values"][0][
                    "reported_value"
                ],
                450,
            )
            self.assertIsNotNone(best_fact(indexed, "annual_recurring_revenue"))
            self.assertIsNotNone(best_fact(indexed, "churn_rate"))
            self.assertIsNotNone(best_fact(indexed, "same_store_sales_growth"))

    def test_three_year_statement_removes_packed_note_refs_and_maps_fiscal_years(self):
        catalog, _requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            text = (
                "AREIT, INC.\n"
                "STATEMENTS OF COMPREHENSIVE INCOME\n"
                "For each of the three years in the period ended December 31, 2025\n"
                "(All amounts in Philippine Peso)\n\n"
                "                                             Notes               2025                 2024               2023\n"
                "Revenue\n"
                "  Rental income                                5,12      8,826,839,176       7,562,124,980       5,438,890,870\n"
                "Income before income tax                                 9,540,713,213       7,320,178,539       5,031,610,964\n"
                "Net income for the year                                  9,539,219,827       7,317,064,621       5,030,544,039\n"
            )
            (pages / "page-0001.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 1,
                    "source_sha256": "areit-annual",
                    "source_pdf": "areit.pdf",
                    "pages": [
                        {
                            "page": 1,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                    ],
                },
            )
            locate_statements(workdir, pad=0)
            facts = build_fact_index(workdir, catalog)
            rental = best_fact(facts["facts"], "rental_income")
            self.assertEqual(rental["note_reference"], "5,12")
            self.assertEqual(
                [value["reported_value"] for value in rental["values"]],
                [8_826_839_176, 7_562_124_980, 5_438_890_870],
            )
            self.assertEqual(
                [value["period_hint"] for value in rental["values"]],
                ["FY2025", "FY2024", "FY2023"],
            )
            self.assertEqual(rental["period_alignment"], "exact")

    def test_interim_statement_keeps_quarter_and_ytd_columns_separate(self):
        catalog, _requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            text = (
                "AREIT, INC.\n"
                "INTERIM STATEMENTS OF COMPREHENSIVE INCOME\n"
                "(All amounts in Philippine Peso)\n\n"
                "                                                                    2025 Unaudited                       2024 Unaudited\n"
                "                                                      July 1 to        January 1 to    July 1 to            January 1 to\n"
                "                                                 September 30        September 30 September 30            September 30\n\n"
                "REVENUE\n"
                "Rental income                                    2,307,622,503       6,583,118,618 2,102,151,882          5,245,008,686\n"
                "INCOME BEFORE INCOME TAX                         2,607,734,979       6,729,802,719 1,958,115,434          4,820,840,476\n"
                "NET INCOME                                       2,607,502,469       6,728,583,872 1,957,192,190          4,818,485,174\n"
            )
            (pages / "page-0001.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 1,
                    "source_sha256": "areit-quarter",
                    "source_pdf": "areit-q3.pdf",
                    "pages": [
                        {
                            "page": 1,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                    ],
                },
            )
            locate_statements(workdir, pad=0)
            facts = build_fact_index(workdir, catalog)
            rental = best_fact(facts["facts"], "rental_income")
            self.assertEqual(
                [value["period_hint"] for value in rental["values"]],
                ["Q3 2025", "9M 2025 YTD", "Q3 2024", "9M 2024 YTD"],
            )
            self.assertEqual(
                [value["period_kind"] for value in rental["values"]],
                ["quarter", "year_to_date", "quarter", "year_to_date"],
            )
            self.assertEqual(rental["period_alignment"], "exact")

    def test_mixed_ytd_then_quarter_columns_keep_each_duration(self):
        catalog, _requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            text = (
                "PUREGOLD PRICE CLUB, INC. AND SUBSIDIARIES\n"
                "INTERIM CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME\n\n"
                "                     For the Six-Month Periods Ended       For the Three-Month Periods\n"
                "                                      June 30                    April 1 to June 30\n"
                "                        Note       2025       2024              2025       2024\n"
                "NET INCOME                         5,299      4,949             2,660      2,470\n"
            )
            (pages / "page-0001.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 1,
                    "source_sha256": "puregold-quarter",
                    "source_pdf": "puregold-q2.pdf",
                    "pages": [
                        {
                            "page": 1,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                    ],
                },
            )
            locate_statements(workdir, pad=0)
            facts = build_fact_index(workdir, catalog)
            net_income = best_fact(facts["facts"], "net_income")
            self.assertEqual(
                [value["period_hint"] for value in net_income["values"]],
                ["6M 2025 YTD", "6M 2024 YTD", "Q2 2025", "Q2 2024"],
            )
            self.assertEqual(
                [value["period_kind"] for value in net_income["values"]],
                ["year_to_date", "year_to_date", "quarter", "quarter"],
            )
            self.assertEqual(net_income["period_alignment"], "exact")

    def test_singular_consolidated_statement_headings_are_located(self):
        catalog, _requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            text = (
                "CENTURY PACIFIC FOOD, INC. AND SUBSIDIARIES\n"
                "CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME\n"
                "For the Six Months     For the Six Months\n"
                "      Ended                  Ended\n"
                "June 30, 2025        June 30, 2024\n"
                "Net Revenue          39,714,918,731  37,741,001,920\n"
                "Net Profit after Tax  3,899,089,307   3,634,155,164\n"
            )
            (pages / "page-0001.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 1,
                    "source_sha256": "cnpf-quarter",
                    "source_pdf": "cnpf-q2.pdf",
                    "pages": [
                        {
                            "page": 1,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                    ],
                },
            )
            located = locate_statements(workdir, pad=0)
            self.assertEqual(located["anchor_hits"][0]["statement"], "income")
            facts = build_fact_index(workdir, catalog)
            revenue = best_fact(facts["facts"], "revenue")
            self.assertIsNotNone(revenue)
            self.assertEqual(revenue["period_alignment"], "exact")
            self.assertEqual(
                [value["period_hint"] for value in revenue["values"]],
                ["6M 2025 YTD", "6M 2024 YTD"],
            )

    def test_ending_headers_distinguish_quarter_from_nine_month_ytd(self):
        catalog, _requirements = configurations()
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            text = (
                "BDO UNIBANK, INC. & SUBSIDIARIES\n"
                "CONDENSED STATEMENTS OF INCOME\n"
                "(Amounts in Millions of Pesos)\n\n"
                "              For the nine-month period ending                 For the quarter ending\n"
                "       September 30, 2024  September 30, 2023       September 30, 2024  September 30, 2023\n"
                "Net income       60,747              53,997                 21,225              18,746\n"
            )
            (pages / "page-0001.txt").write_text(text, encoding="utf-8")
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 1,
                    "source_sha256": "bank-quarter",
                    "source_pdf": "bank.pdf",
                    "pages": [
                        {
                            "page": 1,
                            "chars": len(text),
                            "needs_ocr": False,
                            "extraction_method": "pdftotext",
                        }
                    ],
                },
            )
            locate_statements(workdir, pad=0)
            facts = build_fact_index(workdir, catalog)
            net_income = best_fact(facts["facts"], "net_income")
            self.assertEqual(
                [value["period_hint"] for value in net_income["values"]],
                ["9M 2024 YTD", "9M 2023 YTD", "Q3 2024", "Q3 2023"],
            )

    def test_arbitrary_future_query_keeps_page_and_line(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            pages = workdir / "pages"
            pages.mkdir()
            (pages / "page-0001.txt").write_text(
                "Ordinary text\nExperimental cobalt\nrecovery rate was 91%.\n",
                encoding="utf-8",
            )
            write_json(
                workdir / "manifest.json",
                {
                    "page_count": 1,
                    "source_sha256": "abc",
                    "source_pdf": "sample.pdf",
                    "pages": [],
                },
            )
            result = search_pages(workdir, "cobalt recovery")
            self.assertEqual(result["hit_count"], 1)
            self.assertEqual(result["hits"][0]["page"], 1)
            self.assertEqual(result["hits"][0]["line"], 2)
            self.assertEqual(result["hits"][0]["line_end"], 3)
            self.assertTrue((workdir / "queries" / "cobalt-recovery.json").is_file())

    def test_corpus_merge_deduplicates_documents_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = []
            for index, document_hash in enumerate(("hash-one", "hash-two"), start=1):
                workdir = root / f"input-{index}"
                workdir.mkdir()
                write_json(
                    workdir / "facts.json",
                    {
                        "document": {
                            "path": f"report-{index}.pdf",
                            "sha256": document_hash,
                            "page_count": 10,
                        },
                        "facts": [
                            {
                                "row_id": "row-1",
                                "canonical_key": "revenue",
                                "catalog_statement": "income",
                                "raw_label": "Revenue",
                                "raw_text": f"Revenue {index}00",
                                "statement_context": "income",
                                "values": [
                                    {
                                        "reported_value": index * 100,
                                        "normalized_value": index * 100,
                                    }
                                ],
                                "unit_context": {
                                    "currency": "PHP",
                                    "scale": "units",
                                    "scale_multiplier": 1,
                                },
                                "period_context": {"kind": "annual"},
                                "confidence": 1.0,
                                "source": {
                                    "page": 2,
                                    "line": 10,
                                    "method": "pdftotext",
                                    "document_sha256": document_hash,
                                },
                            }
                        ],
                        "unmatched_numeric_rows": [],
                    },
                )
                inputs.append(workdir)
            output = root / "corpus"
            corpus = merge_fact_indexes([inputs[0], inputs[1], inputs[0]], output)
            self.assertEqual(len(corpus["documents"]), 2)
            self.assertEqual(len(corpus["facts"]), 2)
            self.assertNotEqual(corpus["facts"][0]["row_id"], corpus["facts"][1]["row_id"])
            self.assertTrue(
                all(fact["source"].get("source_workdir") for fact in corpus["facts"])
            )
            validation = validate_index(output)
            self.assertEqual(validation["summary"]["calculation_status"], "validated")


if __name__ == "__main__":
    unittest.main()
