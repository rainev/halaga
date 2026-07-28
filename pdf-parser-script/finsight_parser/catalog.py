from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class CatalogError(ValueError):
    """Raised when a parser configuration file is internally inconsistent."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError(f"Configuration root must be an object: {path}")
    return data


def load_line_item_catalog(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise CatalogError(f"Line-item catalog must contain a non-empty items list: {path}")

    keys: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CatalogError(f"Catalog item {index} must be an object")
        key = str(item.get("key", "")).strip()
        statement = str(item.get("statement", "")).strip()
        aliases = item.get("aliases")
        if not key or not statement or not isinstance(aliases, list) or not aliases:
            raise CatalogError(f"Catalog item {index} requires key, statement, and aliases")
        if key in keys:
            raise CatalogError(f"Duplicate line-item key: {key}")
        keys.add(key)
        normalized.append(
            {
                "key": key,
                "statement": statement,
                "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
                "tags": [str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()],
            }
        )
    return normalized


def load_wave1_requirements(path: Path, catalog_keys: set[str]) -> dict[str, Any]:
    data = load_json(path)
    templates = data.get("templates")
    companies = data.get("companies")
    subsectors = data.get("subsectors", {})
    issuer_directory = data.get("issuer_directory", {})
    if not isinstance(templates, dict) or not isinstance(companies, dict):
        raise CatalogError("Wave 1 requirements need templates and companies objects")
    if not isinstance(subsectors, dict) or not isinstance(issuer_directory, dict):
        raise CatalogError("Subsectors and issuer_directory must be objects")

    resolved_templates: dict[str, dict[str, list[str]]] = {}
    resolving: set[str] = set()

    def resolve_template(name: str) -> dict[str, list[str]]:
        if name in resolved_templates:
            return resolved_templates[name]
        if name in resolving:
            raise CatalogError(f"Template inheritance cycle at {name}")
        raw = templates.get(name)
        if not isinstance(raw, dict):
            raise CatalogError(f"Unknown Wave 1 template: {name}")
        resolving.add(name)
        required: list[str] = []
        recommended: list[str] = []
        for parent in raw.get("extends", []):
            inherited = resolve_template(str(parent))
            required.extend(inherited["required"])
            recommended.extend(inherited["recommended"])
        required.extend(str(key) for key in raw.get("required", []))
        recommended.extend(str(key) for key in raw.get("recommended", []))
        resolving.remove(name)
        result = {
            "required": list(dict.fromkeys(required)),
            "recommended": list(dict.fromkeys(recommended)),
        }
        resolved_templates[name] = result
        return result

    for template_name in templates:
        resolve_template(template_name)

    def resolve_profile(
        symbol: str,
        raw: dict[str, Any],
        *,
        default_name: str | None = None,
    ) -> dict[str, Any]:
        required: list[str] = []
        recommended: list[str] = []
        template_names: list[str] = []
        subsector_key = str(raw.get("subsector", "")).strip()
        subsector = subsectors.get(subsector_key) if subsector_key else None
        if subsector_key and not isinstance(subsector, dict):
            raise CatalogError(f"Unknown PSE subsector: {subsector_key}")
        explicit_templates = [str(item) for item in raw.get("templates", [])]
        if explicit_templates:
            # A company-level template is a business-model override (for example,
            # a REIT within Property or an upstream producer within Oil).
            template_names.extend(explicit_templates)
        elif subsector:
            template_names.extend(str(item) for item in subsector.get("templates", []))
        template_names = list(dict.fromkeys(template_names))
        for template_name in template_names:
            template = resolve_template(template_name)
            required.extend(template["required"])
            recommended.extend(template["recommended"])
        if subsector:
            required.extend(str(key) for key in subsector.get("required", []))
            recommended.extend(str(key) for key in subsector.get("recommended", []))
        required.extend(str(key) for key in raw.get("required", []))
        recommended.extend(str(key) for key in raw.get("recommended", []))
        required = list(dict.fromkeys(required))
        recommended = [key for key in dict.fromkeys(recommended) if key not in required]
        referenced_keys.update(required)
        referenced_keys.update(recommended)
        primary_model = str(
            raw.get(
                "primary_model",
                subsector.get("primary_model", "manual_review")
                if subsector
                else "manual_review",
            )
        )
        archetype = str(
            raw.get(
                "archetype",
                subsector.get("archetype", "unknown") if subsector else "unknown",
            )
        )
        return {
            "symbol": symbol,
            "name": str(raw.get("name", default_name or symbol)),
            "aliases": [
                str(alias).strip()
                for alias in raw.get("aliases", [])
                if str(alias).strip()
            ],
            "auto_detect": bool(raw.get("auto_detect", True)),
            "subsector": subsector_key or None,
            "archetype": archetype,
            "primary_model": primary_model,
            "supporting_models": [
                str(model)
                for model in (
                    raw.get(
                        "supporting_models",
                        subsector.get("supporting_models", []) if subsector else [],
                    )
                )
            ],
            "templates": template_names,
            "required": required,
            "recommended": recommended,
        }

    referenced_keys: set[str] = set()
    resolved_companies: dict[str, dict[str, Any]] = {}
    for symbol, raw in companies.items():
        if not isinstance(raw, dict):
            raise CatalogError(f"Company definition must be an object: {symbol}")
        normalized_symbol = str(symbol).upper()
        resolved_companies[normalized_symbol] = resolve_profile(
            normalized_symbol,
            raw,
        )

    resolved_issuers: dict[str, dict[str, Any]] = {}
    for symbol, raw in issuer_directory.items():
        if not isinstance(raw, dict):
            raise CatalogError(f"Issuer-directory definition must be an object: {symbol}")
        normalized_symbol = str(symbol).upper()
        resolved_issuers[normalized_symbol] = resolve_profile(
            normalized_symbol,
            raw,
        )

    default_profile_raw = data.get(
        "default_profile",
        {
            "name": "Unclassified PSE issuer",
            "archetype": "unclassified",
            "primary_model": "manual_review",
            "templates": ["common_equity"],
        },
    )
    if not isinstance(default_profile_raw, dict):
        raise CatalogError("default_profile must be an object")
    default_profile = resolve_profile("UNKNOWN", default_profile_raw)

    unknown = sorted(referenced_keys - catalog_keys)
    if unknown:
        raise CatalogError(f"Wave 1 requirements reference unknown catalog keys: {unknown}")

    return {
        "schema_version": str(data.get("schema_version", "1.0")),
        "templates": resolved_templates,
        "subsectors": subsectors,
        "companies": resolved_companies,
        "issuer_directory": resolved_issuers,
        "default_profile": default_profile,
    }


def requirements_for_symbol(requirements: dict[str, Any], symbol: str) -> dict[str, Any]:
    normalized = symbol.strip().upper()
    company = requirements["companies"].get(normalized)
    if company is None:
        company = requirements.get("issuer_directory", {}).get(normalized)
    if company is None:
        available = sorted(
            set(requirements["companies"])
            | set(requirements.get("issuer_directory", {}))
        )
        raise CatalogError(
            f"{normalized} is not in the configured PSE issuer directory. "
            f"Available: {', '.join(available)}"
        )
    return company


def _normalize_identity(value: str) -> str:
    value = value.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def select_document_requirements(
    requirements: dict[str, Any],
    *,
    symbol: str | None = None,
    filename: str = "",
    document_text: str = "",
) -> dict[str, Any]:
    """Resolve issuer and PSE subsector without guessing ambiguous identities."""
    if symbol:
        company = requirements_for_symbol(requirements, symbol)
        return {
            "status": "resolved",
            "method": "explicit_symbol",
            "confidence": 1.0,
            "review_required": False,
            "matched_alias": symbol.strip().upper(),
            "company": company,
        }

    haystack = _normalize_identity(f"{filename} {document_text[:50000]}")
    normalized_filename_tokens = set(_normalize_identity(filename).split())
    candidates: list[tuple[int, int, int, str, str, dict[str, Any]]] = []
    profiles = {
        **requirements.get("issuer_directory", {}),
        **requirements.get("companies", {}),
    }
    ticker_matches = [
        profile
        for candidate_symbol, profile in profiles.items()
        if len(candidate_symbol) >= 2
        and profile.get("auto_detect", True)
        and candidate_symbol.lower() in normalized_filename_tokens
    ]
    if len(ticker_matches) == 1:
        return {
            "status": "resolved",
            "method": "filename_ticker",
            "confidence": 0.98,
            "review_required": False,
            "matched_alias": ticker_matches[0]["symbol"],
            "company": ticker_matches[0],
        }
    for candidate_symbol, profile in profiles.items():
        if not profile.get("auto_detect", True):
            continue
        aliases = [profile["name"], *profile.get("aliases", [])]
        for alias in aliases:
            normalized_alias = _normalize_identity(alias)
            position = haystack.find(normalized_alias)
            if len(normalized_alias) < 5 or position < 0:
                continue
            candidates.append(
                (
                    position,
                    -len(normalized_alias.split()),
                    -len(normalized_alias),
                    candidate_symbol,
                    alias,
                    profile,
                )
            )

    if candidates:
        candidates.sort()
        best = candidates[0]
        tied_symbols = {
            item[3]
            for item in candidates
            if item[:3] == best[:3]
        }
        if len(tied_symbols) == 1:
            return {
                "status": "resolved",
                "method": "issuer_name_or_alias",
                "confidence": 0.95,
                "review_required": False,
                "matched_alias": best[4],
                "company": best[5],
            }
        ambiguity = sorted(tied_symbols)
    else:
        ambiguity = []

    fallback = dict(requirements["default_profile"])
    fallback["name"] = "Unclassified issuer"
    return {
        "status": "ambiguous" if ambiguity else "unresolved",
        "method": "safe_common_equity_fallback",
        "confidence": 0.0,
        "review_required": True,
        "matched_alias": None,
        "candidate_symbols": ambiguity,
        "company": fallback,
    }
