"use client";

import { TableData } from "@/lib/types";

interface TableBlockProps {
    data: TableData;
}

export default function TableBlock({ data }: TableBlockProps) {
    const { columns, rows } = data;

    return (
        <div className="table-wrapper">
            <div className="table-scroll">
                <table className="data-table">
                    <thead>
                        <tr>
                            {columns.map((col) => (
                                <th key={col}>{col.replace(/_/g, " ")}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, ri) => (
                            <tr key={ri}>
                                {row.map((cell, ci) => (
                                    <td key={ci}>{cell !== null && cell !== undefined ? String(cell) : "—"}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="table-meta">{rows.length} row{rows.length !== 1 ? "s" : ""}</p>
        </div>
    );
}
