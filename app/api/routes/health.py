"""GET /health — liveness probe. Must return {"status":"ok"} fast."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
