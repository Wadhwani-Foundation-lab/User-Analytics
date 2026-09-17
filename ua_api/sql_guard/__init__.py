"""
sql_guard — deterministic SQL linter for NEP Analytics.

Checks generated SQL for semantic violations that the LLM commonly produces.
Rules are derived from the catalog (authority, partition, incompatible_pairs)
plus hard-coded structural patterns.

Usage:
    from ua_api.sql_guard import lint
    violations = lint(sql_string)  # returns list[Violation]; empty = clean

    # Or for the self-repair message:
    from ua_api.sql_guard import lint_with_message
    msg = lint_with_message(sql_string)  # None = clean, str = repair prompt
"""
from .linter import Violation, lint, lint_with_message

__all__ = ["Violation", "lint", "lint_with_message"]
