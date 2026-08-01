"""SEC Companyfacts selection and canonical U.S.-GAAP normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from statistics import median
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class SelectedFact:
    field: str
    namespace: str
    concept: str
    unit: str
    value: float
    start: str | None
    end: str
    accession: str
    form: str
    filed: str
    fiscal_year: int | None
    fiscal_period: str | None
    frame: str | None
    selection_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "namespace": self.namespace,
            "concept": self.concept,
            "unit": self.unit,
            "value": self.value,
            "start": self.start,
            "end": self.end,
            "accession": self.accession,
            "form": self.form,
            "filed": self.filed,
            "fiscal_year": self.fiscal_year,
            "fiscal_period": self.fiscal_period,
            "frame": self.frame,
            "dimensions": [],
            "taxonomy_type": "standard",
            "value_status": "reported",
            "selection_reason": self.selection_reason,
        }


def load_concept_config() -> dict[str, Any]:
    path = files(__package__).joinpath("config/concept_aliases.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


class CompanyFactsNormalizer:
    def __init__(
        self,
        companyfacts: dict[str, Any],
        concept_config: dict[str, Any] | None = None,
        *,
        fiscal_year_end: str | None = None,
        as_of_date: str | None = None,
        filing_records: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        self.companyfacts = companyfacts
        self.config = concept_config or load_concept_config()
        self.namespaces = companyfacts.get("facts", {})
        self.us_gaap = self.namespaces.get("us-gaap", {})
        self.fiscal_year_end = (
            fiscal_year_end
            if fiscal_year_end
            and len(fiscal_year_end) == 4
            and fiscal_year_end.isdigit()
            else None
        )
        self.as_of_date = as_of_date
        self.filing_records = [dict(record) for record in filing_records]
        if as_of_date:
            date.fromisoformat(as_of_date)
        if not self.us_gaap:
            raise ValueError("SEC Companyfacts payload has no us-gaap facts")

    def _candidates(
        self,
        field: str,
    ) -> list[tuple[str, str, str, dict[str, Any]]]:
        definition = self.config["fields"][field]
        unit = definition["unit"]
        candidates: list[tuple[str, str, str, dict[str, Any]]] = []
        for concept_reference in definition["concepts"]:
            if ":" in concept_reference:
                namespace, concept = concept_reference.split(":", 1)
            else:
                namespace, concept = "us-gaap", concept_reference
            units = (
                self.namespaces.get(namespace, {})
                .get(concept, {})
                .get("units", {})
            )
            if unit in units and units[unit]:
                candidates.extend(
                    (namespace, concept, unit, fact)
                    for fact in units[unit]
                    if not self.as_of_date
                    or fact.get("filed", "") <= self.as_of_date
                )
        return candidates

    @staticmethod
    def _select_latest_duplicate(
        facts: Iterable[tuple[str, str, str, dict[str, Any]]],
    ) -> list[tuple[str, str, str, dict[str, Any]]]:
        chosen: dict[
            tuple[str | None, str, str],
            tuple[str, str, str, dict[str, Any]],
        ] = {}
        for namespace, concept, unit, fact in facts:
            form = fact.get("form", "")
            form_family = form[:-2] if form.endswith("/A") else form
            key = (fact.get("start"), fact["end"], form_family)
            current = chosen.get(key)
            if current is None or (
                fact.get("filed", ""),
                form.endswith("/A"),
                fact.get("accn", ""),
            ) > (
                current[3].get("filed", ""),
                current[3].get("form", "").endswith("/A"),
                current[3].get("accn", ""),
            ):
                chosen[key] = (namespace, concept, unit, fact)
        return list(chosen.values())

    def _fiscal_year_for_start(self, fiscal_start: str) -> int:
        """Label a fiscal period from the issuer's declared fiscal-year end."""
        start_year = int(fiscal_start[:4])
        if not self.fiscal_year_end:
            raise ValueError(
                "SEC submissions fiscalYearEnd is required to label reconstructed quarters"
            )
        start_month_day = fiscal_start[5:7] + fiscal_start[8:10]
        return start_year + (1 if start_month_day > self.fiscal_year_end else 0)

    @staticmethod
    def _selected(
        field: str,
        item: tuple[str, str, str, dict[str, Any]],
        reason: str,
    ) -> SelectedFact:
        namespace, concept, unit, fact = item
        return SelectedFact(
            field=field,
            namespace=namespace,
            concept=concept,
            unit=unit,
            value=float(fact["val"]),
            start=fact.get("start"),
            end=fact["end"],
            accession=fact.get("accn", ""),
            form=fact.get("form", ""),
            filed=fact.get("filed", ""),
            fiscal_year=fact.get("fy"),
            fiscal_period=fact.get("fp"),
            frame=fact.get("frame"),
            selection_reason=reason,
        )

    def annual_series(self, field: str, count: int = 5) -> list[SelectedFact]:
        candidates = [
            item
            for item in self._candidates(field)
            if item[3].get("form") in {"10-K", "10-K/A"}
            and item[3].get("fp") == "FY"
            and item[3].get("start")
            and 330 <= _days(item[3]["start"], item[3]["end"]) <= 385
        ]
        deduped = self._select_latest_duplicate(candidates)
        deduped.sort(key=lambda item: item[3]["end"])
        return [
            self._selected(
                field,
                item,
                "Latest filed 10-K fact for the annual start/end context; later comparative facts supersede duplicates.",
            )
            for item in deduped[-count:]
        ]

    def annual_at_end(self, field: str, end: str) -> SelectedFact | None:
        rows = [row for row in self.annual_series(field, 20) if row.end == end]
        return rows[-1] if rows else None

    def latest_ytd_pair(
        self,
        field: str,
        *,
        after_end: str,
    ) -> tuple[SelectedFact, SelectedFact] | None:
        candidates = [
            item
            for item in self._candidates(field)
            if item[3].get("form") in {"10-Q", "10-Q/A"}
            and item[3].get("start")
            and item[3]["end"] > after_end
            and 70 <= _days(item[3]["start"], item[3]["end"]) <= 310
        ]
        if not candidates:
            return None
        current_item = max(
            candidates,
            key=lambda item: (
                item[3]["end"],
                item[3].get("filed", ""),
                _days(item[3]["start"], item[3]["end"]),
            ),
        )
        current_days = _days(current_item[3]["start"], current_item[3]["end"])
        comparison_candidates = [
            item
            for item in self._candidates(field)
            if item[3].get("accn") == current_item[3].get("accn")
            and item[3].get("start")
            and item[3]["end"] < current_item[3]["end"]
            and abs(_days(item[3]["start"], item[3]["end"]) - current_days) <= 8
        ]
        if not comparison_candidates:
            return None
        prior_item = max(comparison_candidates, key=lambda item: item[3]["end"])
        return (
            self._selected(
                field,
                current_item,
                "Latest post-fiscal-year cumulative 10-Q fact.",
            ),
            self._selected(
                field,
                prior_item,
                "Prior-year comparable cumulative fact from the same 10-Q accession.",
            ),
        )

    def ttm_flow(self, field: str) -> dict[str, Any]:
        annual = self.annual_series(field, 1)
        if not annual:
            raise ValueError(f"Missing annual fact for {field}")
        fiscal_year = annual[-1]
        pair = self.latest_ytd_pair(field, after_end=fiscal_year.end)
        if pair is None:
            return {
                "value": fiscal_year.value,
                "period_end": fiscal_year.end,
                "method": "latest_fiscal_year",
                "sources": [fiscal_year.as_dict()],
            }
        current, prior = pair
        return {
            "value": fiscal_year.value + current.value - prior.value,
            "period_end": current.end,
            "method": "latest_fy_plus_current_ytd_minus_prior_ytd",
            "sources": [
                fiscal_year.as_dict(),
                current.as_dict(),
                prior.as_dict(),
            ],
            "current_ytd": current.as_dict(),
            "prior_ytd": prior.as_dict(),
        }

    def ttm_history(self, field: str, count: int = 4) -> list[dict[str, Any]]:
        """Build non-overlapping TTM observations from FY + YTD - prior YTD."""
        annual = self.annual_series(field, 12)
        annual_by_end = {fact.end: fact for fact in annual}
        by_accession: dict[str, list[tuple[str, str, str, dict[str, Any]]]] = {}
        for item in self._candidates(field):
            fact = item[3]
            if (
                fact.get("form") in {"10-Q", "10-Q/A"}
                and fact.get("start")
                and 70 <= _days(fact["start"], fact["end"]) <= 310
            ):
                by_accession.setdefault(fact.get("accn", ""), []).append(item)

        observations: dict[str, dict[str, Any]] = {}
        for accession_items in by_accession.values():
            current_item = max(
                accession_items,
                key=lambda item: (
                    item[3]["end"],
                    _days(item[3]["start"], item[3]["end"]),
                ),
            )
            current = current_item[3]
            current_days = _days(current["start"], current["end"])
            prior_items = [
                item
                for item in accession_items
                if item[3]["end"] < current["end"]
                and abs(_days(item[3]["start"], item[3]["end"]) - current_days) <= 8
            ]
            if not prior_items:
                continue
            prior_item = max(prior_items, key=lambda item: item[3]["end"])
            prior = prior_item[3]
            matching_fy = [
                fact
                for fact in annual_by_end.values()
                if fact.end < current["start"]
                and 0 <= (date.fromisoformat(current["start"]) - date.fromisoformat(fact.end)).days <= 8
            ]
            if not matching_fy:
                continue
            fiscal_year = max(matching_fy, key=lambda fact: fact.end)
            selected_current = self._selected(
                field,
                current_item,
                "Current cumulative interim fact used in a reconstructed TTM value.",
            )
            selected_prior = self._selected(
                field,
                prior_item,
                "Prior-year comparable cumulative fact used in a reconstructed TTM value.",
            )
            candidate = {
                "period_end": selected_current.end,
                "value": fiscal_year.value + selected_current.value - selected_prior.value,
                "method": "latest_fy_plus_current_ytd_minus_prior_ytd",
                "sources": [
                    fiscal_year.as_dict(),
                    selected_current.as_dict(),
                    selected_prior.as_dict(),
                ],
                "filed": selected_current.filed,
            }
            existing = observations.get(selected_current.end)
            if existing is None or candidate["filed"] > existing["filed"]:
                observations[selected_current.end] = candidate
        return sorted(observations.values(), key=lambda row: row["period_end"])[-count:]

    def standalone_quarters(
        self,
        field: str,
        count: int = 8,
    ) -> list[dict[str, Any]]:
        """Reconstruct stand-alone quarters from Q1/YTD/FY duration facts."""
        candidates = [
            item
            for item in self._candidates(field)
            if item[3].get("form") in {"10-K", "10-K/A", "10-Q", "10-Q/A"}
            and item[3].get("start")
            and 70 <= _days(item[3]["start"], item[3]["end"]) <= 385
        ]
        deduped = self._select_latest_duplicate(candidates)
        valid_fiscal_starts = {
            item[3]["start"]
            for item in deduped
            if (
                item[3].get("form") in {"10-K", "10-K/A"}
                and 330 <= _days(item[3]["start"], item[3]["end"]) <= 385
            )
            or (
                item[3].get("form") in {"10-Q", "10-Q/A"}
                and item[3].get("fp") == "Q1"
                and 70 <= _days(item[3]["start"], item[3]["end"]) <= 115
            )
        }
        by_start: dict[str, list[tuple[str, str, str, dict[str, Any]]]] = {}
        for item in deduped:
            if item[3]["start"] in valid_fiscal_starts:
                by_start.setdefault(item[3]["start"], []).append(item)

        quarters: dict[str, dict[str, Any]] = {}
        for fiscal_start, items in by_start.items():
            by_duration = {
                "q1": [
                    item
                    for item in items
                    if 70 <= _days(fiscal_start, item[3]["end"]) <= 115
                ],
                "q2_ytd": [
                    item
                    for item in items
                    if 150 <= _days(fiscal_start, item[3]["end"]) <= 215
                ],
                "q3_ytd": [
                    item
                    for item in items
                    if 240 <= _days(fiscal_start, item[3]["end"]) <= 310
                ],
                "fy": [
                    item
                    for item in items
                    if 330 <= _days(fiscal_start, item[3]["end"]) <= 385
                ],
            }
            selected = {
                key: (
                    max(
                        values,
                        key=lambda item: (
                            item[3]["end"],
                            item[3].get("filed", ""),
                            item[3].get("accn", ""),
                        ),
                    )
                    if values
                    else None
                )
                for key, values in by_duration.items()
            }

            def add_quarter(
                quarter: int,
                end: str,
                value: float,
                source_items: list[tuple[str, str, str, dict[str, Any]]],
                formula: str,
            ) -> None:
                row = {
                    "fiscal_start": fiscal_start,
                    "fiscal_year": self._fiscal_year_for_start(fiscal_start),
                    "fiscal_quarter": quarter,
                    "period_end": end,
                    "value": value,
                    "formula": formula,
                    "sources": [
                        self._selected(
                            field,
                            item,
                            "Source fact used to reconstruct a stand-alone quarter.",
                        ).as_dict()
                        for item in source_items
                    ],
                    "filed": max(item[3].get("filed", "") for item in source_items),
                }
                current = quarters.get(end)
                if current is None or row["filed"] > current["filed"]:
                    quarters[end] = row

            q1 = selected["q1"]
            q2_ytd = selected["q2_ytd"]
            q3_ytd = selected["q3_ytd"]
            fy = selected["fy"]
            if q1:
                add_quarter(1, q1[3]["end"], float(q1[3]["val"]), [q1], "reported Q1")
            if q1 and q2_ytd:
                add_quarter(
                    2,
                    q2_ytd[3]["end"],
                    float(q2_ytd[3]["val"]) - float(q1[3]["val"]),
                    [q2_ytd, q1],
                    "Q2 YTD - Q1",
                )
            if q2_ytd and q3_ytd:
                add_quarter(
                    3,
                    q3_ytd[3]["end"],
                    float(q3_ytd[3]["val"]) - float(q2_ytd[3]["val"]),
                    [q3_ytd, q2_ytd],
                    "Q3 YTD - Q2 YTD",
                )
            if q3_ytd and fy:
                add_quarter(
                    4,
                    fy[3]["end"],
                    float(fy[3]["val"]) - float(q3_ytd[3]["val"]),
                    [fy, q3_ytd],
                    "FY - Q3 YTD",
                )
        return sorted(quarters.values(), key=lambda row: row["period_end"])[-count:]

    def instant(
        self,
        field: str,
        *,
        end: str | None = None,
        at_or_before: str | None = None,
    ) -> SelectedFact | None:
        candidates = [
            item
            for item in self._candidates(field)
            if not item[3].get("start")
            and item[3].get("form") in {"10-K", "10-K/A", "10-Q", "10-Q/A"}
            and (end is None or item[3]["end"] == end)
            and (at_or_before is None or item[3]["end"] <= at_or_before)
        ]
        if not candidates:
            return None
        item = max(
            candidates,
            key=lambda candidate: (
                candidate[3]["end"],
                candidate[3].get("filed", ""),
                candidate[3].get("accn", ""),
            ),
        )
        return self._selected(
            field,
            item,
            "Latest filed point-in-time fact for the requested balance-sheet date.",
        )

    def operating_nwc(self, end: str) -> dict[str, Any]:
        components = {
            field: self.instant(field, end=end)
            for field in (
                "accounts_receivable",
                "inventory",
                "accounts_payable",
                "deferred_revenue_current",
            )
        }
        missing = [field for field, fact in components.items() if fact is None]
        if missing:
            raise ValueError(
                f"Operating NWC cannot be built at {end}; missing {', '.join(missing)}"
            )
        value = (
            components["accounts_receivable"].value
            + components["inventory"].value
            - components["accounts_payable"].value
            - components["deferred_revenue_current"].value
        )
        return {
            "value": value,
            "period_end": end,
            "definition": "accounts receivable + inventory - accounts payable - current deferred revenue",
            "sources": [fact.as_dict() for fact in components.values() if fact],
        }

    def normalize(
        self,
        annual_count: int = 5,
        *,
        verified_zero_bridge_fields: Mapping[str, dict[str, Any]]
        | Iterable[str] = (),
    ) -> dict[str, Any]:
        if isinstance(verified_zero_bridge_fields, Mapping):
            verified_zero_evidence = dict(verified_zero_bridge_fields)
        else:
            verified_zero_evidence = {
                field: {
                    "rationale": "Caller marked this bridge field as verified zero.",
                    "verification_version": "legacy-caller",
                }
                for field in verified_zero_bridge_fields
            }
        annual_revenue = self.annual_series("revenue", annual_count)
        if len(annual_revenue) < 3:
            raise ValueError("At least three annual revenue facts are required")
        annual_periods: list[dict[str, Any]] = []
        for revenue in annual_revenue:
            row: dict[str, Any] = {
                "period_end": revenue.end,
                "fiscal_year": int(revenue.end[:4]),
                "source_filing_fiscal_year": revenue.fiscal_year,
                "values": {},
                "sources": {},
            }
            for field in (
                "revenue",
                "operating_income",
                "pretax_income",
                "income_tax",
                "depreciation_amortization",
                "capital_expenditures",
            ):
                fact = self.annual_at_end(field, revenue.end)
                row["values"][field] = fact.value if fact else None
                row["sources"][field] = fact.as_dict() if fact else None
            pretax = row["values"]["pretax_income"]
            taxes = row["values"]["income_tax"]
            row["values"]["effective_tax_rate"] = (
                taxes / pretax if pretax and taxes is not None and pretax > 0 else None
            )
            annual_periods.append(row)

        ttm_fields = {
            field: self.ttm_flow(field)
            for field in (
                "revenue",
                "operating_income",
                "pretax_income",
                "income_tax",
                "depreciation_amortization",
                "capital_expenditures",
            )
        }
        ttm_period_ends = {
            fact["period_end"] for fact in ttm_fields.values()
        }
        ttm_methods = {fact["method"] for fact in ttm_fields.values()}
        if len(ttm_period_ends) != 1 or len(ttm_methods) != 1:
            raise ValueError(
                "TTM flow inputs do not share one period end and reconstruction basis"
            )
        ttm_end = ttm_fields["revenue"]["period_end"]
        controlling_filings = [
            record
            for record in self.filing_records
            if record.get("reportDate") == ttm_end
            and record.get("form") in {"10-Q", "10-Q/A", "10-K", "10-K/A"}
            and (
                not self.as_of_date
                or record.get("filingDate", "") <= self.as_of_date
            )
        ]
        controlling_accession = (
            max(
                controlling_filings,
                key=lambda record: (
                    record.get("filingDate", ""),
                    record.get("form", "").endswith("/A"),
                    record.get("accessionNumber", ""),
                ),
            ).get("accessionNumber")
            if controlling_filings
            else None
        )
        verified_zero_fields = {
            field
            for field, evidence in verified_zero_evidence.items()
            if evidence.get("controlled_period_end") == ttm_end
            and evidence.get("source_accession") == controlling_accession
            and (
                not self.as_of_date
                or (
                    bool(evidence.get("reviewed_on"))
                    and evidence["reviewed_on"] <= self.as_of_date
                )
            )
        }
        prior_end = ttm_fields["revenue"].get("prior_ytd", {}).get("end")
        if not prior_end:
            prior_end = annual_periods[-2]["period_end"]
        nwc_current = self.operating_nwc(ttm_end)
        nwc_prior = self.operating_nwc(prior_end)
        change_nwc = nwc_current["value"] - nwc_prior["value"]
        pretax = ttm_fields["pretax_income"]["value"]
        tax = ttm_fields["income_tax"]["value"]
        effective_tax = tax / pretax if pretax > 0 else None
        reported_fcff = (
            ttm_fields["operating_income"]["value"] * (1 - effective_tax)
            + ttm_fields["depreciation_amortization"]["value"]
            - ttm_fields["capital_expenditures"]["value"]
            - change_nwc
        )

        balance_fields = {}
        for field in (
            "cash",
            "marketable_securities_current",
            "marketable_securities_noncurrent",
            "commercial_paper",
            "current_debt",
            "noncurrent_debt",
            "finance_lease_current",
            "finance_lease_noncurrent",
            "preferred_equity",
            "noncontrolling_interests",
            "common_shares_outstanding",
            "diluted_weighted_average_shares",
            "incremental_dilutive_shares",
        ):
            if field in {
                "diluted_weighted_average_shares",
                "incremental_dilutive_shares",
            }:
                latest_diluted = self.latest_ytd_pair(
                    field,
                    after_end=annual_periods[-1]["period_end"],
                )
                fact = latest_diluted[0] if latest_diluted else self.annual_at_end(
                    field,
                    annual_periods[-1]["period_end"],
                )
            else:
                fact = self.instant(
                    field,
                    at_or_before=None
                    if field == "common_shares_outstanding"
                    else ttm_end,
                )
            balance_fields[field] = {
                "value": (
                    fact.value
                    if fact
                    else 0.0
                    if field in verified_zero_fields
                    else None
                ),
                "source": (
                    fact.as_dict()
                    if fact
                    else {
                        "value_status": "policy_verified_zero",
                        **verified_zero_evidence[field],
                    }
                    if field in verified_zero_fields
                    else None
                ),
                "state": (
                    "reported"
                    if fact
                    else "policy_verified_zero"
                    if field in verified_zero_fields
                    else "verification_stale"
                    if field in verified_zero_evidence
                    else "missing"
                ),
            }

        if balance_fields["common_shares_outstanding"]["value"] is None:
            raise ValueError("Latest common shares outstanding are required")
        incremental_dilution = (
            balance_fields["incremental_dilutive_shares"]["value"] or 0.0
        )
        incremental_dilution_missing = (
            balance_fields["incremental_dilutive_shares"]["state"] == "missing"
        )
        diluted_proxy = (
            balance_fields["common_shares_outstanding"]["value"]
            + incremental_dilution
        )
        required_bridge_fields = (
            "cash",
            "marketable_securities_current",
            "marketable_securities_noncurrent",
            "commercial_paper",
            "current_debt",
            "noncurrent_debt",
            "preferred_equity",
            "noncontrolling_interests",
            "finance_lease_current",
            "finance_lease_noncurrent",
        )
        missing_bridge = [
            field
            for field in required_bridge_fields
            if balance_fields[field]["value"] is None
        ]
        cash_and_investments = (
            balance_fields["cash"]["value"]
            + balance_fields["marketable_securities_current"]["value"]
            + balance_fields["marketable_securities_noncurrent"]["value"]
        )
        total_debt = (
            balance_fields["commercial_paper"]["value"]
            + balance_fields["current_debt"]["value"]
            + balance_fields["noncurrent_debt"]["value"]
            + (balance_fields["finance_lease_current"]["value"] or 0.0)
            + (balance_fields["finance_lease_noncurrent"]["value"] or 0.0)
        )

        tax_rates = [
            row["values"]["effective_tax_rate"]
            for row in annual_periods
            if row["values"]["effective_tax_rate"] is not None
            and 0 <= row["values"]["effective_tax_rate"] <= 0.4
        ]
        if effective_tax is not None and 0 <= effective_tax <= 0.4:
            tax_rates.append(effective_tax)

        return {
            "mapping_version": self.config["version"],
            "entity_name": self.companyfacts.get("entityName"),
            "cik": str(self.companyfacts.get("cik", "")).zfill(10),
            "currency": "USD",
            "annual": annual_periods,
            "ttm": {
                "period_end": ttm_end,
                "method": ttm_fields["revenue"]["method"],
                "values": {
                    **{field: fact["value"] for field, fact in ttm_fields.items()},
                    "effective_tax_rate": effective_tax,
                    "operating_nwc": nwc_current["value"],
                    "change_in_operating_nwc": change_nwc,
                    "reported_fcff": reported_fcff,
                },
                "sources": ttm_fields,
                "nwc_sources": {
                    "current": nwc_current,
                    "prior": nwc_prior,
                },
            },
            "balance_sheet": {
                "period_end": ttm_end,
                "values": {
                    field: item["value"] for field, item in balance_fields.items()
                },
                "sources": {
                    field: item["source"] for field, item in balance_fields.items()
                },
                "field_states": {
                    field: item["state"] for field, item in balance_fields.items()
                },
                "bridge_complete": not missing_bridge,
                "bridge_missing_fields": missing_bridge,
                "cash_and_nonoperating_investments": cash_and_investments,
                "total_interest_bearing_debt": total_debt,
                "preferred_equity": balance_fields["preferred_equity"]["value"],
                "noncontrolling_interests": balance_fields[
                    "noncontrolling_interests"
                ]["value"],
                "fully_diluted_shares_proxy": diluted_proxy,
                "dilution_proxy_state": (
                    "cover_only_incremental_dilution_missing"
                    if incremental_dilution_missing
                    else "cover_plus_reported_incremental_dilution"
                ),
                "proxy_fields": [
                    "fully_diluted_shares_proxy",
                    "operating_nwc",
                ],
            },
            "normalized": {
                "tax_rate": median(tax_rates),
                "tax_rate_method": "median of valid annual and TTM effective tax rates",
                "revenue_ttm_history": self.ttm_history("revenue", 4),
            },
            "quarterly": {
                "revenue": self.standalone_quarters("revenue", 8),
                "operating_income": self.standalone_quarters(
                    "operating_income",
                    8,
                ),
            },
            "warnings": [
                "Fully diluted shares are proxied by the latest SEC cover-page/common share count plus the latest reported incremental shares from share-based awards; a complete award roll-forward is not yet modeled.",
                *(
                    [
                        "Incremental dilutive shares were not available; the per-share denominator uses cover-page/common shares only and requires review."
                    ]
                    if incremental_dilution_missing
                    else []
                ),
                "Operating NWC uses a consistent four-account public-data definition and may omit issuer-specific operating accruals.",
                "Operating leases remain in operating expense and are not added to debt; finance leases are included when separately reported.",
            ],
        }
