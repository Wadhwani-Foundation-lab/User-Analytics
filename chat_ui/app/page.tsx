"use client";

import { useState, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import ChatThread from "@/components/ChatThread";
import ChatInput from "@/components/ChatInput";
import { sendMessage, clearHistory } from "@/lib/api";
import { getOrCreateSessionId, resetSessionId } from "@/lib/session";
import { ChatMessage, HistoryTurn } from "@/lib/types";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = useCallback(async (question: string) => {
    setError(null);
    const sessionId = getOrCreateSessionId();

    // Add user message immediately
    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      // Build history from current messages (last 10 turns)
      const history: HistoryTurn[] = messages
        .slice(-20)
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await sendMessage(sessionId, question, history);

      const assistantMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: response.answer,
        response_type: response.response_type,
        chart_config: response.chart_config,
        table_data: response.table_data,
        sql_used: response.sql_used,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          role: "assistant",
          content: `⚠️ ${msg}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [messages]);

  const handleNewChat = async () => {
    const oldId = getOrCreateSessionId();
    await clearHistory(oldId).catch(() => { });
    resetSessionId();
    setMessages([]);
    setError(null);
  };

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">◈</span>
          <span className="logo-text">NEP Analytics</span>
        </div>
        <button className="new-chat-btn" onClick={handleNewChat}>
          + New Chat
        </button>
        <div className="sidebar-section">
          <p className="sidebar-label">Data Sources</p>
          <ul className="sidebar-list">
            <li>👥 Users</li>
            <li>📅 Live Events</li>
            <li>📊 Activity</li>
            <li>🎓 Mentors</li>
          </ul>
        </div>
        <div className="sidebar-section">
          <p className="sidebar-label">Model</p>
          <p className="sidebar-value">Claude claude-sonnet-4-5</p>
        </div>
        <div className="sidebar-footer">
          <p>Internal use only</p>
          <p>Wadhwani Foundation</p>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-panel">
        <header className="chat-header">
          <div>
            <h1 className="chat-title">User Analytics Assistant</h1>
            <p className="chat-subtitle">Ask anything about NEP platform data</p>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
        </header>

        <div className="thread-container">
          <ChatThread messages={messages} loading={loading} />
        </div>

        <ChatInput onSend={handleSend} loading={loading} />
      </main>
    </div>
  );
}
