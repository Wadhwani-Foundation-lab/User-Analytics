"""
Ad-hoc re-run of just the previously-flagged (INCORRECT / PARTIALLY_CORRECT)
single-turn questions, to verify the fixes without paying for a full 78-question
+ judge run. Reuses run_nep_tests.py and run_judge.py machinery unchanged.

Usage:
    python nep_analytics/tests/run_flagged_only.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from nep_analytics.tests.run_nep_tests import load_questions, run_question, MAX_CONCURRENT  # noqa: E402
from nep_analytics.tests.run_judge import judge_one, JUDGE_MODEL  # noqa: E402

PREV_JUDGE_REPORT = HERE / "judge_report.json"

FLAGGED_NUMS = [16, 17, 21, 23, 25, 31, 39, 44, 48, 50, 52, 63, 68]


def load_prev_verdicts() -> dict[int, str]:
    with open(PREV_JUDGE_REPORT, encoding="utf-8") as f:
        data = json.load(f)
    return {r["num"]: r["judge"]["verdict"] for r in data["results"]}


async def main():
    all_questions = load_questions()
    questions = [q for q in all_questions if q["num"] in FLAGGED_NUMS]
    print(f"Re-running {len(questions)} previously-flagged questions...\n")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient() as client:
        tasks = [run_question(client, semaphore, q) for q in questions]
        results = await asyncio.gather(*tasks)

    print(f"\n{'─'*70}\n  Judging {len(results)} results with {JUDGE_MODEL}\n{'─'*70}")
    judge_sem = asyncio.Semaphore(4)

    async def _judge(r):
        j = await judge_one(
            judge_sem,
            question=r["question"],
            status=r["status"],
            response_type=r.get("response_type", ""),
            sql=r.get("sql_used", ""),
            answer=r.get("answer", ""),
            row_count=r.get("row_count"),
            error=r.get("error"),
        )
        return {**r, "judge": j}

    judged = await asyncio.gather(*[_judge(r) for r in results])
    judged.sort(key=lambda r: r["num"])

    prev_verdicts = load_prev_verdicts()

    print(f"\n{'='*90}")
    print(f"  Before → After comparison ({len(judged)} questions)")
    print(f"{'='*90}")
    improved = same = worse = 0
    rank = {"INCORRECT": 0, "UNCERTAIN": 1, "PARTIALLY_CORRECT": 2, "NOT_EVALUABLE": 1, "CORRECT": 3}
    for r in judged:
        prev = prev_verdicts.get(r["num"], "?")
        new = r["judge"]["verdict"]
        prev_r, new_r = rank.get(prev, 1), rank.get(new, 1)
        if new_r > prev_r:
            tag, improved = "IMPROVED", improved + 1
        elif new_r < prev_r:
            tag, worse = "WORSE", worse + 1
        else:
            tag, same = "SAME", same + 1
        print(f"  Q{r['num']:02d}  {prev:<18} -> {new:<18}  [{tag}]")
        print(f"        {r['question'][:85]}")
        if new != "CORRECT":
            print(f"        issue: {r['judge'].get('sql_issues') or r['judge'].get('reasoning', '')[:200]}")

    print(f"\n  Improved: {improved}   Same: {same}   Worse: {worse}")

    out = HERE / "flagged_recheck_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(judged, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
