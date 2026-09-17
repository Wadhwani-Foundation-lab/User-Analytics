"""
Quality runner — executes all catalog-driven checks, writes a JSON report
(telemetry-style: timestamped, with model/schema context) and prints a summary.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from ..catalog import load_catalog
from ..config import REPORTS_DIR, run_sql
from .checks import CheckResult, Status, run_all_checks

_STATUS_ICON = {
    Status.PASS: "✓",
    Status.WARN: "!",
    Status.FAIL: "✗",
    Status.ERROR: "?",
}


def _summary(results: List[CheckResult]) -> dict:
    counts = {s.value: 0 for s in Status}
    for r in results:
        counts[r.status.value] += 1
    return counts


def run(
    only_table: Optional[str] = None,
    write_report: bool = True,
    timestamp: Optional[str] = None,
) -> dict:
    """
    Run the full quality suite.

    `timestamp` is injected by the caller (the module cannot read the clock in
    all execution contexts); when omitted the report records null.
    """
    catalog = load_catalog()
    results = run_all_checks(catalog, run_sql, only_table=only_table)
    summary = _summary(results)

    report = {
        "generated_at": timestamp,
        "tables_checked": [t.name for t in catalog] if not only_table else [only_table],
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }

    # Console output -------------------------------------------------------
    print("\n" + "=" * 70)
    print("DATA QUALITY REPORT" + (f"  (table: {only_table})" if only_table else ""))
    print("=" * 70)
    current_table = None
    for r in sorted(results, key=lambda x: (x.table, x.check)):
        if r.table != current_table:
            current_table = r.table
            print(f"\n■ {r.table}")
        icon = _STATUS_ICON[r.status]
        line = f"  {icon} [{r.status.value:5}] {r.check}:{r.target} — {r.detail}"
        print(line)
        if r.samples and r.status in (Status.FAIL, Status.WARN):
            print(f"        e.g. {', '.join(r.samples[:5])}")

    print("\n" + "-" * 70)
    print(
        f"Summary: {summary['PASS']} pass · {summary['WARN']} warn · "
        f"{summary['FAIL']} fail · {summary['ERROR']} error"
    )
    print("-" * 70)

    if write_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / "quality_report.json"
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"Report written to {out}")

    return report


def has_blocking_failures(report: dict) -> bool:
    """FAIL or ERROR are blocking; WARN (orphans, date smells on dirty sample
    data) is informational at this phase."""
    return report["summary"]["FAIL"] > 0 or report["summary"]["ERROR"] > 0
