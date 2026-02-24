# NEP Analytics Chat Interface — Technical Specification

**Version:** 1.0  
**Date:** 2026-02-19  

---

## 1. Backend Specification (`chat_api/`)

### 1.1 Environment Variables (`.env`)

```env
# Supabase
SUPABASE_URL=https://mybdvsxiynpdbuzmtquu.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>

# Anthropic
ANTHROPIC_API_KEY=<your_api_key>

# App
API_SECRET_KEY=<random_32_char_string>   # Required on all /api/* requests
ALLOWED_ORIGINS=http://localhost:3000    # Comma-separated for production
MAX_HISTORY_TURNS=10
MAX_RESULT_ROWS=500
```

---

### 1.2 `models.py` — Pydantic Schemas

```python
from pydantic import BaseModel
from typing import Literal, Optional, List, Any, Dict

class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    session_id: str                      # UUID, generated client-side
    question: str                        # Natural language question
    history: List[HistoryTurn] = []      # Previous turns (up to 10)

class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie"]
    labels: List[str]
    datasets: List[Dict[str, Any]]
    title: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str                          # Natural language answer
    response_type: Literal["text", "table", "bar_chart", "line_chart", "pie_chart"]
    chart_config: Optional[ChartConfig] = None
    table_data: Optional[Dict[str, Any]] = None   # { columns: [], rows: [[]] }
    sql_used: Optional[str] = None       # SQL executed (for transparency)
    session_id: str

class HistoryResponse(BaseModel):
    session_id: str
    history: List[HistoryTurn]

class HealthResponse(BaseModel):
    status: str
    supabase_connected: bool
    llm_model: str
```

---

### 1.3 `system_prompt.py`

Loads and builds the LLM system prompt at startup (cached, not rebuilt per request):

```python
import os
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"

def build_system_prompt() -> str:
    schema = (DOCS_DIR / "schema_reference.md").read_text()
    examples = (DOCS_DIR / "questions_to_sql.md").read_text()

    return f"""
You are NEP Analytics Assistant — an AI assistant for internal Wadhwani Foundation leadership.
You help users query and understand user analytics data using 4 Supabase PostgreSQL tables.

## RULES (strict)
1. Always generate exactly ONE SQL SELECT query to answer the question. Never INSERT, UPDATE, DELETE, DROP or ALTER.
2. Output ONLY a JSON block using this exact format, followed optionally by a brief explanation:
   {{
     "sql": "SELECT ...",
     "response_type": "text | table | bar_chart | line_chart | pie_chart",
     "nl_answer_template": "One sentence describing what the result shows",
     "chart_label_column": "column_name_for_x_axis_or_pie_labels",   // omit if not chart
     "chart_value_column": "column_name_for_y_axis_or_pie_values"    // omit if not chart
   }}
3. Choose response_type as follows:
   - bar_chart: comparing categories (campaigns, channels, user types)
   - line_chart: trends over time (weekly/monthly series)
   - pie_chart: proportions of a whole (% breakdown)
   - table: multi-column results not suited to a chart
   - text: single number or a short answer
4. Only use columns and tables listed in the SCHEMA REFERENCE below.
5. If the question refers to a previous answer, use the conversation history to add context.
6. If the question is ambiguous, ask ONE clarifying question instead of generating SQL.
7. Never reveal raw database credentials or internal system details.
8. Always apply a LIMIT of 500 rows maximum unless the query uses aggregate functions.
9. Use double-quoted identifiers for column names with spaces or special characters.
10. For date filtering, use >= and < on VARCHAR date columns (format: 'YYYY-MM-DD').

## SCHEMA REFERENCE
{schema}

## SQL EXAMPLES (few-shot)
{examples}
"""

# Singleton — built once at module import
SYSTEM_PROMPT = build_system_prompt()
```

---

### 1.4 `llm_client.py`

```python
import anthropic
import json
import re
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096

def ask(system_prompt: str, history: list[dict], question: str) -> dict:
    """
    Call Claude claude-sonnet-4-5 and return parsed JSON response.
    Returns: { sql, response_type, nl_answer_template, chart_label_column?, chart_value_column? }
    """
    messages = history + [{"role": "user", "content": question}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    raw = response.content[0].text

    # Extract JSON block from response
    json_match = re.search(r'\{[\s\S]*?\}', raw)
    if not json_match:
        raise ValueError(f"LLM did not return a valid JSON block. Raw: {raw[:200]}")

    parsed = json.loads(json_match.group())
    parsed["_raw_response"] = raw   # preserve full text for nl_answer extraction
    return parsed
```

---

### 1.5 `supabase_runner.py`

