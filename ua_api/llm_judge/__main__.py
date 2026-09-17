"""
CLI entry point for the LLM-as-Judge module.

Usage:
  python -m ua_api.llm_judge                          # evaluate all 78 questions
  python -m ua_api.llm_judge --limit 5                # smoke test on first 5 rows
  python -m ua_api.llm_judge --verbose                # print reasoning to console
  python -m ua_api.llm_judge --delay 0.5              # faster (0.5s between calls)
  python -m ua_api.llm_judge --input  docs/NEP_Test_Report.xlsx
  python -m ua_api.llm_judge --output docs/NEP_Judge_Report.xlsx
"""
import argparse
from pathlib import Path

from .runner import DEFAULT_INPUT, DEFAULT_OUTPUT, run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ua_api.llm_judge",
        description=(
            "LLM-as-Judge: evaluate SQL correctness and response accuracy "
            "in the NEP test report using Claude Opus 4.8."
        ),
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT), metavar="FILE.xlsx",
        help=f"Source test report (default: {DEFAULT_INPUT.name})",
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT), metavar="FILE.xlsx",
        help=f"Output judge report (default: {DEFAULT_OUTPUT.name})",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only evaluate the first N rows (useful for a smoke test).",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, metavar="SECS",
        help="Seconds to wait between Opus API calls (default 1.0, use 0 to disable).",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print SQL issues and reasoning snippet to console.",
    )

    args = parser.parse_args()
    run(
        input_path=Path(args.input),
        output_path=Path(args.output),
        limit=args.limit,
        delay_secs=args.delay,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
