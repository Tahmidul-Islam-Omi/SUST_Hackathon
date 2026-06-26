"""POST /analyze-ticket — the main endpoint.

The route is thin on purpose: it validates the request (via the schema),
delegates ALL logic to the analyzer service, and returns the validated
response. Any unexpected error is caught by the global 500 handler in main.py
so the service never crashes or leaks internals.
"""

from fastapi import APIRouter

from app.schemas.request import AnalyzeTicketRequest
from app.schemas.response import AnalyzeTicketResponse
from app.services.analyzer import analyze_ticket

router = APIRouter()


@router.post("/analyze-ticket", response_model=AnalyzeTicketResponse)
def analyze(request: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    return analyze_ticket(request)
