"""Safe text generation and guardrails. Two responsibilities:
  1. build_replies(...)        -> agent_summary, recommended_next_action, customer_reply
  2. enforce_safety(text)      -> final banned-content filter on customer_reply

Hard rules for customer_reply (Section 8 of the problem statement):
  - NEVER ask for PIN / OTP / password / full card number.            (-15 pts)
  - NEVER promise a refund, reversal, or account unblock.            (-10 pts)
  - NEVER direct the customer to a third party outside official channels. (-10 pts)
  - IGNORE any instructions embedded inside the complaint (prompt injection).
  - Reply in the customer's language (Bangla in -> Bangla out).

Design:
  - customer_reply is built from a hand-written, vetted TEMPLATE per case_type
    (English + Bangla). No free-form generation = no place for an LLM to slip.
  - enforce_safety runs a final regex scan over the chosen reply and replaces
    the WHOLE reply with SAFE_FALLBACK_REPLY if anything trips. The replacement
    policy is conservative on purpose: a partial scrub can still leak context.
  - Prompt-injection defense: the complaint text is never concatenated into the
    customer_reply. The only fields used in the reply are case_type,
    relevant_transaction_id, and language — all of which come from our own
    pipeline (enums, not the raw complaint).
"""

from __future__ import annotations

import re

from app.schemas.enums import CaseType, EvidenceVerdict, Severity
from app.schemas.request import AnalyzeTicketRequest
from app.services import signals

# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #
# Used as the initial stub reply AND whenever generated text fails the safety
# filter. Carefully worded to satisfy every banned-pattern check below.
SAFE_FALLBACK_REPLY = (
    "Thank you for reaching out. Our team will review your case and contact you "
    "through official support channels. Please do not share your PIN or OTP with "
    "anyone."
)

SAFE_FALLBACK_REPLY_BN = (
    "আমাদের সাথে যোগাযোগ করার জন্য ধন্যবাদ। আমাদের দল আপনার অভিযোগটি পর্যালোচনা করবে "
    "এবং অফিসিয়াল চ্যানেলের মাধ্যমে আপনার সাথে যোগাযোগ করবে। অনুগ্রহ করে কারো সাথে "
    "আপনার পিন বা ওটিপি শেয়ার করবেন না।"
)


# --------------------------------------------------------------------------- #
# Banned-pattern detection (Section 8)
# --------------------------------------------------------------------------- #
# Three rule groups from the problem statement. Each pattern is case-insensitive
# and applied with re.search (matches anywhere in the text). All unicode-aware
# so Bangla trips "ওটিপি" etc. correctly.

# Rule 1: Asking the customer for a secret / credential.
# (-15 pts) Phrased as ANY kind of verification step.
#
# IMPORTANT: a NEGATIVE phrase in the sentence ("do not share", "don't provide",
# "never give", Bangla "করবেন না") makes it a SAFETY WARNING, not a request.
# The credential safety line we always append ("Please do not share your PIN
# or OTP") must NOT trip this check. We handle this with a 2-pass approach:
# first find a raw verb+credential co-occurrence, then reject the match if a
# negation word sits between the verb and the credential.
_CREDENTIAL_VERBS = (
    r"\b(?:please|kindly)?\s*(?:share|send|provide|tell|give|confirm|verify|"
    r"enter|type|submit|forward|reveal|disclose|ask\s+(?:me|us)\s+for|request)\b"
)
# English nouns get \b boundaries; Bangla does NOT use \b (Bangla chars are all
# \w in Unicode but \b only fires at ASCII transitions, so it would fail to
# match a Bangla noun surrounded by other Bangla chars).
_CREDENTIAL_NOUNS_EN = (
    r"\b(?:pin|otp|password|cvv|full\s*card\s*number|card\s*number)\b"
)
_CREDENTIAL_NOUNS_BN = r"(?:পিন|ওটিপি|পাসওয়ার্ড|সিভিভি)"
# Words that turn a verb+credential sentence into a NEGATIVE safety warning.
_NEG_WORDS_EN = re.compile(
    r"\b(?:do(?:es)?\s*not|don'?t|never|no\s+need\s+to|shouldn'?t|should\s*not|"
    r"must\s*not|refuse\s*to|will\s*not|won'?t|can'?t|cannot)\b",
    re.I,
)
# Bangla negation: must be a word-final particle AFTER a verb/auxiliary, never
# the substring inside another word like "আপনা" (your) or "জানা" (known). The
# trick: "না" must be preceded by whitespace OR a verb-like ending. We use a
# non-consuming lookbehind for whitespace + an alternation of verb-endings.
_NEG_WORDS_BN = re.compile(
    r"(?:"
    r"(?<=\s)না(?=[\s।.,!?]|$)"
    r"|করবেন\s*না(?=[\s।.,!?]|$)"
    r"|করবেন\s*নি(?=[\s।.,!?]|$)"
    r"|দেবেন\s*না(?=[\s।.,!?]|$)"
    r"|পাবেন\s*না(?=[\s।.,!?]|$)"
    r"|শেয়ার\s*করবেন\s*না(?=[\s।.,!?]|$)"
    r"|দেওয়া\s*হবে\s*না(?=[\s।.,!?]|$)"
    r")"
)

