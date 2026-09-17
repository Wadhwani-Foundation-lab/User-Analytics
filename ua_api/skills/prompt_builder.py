"""
Prompt builder — assembles a system prompt from skill blocks + schema docs.

build_prompt() is a drop-in replacement for chat_api's SYSTEM_PROMPT string.
The calling convention is identical: mount the result as the system= arg to
the LLM. The adapter or a future chat_api replacement can call this instead of
loading the monolithic system_prompt.py.

Preset profiles:
  "full"    — all blocks (equivalent to the current monolith)
  "minimal" — identity + output format + enum values (fast/cheap questions)
  "sql"     — adds SQL rules + column map + performance on top of minimal
  "events"  — full with emphasis on events/mentor blocks
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .blocks import (
    CLARIFICATION,
    COLUMN_MAP,
    DATE_HANDLING,
    ENUM_VALUES,
    IDENTITY,
    OUTPUT_FORMAT,
    PERFORMANCE,
    RESPONSE_TYPES,
    SEMANTIC_CONTEXT,
    SQL_RULES,
)

_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"

# Ordered block list for the "full" profile — same information as the monolith,
# now separated so blocks can be included/excluded independently.
# semantic_context sits after sql_rules so the LLM gets structural rules first,
# then the higher-level domain constraints that override mechanical defaults.
_FULL_ORDER: List[str] = [
    "identity",
    "output_format",
    "response_types",
    "enum_values",
    "date_handling",
    "sql_rules",
    "semantic_context",
    "column_map",
    "performance",
    "clarification",
]

_BLOCK_MAP = {
    "identity": IDENTITY,
    "output_format": OUTPUT_FORMAT,
    "response_types": RESPONSE_TYPES,
    "enum_values": ENUM_VALUES,
    "date_handling": DATE_HANDLING,
    "sql_rules": SQL_RULES,
    "semantic_context": SEMANTIC_CONTEXT,
    "column_map": COLUMN_MAP,
    "performance": PERFORMANCE,
    "clarification": CLARIFICATION,
}

_PROFILES: dict = {
    "full":    _FULL_ORDER,
    "minimal": ["identity", "output_format", "enum_values", "clarification"],
    "sql":     ["identity", "output_format", "response_types", "enum_values",
                "date_handling", "sql_rules", "semantic_context", "column_map", "clarification"],
    "events":  ["identity", "output_format", "response_types", "enum_values",
                "date_handling", "sql_rules", "semantic_context", "column_map", "performance", "clarification"],
}


def _load_docs() -> str:
    """Load schema_reference.md + questions_to_sql.md, same as chat_api."""
    schema = (_DOCS_DIR / "schema_reference.md").read_text(encoding="utf-8")
    examples = (_DOCS_DIR / "questions_to_sql.md").read_text(encoding="utf-8")
    return (
        "\n\n## SCHEMA REFERENCE\n\n"
        + schema
        + "\n\n## SQL EXAMPLES (few-shot reference)\n\n"
        + examples
    )


def build_prompt(
    profile: str = "full",
    blocks: Optional[List[str]] = None,
    include_docs: bool = True,
    today: Optional[str] = None,
) -> str:
    """
    Assemble a system prompt.

    Args:
        profile:      "full" | "minimal" | "sql" | "events"
        blocks:       Override profile with an explicit list of block names.
        include_docs: Append schema_reference.md + questions_to_sql.md.
        today:        ISO date string injected into date rules block
                      (replaces the hardcoded date in the monolith).
    """
    chosen = blocks if blocks is not None else _PROFILES.get(profile, _FULL_ORDER)
    parts = [_BLOCK_MAP[b] for b in chosen if b in _BLOCK_MAP]
    prompt = "\n\n".join(parts)

    if today:
        prompt = prompt.replace(
            "Use the current date from context when user says",
            f"Today's date is {today}. Use this when user says",
        )

    if include_docs:
        prompt += _load_docs()

    return prompt


# Convenience singleton — same usage pattern as chat_api's SYSTEM_PROMPT.
# Import this to replace the monolith:
#   from ua_api.skills.prompt_builder import SYSTEM_PROMPT
SYSTEM_PROMPT: str = build_prompt(profile="full", include_docs=True)
