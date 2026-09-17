"""
LLM-as-Judge: evaluates SQL correctness and response accuracy using Claude Opus 4.8.

Each evaluation receives the question, SQL used, natural-language response, and row
count. The judge returns a structured verdict with reasoning, SQL issues, data
accuracy notes, and optional recommended SQL / response.

Uses Claude's tool-use API for structured output — the verdict enum is enforced at
the API schema layer so invalid verdicts can't slip through.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import DOCS_DIR, JUDGE_MODEL, SCHEMA_REF

MAX_TOKENS = 2048

# ---------------------------------------------------------------------------
# Schema context — loaded once at import time
# ---------------------------------------------------------------------------

def _load_schema() -> str:
    try:
        return SCHEMA_REF.read_text(encoding="utf-8")
    except Exception:
        return "(schema_reference.md unavailable)"


_SCHEMA_CONTEXT: str = _load_schema()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are an expert SQL reviewer and data analyst evaluating analytics queries for
NEP (National Entrepreneurship Platform) by Wadhwani Foundation.

Your job per question:
1. Is the SQL logically correct for what was asked?
2. Does it follow all platform SQL rules?
3. Is the natural-language response an accurate reflection of the SQL and its results?
4. Are numbers or claims in the response plausible?
5. If you see a better SQL, provide it.

PLATFORM SQL RULES — every SQL must follow these:
- CTEs (WITH ... AS) ARE supported by the Supabase execute_sql RPC — verified.
  Do NOT flag CTE usage as an error. Subqueries are equally valid.
- Always LIMIT 500 (in the final SELECT when a CTE is used).
- All date columns (except nep_master_live_events_data.start_date) are stored as TEXT/VARCHAR.
  Compare using string literals: >= '2026-01-01' and < '2026-02-01'. Never use NOW(),
  CURRENT_DATE, or ::timestamp casts on these columns.
- JOIN key inconsistency: activity table uses `userid` (NO underscore);
  user / mentor / events tables use `user_id` (WITH underscore).
- Mentor table is exploded ~33x per mentor. Always COUNT(DISTINCT user_id), never COUNT(*).
- Qualify all columns with table aliases in multi-table queries to avoid ambiguity.
- No correlated subqueries in SELECT clause (causes timeouts on 154k-row activity table).

DATABASE SCHEMA:
"""


def _build_system() -> str:
    return _SYSTEM_BASE + _SCHEMA_CONTEXT


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

_JUDGE_TOOL = {
    "name": "evaluate_response",
    "description": (
        "Submit your evaluation of the SQL query and response accuracy. "
        "Always call this tool — do not return plain text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["ACCURATE", "INACCURATE", "UNCERTAIN", "SKIPPED"],
                "description": (
                    "ACCURATE: SQL correctly answers the question and response reflects results. "
                    "INACCURATE: SQL has logical errors or response misrepresents the data. "
                    "UNCERTAIN: Cannot determine correctness without executing the SQL. "
                    "SKIPPED: No SQL was provided."
                ),
            },
            "confidence_pct": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Confidence in your verdict (0–100).",
            },
            "reasoning": {
                "type": "string",
                "description": (
                    "Detailed reasoning. Explain which parts of the SQL you checked, "
                    "what the SQL computes, and why you reached your verdict."
                ),
            },
            "sql_issues": {
                "type": "string",
                "description": (
                    "Specific SQL problems found: wrong join key, missing filter, incorrect "
                    "aggregation, missing DISTINCT, wrong column, etc. "
                    "Empty string if the SQL is correct."
                ),
            },
            "data_accuracy_note": {
                "type": "string",
                "description": (
                    "Note on whether numbers or claims in the response are plausible given "
                    "the SQL structure and the platform's data. E.g. 'Response says 45 users "
                    "but the SQL counts rows not distinct users — likely an overcount.' "
                    "Empty string if the response accurately reflects the SQL."
                ),
            },
            "recommended_sql": {
                "type": "string",
                "description": (
                    "Corrected or optimized SQL if you found issues. Must follow all platform "
                    "rules (LIMIT 500, correct join keys, etc.; CTEs are allowed). "
                    "Empty string if the original SQL is correct."
                ),
            },
            "recommended_response": {
                "type": "string",
                "description": (
                    "A more accurate natural-language response if the original was wrong or "
                    "misleading. Empty string if the original response is fine."
                ),
            },
        },
        "required": [
            "verdict", "confidence_pct", "reasoning",
            "sql_issues", "data_accuracy_note",
            "recommended_sql", "recommended_response",
        ],
    },
}

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class JudgeResult:
    verdict: str           # ACCURATE | INACCURATE | UNCERTAIN | SKIPPED
    confidence_pct: int
    reasoning: str
    sql_issues: str
    data_accuracy_note: str
    recommended_sql: str
    recommended_response: str
    error: str = ""


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate(
    question: str,
    sql_used: str,
    answer: str,
    row_count: Optional[int],
    path: str,
    metric: Optional[str] = None,
) -> JudgeResult:
    """
    Evaluate one question/SQL/response using Claude Opus 4.8.

    When sql_used is empty or missing, returns SKIPPED immediately without an
    API call. All other verdicts require a live Opus call.
    """
    if not sql_used or not sql_used.strip():
        return JudgeResult(
            verdict="SKIPPED",
            confidence_pct=0,
            reasoning="No SQL was available for this response (error or missing).",
            sql_issues="",
            data_accuracy_note="",
            recommended_sql="",
            recommended_response="",
        )

    import anthropic

    client = anthropic.Anthropic()

    truncated = sql_used.rstrip().endswith("…") or sql_used.rstrip().endswith("...")
    trunc_note = (
        "\n\nNOTE: The SQL shown above appears to be truncated. "
        "Evaluate what is visible; note truncation in your reasoning."
    ) if truncated else ""

    row_info = f"{row_count} rows returned" if row_count is not None else "row count not available"
    path_info = f"Path: {path}" + (f"  |  Certified metric: {metric}" if metric else "")

    user_message = (
        f"QUESTION:\n{question}\n\n"
        f"{path_info}\n"
        f"Result: {row_info}\n\n"
        f"SQL USED:\n```sql\n{sql_used}\n```{trunc_note}\n\n"
        f"RESPONSE GIVEN TO USER:\n{answer}\n\n"
        "Evaluate the SQL correctness and response accuracy using the evaluate_response tool."
    )

    try:
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=MAX_TOKENS,
            system=_build_system(),
            tools=[_JUDGE_TOOL],
            tool_choice={"type": "tool", "name": "evaluate_response"},
            messages=[{"role": "user", "content": user_message}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "evaluate_response":
                inp = block.input
                return JudgeResult(
                    verdict=inp["verdict"],
                    confidence_pct=int(inp["confidence_pct"]),
                    reasoning=inp["reasoning"],
                    sql_issues=inp.get("sql_issues", ""),
                    data_accuracy_note=inp.get("data_accuracy_note", ""),
                    recommended_sql=inp.get("recommended_sql", ""),
                    recommended_response=inp.get("recommended_response", ""),
                )

        return JudgeResult(
            verdict="UNCERTAIN",
            confidence_pct=0,
            reasoning="Judge returned no tool call — unexpected API response.",
            sql_issues="",
            data_accuracy_note="",
            recommended_sql="",
            recommended_response="",
        )

    except Exception as exc:
        return JudgeResult(
            verdict="UNCERTAIN",
            confidence_pct=0,
            reasoning=f"Judge API call failed: {exc}",
            sql_issues="",
            data_accuracy_note="",
            recommended_sql="",
            recommended_response="",
            error=str(exc),
        )