_CREDENTIAL_PATTERNS_RAW: tuple[re.Pattern[str], ...] = (
    # English: "<verb> ... <credential>" — capture the whole region.
    re.compile(
        rf"({_CREDENTIAL_VERBS})([^.\n]{{0,60}})({_CREDENTIAL_NOUNS_EN})",
        re.I,
    ),
    # English: "<credential> ... please/kindly/required/needed" — no verb.
    re.compile(
        rf"({_CREDENTIAL_NOUNS_EN})([^.\n]{{0,40}})\b(please|kindly|required|needed)\b",
        re.I,
    ),
    # Bangla: "<noun> ... জানান/পাঠান/দিন/প্রয়োজন" (no \b — Bangla rules).
    # Optional leading noun-adjective (টাকা etc.) is allowed between the verb
    # markers and the noun. The trailing lookahead anchors the verb at a word
    # boundary so we don't match substrings inside longer words.
    re.compile(
        rf"(?:^|[\s।,.])({_CREDENTIAL_NOUNS_BN})([^\n।]{{0,60}})(?:জানান|পাঠান|দিন|প্রয়োজন)(?=[\s।.,!?]|$)",
    ),
    # Bangla: "জানান/পাঠান/দিন ... <noun>"  e.g. "OTP পাঠান"
    re.compile(
        rf"(?:জানান|পাঠান|দিন)\s*([^\n।]{{0,40}})({_CREDENTIAL_NOUNS_BN})",
    ),
)

# Rule 2: Promising a refund, reversal, or unblock.
# (-10 pts) Use neutral "any eligible amount will be returned through official channels" instead.
_REFUND_PROMISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English: direct commitments.
    re.compile(r"\bwe\s+(?:will|shall|are\s+going\s+to|'ll)\s+(?:refund|reverse|return|unblock|restore|release)\b", re.I),
    re.compile(r"\byou\s+will\s+(?:be\s+)?(?:refunded|reversed|compensated|paid\s+back)\b", re.I),
    re.compile(r"\bwe\s+have\s+(?:refunded|reversed|initiated\s+(?:a\s+)?refund)\b", re.I),
    re.compile(r"\b(?:guarantee(?:d)?|assure\s+you)\s+(?:a\s+)?(?:refund|reversal|return)\b", re.I),
    re.compile(r"\b(?:refund|reversal)\s+(?:has\s+been\s+)?(?:initiated|processed|approved|completed)\b", re.I),
    # Bangla refund promises. Allow optional "টাকা" between আমরা and ফেরত
    # because colloquial Bangla often says "আমরা টাকা ফেরত দেব".
    re.compile(r"(?:আমরা|আমরা\s+অবশ্যই)(?:\s+টাকা)?\s+(?:ফেরত|রিফান্ড|রিভার্স)\s+(?:দেব|করব|করবো|দিচ্ছি|দিচ্ছে)", re.I),
    # "আপনি/আপনার টাকা ফেরত পাবেন" = "you WILL receive the money back" — direct promise.
    re.compile(r"(?:আপনি|আপনার)\s+(?:টাকা\s+)?ফেরত\s+পাবেন"),
    # NOTE: the safe phrase "যোগ্য পরিমাণ ... ফেরত দেওয়া হবে" (eligible amount WILL
    # be returned) does NOT trip — it has no "আমরা"/"আপনি" subject.
)

