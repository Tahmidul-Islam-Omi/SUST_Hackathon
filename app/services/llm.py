"""Optional LLM drafting with a rule-based fallback. Used only to polish the
wording of agent_summary / customer_reply. Falls back to rule-based text when
disabled, unconfigured, erroring, or slow, and the output is always re-checked
by safety.enforce_safety. Kept import-light so the app starts without an SDK."""

from __future__ import annotations

from app.core.config import settings


def is_available() -> bool:
    return bool(settings.llm_enabled and settings.openai_api_key)


def draft_reply(prompt: str) -> str | None:
    """Return polished text, or None to signal 'use the rule-based fallback'."""
    if not is_available():
        return None
    # If implemented later: call the provider SDK with a short timeout, catch all
    # errors, and return None on failure. Disabled and unused in this submission.
    return None
