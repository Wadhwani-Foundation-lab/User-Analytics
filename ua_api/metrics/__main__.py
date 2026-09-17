"""
metrics CLI.

  python -m metrics list                       # list certified metrics
  python -m metrics show <name>                # show one metric's spec + template
  python -m metrics render <name> [--params JSON]   # render SQL (no DB)
  python -m metrics validate [--name N]        # run each template against live DB
  python -m metrics resolve "<question>"       # classify a question -> metric+params
  python -m metrics answer "<question>"        # full path: resolve -> render -> execute
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from .registry import load_registry
from .renderer import render


def _today() -> str:
    return date.today().isoformat()


def cmd_list(_args) -> int:
    reg = load_registry()
    print(f"\n{len(reg)} certified metrics\n" + "=" * 60)
    for m in reg:
        params = []
        if m.date_filter:
            params.append("period")
        params += list(m.choices.keys())
        if m.segment:
            params.append("segment")
        print(f"\n■ {m.name}   [{m.response_type}]")
        print(f"  {m.description.strip()}")
        print(f"  params: {params or 'none'}  | source: {m.source}")
    return 0


def cmd_show(args) -> int:
    reg = load_registry()
    m = reg.get(args.name)
    if not m:
        print(f"unknown metric: {args.name}")
        return 1
    print(json.dumps({
        "name": m.name, "description": m.description.strip(), "aliases": m.aliases,
        "certified": m.certified, "owner": m.owner, "source": m.source,
        "returns": {"response_type": m.response_type, "label": m.label_column, "value": m.value_column},
        "date_filter": m.date_filter.column if m.date_filter else None,
        "choices": {k: {"default": c.default, "values": c.values} for k, c in m.choices.items()},
        "segment": (m.segment.column if m.segment else None),
    }, indent=2))
    print("\n--- sql_template ---\n" + m.sql_template)
    return 0


def cmd_render(args) -> int:
    reg = load_registry()
    m = reg.get(args.name)
    if not m:
        print(f"unknown metric: {args.name}")
        return 1
    params = json.loads(args.params) if args.params else {}
    sql, resolved = render(m, params)
    print(sql)
    return 0


def cmd_validate(args) -> int:
    from ..data_context.config import run_sql

    reg = load_registry()
    targets = [reg.get(args.name)] if args.name else list(reg)
    targets = [t for t in targets if t]
    print("\nMETRIC VALIDATION (render with defaults -> execute against live DB)")
    print("=" * 70)
    failures = 0
    for m in targets:
        try:
            sql, _ = render(m, {})  # defaults only
            rows = run_sql(sql)
            cols = list(rows[0].keys()) if rows else []
            # check the declared value column is actually produced
            missing = m.value_column and m.value_column not in cols and rows
            flag = "✗" if missing else "✓"
            if missing:
                failures += 1
            print(f"  {flag} {m.name:42} {len(rows)} rows  cols={cols}")
            if missing:
                print(f"      ! declared value '{m.value_column}' not in result columns")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  ✗ {m.name:42} ERROR: {str(exc)[:120]}")
    print("=" * 70)
    print(f"{len(targets) - failures}/{len(targets)} metrics valid")
    return 1 if failures else 0


def cmd_resolve(args) -> int:
    from .resolver import resolve

    match = resolve(args.question, today=_today())
    print(json.dumps(match, indent=2) if match else "no metric matched (would fall back to text-to-SQL)")
    return 0


def cmd_answer(args) -> int:
    from .resolver import answer

    result = answer(args.question, today=_today())
    # rows can be large; trim for console
    if result.get("rows") and len(result["rows"]) > 10:
        shown = result["rows"][:10]
        result = {**result, "rows": shown, "rows_truncated_to": 10}
    print(json.dumps(result, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="metrics", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    s = sub.add_parser("show")
    s.add_argument("name")
    s.set_defaults(func=cmd_show)

    r = sub.add_parser("render")
    r.add_argument("name")
    r.add_argument("--params", help="JSON params object")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("validate")
    v.add_argument("--name", help="validate only this metric")
    v.set_defaults(func=cmd_validate)

    rs = sub.add_parser("resolve")
    rs.add_argument("question")
    rs.set_defaults(func=cmd_resolve)

    a = sub.add_parser("answer")
    a.add_argument("question")
    a.set_defaults(func=cmd_answer)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
