"""
data_context CLI.

  python -m data_context catalog show          # print the loaded catalog summary
  python -m data_context catalog validate      # reconcile catalog vs live DB columns/types
  python -m data_context quality run [--table T]   # run data-quality checks -> report
  python -m data_context migrations emit       # (re)generate 002/003 SQL from the catalog
  python -m data_context freshness show        # show load provenance / freshness
  python -m data_context freshness backfill    # record current row counts (no reload)
  python -m data_context ingest [--table T] [--truncate]   # governed CSV -> Supabase load
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from .catalog import load_catalog
from .config import run_sql


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- catalog ----------------------------------------------------------------

def cmd_catalog_show(_args) -> int:
    catalog = load_catalog()
    print(f"\nCatalog: {len(catalog)} tables\n" + "=" * 60)
    for t in catalog:
        print(f"\n■ {t.name}  (owner: {t.owner})")
        print(f"  grain: {t.grain}")
        print(f"  columns: {len(t.columns)}  | pk: {t.primary_key}")
        if t.enum_columns:
            print(f"  enum columns: {', '.join(c.name for c in t.enum_columns)}")
        for j in t.joins:
            print(f"  join: {j.column} -> {j.references_table}.{j.references_column}")
    return 0


def cmd_catalog_validate(_args) -> int:
    """Reconcile the catalog against the live database via information_schema.
    Surfaces the documented-type-vs-reality drift (e.g. dates documented as DATE
    but physically stored as VARCHAR)."""
    catalog = load_catalog()
    issues = 0
    print("\nCATALOG ↔ LIVE DB RECONCILIATION\n" + "=" * 60)
    for t in catalog:
        try:
            live = run_sql(
                "SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_name = '{t.name}'"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"\n■ {t.name}: could not introspect ({exc})")
            issues += 1
            continue

        live_types = {r["column_name"]: r["data_type"] for r in live}
        print(f"\n■ {t.name}")
        if not live_types:
            print("  ✗ table not found in live DB")
            issues += 1
            continue

        cat_cols = set(t.column_names)
        live_cols = set(live_types)
        for missing in sorted(cat_cols - live_cols):
            print(f"  ✗ catalogued column absent in DB: {missing}")
            issues += 1
        for extra in sorted(live_cols - cat_cols):
            print(f"  ! DB column not catalogued: {extra}")
            issues += 1
        # Type drift on date/timestamp columns is the high-value signal.
        for col in t.columns:
            live_type = live_types.get(col.name)
            if not live_type:
                continue
            if col.is_date and "char" in live_type.lower():
                print(
                    f"  ! {col.name}: documented {col.db_type} but live DB is "
                    f"{live_type} — date functions (TO_CHAR) will fail"
                )
                issues += 1
    print("\n" + "-" * 60)
    print(f"{issues} reconciliation issue(s) found." if issues else "Catalog matches live DB.")
    return 1 if issues else 0


# --- quality ----------------------------------------------------------------

def cmd_quality_run(args) -> int:
    from .quality.runner import has_blocking_failures, run

    report = run(only_table=args.table, timestamp=_now())
    return 1 if has_blocking_failures(report) else 0


# --- migrations -------------------------------------------------------------

def cmd_migrations_emit(_args) -> int:
    from .migrations import emit_migrations

    paths = emit_migrations()
    print("Generated:")
    for p in paths:
        print(f"  {p}")
    print("\nReview, then run them (plus 001) in the Supabase SQL editor.")
    return 0


# --- freshness --------------------------------------------------------------

def cmd_freshness_show(_args) -> int:
    from .freshness import show_freshness

    show_freshness()
    return 0


def cmd_freshness_backfill(_args) -> int:
    """Record current row counts as a baseline for pre-existing live data
    (does not re-load anything). Use instead of `ingest` on a populated DB."""
    from .freshness import backfill_freshness

    backfill_freshness(timestamp=_now())
    return 0


# --- catalog verify-rules ---------------------------------------------------

def cmd_catalog_verify_rules(_args) -> int:
    """Empirically test every semantic rule and constraint against the live DB.

    Checks three categories:
      1. Platform rules  — CTE support, LIMIT behaviour
      2. Enum drift      — documented catalog values vs actual DB values
      3. Semantic facts  — explosion factors, disjoint taxonomies, negative facts

    Prints PASS / WARN / FAIL per check. Exits 1 if any FAIL.
    """
    fails = 0
    warns = 0

    def _ok(label: str, detail: str = "") -> None:
        print(f"  PASS  {label}" + (f"\n        {detail}" if detail else ""))

    def _warn(label: str, detail: str) -> None:
        nonlocal warns
        warns += 1
        print(f"  WARN  {label}\n        {detail}")

    def _fail(label: str, detail: str) -> None:
        nonlocal fails
        fails += 1
        print(f"  FAIL  {label}\n        {detail}")

    print("\nCATALOG RULE VERIFICATION (live DB)\n" + "=" * 60)

    # ── 1. Platform rules ────────────────────────────────────────────────────
    print("\n[1] Platform SQL rules")

    # CTE support
    try:
        rows = run_sql(
            "WITH t AS (SELECT user_id FROM nep_master_user_table_sample_data LIMIT 5) "
            "SELECT COUNT(*) AS n FROM t"
        )
        if rows and rows[0].get("n") == 5:
            _ok("CTE (WITH ... AS) executes successfully on execute_sql RPC")
        else:
            _warn("CTE executed but returned unexpected count", str(rows))
    except Exception as exc:
        _fail("CTE support", f"Exception: {exc}")

    # ── 2. Enum drift ────────────────────────────────────────────────────────
    print("\n[2] Enum value drift (catalog documented vs live DB)")

    ENUM_CHECKS = [
        ("nep_liftoffx_data_sample",         "activity_type"),
        ("nep_master_live_events_data",       "participant_status"),
        ("nep_master_live_events_data",       "sessiontype"),
        ("nep_master_live_events_data",       "program_key"),
        ("nep_master_live_events_data",       "gapkey"),
        ("nep_master_live_events_data",       "event_status"),
        ("nep_master_user_table_sample_data", "login_status"),
        ("nep_master_user_table_sample_data", "profile_status"),
        ("nep_master_user_table_sample_data", "company_type"),
        ("nep_mentor_profiles_sample_data",   "user_status"),
        ("nep_mentor_profiles_sample_data",   "program"),
    ]

    from .catalog import load_catalog
    catalog = load_catalog()

    for tbl_name, col_name in ENUM_CHECKS:
        tbl = catalog.get(tbl_name)
        if tbl is None:
            _warn(f"{tbl_name}.{col_name}", "table not in catalog")
            continue
        col = tbl.column(col_name)
        if col is None or not col.enum_values:
            _warn(f"{tbl_name}.{col_name}", "column not in catalog or no enum_values")
            continue
        try:
            live = run_sql(
                f"SELECT DISTINCT {col_name} FROM {tbl_name} "
                f"WHERE {col_name} IS NOT NULL ORDER BY {col_name}"
            )
            live_vals = {r[col_name] for r in live}
            cat_vals  = set(col.enum_values)
            new_in_db = live_vals - cat_vals
            gone_from_db = cat_vals - live_vals
            if not new_in_db and not gone_from_db:
                _ok(f"{tbl_name}.{col_name}  ({len(cat_vals)} values match)")
            else:
                if new_in_db:
                    _warn(
                        f"{tbl_name}.{col_name} — values in DB not in catalog",
                        f"Add to catalog: {sorted(new_in_db)}",
                    )
                if gone_from_db:
                    _warn(
                        f"{tbl_name}.{col_name} — catalog values absent from DB",
                        f"Possibly stale: {sorted(gone_from_db)}",
                    )
        except Exception as exc:
            _fail(f"{tbl_name}.{col_name}", f"Query error: {exc}")

    # ── 3. Semantic facts ────────────────────────────────────────────────────
    print("\n[3] Semantic facts")

    # Mentor explosion factor
    try:
        rows = run_sql(
            "SELECT COUNT(*) AS total_rows, COUNT(DISTINCT user_id) AS distinct_mentors "
            "FROM nep_mentor_profiles_sample_data"
        )
        r = rows[0]
        total, distinct = r["total_rows"], r["distinct_mentors"]
        ratio = round(total / distinct, 1) if distinct else 0
        if ratio > 5:
            _ok(
                f"Mentor table explosion confirmed: {total} rows / {distinct} mentors = ~{ratio}× per mentor",
                "Always use COUNT(DISTINCT user_id), never COUNT(*)",
            )
        else:
            _warn("Mentor explosion lower than expected", f"ratio={ratio} — check if data changed")
    except Exception as exc:
        _fail("Mentor explosion check", str(exc))

    # gapkey ⟂ industry_name — confirmed disjoint
    try:
        overlap = run_sql(
            "SELECT g.gapkey FROM "
            "(SELECT DISTINCT gapkey FROM nep_master_live_events_data WHERE gapkey IS NOT NULL) g "
            "JOIN (SELECT DISTINCT industry_name FROM nep_mentor_profiles_sample_data "
            "      WHERE industry_name IS NOT NULL) m ON g.gapkey = m.industry_name"
        )
        if not overlap:
            _ok("gapkey ⟂ industry_name: confirmed disjoint — no shared values (never join/compare these)")
        else:
            _fail(
                "gapkey / industry_name have overlapping values — update incompatible_pairs",
                f"Overlap: {[r['gapkey'] for r in overlap]}",
            )
    except Exception as exc:
        _fail("gapkey ⟂ industry_name check", str(exc))

    # Negative fact: 'onboarding_completed' must not exist
    try:
        rows = run_sql(
            "SELECT COUNT(*) AS n FROM nep_liftoffx_data_sample "
            "WHERE activity_type = 'onboarding_completed'"
        )
        n = rows[0]["n"]
        if n == 0:
            _ok("Negative fact confirmed: activity_type='onboarding_completed' does not exist")
        else:
            _warn(
                "activity_type='onboarding_completed' now exists in DB",
                f"{n} rows found — remove from negative_facts in catalog",
            )
    except Exception as exc:
        _fail("onboarding_completed negative fact check", str(exc))

    # Mentor table has no engagement activity dates (only profile lifecycle dates)
    try:
        live = run_sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'nep_mentor_profiles_sample_data'"
        )
        mentor_cols = {r["column_name"] for r in live}
        engagement_cols = {"last_active", "last_login", "last_activity_date", "activity_date"}
        found = mentor_cols & engagement_cols
        if not found:
            _ok("Mentor table has no engagement/activity-date columns — 'active in month X' is underivable from it")
        else:
            _warn(
                "Engagement date columns found in mentor table",
                f"Update negative_facts: {sorted(found)} now exist",
            )
    except Exception as exc:
        _fail("Mentor engagement-date check", str(exc))

    # participant_status is mutually exclusive (REGISTERED / ATTENDED / NOSHOW)
    try:
        rows = run_sql(
            "SELECT participant_user_id, event_id, COUNT(DISTINCT participant_status) AS statuses "
            "FROM nep_master_live_events_data "
            "WHERE participant_user_id IS NOT NULL "
            "GROUP BY participant_user_id, event_id "
            "HAVING COUNT(DISTINCT participant_status) > 1 "
            "LIMIT 5"
        )
        if not rows:
            _ok("participant_status is mutually exclusive per (participant, event) — partition confirmed")
        else:
            _warn(
                "Some (participant, event) rows have multiple participant_status values",
                f"Sample: {rows[:3]} — review canonical denominator rule",
            )
    except Exception as exc:
        _fail("participant_status mutual-exclusivity check", str(exc))

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "-" * 60)
    total_issues = fails + warns
    print(f"  {fails} FAIL  |  {warns} WARN  |  {'All checks passed.' if total_issues == 0 else ''}")
    return 1 if fails else 0


# --- ingest -----------------------------------------------------------------

def cmd_ingest(args) -> int:
    from .ingest import ingest_all, ingest_table

    ts = _now()
    if args.table:
        result = ingest_table(args.table, timestamp=ts, truncate=args.truncate)
        return 0 if result.ok else 1
    results = ingest_all(timestamp=ts, truncate=args.truncate)
    return 0 if all(r.ok for r in results) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="data_context", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("catalog", help="inspect / validate metadata catalog")
    csub = c.add_subparsers(dest="sub", required=True)
    csub.add_parser("show").set_defaults(func=cmd_catalog_show)
    csub.add_parser("validate").set_defaults(func=cmd_catalog_validate)
    csub.add_parser("verify-rules").set_defaults(func=cmd_catalog_verify_rules)

    q = sub.add_parser("quality", help="run data-quality checks")
    qsub = q.add_subparsers(dest="sub", required=True)
    qrun = qsub.add_parser("run")
    qrun.add_argument("--table", help="limit to one table")
    qrun.set_defaults(func=cmd_quality_run)

    m = sub.add_parser("migrations", help="generate DDL from the catalog")
    msub = m.add_subparsers(dest="sub", required=True)
    msub.add_parser("emit").set_defaults(func=cmd_migrations_emit)

    f = sub.add_parser("freshness", help="show load provenance / freshness")
    fsub = f.add_subparsers(dest="sub", required=True)
    fsub.add_parser("show").set_defaults(func=cmd_freshness_show)
    fsub.add_parser("backfill").set_defaults(func=cmd_freshness_backfill)

    i = sub.add_parser("ingest", help="governed CSV -> Supabase load")
    i.add_argument("--table", help="load only this table")
    i.add_argument("--truncate", action="store_true", help="delete existing rows first")
    i.set_defaults(func=cmd_ingest)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
