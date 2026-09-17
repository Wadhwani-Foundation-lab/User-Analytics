"""
Ablation runner — evaluates the analytics stack against the frozen eval set.

Three test modes:
  certified_only  — run each case through ua_api.metrics.resolver.answer() directly
  adapter         — POST to the chat_adapter /api/chat (requires adapter running)
  sql_guard       — checks must_not_sql fragments against SQL in the response

Run via:  python -m ua_api.validation [--mode certified_only|adapter|sql_guard] [--tag TAG]
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from typing import List, Optional

from .eval_set import EVAL_SET, EvalCase, TODAY

# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    question: str
    expected_path: str
    expected_metric: Optional[str]
    tags: List[str]
    passed: bool
    path_matched: bool          # certified vs text_to_sql
    metric_matched: Optional[bool]  # None = not applicable
    cols_found: List[str]
    cols_missing: List[str]
    sql_violations: List[str]   # must_not_sql fragments that appeared
    rows_in_bounds: Optional[bool]
    row_count: Optional[int]
    error: Optional[str]
    latency_ms: int


@dataclass
class RunSummary:
    mode: str
    total: int
    passed: int
    failed: int
    path_miss: int              # certified/text_to_sql classification wrong
    metric_miss: int            # correct path but wrong metric
    sql_violations: int
    missing_cols: int
    errors: int
    pass_rate_pct: float
    results: List[CaseResult]


# ── Certified-only runner (no HTTP needed) ────────────────────────────────────

def _run_certified_only(cases: List[EvalCase]) -> List[CaseResult]:
    from ua_api.metrics.resolver import answer as metrics_answer

    results = []
    for case in cases:
        t0 = time.monotonic()
        try:
            resp = metrics_answer(case.question, today=TODAY, execute=True)
        except Exception as exc:
            results.append(CaseResult(
                question=case.question,
                expected_path=case.expected_path,
                expected_metric=case.expected_metric,
                tags=list(case.tags),
                passed=False,
                path_matched=False,
                metric_matched=None,
                cols_found=[],
                cols_missing=[],
                sql_violations=[],
                rows_in_bounds=None,
                row_count=None,
                error=str(exc),
                latency_ms=int((time.monotonic() - t0) * 1000),
            ))
            continue

        latency_ms = int((time.monotonic() - t0) * 1000)
        matched = resp.get("matched", False)
        rows = resp.get("rows", [])
        sql = resp.get("sql", "")
        metric_name = resp.get("metric") or resp.get("metric_name")

        # Path determination
        actual_path = "certified" if matched else "text_to_sql"
        path_matched = actual_path == case.expected_path

        # Metric check (certified path only)
        metric_matched: Optional[bool] = None
        if case.expected_path == "certified":
            metric_matched = matched and (metric_name == case.expected_metric)

        # Column check — fall back to SQL text scan when rows are empty (e.g. future date range)
        col_names = list(rows[0].keys()) if rows else []
        if rows:
            cols_found = [c for c in case.must_contain_cols if c in col_names]
            cols_missing = [c for c in case.must_contain_cols if c not in col_names]
        else:
            # No rows: check that each expected column appears as an alias in the SQL
            sql_lower = sql.lower()
            cols_found = [c for c in case.must_contain_cols if c.lower() in sql_lower]
            cols_missing = [c for c in case.must_contain_cols if c.lower() not in sql_lower]

        # SQL guard
        violations = [frag for frag in case.must_not_sql if frag.lower() in sql.lower()]

        # Row bounds
        rows_in_bounds: Optional[bool] = None
        if rows and (case.min_rows is not None or case.max_rows is not None):
            n = len(rows)
            lo = case.min_rows if case.min_rows is not None else 0
            hi = case.max_rows if case.max_rows is not None else float("inf")
            rows_in_bounds = lo <= n <= hi

        passed = (
            path_matched
            and (metric_matched is not False)
            and not cols_missing
            and not violations
            and (rows_in_bounds is not False)
        )

        results.append(CaseResult(
            question=case.question,
            expected_path=case.expected_path,
            expected_metric=case.expected_metric,
            tags=list(case.tags),
            passed=passed,
            path_matched=path_matched,
            metric_matched=metric_matched,
            cols_found=cols_found,
            cols_missing=cols_missing,
            sql_violations=violations,
            rows_in_bounds=rows_in_bounds,
            row_count=len(rows) if rows else None,
            error=None,
            latency_ms=latency_ms,
        ))

    return results


# ── Adapter runner (HTTP to running adapter) ──────────────────────────────────

def _run_adapter(cases: List[EvalCase], base_url: str, api_key: str) -> List[CaseResult]:
    import httpx

    results = []
    for case in cases:
        t0 = time.monotonic()
        try:
            r = httpx.post(
                f"{base_url}/api/chat",
                json={"question": case.question, "session_id": "validation-harness"},
                headers={"x-api-key": api_key} if api_key else {},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            results.append(CaseResult(
                question=case.question,
                expected_path=case.expected_path,
                expected_metric=case.expected_metric,
                tags=list(case.tags),
                passed=False,
                path_matched=False,
                metric_matched=None,
                cols_found=[],
                cols_missing=[],
                sql_violations=[],
                rows_in_bounds=None,
                row_count=None,
                error=str(exc),
                latency_ms=int((time.monotonic() - t0) * 1000),
            ))
            continue

        latency_ms = int((time.monotonic() - t0) * 1000)
        sql = data.get("sql", "") or ""
        table = data.get("table") or {}
        rows = table.get("rows", []) if table else []
        is_certified = bool(data.get("_certified"))

        actual_path = "certified" if is_certified else "text_to_sql"
        path_matched = actual_path == case.expected_path

        metric_matched: Optional[bool] = None
        if case.expected_path == "certified":
            returned_metric = data.get("_metric")
            metric_matched = is_certified and (returned_metric == case.expected_metric)

        col_names = list(rows[0].keys()) if rows else []
        cols_found = [c for c in case.must_contain_cols if c in col_names]
        cols_missing = [c for c in case.must_contain_cols if c not in col_names]

        violations = [frag for frag in case.must_not_sql if frag.lower() in sql.lower()]

        rows_in_bounds: Optional[bool] = None
        if rows and (case.min_rows is not None or case.max_rows is not None):
            n = len(rows)
            lo = case.min_rows if case.min_rows is not None else 0
            hi = case.max_rows if case.max_rows is not None else float("inf")
            rows_in_bounds = lo <= n <= hi

        passed = (
            path_matched
            and (metric_matched is not False)
            and not cols_missing
            and not violations
            and (rows_in_bounds is not False)
        )

        results.append(CaseResult(
            question=case.question,
            expected_path=case.expected_path,
            expected_metric=case.expected_metric,
            tags=list(case.tags),
            passed=passed,
            path_matched=path_matched,
            metric_matched=metric_matched,
            cols_found=cols_found,
            cols_missing=cols_missing,
            sql_violations=violations,
            rows_in_bounds=rows_in_bounds,
            row_count=len(rows) if rows else None,
            error=None,
            latency_ms=latency_ms,
        ))

    return results


# ── Judge runner (adapter + LLM semantic verdict) ────────────────────────────

# Confidence threshold: INACCURATE at >= this level counts as a hard failure.
_JUDGE_FAIL_CONFIDENCE = 70


def _run_judge(cases: List[EvalCase], base_url: str, api_key: str) -> List[CaseResult]:
    """
    For each case: POST to the adapter, extract sql_used, call the LLM judge.

    Pass/fail rules:
      ACCURATE → pass
      INACCURATE with confidence >= _JUDGE_FAIL_CONFIDENCE → fail
      INACCURATE with confidence < _JUDGE_FAIL_CONFIDENCE → pass (logged as warning)
      UNCERTAIN → pass (logged)
      SKIPPED   → pass (no SQL to judge)
    """
    import httpx
    from ua_api.llm_judge.judge import evaluate as judge_evaluate

    results = []
    for case in cases:
        t0 = time.monotonic()

        # Step 1: call the adapter
        try:
            r = httpx.post(
                f"{base_url}/api/chat",
                json={"question": case.question, "session_id": "judge-harness"},
                headers={"x-api-key": api_key} if api_key else {},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            results.append(CaseResult(
                question=case.question,
                expected_path=case.expected_path,
                expected_metric=case.expected_metric,
                tags=list(case.tags),
                passed=False,
                path_matched=False,
                metric_matched=None,
                cols_found=[],
                cols_missing=[],
                sql_violations=[],
                rows_in_bounds=None,
                row_count=None,
                error=f"adapter error: {exc}",
                latency_ms=int((time.monotonic() - t0) * 1000),
            ))
            continue

        sql = data.get("sql_used") or data.get("sql") or ""
        answer = data.get("answer") or ""
        table = data.get("table_data") or {}
        rows = table.get("rows", []) if table else []
        row_count = len(rows) if rows else None

        # Step 2: LLM judge evaluation
        try:
            verdict = judge_evaluate(
                question=case.question,
                sql_used=sql,
                answer=answer,
                row_count=row_count,
                path=case.expected_path,
            )
        except Exception as exc:
            results.append(CaseResult(
                question=case.question,
                expected_path=case.expected_path,
                expected_metric=case.expected_metric,
                tags=list(case.tags),
                passed=False,
                path_matched=True,
                metric_matched=None,
                cols_found=[],
                cols_missing=[],
                sql_violations=[],
                rows_in_bounds=None,
                row_count=row_count,
                error=f"judge error: {exc}",
                latency_ms=int((time.monotonic() - t0) * 1000),
            ))
            continue

        latency_ms = int((time.monotonic() - t0) * 1000)

        # Deterministic checks still run alongside the judge verdict
        col_names = list(rows[0].keys()) if rows else []
        cols_found = [c for c in case.must_contain_cols if c in col_names]
        cols_missing = [c for c in case.must_contain_cols if c not in col_names]
        sql_violations = [f for f in case.must_not_sql if f.lower() in sql.lower()]

        judge_fail = (
            verdict.verdict == "INACCURATE"
            and verdict.confidence_pct >= _JUDGE_FAIL_CONFIDENCE
        )
        passed = not judge_fail and not cols_missing and not sql_violations

        error_msg: Optional[str] = None
        if verdict.verdict == "INACCURATE":
            error_msg = f"INACCURATE ({verdict.confidence_pct}%): {verdict.sql_issues or verdict.reasoning[:120]}"
        elif verdict.verdict == "UNCERTAIN":
            error_msg = f"UNCERTAIN ({verdict.confidence_pct}%): {verdict.reasoning[:120]}"

        results.append(CaseResult(
            question=case.question,
            expected_path=case.expected_path,
            expected_metric=case.expected_metric,
            tags=list(case.tags),
            passed=passed,
            path_matched=True,
            metric_matched=None,
            cols_found=cols_found,
            cols_missing=cols_missing,
            sql_violations=sql_violations,
            rows_in_bounds=None,
            row_count=row_count,
            error=error_msg,
            latency_ms=latency_ms,
        ))

    return results


# ── Summary builder ───────────────────────────────────────────────────────────

def _summarize(mode: str, results: List[CaseResult]) -> RunSummary:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    path_miss = sum(1 for r in results if not r.path_matched)
    metric_miss = sum(1 for r in results if r.metric_matched is False)
    sql_violations = sum(1 for r in results if r.sql_violations)
    missing_cols = sum(1 for r in results if r.cols_missing)
    errors = sum(1 for r in results if r.error)
    return RunSummary(
        mode=mode,
        total=total,
        passed=passed,
        failed=failed,
        path_miss=path_miss,
        metric_miss=metric_miss,
        sql_violations=sql_violations,
        missing_cols=missing_cols,
        errors=errors,
        pass_rate_pct=round(passed / total * 100, 1) if total else 0.0,
        results=results,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def run(
    mode: str = "certified_only",
    tag: Optional[str] = None,
    base_url: str = "http://localhost:8001",
    api_key: str = "",
    output_json: Optional[str] = None,
    verbose: bool = False,
) -> RunSummary:
    cases = [c for c in EVAL_SET if (tag is None or tag in c.tags)]

    if mode == "certified_only":
        cases_to_run = [c for c in cases if c.expected_path == "certified"]
        results = _run_certified_only(cases_to_run)
    elif mode == "adapter":
        results = _run_adapter(cases, base_url, api_key)
    elif mode == "sql_guard":
        cases_to_run = [c for c in cases if c.expected_path == "text_to_sql"]
        results = _run_adapter(cases_to_run, base_url, api_key)
    elif mode == "judge":
        # LLM-judge mode: run adapter then score SQL with Opus. Expensive — use for nightly CI.
        cases_to_run = [c for c in cases if "semantic_guard" in c.tags]
        results = _run_judge(cases_to_run, base_url, api_key)
    else:
        raise ValueError(f"Unknown mode: {mode!r}. Use certified_only | adapter | sql_guard | judge")

    summary = _summarize(mode, results)

    # Print report
    _print_report(summary, verbose=verbose)

    if output_json:
        with open(output_json, "w") as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"\nResults saved to {output_json}")

    return summary


def _print_report(summary: RunSummary, verbose: bool = False) -> None:
    line = "=" * 62
    print(line)
    print(f"  Validation Run  |  mode={summary.mode}  |  {summary.total} cases")
    print(line)
    print(f"  PASS: {summary.passed:>3}   FAIL: {summary.failed:>3}   ({summary.pass_rate_pct}%)")
    print(f"  Path misclassified : {summary.path_miss}")
    print(f"  Wrong metric       : {summary.metric_miss}")
    print(f"  SQL violations     : {summary.sql_violations}")
    print(f"  Missing columns    : {summary.missing_cols}")
    print(f"  Errors             : {summary.errors}")
    print(line)

    for r in summary.results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.question[:58]}")
        if not r.passed or verbose:
            if r.error:
                print(f"         ERROR: {r.error}")
            if not r.path_matched:
                print(f"         path: expected={r.expected_path!r} got={'certified' if r.metric_matched else 'text_to_sql'!r}")
            if r.metric_matched is False:
                print(f"         metric mismatch: expected={r.expected_metric!r}")
            if r.cols_missing:
                print(f"         missing cols: {r.cols_missing}")
            if r.sql_violations:
                print(f"         SQL violations: {r.sql_violations}")
            if r.latency_ms:
                print(f"         latency: {r.latency_ms}ms")
    print(line)
