"""Orchestrator — the single entry point Person B owns.

The route calls only `analyze_ticket(request)`. This function ties the three
logic stages together and assembles the final response:

    1. reasoning.investigate(...)  -> relevant_transaction_id, evidence_verdict
    2. classify.classify(...)      -> case_type, department, severity, review flag
    3. safety.build_replies(...)   -> agent_summary, next_action, SAFE customer_reply

NOTE: right now every stage returns a safe, schema-valid STUB so the whole app
runs and deploys today. Person B fills in the real logic stage by stage
(Phase 3 reasoning, then Phase 4 safety) without ever touching the route layer.
"""

from __future__ import annotations

from app.schemas.request import AnalyzeTicketRequest
from app.schemas.response import AnalyzeTicketResponse
from app.services import classify, reasoning, safety


def analyze_ticket(request: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    transactions = request.transaction_history or []

    # Stage 1 — evidence reasoning (Phase 3).
    investigation = reasoning.investigate(request.complaint, transactions)

    # Stage 2 — classification & routing (Phase 3).
    classification = classify.classify(
        request.complaint,
        transactions,
        investigation["relevant_transaction_id"],
    )

    # Stage 3 — safe, agent-ready text (Phase 4).
    replies = safety.build_replies(request, investigation, classification)

    return AnalyzeTicketResponse(
        ticket_id=request.ticket_id,
        relevant_transaction_id=investigation["relevant_transaction_id"],
        evidence_verdict=investigation["evidence_verdict"],
        case_type=classification["case_type"],
        severity=classification["severity"],
        department=classification["department"],
        agent_summary=replies["agent_summary"],
        recommended_next_action=replies["recommended_next_action"],
        customer_reply=replies["customer_reply"],
        human_review_required=classification["human_review_required"],
        confidence=investigation.get("confidence"),
        reason_codes=investigation.get("reason_codes"),
    )