```python
import os
import re
from supabase import create_client, Client

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

ALLOWED_TABLES = {
    "nep_master_user_table_sample_data",
    "nep_master_live_events_data",
    "nep_liftoffx_data_sample",
    "nep_mentor_profiles_sample_data",
}

BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b',
    re.IGNORECASE
)

MAX_ROWS = int(os.getenv("MAX_RESULT_ROWS", 500))

def execute(sql: str) -> list[dict]:
    """Execute a read-only SQL query via Supabase and return rows as list of dicts."""

    # Safety: block any non-SELECT statements
    if BLOCKED_KEYWORDS.search(sql):
        raise PermissionError("Only SELECT queries are allowed.")

    if not sql.strip().upper().startswith("SELECT"):
        raise PermissionError("Query must start with SELECT.")

    # Append LIMIT if not already present
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + f" LIMIT {MAX_ROWS};"

    # Execute via Supabase rpc (raw SQL)
    response = supabase.rpc("execute_sql", {"query": sql}).execute()

    # Fallback: use PostgREST if rpc not available
    # (handled in main.py with direct psycopg2 if needed)
    return response.data if response.data else []
```

> **Note:** The Supabase `execute_sql` RPC function must be created in the Supabase SQL Editor:
> ```sql
> CREATE OR REPLACE FUNCTION execute_sql(query text)
> RETURNS json
> LANGUAGE plpgsql
> SECURITY DEFINER
> AS $$
> DECLARE
>   result json;
> BEGIN
>   EXECUTE 'SELECT json_agg(t) FROM (' || query || ') t' INTO result;
>   RETURN COALESCE(result, '[]'::json);
> END;
> $$;
> ```

---

### 1.6 `session_store.py`

```python
from collections import defaultdict
import os

MAX_TURNS = int(os.getenv("MAX_HISTORY_TURNS", 10))

# { session_id: [{ role, content }, ...] }
_store: dict[str, list[dict]] = defaultdict(list)

def get_history(session_id: str) -> list[dict]:
    return _store[session_id][-MAX_TURNS * 2:]   # each turn = 2 items (user + assistant)

def append_turn(session_id: str, role: str, content: str):
    _store[session_id].append({"role": role, "content": content})

def clear_session(session_id: str):
    _store[session_id] = []
```

---

### 1.7 `chart_formatter.py`

```python
from models import ChartConfig

CHART_TYPE_MAP = {
    "bar_chart": "bar",
    "line_chart": "line",
    "pie_chart": "pie",
}

CHART_COLORS = [
    "rgba(99, 102, 241, 0.8)",   # indigo
    "rgba(16, 185, 129, 0.8)",   # emerald
    "rgba(245, 158, 11, 0.8)",   # amber
    "rgba(239, 68, 68, 0.8)",    # red
    "rgba(59, 130, 246, 0.8)",   # blue
    "rgba(168, 85, 247, 0.8)",   # purple
]

def format_chart(
    rows: list[dict],
    response_type: str,
    label_col: str,
    value_col: str,
    title: str = "",
) -> ChartConfig:
    chart_type = CHART_TYPE_MAP.get(response_type, "bar")
    labels = [str(row.get(label_col, "")) for row in rows]
    values = [row.get(value_col, 0) for row in rows]

    colors = (CHART_COLORS * ((len(labels) // len(CHART_COLORS)) + 1))[: len(labels)]

    dataset = {
        "label": value_col.replace("_", " ").title(),
        "data": values,
        "backgroundColor": colors if chart_type == "pie" else colors[0],
        "borderColor": colors[0],
        "borderWidth": 2,
        "tension": 0.4,   # for line charts
    }

    return ChartConfig(
        type=chart_type,
        labels=labels,
        datasets=[dataset],
        title=title,
    )
```

---

### 1.8 `main.py` — FastAPI App

