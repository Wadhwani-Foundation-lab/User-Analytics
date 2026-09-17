"""
CLI for manual linter testing.

  echo "SELECT COUNT(*) FROM nep_mentor_profiles_sample_data" | python -m ua_api.sql_guard
  python -m ua_api.sql_guard "SELECT COUNT(*) FROM nep_mentor_profiles_sample_data"
"""
import sys
from .linter import lint

def main():
    sql = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    violations = lint(sql)
    if not violations:
        print("CLEAN — no violations found.")
        sys.exit(0)
    print(f"{len(violations)} violation(s) found:\n")
    for v in violations:
        print(f"  [{v.rule}]")
        print(f"  {v.message}")
        print(f"  Fix: {v.fix_hint}")
        print()
    sys.exit(1)

if __name__ == "__main__":
    main()
