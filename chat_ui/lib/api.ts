import { ChatResponse, HistoryTurn } from "./types";

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
