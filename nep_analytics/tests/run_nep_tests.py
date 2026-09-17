"""
NEP Analytics Test Runner
Executes all 78 single-turn test questions + 20 multi-turn scenarios against
the nep_analytics API (port 8002) and saves a structured report to
nep_analytics/tests/test_report.json.

Usage:
    python -m nep_analytics.tests.run_nep_tests
    # or directly:
    python nep_analytics/tests/run_nep_tests.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import openpyxl

# ── Config ───────────────────────────────────────────────────────────────────

API_URL = os.getenv("NEP_API_URL", "http://localhost:8002")
API_KEY = os.getenv("NEP_API_KEY", "nep-analytics-internal-2026")
HEADERS = {"Content-Type": "application/json", "x-api-key": API_KEY}
MAX_CONCURRENT = 5        # limit to avoid LLM rate limits
REQUEST_TIMEOUT = 90.0    # seconds per question

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
QUESTIONS_FILE = REPO_ROOT / "docs" / "NEP Test Questions.xlsx"
SCENARIOS_FILE = Path(__file__).resolve().parent / "multi_turn_scenarios.json"
REPORT_FILE = Path(__file__).resolve().parent / "test_report.json"


# ── Status classification ────────────────────────────────────────────────────

def classify(resp: dict | None, error: str | None, http_status: int) -> str:
    """Assign a status tag to a test result."""
    if error or http_status >= 500:
        if error and "parse" in error.lower():
            return "PARSE_ERROR"
        if error and ("database" in error.lower() or "sql" in error.lower()):
            return "SQL_ERROR"
        return "API_ERROR"

    if resp is None:
        return "API_ERROR"

    sql = resp.get("sql_used") or ""
    answer = (resp.get("answer") or "").lower()
    response_type = resp.get("response_type", "")

    # LLM chose not to generate SQL → asked for clarification
    if not sql:
        return "CLARIFICATION_NEEDED"

    # SQL ran but returned no data
    no_data_phrases = [
        "no data", "no results", "no matching", "no records", "couldn't find",
        "0 results", "zero results", "not find", "no users found", "no events found",
        "no mentors", "does not exist", "no information available",
        "no entries", "no rows",
    ]
    if any(p in answer for p in no_data_phrases):
        return "DATA_NOT_AVAILABLE"

    # Table/chart with no rows
    table = resp.get("table_data") or {}
    if response_type == "table" and isinstance(table.get("rows"), list) and len(table["rows"]) == 0:
        return "DATA_NOT_AVAILABLE"

    chart = resp.get("chart_config") or {}
    if response_type in ("bar_chart", "line_chart") and isinstance(chart.get("labels"), list) and len(chart["labels"]) == 0:
        return "DATA_NOT_AVAILABLE"

    return "PASS"


def scenario_overall_status(turn_statuses: list[str]) -> str:
    """Roll up turn statuses to a single scenario status."""
    error_statuses = {"SQL_ERROR", "PARSE_ERROR", "API_ERROR"}
    if any(s in error_statuses for s in turn_statuses):
        return "ERROR"
    if all(s == "PASS" for s in turn_statuses):
        return "PASS"
    if all(s in ("PASS", "DATA_NOT_AVAILABLE") for s in turn_statuses):
        # At least one was data n/a but no errors
        return "PARTIAL"
    if any(s == "CLARIFICATION_NEEDED" for s in turn_statuses):
        return "CLARIFICATION_NEEDED"
    return "PARTIAL"


# ── Question loader ──────────────────────────────────────────────────────────

def _row_count(resp_data: dict | None) -> int:
    """
    Number of rows actually returned by the query. table_data/chart_config
    cover table and chart responses; a "text" response with a non-empty
    answer represents exactly one scalar row that never gets surfaced as
    table_data, so it must still count as 1 (not 0) for the judge to reason
    about row-count consistency correctly.
    """
    resp_data = resp_data or {}
    table_rows = len((resp_data.get("table_data") or {}).get("rows") or [])
    if table_rows:
        return table_rows
    chart_labels = len((resp_data.get("chart_config") or {}).get("labels") or [])
    if chart_labels:
        return chart_labels
    if resp_data.get("response_type") == "text" and (resp_data.get("answer") or "").strip():
        return 1
    return 0


def load_questions() -> list[dict]:
    wb = openpyxl.load_workbook(QUESTIONS_FILE)
    ws = wb.active
    questions = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        num, category, question = row[0], row[1], row[2]
        if question and str(question).strip():
            questions.append({
                "num": num,
                "category": str(category or "").strip(),
                "question": str(question).strip(),
            })
    return questions


def load_scenarios() -> list[dict]:
    with open(SCENARIOS_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── Single question execution ────────────────────────────────────────────────

async def run_question(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    q: dict,
) -> dict:
    session_id = f"nep-test-{q['num']}-{uuid.uuid4().hex[:8]}"
    payload = {"session_id": session_id, "question": q["question"], "history": []}

    start = time.monotonic()
    resp_data = None
    error = None
    http_status = 0

    async with semaphore:
        try:
            r = await client.post(
                f"{API_URL}/api/chat",
                json=payload,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            http_status = r.status_code
            if r.status_code == 200:
                resp_data = r.json()
            else:
                body = r.text[:300]
                error = f"HTTP {r.status_code}: {body}"
        except httpx.TimeoutException:
            error = "Request timed out after 90s"
            http_status = 0
        except Exception as exc:
            error = str(exc)[:200]
            http_status = 0

    latency_ms = round((time.monotonic() - start) * 1000)
    status = classify(resp_data, error, http_status)

    result = {
        "num": q["num"],
        "category": q["category"],
        "question": q["question"],
        "status": status,
        "http_status": http_status,
        "latency_ms": latency_ms,
        "answer": (resp_data or {}).get("answer", ""),
        "response_type": (resp_data or {}).get("response_type", ""),
        "sql_used": (resp_data or {}).get("sql_used", ""),
        "certified": (
            (resp_data or {}).get("provenance") or {}
        ).get("certified", False),
        "metric": (
            (resp_data or {}).get("provenance") or {}
        ).get("metric"),
        "error": error,
        "has_chart": bool((resp_data or {}).get("chart_config")),
        "has_table": bool((resp_data or {}).get("table_data")),
        "row_count": _row_count(resp_data),
    }

    icon = {"PASS": "✓", "DATA_NOT_AVAILABLE": "◌", "CLARIFICATION_NEEDED": "?",
            "SQL_ERROR": "✗", "PARSE_ERROR": "✗", "API_ERROR": "✗"}.get(status, "?")
    print(f"  [{icon}] Q{q['num']:02d} {status:<22} {latency_ms:>5}ms  {q['question'][:65]}")
    return result


# ── Multi-turn scenario execution ─────────────────────────────────────────────

async def run_scenario(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    scenario: dict,
) -> dict:
    """Run all turns of a scenario sequentially under one session_id."""
    session_id = f"nep-mt-{scenario['id']}-{uuid.uuid4().hex[:8]}"
    turns = []
    scenario_start = time.monotonic()

    print(f"\n  ── {scenario['id']}: {scenario['name']}")

    async with semaphore:
        for ti, question in enumerate(scenario["turns"], 1):
            payload = {"session_id": session_id, "question": question, "history": []}
            start = time.monotonic()
            resp_data = None
            error = None
            http_status = 0

            try:
                r = await client.post(
                    f"{API_URL}/api/chat",
                    json=payload,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                http_status = r.status_code
                if r.status_code == 200:
                    resp_data = r.json()
                else:
                    error = f"HTTP {r.status_code}: {r.text[:200]}"
            except httpx.TimeoutException:
                error = "Request timed out after 90s"
            except Exception as exc:
                error = str(exc)[:200]

            latency_ms = round((time.monotonic() - start) * 1000)
            status = classify(resp_data, error, http_status)

            icon = {"PASS": "✓", "DATA_NOT_AVAILABLE": "◌", "CLARIFICATION_NEEDED": "?",
                    "SQL_ERROR": "✗", "PARSE_ERROR": "✗", "API_ERROR": "✗"}.get(status, "?")
            print(f"    T{ti} [{icon}] {status:<22} {latency_ms:>5}ms  {question[:60]}")

            turns.append({
                "turn_num": ti,
                "question": question,
                "status": status,
                "http_status": http_status,
                "latency_ms": latency_ms,
                "answer": (resp_data or {}).get("answer", ""),
                "response_type": (resp_data or {}).get("response_type", ""),
                "sql_used": (resp_data or {}).get("sql_used", ""),
                "error": error,
                "row_count": _row_count(resp_data),
            })

            # Stop the scenario early on a hard error
            if status in ("SQL_ERROR", "PARSE_ERROR", "API_ERROR"):
                break

    total_latency = round((time.monotonic() - scenario_start) * 1000)
    overall = scenario_overall_status([t["status"] for t in turns])

    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "overall_status": overall,
        "total_latency_ms": total_latency,
        "turns": turns,
    }


# ── Main runners ──────────────────────────────────────────────────────────────

async def run_all(questions: list[dict]) -> list[dict]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient() as client:
        tasks = [run_question(client, semaphore, q) for q in questions]
        results = await asyncio.gather(*tasks)
    return list(results)


async def run_all_scenarios(scenarios: list[dict]) -> list[dict]:
    # Scenarios run with concurrency 2 — each scenario is already sequential internally
    semaphore = asyncio.Semaphore(2)
    async with httpx.AsyncClient() as client:
        tasks = [run_scenario(client, semaphore, s) for s in scenarios]
        results = await asyncio.gather(*tasks)
    return list(results)


def build_report(
    results: list[dict],
    scenario_results: list[dict],
    started_at: str,
    finished_at: str,
) -> dict:
    total = len(results)
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    passed = by_status.get("PASS", 0)
    certified = sum(1 for r in results if r.get("certified"))
    data_na = by_status.get("DATA_NOT_AVAILABLE", 0)
    clarification = by_status.get("CLARIFICATION_NEEDED", 0)
    errors = by_status.get("SQL_ERROR", 0) + by_status.get("PARSE_ERROR", 0) + by_status.get("API_ERROR", 0)

    avg_latency = round(sum(r["latency_ms"] for r in results) / total) if total else 0

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "pass": 0, "data_na": 0, "error": 0, "clarification": 0}
        by_category[cat]["total"] += 1
        s = r["status"]
        if s == "PASS":
            by_category[cat]["pass"] += 1
        elif s == "DATA_NOT_AVAILABLE":
            by_category[cat]["data_na"] += 1
        elif s in ("SQL_ERROR", "PARSE_ERROR", "API_ERROR"):
            by_category[cat]["error"] += 1
        elif s == "CLARIFICATION_NEEDED":
            by_category[cat]["clarification"] += 1

    # Multi-turn summary
    mt_total = len(scenario_results)
    mt_pass = sum(1 for s in scenario_results if s["overall_status"] == "PASS")
    mt_partial = sum(1 for s in scenario_results if s["overall_status"] == "PARTIAL")
    mt_error = sum(1 for s in scenario_results if s["overall_status"] == "ERROR")
    mt_clarification = sum(1 for s in scenario_results if s["overall_status"] == "CLARIFICATION_NEEDED")

    return {
        "meta": {
            "api_url": API_URL,
            "started_at": started_at,
            "finished_at": finished_at,
            "total_questions": total,
            "total_scenarios": mt_total,
        },
        "summary": {
            "pass": passed,
            "data_not_available": data_na,
            "clarification_needed": clarification,
            "sql_error": by_status.get("SQL_ERROR", 0),
            "parse_error": by_status.get("PARSE_ERROR", 0),
            "api_error": by_status.get("API_ERROR", 0),
            "total_errors": errors,
            "certified_path": certified,
            "sql_gen_path": passed - certified,
            "pass_rate_pct": round(passed / total * 100, 1) if total else 0,
            "avg_latency_ms": avg_latency,
        },
        "multi_turn_summary": {
            "total": mt_total,
            "pass": mt_pass,
            "partial": mt_partial,
            "error": mt_error,
            "clarification_needed": mt_clarification,
            "pass_rate_pct": round(mt_pass / mt_total * 100, 1) if mt_total else 0,
        },
        "by_category": by_category,
        "results": results,
        "scenario_results": scenario_results,
    }


def print_summary(report: dict) -> None:
    s = report["summary"]
    m = report["meta"]
    mt = report["multi_turn_summary"]
    print("\n" + "=" * 70)
    print(f"  NEP Analytics Test Report — {m['finished_at'][:19]}")
    print("=" * 70)
    print(f"  Single-turn ({m['total_questions']} questions):")
    print(f"  ✓  PASS          : {s['pass']}  ({s['pass_rate_pct']}%)")
    print(f"     ↳ certified   : {s['certified_path']}")
    print(f"     ↳ sql-gen     : {s['sql_gen_path']}")
    print(f"  ◌  Data N/A      : {s['data_not_available']}")
    print(f"  ?  Clarification : {s['clarification_needed']}")
    print(f"  ✗  SQL error     : {s['sql_error']}")
    print(f"  ✗  Parse error   : {s['parse_error']}")
    print(f"  ✗  API error     : {s['api_error']}")
    print(f"  Avg latency      : {s['avg_latency_ms']}ms")
    print()
    print(f"  Multi-turn ({m['total_scenarios']} scenarios):")
    print(f"  ✓  PASS          : {mt['pass']}  ({mt['pass_rate_pct']}%)")
    print(f"  ~  PARTIAL       : {mt['partial']}")
    print(f"  ✗  ERROR         : {mt['error']}")
    print(f"  ?  Clarification : {mt['clarification_needed']}")
    print()
    print("  By category (single-turn):")
    for cat, counts in report["by_category"].items():
        pct = round(counts["pass"] / counts["total"] * 100) if counts["total"] else 0
        print(f"    {cat[:45]:<45}  {counts['pass']}/{counts['total']} ({pct}%)")
    print("=" * 70)
    print(f"  Report saved to: {REPORT_FILE}")
    print("=" * 70)


def main() -> None:
    print(f"\nNEP Analytics Test Runner")
    print(f"  API:  {API_URL}")
    print(f"  Max concurrent: {MAX_CONCURRENT}")

    # Verify server is reachable
    try:
        r = httpx.get(f"{API_URL}/api/health", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"\n✗ Health check failed: HTTP {r.status_code}")
            sys.exit(1)
        health = r.json()
        print(f"  SQL gen model:  {health.get('sql_gen_model')}")
        print(f"  Supabase:       {'✓' if health.get('supabase_connected') else '✗'}")
    except Exception as e:
        print(f"\n✗ Cannot reach {API_URL}: {e}")
        sys.exit(1)

    questions = load_questions()
    scenarios = load_scenarios()
    started_at = datetime.utcnow().isoformat() + "Z"

    # ── Single-turn questions ─────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  SINGLE-TURN: {len(questions)} questions")
    print(f"{'─'*70}")
    results = asyncio.run(run_all(questions))

    # ── Multi-turn scenarios ──────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  MULTI-TURN: {len(scenarios)} scenarios")
    print(f"{'─'*70}")
    scenario_results = asyncio.run(run_all_scenarios(scenarios))

    finished_at = datetime.utcnow().isoformat() + "Z"

    report = build_report(results, scenario_results, started_at, finished_at)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print_summary(report)


if __name__ == "__main__":
    main()
