"""
Ad-hoc re-run of just the 20 multi-turn scenarios (skips the 78 single-turn
questions) to get a current, accurate INCORRECT/PARTIALLY_CORRECT list after
code changes, without paying for a full single-turn re-run too.

Usage:
    python nep_analytics/tests/run_multiturn_only.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from nep_analytics.tests.run_nep_tests import load_scenarios, run_all_scenarios  # noqa: E402
from nep_analytics.tests.run_judge import judge_multi_turn  # noqa: E402

OUT = HERE / "multiturn_recheck_report.json"


async def main():
    scenarios = load_scenarios()
    print(f"Running {len(scenarios)} multi-turn scenarios...\n")
    scenario_results = await run_all_scenarios(scenarios)

    print(f"\n{'─'*70}\n  Judging {sum(len(s['turns']) for s in scenario_results)} turns\n{'─'*70}")
    judged_scenarios = await judge_multi_turn(scenario_results)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(judged_scenarios, f, indent=2, ensure_ascii=False)

    verdicts = [t["judge"]["verdict"] for s in judged_scenarios for t in s["turns"]]
    total = len(verdicts)
    print(f"\n{'='*70}\n  Multi-turn verdicts — {total} turns\n{'='*70}")
    for v in ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "UNCERTAIN", "NOT_EVALUABLE"):
        n = verdicts.count(v)
        print(f"  {v:<22}: {n:>2}  ({round(n/total*100,1) if total else 0}%)")

    print(f"\n  INCORRECT turns:")
    for s in judged_scenarios:
        for t in s["turns"]:
            if t["judge"]["verdict"] == "INCORRECT":
                print(f"    {s['id']} T{t['turn_num']}: {t['question']}")
                print(f"      issue: {t['judge'].get('sql_issues') or t['judge'].get('reasoning','')[:200]}")

    print(f"\n  Saved -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
