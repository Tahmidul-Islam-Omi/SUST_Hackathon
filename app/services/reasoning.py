"""Evidence reasoning — the 35-point core. OWNER: Person B (Phase 3).

Decides WHICH transaction the complaint refers to and whether the evidence backs
the claim, without ever guessing when the data is ambiguous.

Return contract (dict):
    {
        "relevant_transaction_id": str | None,
        "evidence_verdict": EvidenceVerdict,
        "confidence": float,            # 0..1
        "reason_codes": list[str],
    }

Core rules (calibrated against the 10 public sample cases):
  - Match transactions by the amount(s) mentioned in the complaint.
  - relevant_transaction_id = None when nothing matches, the complaint is vague,
    OR several transactions to DIFFERENT recipients plausibly match (don't guess).
  - duplicate_payment: two+ identical (same amount & counterparty) payments ARE
    the evidence → point at the later one, verdict consistent.
  - wrong_transfer where the matched recipient also appears in other history
    entries → established recipient → verdict inconsistent (claim contradicted).
  - phishing / empty history → insufficient_data with a null transaction.
"""

from __future__ import annotations

from app.schemas.enums import CaseType, EvidenceVerdict
from app.schemas.request import Transaction
from app.services import signals


def _result(txn_id, verdict, confidence, reason_codes) -> dict:
    return {
        "relevant_transaction_id": txn_id,
        "evidence_verdict": verdict,
        "confidence": confidence,
        "reason_codes": reason_codes,
    }


def _latest(transactions: list[Transaction]) -> Transaction:
    """Most recent transaction (ISO timestamps sort lexicographically; fall back
    to list order for missing/odd timestamps)."""
    return max(
        enumerate(transactions),
        key=lambda pair: (pair[1].timestamp or "", pair[0]),
    )[1]


def _counterparty_count(counterparty: str | None, transactions: list[Transaction]) -> int:
    if not counterparty:
        return 0
    return sum(1 for t in transactions if t.counterparty == counterparty)


def investigate(
    complaint: str,
    transactions: list[Transaction],
    case_type: CaseType,
) -> dict:
    # Phishing reports are about a call/SMS, not a ledger entry.
    if case_type == CaseType.phishing_or_social_engineering:
        return _result(None, EvidenceVerdict.insufficient_data, 0.9, ["phishing_no_transaction_reference"])

    txns = [t for t in (transactions or []) if t.amount is not None]
    if not txns:
        return _result(None, EvidenceVerdict.insufficient_data, 0.5, ["no_transaction_history"])

    amounts = signals.parse_amounts(complaint)
    matches = [t for t in txns if t.amount in amounts] if amounts else []

    # Duplicate payment: look for 2+ identical (amount, counterparty) entries.
    if case_type == CaseType.duplicate_payment:
        pool = matches or txns
        groups: dict[tuple, list[Transaction]] = {}
        for t in pool:
            groups.setdefault((t.amount, t.counterparty), []).append(t)
        dupes = [g for g in groups.values() if len(g) >= 2]
        if dupes:
            suspected = _latest(max(dupes, key=len))
            return _result(
                suspected.transaction_id,
                EvidenceVerdict.consistent,
                0.93,
                ["duplicate_payment", "biller_verification_required"],
            )

    # Exactly one amount match → confident identification.
    if len(matches) == 1:
        t = matches[0]
        if case_type == CaseType.wrong_transfer and _counterparty_count(t.counterparty, txns) >= 2:
            # Repeated transfers to the same recipient contradict "wrong number".
            return _result(
                t.transaction_id,
                EvidenceVerdict.inconsistent,
                0.75,
                ["wrong_transfer_claim", "established_recipient_pattern", "evidence_inconsistent"],
            )
        return _result(
            t.transaction_id,
            EvidenceVerdict.consistent,
            0.9,
            [case_type.value, "transaction_match"],
        )

    # Several matches.
    if len(matches) >= 2:
        # Different recipients → cannot tell which one the complaint means.
        if len({t.counterparty for t in matches}) >= 2:
            return _result(None, EvidenceVerdict.insufficient_data, 0.65, ["ambiguous_match", "needs_clarification"])
        # All to the same recipient → take the most recent.
        return _result(
            _latest(matches).transaction_id,
            EvidenceVerdict.consistent,
            0.7,
            [case_type.value, "transaction_match"],
        )

    # No amount match: vague complaint or the referenced transaction isn't here.
    if not amounts:
        return _result(None, EvidenceVerdict.insufficient_data, 0.55, ["vague_complaint", "needs_clarification"])
    return _result(None, EvidenceVerdict.insufficient_data, 0.5, ["no_matching_transaction"])
