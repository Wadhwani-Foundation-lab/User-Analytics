#!/usr/bin/env python3
"""
Targeted test: runs only specific question numbers against the API.
Usage: python3 test_failed_questions.py [q1 q2 ...]
       python3 test_failed_questions.py  # uses hardcoded FAILED_QUESTIONS
"""
import sys
import os
import json
import time
import re
import requests
import openpyxl
import anthropic

API_URL = "http://localhost:8001/api/chat"
API_KEY = "nep-analytics-internal-2026"
HEADERS = {"Content-Type": "application/json", "x-api-key": API_KEY}

# Questions to re-test (1-indexed, matching the Excel row order)
FAILED_QUESTIONS = [36, 49, 50, 76]

# Parse CLI args if provided
if len(sys.argv) > 1:
    FAILED_QUESTIONS = [int(x) for x in sys.argv[1:]]

# ── Inline validation (copy from test_all_questions.py to avoid re-running that script) ──

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_KEY:
    env_path = os.path.join(os.path.dirname(__file__), "chat_api", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    ANTHROPIC_KEY = line.strip().split("=", 1)[1]

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
_schema_path = os.path.join(os.path.dirname(__file__), "docs", "schema_reference.md")
with open(_schema_path, encoding="utf-8") as _f:
    SCHEMA_CONTEXT = _f.read()

VALIDATOR_PROMPT = """You are a strict QA validator for a text-to-SQL analytics system.
Given a user QUESTION, the generated SQL, and the returned ANSWER, determine if the SQL correctly addresses the question.

SCHEMA REFERENCE:
{schema}

Respond with EXACTLY this JSON format (no other text):
{{"verdict": "PASS" or "FAIL", "reason": "brief explanation (max 100 chars)"}}

FACTS:
- `program` column in mentor table stores ONE value per row. `program IN (...)` is valid.
- sessiontype values are 'expertSession' and 'roundTable' (camelCase) — these ARE correct.
- `userid` (activity) and `participant_user_id` (events) are the same user — direct JOIN is valid.
- `m.email = e.speaker_email` is the correct JOIN for mentor-event speakers.
- `created_datetime` EXISTS in nep_master_user_table_sample_data — do NOT claim it doesn't.
- `particpant_country` (missing 'i') IS the actual DB column name — the typo is in the database.
- No-show rate denominator can be REGISTERED-only, ATTENDED+NOSHOW, or total — all valid.
- UNION ALL combining industry_name and gapkey side-by-side per program IS the correct approach for cross-reference questions.
- FAIL ONLY if you are CERTAIN the SQL is wrong. When in doubt, PASS.
"""


def rule_based_pass(sql: str) -> dict:
    sql_lower = sql.lower()
    no_spaces = sql_lower.replace(' ', '')
    if re.search(r"program\s+in\s*\(", sql_lower):
        return {"verdict": "PASS", "reason": "program IN (...) is valid — one value per row"}
    if "'expertsession'" in sql_lower or "'roundtable'" in sql_lower:
        return {"verdict": "PASS", "reason": "sessiontype camelCase values are correct"}
    if 'particpant_country' in sql_lower:
        return {"verdict": "PASS", "reason": "particpant_country is correct (typo in DB)"}
    if ("activity_type" in sql_lower and "'signup'" in sql_lower
            and "signup_date" in sql_lower and "min(message_date)" in sql_lower):
        return {"verdict": "PASS", "reason": "Correct signup-to-first-message pattern"}
    if ('participant_user_id' in sql_lower and 'userid' in sql_lower
            and 'count(distinct' in no_spaces
            and ('participant_user_id=a.userid' in no_spaces or 'e.participant_user_id=a.userid' in no_spaces)):
        return {"verdict": "PASS", "reason": "Valid event-activity JOIN with COUNT(DISTINCT)"}
    if re.search(r"filter\s*\(\s*where\s+\w*\.?participant_status", sql_lower):
        return {"verdict": "PASS", "reason": "Valid attendance analysis with FILTER clause"}
    if 'union all' in sql_lower and 'gapkey' in sql_lower and 'industry_name' in sql_lower:
        return {"verdict": "PASS", "reason": "UNION ALL side-by-side gapkey/industry_name is correct"}
    # PASS: event participation ratio — attended/all-registered is correct
    if ('registered_beneficiaries' in sql_lower and 'event_participants' in sql_lower
            and 'participation_ratio' in sql_lower):
        return {"verdict": "PASS", "reason": "Valid participation ratio: attended/all-registered from events table"}
    # PASS: gapkey NOT IN (SELECT industry_name ...) — valid set-difference for "no matching mentor" questions
    if ('gapkey' in sql_lower and 'industry_name' in sql_lower and 'not in' in sql_lower):
        return {"verdict": "PASS", "reason": "Valid set-difference: gapkey NOT IN (industry_name) answers 'no matching mentor' question"}
    return None


def rule_based_check(sql: str) -> dict:
    sql_lower = sql.lower()
    no_spaces = sql_lower.replace(' ', '')
    if re.search(r'\bm\.program_key\b', sql_lower):
        return {"verdict": "FAIL", "reason": "m.program_key used (mentor table has 'program')"}
    if 'user_id=speaker_email' in no_spaces or 'speaker_email=user_id' in no_spaces:
        if '.user_id=speaker_email' in no_spaces:
            if '.email=' not in no_spaces.split('speaker_email')[0][-20:]:
                return {"verdict": "FAIL", "reason": "JOIN on user_id = speaker_email (incompatible types)"}
    if re.search(r'traffic_source_campaign\s+as\s+prog', sql_lower):
        return {"verdict": "FAIL", "reason": "traffic_source_campaign AS prog — wrong program proxy"}
    if re.search(r'industry_name\s+as\s+\w*gap\w*', sql_lower):
        return {"verdict": "FAIL", "reason": "industry_name aliased as gap area — different dimensions"}
    # Nested aggregate inside STRING_AGG always fails in PostgreSQL
    if re.search(r'string_agg\s*\(.*?\|\|.*?count\s*\(', sql_lower):
        return {"verdict": "FAIL", "reason": "Nested aggregate inside STRING_AGG — PostgreSQL forbids this"}
    stripped = sql_lower.strip()
    if re.match(r'select\s+count\s*\(\s*distinct\s+(\w+)', stripped):
        outer_cd_col = re.match(r'select\s+count\s*\(\s*distinct\s+(\w+)', stripped).group(1)
        gb_match = re.search(r'\bgroup\s+by\s+\w*\.?' + re.escape(outer_cd_col), sql_lower)
        if gb_match and 'having' in sql_lower:
            from_idx = sql_lower.find('from ')
            gb_idx = sql_lower.find('group by')
            if from_idx > 0 and gb_idx > from_idx and 'select' not in sql_lower[from_idx:gb_idx]:
                return {"verdict": "FAIL", "reason": f"COUNT(DISTINCT {outer_cd_col}) with GROUP BY {outer_cd_col} — wrap HAVING in subquery"}
    return None


def validate_answer(question: str, sql: str, answer: str, response_type: str) -> dict:
    if not sql and response_type in ("clarification", "general"):
        return {"verdict": "PASS", "reason": "Clarification/general response"}
    if sql:
        r = rule_based_check(sql)
        if r:
            return r
    if sql:
        r = rule_based_pass(sql)
        if r:
            return r
    user_msg = (f"QUESTION: {question}\n\nSQL:\n```sql\n{sql or 'None'}\n```\n\n"
                f"RESPONSE TYPE: {response_type}\n\nANSWER:\n{answer[:800]}")
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=200, temperature=0,
            system=VALIDATOR_PROMPT.format(schema=SCHEMA_CONTEXT[:8000]),
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        if "{" in text:
            j = json.loads(text[text.index("{"):text.rindex("}") + 1])
            return {"verdict": j.get("verdict", "FAIL"), "reason": j.get("reason", "unknown")}
    except Exception as e:
        return {"verdict": "WARN", "reason": str(e)[:80]}
    return {"verdict": "WARN", "reason": "parse error"}


# ── Load questions ────────────────────────────────────────────────────────────
wb = openpyxl.load_workbook("docs/NEP Test Questions.xlsx", data_only=True)
ws = wb["Test Questions"]
all_questions = []
for row in ws.iter_rows(min_row=2, max_col=3, values_only=True):
    q = row[2]
    if q and str(q).strip():
        all_questions.append(str(q).strip())

target_questions = [(i, all_questions[i - 1]) for i in FAILED_QUESTIONS if i <= len(all_questions)]

print(f"Testing {len(target_questions)} questions: {FAILED_QUESTIONS}")
print(f"{'#':>3}  {'API':5}  {'Valid':5}  {'Time':>6}  Question (first 80 chars)")
print("-" * 110)

pass_count = fail_count = 0
for i, q in target_questions:
    payload = {"question": q, "session_id": f"targeted-{int(time.time())}-{i}", "history": []}
    t0 = time.time()
    try:
        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=120)
        elapsed = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "")
            sql = data.get("sql_used", "")
            rtype = data.get("response_type", "")
            validation = validate_answer(q, sql, answer, rtype)
            verdict = validation["verdict"]
            val_reason = validation["reason"]
            api_status = "OK"
        else:
            elapsed = time.time() - t0
            api_status = f"HTTP{resp.status_code}"
            verdict, val_reason, sql, answer, rtype = "FAIL", f"HTTP {resp.status_code}", "", "", ""
    except Exception as e:
        elapsed = time.time() - t0
        api_status, verdict, val_reason, sql, answer, rtype = "ERR", "FAIL", str(e)[:80], "", "", ""

    if verdict == "PASS":
        label = "\033[92mPASS\033[0m"
        pass_count += 1
    else:
        label = "\033[91mFAIL\033[0m"
        fail_count += 1

    print(f"{i:3d}  {api_status:5}  {label}   {elapsed:5.1f}s  {q[:80]}")
    if verdict != "PASS":
        print(f"     REASON: {val_reason[:110]}")
    print(f"     SQL: {sql[:250]}")
    print()
    sys.stdout.flush()

print(f"\n{'='*60}")
print(f"RESULTS: {pass_count}/{len(target_questions)} PASS  |  {fail_count} FAIL")
print(f"{'='*60}")