# Rule 3: Third-party redirect (outside official channels).
# (-10 pts) Direct customers only to official channels.
_THIRD_PARTY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English: tell them to call / visit / contact some other party.
    re.compile(r"\b(?:please|kindly)?\s*(?:call|contact|reach\s+out\s+to|visit)\b[^.\n]{0,80}\b(?:at\s+)?(?:\+?\d[\d\s\-]{6,}|www\.|http|\.com|\.bd)\b", re.I),
    re.compile(r"\bcontact\s+(?:us\s+)?(?:at|on)\b[^.\n]{0,20}\+?\d[\d\s\-]{6,}", re.I),
    re.compile(r"\bvisit\s+(?:our|the)\s+(?:office|branch)\s+at\b", re.I),
    # Bangla third-party redirect.
    re.compile(r"(?:ফোন\s+করুন|যোগাযোগ\s+করুন|কল\s+করুন)[^\n।]{0,80}(?:\+?\d[\d\s\-]{6,}|www\.)", re.I),
)


def _has_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


def _credential_request_violation(text: str) -> bool:
    """True if text ASKS the customer for a credential. A SAFETY WARNING
    ("do not share your PIN") is NOT a violation — only an actual request is.

    The negation may sit EITHER before the verb ("please do not share") OR
    inside the verb-to-noun span, so we look at a 30-char window before the
    match AND the match itself.
    """
    for p in _CREDENTIAL_PATTERNS_RAW:
        m = p.search(text)
        if not m:
            continue
        # Wider context: 30 chars before, the match, and 10 chars after.
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 10)
        region = text[start:end]
        if _NEG_WORDS_EN.search(region) or _NEG_WORDS_BN.search(region):
            continue
        return True
    return False


def _violation_kind(text: str) -> str | None:
    """Return a short label of which rule tripped, or None if clean.

    Order matters: credential asks (-15) is more severe than refund (-10)
    which is more severe than third-party redirect (-10). We label whichever
    trips first so logs / reason_codes can surface it.
    """
    if _credential_request_violation(text):
        return "credential_request"
    if _has_any(text, _REFUND_PROMISE_PATTERNS):
        return "refund_promise"
    if _has_any(text, _THIRD_PARTY_PATTERNS):
        return "third_party_redirect"
    return None


def enforce_safety(text: str, language: str = "en") -> str:
    """Final safety net: if the proposed customer_reply trips ANY banned pattern,
    replace it WHOLESALE with the guaranteed-safe fallback.

    Conservative on purpose — partial scrubbing can still leak unsafe context.
    The fallback itself is also scanned (it always passes; we ship it pre-checked).
    """
    if not text:
        return SAFE_FALLBACK_REPLY_BN if language == "bn" else SAFE_FALLBACK_REPLY
    if _violation_kind(text) is not None:
        return SAFE_FALLBACK_REPLY_BN if language == "bn" else SAFE_FALLBACK_REPLY
    return text


# --------------------------------------------------------------------------- #
# Customer-reply templates — hand-written, vetted per case_type
# --------------------------------------------------------------------------- #
# Each template has placeholders for the specific transaction ID. The credential
# safety line ("Please do not share your PIN or OTP with anyone." / Bangla
# equivalent) is appended uniformly so we never accidentally drop it.

