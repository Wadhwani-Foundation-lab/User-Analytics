"""
CLI entry point for the test suite.

Usage:
  python -m ua_api.test_suite
  python -m ua_api.test_suite --limit 10
  python -m ua_api.test_suite --category "Multi-Filter Mentor Network Queries"
  python -m ua_api.test_suite --skip-multiturn
  python -m ua_api.test_suite --output /path/to/report.xlsx
"""
import argparse
import sys
from pathlib import Path

from .runner import DEFAULT_OUTPUT, run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ua_api.test_suite",
        description="Run all NEP Test Questions against the analytics adapter and generate an Excel report.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Run only the first N questions (useful for a quick smoke test).",
    )
    parser.add_argument(
        "--category", default=None,
        help="Filter to questions whose category contains this string (case-insensitive).",
    )
    parser.add_argument(
        "--skip-multiturn", action="store_true",
        help="Skip the multi-turn conversation scenarios.",
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT), metavar="FILE.xlsx",
        help=f"Output Excel file path (default: {DEFAULT_OUTPUT}).",
    )

    args = parser.parse_args()
    run(
        category=args.category,
        limit=args.limit,
        skip_multiturn=args.skip_multiturn,
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
