"""
Frozen evaluation set for the analytics assistant.

Each EvalCase captures:
  - question: the natural-language input
  - expected_path: "certified" | "text_to_sql" | "clarification"
  - expected_metric: (certified only) which metric should be matched
  - must_contain_cols: column names that MUST appear in the result
  - must_not_sql: SQL fragments that must NOT appear (hallucinated columns etc.)
  - min_rows / max_rows: bounds on result size (None = unchecked)
  - tags: for filtering (e.g. "retention", "events", "mentor")

The set is immutable at runtime — never mutate EVAL_SET; create new entries.
Run with: python -m ua_api.validation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

TODAY = "2026-06-10"  # frozen anchor date for all eval cases


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected_path: str                          # "certified" | "text_to_sql" | "clarification"
    expected_metric: Optional[str] = None       # metric name (certified path only)
    must_contain_cols: List[str] = field(default_factory=list)
    must_not_sql: List[str] = field(default_factory=list)
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.expected_path == "certified" and not self.expected_metric:
            raise ValueError(f"certified path requires expected_metric: {self.question!r}")


EVAL_SET: List[EvalCase] = [
    # ── Certified — active_users ──────────────────────────────────────────────
    EvalCase(
        question="how many monthly active users did we have in Q4 2025?",
        expected_path="certified",
        expected_metric="active_users",
        must_contain_cols=["period", "active_users"],
        min_rows=1, max_rows=3,
        tags=["mau", "certified"],
    ),
    EvalCase(
        question="show DAU trend for November 2025",
        expected_path="certified",
        expected_metric="active_users",
        must_contain_cols=["period", "active_users"],
        min_rows=1,
        tags=["dau", "certified"],
    ),
    EvalCase(
        question="what is our WAU over the last 2 months of available data?",
        expected_path="certified",
        expected_metric="active_users",
        must_contain_cols=["period", "active_users"],
        tags=["wau", "certified"],
    ),
    # ── Certified — new_registrations ─────────────────────────────────────────
    EvalCase(
        question="how many users registered in January 2026?",
        expected_path="certified",
        expected_metric="new_registrations",
        must_contain_cols=["registered_users"],
        min_rows=1, max_rows=1,
        tags=["registrations", "certified"],
    ),
    # ── Certified — questions growth ──────────────────────────────────────────
    EvalCase(
        question="show the month over month growth in questions asked",
        expected_path="certified",
        expected_metric="questions_growth",
        must_contain_cols=["month_year", "questions"],
        tags=["questions", "growth", "certified"],
    ),
    # ── Certified — weekly_retention ─────────────────────────────────────────
    EvalCase(
        question="what is the week over week retention rate?",
        expected_path="certified",
        expected_metric="weekly_retention",
        must_contain_cols=["current_week", "retention_rate_pct"],
        tags=["retention", "certified"],
    ),
    # ── Certified — event_noshow_by_gap ──────────────────────────────────────
    EvalCase(
        question="which gap areas have the highest no-show rates?",
        expected_path="certified",
        expected_metric="event_noshow_by_gap",
        must_contain_cols=["gap_area", "no_show_rate_pct"],
        tags=["events", "noshow", "certified"],
    ),
    # ── Certified — mentors_by_industry ──────────────────────────────────────
    EvalCase(
        question="how many active mentors are there per industry?",
        expected_path="certified",
        expected_metric="mentors_by_industry",
        must_contain_cols=["industry_name", "active_mentors"],
        tags=["mentors", "certified"],
    ),
    # ── Certified — power_users (resolver prefers this over user_engagement_tiers) ──
    EvalCase(
        question="show the distribution of users by how many questions they've asked",
        expected_path="certified",
        expected_metric="power_users",
        must_contain_cols=["user_segment", "users"],
        tags=["engagement", "power_users", "certified"],
    ),
    # ── Certified — repeat_users ──────────────────────────────────────────────
    EvalCase(
        question="how many repeat users do we have and what is the repeat rate?",
        expected_path="certified",
        expected_metric="repeat_users",
        must_contain_cols=["repeat_users", "repeat_rate_pct"],
        min_rows=1, max_rows=1,
        tags=["retention", "certified"],
    ),
    # ── Text-to-SQL path — known-safe queries ────────────────────────────────
    EvalCase(
        question="show me all users who registered after February 2026",
        expected_path="text_to_sql",
        must_contain_cols=["user_id"],
        must_not_sql=["ai_chat", "mentor_session", "live_event"],
        tags=["text_to_sql"],
    ),
    EvalCase(
        question="which campaigns have the most signups?",
        expected_path="text_to_sql",
        must_not_sql=["ai_chat", "program_key AS program"],
        tags=["text_to_sql", "utm"],
    ),
    EvalCase(
        question="list the top 10 users by number of AI questions asked",
        expected_path="text_to_sql",
        must_not_sql=["ai_chat"],
        min_rows=1,
        tags=["text_to_sql", "power_users"],
    ),
    # ── Anti-hallucination checks ──────────────────────────────────────────────
    EvalCase(
        question="how many users are in the 'ai_chat' activity type?",
        expected_path="text_to_sql",
        must_not_sql=["activity_type = 'ai_chat'"],   # must correct to 'message'
        tags=["text_to_sql", "hallucination_guard"],
    ),
    EvalCase(
        question="show program performance for the ignite program from the events table",
        expected_path="text_to_sql",
        must_not_sql=["e.program =", "events.program"],  # must use program_key
        tags=["text_to_sql", "column_guard"],
    ),

    # ── Certified — signups_by_segment ───────────────────────────────────────
    EvalCase(
        question="how many startups signed up vs MSMEs?",
        expected_path="certified",
        expected_metric="signups_by_segment",
        must_contain_cols=["segment", "signups"],
        min_rows=1,
        tags=["signups", "certified", "signups_by_segment"],
    ),
    EvalCase(
        question="show signup counts broken down by user type in January 2026",
        expected_path="certified",
        expected_metric="signups_by_segment",
        must_contain_cols=["segment", "signups"],
        min_rows=1,
        tags=["signups", "certified", "signups_by_segment"],
    ),
    EvalCase(
        question="which traffic source medium brings the most new signups?",
        expected_path="certified",
        expected_metric="signups_by_segment",
        must_contain_cols=["segment", "signups"],
        min_rows=1,
        tags=["signups", "certified", "signups_by_segment"],
    ),

    # ── Certified — platform_user_funnel ─────────────────────────────────────
    EvalCase(
        question="what is the homepage to onboarding to first message funnel?",
        expected_path="certified",
        expected_metric="platform_user_funnel",
        must_contain_cols=["stage_name", "users"],
        min_rows=3, max_rows=3,
        tags=["funnel", "certified", "platform_user_funnel"],
    ),
    EvalCase(
        question="show drop-off at each user journey stage",
        expected_path="certified",
        expected_metric="platform_user_funnel",
        must_contain_cols=["stage_name", "users"],
        min_rows=3, max_rows=3,
        tags=["funnel", "certified", "platform_user_funnel"],
    ),
    EvalCase(
        question="what is the activation funnel conversion rate for External Users?",
        expected_path="certified",
        expected_metric="platform_user_funnel",
        must_contain_cols=["stage_name", "users"],
        min_rows=3, max_rows=3,
        tags=["funnel", "certified", "platform_user_funnel"],
    ),

    # ── Certified — mentor_coverage_by_program ────────────────────────────────
    EvalCase(
        question="how many mentors are in each program?",
        expected_path="certified",
        expected_metric="mentor_coverage_by_program",
        must_contain_cols=["program", "active_mentors"],
        min_rows=1,
        tags=["mentors", "certified", "mentor_coverage_by_program"],
    ),
    EvalCase(
        question="which program has the most active mentors?",
        expected_path="certified",
        expected_metric="mentor_coverage_by_program",
        must_contain_cols=["program", "active_mentors"],
        min_rows=1,
        tags=["mentors", "certified", "mentor_coverage_by_program"],
    ),

    # ── Semantic guard: mentor table explosion ────────────────────────────────
    # QC1: COUNT(*) on mentor table must use DISTINCT user_id
    EvalCase(
        question="how many total active mentors do we have on the platform?",
        expected_path="text_to_sql",
        must_not_sql=["count(*) from nep_mentor_profiles_sample_data",
                      "count(*)\nfrom nep_mentor_profiles_sample_data"],
        must_contain_cols=["active_mentors"],
        tags=["text_to_sql", "mentor_guard", "semantic_guard"],
    ),
    # Mentor select without dedup — must not return duplicate rows
    EvalCase(
        question="list all active mentors with their industry and stage expertise",
        expected_path="text_to_sql",
        must_not_sql=["onboarding_completed"],   # hallucinated column
        tags=["text_to_sql", "mentor_guard"],
    ),

    # ── Semantic guard: attendance rate denominator ───────────────────────────
    # QC2: attendance rate must NOT use participant_status='REGISTERED' as denominator
    EvalCase(
        question="what is the overall attendance rate for completed events?",
        expected_path="text_to_sql",
        must_not_sql=["participant_status = 'REGISTERED'"],
        tags=["text_to_sql", "events", "attendance_guard", "semantic_guard"],
    ),
    EvalCase(
        question="what is the no-show rate for expert sessions?",
        expected_path="text_to_sql",
        must_not_sql=["participant_status = 'REGISTERED'"],
        tags=["text_to_sql", "events", "attendance_guard", "semantic_guard"],
    ),

    # ── Semantic guard: active user query must NOT filter to message only ─────
    # QC4: weekly/monthly active users = all activity types, not just 'message'
    EvalCase(
        question="how many weekly active users were there in February 2026?",
        expected_path="text_to_sql",
        must_not_sql=["activity_type = 'message'"],
        tags=["text_to_sql", "active_users", "semantic_guard"],
    ),

    # ── Semantic guard: hallucinated activity_type values ────────────────────
    EvalCase(
        question="how many users completed the onboarding process?",
        expected_path="text_to_sql",
        must_not_sql=["activity_type = 'onboarding_completed'",
                      "activity_type='onboarding_completed'"],
        tags=["text_to_sql", "hallucination_guard", "semantic_guard"],
    ),

    # ── Semantic guard: incompatible taxonomy join ────────────────────────────
    # gapkey and industry_name are disjoint — must never be compared
    EvalCase(
        question="which gap areas match the FinTech mentor industry?",
        expected_path="text_to_sql",
        must_not_sql=["gapkey = industry_name", "gapkey in (select industry_name"],
        tags=["text_to_sql", "semantic_guard", "incompatible_pair"],
    ),

    # ── Text-to-SQL: known-good cross-table queries ───────────────────────────
    EvalCase(
        question="for each signup cohort month, how many users later attended a live event?",
        expected_path="text_to_sql",
        must_contain_cols=["cohort_month"],
        tags=["text_to_sql", "cohort", "cross_table"],
    ),
    EvalCase(
        question="which event speakers conducted more than 2 sessions in Liftoff-Propel?",
        expected_path="text_to_sql",
        must_contain_cols=["speaker_name"],
        tags=["text_to_sql", "events"],
    ),
]
