"""Application entry point.

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Wires the two required endpoints and installs a global exception handler so the
service returns a controlled, non-sensitive 500 instead of crashing or leaking
stack traces / secrets (a hard requirement in the spec).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import analyze, health

app = FastAPI(
    title="QueueStorm Investigator",
    description="AI/API SupportOps investigator for digital finance complaints.",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(analyze.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak the exception message, stack trace, tokens, or secrets.
    return JSONResponse(
        status_code=500,
        content={"error": "Internal error while processing the ticket."},
    )