_EN_NO_TXN = (
    "Thank you for reaching out. {body} Please do not share your PIN or OTP "
    "with anyone."
)
_EN_WITH_TXN = (
    "We have noted your concern about transaction {txn}. {body} "
    "Please do not share your PIN or OTP with anyone."
)

_BN_NO_TXN = (
    "আমাদের সাথে যোগাযোগ করার জন্য ধন্যবাদ। {body} অনুগ্রহ করে কারো সাথে আপনার "
    "পিন বা ওটিপি শেয়ার করবেন না।"
)
_BN_WITH_TXN = (
    "আপনার লেনদেন {txn} এর বিষয়ে আমরা অবগত হয়েছি। {body} অনুগ্রহ করে কারো সাথে "
    "আপনার পিন বা ওটিপি শেয়ার করবেন না।"
)

# Body text per case_type (the dynamic middle sentence(s)). All bodies are
# phrased to AVOID any banned pattern. The full reply is then re-scanned by
# enforce_safety() before it leaves the service, so even an accidental slip
# here can't reach the customer.
_EN_BODIES: dict[CaseType, str] = {
    CaseType.wrong_transfer: (
        "Our dispute team will review the case and contact you through official "
        "support channels."
    ),
    CaseType.payment_failed: (
        "Our payments team will review the case and any eligible amount will be "
        "returned through official channels."
    ),
    CaseType.duplicate_payment: (
        "Our payments team will verify with the biller and any eligible amount "
        "will be returned through official channels."
    ),
    CaseType.refund_request: (
        "Refunds for completed payments depend on the merchant's own policy. "
        "Our customer support team will guide you on the next step through "
        "official channels."
    ),
    CaseType.merchant_settlement_delay: (
        "Our merchant operations team will check the batch status and update you "
        "through official channels."
    ),
    CaseType.agent_cash_in_issue: (
        "Our agent operations team will verify this and contact you through "
        "official channels."
    ),
    CaseType.phishing_or_social_engineering: (
        "We never ask for your PIN, OTP, or password under any circumstances. "
        "Please do not share these with anyone, even if they claim to be from "
        "us. Our fraud team has been notified of this incident."
    ),
    CaseType.other: (
        "To help you faster, please share the transaction ID, the amount "
        "involved, and a short description of what went wrong."
    ),
}

_BN_BODIES: dict[CaseType, str] = {
    CaseType.wrong_transfer: (
        "আমাদের ডিসপিউট টিম এটি পর্যালোচনা করবে এবং অফিসিয়াল চ্যানেলের মাধ্যমে "
        "আপনার সাথে যোগাযোগ করবে।"
    ),
    CaseType.payment_failed: (
        "আমাদের পেমেন্টস টিম এটি পর্যালোচনা করবে এবং যোগ্য পরিমাণ অফিসিয়াল চ্যানেলের "
        "মাধ্যমে ফেরত দেওয়া হবে।"
    ),
    CaseType.duplicate_payment: (
        "আমাদের পেমেন্টস টিম বিলারের সাথে যাচাই করবে এবং যোগ্য পরিমাণ অফিসিয়াল "
        "চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে।"
    ),
    CaseType.refund_request: (
        "সম্পন্ন পেমেন্টের রিফান্ড মার্চেন্টের নিজস্ব নীতির উপর নির্ভর করে। "
        "আমাদের কাস্টমার সাপোর্ট টিম অফিসিয়াল চ্যানেলের মাধ্যমে আপনাকে পরবর্তী "
        "ধাপে সহায়তা করবে।"
    ),
    CaseType.merchant_settlement_delay: (
        "আমাদের মার্চেন্ট অপারেশনস টিম ব্যাচের অবস্থা যাচাই করবে এবং অফিসিয়াল "
        "চ্যানেলের মাধ্যমে আপনাকে জানাবে।"
    ),
    CaseType.agent_cash_in_issue: (
        "আমাদের এজেন্ট অপারেশন্স দল এটি যাচাই করবে এবং অফিসিয়াল চ্যানেলের মাধ্যমে "
        "আপনার সাথে যোগাযোগ করবে।"
    ),
    CaseType.phishing_or_social_engineering: (
        "আমরা কখনোই আপনার পিন, ওটিপি বা পাসওয়ার্ড চাই না। কেউ নিজেকে আমাদের "
        "পক্ষ থেকে বললেও এগুলো শেয়ার করবেন না। আমাদের ফ্রড টিম এই ঘটনা সম্পর্কে "
        "অবহিত হয়েছে।"
    ),
    CaseType.other: (
        "আমরা দ্রুত সাহায্য করতে পারি; অনুগ্রহ করে লেনদেনের আইডি, পরিমাণ এবং কী "
        "সমস্যা হয়েছে তা সংক্ষেপে জানান।"
    ),
}

