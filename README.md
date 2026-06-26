# QueueStorm Investigator

AI/API SupportOps service for the **SUST CSE Carnival 2026 · Codex Community Hackathon** (Online Preliminary Round).

It exposes two HTTP endpoints. Given one customer complaint plus a short snippet
of the customer's recent transactions, it **investigates** which transaction the
complaint is really about, judges whether the evidence supports the claim,
classifies and routes the case to the right department, and drafts a **safe**
agent-ready reply — without ever asking for credentials or promising a refund it
cannot authorize.

The service is a support **copilot**, not an autonomous financial decision maker.
It escalates ambiguous, high-risk, and disputed cases for human review.

---

## Endpoints

| Method | Path             | Purpose                                                        |
| ------ | ---------------- | -------------------------------------------------------------- |
| GET    | `/health`        | Returns `{"status":"ok"}`. Liveness probe.                     |
| POST   | `/analyze-ticket`| Accepts one ticket, returns the structured investigation JSON. |

### HTTP status codes

| Code | Meaning                                                                 |
| ---- | ---------------------------------------------------------------------- |
| 200  | Successful analysis; body matches the output schema.                   |
| 422  | Schema-valid request rejected by validation (e.g. missing `complaint`).|
| 400  | Malformed input.                                                       |
| 500  | Internal error. Body carries a non-sensitive message (no stack traces).|

The service never crashes on bad input — it returns a controlled error instead.

---

## Tech stack

- **Python 3.12**
- **FastAPI** — HTTP layer and request/response validation.
- **Pydantic v2** — typed schema with strict output enums.
- **Uvicorn** — ASGI server.
- **pydantic-settings** — environment-variable configuration.

No database, no external state. The service is a pure function: one request in,
one structured response out.

---

## AI approach

**This submission uses no LLM and makes no external AI/API calls — the entire
pipeline is rule-based and deterministic.** The investigation logic (transaction
matching, evidence verdict, classification, routing, escalation) and every piece
of generated text are implemented in plain Python. This keeps every decision
explainable, fast (well under the 30-second limit), free, and fully reproducible,
with no API keys, no cost, and no network dependency at request time.

How a request is processed (`app/services/`):

1. **`signals.py`** — reads the complaint text: extracts the money amount(s)
   mentioned (handles Bangla digits like `২০০০`, ignores phone-number-length
   digit runs), detects the language, and classifies the `case_type` from
   prioritised keyword patterns (English and Bangla).
2. **`reasoning.py`** — matches the complaint's amount(s) against the supplied
   transaction history to pick `relevant_transaction_id` and the
   `evidence_verdict`. It deliberately returns `null` /  `insufficient_data` when
   nothing matches, the complaint is vague, or several transactions to different
   recipients plausibly match — it does not guess.
3. **`classify.py`** — maps `case_type` to the owning `department`, assigns
   `severity`, and decides `human_review_required`.
4. **`replies.py` + `safety.py`** — `replies.py` holds the per-case, bilingual
   text templates and builds the `agent_summary` (content); `safety.py` composes
   them into `agent_summary`, `recommended_next_action`, and `customer_reply`,
   then runs a final `enforce_safety()` filter over the reply (policy).

**No LLM is used in this submission.** The codebase includes a disabled
extension hook (`app/services/llm.py`) that *could* optionally refine wording in
future, but it is switched off, needs no API key, and is never called — every
response is produced entirely by the rule-based pipeline above.

### Evidence reasoning highlights

- **Wrong transfer to a repeat recipient** → flagged `inconsistent` (the data
  contradicts the "wrong number" claim) and escalated.
- **Duplicate payment** → two or more identical (amount + counterparty) payments
  are the evidence; the service points at the later one.
- **Ambiguous match** (several transactions of the same amount to different
  recipients) → `null` / `insufficient_data`, asks the customer to clarify.
- **Phishing / OTP report** → `critical`, routed to `fraud_risk`, escalated, even
  with an empty transaction history.

---

## Safety logic

Fintech safety is a hard requirement, so the guardrails live in code rather than
relying on a model's good behaviour. The `customer_reply`:

- **Never** asks for PIN, OTP, password, or full card number.
- **Never** promises a refund, reversal, or account unblock. It uses neutral
  language such as *"any eligible amount will be returned through official
  channels"* instead of *"we will refund you"*.
