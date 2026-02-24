"use client";

import { useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import { ChatMessage } from "@/lib/types";
import TableBlock from "./TableBlock";
import SqlBlock from "./SqlBlock";

const ChartBlock = dynamic(() => import("./ChartBlock"), { ssr: false });

interface ChatThreadProps {
    messages: ChatMessage[];
    loading: boolean;
}

function TypingIndicator() {
    return (
        <div className="bubble-row assistant">
            <div className="avatar assistant-avatar">AI</div>
            <div className="bubble assistant-bubble typing">
                <span />
                <span />
                <span />
            </div>
        </div>
    );
}

function AssistantBubble({ msg }: { msg: ChatMessage }) {
    const isChart = ["bar_chart", "line_chart", "pie_chart"].includes(
        msg.response_type ?? ""
    );
    const isTable = msg.response_type === "table";

    return (
        <div className="bubble-row assistant">
            <div className="avatar assistant-avatar">AI</div>
            <div className="bubble-group">
                <div className="bubble assistant-bubble">
                    <p className="bubble-text">{msg.content}</p>
                </div>
                {isChart && msg.chart_config && (
                    <div className="chart-wrapper">
                        <ChartBlock config={msg.chart_config} />
                    </div>
                )}
                {isTable && msg.table_data && (
                    <TableBlock data={msg.table_data} />
                )}
                {msg.sql_used && <SqlBlock sql={msg.sql_used} />}
                <p className="msg-time">
                    {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
            </div>
        </div>
    );
}

export default function ChatThread({ messages, loading }: ChatThreadProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

    if (messages.length === 0 && !loading) {
        return (
            <div className="empty-state">
                <div className="empty-icon">📊</div>
                <h2 className="empty-title">NEP Analytics Assistant</h2>
                <p className="empty-sub">
                    Ask any question about user registrations, engagement, events, mentors,
                    or UTM campaigns. I&apos;ll query the data and respond with insights.
                </p>
            </div>
        );
    }

    return (
        <div className="chat-thread">
            {messages.map((msg) =>
                msg.role === "user" ? (
                    <div key={msg.id} className="bubble-row user">
                        <div className="bubble user-bubble">
                            <p className="bubble-text">{msg.content}</p>
                        </div>
                        <div className="avatar user-avatar">You</div>
                    </div>
                ) : (
                    <AssistantBubble key={msg.id} msg={msg} />
                )
            )}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
        </div>
    );
}
