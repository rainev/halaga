"""A single, lazily-created OpenAI client for the process.

Optional by design: if OPENAI_API_KEY is unset, `is_enabled()` returns False and
callers skip the LLM/embedding steps (the deterministic ticker/sector matching
still works). This keeps the app bootable and the tests hermetic without a key.
"""

import logging

from ..env import env

log = logging.getLogger("uvicorn.error")

_client = None


def is_enabled() -> bool:
    return bool(env.OPENAI_API_KEY)


def client():
    """Return the shared OpenAI client, or None when no API key is configured."""
    global _client
    if not is_enabled():
        return None
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=env.OPENAI_API_KEY)
    return _client
