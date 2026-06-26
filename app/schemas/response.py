"""Response schema for POST /analyze-ticket. 10 required fields, 2 optional; output enums are strict."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import CaseType, Department, EvidenceVerdict, Severity


class AnalyzeTicketResponse(BaseModel):
    # Echoed from the request.
    ticket_id: str

    # The investigation result.
    relevant_transaction_id: str | None = Field(
        ..., description="Matching transaction id, or null if none in history matches."
    )
    evidence_verdict: EvidenceVerdict

    # Classification & routing.
    case_type: CaseType
    severity: Severity
    department: Department

    # Agent-facing + customer-facing text.
    agent_summary: str
    recommended_next_action: str
    customer_reply: str

    # Escalation flag.
    human_review_required: bool

    # Optional.
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason_codes: list[str] | None = None
