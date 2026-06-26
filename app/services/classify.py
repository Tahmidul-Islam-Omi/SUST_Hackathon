"""Case routing, severity and escalation. Takes the detected case_type plus the
investigation result and returns a dict with case_type, department, severity and
human_review_required (department via a fixed routing table)."""

from __future__ import annotations

from app.schemas.enums import CaseType, Department, EvidenceVerdict, Severity
from app.schemas.request import Transaction

# case_type → owning department (Section 7.2 of the problem statement).
_DEPARTMENT: dict[CaseType, Department] = {
    CaseType.wrong_transfer: Department.dispute_resolution,
    CaseType.payment_failed: Department.payments_ops,
    CaseType.duplicate_payment: Department.payments_ops,
    CaseType.refund_request: Department.customer_support,
    CaseType.merchant_settlement_delay: Department.merchant_operations,
    CaseType.agent_cash_in_issue: Department.agent_operations,
    CaseType.phishing_or_social_engineering: Department.fraud_risk,
    CaseType.other: Department.customer_support,
}

# Amount at/above which we always escalate, regardless of case_type.
_HIGH_VALUE_BDT = 25_000


def _severity(case_type: CaseType, verdict: EvidenceVerdict) -> Severity:
    if case_type == CaseType.phishing_or_social_engineering:
        return Severity.critical
    if case_type in (CaseType.payment_failed, CaseType.duplicate_payment, CaseType.agent_cash_in_issue):
        return Severity.high
    if case_type == CaseType.wrong_transfer:
        # Confirmed wrong transfer is high; unconfirmed/contradicted is medium.
        return Severity.high if verdict == EvidenceVerdict.consistent else Severity.medium
    if case_type == CaseType.merchant_settlement_delay:
        return Severity.medium
    return Severity.low  # refund_request, other


def _max_amount(transactions: list[Transaction]) -> float:
    return max((t.amount or 0) for t in transactions) if transactions else 0


def _human_review(
    case_type: CaseType,
    severity: Severity,
    relevant_transaction_id: str | None,
    transactions: list[Transaction],
) -> bool:
    # Always escalate fraud, duplicates, and agent cash-in disputes.
    if case_type in (
        CaseType.phishing_or_social_engineering,
        CaseType.duplicate_payment,
        CaseType.agent_cash_in_issue,
    ):
        return True
    # Wrong transfer only once we've pinned a specific transaction to dispute.
    if case_type == CaseType.wrong_transfer:
        return relevant_transaction_id is not None
    # Critical or high-value anything → human eyes.
    if severity == Severity.critical or _max_amount(transactions) >= _HIGH_VALUE_BDT:
        return True
    return False


def classify(
    case_type: CaseType,
    transactions: list[Transaction],
    investigation: dict,
) -> dict:
    verdict: EvidenceVerdict = investigation["evidence_verdict"]
    relevant_id = investigation["relevant_transaction_id"]

    severity = _severity(case_type, verdict)
    return {
        "case_type": case_type,
        "department": _DEPARTMENT.get(case_type, Department.customer_support),
        "severity": severity,
        "human_review_required": _human_review(case_type, severity, relevant_id, transactions or []),
    }
