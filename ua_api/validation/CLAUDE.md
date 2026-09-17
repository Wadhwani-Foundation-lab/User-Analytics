# CLAUDE.md — ua_api/validation

## What this module is

Frozen evaluation set + ablation runner for the analytics stack.

```
validation/
├── eval_set.py     # EvalCase dataclass + EVAL_SET list (immutable)
├── runner.py       # Run cases through certified_only | adapter | sql_guard
└── __main__.py     # CLI: python -m ua_api.validation
```

## Running

```bash
# Certified-only (no HTTP, no adapter running needed)
python -m ua_api.validation

# Full adapter round-trip (adapter must be running on port 8001)
python -m ua_api.validation --mode adapter --api-key $API_SECRET_KEY

# SQL hallucination guard (text-to-SQL path only)
python -m ua_api.validation --mode sql_guard

# Filter by tag
python -m ua_api.validation --tag retention

# Save results to file
python -m ua_api.validation --output test_results.json
```

Exit code 0 = all passed, 1 = any failures (CI-safe).

## Adding eval cases

Edit `eval_set.py` only. Never mutate `EVAL_SET` at runtime — all cases are frozen dataclasses.

```python
EvalCase(
    question="...",
    expected_path="certified",      # or "text_to_sql"
    expected_metric="metric_name",  # certified path only
    must_contain_cols=["col1", "col2"],
    must_not_sql=["hallucinated_column"],
    min_rows=1, max_rows=10,
    tags=["my_tag"],
)
```

Column check degrades gracefully when rows are empty (e.g. future date range) — falls back to checking that expected column names appear in the SQL SELECT clause.

## Interpreting failures

| Failure field | Meaning |
|---|---|
| `path_matched=False` | Certified vs text-to-SQL routing is wrong |
| `metric_matched=False` | Right path, wrong metric matched |
| `cols_missing` | Expected output columns absent (likely SQL bug) |
| `sql_violations` | Hallucinated column/value appeared in generated SQL |
| `error` | Python exception — resolver/DB connectivity issue |

## Anti-hallucination checks

`must_not_sql` fragments are checked case-insensitively against the SQL returned by the resolver or adapter. Use this to catch:
- Invented `activity_type` values (`'ai_chat'`, `'live_event'`)
- Wrong column names (`events.program` instead of `program_key`)
- CTE usage (`WITH ... AS`) — not valid in Supabase RPC
