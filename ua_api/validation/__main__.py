"""
CLI entry point for the validation harness.

Usage:
  python -m ua_api.validation
  python -m ua_api.validation --mode certified_only
  python -m ua_api.validation --mode adapter --base-url http://localhost:8001
  python -m ua_api.validation --mode sql_guard --api-key $API_SECRET_KEY
  python -m ua_api.validation --tag retention
  python -m ua_api.validation --mode certified_only --output test_results.json
  python -m ua_api.validation --verbose
"""
import argparse
import sys

from .runner import run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ua_api.validation",
        description="Run the frozen eval set against the analytics stack.",
    )
    parser.add_argument(
        "--mode",
        default="certified_only",
        choices=["certified_only", "adapter", "sql_guard", "judge"],
        help=(
            "certified_only: metrics path only (no HTTP). "
            "adapter: full HTTP round-trip. "
            "sql_guard: text-to-SQL anti-hallucination checks. "
            "judge: semantic verdict via Opus LLM (requires adapter running, expensive)."
        ),
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Filter to eval cases with this tag (e.g. retention, events, certified).",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Base URL for adapter/sql_guard modes (default: http://localhost:8001).",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="x-api-key header value for the adapter.",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE.json",
        help="Write full results to this JSON file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-case details even for passing cases.",
    )

    args = parser.parse_args()
    summary = run(
        mode=args.mode,
        tag=args.tag,
        base_url=args.base_url,
        api_key=args.api_key,
        output_json=args.output,
        verbose=args.verbose,
    )

    sys.exit(0 if summary.failed == 0 else 1)


if __name__ == "__main__":
    main()
