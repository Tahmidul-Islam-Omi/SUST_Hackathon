"""Evidence reasoning — the 35-point core. OWNER: Person B (Phase 3).

Goal: given the complaint text and the recent transactions, decide WHICH
transaction the complaint is about and whether the evidence backs the claim.

Return contract (dict):
    {
        "relevant_transaction_id": str | None,
        "evidence_verdict": EvidenceVerdict,
        "confidence": float,            # 0..1
        "reason_codes": list[str],
    }

Key rules to implement (see the 10 sample cases):
  - Match by amount + approximate time + transaction type.
  - relevant_transaction_id = None when nothing matches, the complaint is vague,
    OR multiple transactions plausibly match (don't guess!).
  - evidence_verdict:
        consistent        -> data supports the complaint
        inconsistent      -> data contradicts it (e.g. repeated prior transfers
                             to the "wrong" recipient)
        insufficient_data -> can't tell / vague / ambiguous / empty history
"""

from __future__ import annotations

from app.schemas.enums import EvidenceVerdict
from app.schemas.request import Transaction


def investigate(complaint: str, transactions: list[Transaction]) -> dict:
    # TODO(Person B, Phase 3): real transaction matching + verdict logic.
    # Safe placeholder: never guesses a transaction.
    return {
        "relevant_transaction_id": None,
        "evidence_verdict": EvidenceVerdict.insufficient_data,
        "confidence": 0.5,
        "reason_codes": ["stub_not_implemented"],
    }
