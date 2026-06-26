"""Schema-contract tests.

Run: pytest -q

These confirm the API contract: /health works, every sample input returns 200,
ticket_id is echoed, and all required output fields are present with valid enum
values. They do not check reasoning correctness — see tests/run_samples.py for
the reasoning-accuracy tracker.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.enums import CaseType, Department, EvidenceVerdict, Severity

client = TestClient(app)
SAMPLES_PATH = Path(__file__).resolve().parents[1] / "SUST_Preli_Sample_Cases.json"

REQUIRED_FIELDS = [
    "ticket_id",
    "relevant_transaction_id",
    "evidence_verdict",
    "case_type",
    "severity",
    "department",
    "agent_summary",
    "recommended_next_action",
    "customer_reply",
    "human_review_required",
]


def load_cases() -> list[dict]:
    data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_all_samples_return_valid_schema():
    for case in load_cases():
        resp = client.post("/analyze-ticket", json=case["input"])
        assert resp.status_code == 200, f"{case['id']} did not return 200"
        body = resp.json()

        # ticket_id echoed.
        assert body["ticket_id"] == case["input"]["ticket_id"], case["id"]

        # all required fields present.
        for field in REQUIRED_FIELDS:
            assert field in body, f"{case['id']} missing {field}"

        # enum values are valid members.
        assert body["evidence_verdict"] in {e.value for e in EvidenceVerdict}, case["id"]
        assert body["case_type"] in {e.value for e in CaseType}, case["id"]
        assert body["severity"] in {e.value for e in Severity}, case["id"]
        assert body["department"] in {e.value for e in Department}, case["id"]

        # relevant_transaction_id is a string or null.
        assert body["relevant_transaction_id"] is None or isinstance(
            body["relevant_transaction_id"], str
        ), case["id"]


def test_malformed_input_does_not_crash():
    # Missing required `complaint` -> controlled 4xx, never a 5xx/crash.
    resp = client.post("/analyze-ticket", json={"ticket_id": "X"})
    assert resp.status_code < 500
