"""
Deterministic SQL linter for NEP Analytics.

Rules are loaded from the catalog (ua_api/data_context/catalog) at first call
and cached. Hard-coded structural rules that don't require catalog data are
defined inline.

Each rule is a function: (sql_lower: str, sql_original: str) -> Violation | None.
A violation is returned only when the rule is CERTAIN the SQL is wrong — borderline
cases are skipped rather than flagged (false-positives are worse than misses here
because they trigger a costly repair round-trip).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Optional

# ── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class Violation:
    rule: str         # short rule name for logging / telemetry
    message: str      # human-readable explanation
    fix_hint: str     # brief instruction to send back to the LLM


# ── Catalog-derived rules (loaded once) ──────────────────────────────────────

@lru_cache(maxsize=1)
def _load_catalog():
    try:
        from ua_api.data_context.catalog import load_catalog
        return load_catalog()
    except Exception:
        return None


def _incompatible_pair_rules() -> List[Callable]:
    """Generate one rule per incompatible pair declared in the catalog."""
    cat = _load_catalog()
    if cat is None:
        return []

    rules = []
    for pair in cat.incompatible_pairs:
        # Extract the column names from "table.column" strings
        left_col  = pair.left.split(".")[-1]
        right_col = pair.right.split(".")[-1]
        reason    = pair.reason.strip()
        left_ref  = pair.left
        right_ref = pair.right

        def _make_rule(lc, rc, lr, rr, rsn):
            def rule(sql_lower: str, _sql: str) -> Optional[Violation]:
                if lc in sql_lower and rc in sql_lower:
                    # Only flag if both appear near each other (JOIN, ON, WHERE, IN subquery)
                    # Look for patterns like: col = col, JOIN ... ON ... col ... col
                    patterns = [
                        rf'\b{re.escape(lc)}\b.*\b{re.escape(rc)}\b',
                        rf'\b{re.escape(rc)}\b.*\b{re.escape(lc)}\b',
                    ]
                    for pat in patterns:
                        if re.search(pat, sql_lower):
                            return Violation(
                                rule=f"incompatible_pair:{lc}_vs_{rc}",
                                message=(
                                    f"`{lr}` and `{rr}` are incompatible domains — "
                                    f"never join or compare them. {rsn}"
                                ),
                                fix_hint=(
                                    f"Remove any join or comparison between `{lc}` and `{rc}`. "
                                    f"They represent different taxonomies: {rsn}"
                                ),
                            )
                return None
            return rule

        rules.append(_make_rule(left_col, right_col, left_ref, right_ref, reason))
    return rules


def _authority_rules() -> List[Callable]:
    """Generate rules for non-authoritative column usage without a JOIN to the authoritative table."""
    cat = _load_catalog()
    if cat is None:
        return []

    rules = []
    for tbl in cat:
        for col in tbl.columns:
            if col.authority or not col.authoritative_source:
                continue
            non_auth_table = tbl.name
            auth_source    = col.authoritative_source  # "auth_table.col"
            auth_table     = auth_source.split(".")[0]
            col_name       = col.name

            def _make_rule(nat, at, cn):
                def rule(sql_lower: str, _sql: str) -> Optional[Violation]:
                    # Flag only if the non-authoritative table is queried
                    # WITHOUT a JOIN to the authoritative table
                    if nat not in sql_lower:
                        return None
                    if at in sql_lower:
                        return None  # authoritative table is present — OK
                    # Check the column is actually referenced in a SELECT/WHERE
                    if not re.search(rf'\b{re.escape(cn)}\b', sql_lower):
                        return None
                    return Violation(
                        rule=f"authority:{cn}_from_{nat}",
                        message=(
                            f"`{cn}` is queried from `{nat}` without joining `{at}`. "
                            f"`{nat}.{cn}` is a denormalised copy that misses users with no activity rows."
                        ),
                        fix_hint=(
                            f"Join `{at}` to get `{cn}` from the authoritative source, "
                            f"or add a JOIN to `{at}` if you need to filter by `{cn}`."
                        ),
                    )
                return rule

            rules.append(_make_rule(non_auth_table, auth_table, col_name))
    return rules


# ── Hard-coded structural rules ───────────────────────────────────────────────

MENTOR_TABLE = "nep_mentor_profiles_sample_data"


def _rule_mentor_count_star(sql_lower: str, _sql: str) -> Optional[Violation]:
    """COUNT(*) on the mentor table gives ~33× inflated results."""
    if MENTOR_TABLE not in sql_lower:
        return None
    # COUNT(*) without an outer wrapper that deduplicates
    if re.search(r'\bcount\s*\(\s*\*\s*\)', sql_lower):
        # Allow it if there's also a GROUP BY user_id — that's a valid fanout count
        if "group by" in sql_lower and "user_id" in sql_lower:
            return None
        return Violation(
            rule="mentor_count_star",
            message=(
                f"`COUNT(*)` on `{MENTOR_TABLE}` counts ~33 rows per mentor (the table is "
                "exploded by program/industry/stage). Use `COUNT(DISTINCT user_id)` instead."
            ),
            fix_hint=(
                f"Replace `COUNT(*)` with `COUNT(DISTINCT user_id)` when counting mentors "
                f"from `{MENTOR_TABLE}`."
            ),
        )
    return None


def _rule_mentor_select_without_dedup(sql_lower: str, _sql: str) -> Optional[Violation]:
    """SELECT without GROUP BY user_id on mentor table returns duplicate mentor rows."""
    if MENTOR_TABLE not in sql_lower:
        return None
    # Only flag SELECT queries (not subqueries with COUNT DISTINCT — those are fine)
    # Heuristic: top-level SELECT with industry_name or stage_name included
    # without any GROUP BY user_id or DISTINCT user_id
    has_exploded_col = any(c in sql_lower for c in ("industry_name", "stage_name", "stage_id", "industry_id"))
    if not has_exploded_col:
        return None
    has_dedup = (
        ("group by" in sql_lower and "user_id" in sql_lower) or
        re.search(r'distinct\s+\w*\.?user_id', sql_lower)
    )
    if has_dedup:
        return None
    return Violation(
        rule="mentor_exploded_select",
        message=(
            f"Query selects `industry_name` or `stage_name` from `{MENTOR_TABLE}` without "
            "deduplicating by `user_id`. The table has ~33 rows per mentor — LIMIT 500 will "
            "return far fewer distinct mentors than expected."
        ),
        fix_hint=(
            f"Add `GROUP BY user_id` and wrap other columns in `MAX()` to get one row per mentor. "
            "Example: `SELECT user_id, MAX(first_name) AS first_name, ... "
            f"FROM {MENTOR_TABLE} WHERE ... GROUP BY user_id`."
        ),
    )


def _rule_attendance_denominator(sql_lower: str, _sql: str) -> Optional[Violation]:
    """Catch attendance/no-show rate computed with REGISTERED-only denominator."""
    events_table = "nep_master_live_events_data"
    if events_table not in sql_lower:
        return None
    # Must be a rate/ratio query
    if not any(kw in sql_lower for kw in ("rate", "ratio", "pct", "percent", "attendance")):
        return None
    # Flag: dividing by a count filtered to status='REGISTERED' only
    if re.search(r"participant_status\s*=\s*'registered'", sql_lower):
        # Check it appears in a denominator-like position (NULLIF, division, filter)
        if re.search(
            r"(nullif|\/|sum|count).*participant_status\s*=\s*'registered'|"
            r"participant_status\s*=\s*'registered'.*\s*(nullif|\/)",
            sql_lower,
        ):
            return Violation(
                rule="attendance_denominator",
                message=(
                    "Attendance/no-show rate uses `participant_status='REGISTERED'` as the denominator. "
                    "`participant_status` is mutually exclusive — REGISTERED, ATTENDED, and NOSHOW are "
                    "separate buckets. Using only REGISTERED rows as the denominator excludes attended "
                    "and no-show rows, producing rates > 100%."
                ),
                fix_hint=(
                    "Use `COUNT(DISTINCT participant_user_id)` (all statuses) as the denominator, "
                    "not a count filtered to `participant_status='REGISTERED'`. "
                    "Canonical: ROUND(COUNT(DISTINCT CASE WHEN participant_status='ATTENDED' "
                    "THEN participant_user_id END)::NUMERIC / NULLIF(COUNT(DISTINCT participant_user_id), 0) * 100, 2)"
                ),
            )
    return None


def _rule_active_users_message_filter(sql_lower: str, _sql: str) -> Optional[Violation]:
    """'Active users' should not be restricted to activity_type='message' unless AI-chat is specifically asked."""
    # Only applicable to activity table queries
    if "nep_liftoffx_data_sample" not in sql_lower:
        return None
    # Check for 'active' in column aliases or aggregations — signals this is an active-user query
    is_active_query = any(kw in sql_lower for kw in (
        "active_user", "weekly_active", "monthly_active", "wau", "mau", "dau",
        "active users", "activity decay", "week_range", "week_activity_number",
    ))
    if not is_active_query:
        return None
    # Flag: restricts to message activity only
    if re.search(r"activity_type\s*=\s*'message'", sql_lower):
        return Violation(
            rule="active_users_message_filter",
            message=(
                "Active user count is filtered to `activity_type='message'` (AI-chat only). "
                "Unless the question specifically asks about AI-chat activity, "
                "'active users' means any activity type — remove or broaden the filter."
            ),
            fix_hint=(
                "Remove `activity_type = 'message'` from the WHERE clause for active-user queries. "
                "Only add it back if the question specifically mentions AI messages or questions asked."
            ),
        )
    return None


def _rule_no_limit(sql_lower: str, sql: str) -> Optional[Violation]:
    """Every query must end with LIMIT 500 (platform rule)."""
    # Strip trailing whitespace/semicolons for the check
    trimmed = sql.rstrip("; \n\t")
    # Allow subqueries: only check the final SELECT (no LIMIT inside a CTE is OK)
    # A quick proxy: the word 'limit' must appear in the last 60 chars of the query
    tail = trimmed[-80:].lower()
    if "limit" not in tail:
        # Don't flag if it's a pure scalar (no GROUP BY, no multi-row result expected)
        if "group by" not in sql_lower and "union" not in sql_lower:
            return None
        return Violation(
            rule="missing_limit",
            message="Query is missing `LIMIT 500` — all analytical queries must cap results at 500 rows.",
            fix_hint="Add `LIMIT 500` as the final clause of the outermost SELECT.",
        )
    return None


def _rule_week_month_crossboundary(sql_lower: str, _sql: str) -> Optional[Violation]:
    """Detect GROUP BY combining a week expression AND a month expression — weeks can straddle month boundaries."""
    if "group by" not in sql_lower:
        return None
    # Week expressions: date_trunc('week'), to_char(...'IW'), week_number
    has_week = bool(re.search(
        r"date_trunc\s*\(\s*'week'|to_char[^)]*'\s*iw\s*'|week_number|week_range|signup_week",
        sql_lower,
    ))
    # Month expressions: date_trunc('month'), to_char(...'YYYY-MM'), month_year
    has_month = bool(re.search(
        r"date_trunc\s*\(\s*'month'|to_char[^)]*'yyyy-mm'|month_year|signup_month",
        sql_lower,
    ))
    if has_week and has_month:
        return Violation(
            rule="week_month_crossboundary",
            message=(
                "GROUP BY includes both a week dimension and a month dimension. "
                "Weeks that straddle a month boundary appear in two month groups, "
                "producing double-counted rows and misleading totals."
            ),
            fix_hint=(
                "Choose ONE time grain: use DATE_TRUNC('week', ...) for weekly trends, "
                "or DATE_TRUNC('month', ...) for monthly trends — never both in the same GROUP BY."
            ),
        )
    return None


def _rule_first_activity_includes_signup(sql_lower: str, _sql: str) -> Optional[Violation]:
    """MIN(ga_event_date) used for 'time to first activity' must exclude the signup event itself."""
    if "nep_liftoffx_data_sample" not in sql_lower:
        return None
    # Detect time-to-first-activity pattern: MIN of a date/timestamp column
    if not re.search(r"\bmin\s*\([^)]*(?:date|time|datetime|created)\b", sql_lower):
        return None
    # Only flag if it looks like a conversion-time query
    if not any(kw in sql_lower for kw in ("time_to", "days_to", "conversion", "first_activit", "first_messag", "first_action")):
        return None
    # Red flag: no exclusion of the signup activity type itself
    if "activity_type" in sql_lower and "signup" not in sql_lower:
        return Violation(
            rule="first_activity_includes_signup",
            message=(
                "Time-to-first-activity query uses MIN(date) but does not exclude "
                "`activity_type = 'signup'`. The signup event itself has a date equal to "
                "registration, so MIN will always return 0 days — making the metric meaningless."
            ),
            fix_hint=(
                "Add `AND activity_type != 'signup'` (or `AND activity_type = 'message'` "
                "if measuring time-to-first-AI-message) inside the subquery that computes MIN(date)."
            ),
        )
    return None


def _rule_funnel_non_sequential(sql_lower: str, _sql: str) -> Optional[Violation]:
    """Funnels must nest each stage cohort inside the previous — detect independent parallel counts."""
    # Only check funnel-type queries
    if not any(kw in sql_lower for kw in ("funnel", "conversion", "step", "stage")):
        return None
    # Signal: multiple independent COUNT(DISTINCT...) joined with CROSS JOIN
    # on different tables without stage-nesting
    cross_join = "cross join" in sql_lower
    multiple_counts = len(re.findall(r'count\s*\(\s*distinct', sql_lower)) >= 3
    if cross_join and multiple_counts:
        # Check if any stage restricts to the prior stage's cohort (IN subquery or JOIN)
        has_nesting = re.search(
            r"userid\s+in\s*\(\s*select|participant_user_id\s+in\s*\(\s*select",
            sql_lower,
        )
        if not has_nesting:
            return Violation(
                rule="funnel_non_sequential",
                message=(
                    "Multi-stage funnel uses independent CROSS JOIN counts without stage nesting. "
                    "Each stage counts from the full population, not from users who completed "
                    "the prior stage — this produces impossible conversion rates (> 100%)."
                ),
                fix_hint=(
                    "Make each funnel stage a nested subset of the previous: "
                    "Stage 2 users must also appear in Stage 1 (use IN subquery or JOIN). "
                    "Example: `WHERE userid IN (SELECT userid FROM ... WHERE <stage1_condition>)`."
                ),
            )
    return None


# ── Rule registry ─────────────────────────────────────────────────────────────

def _get_all_rules() -> List[Callable]:
    """Assemble all rules: catalog-derived first, then hard-coded."""
    return [
        *_incompatible_pair_rules(),
        *_authority_rules(),
        _rule_mentor_count_star,
        _rule_mentor_select_without_dedup,
        _rule_attendance_denominator,
        _rule_active_users_message_filter,
        _rule_week_month_crossboundary,
        _rule_first_activity_includes_signup,
        _rule_funnel_non_sequential,
        _rule_no_limit,
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def lint(sql: str) -> List[Violation]:
    """
    Run all lint rules against the given SQL string.

    Returns a (possibly empty) list of Violation objects.
    An empty list means no violations were detected.
    """
    if not sql or not sql.strip():
        return []
    sql_lower = sql.lower()
    violations: List[Violation] = []
    for rule_fn in _get_all_rules():
        try:
            v = rule_fn(sql_lower, sql)
            if v is not None:
                violations.append(v)
        except Exception:
            pass  # a failing rule must never block the response
    return violations


def lint_with_message(sql: str) -> Optional[str]:
    """
    Lint the SQL and return a repair prompt string if violations were found,
    or None if the SQL is clean.

    The returned string is ready to append to the original question as a
    follow-up instruction to the LLM.
    """
    violations = lint(sql)
    if not violations:
        return None

    lines = [
        "The SQL you generated has the following issues that must be fixed:\n"
    ]
    for i, v in enumerate(violations, 1):
        lines.append(f"{i}. [{v.rule}] {v.message}")
        lines.append(f"   Fix: {v.fix_hint}\n")
    lines.append(
        "Please regenerate the SQL addressing ALL of the issues above. "
        "Keep all other aspects of the query (filters, date ranges, groupings) unchanged."
    )
    return "\n".join(lines)
