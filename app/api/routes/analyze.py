"""POST /analyze-ticket — thin route: validate request, delegate to analyzer, return validated response."""

from fastapi import APIRouter

from app.schemas.request import AnalyzeTicketRequest
from app.schemas.response import AnalyzeTicketResponse
from app.services.analyzer import analyze_ticket

router = APIRouter()


@router.post("/analyze-ticket", response_model=AnalyzeTicketResponse)
def analyze(request: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    return analyze_ticket(request)
