"""Request schema for POST /analyze-ticket. Input is lenient so odd values don't reject the ticket."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_id: str | None = None
    timestamp: str | None = None  # ISO 8601 string
    type: str | None = None  # see TransactionType for allowed values
    amount: float | None = None  # BDT
    counterparty: str | None = None  # phone / merchant ID / agent ID
    status: str | None = None  # see TransactionStatus for allowed values


class AnalyzeTicketRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Required.
    ticket_id: str = Field(..., description="Unique ticket id. Echoed in the response.")
    complaint: str = Field(..., description="Customer complaint text (en / bn / mixed).")

    # Optional context.
    language: str | None = None
    channel: str | None = None
    user_type: str | None = None
    campaign_context: str | None = None
    # Accept a missing field or an explicit null; the analyzer treats both as empty.
    transaction_history: list[Transaction] | None = Field(default=None)
    metadata: dict | None = None
