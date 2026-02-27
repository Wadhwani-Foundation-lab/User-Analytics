"use client";

import { useRef } from "react";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Title,
    Tooltip,
    Legend,
    Filler,
    type ChartDataset,
} from "chart.js";
import ChartDataLabels from "chartjs-plugin-datalabels";
import { Bar, Line, Pie } from "react-chartjs-2";
import { ChartConfig } from "@/lib/types";

ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Title,
    Tooltip,
    Legend,
    Filler,
    ChartDataLabels
);

interface ChartBlockProps {
    config: ChartConfig;
}

/** Shared data-label style for bar / line charts */
const BAR_LINE_DATALABELS = {
    display: true,
    color: "#f1f5f9",
    anchor: "end" as const,
    align: "top" as const,
    font: { size: 10, family: "'Inter', sans-serif" },
    formatter: (value: number | null) =>
        value === null || value === 0 ? "" : value.toLocaleString(),
};

/** Data-label style for pie charts */
const PIE_DATALABELS = {
    display: true,
    color: "#f1f5f9",
    font: { size: 11, weight: "bold" as const, family: "'Inter', sans-serif" },
    formatter: (value: number, ctx: { chart: ChartJS<"pie">; dataIndex: number }) => {
        const dataset = ctx.chart.data.datasets[0];
        const total = (dataset.data as number[]).reduce((a, b) => a + (b ?? 0), 0);
        const pct = total ? ((value / total) * 100).toFixed(1) : "0";
        return `${pct}%`;
    },
};

function buildTitle(title?: string) {
    if (!title) return { display: false };
    return {
        display: true,
        text: title,
        color: "#f1f5f9",
        font: { size: 14, weight: "bold" as const, family: "'Inter', sans-serif" },
        padding: { bottom: 12 },
    };
}

export default function ChartBlock({ config }: ChartBlockProps) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chartRef = useRef<ChartJS<any>>(null);

    const data = {
        labels: config.labels,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        datasets: config.datasets as ChartDataset<any, (number | null)[]>[],
    };

    const downloadChart = () => {
        if (!chartRef.current) return;
        const chart = chartRef.current;
        const canvas = chart.canvas;

        // Draw onto an off-screen canvas with a dark background so the PNG
        // looks identical to the on-screen chart (transparent → black otherwise).
        const offscreen = document.createElement("canvas");
        offscreen.width = canvas.width;
        offscreen.height = canvas.height;
        const ctx = offscreen.getContext("2d")!;
        ctx.fillStyle = "#0f172a";          // match app dark background
        ctx.fillRect(0, 0, offscreen.width, offscreen.height);
        ctx.drawImage(canvas, 0, 0);

        const link = document.createElement("a");
        link.download = `analytics-chart-${Date.now()}.png`;
        link.href = offscreen.toDataURL("image/png");
        link.click();
    };

    const titlePlugin = buildTitle(config.title);

    return (
        <div className="chart-block">
            {/* Keep the visible heading for UI; the title is ALSO drawn on canvas for PNG */}
            {config.title && <p className="chart-title">{config.title}</p>}
            <div className="chart-canvas-wrapper">
                {config.type === "bar" && (
                    <Bar
                        ref={chartRef}
                        data={data}
                        options={{
                            responsive: true,
                            maintainAspectRatio: true,
                            plugins: {
                                legend: {
                                    labels: {
                                        color: "#cbd5e1",
                                        font: { family: "'Inter', sans-serif", size: 12 },
                                    },
                                },
                                tooltip: {
                                    backgroundColor: "#1e293b",
                                    titleColor: "#f1f5f9",
                                    bodyColor: "#94a3b8",
                                    borderColor: "#334155",
                                    borderWidth: 1,
                                },
                                title: titlePlugin,
                                datalabels: BAR_LINE_DATALABELS,
                            },
                            scales: {
                                x: {
                                    ticks: { color: "#94a3b8", font: { size: 11 } },
                                    grid: { color: "#1e293b" },
                                },
                                y: {
                                    ticks: { color: "#94a3b8", font: { size: 11 } },
                                    grid: { color: "#1e293b" },
                                },
                            },
                        }}
                    />
                )}
                {config.type === "line" && (
                    <Line
                        ref={chartRef}
                        data={data}
                        options={{
                            responsive: true,
                            maintainAspectRatio: true,
                            plugins: {
                                legend: {
                                    labels: {
                                        color: "#cbd5e1",
                                        font: { family: "'Inter', sans-serif", size: 12 },
                                    },
                                },
                                tooltip: {
                                    backgroundColor: "#1e293b",
                                    titleColor: "#f1f5f9",
                                    bodyColor: "#94a3b8",
                                    borderColor: "#334155",
                                    borderWidth: 1,
                                },
                                title: titlePlugin,
                                datalabels: BAR_LINE_DATALABELS,
                            },
                            scales: {
                                x: {
                                    ticks: { color: "#94a3b8", font: { size: 11 } },
                                    grid: { color: "#1e293b" },
                                },
                                y: {
                                    ticks: { color: "#94a3b8", font: { size: 11 } },
                                    grid: { color: "#1e293b" },
                                },
                            },
                        }}
                    />
                )}
                {config.type === "pie" && (
                    <Pie
                        ref={chartRef}
                        data={data}
                        options={{
                            responsive: true,
                            maintainAspectRatio: true,
                            plugins: {
                                legend: {
                                    position: "right",
                                    labels: {
                                        color: "#cbd5e1",
                                        font: { family: "'Inter', sans-serif", size: 12 },
                                        padding: 16,
                                    },
                                },
                                tooltip: {
                                    backgroundColor: "#1e293b",
                                    titleColor: "#f1f5f9",
                                    bodyColor: "#94a3b8",
                                    borderColor: "#334155",
                                    borderWidth: 1,
                                },
                                title: titlePlugin,
                                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                datalabels: PIE_DATALABELS as any,
                            },
                        }}
                    />
                )}
            </div>
            <button onClick={downloadChart} className="download-btn">
                ↓ Download PNG
            </button>
        </div>
    );
}
