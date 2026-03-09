"""
test_schema_scenarios.py
Fires Q21–Q30 natural-language questions at /api/chat and prints a
pass / fail report for each new Section-F scenario.
"""
import json
import uuid
import requests

BASE_URL = "http://localhost:8000"
API_KEY  = "nep-analytics-internal-2026"
HEADERS  = {"Content-Type": "application/json", "x-api-key": API_KEY}
SESSION  = str(uuid.uuid4())

TESTS = [
    # (id, question, expected_keywords_in_sql)
    ("Q21", "How many active mentors are there per industry?",
     ["nep_mentor_profiles_sample_data", "industry_name", "user_status"]),
    ("Q22", "How many mentors cover each startup stage?",
     ["nep_mentor_profiles_sample_data", "stage_name"]),
    ("Q23", "Which industries have the most mentor sessions booked?",
     ["mentor_session", "nep_mentor_profiles_sample_data"]),
    ("Q24", "What is the attendance rate for each completed event?",
     ["nep_master_live_events_data", "ATTENDED", "event_status"]),
    ("Q25", "How many events and attendees does each program and session type have?",
     ["nep_master_live_events_data", "program_key", "sessiontype"]),
    ("Q26", "Which gap areas have the highest no-show rates?",
     ["nep_master_live_events_data", "NOSHOW", "gapkey"]),
    ("Q27", "What is the breakdown of user activity types on the platform?",
     ["nep_liftoffx_data_sample", "activity_type"]),
    ("Q28", "Which traffic sources produce users who attend the most live events?",
     ["nep_master_user_table_sample_data", "ATTENDED", "traffic_source"]),
    ("Q29", "How does engagement compare between Internal and External users?",
     ["user_type", "nep_master_user_table_sample_data"]),
    ("Q30", "What is the profile completion status distribution of registered users?",
     ["nep_master_user_table_sample_data", "login_status"]),
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0
warnings = 0

print(f"\n{BOLD}=== NEP Analytics — Schema Scenario Tests (Q21–Q30) ==={RESET}\n")

for qid, question, keywords in TESTS:
    payload = {
        "session_id": SESSION,
        "question": question,
        "history": []
    }
    try:
        r = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS,
                          json=payload, timeout=60)
        data = r.json()

        if r.status_code != 200:
            print(f"{RED}✗ {qid}{RESET} [{r.status_code}] {data.get('detail', 'error')}")
            print(f"   Question : {question}\n")
            failed += 1
            continue

        sql           = (data.get("sql_used") or "").lower()
        response_type = data.get("response_type", "?")
        answer        = (data.get("answer") or "")[:120]

        missing = [kw for kw in keywords if kw.lower() not in sql]

        if not sql:
            status = f"{YELLOW}⚠ WARN{RESET} (no SQL generated)"
            warnings += 1
        elif missing:
            status = f"{YELLOW}⚠ WARN{RESET} (SQL missing keywords: {missing})"
            warnings += 1
        else:
            status = f"{GREEN}✓ PASS{RESET}"
            passed += 1

        print(f"{BOLD}{qid}{RESET} {status}")
        print(f"   Q         : {question}")
        print(f"   Type      : {response_type}")
        print(f"   Answer    : {answer}{'...' if len(data.get('answer',''))>120 else ''}")
        if sql:
            sql_preview = sql.replace('\n', ' ')[:200]
            print(f"   SQL       : {sql_preview}...")
        print()

    except requests.exceptions.ConnectionError:
        print(f"{RED}✗ {qid} — Connection refused. Is the API running on port 8000?{RESET}\n")
        failed += 1
    except Exception as e:
        print(f"{RED}✗ {qid} — Unexpected error: {e}{RESET}\n")
        failed += 1

total = passed + failed + warnings
print(f"{BOLD}{'='*55}{RESET}")
print(f"Results: {GREEN}{passed} passed{RESET}  {YELLOW}{warnings} warnings{RESET}  {RED}{failed} failed{RESET}  / {total} total")
print(f"{BOLD}{'='*55}{RESET}\n")
