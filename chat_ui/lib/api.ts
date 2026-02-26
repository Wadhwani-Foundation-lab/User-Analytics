import { ChatResponse, HistoryTurn, Session, ChatMessage } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

const defaultHeaders = {
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
        headers: defaultHeaders,
        body: JSON.stringify({ session_id: sessionId, question, history }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `API error ${res.status}`);
    }
    return res.json() as Promise<ChatResponse>;
}

export async function getHistory(sessionId: string): Promise<HistoryTurn[]> {
    const res = await fetch(`${BASE_URL}/api/history/${sessionId}`, {
        headers: defaultHeaders,
    });
    if (!res.ok) throw new Error(`Failed to fetch history: ${res.status}`);
    const data = (await res.json()) as { history: HistoryTurn[] };
    return data.history;
}

export async function clearHistory(sessionId: string): Promise<void> {
    await fetch(`${BASE_URL}/api/history/${sessionId}`, {
        method: "DELETE",
        headers: defaultHeaders,
    });
}

export async function checkHealth(): Promise<{ status: string; llm_model: string }> {
    const res = await fetch(`${BASE_URL}/api/health`, { headers: defaultHeaders });
    return res.json() as Promise<{ status: string; llm_model: string }>;
}

// ── Session persistence ──────────────────────────────────────────────────────

export async function createSession(sessionId: string, title: string): Promise<void> {
    await fetch(`${BASE_URL}/api/sessions`, {
        method: "POST",
        headers: defaultHeaders,
        body: JSON.stringify({ session_id: sessionId, title }),
    });
}

export async function listSessions(): Promise<Session[]> {
    const res = await fetch(`${BASE_URL}/api/sessions`, { headers: defaultHeaders });
    if (!res.ok) return [];
    return res.json() as Promise<Session[]>;
}

export async function getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
    const res = await fetch(`${BASE_URL}/api/sessions/${sessionId}/messages`, {
        headers: defaultHeaders,
    });
    if (!res.ok) return [];
    const rows = (await res.json()) as Array<{
        id: string; role: "user" | "assistant"; content: string;
        response_type?: string; chart_config?: unknown; table_data?: unknown;
        sql_used?: string; created_at: string;
    }>;
    return rows.map((r) => ({
        id: r.id,
        role: r.role,
        content: r.content,
        response_type: r.response_type as ChatMessage["response_type"],
        chart_config: r.chart_config as ChatMessage["chart_config"],
        table_data: r.table_data as ChatMessage["table_data"],
        sql_used: r.sql_used,
        timestamp: new Date(r.created_at),
    }));
}
