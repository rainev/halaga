"""Guardrails + insight generation (OpenAI call stubbed)."""

import pytest

from app.ai import guardrails, insight_generator, openai_client

ARTICLE = {"id": 1, "title": "BSP hikes rates", "url": "https://ex.com/a", "body": "..."}
LINK = {"company_id": 2, "ticker": "MEG", "name": "Megaworld", "sector": "Property",
        "link_type": "thematic", "relevance": 0.6}


# --- guardrails -----------------------------------------------------------

def test_guardrail_flags_advice():
    assert guardrails.check_advice("You should buy MEG now.")
    assert guardrails.check_advice("This is a strong buy.")
    assert guardrails.check_advice("The price will surge tomorrow.")


def test_guardrail_passes_awareness():
    assert guardrails.is_clean(
        "BSP raised rates 25bp.",
        "Higher rates could pressure property developers' financing costs.",
    )


# --- generation -----------------------------------------------------------

def test_generate_none_without_key(monkeypatch):
    monkeypatch.setattr(openai_client, "is_enabled", lambda: False)
    assert insight_generator.generate(ARTICLE, LINK) is None


def test_generate_attaches_article_sources(monkeypatch):
    monkeypatch.setattr(openai_client, "is_enabled", lambda: True)
    monkeypatch.setattr(insight_generator, "_call_openai", lambda s, u: {
        "summary": "BSP raised rates 25bp.",
        "possible_impact": "Higher rates may raise financing costs for developers.",
        "direction": "headwind", "confidence": 0.6,
    })
    out = insight_generator.generate(ARTICLE, LINK)
    assert out["direction"] == "headwind"
    # Sources come from the article, guaranteeing a citation.
    assert out["sources"] == [{"title": "BSP hikes rates", "url": "https://ex.com/a"}]


def test_generate_retries_then_drops_persistent_advice(monkeypatch):
    monkeypatch.setattr(openai_client, "is_enabled", lambda: True)
    calls = {"n": 0}

    def fake(_s, _u):
        calls["n"] += 1
        return {"summary": "You should buy MEG.", "possible_impact": "Strong buy.",
                "direction": "tailwind", "confidence": 0.9}

    monkeypatch.setattr(insight_generator, "_call_openai", fake)
    out = insight_generator.generate(ARTICLE, LINK)
    assert out is None            # advice never makes it through
    assert calls["n"] == 2        # tried once, retried once, then gave up


def test_generate_retry_recovers(monkeypatch):
    monkeypatch.setattr(openai_client, "is_enabled", lambda: True)
    seq = iter([
        {"summary": "You should buy MEG.", "possible_impact": "Strong buy.",
         "direction": "tailwind", "confidence": 0.9},
        {"summary": "BSP raised rates.", "possible_impact": "Could lift financing costs.",
         "direction": "headwind", "confidence": 0.5},
    ])
    monkeypatch.setattr(insight_generator, "_call_openai", lambda s, u: next(seq))
    out = insight_generator.generate(ARTICLE, LINK)
    assert out is not None and out["direction"] == "headwind"
