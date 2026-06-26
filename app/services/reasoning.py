"""Evidence reasoning. Decides which transaction the complaint refers to and
whether the evidence backs the claim, returning a dict with
relevant_transaction_id, evidence_verdict, confidence and reason_codes.

Key rules:
  - Match transactions by the amount(s) mentioned in the complaint.
  - relevant_transaction_id is None when nothing matches, the complaint is vague,
    or several transactions to different recipients plausibly match (don't guess).
  - duplicate_payment: two+ identical payments point at the later one (consistent).
  - wrong_transfer to an already-seen recipient is inconsistent (claim contradicted).
  - phishing / empty history -> insufficient_data with a null transaction.
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
    """Most recent transaction. ISO timestamps sort lexicographically, so a later
    string means a later time. On a tie (or missing timestamps) the one appearing
    later in the list wins."""
    latest = transactions[0]
    for txn in transactions[1:]:
        if (txn.timestamp or "") >= (latest.timestamp or ""):
            latest = txn
    return latest


def _counterparty_count(counterparty: str | None, transactions: list[Transaction]) -> int:
    if not counterparty:
        return 0
    count = 0
    for txn in transactions:
        if txn.counterparty == counterparty:
            count += 1
    return count


def _find_duplicate(transactions: list[Transaction]) -> Transaction | None:
    """Group transactions by (amount, counterparty). If any group has 2 or more
    entries, return the most recent one in the largest such group — that is the
    suspected duplicate charge. Returns None when no group repeats."""
    groups: dict[tuple, list[Transaction]] = {}
    for txn in transactions:
        key = (txn.amount, txn.counterparty)
        groups.setdefault(key, []).append(txn)

    largest_repeat: list[Transaction] = []
    for group in groups.values():
        if len(group) >= 2 and len(group) > len(largest_repeat):
            largest_repeat = group

    if not largest_repeat:
        return None
    return _latest(largest_repeat)


def investigate(
    complaint: str,
    transactions: list[Transaction],
    case_type: CaseType,
) -> dict:
    # Phishing reports are about a call/SMS, not a ledger entry.
    if case_type == CaseType.phishing_or_social_engineering:
        return _result(None, EvidenceVerdict.insufficient_data, 0.9, ["phishing_no_transaction_reference"])

    # Keep only transactions that actually carry an amount.
    txns: list[Transaction] = []
    for txn in transactions or []:
        if txn.amount is not None:
            txns.append(txn)

    if not txns:
        return _result(None, EvidenceVerdict.insufficient_data, 0.5, ["no_transaction_history"])

    # Find transactions whose amount is mentioned in the complaint.
    amounts = signals.parse_amounts(complaint)
    matches: list[Transaction] = []
    for txn in txns:
        if txn.amount in amounts:
            matches.append(txn)

    # Duplicate payment: look for 2+ identical (amount, counterparty) entries.
    if case_type == CaseType.duplicate_payment:
        suspected = _find_duplicate(matches or txns)
        if suspected is not None:
            return _result(
                suspected.transaction_id,
                EvidenceVerdict.consistent,
                0.93,
                ["duplicate_payment", "biller_verification_required"],
            )

    # Exactly one amount match → confident identification.
    if len(matches) == 1:
        match = matches[0]
        repeated_recipient = _counterparty_count(match.counterparty, txns) >= 2
        if case_type == CaseType.wrong_transfer and repeated_recipient:
            # Repeated transfers to the same recipient contradict "wrong number".
            return _result(
                match.transaction_id,
                EvidenceVerdict.inconsistent,
                0.75,
                ["wrong_transfer_claim", "established_recipient_pattern", "evidence_inconsistent"],
            )
        return _result(
            match.transaction_id,
            EvidenceVerdict.consistent,
            0.9,
            [case_type.value, "transaction_match"],
        )

    # Several matches.
    if len(matches) >= 2:
        recipients = set()
        for txn in matches:
            recipients.add(txn.counterparty)

        # Different recipients → cannot tell which one the complaint means.
        if len(recipients) >= 2:
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
