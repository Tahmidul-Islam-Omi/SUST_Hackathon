"""Safe text generation and guardrails. Two responsibilities:
  1. build_replies(...)   -> agent_summary, recommended_next_action, customer_reply
  2. enforce_safety(text) -> final banned-content filter on customer_reply

Hard rules for customer_reply:
  - Never ask for PIN / OTP / password / full card number.
  - Never promise a refund/reversal/unblock; use neutral language such as
    "any eligible amount will be returned through official channels".
  - Never direct the customer to a third party outside official channels.
  - Ignore any instructions embedded inside the complaint (prompt injection).
  - Reply in the customer's language (Bangla in -> Bangla out).
"""

from __future__ import annotations

import re

from app.schemas.request import AnalyzeTicketRequest
from app.services import replies, signals

# Guaranteed-safe fallbacks, used when generated text trips the safety filter.
SAFE_FALLBACK_REPLY_EN = (
    "Thank you for reaching out. Our team will review your case and contact you through official "
    "support channels. Please do not share your PIN or OTP with anyone."
)
SAFE_FALLBACK_REPLY_BN = (
    "যোগাযোগ করার জন্য ধন্যবাদ। আমাদের টিম আপনার বিষয়টি যাচাই করে অফিসিয়াল চ্যানেলে আপনার সাথে "
    "যোগাযোগ করবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
)

# Words/phrases for the credential-ask detector (English + Bangla).
_SECRET_WORDS = ("pin", "otp", "password", "cvv", "card number", "ওটিপি", "পিন", "পাসওয়ার্ড")
# Words that signal the text is asking the customer to hand over a secret.
_ASK_VERBS = (
    "share", "send", "provide", "give", "enter", "tell", "type", "reveal", "disclose",
    "submit", "forward", "verify", "confirm", "required", "needed", "শেয়ার", "দিন", "পাঠান",
)
_NEGATIONS = ("not", "never", "n't", "cannot", "না")

_SENTENCE_SPLIT = re.compile(r"[.!?।]")


def _compile_all(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    compiled = []
    for pattern in patterns:
        compiled.append(re.compile(pattern))
    return compiled


# Unauthorized-promise patterns (refund / reversal / account unblock).
_PROMISE_PATTERNS = _compile_all(
    (
        r"\bwe (will|shall|'ll) (refund|reverse|compensate)\b",
        r"\bwe are refunding\b",
        r"\byou (will|'ll) be (refunded|reversed|compensated|paid back)\b",
        r"\bbe refunded\b",
        r"\brefund (has been|is|will be) (approved|processed|confirmed|issued|completed)\b",
        r"\bguaranteed refund\b",
        r"\bwe (will|have) (reverse|reversed)\b",
        r"\byour account (has been|is|will be) (unblocked|restored|unlocked)\b",
    )
)

# Patterns that direct the customer outside official channels.
_REDIRECT_PATTERNS = _compile_all(
    (
        r"call (this|that|the following) number",
        r"\bwhatsapp\b",
        r"call (us )?(at|on) \+?\d",
        r"\bdial\b \+?\d",
    )
)


def build_replies(
    request: AnalyzeTicketRequest,
    investigation: dict,
    classification: dict,
) -> dict:
    language = signals.detect_language(request.complaint, request.language)
    relevant_id = investigation["relevant_transaction_id"]
    transactions = request.transaction_history or []
    relevant_amount = _amount_of(relevant_id, transactions)

    drafted = replies.compose(
        classification["case_type"],
        investigation["evidence_verdict"],
        relevant_id,
        relevant_amount,
        language,
    )

    # The customer reply is the only customer-facing field, so it is filtered.
    drafted["customer_reply"] = enforce_safety(drafted["customer_reply"], language)
    return drafted


def _amount_of(transaction_id: str | None, transactions: list) -> float | None:
    """Amount of the transaction with this id (None if not found)."""
    if not transaction_id:
        return None
    for txn in transactions:
        if txn.transaction_id == transaction_id:
            return txn.amount
    return None


def enforce_safety(text: str, language: str = "en") -> str:
    """Final safety net: if the text trips any banned pattern, replace it with the
    guaranteed-safe fallback in the appropriate language."""
    if _violates_safety(text):
        if language == "bn":
            return SAFE_FALLBACK_REPLY_BN
        return SAFE_FALLBACK_REPLY_EN
    return text


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    for needle in needles:
        if needle in text:
            return True
    return False


def _asks_for_secret(text: str) -> bool:
    """True if any sentence asks the customer to hand over a secret. A sentence
    that mentions a secret only to warn against sharing it (contains a negation)
    is treated as safe."""
    lowered = text.lower()
    for sentence in _SENTENCE_SPLIT.split(lowered):
        if not _contains_any(sentence, _SECRET_WORDS):
            continue
        if not _contains_any(sentence, _ASK_VERBS):
            continue
        if _contains_any(sentence, _NEGATIONS):
            continue
        return True
    return False


def _violates_safety(text: str) -> bool:
    lowered = text.lower()
    for pattern in _PROMISE_PATTERNS:
        if pattern.search(lowered):
            return True
    for pattern in _REDIRECT_PATTERNS:
        if pattern.search(lowered):
            return True
    if _asks_for_secret(text):
        return True
    return False