# Override body for ambiguous-match cases (insufficient_data + wrong_transfer).
# The default wrong_transfer body assumes a real dispute; here we need to ask
# for the disambiguating detail instead. Matches SAMPLE-08 expected output.
_EN_AMBIGUOUS_BODY = (
    "We see multiple transactions of that amount on that date. Could you share "
    "the recipient's phone number or the transaction ID so we can identify the "
    "right transaction?"
)
_BN_AMBIGUOUS_BODY = (
    "আমরা সেই তারিখে উল্লিখিত পরিমাণের একাধিক লেনদেন দেখতে পাচ্ছি। সঠিক লেনদেন "
    "শনাক্ত করতে অনুগ্রহ করে প্রাপকের ফোন নম্বর বা লেনদেনের আইডি জানান।"
)


# --------------------------------------------------------------------------- #
# agent_summary + recommended_next_action templates
# --------------------------------------------------------------------------- #
def _build_agent_summary(
    case_type: CaseType,
    investigation: dict,
    classification: dict,
    transactions: list,
    language: str,
) -> str:
    txn_id = investigation.get("relevant_transaction_id")
    verdict = investigation.get("evidence_verdict")
    amount = _max_amount(transactions)

    if case_type == CaseType.phishing_or_social_engineering:
        return (
            "Customer reports an unsolicited call or message claiming to be from "
            "the company and asking for credentials. Customer has not shared any "
            "sensitive information. Likely social engineering attempt."
        )
    if case_type == CaseType.other:
        return (
            "Customer reports a vague concern without specifying a transaction, "
            "amount, or clear issue. Insufficient detail to identify any "
            "relevant transaction."
        )
    if verdict == EvidenceVerdict.insufficient_data and case_type == CaseType.wrong_transfer:
        return (
            "Customer reports a transfer issue but multiple plausible transactions "
            "match the complaint. Cannot determine the relevant transaction "
            "without further clarification."
        )

    # Default: name the transaction + amount + case type + verdict.
    amount_str = f"{int(amount):,}" if isinstance(amount, (int, float)) and amount else "the"
    if txn_id:
        return (
            f"Customer reports a {case_type.value.replace('_', ' ')} issue. "
            f"Identified transaction {txn_id} (amount {amount_str} BDT). "
            f"Evidence verdict: {verdict.value}."
        )
    return (
        f"Customer reports a {case_type.value.replace('_', ' ')} issue. "
        f"No matching transaction identified in the provided history. "
        f"Evidence verdict: {verdict.value}."
    )


