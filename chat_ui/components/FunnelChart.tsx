"use client";

import { useRef } from "react";
import { ChartConfig } from "@/lib/types";

interface FunnelChartProps {
    config: ChartConfig;
}

const COLORS = [
    "#6366f1", // indigo
    "#8b5cf6", // violet
    "#3b82f6", // blue
    "#06b6d4", // cyan
    "#10b981", // emerald
    "#f59e0b", // amber
    "#ef4444", // red
];

export default function FunnelChart({ config }: FunnelChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);

    const labels = config.labels;
    const values = (config.datasets[0]?.data as number[]) ?? [];
    const maxVal = Math.max(...values, 1);

    const BAR_HEIGHT = 52;
    const GAP = 6;
    const LABEL_W = 220;
    const BAR_MAX_W = 340;
    const VALUE_W = 100;
    const SVG_W = LABEL_W + BAR_MAX_W + VALUE_W + 24;
    const SVG_H = labels.length * (BAR_HEIGHT + GAP) + 20;

    const downloadSVG = () => {
        const svg = containerRef.current?.querySelector("svg");
        if (!svg) return;
        const blob = new Blob([svg.outerHTML], { type: "image/svg+xml" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `funnel-${Date.now()}.svg`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div style={{ fontFamily: "'Inter', sans-serif" }}>
            {config.title && (
                <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 12, fontWeight: 500 }}>
                    {config.title}
                </p>
            )}
            <div ref={containerRef}>
                <svg
                    width="100%"
                    viewBox={`0 0 ${SVG_W} ${SVG_H}`}
                    style={{ overflow: "visible", maxWidth: SVG_W }}
                >
                    {labels.map((label, i) => {
                        const val = values[i] ?? 0;
                        const prevVal = i > 0 ? (values[i - 1] ?? 0) : val;
                        const barW = maxVal > 0 ? (val / maxVal) * BAR_MAX_W : 0;
                        const offsetX = LABEL_W + (BAR_MAX_W - barW) / 2;
                        const y = i * (BAR_HEIGHT + GAP) + 10;
                        const color = COLORS[i % COLORS.length];
                        const pct = prevVal > 0 ? Math.round((val / prevVal) * 100) : 100;
                        const dropLabel = i > 0 ? `${pct}% of prev` : "100%";

                        return (
                            <g key={label}>
                                {/* Stage label */}
                                <text
                                    x={LABEL_W - 10}
                                    y={y + BAR_HEIGHT / 2 + 5}
                                    textAnchor="end"
                                    fill="#cbd5e1"
                                    fontSize={12}
                                    fontWeight={500}
                                >
                                    {label.length > 26 ? label.slice(0, 24) + "…" : label}
                                </text>

                                {/* Bar */}
                                <rect
                                    x={offsetX}
                                    y={y}
                                    width={barW}
                                    height={BAR_HEIGHT}
                                    rx={4}
                                    fill={color}
                                    opacity={0.88}
                                />

                                {/* Value inside bar */}
                                {barW > 50 && (
                                    <text
                                        x={offsetX + barW / 2}
                                        y={y + BAR_HEIGHT / 2 + 5}
                                        textAnchor="middle"
                                        fill="#fff"
                                        fontSize={13}
                                        fontWeight={600}
                                    >
                                        {val.toLocaleString()}
                                    </text>
                                )}

                                {/* Value outside bar (if bar too narrow) */}
                                {barW <= 50 && (
                                    <text
                                        x={LABEL_W + BAR_MAX_W + 8}
                                        y={y + BAR_HEIGHT / 2 + 5}
                                        fill="#cbd5e1"
                                        fontSize={12}
                                    >
                                        {val.toLocaleString()}
                                    </text>
                                )}

                                {/* Conversion rate badge */}
                                <text
                                    x={LABEL_W + BAR_MAX_W + 8}
                                    y={y + BAR_HEIGHT / 2 + (barW > 50 ? 5 : 20)}
                                    fill={i > 0 && pct < 50 ? "#f87171" : "#94a3b8"}
                                    fontSize={11}
                                >
                                    {dropLabel}
                                </text>

                                {/* Connector line to next bar */}
                                {i < labels.length - 1 && barW > 0 && (
                                    <line
                                        x1={offsetX + barW / 2}
                                        y1={y + BAR_HEIGHT}
                                        x2={
                                            LABEL_W +
                                            (BAR_MAX_W -
                                                ((values[i + 1] ?? 0) / maxVal) * BAR_MAX_W) /
                                                2 +
                                            ((values[i + 1] ?? 0) / maxVal) * BAR_MAX_W / 2
                                        }
                                        y2={y + BAR_HEIGHT + GAP}
                                        stroke="#334155"
                                        strokeWidth={1}
                                        strokeDasharray="3 2"
                                    />
                                )}
                            </g>
                        );
                    })}
                </svg>
            </div>
            <button
                onClick={downloadSVG}
                style={{
                    marginTop: 10,
                    padding: "4px 12px",
                    fontSize: 12,
                    background: "rgba(99,102,241,0.15)",
                    border: "1px solid rgba(99,102,241,0.4)",
                    borderRadius: 6,
                    color: "#a5b4fc",
                    cursor: "pointer",
                }}
            >
                Download SVG
            </button>
        </div>
    );
}
