"use client";

import { useState, useRef, KeyboardEvent } from "react";

const SUGGESTED_QUESTIONS = [
    "How many users registered last month?",
    "What is our weekly active user trend?",
    "Which UTM campaigns have the highest conversion?",
    "How many users asked at least one AI question?",
    "Show event attendance by program",
    "Who are our power users (10+ questions)?",
    "What is week-on-week retention?",
    "Which partners send the most engaged users?",
];

interface ChatInputProps {
    onSend: (question: string) => void;
    loading: boolean;
}

export default function ChatInput({ onSend, loading }: ChatInputProps) {
    const [text, setText] = useState("");
    const [showSuggestions, setShowSuggestions] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const submit = () => {
        const q = text.trim();
        if (!q || loading) return;
        onSend(q);
        setText("");
        if (textareaRef.current) textareaRef.current.style.height = "auto";
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
        }
    };

    const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setText(e.target.value);
        // auto-grow
        const el = e.target;
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 160) + "px";
    };

    const pickSuggestion = (q: string) => {
        onSend(q);
        setShowSuggestions(false);
    };

    return (
        <div className="chat-input-area">
            {showSuggestions && (
                <div className="suggestions-panel">
                    <p className="suggestions-label">Suggested questions</p>
                    <div className="suggestions-grid">
                        {SUGGESTED_QUESTIONS.map((q) => (
                            <button key={q} className="suggestion-chip" onClick={() => pickSuggestion(q)}>
                                {q}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            <div className="input-row">
                <button
                    className="suggest-toggle"
                    onClick={() => setShowSuggestions((s) => !s)}
                    title="Show suggested questions"
                    aria-label="Suggested questions"
                >
                    ✦
                </button>

                <textarea
                    ref={textareaRef}
                    rows={1}
                    className="chat-textarea"
                    placeholder="Ask a question about user analytics… (Enter to send, Shift+Enter for new line)"
                    value={text}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    disabled={loading}
                />

                <button
                    className={`send-btn ${loading ? "loading" : ""}`}
                    onClick={submit}
                    disabled={loading || !text.trim()}
                    aria-label="Send"
                >
                    {loading ? (
                        <span className="send-spinner" />
                    ) : (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    )}
                </button>
            </div>

            <p className="input-hint">
                Powered by Claude claude-sonnet-4-5 · Data from Supabase · All interactions via API
            </p>
        </div>
    );
}
