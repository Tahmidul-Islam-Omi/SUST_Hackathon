"""Reasoning-accuracy progress tracker.

Run: python -m tests.run_samples

Hits every sample case and compares the KEY decision fields against the
expected_output, printing a PASS/FAIL table. With stub logic most rows FAIL —
that is expected. Person B's Phase 3/4 goal is to turn these green. This is a
dev tool, not a pytest test (the hidden judge set differs from these samples).
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
SAMPLES_PATH = Path(__file__).resolve().parents[1] / "SUST_Preli_Sample_Cases.json"

# The fields that actually carry the evidence-reasoning score.
KEY_FIELDS = ["relevant_transaction_id", "evidence_verdict", "case_type", "department"]


def main() -> None:
    data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    passed = 0

    for case in cases:
        resp = client.post("/analyze-ticket", json=case["input"])
        got = resp.json()
        exp = case["expected_output"]

        diffs = [f for f in KEY_FIELDS if got.get(f) != exp.get(f)]
        if not diffs:
            passed += 1
            print(f"{case['id']:<12} PASS")
        else:
            detail = "  ".join(
                f"{f}: got={got.get(f)!r} exp={exp.get(f)!r}" for f in diffs
            )
            print(f"{case['id']:<12} FAIL  {detail}")

    print(f"\n{passed}/{len(cases)} key-field matches")


if __name__ == "__main__":
    main()
