#!/usr/bin/env python3
"""
Test runner: sends all 78 test questions to the NEP API and records PASS/FAIL.
Uses LLM-based validation to verify the returned SQL and answer actually
match the question's intent — not just HTTP 200.
"""
import sys
import os
import json
import time
import requests
import openpyxl
import anthropic

API_URL = "http://localhost:8001/api/chat"
API_KEY = "nep-analytics-internal-2026"
HEADERS = {"Content-Type": "application/json", "x-api-key": API_KEY}

# Anthropic client for answer validation
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_KEY:
    # Try loading from chat_api/.env
    env_path = os.path.join(os.path.dirname(__file__), "chat_api", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    ANTHROPIC_KEY = line.strip().split("=", 1)[1]

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# Load full schema reference for the validator
_schema_path = os.path.join(os.path.dirname(__file__), "docs", "schema_reference.md")
with open(_schema_path, encoding="utf-8") as _f:
    SCHEMA_CONTEXT = _f.read()

VALIDATOR_PROMPT = """You are a strict QA validator for a text-to-SQL analytics system.
Given a user QUESTION, the generated SQL, and the returned ANSWER, determine if:

1. The SQL correctly addresses the question (right tables, columns, filters, aggregations)
2. The answer data makes sense for the question asked
3. No critical errors: wrong table, wrong column, missing filters, wrong JOIN, wrong aggregation

SCHEMA REFERENCE:
{schema}

Respond with EXACTLY this JSON format (no other text):
{{"verdict": "PASS" or "FAIL", "reason": "brief explanation (max 100 chars)"}}

Rules for PASS:
- PASS if the SQL and answer reasonably address the question, even if formatting isn't perfect
- PASS if the answer says "no data found" / "0 results" — that can be a correct answer
- PASS for clarification responses (response_type=clarification) — those are valid
- PASS if SQL uses `created_datetime >= '2025-10-01'` — PostgreSQL auto-casts strings to TIMESTAMP, this is valid
- PASS if SQL uses TO_CHAR(created_datetime, 'YYYY-MM') for grouping — valid on TIMESTAMP columns
- PASS if SQL uses created_datetime for signup date from the user table — created_datetime IS the signup timestamp
- PASS if SQL has extra columns in GROUP BY that aren't in SELECT — PostgreSQL allows this
- PASS if the query returns zero rows but the SQL is structurally correct — empty results are valid answers
- PASS if SQL uses sessiontype = 'expertSession' or 'roundTable' — these ARE the correct camelCase DB values
- PASS if SQL uses particpant_country (with the typo missing 'i') — the typo IS in the actual DB column name
- PASS if SQL uses program = 'liftoff' or program IN ('liftoff', 'liftoff-propel') — program stores ONE value per row (not comma-separated). Each mentor has multiple rows, one per program.
- PASS if SQL uses login_status = 'completedprofile' for profile completion — this IS the standard profile completion check
- PASS if SQL uses GROUP BY participant_user_id ... HAVING COUNT(...) > N — this is valid SQL for finding users with multiple records

Rules for FAIL:
- FAIL if SQL uses wrong table or wrong column for what's being asked
- FAIL if SQL is missing critical WHERE filters the question requires
- FAIL if SQL uses wrong JOIN keys (e.g., user_id instead of userid for activity table)
- FAIL if the answer contains an error message or SQL execution failure
- FAIL if SQL references columns that genuinely don't exist in the specified table (check schema carefully — the schema has ALL columns)
- FAIL if activity_type values don't match exact DB values (e.g., 'journey_explore' instead of 'jounrney_explore')
- FAIL if using program_key in mentor table or program in events table (they're in opposite tables)
- FAIL if JOIN condition uses incompatible types (e.g., user_id = speaker_email)
- FAIL if SQL has a structural logic error that would produce meaningless results (e.g., counting the same metric twice instead of different metrics)
"""


def rule_based_check(sql: str) -> dict:
    """Check SQL for known error patterns. Returns FAIL with reason, or None if no issues found."""
    sql_lower = sql.lower()

    # Check: program_key used in mentor table
    if 'nep_mentor_profiles_sample_data' in sql_lower and 'program_key' in sql_lower:
        # Make sure it's not just in a comment or string
        if 'program_key' in sql_lower.split('nep_mentor_profiles_sample_data')[1][:200] if 'nep_mentor_profiles_sample_data' in sql_lower else False:
            return {"verdict": "FAIL", "reason": "program_key used in mentor table (should be program)"}

    # Check: program used in events table (not program_key)
    # This is tricky — need to find 'program' without 'program_key' near events table
    # Skip this check as it's hard to do reliably

    # Check: user_id = speaker_email (incompatible types)
    if 'speaker_email' in sql_lower and 'user_id' in sql_lower:
        if 'user_id = speaker_email' in sql_lower.replace(' ', '') or \
           'user_id=speaker_email' in sql_lower.replace(' ', '') or \
           'speaker_email = user_id' in sql_lower.replace(' ', ''):
            return {"verdict": "FAIL", "reason": "JOIN on user_id = speaker_email (incompatible types)"}

    # Check: industry_name compared to gapkey (completely different dimensions)
    if 'industry_name' in sql_lower and 'gapkey' in sql_lower:
        if ('=' in sql_lower and 'industry_name' in sql_lower and 'gapkey' in sql_lower):
            # Check for direct comparison
            for pattern in ['industry_name = gapkey', 'gapkey = industry_name',
                           'industry_name=gapkey', 'gapkey=industry_name']:
                if pattern.replace(' ', '') in sql_lower.replace(' ', ''):
                    return {"verdict": "FAIL", "reason": "Comparing industry_name to gapkey (different dimensions)"}

    return None


def validate_answer(question: str, sql: str, answer: str, response_type: str) -> dict:
    """Validate using rule-based checks first, then LLM for complex logic."""
    if not sql and response_type in ("clarification", "general"):
        return {"verdict": "PASS", "reason": "Clarification/general response — no SQL needed"}

    # Rule-based checks first
    if sql:
        rule_result = rule_based_check(sql)
        if rule_result:
            return rule_result

    # LLM validation for complex logic
    user_msg = (
        f"QUESTION: {question}\n\n"
        f"SQL GENERATED:\n```sql\n{sql or 'None'}\n```\n\n"
        f"RESPONSE TYPE: {response_type}\n\n"
        f"ANSWER RETURNED:\n{answer[:1000]}"
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            temperature=0,
            system=VALIDATOR_PROMPT.format(schema=SCHEMA_CONTEXT),
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        # Parse JSON from response
        if "{" in text:
            json_str = text[text.index("{"):text.rindex("}") + 1]
            result = json.loads(json_str)
            return {"verdict": result.get("verdict", "FAIL"), "reason": result.get("reason", "unknown")}
    except Exception as e:
        return {"verdict": "WARN", "reason": f"Validator error: {str(e)[:80]}"}

    return {"verdict": "WARN", "reason": "Could not parse validator response"}


# ─── Main test loop ───────────────────────────────────────────────────────────

# Extract questions from Excel
wb = openpyxl.load_workbook("docs/NEP Test Questions.xlsx", data_only=True)
ws = wb["Test Questions"]
questions = []
for row in ws.iter_rows(min_row=2, max_col=3, values_only=True):
    q = row[2]
    if q and str(q).strip():
        questions.append(str(q).strip())

print(f"Testing {len(questions)} questions against {API_URL}")
print(f"Validation: LLM-based (Claude Haiku) — checks SQL correctness + answer relevance\n")
print(f"{'#':>3}  {'API':5}  {'Valid':5}  {'Time':>6}  Question (first 80 chars)")
print("-" * 120)

results = []
pass_count = 0
fail_count = 0
warn_count = 0

for i, q in enumerate(questions, 1):
    payload = {
        "question": q,
        "session_id": f"test-run-{int(time.time())}-{i}",
        "history": []
    }
    t0 = time.time()
    try:
        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=120)
        elapsed = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "")
            sql = data.get("sql_used", "")
            rtype = data.get("response_type", "")
            api_status = "OK"
            error = ""

            # LLM-based validation
            validation = validate_answer(q, sql, answer, rtype)
            verdict = validation["verdict"]
            val_reason = validation["reason"]

            if verdict == "PASS":
                status = "PASS"
                pass_count += 1
            elif verdict == "WARN":
                status = "WARN"
                warn_count += 1
            else:
                status = "FAIL"
                fail_count += 1
                error = val_reason
        else:
            elapsed = time.time() - t0
            api_status = f"HTTP{resp.status_code}"
            status = "FAIL"
            error = resp.text[:200]
            answer = ""
            sql = ""
            rtype = ""
            verdict = "FAIL"
            val_reason = f"HTTP {resp.status_code}"
            fail_count += 1
    except Exception as e:
        elapsed = time.time() - t0
        api_status = "ERR"
        status = "FAIL"
        error = str(e)[:200]
        answer = ""
        sql = ""
        rtype = ""
        verdict = "FAIL"
        val_reason = str(e)[:80]
        fail_count += 1

    # Color output
    if status == "PASS":
        label = "\033[92mPASS\033[0m"
    elif status == "WARN":
        label = "\033[93mWARN\033[0m"
    else:
        label = "\033[91mFAIL\033[0m"

    print(f"{i:3d}  {api_status:5}  {label}   {elapsed:5.1f}s  {q[:80]}")
    if status == "FAIL":
        print(f"     REASON: {val_reason[:100]}")
    elif status == "WARN":
        print(f"     NOTE: {val_reason[:100]}")

    results.append({
        "num": i,
        "question": q,
        "status": status,
        "api_status": api_status,
        "validation_verdict": verdict,
        "validation_reason": val_reason,
        "response_type": rtype,
        "answer": answer[:500] if answer else "",
        "sql": sql or "",
        "error": error,
        "time_s": round(elapsed, 1)
    })
    sys.stdout.flush()

print(f"\n{'='*80}")
total = len(questions)
print(f"RESULTS: {pass_count}/{total} PASS ({pass_count/total*100:.0f}%)  |  "
      f"{fail_count} FAIL  |  {warn_count} WARN")
print(f"{'='*80}")

# Save results to JSON
with open("test_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Print failures summary
if fail_count > 0:
    print(f"\nFailed questions:")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  Q{r['num']}: {r['question'][:80]}")
            print(f"    Reason: {r['validation_reason'][:120]}")

if warn_count > 0:
    print(f"\nWarnings:")
    for r in results:
        if r["status"] == "WARN":
            print(f"  Q{r['num']}: {r['question'][:80]}")
            print(f"    Note: {r['validation_reason'][:120]}")
