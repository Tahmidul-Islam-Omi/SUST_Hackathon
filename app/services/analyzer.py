"""Orchestrator. The route calls only `analyze_ticket(request)`, which runs the
three stages and assembles the response:

    1. reasoning.investigate  -> relevant_transaction_id, evidence_verdict
    2. classify.classify      -> case_type, department, severity, review flag
    3. safety.build_replies   -> agent_summary, next_action, safe customer_reply
"""

from __future__ import annotations

from app.schemas.request import AnalyzeTicketRequest
from app.schemas.response import AnalyzeTicketResponse
from app.services import classify, reasoning, safety, signals


def analyze_ticket(request: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    transactions = request.transaction_history or []

    # Detect case_type once so reasoning and classify can't disagree.
    case_type = signals.detect_case_type(request.complaint, transactions)

    # Stage 1 — evidence reasoning.
    investigation = reasoning.investigate(request.complaint, transactions, case_type)

    # Stage 2 — classification & routing.
    classification = classify.classify(case_type, transactions, investigation)

    # Stage 3 — safe, agent-ready text.
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