- **Never** directs the customer to a third party outside official channels.
- **Ignores instructions embedded in the complaint text** (prompt-injection
  attempts do not override the service's rules).
- Responds in the customer's language (Bangla in → Bangla out).

Replies are built from hand-written, vetted templates per `case_type` (English
and Bangla) — there is no free-form generation, so there is no place for unsafe
text to originate. A final `enforce_safety()` filter still scans the outgoing
reply (credential-ask, refund-promise, and third-party-redirect patterns, with
negation handling so a "do not share your PIN" warning is not mis-flagged); if
anything trips, the reply is replaced with a guaranteed-safe fallback in the
right language. The complaint text is never echoed into the reply, which neutralises
prompt-injection attempts.

The `agent_summary` states the matched transaction and its amount plus the
evidence verdict (e.g. *"Identified transaction TXN-9101 (5,000 BDT). Evidence
verdict: consistent."*) for fast agent triage. Ambiguous evidence, disputes,
fraud reports, and high-value cases set `human_review_required: true`.

---

## Request schema (`POST /analyze-ticket`)

| Field                 | Type   | Required | Notes                                              |
| --------------------- | ------ | -------- | -------------------------------------------------- |
| `ticket_id`           | string | yes      | Echoed in the response.                            |
| `complaint`           | string | yes      | English, Bangla, or mixed.                         |
| `language`            | string | no       | `en` / `bn` / `mixed`.                             |
| `channel`             | string | no       | `in_app_chat` / `call_center` / `email` / `merchant_portal` / `field_agent`. |
| `user_type`           | string | no       | `customer` / `merchant` / `agent` / `unknown`.     |
| `campaign_context`    | string | no       | Campaign identifier.                               |
| `transaction_history` | array  | no       | 0–5 recent transactions (see below). May be empty. |
| `metadata`            | object | no       | Extra simulated context.                           |

Each transaction: `transaction_id`, `timestamp` (ISO 8601), `type`
(`transfer` / `payment` / `cash_in` / `cash_out` / `settlement` / `refund`),
`amount` (BDT), `counterparty`, `status`
(`completed` / `failed` / `pending` / `reversed`).

Input fields are validated leniently so an unusual value never rejects an
otherwise-analyzable ticket.

## Response schema

| Field                     | Type           | Notes                                                       |
| ------------------------- | -------------- | ----------------------------------------------------------- |
| `ticket_id`               | string         | Matches the request.                                        |
| `relevant_transaction_id` | string \| null | The matched transaction, or `null` if none matches.         |
| `evidence_verdict`        | enum           | `consistent` / `inconsistent` / `insufficient_data`.        |
| `case_type`               | enum           | `wrong_transfer` / `payment_failed` / `refund_request` / `duplicate_payment` / `merchant_settlement_delay` / `agent_cash_in_issue` / `phishing_or_social_engineering` / `other`. |
| `severity`                | enum           | `low` / `medium` / `high` / `critical`.                     |
| `department`              | enum           | `customer_support` / `dispute_resolution` / `payments_ops` / `merchant_operations` / `agent_operations` / `fraud_risk`. |
| `agent_summary`           | string         | Concise case summary for the agent.                         |
| `recommended_next_action` | string         | Suggested operational step.                                 |
| `customer_reply`          | string         | Safe official reply.                                        |
| `human_review_required`   | boolean        | True for disputes, fraud, high-value, or ambiguous cases.   |
| `confidence`              | number \| null | Optional, 0–1.                                              |
| `reason_codes`            | array \| null  | Optional short labels supporting the decision.              |

All enum values are emitted exactly as listed above.

---

## Setup and run

### Local

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Health: <http://localhost:8000/health>
- Interactive docs: <http://localhost:8000/docs>

### Docker

```bash
docker build -t queuestorm .
docker run -p 8000:8000 queuestorm
```

The service then responds on <http://localhost:8000>. No environment file is
needed — the service runs with defaults and requires no API key. To enable the
optional LLM layer, pass variables explicitly, e.g.
`docker run -p 8000:8000 -e LLM_ENABLED=true -e OPENAI_API_KEY=... queuestorm`.

The image is built on `python:3.12-slim`, runs on CPU only, binds `0.0.0.0`, and
reads secrets from environment variables (never baked into the image).

---

## Environment variables

Copy `.env.example` to `.env`. All values are optional — the service runs with
defaults and **requires no API key**.

| Variable         | Default | Purpose                                          |
| ---------------- | ------- | ------------------------------------------------ |
| `LLM_ENABLED`    | `false` | Toggle the optional LLM reply-drafting layer.    |
| `OPENAI_API_KEY` | —       | Provider key, only if `LLM_ENABLED=true`.        |
| `MODEL_NAME`     | —       | Model id, only if `LLM_ENABLED=true`.            |
| `PORT`           | `8000`  | Service port.                                    |

No real secrets are committed to the repository.

---

## Testing

```bash
pytest -q                    # full suite: contract + reliability + safety (28 tests)
python -m tests.run_samples  # reasoning accuracy vs the 10 public sample cases (no server needed)
```

The pytest suite covers three areas:

- **Contract** (`test_samples.py`) — `/health`, required fields, exact enum
  values, and malformed input returning a controlled 4xx.
- **Reliability** (`test_reliability.py`) — empty / null / missing fields,
  malformed JSON, oversized and Bangla input, and prompt-injection text: the
  service must never return 5xx or crash.
- **Safety** (`test_safety.py`) — `customer_reply` never asks for credentials or
  promises a refund, prompt-injection is ignored, Bangla complaints get a Bangla
  reply, and `agent_summary` quotes the matched transaction's amount.

A live-HTTP smoke tester is also provided:

```bash
# in one terminal
uvicorn app.main:app --host 0.0.0.0 --port 8000
# in another
./test.sh summary            # all 10 cases vs expected output, pass/fail tally
./test.sh all                # full request/response detail for every case
./test.sh                    # interactive menu
```

The service reproduces the expected decision fields
(`relevant_transaction_id`, `evidence_verdict`, `case_type`, `department`,
`severity`, `human_review_required`) on all 10 public sample cases.

---

## MODELS

**No models are used. This is a 100% rule-based solution** — no LLM, no local
model, no external AI/API calls, no GPU, no API keys.

| Model | Used? | Where it runs | Notes |
| ----- | ----- | ------------- | ----- |
| None — rule-based Python | **Yes (only this)** | In-process, CPU | The investigation, classification, routing, text generation, and safety guardrails are deterministic Python. This produces correct, schema-valid, safe responses while staying fast, free, and fully reproducible. |
| External / local LLM | **No** | — | A disabled hook exists at `app/services/llm.py` for a possible future option, but it is off, needs no key, and is never invoked in this submission. |

---

## Sample request and response

Request:

```json
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today. Please help me get my money back.",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "transaction_history": [
    { "transaction_id": "TXN-9101", "timestamp": "2026-04-14T14:08:22Z", "type": "transfer", "amount": 5000, "counterparty": "+8801719876543", "status": "completed" },
    { "transaction_id": "TXN-9087", "timestamp": "2026-04-13T18:12:00Z", "type": "cash_in", "amount": 10000, "counterparty": "AGENT-512", "status": "completed" }
  ]
}
```

Response:

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports a wrong transfer. Identified transaction TXN-9101 (5,000 BDT). Evidence verdict: consistent.",
  "recommended_next_action": "Verify transaction TXN-9101 with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Our dispute resolution team will review the case and contact you through official support channels. Please do not share your PIN or OTP with anyone.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer", "transaction_match"]
}
```

---

## Project structure

```
app/
  main.py              # app entry + global error handler
  core/config.py       # environment configuration
  api/routes/          # health.py, analyze.py
  schemas/             # enums.py, request.py, response.py
  services/            # analyzer.py (orchestrator) + signals / reasoning / classify / replies / safety / llm
