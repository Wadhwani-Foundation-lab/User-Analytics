# NEP Analytics Chat API — API Documentation

**Base URL:** `http://localhost:8000` (development)  
**Version:** 1.0.0  
**Auth:** All endpoints require `x-api-key` header  

---

## Authentication

All API requests must include the `x-api-key` header:

```
x-api-key: <API_SECRET_KEY from .env>
```

Requests without a valid key return:
```json
{ "detail": "Invalid API key" }
```
Status: `401 Unauthorized`

---

## Endpoints

### `GET /api/health`

Check if the API and its dependencies are running.

**Request:**
```
GET /api/health
x-api-key: <key>
```

**Response `200 OK`:**
```json
{
  "status": "ok",
  "supabase_connected": true,
  "llm_model": "claude-sonnet-4-5"
}
```

---

### `POST /api/chat`

Send a user question and receive an AI-generated answer (text, table, or chart).

**Request:**
```
POST /api/chat
Content-Type: application/json
x-api-key: <key>
```

**Request Body:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "question": "How many users registered in January 2026?",
  "history": [
    {
      "role": "user",
      "content": "What is our MAU for February 2026?"
    },
    {
      "role": "assistant",
      "content": "There were 1,240 monthly active users in February 2026."
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string (UUID) | Yes | Unique session identifier. Generate with `crypto.randomUUID()` on first load. |
| `question` | string | Yes | Natural language question from the user. |
| `history` | array | No | Previous conversation turns. Pass last 10 turns for context. Defaults to `[]`. |

**Response `200 OK`:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "answer": "342 users registered in January 2026.",
  "response_type": "text",
  "chart_config": null,
  "table_data": null,
  "sql_used": "SELECT COUNT(*) AS registered_users FROM nep_master_user_table_sample_data WHERE created_datetime >= '2026-01-01' AND created_datetime < '2026-02-01';"
}
```

**Response with chart (`response_type: "bar_chart"`):**
```json
{
  "session_id": "a1b2c3d4-...",
  "answer": "Here are the top UTM campaigns by engaged users:",
  "response_type": "bar_chart",
  "chart_config": {
    "type": "bar",
    "title": "Top Campaigns by Engaged Users",
    "labels": ["EEPC Email", "Meta Social", "WhatsApp Leaflet"],
    "datasets": [
      {
        "label": "Engaged Users",
        "data": [87, 54, 32],
        "backgroundColor": "rgba(99, 102, 241, 0.8)",
        "borderColor": "rgba(99, 102, 241, 1)",
        "borderWidth": 2
      }
    ]
  },
  "table_data": null,
  "sql_used": "SELECT traffic_source_campaign, COUNT(DISTINCT user_id) AS engaged_users ..."
}
```

**Response with table (`response_type: "table"`):**
```json
{
  "session_id": "a1b2c3d4-...",
  "answer": "Here is the weekly active user breakdown:",
  "response_type": "table",
  "chart_config": null,
  "table_data": {
    "columns": ["week_range", "weekly_active_users"],
    "rows": [
      ["2 Feb - 8 Feb", 423],
      ["9 Feb - 15 Feb", 518],
      ["16 Feb - 22 Feb", 601]
    ]
  },
  "sql_used": "SELECT week_range, COUNT(DISTINCT userid) AS weekly_active_users ..."
}
```

**Response Field Reference:**

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Echoed from request. Store for subsequent calls. |
| `answer` | string | Natural-language summary of the result. Always present. |
| `response_type` | string | One of: `text`, `table`, `bar_chart`, `line_chart`, `pie_chart` |
| `chart_config` | object \| null | Chart.js-compatible config. Present when `response_type` is a chart type. |
| `chart_config.type` | string | `"bar"`, `"line"`, or `"pie"` |
| `chart_config.labels` | string[] | X-axis labels or pie segment names |
| `chart_config.datasets` | object[] | Chart.js dataset objects with `data`, `backgroundColor`, etc. |
| `chart_config.title` | string | Chart title to display above the chart |
| `table_data` | object \| null | Present when `response_type` is `"table"` |
| `table_data.columns` | string[] | Column header names |
| `table_data.rows` | array[][] | 2D array of row values (parallel to `columns`) |
| `sql_used` | string | The SQL query that was executed (for transparency / debugging) |

**Error Responses:**

| Code | Condition | Body |
|------|-----------|------|
| `401` | Missing or invalid `x-api-key` | `{ "detail": "Invalid API key" }` |
| `403` | LLM attempted a non-SELECT query | `{ "detail": "Only SELECT queries are allowed." }` |
| `422` | Request body validation failed | Standard FastAPI validation error |
| `500` | LLM parsing error or Supabase error | `{ "detail": "Error processing request: <message>" }` |

---

### `GET /api/history/{session_id}`

Retrieve the full conversation history for a session.

**Request:**
```
GET /api/history/a1b2c3d4-e5f6-7890-abcd-ef1234567890
x-api-key: <key>
```

**Response `200 OK`:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "history": [
    {
      "role": "user",
      "content": "How many users registered in January 2026?"
    },
    {
      "role": "assistant",
      "content": "342 users registered in January 2026."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | The session ID |
| `history` | array | All conversation turns in chronological order |
| `history[].role` | string | `"user"` or `"assistant"` |
| `history[].content` | string | Text content of the turn |

---

### `DELETE /api/history/{session_id}`

Clear all conversation history for a session (e.g., when user clicks "New Chat").

**Request:**
```
DELETE /api/history/a1b2c3d4-e5f6-7890-abcd-ef1234567890
x-api-key: <key>
```

**Response `200 OK`:**
```json
{
  "message": "Session cleared",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## Frontend Integration Guide

### Session Management

Generate a session ID once per browser session and reuse it across all requests:

```typescript
// lib/session.ts
export function getOrCreateSessionId(): string {
  let id = sessionStorage.getItem("nep_chat_session");
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem("nep_chat_session", id);
  }
  return id;
}
```

### Sending a Message

```typescript
import { sendMessage } from "@/lib/api";
import { getOrCreateSessionId } from "@/lib/session";

const sessionId = getOrCreateSessionId();
const history = messages.map(m => ({ role: m.role, content: m.content }));

const response = await sendMessage(sessionId, userQuestion, history);

// Use response.response_type to decide which component to render
if (response.response_type === "bar_chart" || ...) {
  // render <ChartBlock config={response.chart_config} />
} else if (response.response_type === "table") {
  // render <TableBlock data={response.table_data} />
} else {
  // render plain text answer
}
```

### Rendering Chart Data

The `chart_config` returned by the API is directly compatible with `react-chartjs-2`:

```tsx
import { Bar, Line, Pie } from "react-chartjs-2";

const componentMap = { bar: Bar, line: Line, pie: Pie };

function ChartBlock({ config }) {
  const Chart = componentMap[config.type];
  return <Chart data={{ labels: config.labels, datasets: config.datasets }} />;
}
```

---

## Rate Limits & Constraints

| Constraint | Value | Notes |
|-----------|-------|-------|
| Max result rows | 500 | Enforced by `supabase_runner.py` |
| Max history turns passed | 10 | Older turns are dropped from the window |
| Max response tokens | 4096 | Set in `llm_client.py` |
| Allowed SQL operations | SELECT only | INSERT/UPDATE/DELETE blocked at API level |
| CORS allowed origins | `localhost:3000` | Configurable via `ALLOWED_ORIGINS` env var |
