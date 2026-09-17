# CLAUDE.md — ua_api/feedback

## What this module is

Read-only quality signal reader. Queries `message_rating` and `message_rating_feedback`
from `nep_liftoffx_data_sample` to surface aggregate AI-chat quality.

```
feedback/
├── signals.py    # overall_rating, rating_by_period, low_rated_questions
└── __main__.py   # CLI: python -m ua_api.feedback
```

## Running

```bash
# Summary report
python -m ua_api.feedback

# Include sample low-rated questions
python -m ua_api.feedback --verbose

# Low-rated questions only (candidates for new eval cases)
python -m ua_api.feedback --low-rated --start 2026-01-01 --end 2026-03-01

# Higher threshold
python -m ua_api.feedback --low-rated --max-rating 3 --limit 30
```

## Schema note

`message_rating` is a TEXT column — all numeric comparisons cast via `::INTEGER`.
A guard `message_rating ~ '^[0-9]+$'` filters out any non-numeric values before casting.

## Feedback loop design

The provenance fields (`_certified`, `_metric`, `_confidence`) on `ChatResponse` are
the bridge between this module and per-metric quality tracking. Once the frontend
starts sending back which metric produced a response (e.g. in a thumbs-up/down payload),
queries in `signals.py` can be extended to GROUP BY metric name.

Until then, `overall_rating()` and `low_rated_questions()` serve as the quality floor:
low-rated questions are candidates for:
1. A new certified metric YAML
2. A new eval case in `ua_api/validation/eval_set.py`
3. A fix to the system prompt blocks in `ua_api/skills/blocks.py`