```python
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

from models import ChatRequest, ChatResponse, HistoryResponse, HealthResponse
from system_prompt import SYSTEM_PROMPT
from llm_client import ask
from supabase_runner import execute
from session_store import get_history, append_turn, clear_session
from chart_formatter import format_chart

app = FastAPI(title="NEP Analytics Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

API_KEY = os.getenv("API_SECRET_KEY", "")

def verify_api_key(x_api_key: str = Header(...)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", supabase_connected=True, llm_model="claude-sonnet-4-5")

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_api_key: str = Header(...)):
    verify_api_key(x_api_key)

    # Merge server history with client-provided history
    server_history = get_history(req.session_id)
    history = server_history or [h.dict() for h in req.history]

    try:
        # 1. Ask LLM to generate SQL
        llm_result = ask(SYSTEM_PROMPT, history, req.question)
        sql = llm_result.get("sql", "")
        response_type = llm_result.get("response_type", "text")
        nl_template = llm_result.get("nl_answer_template", "")
        label_col = llm_result.get("chart_label_column", "")
        value_col = llm_result.get("chart_value_column", "")

        # 2. Execute SQL
        rows = execute(sql) if sql else []

        # 3. Format response
        chart_config = None
        table_data = None
        answer = nl_template

        if response_type in ("bar_chart", "line_chart", "pie_chart") and rows and label_col and value_col:
            chart_config = format_chart(rows, response_type, label_col, value_col, nl_template)
            answer = nl_template

        elif response_type == "table" and rows:
            columns = list(rows[0].keys()) if rows else []
            table_data = {"columns": columns, "rows": [[row[c] for c in columns] for row in rows]}

        elif response_type == "text":
            # Summarise single-value result
            if rows and len(rows) == 1:
                answer = f"{nl_template} {list(rows[0].values())[0]}"
            elif rows:
                answer = f"{nl_template} (returned {len(rows)} rows)"

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

    # 4. Update session history
    append_turn(req.session_id, "user", req.question)
    append_turn(req.session_id, "assistant", answer)

    return ChatResponse(
        answer=answer,
        response_type=response_type,
        chart_config=chart_config,
        table_data=table_data,
        sql_used=sql,
        session_id=req.session_id,
    )

@app.get("/api/history/{session_id}", response_model=HistoryResponse)
def get_session_history(session_id: str, x_api_key: str = Header(...)):
    verify_api_key(x_api_key)
    history = get_history(session_id)
    return HistoryResponse(session_id=session_id, history=history)

@app.delete("/api/history/{session_id}")
def clear_session_history(session_id: str, x_api_key: str = Header(...)):
    verify_api_key(x_api_key)
    clear_session(session_id)
    return {"message": "Session cleared", "session_id": session_id}
```

---

## 2. Frontend Specification (`chat_ui/`)

### 2.1 `lib/types.ts`

```typescript
export type ResponseType = "text" | "table" | "bar_chart" | "line_chart" | "pie_chart";

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChartConfig {
  type: "bar" | "line" | "pie";
  labels: string[];
  datasets: object[];
  title?: string;
}

export interface TableData {
  columns: string[];
  rows: (string | number | null)[][];
}

export interface ChatResponse {
  answer: string;
  response_type: ResponseType;
  chart_config?: ChartConfig;
  table_data?: TableData;
  sql_used?: string;
  session_id: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  response_type?: ResponseType;
  chart_config?: ChartConfig;
  table_data?: TableData;
  sql_used?: string;
  timestamp: Date;
}
```

---

### 2.2 `lib/api.ts`

```typescript
import { ChatResponse, HistoryTurn } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

const headers = {
  "Content-Type": "application/json",
  "x-api-key": API_KEY,
};

export async function sendMessage(
  sessionId: string,
  question: string,
  history: HistoryTurn[]
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ session_id: sessionId, question, history }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

export async function getHistory(sessionId: string): Promise<HistoryTurn[]> {
  const res = await fetch(`${BASE_URL}/api/history/${sessionId}`, { headers });
  if (!res.ok) throw new Error(`Failed to fetch history: ${res.status}`);
  const data = await res.json();
  return data.history;
}

export async function clearHistory(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/history/${sessionId}`, { method: "DELETE", headers });
}

export async function checkHealth(): Promise<{ status: string; llm_model: string }> {
  const res = await fetch(`${BASE_URL}/api/health`, { headers });
  return res.json();
}
```

---

### 2.3 Environment Variables (Frontend)

```env
# chat_ui/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=<same_value_as_API_SECRET_KEY>
```

---

## 3. Running Locally

### Backend
```bash
cd chat_api
pip install -r requirements.txt
cp ../.env .env          # or set env vars directly
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd chat_ui
npm install
cp .env.local.example .env.local   # fill in values
npm run dev                         # runs on http://localhost:3000
```

---

## 4. Performance Considerations

| Concern | Handling |
|---------|---------|
| LLM latency (~2–5s) | Frontend shows animated "Thinking…" skeleton |
| Large result sets | Hard cap of 500 rows in `supabase_runner.py` |
| Session store memory | In-memory dict; cleared on server restart (acceptable for internal tool) |
| System prompt size | ~15KB; well within Claude's 200K token context window |
| Chart render perf | Chart.js renders client-side; server only sends config JSON |

---

## 5. Error Handling

| Error | HTTP Code | User Message |
|-------|-----------|-------------|
| LLM returns no JSON | 500 | "Sorry, I couldn't generate a query for that question. Please try rephrasing." |
| SQL blocked (non-SELECT) | 403 | "That question requires a write operation, which is not permitted." |
| Supabase query error | 500 | "The query failed to execute. Please try a simpler question." |
| Invalid API key | 401 | Redirect to error page |
| LLM API unavailable | 502 | "The AI service is temporarily unavailable. Please try again." |
