# analytics-query

Run a live NEP platform analytics query using the nep_analytics engine.
Converts natural language to SQL, executes against Supabase, and returns structured results.

## When to use
- Answering one-off data questions: "how many users signed up last month?"
- Validating that a metric YAML is working: "test active_users for Q1 2026"
- Spot-checking query results without launching the full API
- Debugging: "why is my question going to sql_generator instead of certified path?"

## Usage
```
/analytics-query <your question>
```

Examples:
```
/analytics-query how many monthly active users in Q1 2026?
/analytics-query show me the top 10 mentors by session count
/analytics-query what is the signup to first message conversion rate?
/analytics-query how many external users registered in February 2026?
```

## What it does
1. Loads `nep_analytics` from the repo (no server needed)
2. Tries the certified semantic path first (fast, no SQL generation)
3. Falls back to Claude Opus SQL generation if no metric matches
4. Executes the query against the live Supabase DB
5. Returns the answer, SQL used, and provenance (certified vs generated)

## Instructions for Claude

When this skill is invoked with `/analytics-query <question>`:

1. Extract the question from args (everything after `/analytics-query`).

2. Run the query using the AnalyticsSkill:
```python
import sys
sys.path.insert(0, '/Applications/Git/User-Analytics')
from nep_analytics.skill import AnalyticsSkill

skill = AnalyticsSkill(session_id="skill-cli")
response = skill.ask("<QUESTION>")
```

3. Report back:
   - **Answer:** `response.answer`
   - **Response type:** `response.response_type`
   - **SQL used:** `response.sql_used` (show it for transparency)
   - **Certified?** `response.provenance['certified']` if provenance is set
   - If `chart_config` is populated, describe the chart data briefly
   - If `table_data` is populated, show the first 10 rows

4. If an exception is raised, show the full error and the SQL that failed (if available).

## Notes
- The engine reads credentials from `chat_api/.env` — ensure it's populated.
- SQL generation uses `claude-opus-5` (configurable via `SQL_GEN_MODEL` env var).
- Interpretation uses `claude-sonnet-5`.
- Certified metrics return `provenance.certified=True`; ad-hoc queries return `None`.
