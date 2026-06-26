"""Case classification, routing & severity. OWNER: Person B (Phase 3).

Return contract (dict):
    {
        "case_type": CaseType,
        "department": Department,
        "severity": Severity,
        "human_review_required": bool,
    }

Mapping hints (from the problem statement taxonomy):
  case_type          -> department
  -----------------------------------------
  wrong_transfer     -> dispute_resolution
  payment_failed     -> payments_ops
  duplicate_payment  -> payments_ops
  refund_request     -> customer_support (or dispute_resolution if contested)
  merchant_settlement_delay -> merchant_operations
  agent_cash_in_issue       -> agent_operations
  phishing_or_social_engineering -> fraud_risk   (severity=critical)
  other              -> customer_support

human_review_required = True for disputes, fraud/phishing, high-value, or
ambiguous evidence; False for clear low-severity informational cases.
"""

from __future__ import annotations

from app.schemas.enums import CaseType, Department, Severity
from app.schemas.request import Transaction


def classify(
    complaint: str,
    transactions: list[Transaction],
    relevant_transaction_id: str | None,
) -> dict:
    # TODO(Person B, Phase 3): keyword + transaction-type driven classification.
    # Safe placeholder: lowest-risk routing.
    return {
        "case_type": CaseType.other,
        "department": Department.customer_support,
        "severity": Severity.low,
        "human_review_required": False,
    }
