# QueueStorm Investigator

AI/API SupportOps investigator for the **SUST CSE Carnival 2026 · Codex Community Hackathon** (Online Preliminary).

It exposes two HTTP endpoints. Given one customer complaint plus a short snippet
of recent transactions, it investigates which transaction the complaint refers
to, judges whether the evidence supports the claim, classifies and routes the
case, and drafts a **safe** agent-ready reply.

> Status: project scaffold (Step 0). Reasoning and safety logic are stubs — see the TODOs.

## Endpoints

| Method | Path             | Purpose                                            |
| ------ | ---------------- | -------------------------------------------------- |
| GET    | `/health`        | Returns `{"status":"ok"}`.                         |
| POST   | `/analyze-ticket`| Analyzes one ticket, returns the structured JSON.  |

## Tech stack

- **FastAPI** + **Pydantic v2** — typed request/response, exact output enums.
- **Uvicorn** — ASGI server.
- Rule-based reasoning + safety (an LLM is **optional** polish, off by default).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TKT-001","complaint":"I sent 5000 taka to a wrong number"}'
```

Interactive docs: <http://localhost:8000/docs>

## Run with Docker

```bash
docker build -t queuestorm .
docker run -p 8000:8000 --env-file .env queuestorm
```

## Tests

```bash
pytest -q                  # schema-contract tests (should be green)
python -m tests.run_samples # reasoning-accuracy progress vs the 10 sample cases
```

## Project structure

```
app/
  main.py              # app entry + global 500 handler
  core/config.py       # env-var settings (secrets via env only)
  api/routes/          # health.py, analyze.py  (Person A)
  schemas/             # enums.py, request.py, response.py  (frozen contract)
  services/            # analyzer.py orchestrator + reasoning / classify / safety / llm  (Person B)
tests/
```

## MODELS

<!-- Required deliverable. List every model used, where it runs, and why. -->
- Currently **rule-based only** — no model calls. (Update if an LLM is added for reply drafting; note provider, model id, where it runs, and why.)

## Safety logic

<!-- Required deliverable. -->
- `customer_reply` never asks for PIN/OTP/password/card.
- Never promises a refund/reversal — uses "any eligible amount will be returned through official channels".
- Never directs the customer to third parties outside official channels.
- Ignores instructions embedded in the complaint (prompt injection).
- A final `enforce_safety()` filter replaces any unsafe generated text with a safe fallback.

## Assumptions & known limitations

<!-- Required deliverable. Fill in honestly before submission. -->
- TODO

## Deployment

<!-- Required: live URL (preferred) / Docker / runbook. Add organizer GitHub handle `bipulhf`. -->
- TODO