tests/
  test_samples.py      # schema-contract tests
  test_reliability.py  # edge-case / malformed-input robustness
  test_safety.py       # customer_reply guardrail tests
  run_samples.py       # reasoning accuracy tracker
test.sh                # live-HTTP smoke tester
Dockerfile
requirements.txt
.env.example
```

Request flow: `routes/analyze.py` → `services/analyzer.py` → `signals` →
`reasoning` → `classify` → `safety` (composes `replies` templates, then
`enforce_safety`) → validated response.

---

## Assumptions

- All complaints and transaction histories are synthetic; no real customer or
  payment-system integration is involved.
- A complaint refers to a transaction whose amount is mentioned in the text;
  amount is the primary matching signal.
- When the language is not declared, it is inferred from the script of the text.
- The transaction history provided in the request is the only evidence available;
  the service does not fetch or store any data.

## Known limitations

- Transaction matching is amount-driven. A complaint that omits the amount, or
  references a transaction not present in the supplied history, resolves to
  `insufficient_data` by design rather than a guess.
- Time-phrase parsing (e.g. "around 2pm") is not used as a matching signal; only
  amount and recipient patterns are.
- Keyword-based `case_type` detection covers the common phrasings in English and
  Bangla; highly unusual phrasings may fall back to `other`.
- No LLM is used; the `llm.py` hook is disabled and never called in this submission.

---

## Deployment

- **Primary — Live URL:** <https://sust-hackathon-five.vercel.app> — public base
  URL exposing `/health` and `/analyze-ticket` (deployed on Vercel).
- **Re-deploy fallback (runbook) — Docker:** if the live URL is unreachable, the
  service can be rebuilt and run from this repository with no extra setup:

  ```bash
  docker build -t queuestorm .
  docker run -p 8000:8000 queuestorm
  ```

  It then serves `/health` and `/analyze-ticket` on port 8000. No `.env`, API
  key, GPU, or external dependency is required.
- **Local:** alternatively, `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  after installing `requirements.txt`.

No login or private network access is required to reach the endpoints.