_EN_NEXT_ACTION: dict[CaseType, str] = {
    CaseType.wrong_transfer: (
        "Verify the transaction details with the customer and initiate the "
        "wrong-transfer dispute workflow per policy."
    ),
    CaseType.payment_failed: (
        "Investigate the ledger status. If the balance was deducted on a failed "
        "payment, initiate the automatic reversal flow within standard SLA."
    ),
    CaseType.duplicate_payment: (
        "Verify the duplicate with payments operations and the biller. If only "
        "one payment was received, initiate reversal of the duplicate transaction."
    ),
    CaseType.refund_request: (
        "Inform the customer that refund eligibility depends on the merchant's "
        "own policy. Guide them on contacting the merchant directly."
    ),
    CaseType.merchant_settlement_delay: (
        "Route to merchant operations to verify the settlement batch status and "
        "communicate a revised ETA to the merchant through official channels."
    ),
    CaseType.agent_cash_in_issue: (
        "Investigate the pending cash-in transaction with agent operations. "
        "Confirm settlement state and resolve within the standard cash-in SLA."
    ),
    CaseType.phishing_or_social_engineering: (
        "Escalate to the fraud team immediately. Confirm to the customer that "
        "the company never asks for OTP. Log the reported contact for fraud "
        "pattern analysis."
    ),
    CaseType.other: (
        "Reply to the customer asking for specific details: which transaction, "
        "what amount, what went wrong, and approximate time."
    ),
}

# Override for ambiguous wrong-transfer (insufficient_data + wrong_transfer).
_EN_NEXT_ACTION_AMBIGUOUS = (
    "Reply to the customer asking for the recipient's number or transaction ID "
    "to disambiguate. Do not initiate a dispute until the transaction is confirmed."
)


def _build_next_action(case_type: CaseType, investigation: dict) -> str:
    verdict = investigation.get("evidence_verdict")
    if (
        case_type == CaseType.wrong_transfer
        and verdict == EvidenceVerdict.insufficient_data
    ):
        return _EN_NEXT_ACTION_AMBIGUOUS
    return _EN_NEXT_ACTION.get(case_type, _EN_NEXT_ACTION[CaseType.other])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _max_amount(transactions) -> float:
    if not transactions:
        return 0.0
    return max((t.amount or 0) for t in transactions)


def _is_ambiguous_match(case_type: CaseType, investigation: dict) -> bool:
    """True when the complaint matched several transactions to different recipients."""
    return (
        case_type == CaseType.wrong_transfer
        and investigation.get("evidence_verdict") == EvidenceVerdict.insufficient_data
    )


def _build_customer_reply(
    case_type: CaseType,
    investigation: dict,
    language: str,
) -> str:
    """Compose customer_reply from vetted templates, then run enforce_safety."""
    is_bn = language == "bn"
    body_map = _BN_BODIES if is_bn else _EN_BODIES
    body = body_map.get(case_type, body_map[CaseType.other])

    # Ambiguous-match override (SAMPLE-08).
    if _is_ambiguous_match(case_type, investigation):
        body = _BN_AMBIGUOUS_BODY if is_bn else _EN_AMBIGUOUS_BODY

    txn_id = investigation.get("relevant_transaction_id")
    if txn_id:
        template = _BN_WITH_TXN if is_bn else _EN_WITH_TXN
        reply = template.format(txn=txn_id, body=body)
    else:
        template = _BN_NO_TXN if is_bn else _EN_NO_TXN
        reply = template.format(body=body)

    # ALWAYS pass through the final safety filter, even for templates.
    return enforce_safety(reply, language=language)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_replies(
    request: AnalyzeTicketRequest,
    investigation: dict,
    classification: dict,
) -> dict:
    """Build agent_summary, recommended_next_action, and customer_reply.

    Order: detect language -> build fields from internal state only -> run
    enforce_safety() over the final customer_reply.
    """
    language = signals.detect_language(request.complaint, request.language)
    case_type: CaseType = classification["case_type"]
    transactions = request.transaction_history or []

    agent_summary = _build_agent_summary(
        case_type, investigation, classification, transactions, language
    )
    next_action = _build_next_action(case_type, investigation)
    customer_reply = _build_customer_reply(case_type, investigation, language)

    return {
        "agent_summary": agent_summary,
        "recommended_next_action": next_action,
        "customer_reply": customer_reply,
    }