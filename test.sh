#!/usr/bin/env bash
# Manual tester for QueueStorm Investigator.
# Run while the FastAPI app is up:  uvicorn app.main:app --host 0.0.0.0 --port 8000
#
# Usage:
#   ./test.sh                  # interactive menu (prompts 1..11 / q)
#   ./test.sh 1                # run just health check
#   ./test.sh 5                # run just SAMPLE-04 (refund, change of mind)
#   ./test.sh all              # run health + all 10 cases
#
# Menu mapping (1-indexed):
#   1   = GET /health
#   2   = SAMPLE-01  wrong transfer, matches
#   3   = SAMPLE-02  wrong transfer, repeat recipient
#   4   = SAMPLE-03  failed payment, balance cut
#   5   = SAMPLE-04  refund, change of mind
#   6   = SAMPLE-05  phishing / OTP call
#   7   = SAMPLE-06  vague complaint
#   8   = SAMPLE-07  agent cash-in (Bangla)
#   9   = SAMPLE-08  ambiguous (3 x 1000)
#   10  = SAMPLE-09  merchant settlement delay
#   11  = SAMPLE-10  duplicate payment
#   q   = quit

set -u

HOST="${HOST:-http://localhost:8000}"
SAMPLES="${SAMPLES:-SUST_Preli_Sample_Cases.json}"

# ---------- helpers ----------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

check_server() {
  if ! curl -fsS --max-time 3 "$HOST/health" >/dev/null 2>&1; then
    die "Server not reachable at $HOST. Start it first: uvicorn app.main:app --host 0.0.0.0 --port 8000"
  fi
}

run_health() {
  echo "==> GET $HOST/health"
  local resp
  resp=$(curl -fsS --max-time 10 -w "\nHTTP_STATUS:%{http_code}\n" "$HOST/health") || die "health request failed"
  echo "$resp"
  if echo "$resp" | grep -q '"status":"ok"'; then
    echo "[OK] /health returned {\"status\":\"ok\"}"
  else
    echo "[WARN] /health did not return ok"
  fi
}

run_case() {
  local idx="$1"   # 1..10
  echo "==> SAMPLE-$(printf '%02d' "$idx")  -> POST $HOST/analyze-ticket"
  python3 - "$SAMPLES" "$idx" "$HOST" <<'PY'
import json, sys, urllib.request

path, idx, host = sys.argv[1], int(sys.argv[2]), sys.argv[3]
data = json.load(open(path))
case = next(c for c in data["cases"] if c["id"] == f"SAMPLE-{idx:02d}")

req = urllib.request.Request(
    f"{host}/analyze-ticket",
    data=json.dumps(case["input"]).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8")
        print(f"HTTP {r.status}")
        got = json.loads(body)
        print(json.dumps(got, indent=2, ensure_ascii=False))

        exp = case["expected_output"]
        key = ["relevant_transaction_id", "evidence_verdict", "case_type", "department"]
        diffs = [f"{f}: got={got.get(f)!r}  exp={exp.get(f)!r}" for f in key if got.get(f) != exp.get(f)]
        print()
        if diffs:
            print("KEY-FIELD DIFFS (vs expected_output in sample JSON):")
            for d in diffs:
                print("  -", d)
        else:
            print("KEY FIELDS MATCH EXPECTED OUTPUT.")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read().decode("utf-8", errors="replace"))
PY
}

show_menu() {
  cat <<'MENU'

  QueueStorm Investigator — manual tester
  ----------------------------------------
    1  -> GET /health
    2  -> SAMPLE-01  wrong transfer (matches)
    3  -> SAMPLE-02  wrong transfer (repeat recipient)
    4  -> SAMPLE-03  failed payment, balance cut
    5  -> SAMPLE-04  refund, change of mind
    6  -> SAMPLE-05  phishing / OTP call
    7  -> SAMPLE-06  vague complaint
    8  -> SAMPLE-07  agent cash-in (Bangla)
    9  -> SAMPLE-08  ambiguous (3 x 1000)
   10  -> SAMPLE-09  merchant settlement delay
   11  -> SAMPLE-10  duplicate payment
    q  -> quit
MENU
}

interactive() {
  check_server
  while true; do
    show_menu
    printf "Choose (1-11, q): "
    read -r choice
    case "$choice" in
      q|Q) echo "Bye."; exit 0 ;;
      1)   run_health ;;
      [2-9]|10|11)
        idx=$(( 10#$choice - 1 ))
        run_case "$idx"
        ;;
      *) echo "Invalid choice: $choice" ;;
    esac
    echo
  done
}

# ---------- main -------------------------------------------------------------
case "${1:-}" in
  "")        interactive ;;
  1|health)  check_server; run_health ;;
  [2-9]|10|11)
             check_server
             idx=$(( 10#$1 - 1 ))
             run_case "$idx"
             ;;
  all)       check_server; run_health; for i in 1 2 3 4 5 6 7 8 9 10; do run_case "$i"; echo; done ;;
  *)         echo "Unknown option: $1" >&2; exit 2 ;;
esac