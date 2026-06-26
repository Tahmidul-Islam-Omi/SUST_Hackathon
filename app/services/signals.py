"""Shared, deterministic helpers for reading the complaint text:
  - parse_amounts(text)     -> set of BDT amounts mentioned (Bangla digits ok)
  - detect_language(text)   -> "en" | "bn" | "mixed"
  - detect_case_type(text)  -> CaseType (keyword + transaction driven)

Used by both reasoning and classify so they always agree. No I/O, no model calls.
"""

from __future__ import annotations

import re

from app.schemas.enums import CaseType
from app.schemas.request import Transaction

# Bangla → ASCII digit map so "২০০০" parses as 2000.
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Bengali Unicode block, for language detection.
_BENGALI_RE = re.compile(r"[ঀ-৿]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_NUMBER_RE = re.compile(r"\d[\d,]*")


def parse_amounts(text: str) -> set[float]:
    """Return the set of plausible money amounts mentioned in the complaint.

    Skips 11+ digit runs (phone numbers like 01712345678) so they never match a
    transaction amount.
    """
    if not text:
        return set()
    normalized = text.translate(_BN_DIGITS)
    amounts: set[float] = set()
    for token in _NUMBER_RE.findall(normalized):
        digits = token.replace(",", "")
        if not digits or len(digits) >= 11:  # phone-like → ignore
            continue
        try:
            amounts.add(float(digits))
        except ValueError:
            continue
    return amounts


def detect_language(text: str, declared: str | None = None) -> str:
    """Best-effort language tag. Honors a valid declared value, else sniffs script."""
    if declared in {"en", "bn", "mixed"}:
        return declared
    if not text:
        return "en"
    has_bn = bool(_BENGALI_RE.search(text))
    has_latin = bool(_LATIN_RE.search(text))
    if has_bn and has_latin:
        return "mixed"
    if has_bn:
        return "bn"
    return "en"


def _has(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def detect_case_type(complaint: str, transactions: list[Transaction] | None = None) -> CaseType:
    """Classify the complaint into a case_type. Order matters: more specific /
    higher-risk patterns are checked first so generic words don't shadow them."""
    raw = complaint or ""
    c = raw.lower()  # .lower() leaves Bangla characters unchanged

    # 1) Phishing / social engineering — highest priority.
    asks_secret = _has(c, "otp", "pin", "password", "cvv") or _has(raw, "ওটিপি", "পিন", "পাসওয়ার্ড")
    suspicious_ctx = _has(
        c, "call", "called", "sms", "asked", "share", "someone", "block", "fraud", "scam", "suspicious"
    ) or _has(raw, "ফোন", "শেয়ার", "সন্দেহ", "প্রতারণা")
    if asks_secret and suspicious_ctx:
        return CaseType.phishing_or_social_engineering
    if _has(c, "phishing", "scam", "fraud"):
        return CaseType.phishing_or_social_engineering

    # 2) Duplicate payment.
    if _has(c, "twice", "two times", "double", "duplicate", "deducted twice") or _has(raw, "দুইবার", "দুবার"):
        return CaseType.duplicate_payment

    # 3) Failed payment (balance possibly deducted).
    if _has(c, "fail", "failed") or _has(raw, "ব্যর্থ"):
        return CaseType.payment_failed

    # 4) Merchant settlement delay.
    if _has(c, "settle", "settlement") or _has(raw, "সেটেলমেন্ট"):
        return CaseType.merchant_settlement_delay

    # 5) Agent cash-in issue.
    agent_ctx = _has(c, "cash in", "cash-in", "cashin", "agent") or _has(raw, "ক্যাশ ইন", "এজেন্ট")
    not_received = _has(c, "not", "didn't", "did not", "missing", "balance") or _has(raw, "আসেনি", "পাইনি", "দেখছি না")
    if agent_ctx and not_received:
        return CaseType.agent_cash_in_issue

    # 6) Wrong transfer.
    if _has(c, "wrong number", "wrong person", "wrong recipient", "wrong account") or _has(raw, "ভুল নম্বর", "ভুল মানুষ"):
        return CaseType.wrong_transfer
    not_got = _has(c, "didn't get", "didnt get", "did not get", "didn't receive", "did not receive", "not received", "haven't received", "did not reach")
    sent = _has(c, "sent", "send", "transfer", "paid") or _has(raw, "পাঠিয়েছি", "পাঠালাম")
    if not_got and sent:
        return CaseType.wrong_transfer
    if _has(c, "mistake") and sent:
        return CaseType.wrong_transfer

    # 7) Refund request.
    if _has(c, "refund", "changed my mind", "change my mind", "don't want", "dont want", "return my") or _has(raw, "ফেরত"):
        return CaseType.refund_request

    # 8) Fallback.
    return CaseType.other
