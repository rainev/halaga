"""The "awareness, not advice" contract, enforced in code.

FinSight surfaces information and explains *possible* impact — it never tells a
user to buy/sell/hold or predicts a price. The system prompt asks the model to
follow this; `check_advice()` is the belt-and-suspenders output check that
catches anything imperative that slips through, so we can reject/flag it before
it ever reaches a user.
"""

import re

# Phrases that read as a recommendation or a price call. Word-boundaried and
# case-insensitive. Deliberately conservative — better to flag and rewrite than
# to let advice through.
_ADVICE_PATTERNS: tuple[str, ...] = (
    r"\byou should\b",
    r"\bwe recommend\b",
    r"\brecommend(?:ed|ation)?\b",
    r"\b(?:a|strong)\s+(?:buy|sell)\b",
    r"\bbuy now\b",
    r"\bsell now\b",
    r"\bshould (?:buy|sell|hold|invest)\b",
    r"\b(?:must|need to) (?:buy|sell)\b",
    r"\bprice target\b",
    r"\bwill (?:rise|fall|surge|plunge|hit|reach)\b",
    r"\bguaranteed?\b",
)

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _ADVICE_PATTERNS]


def check_advice(*texts: str) -> list[str]:
    """Return the advice-like phrases found across the given texts (empty =
    clean). Callers reject or rewrite when this is non-empty."""
    found: list[str] = []
    for text in texts:
        if not text:
            continue
        for pattern in _COMPILED:
            m = pattern.search(text)
            if m:
                found.append(m.group(0))
    return found


def is_clean(*texts: str) -> bool:
    return not check_advice(*texts)
