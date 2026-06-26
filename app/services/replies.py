"""Case-specific reply content (templates only — no safety policy lives here).

`compose(...)` returns the three text fields for a case:
  - agent_summary and recommended_next_action are always English (agent-facing).
  - customer_reply mirrors the customer's language (English or Bangla).

The agent_summary is assembled from a per-case lead sentence plus a factual
clause naming the matched transaction (with its amount) and the evidence verdict.
customer_reply / recommended_next_action come from hand-written templates that may
use a single `{ref}` placeholder. The safety filter in `safety.py` is applied to
the customer_reply afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.enums import CaseType, EvidenceVerdict

# Standard credential-safety reminder appended to customer replies.
_PIN_NOTE_EN = "Please do not share your PIN or OTP with anyone."
_PIN_NOTE_BN = "অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"


@dataclass(frozen=True)
class ReplyTemplate:
    next_action: str  # English, may use {ref}
    customer_reply_en: str  # may use {ref}
    customer_reply_bn: str  # may use {ref}


CASE_TEMPLATES: dict[CaseType, ReplyTemplate] = {
    CaseType.wrong_transfer: ReplyTemplate(
        next_action="Verify {ref} with the customer and initiate the wrong-transfer dispute workflow per policy.",
        customer_reply_en=(
            "We have noted your concern about {ref}. Our dispute resolution team will review the case "
            "and contact you through official support channels. " + _PIN_NOTE_EN
        ),
        customer_reply_bn=(
            "{ref} সম্পর্কে আপনার উদ্বেগ আমরা নোট করেছি। আমাদের ডিসপিউট রেজোলিউশন টিম বিষয়টি যাচাই করে "
            "অফিসিয়াল চ্যানেলে আপনার সাথে যোগাযোগ করবে। " + _PIN_NOTE_BN
        ),
    ),
    CaseType.payment_failed: ReplyTemplate(
        next_action="Investigate the ledger status of {ref}; if the balance was deducted on a failed payment, initiate the standard reversal flow.",
        customer_reply_en=(
            "We have noted that {ref} may have caused an unexpected balance deduction. Our payments team "
            "will review it and any eligible amount will be returned through official channels. " + _PIN_NOTE_EN
        ),
        customer_reply_bn=(
            "{ref} এর কারণে আপনার ব্যালেন্স থেকে অপ্রত্যাশিতভাবে অর্থ কেটে যেতে পারে বলে আমরা নোট করেছি। "
            "আমাদের পেমেন্টস টিম এটি যাচাই করবে এবং যেকোনো প্রযোজ্য পরিমাণ অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত "
            "দেওয়া হবে। " + _PIN_NOTE_BN
        ),
    ),
    CaseType.refund_request: ReplyTemplate(
        next_action="Explain that refund eligibility depends on the merchant's policy and guide the customer to contact the merchant.",
        customer_reply_en=(
            "Thank you for reaching out. Refund eligibility for {ref} depends on the merchant's own policy. "
            "We recommend contacting the merchant directly, and we are happy to guide you if needed. " + _PIN_NOTE_EN
        ),
        customer_reply_bn=(
            "যোগাযোগ করার জন্য ধন্যবাদ। {ref} এর রিফান্ড মার্চেন্টের নিজস্ব নীতির উপর নির্ভর করে। আমরা সরাসরি "
            "মার্চেন্টের সাথে যোগাযোগ করার পরামর্শ দিচ্ছি, প্রয়োজনে আমরা সাহায্য করতে প্রস্তুত। " + _PIN_NOTE_BN
        ),
    ),
    CaseType.duplicate_payment: ReplyTemplate(
        next_action="Verify the duplicate with payments operations; if the biller confirms a single charge, initiate reversal of the duplicate.",
        customer_reply_en=(
            "We have noted the possible duplicate payment for {ref}. Our payments team will verify it with "
            "the biller and any eligible amount will be returned through official channels. " + _PIN_NOTE_EN
        ),
        customer_reply_bn=(
            "{ref} এর জন্য সম্ভাব্য ডুপ্লিকেট পেমেন্ট আমরা নোট করেছি। আমাদের পেমেন্টস টিম বিলারের সাথে এটি "
            "যাচাই করবে এবং যেকোনো প্রযোজ্য পরিমাণ অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে। " + _PIN_NOTE_BN
        ),
    ),
    CaseType.merchant_settlement_delay: ReplyTemplate(
        next_action="Check the settlement batch status with merchant operations and communicate a revised ETA if it is delayed.",
        customer_reply_en=(
            "We have noted your concern about {ref}. Our merchant operations team will check the settlement "
            "batch status and update you on the expected settlement time through official channels."
        ),
        customer_reply_bn=(
            "{ref} সম্পর্কে আপনার উদ্বেগ আমরা নোট করেছি। আমাদের মার্চেন্ট অপারেশন্স টিম সেটেলমেন্ট ব্যাচ "
            "স্ট্যাটাস যাচাই করে অফিসিয়াল চ্যানেলে প্রত্যাশিত সেটেলমেন্ট সময় সম্পর্কে আপনাকে জানাবে।"
        ),
    ),
    CaseType.agent_cash_in_issue: ReplyTemplate(
        next_action="Investigate the status of {ref} with agent operations and resolve within the standard cash-in SLA.",
        customer_reply_en=(
            "We have noted your concern about {ref}. Our agent operations team will verify it promptly and "
            "update you through official channels. " + _PIN_NOTE_EN
        ),
        customer_reply_bn=(
            "{ref} সম্পর্কে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স টিম এটি দ্রুত যাচাই করবে এবং অফিসিয়াল "
            "চ্যানেলে আপনাকে জানাবে। " + _PIN_NOTE_BN
        ),
    ),
    CaseType.phishing_or_social_engineering: ReplyTemplate(
        next_action="Escalate to the fraud risk team, confirm the company never asks for OTP, and log the reported contact for fraud-pattern analysis.",
        customer_reply_en=(
            "Thank you for reaching out before sharing any information. We never ask for your PIN, OTP, or "
            "password under any circumstances. Please do not share these with anyone, even if they claim to "
            "be from us. Our fraud team has been notified of this incident."
        ),
        customer_reply_bn=(
            "কোনো তথ্য শেয়ার করার আগে যোগাযোগ করার জন্য ধন্যবাদ। আমরা কখনোই আপনার পিন, ওটিপি বা পাসওয়ার্ড "
            "চাই না। কেউ নিজেকে আমাদের প্রতিনিধি দাবি করলেও এগুলো কারো সাথে শেয়ার করবেন না। আমাদের ফ্রড "
            "টিমকে বিষয়টি জানানো হয়েছে।"
        ),
    ),
    CaseType.other: ReplyTemplate(
        next_action="Ask the customer for specific details: transaction ID, amount, what went wrong, and the approximate time.",
        customer_reply_en=(
            "Thank you for reaching out. To help you faster, please provide the transaction ID, the amount "
            "involved, and a short description of what went wrong. " + _PIN_NOTE_EN
        ),
        customer_reply_bn=(
            "যোগাযোগ করার জন্য ধন্যবাদ। আপনাকে দ্রুত সহায়তা করতে অনুগ্রহ করে লেনদেন আইডি, পরিমাণ এবং কী "
            "সমস্যা হয়েছে তার সংক্ষিপ্ত বিবরণ জানান। " + _PIN_NOTE_BN
        ),
    ),
}

# Used when a money case is recognized but no single transaction could be pinned.
CLARIFICATION = ReplyTemplate(
    next_action="Ask the customer for the transaction ID, or the recipient and amount, to identify the correct transaction before proceeding.",
    customer_reply_en=(
        "Thank you for reaching out. We see more than one transaction that could match your complaint. "
        "Could you provide the transaction ID, or the recipient's number and amount, so we can identify "
        "the right one? " + _PIN_NOTE_EN
    ),
    customer_reply_bn=(
        "যোগাযোগ করার জন্য ধন্যবাদ। আপনার অভিযোগের সাথে মেলে এমন একাধিক লেনদেন আমরা দেখতে পাচ্ছি। সঠিকটি "
        "শনাক্ত করতে অনুগ্রহ করে লেনদেন আইডি অথবা প্রাপকের নম্বর ও পরিমাণ জানান। " + _PIN_NOTE_BN
    ),
)


# --------------------------------------------------------------------------- #
# agent_summary (English, agent-facing) — assembled from facts, not a template.
# --------------------------------------------------------------------------- #
# Lead sentence per case for the standard money cases.
_AGENT_LEAD: dict[CaseType, str] = {
    CaseType.wrong_transfer: "Customer reports a wrong transfer.",
    CaseType.payment_failed: "Customer reports a failed payment with a possible balance deduction.",
    CaseType.refund_request: "Customer requests a refund; this is not a service failure.",
    CaseType.duplicate_payment: "Customer reports a duplicate payment.",
    CaseType.merchant_settlement_delay: "Merchant reports a delayed settlement.",
    CaseType.agent_cash_in_issue: "Customer reports a cash-in that is not reflected in their balance.",
}
_AGENT_PHISHING = "Customer reports a suspected phishing or social-engineering attempt; no credentials were shared."
_AGENT_OTHER = "Vague complaint with insufficient detail to identify a transaction."
_AGENT_AMBIGUOUS = "Complaint matched multiple plausible transactions; the relevant one cannot be determined without clarification."


def _format_amount(amount: float) -> str:
    return f"{int(amount):,}"


def _transaction_clause(relevant_transaction_id: str | None, relevant_amount: float | None) -> str:
    if not relevant_transaction_id:
        return "No matching transaction was identified in the provided history."
    if relevant_amount is None:
        return f"Identified transaction {relevant_transaction_id}."
    return f"Identified transaction {relevant_transaction_id} ({_format_amount(relevant_amount)} BDT)."


def build_agent_summary(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    relevant_transaction_id: str | None,
    relevant_amount: float | None,
) -> str:
    """Factual one/two-sentence summary for the support agent (always English).

    `relevant_amount` is the amount of the matched transaction (not the largest in
    history), so the figure quoted always belongs to the transaction named.
    """
    if case_type == CaseType.phishing_or_social_engineering:
        return _AGENT_PHISHING
    if case_type == CaseType.other:
        return _AGENT_OTHER
    if _is_ambiguous(case_type, verdict, relevant_transaction_id):
        return _AGENT_AMBIGUOUS

    lead = _AGENT_LEAD.get(case_type, _AGENT_OTHER)
    txn_clause = _transaction_clause(relevant_transaction_id, relevant_amount)
    return f"{lead} {txn_clause} Evidence verdict: {verdict.value}."


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #
def _is_ambiguous(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    relevant_transaction_id: str | None,
) -> bool:
    """A recognized money case where no single transaction could be pinned."""
    if case_type in (CaseType.phishing_or_social_engineering, CaseType.other):
        return False
    return verdict == EvidenceVerdict.insufficient_data and relevant_transaction_id is None


def _reference_phrases(relevant_transaction_id: str | None) -> tuple[str, str]:
    """Return (english, bangla) phrases for the matched transaction reference."""
    if relevant_transaction_id:
        return f"transaction {relevant_transaction_id}", f"লেনদেন {relevant_transaction_id}"
    return "your request", "আপনার অনুরোধ"


def _select_template(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    relevant_transaction_id: str | None,
) -> ReplyTemplate:
    if case_type == CaseType.phishing_or_social_engineering:
        return CASE_TEMPLATES[CaseType.phishing_or_social_engineering]
    if case_type == CaseType.other:
        return CASE_TEMPLATES[CaseType.other]
    if _is_ambiguous(case_type, verdict, relevant_transaction_id):
        return CLARIFICATION
    return CASE_TEMPLATES.get(case_type, CASE_TEMPLATES[CaseType.other])


def compose(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    relevant_transaction_id: str | None,
    relevant_amount: float | None,
    language: str,
) -> dict:
    """Build the three text fields for the response (reply not yet safety-filtered)."""
    template = _select_template(case_type, verdict, relevant_transaction_id)
    ref_en, ref_bn = _reference_phrases(relevant_transaction_id)

    if language == "bn":
        customer_reply = template.customer_reply_bn.format(ref=ref_bn)
    else:
        customer_reply = template.customer_reply_en.format(ref=ref_en)

    return {
        "agent_summary": build_agent_summary(case_type, verdict, relevant_transaction_id, relevant_amount),
        "recommended_next_action": template.next_action.format(ref=ref_en),
        "customer_reply": customer_reply,
    }
