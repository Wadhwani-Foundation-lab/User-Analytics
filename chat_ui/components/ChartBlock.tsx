"use client";

import { useEffect, useRef } from "react";
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
    Filler
);

interface ChartBlockProps {
    config: ChartConfig;
}

const CHART_OPTIONS_BASE = {
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
};

const PIE_OPTIONS = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
        legend: {
            position: "right" as const,
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
    },
};

export default function ChartBlock({ config }: ChartBlockProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    const data = {
        labels: config.labels,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        datasets: config.datasets as ChartDataset<any, (number | null)[]>[],
    };

    const downloadChart = () => {
        if (canvasRef.current) {
            const link = document.createElement("a");
            link.download = `analytics-chart-${Date.now()}.png`;
            link.href = canvasRef.current.toDataURL("image/png");
            link.click();
        }
    };

    return (
        <div className="chart-block">
            {config.title && <p className="chart-title">{config.title}</p>}
            <div className="chart-canvas-wrapper">
                {config.type === "bar" && (
                    <Bar
                        data={data}
                        options={{
                            ...CHART_OPTIONS_BASE,
                            plugins: {
                                ...CHART_OPTIONS_BASE.plugins,
                                title: { display: false },
                            },
                        }}
                    />
                )}
                {config.type === "line" && (
                    <Line
                        data={data}
                        options={{
                            ...CHART_OPTIONS_BASE,
                            plugins: {
                                ...CHART_OPTIONS_BASE.plugins,
                                title: { display: false },
                            },
                        }}
                    />
                )}
                {config.type === "pie" && <Pie data={data} options={PIE_OPTIONS} />}
            </div>
            <button onClick={downloadChart} className="download-btn">
                ↓ Download PNG
            </button>
        </div>
    );
}
