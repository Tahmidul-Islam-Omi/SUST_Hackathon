"""OPTIONAL LLM drafting with a rule-based fallback. OWNER: Person B (Phase 6).

The service must score fully WITHOUT this. Only use an LLM to polish the wording
of agent_summary / customer_reply, and ALWAYS:
  - fall back to rule-based text if LLM_ENABLED is false, no key is set, the call
    errors, or it risks the 30s timeout;
  - run the output back through safety.enforce_safety(...) before returning.

Keep this import-light so the app starts even when no LLM SDK is installed.
"""

from __future__ import annotations

from app.core.config import settings


def is_available() -> bool:
    return bool(settings.llm_enabled and settings.openai_api_key)


def draft_reply(prompt: str) -> str | None:
    """Return polished text, or None to signal 'use the rule-based fallback'."""
    if not is_available():
        return None
    # TODO(Person B, Phase 6): call provider SDK with a short timeout, catch all
    # errors and return None on failure.
    return None
