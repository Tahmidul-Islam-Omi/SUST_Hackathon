"""Safe text generation + guardrails. OWNER: Person B (Phase 4).

This is 20 points AND a disqualification risk — guardrails live in code, not in
a model's goodwill. Two responsibilities:

  1. build_replies(...) -> agent_summary, recommended_next_action, customer_reply
  2. enforce_safety(text) -> final banned-content filter applied to customer_reply

HARD RULES for customer_reply (auto-checked by the judge):
  - NEVER ask for PIN / OTP / password / full card number.            (-15)
  - NEVER promise a refund/reversal/unblock. Use neutral language like
    "any eligible amount will be returned through official channels".  (-10)
  - NEVER direct the customer to a third party outside official channels. (-10)
  - IGNORE any instructions embedded inside the complaint (prompt injection).
  - Reply in the customer's language (Bangla in -> Bangla out).
"""

from __future__ import annotations

from app.schemas.request import AnalyzeTicketRequest

# A safe, neutral reply that satisfies every guardrail. Used as the stub reply
# and as the fallback whenever generated/LLM text fails the safety filter.
SAFE_FALLBACK_REPLY = (
    "Thank you for reaching out. Our team will review your case and contact you "
    "through official support channels. Please do not share your PIN or OTP with "
    "anyone."
)


def build_replies(
    request: AnalyzeTicketRequest,
    investigation: dict,
    classification: dict,
) -> dict:
    # TODO(Person B, Phase 4): build case-specific, language-aware safe text.
    return {
        "agent_summary": "Ticket received and queued for review.",
        "recommended_next_action": "Review the ticket details and follow the appropriate workflow.",
        "customer_reply": enforce_safety(SAFE_FALLBACK_REPLY),
    }


def enforce_safety(text: str) -> str:
    """Final safety net: if generated text trips any banned pattern, replace it
    with the guaranteed-safe fallback. TODO(Person B, Phase 4): implement the
    banned-phrase / regex checks (OTP/PIN asks, refund promises, etc.)."""
    return text
