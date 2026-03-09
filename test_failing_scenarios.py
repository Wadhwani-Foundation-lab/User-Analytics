"""
test_failing_scenarios.py
Re-tests only the 4 scenarios that failed (Q26-Q29).
"""
import json
import uuid
import requests

BASE_URL = "http://localhost:8000"
API_KEY  = "nep-analytics-internal-2026"
HEADERS  = {"Content-Type": "application/json", "x-api-key": API_KEY}
SESSION  = str(uuid.uuid4())

TESTS = [
    ("Q26", "Which gap areas have the highest no-show rates?",
     ["nep_master_live_events_data", "noshow", "gapkey"]),
    ("Q27", "What is the breakdown of user activity types on the platform?",
     ["nep_liftoffx_data_sample", "activity_type"]),
    ("Q28", "Which traffic sources produce users who attend the most live events?",
     ["nep_master_user_table_sample_data", "attended", "traffic_source"]),
    ("Q29", "How does engagement compare between Internal and External users?",
     ["user_type", "nep_master_user_table_sample_data"]),
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0

print(f"\n{BOLD}=== Re-test: Q26–Q29 (previously failing) ==={RESET}\n")

for qid, question, keywords in TESTS:
    payload = {"session_id": SESSION, "question": question, "history": []}
    try:
        r = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS,
                          json=payload, timeout=60)
        data = r.json()

        if r.status_code != 200:
            print(f"{RED}✗ {qid}{RESET} [{r.status_code}] {data.get('detail','error')}")
            print(f"   Q: {question}\n")
            failed += 1
            continue

        sql           = (data.get("sql_used") or "").lower()
        response_type = data.get("response_type", "?")
        answer        = (data.get("answer") or "")[:120]
        missing       = [kw for kw in keywords if kw.lower() not in sql]

        if not sql:
            status = f"{YELLOW}⚠ WARN{RESET} (no SQL generated)"
            failed += 1
        elif missing:
            status = f"{YELLOW}⚠ WARN{RESET} (SQL missing: {missing})"
            failed += 1
        else:
            status = f"{GREEN}✓ PASS{RESET}"
            passed += 1

        print(f"{BOLD}{qid}{RESET} {status}")
        print(f"   Q    : {question}")
        print(f"   Type : {response_type}")
        print(f"   Ans  : {answer}")
        if sql:
            print(f"   SQL  : {sql.replace(chr(10),' ')[:200]}...")
        print()

    except Exception as e:
        print(f"{RED}✗ {qid} — {e}{RESET}\n")
        failed += 1

print(f"{BOLD}{'='*50}{RESET}")
print(f"Re-test: {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}")
print(f"{BOLD}{'='*50}{RESET}\n")
