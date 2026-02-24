"use client";

import { useState } from "react";

interface SqlBlockProps {
    sql: string;
}

export default function SqlBlock({ sql }: SqlBlockProps) {
    const [open, setOpen] = useState(false);
    const [copied, setCopied] = useState(false);

    const copy = () => {
        navigator.clipboard.writeText(sql);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="sql-block">
            <button
                onClick={() => setOpen((o) => !o)}
                className="sql-toggle"
                aria-expanded={open}
            >
                <span className="sql-icon">◈</span>
                {open ? "Hide SQL" : "Show SQL"}
                <span className={`sql-chevron ${open ? "open" : ""}`}>›</span>
            </button>
            {open && (
                <div className="sql-content">
                    <pre className="sql-code">{sql}</pre>
                    <button onClick={copy} className="copy-btn">
                        {copied ? "✓ Copied" : "Copy"}
                    </button>
                </div>
            )}
        </div>
    );
}
