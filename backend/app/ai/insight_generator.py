"""Generate one grounded, non-advice insight for an (article, company) pair.

Uses the OpenAI API with **structured outputs** so the result comes back as
validated fields, never free-form prose. The article text is the grounding: the
model explains the connection from what's actually in the article. Sources are
attached from the article itself (not the model), so every insight is cited.

Returns None when generation isn't possible (no API key) or the output fails the
non-advice guardrail even after one rewrite — the caller then skips that pair.
"""

import json
import logging
from typing import Any

from ..env import env
from . import guardrails, openai_client

log = logging.getLogger("uvicorn.error")

_DIRECTIONS = ("headwind", "tailwind", "mixed", "neutral")

# Structured-output contract. `direction` is informational only — NOT advice.
_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string", "description": "One sentence: what happened, plainly."},
        "possible_impact": {
            "type": "string",
            "description": "How this could relate to the company's position. Hedged "
            "(may/could/historically). No buy/sell/hold, no price prediction.",
        },
        "direction": {"type": "string", "enum": list(_DIRECTIONS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["summary", "possible_impact", "direction", "confidence"],
}

_SYSTEM = (
    "You are FinSight, an investment AWARENESS assistant for Philippine (PSE) "
    "investors. You surface information and explain POSSIBLE impact so an investor "
    "is never blindsided by news touching what they own. You are NOT a financial "
    "adviser.\n"
    "Hard rules:\n"
    "- Never tell the user to buy, sell, hold, or invest. No recommendations.\n"
    "- Never predict a price or say something 'will' happen. Use may / could / "
    "historically / tends to.\n"
    "- Ground every statement in the provided article. Do not invent facts.\n"
    "- Be concise, neutral, and specific to the company.\n"
    "'direction' describes the possible nature of the effect (headwind/tailwind/"
    "mixed/neutral) for awareness only — it is NOT a recommendation."
)


def _user_prompt(article: dict[str, Any], link: dict[str, Any]) -> str:
    return (
        f"COMPANY: {link['name']} ({link['ticker']}), sector: {link['sector']}.\n"
        f"LINK TO ARTICLE: {link['link_type']} (relevance {link.get('relevance')}).\n\n"
        f"ARTICLE TITLE: {article.get('title')}\n"
        f"ARTICLE BODY:\n{(article.get('body') or '')[:6000]}\n\n"
        "Write an awareness insight for someone who owns this company: a one-line "
        "summary of what happened, and how it could relate to their position. "
        "Follow every hard rule."
    )


def _call_openai(system: str, user: str) -> dict[str, Any]:
    """Isolated so tests can monkeypatch it. Returns the parsed insight dict."""
    oa = openai_client.client()
    resp = oa.chat.completions.create(
        model=env.OPENAI_INSIGHT_MODEL,
        temperature=0.2,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "insight", "strict": True, "schema": _SCHEMA},
        },
    )
    return json.loads(resp.choices[0].message.content)


def generate(article: dict[str, Any], link: dict[str, Any]) -> dict[str, Any] | None:
    if not openai_client.is_enabled():
        return None

    system, user = _SYSTEM, _user_prompt(article, link)
    try:
        data = _call_openai(system, user)
    except Exception as exc:
        log.warning("Insight generation failed (%s / %s): %s", article["id"], link["ticker"], exc)
        return None

    # Guardrail: reject advice-like output. Retry once with an explicit nudge.
    if not guardrails.is_clean(data.get("summary", ""), data.get("possible_impact", "")):
        offending = guardrails.check_advice(data.get("summary", ""), data.get("possible_impact", ""))
        log.info("Insight tripped guardrail %s — retrying once", offending)
        try:
            data = _call_openai(
                system,
                user + "\n\nYour previous answer used advice-like language "
                f"({offending}). Rewrite WITHOUT any recommendation or prediction.",
            )
        except Exception:
            return None
        if not guardrails.is_clean(data.get("summary", ""), data.get("possible_impact", "")):
            log.warning("Insight still advice-like after retry — dropping")
            return None

    if data.get("direction") not in _DIRECTIONS:
        data["direction"] = "neutral"
    # Sources come from the ARTICLE, not the model — guarantees a real citation.
    data["sources"] = [{"title": article.get("title"), "url": article.get("url")}]
    return data
