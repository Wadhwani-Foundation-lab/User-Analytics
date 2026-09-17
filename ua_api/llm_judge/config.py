"""Config for llm_judge — loads chat_api/.env and sets the judge model."""
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV = REPO_ROOT / "chat_api" / ".env"
load_dotenv(_ENV, override=False)
load_dotenv(override=False)

JUDGE_MODEL = "claude-opus-5"
DOCS_DIR = REPO_ROOT / "docs"
SCHEMA_REF = DOCS_DIR / "schema_reference.md"
