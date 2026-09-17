"""
CLI entry point for the feedback signal reader.

Usage:
  python -m ua_api.feedback
  python -m ua_api.feedback --verbose
  python -m ua_api.feedback --low-rated --start 2026-01-01 --end 2026-03-01
"""
import argparse

from .signals import low_rated_questions, print_report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ua_api.feedback",
        description="Read AI chat quality signals from the activity table.",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Include sample low-rated questions in report.")
    parser.add_argument("--low-rated", action="store_true",
                        help="Print low-rated questions only (for eval set review).")
    parser.add_argument("--max-rating", type=int, default=2,
                        help="Rating threshold for --low-rated (default 2).")
    parser.add_argument("--start", default=None, metavar="YYYY-MM-DD",
                        help="Filter low-rated questions from this date.")
    parser.add_argument("--end", default=None, metavar="YYYY-MM-DD",
                        help="Filter low-rated questions up to (not including) this date.")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max low-rated questions to return (default 20).")

    args = parser.parse_args()

    if args.low_rated:
        rows = low_rated_questions(
            max_rating=args.max_rating,
            limit=args.limit,
            start_date=args.start,
            end_date=args.end,
        )
        if not rows:
            print("No low-rated questions found for the given filters.")
            return
        print(f"{'Date':>12}  {'Rating'}  {'Question':<60}  Feedback")
        print("-" * 100)
        for row in rows:
            date = row.get("message_date", "")
            rating = row.get("message_rating", "")
            q = (row.get("message_query") or "")[:58]
            fb = (row.get("message_rating_feedback") or "")[:40]
            print(f"{str(date):>12}  [{rating}]    {q:<60}  {fb}")
        return

    print_report(verbose=args.verbose)


if __name__ == "__main__":
    main()
