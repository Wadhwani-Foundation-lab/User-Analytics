"""
Multi-turn conversation test scenarios.

Each scenario is a list of turns. The first turn starts a fresh session.
Subsequent turns are sent with the accumulated history so the assistant
can resolve pronouns, follow-up filters, and drill-down requests.

Design principles:
- Each scenario tests a realistic conversation arc, not isolated questions.
- Scenarios probe: pronoun resolution ("that source"), implicit continuation
  ("now filter to startups"), drill-down ("show me just the top one"),
  and cross-turn aggregation ("combine those two numbers").
- Expected_intent describes what a correct response should address, used
  for the report but not auto-validated (human review needed for open-ended).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Turn:
    question: str
    expected_intent: str                # human-readable hint for report reviewer
    expected_path: Optional[str] = None  # "certified" | "text_to_sql" | None (either)


@dataclass
class Scenario:
    id: int
    name: str
    description: str
    turns: List[Turn]


SCENARIOS: List[Scenario] = [
    Scenario(
        id=1,
        name="MAU Drill-Down",
        description="User asks for monthly active users, then drills into a specific month and then power-user segment.",
        turns=[
            Turn(
                question="How many monthly active users did we have in Q4 2025?",
                expected_intent="Should return MAU counts for Oct, Nov, Dec 2025.",
                expected_path="certified",
            ),
            Turn(
                question="Which month in that period had the most active users?",
                expected_intent="Should reference Q4 2025 context and identify Nov or Dec as peak.",
            ),
            Turn(
                question="Of those users, how many asked more than 5 questions?",
                expected_intent="Should filter to power users (engaged/power tier) in the same period.",
                expected_path="certified",
            ),
        ],
    ),
    Scenario(
        id=2,
        name="Signup-to-Engagement Funnel",
        description="Start with registration count, then conversion to first AI question, then retention.",
        turns=[
            Turn(
                question="How many users signed up in January 2026?",
                expected_intent="New registrations for Jan 2026 — scalar count.",
                expected_path="certified",
            ),
            Turn(
                question="Of those, how many went on to ask at least one AI question?",
                expected_intent="Conversion from signup to first message — subset of Jan 2026 signups.",
                expected_path="certified",
            ),
            Turn(
                question="What was the average number of days between signup and their first question?",
                expected_intent="Time-to-first-message metric, should reference Jan 2026 cohort.",
                expected_path="certified",
            ),
        ],
    ),
    Scenario(
        id=3,
        name="Event No-Show Investigation",
        description="User finds a problem (high no-shows), drills into which program, then asks for the specific events.",
        turns=[
            Turn(
                question="Which gap areas have the highest no-show rates across all events?",
                expected_intent="event_noshow_by_gap metric — ranks gap areas by no-show %.",
                expected_path="certified",
            ),
            Turn(
                question="For that top gap area, which program has the most no-shows?",
                expected_intent="Should pick up the top gap area from previous turn and break by program.",
            ),
            Turn(
                question="Show me the specific events in that gap area with their dates and attendance counts.",
                expected_intent="List of events filtered to the identified gap area.",
                expected_path="text_to_sql",
            ),
        ],
    ),
    Scenario(
        id=4,
        name="Mentor Coverage Analysis",
        description="Explore mentor distribution, then narrow to a specific industry, then check for event coverage.",
        turns=[
            Turn(
                question="How many active mentors do we have per industry?",
                expected_intent="mentors_by_industry — COUNT DISTINCT by industry_name.",
                expected_path="certified",
            ),
            Turn(
                question="Which stage do most FinTech mentors cover?",
                expected_intent="Should filter mentor profiles to FinTech industry and group by stage_name.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Are there any events covering FinTech-related gap areas in our data?",
                expected_intent="Query events table for FinTech-related gap areas (e.g. StartupFinancials).",
                expected_path="text_to_sql",
            ),
        ],
    ),
    Scenario(
        id=5,
        name="Traffic Source Attribution",
        description="Identify top traffic source, then dig into user quality from that source.",
        turns=[
            Turn(
                question="Which traffic source brings the most new signups?",
                expected_intent="Group signups by traffic_source_source — top source by count.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="What is the repeat user rate for users from that source?",
                expected_intent="Should refer to the top source from previous answer and compute repeat rate.",
            ),
            Turn(
                question="And how does their AI conversation rate compare to the overall platform average?",
                expected_intent="Compare message activity rate for that source vs all users.",
                expected_path="text_to_sql",
            ),
        ],
    ),
    Scenario(
        id=6,
        name="Retention Rate Follow-up",
        description="Get overall retention, then ask about a specific channel, then compare two channels.",
        turns=[
            Turn(
                question="What is the week over week retention rate on the platform?",
                expected_intent="weekly_retention metric.",
                expected_path="certified",
            ),
            Turn(
                question="How does retention differ by traffic source?",
                expected_intent="retention_by_channel metric — breakdown by channel.",
                expected_path="certified",
            ),
            Turn(
                question="Which channel has improved the most over the last 2 months of data?",
                expected_intent="Should detect trend improvement in retention_by_channel or related query.",
                expected_path="text_to_sql",
            ),
        ],
    ),
    Scenario(
        id=7,
        name="Program Event Comparison",
        description="Compare event metrics across programs, then focus on a specific underperformer.",
        turns=[
            Turn(
                question="Compare the attendance rate for Expert Sessions across Liftoff, Liftoff-Spark, and Liftoff-Propel.",
                expected_intent="Attendance rate per program for Expert Sessions — table or bar chart.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Which program had the lowest attendance rate?",
                expected_intent="Should derive from previous answer which program is lowest.",
            ),
            Turn(
                question="What gap areas did that program cover in its events?",
                expected_intent="Events table filtered to the identified program — list of gap areas.",
                expected_path="text_to_sql",
            ),
        ],
    ),
    Scenario(
        id=8,
        name="User Segment Exploration",
        description="Start with user type breakdown, then add company type, then engagement depth.",
        turns=[
            Turn(
                question="Show me the breakdown of users by Internal vs External type.",
                expected_intent="Group by user_type — Internal Users vs External Users count.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Now break that down further by company type (startup vs MSME).",
                expected_intent="Two-level segmentation: user_type x company_type.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="For the MSME External Users, what is the distribution of activity types?",
                expected_intent="Activity type breakdown filtered to MSME + External — activity_type_breakdown metric or text-to-sql.",
                expected_path="certified",
            ),
        ],
    ),
    Scenario(
        id=9,
        name="Quarterly Platform Health Review",
        description=(
            "A 15-turn end-to-end review covering Q1 2026: signups → funnel → "
            "events → mentors → cross-domain. Tests pronoun resolution, "
            "implicit context carry-forward, and drill-down across all four tables."
        ),
        turns=[
            Turn(
                question="What were the total new signups in Q1 2026 (January through March)?",
                expected_intent="new_registrations for Q1 2026 — period Jan 1 to Apr 1.",
                expected_path="certified",
            ),
            Turn(
                question="How does that break down by user type — startups vs MSMEs?",
                expected_intent="Q1 2026 signups segmented by company_type (startup / MSME).",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Which month in Q1 had the highest MSME signups?",
                expected_intent="Monthly signup counts filtered to MSME within Q1 2026 — identify peak month.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="For January 2026, show me the homepage to first AI message conversion funnel.",
                expected_intent="platform_user_funnel for Jan 2026 — signup → onboarding → first message.",
                expected_path="certified",
            ),
            Turn(
                question="What was the average time from signup to first AI message for January 2026 signups?",
                expected_intent="signup_to_first_message metric for Jan 2026 cohort.",
                expected_path="certified",
            ),
            Turn(
                question="For startup users specifically, how many sent their first AI message within 7 days of signing up?",
                expected_intent="Filter Jan 2026 signups to company_type=startup, count those with first message ≤7 days after created_datetime.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Now let's look at live events. How many completed events were there across all programs in Q1 2026?",
                expected_intent="COUNT DISTINCT event_id WHERE event_status=COMPLETED and start_date in Q1 2026.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Compare attendance rates across Liftoff, Liftoff-Spark, and Liftoff-Propel for January 2026.",
                expected_intent="events_by_program with date filter for Jan 2026 — attendance rate per program.",
                expected_path="certified",
            ),
            Turn(
                question="Which program had the lowest attendance rate in that comparison?",
                expected_intent="Derive from previous answer which program is the lowest-performing — context resolution.",
            ),
            Turn(
                question="Show me all the Round Table sessions from that program, with their event titles, dates, and attendance counts.",
                expected_intent="Events table filtered to the identified program + sessiontype=roundTable — list with dates and attendance.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Across those Round Table sessions, which gap areas had the highest no-show rates?",
                expected_intent="Aggregate no-shows by gapkey for the Round Table events from the previous answer's program.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="Are there active mentors covering that top gap area? List them with their program and industry.",
                expected_intent="Join mentor profiles to find ACTIVE mentors whose industry or stage maps to the identified gap area.",
                expected_path="text_to_sql",
            ),
            Turn(
                question="How many active mentors does each program have in total?",
                expected_intent="mentor_coverage_by_program — COUNT DISTINCT user_id per program.",
                expected_path="certified",
            ),
            Turn(
                question="Show me the industry breakdown of active mentors in the Liftoff-Propel program.",
                expected_intent="mentors_by_industry with program=liftoff-propel filter.",
                expected_path="certified",
            ),
            Turn(
                question="Which of those Liftoff-Propel mentor industries also had participants attending events in Q1 2026? Show the overlap.",
                expected_intent="Cross-domain join: gapkey from events → industry_name from mentors; find industries represented in both Q1 2026 events and Liftoff-Propel mentor pool.",
                expected_path="text_to_sql",
            ),
        ],
    ),
]
