"""
SQL generator — uses Claude Opus (claude-opus-5) to convert natural language
questions into validated SQL queries.

Return shape:
  {
    "sql": "SELECT ...",           # empty string when clarification needed
    "response_type": "text|table|bar_chart|line_chart|pie_chart|funnel_chart",
    "chart_label_column": "",
    "chart_value_column": "",
    "nl_answer_template": "...",
  }
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Optional

from .config import get_anthropic, SQL_GEN_MODEL
from .schema_context import build_system_prompt

_MAX_TOKENS = 4096

_JSON_REMINDER = (
    "\n\n[REMINDER: Your entire response MUST be a single valid JSON object "
    "matching the required format. No prose before or after it.]"
)

_CORRECTION_PROMPT = (
    "Your last response did not contain a valid JSON object. "
    "Restate your answer strictly in this format:\n"
    '{"sql":"SELECT ...","response_type":"text","nl_answer_template":"...","chart_label_column":"","chart_value_column":""}\n'
    "Output ONLY the JSON object. Nothing else."
)

# ── Deterministic guard for Rule 34 (event_status leakage) ──────────────────
# Prompt-level reinforcement (numbered rule + final checklist) proved unreliable
# in practice — the model kept adding this filter on attendance/trend questions
# regardless of wording or prompt position. Enforced in code instead.
_COMPLETE_KEYWORDS_RE = re.compile(r"\b(completed?|held|finished)\b", re.IGNORECASE)
_EVENT_STATUS_AND_AFTER_RE = re.compile(r"event_status\s*=\s*'COMPLETED'\s+AND\s+", re.IGNORECASE)
_EVENT_STATUS_AND_BEFORE_RE = re.compile(r"\s+AND\s+event_status\s*=\s*'COMPLETED'", re.IGNORECASE)
_EVENT_STATUS_ALONE_RE = re.compile(r"event_status\s*=\s*'COMPLETED'", re.IGNORECASE)


# ── Deterministic fix for the user_type enum truncation bug ──────────────────
# 'External'/'Internal' (without "Users") are never valid stored values for
# user_type — the schema only has 'External Users' | 'Internal Users' |
# 'Incomplete Profile' — yet the model periodically drops the suffix, which
# silently zeroes out every row (a WHERE clause that can never match). Unlike
# Rule 30/31/25 (judgment calls with legitimate exceptions), this has no
# ambiguity: a straight string substitution is more reliable than depending on
# a corrective retry succeeding.
_USER_TYPE_EXTERNAL_RE = re.compile(r"user_type\s*=\s*'External'(?!\s*Users)", re.IGNORECASE)
_USER_TYPE_INTERNAL_RE = re.compile(r"user_type\s*=\s*'Internal'(?!\s*Users)", re.IGNORECASE)


def fix_user_type_enum(sql: str) -> str:
    """Correct user_type = 'External'/'Internal' to the real enum values, unconditionally."""
    if not sql:
        return sql
    sql = _USER_TYPE_EXTERNAL_RE.sub("user_type = 'External Users'", sql)
    sql = _USER_TYPE_INTERNAL_RE.sub("user_type = 'Internal Users'", sql)
    return sql


_HISTORY_LOOKBACK_TURNS = 4


def mentions_completed_events(question: str, history: Optional[list[dict]] = None) -> bool:
    """
    True if the question explicitly asks for completed/held/finished events, OR
    a recent turn in this conversation already established that scope — e.g.
    T1 "How many completed events have taken place?" followed by T2 "Split
    that between expertSession and roundTable" should still mean completed
    events, even though T2 never repeats the word. Only recent turns are
    checked so an old, unrelated mention several turns back doesn't leak
    into an unrelated follow-up.

    Shared by both the free-form SQL path (_strip_unrequested_completed_filter)
    and the certified-metric path (router.py event_status param override) so
    "completed events" is defined identically regardless of which path answers
    the question.
    """
    if _COMPLETE_KEYWORDS_RE.search(question):
        return True
    for turn in (history or [])[-_HISTORY_LOOKBACK_TURNS:]:
        if _COMPLETE_KEYWORDS_RE.search(turn.get("content") or ""):
            return True
    return False


def _strip_unrequested_completed_filter(sql: str, question: str, history: Optional[list[dict]] = None) -> str:
    """
    Remove an event_status = 'COMPLETED' filter the LLM added on its own when
    neither the question nor recent conversation history asked for
    completed/held/finished events.
    """
    if not sql or mentions_completed_events(question, history):
        return sql
    if not _EVENT_STATUS_ALONE_RE.search(sql):
        return sql
    stripped = _EVENT_STATUS_AND_AFTER_RE.sub("", sql)
    stripped = _EVENT_STATUS_AND_BEFORE_RE.sub("", stripped)
    stripped = _EVENT_STATUS_ALONE_RE.sub("1=1", stripped)
    return stripped


# ── Deterministic guard for mentor user_status leakage (same shape as Rule 34) ─
# "Show me mentor counts grouped by industry" (no qualifier) silently added
# user_status = 'ACTIVE', excluding PENDING mentors without disclosure — the
# same unrequested-scope-narrowing pattern as event_status, just on a
# different column. \b word boundaries keep this from ever matching the
# unrelated user_profile_status column on the user table.
_ACTIVE_KEYWORDS_RE = re.compile(r"\bactive\b", re.IGNORECASE)
_USER_STATUS_AND_AFTER_RE = re.compile(r"\buser_status\s*=\s*'ACTIVE'\s+AND\s+", re.IGNORECASE)
_USER_STATUS_AND_BEFORE_RE = re.compile(r"\s+AND\s+\buser_status\s*=\s*'ACTIVE'", re.IGNORECASE)
_USER_STATUS_ALONE_RE = re.compile(r"\buser_status\s*=\s*'ACTIVE'", re.IGNORECASE)


def mentions_active_mentors(question: str, history: Optional[list[dict]] = None) -> bool:
    """True if the question (or a recent turn) explicitly asks about ACTIVE mentors."""
    if _ACTIVE_KEYWORDS_RE.search(question):
        return True
    for turn in (history or [])[-_HISTORY_LOOKBACK_TURNS:]:
        if _ACTIVE_KEYWORDS_RE.search(turn.get("content") or ""):
            return True
    return False


def _strip_unrequested_active_filter(sql: str, question: str, history: Optional[list[dict]] = None) -> str:
    """Remove a user_status = 'ACTIVE' filter added without the question asking for active mentors."""
    if not sql or mentions_active_mentors(question, history):
        return sql
    if not _USER_STATUS_ALONE_RE.search(sql):
        return sql
    stripped = _USER_STATUS_AND_AFTER_RE.sub("", sql)
    stripped = _USER_STATUS_AND_BEFORE_RE.sub("", stripped)
    stripped = _USER_STATUS_ALONE_RE.sub("1=1", stripped)
    return stripped


# ── Deterministic guard for Rule 30 (unwanted GROUP BY on scalar questions) ──
# Rule 30 already names several of these exact questions as anti-patterns in
# the prompt, and the model still violates it in practice — the same
# unreliability pattern seen with Rule 34. A single corrective retry, fired
# only when the heuristic below detects the specific mismatch, is more
# reliable than further prompt wording.
_BY_DEADLINE_EXCLUSIONS = (
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"\d{4}|\d{1,2}[/-]\d{1,2}|today|tomorrow|now|then|end|noon|midnight"
)
_GROUPBY_TRIGGER_WORDS_RE = re.compile(
    r"\b(broken down by|for each|each\s+\w+|per\s+\w+|"
    rf"by\s+(?!(?:{_BY_DEADLINE_EXCLUSIONS})\b)\w+(?:\s+\w+)?|"
    r"distribution|grouped by|group by|highest|lowest|most|least|top|best|worst|peak|"
    r"trend|trends|over time|monthly|weekly|daily|month-over-month|week-over-week|"
    r"month over month|week over week|funnel|conversion|drop-off|dropoff|stages?|"
    r"compare|comparison|vs\.?|versus)\b",
    re.IGNORECASE,
)
_GROUP_BY_RE = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)

# ── Deterministic guard for Rule 31 (any-activity / after-signup violations) ─
# Same unreliability pattern as Rules 30/34: the worked example in the prompt
# helps but doesn't hold 100% of the time. Folded into the same single
# corrective retry as the Rule 30 check below rather than adding a second
# round-trip.
_ANY_ACTIVITY_RE = re.compile(
    r"\b(any activity|at least one activity|had (?:any|some) activity|activity of any kind)\b",
    re.IGNORECASE,
)
_ACTIVITY_TYPE_FILTER_RE = re.compile(r"activity_type\s*=\s*'[^']+'", re.IGNORECASE)
_AFTER_SIGNUP_RE = re.compile(
    r"after\s+(?:signing up|sign(?:ing)?up|they signed up|registration|registering)",
    re.IGNORECASE,
)
_TEMPORAL_SIGNUP_CONDITION_RE = re.compile(
    r"(created_at|message_date)\s*>\s*\w*\.?signup_date", re.IGNORECASE
)

# ── Deterministic guard for Rule 25 (first-activity-after-signup lag) ───────
# "Time between signup and first X" questions need a MIN(...) computed only
# over rows after signup_date; without that guard, same-day (0-day) or even
# pre-signup rows deflate the lag average. Same unreliability pattern as
# Rules 30/31/34 — the worked example in the prompt doesn't hold reliably.
_TIME_TO_FIRST_RE = re.compile(
    r"(time (between|to|from|until)\s+sign\s*up|signup to first|conversion lag|"
    r"days?\s+(to|until)\s+first|how (long|quickly).*(after|before)\s+sign)",
    re.IGNORECASE,
)


def _detect_rule25_issues(sql: str, question: str) -> list[str]:
    """Detect Rule 25 violations: missing after-signup guard on a first-activity lag calc."""
    if not sql:
        return []
    if _TIME_TO_FIRST_RE.search(question) and not _TEMPORAL_SIGNUP_CONDITION_RE.search(sql):
        return [
            "Rule 25: the question computes time-to-first-activity (a lag from signup), "
            "but the SQL has no guard restricting the activity to rows AFTER signup_date "
            "(e.g. message_date > signup_date or created_at > signup_date). Without it, "
            "same-day or pre-signup rows collapse the lag toward 0."
        ]
    return []


def _detect_rule31_issues(sql: str, question: str) -> list[str]:
    """Detect Rule 31 violations: over-restricted activity_type, missing after-signup condition."""
    issues: list[str] = []
    if not sql:
        return issues
    if _ANY_ACTIVITY_RE.search(question) and _ACTIVITY_TYPE_FILTER_RE.search(sql):
        issues.append(
            "Rule 31: the question asks about ANY activity, but the SQL restricts "
            "activity_type to one specific value — remove the activity_type filter "
            "entirely so all activity types are counted."
        )
    if _AFTER_SIGNUP_RE.search(question) and not _TEMPORAL_SIGNUP_CONDITION_RE.search(sql):
        issues.append(
            "Rule 31: the question asks for activity AFTER signing up, but the SQL is "
            "missing the temporal condition created_at > signup_date on the activity "
            "table alias."
        )
    return issues


_LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)


def _detect_rule2_issues(sql: str) -> list[str]:
    """Detect Rule 2 violations: no LIMIT clause anywhere in the SQL."""
    if sql and not _LIMIT_RE.search(sql):
        return ["Rule 2: the SQL has no LIMIT clause at all — add LIMIT 500 to the final SELECT."]
    return []


def _detect_sql_issues(sql: str, question: str) -> list[str]:
    """All deterministic post-generation checks, combined into one issue list."""
    issues: list[str] = []
    if _looks_like_unwanted_groupby(sql, question):
        issues.append(
            "Rule 30: the SQL used GROUP BY, but the question has no breakdown or "
            "ranking language (\"broken down by\", \"for each\", \"per X\", "
            "\"by program/type/category\", \"distribution\", \"grouped by\", or a "
            "superlative like \"highest\"/\"most\"/\"top\"). Return ONE aggregate row "
            "with NO GROUP BY."
        )
    issues.extend(_detect_rule31_issues(sql, question))
    issues.extend(_detect_rule25_issues(sql, question))
    issues.extend(_detect_rule2_issues(sql))
    return issues


# ── Guard for certified-metric granularity mismatch ──────────────────────────
# event_attendance_rate.yaml is hardcoded to GROUP BY event_id (one row per
# event) — too fine-grained to satisfy a question that explicitly compares
# session types, which needs one row per sessiontype instead. Rather than
# rework that certified metric's grain, router.py declines the match for this
# specific case and lets the free-form generator (which already produces
# correct sessiontype-level comparisons per Rule 22/4b) answer it.
_SESSION_TYPE_COMPARISON_RE = re.compile(
    r"(expert\s*session.*round\s*table|round\s*table.*expert\s*session|"
    r"by\s+session\s*type|session\s*type\s*(?:comparison|breakdown))",
    re.IGNORECASE | re.DOTALL,
)


def wants_session_type_comparison(question: str) -> bool:
    """True if the question explicitly compares session types (expertSession vs roundTable)."""
    return bool(_SESSION_TYPE_COMPARISON_RE.search(question))


# ── Guard for "top N" follow-ups against a certified metric ─────────────────
# Certified metrics have a fixed LIMIT 500 with no way to express "only the
# top N rows" — a follow-up like "share top 5" re-matches the same metric and
# re-renders the identical full breakdown, even though the narrative (written
# from a 30-row sample) correctly narrows to N. Decline the certified match so
# the free-form generator can write an actual ORDER BY ... LIMIT N query.
_TOP_N_RE = re.compile(
    r"\btop\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.IGNORECASE,
)


def wants_top_n(question: str) -> bool:
    """True if the question asks for a specific top-N slice (e.g. "top 5", "top ten")."""
    return bool(_TOP_N_RE.search(question))


# ── Guard for two-dimensional breakdown vs single-dimension certified metric ──
# signups_by_segment (and similarly-shaped metrics) can only split by ONE
# dimension via its `dimension` choice — it has no way to ALSO split by time
# period. A question naming both a time axis ("month over month", "for
# January and February") AND a category axis ("by company type") needs two
# columns (chart_series_column), which only the free-form generator can
# produce. Decline the single-dimension metric so it falls through.
_TIME_AXIS_RE = re.compile(
    r"(month.over.month|week.over.week|day.over.day|monthly|weekly|trend|"
    r"over time|for \w+ and \w+ 20\d\d|across \w+ and \w+)",
    re.IGNORECASE,
)
_CATEGORY_AXIS_RE = re.compile(
    r"(by\s+company\s*type|by\s+user\s*type|by\s+segment|by\s+revenue|"
    r"broken down by|grouped by)",
    re.IGNORECASE,
)


def wants_two_dimensional_breakdown(question: str) -> bool:
    """True if the question names both a time axis and a category axis together."""
    return bool(_TIME_AXIS_RE.search(question) and _CATEGORY_AXIS_RE.search(question))


# "overall"/"total"/etc. are explicit scalar-intent words. event_attendance_rate
# is otherwise exempt from the breakdown-language shape check (see router.py)
# since its typical single-filter use naturally lists multiple events without
# needing "broken down by" wording — but "overall no-show rate" still means
# one aggregate number, not a per-event list, so these words override the
# exemption.
_EXPLICIT_SCALAR_RE = re.compile(r"\b(overall|in total|altogether|combined|aggregate)\b", re.IGNORECASE)


def wants_explicit_scalar(question: str) -> bool:
    """True if the question uses an explicit aggregate word like 'overall'/'in total'."""
    return bool(_EXPLICIT_SCALAR_RE.search(question))


def has_breakdown_language(question: str) -> bool:
    """
    True if the question asks for a breakdown/ranking (Rule 30's trigger words,
    plus superlatives like "highest"/"most"/"top"). Shared by the free-form
    SQL guard below and by router.py, which uses it to decline a certified
    metric match when the metric is structurally a breakdown/chart (has a
    label column) but the question never asked for one — the certified-metric
    analogue of _looks_like_unwanted_groupby, since a hardcoded GROUP BY in a
    metric template is just as immune to prompt wording as one the LLM writes.
    "at least"/"at most" are idioms (e.g. "attended at least one event") that
    don't imply ranking, so they're stripped before matching to avoid a false
    positive on "least"/"most".
    """
    cleaned_question = re.sub(r"\bat\s+(least|most)\b", "", question, flags=re.IGNORECASE)
    return bool(_GROUPBY_TRIGGER_WORDS_RE.search(cleaned_question))


def _looks_like_unwanted_groupby(sql: str, question: str) -> bool:
    """
    Heuristic for Rule 30 violations: the SQL groups results but the question
    has no breakdown/ranking language, so a single aggregate was likely wanted.
    """
    if not sql or not _GROUP_BY_RE.search(sql):
        return False
    return not has_breakdown_language(question)


def _maybe_correct_sql(
    parsed: dict,
    question: str,
    messages: list[dict],
    system_prompt: str,
    client,
    raw_text: str,
) -> dict:
    """One extra corrective round-trip if any deterministic post-generation check fails."""
    sql = str(parsed.get("sql", "") or "")
    issues = _detect_sql_issues(sql, question)
    if not issues:
        return parsed

    correction_prompt = (
        f'Review your last SQL against these specific issues for the question "{question}":\n'
        + "\n".join(f"- {issue}" for issue in issues)
        + "\n\nAlso double-check Rule 35 while correcting: use nep_master_user_table_sample_data "
        "for a plain user-registration count, and nep_master_live_events_data with "
        "participant_status = 'ATTENDED' for an event-attendance count — not the activity table. "
        "Restate your full JSON response with corrected SQL."
    )
    correction_messages = messages + [
        {"role": "assistant", "content": raw_text},
        {"role": "user", "content": correction_prompt},
    ]
    response = client.messages.create(
        model=SQL_GEN_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=correction_messages,
    )
    raw = _response_text(response)
    corrected = _parse(raw)
    return corrected if corrected is not None else parsed


def _response_text(response) -> str:
    """Return the first text block's content, skipping thinking blocks."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _extract_json(text: str) -> str | None:
    """Find the first complete {...} block, respecting nested braces and strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth, in_string, escape_next = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse(raw: str) -> dict | None:
    fenced = re.search(r"```json\s*([\s\S]*?)\s*```", raw)
    raw_json = _extract_json(fenced.group(1) if fenced else raw) or _extract_json(raw)
    if not raw_json:
        return None
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        return None


def generate(
    question: str,
    history: Optional[list[dict]] = None,
    today: Optional[str] = None,
) -> dict:
    """
    Convert a natural language question to a structured SQL generation result.

    Args:
        question: The user's natural language question.
        history:  Conversation history as list of {"role": ..., "content": ...} dicts.
        today:    Override today's date (YYYY-MM-DD); defaults to real today.

    Returns:
        Dict with keys: sql, response_type, chart_label_column,
        chart_value_column, nl_answer_template.
    """
    client = get_anthropic()
    today = today or date.today().isoformat()
    system_prompt = build_system_prompt(today)

    history = history or []
    messages = history + [{"role": "user", "content": question + _JSON_REMINDER}]

    response = client.messages.create(
        model=SQL_GEN_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    raw: str = _response_text(response)
    parsed = _parse(raw)

    if parsed is not None:
        parsed = _maybe_correct_sql(parsed, question, messages, system_prompt, client, raw)
        return _finalise(parsed, question, history)

    # Retry with correction prompt
    retry_messages = messages + [
        {"role": "assistant", "content": raw},
        {"role": "user", "content": _CORRECTION_PROMPT},
    ]
    retry_response = client.messages.create(
        model=SQL_GEN_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=retry_messages,
    )
    retry_raw: str = _response_text(retry_response)
    parsed_retry = _parse(retry_raw)

    if parsed_retry is not None:
        parsed_retry = _maybe_correct_sql(parsed_retry, question, retry_messages, system_prompt, client, retry_raw)
        return _finalise(parsed_retry, question, history)

    raise ValueError(
        f"SQL generator returned no valid JSON after retry. "
        f"Raw (first 300 chars): {raw[:300]}"
    )


def _finalise(d: dict, question: str, history: Optional[list[dict]] = None) -> dict:
    """Normalise the parsed result and apply deterministic post-generation guards."""
    result = _normalise(d)
    result["sql"] = _strip_unrequested_completed_filter(result["sql"], question, history)
    result["sql"] = _strip_unrequested_active_filter(result["sql"], question, history)
    result["sql"] = fix_user_type_enum(result["sql"])
    return result


def _normalise(d: dict) -> dict:
    """Ensure all expected keys are present with safe defaults."""
    return {
        "sql": str(d.get("sql", "") or "").strip(),
        "response_type": str(d.get("response_type", "text") or "text"),
        "chart_label_column": str(d.get("chart_label_column", "") or ""),
        "chart_value_column": str(d.get("chart_value_column", "") or ""),
        "chart_series_column": str(d.get("chart_series_column", "") or ""),
        "nl_answer_template": str(d.get("nl_answer_template", "") or ""),
    }
