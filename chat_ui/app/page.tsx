"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import ChatThread from "@/components/ChatThread";
import ChatInput from "@/components/ChatInput";
import {
  sendMessage,
  clearHistory,
  createSession,
  listSessions,
  getSessionMessages,
} from "@/lib/api";
import { getOrCreateSessionId, resetSessionId } from "@/lib/session";
import { ChatMessage, HistoryTurn, Session } from "@/lib/types";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  // Track whether we've already registered this session in the DB
  const sessionRegistered = useRef<Set<string>>(new Set());

  // Load sidebar sessions on mount
  useEffect(() => {
    listSessions().then(setSessions).catch(() => { });
    const id = getOrCreateSessionId();
    setActiveSessionId(id);
  }, []);

  const handleSend = useCallback(async (question: string) => {
    setError(null);
    const sessionId = activeSessionId || getOrCreateSessionId();

    // Register session in DB on first message
    if (!sessionRegistered.current.has(sessionId)) {
      sessionRegistered.current.add(sessionId);
      const title = question.length > 60 ? question.slice(0, 57) + "…" : question;
      await createSession(sessionId, title).catch(() => { });
      // Refresh sidebar
      listSessions().then(setSessions).catch(() => { });
    }

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
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
      // Refresh sidebar to update updated_at ordering
      listSessions().then(setSessions).catch(() => { });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), role: "assistant", content: `⚠️ ${msg}`, timestamp: new Date() },
      ]);
    } finally {
      setLoading(false);
    }
  }, [messages, activeSessionId]);

  const handleNewChat = async () => {
    const oldId = activeSessionId || getOrCreateSessionId();
    await clearHistory(oldId).catch(() => { });
    const newId = resetSessionId();
    setActiveSessionId(newId);
    setMessages([]);
    setError(null);
  };

  const handleSelectSession = async (session: Session) => {
    if (session.id === activeSessionId) return;
    setActiveSessionId(session.id);
    setMessages([]);
    setLoading(true);
    setError(null);
    try {
      const msgs = await getSessionMessages(session.id);
      setMessages(msgs);
      // Mark as already registered so next message doesn't re-create
      sessionRegistered.current.add(session.id);
    } catch {
      setError("Failed to load session.");
    } finally {
      setLoading(false);
    }
  };

  const relativeTime = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
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

        {/* ── Recent Chats ── */}
        {sessions.length > 0 && (
          <div className="sidebar-section">
            <p className="sidebar-label">Recent Chats</p>
            <ul className="sidebar-sessions">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className={`session-item ${s.id === activeSessionId ? "active" : ""}`}
                  onClick={() => handleSelectSession(s)}
                  title={s.title}
                >
                  <span className="session-icon">🗨</span>
                  <span className="session-info">
                    <span className="session-title">{s.title}</span>
                    <span className="session-time">{relativeTime(s.updated_at)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

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
