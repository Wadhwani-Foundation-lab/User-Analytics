"""
Generates NEP_Analytics_Test_Report.xlsx from nep_analytics/tests/test_report.json.
Matches the format of the existing docs/NEP_Test_Report.xlsx.

Usage:
    python nep_analytics/tests/generate_report.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ── Paths ────────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
REPORT_JSON = HERE / "test_report.json"
OUTPUT_XLSX = HERE / "NEP_Analytics_Test_Report.xlsx"

# ── Palette (matches existing report exactly) ────────────────────────────────
C_HEADER_DARK   = "002C5282"   # dark navy — section headers
C_HEADER_MID    = "001E3A5F"   # mid navy — table column headers
C_HEADER_LIGHT  = "00EBF5FF"   # pale blue — row labels in summary
C_ROW_ALT       = "00F7F9FC"   # near-white — alternating rows
C_PASS          = "00D4EDDA"   # green — PASS cells
C_WARN          = "00FFF3CD"   # amber — DATA_NOT_AVAILABLE
C_FAIL          = "00F8D7DA"   # red — SQL/parse/API error
C_INFO          = "00D1ECF1"   # teal — CLARIFICATION_NEEDED
C_WHITE         = "00FFFFFF"
C_NONE          = "00000000"   # transparent (no fill)

STATUS_FILL = {
    "PASS":                 C_PASS,
    "DATA_NOT_AVAILABLE":   C_WARN,
    "CLARIFICATION_NEEDED": C_INFO,
    "SQL_ERROR":            C_FAIL,
    "PARSE_ERROR":          C_FAIL,
    "API_ERROR":            C_FAIL,
}

STATUS_LABEL = {
    "PASS":                 "PASS",
    "DATA_NOT_AVAILABLE":   "DATA N/A",
    "CLARIFICATION_NEEDED": "CLARIFICATION",
    "SQL_ERROR":            "SQL ERROR",
    "PARSE_ERROR":          "PARSE ERROR",
    "API_ERROR":            "API ERROR",
}


# ── Style helpers ─────────────────────────────────────────────────────────────

def fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def font(bold=False, color="FF000000", size=10, name="Calibri") -> Font:
    return Font(bold=bold, color=color, size=size, name=name)


def wrap_align(horizontal="left", vertical="top") -> Alignment:
    return Alignment(horizontal=horizontal, vertical=vertical, wrap_text=True)


def thin_border() -> Border:
    s = Side(style="thin", color="FFD0D0D0")
    return Border(left=s, right=s, top=s, bottom=s)


def header_font(size=10) -> Font:
    return Font(bold=True, color="FFFFFFFF", size=size, name="Calibri")


def set_cell(ws, row, col, value, fill_color=None, bold=False, wrap=True,
             horizontal="left", font_color="FF000000", border=True):
    cell = ws.cell(row=row, column=col, value=value)
    if fill_color:
        cell.fill = fill(fill_color)
    cell.font = Font(bold=bold, color=font_color, size=10, name="Calibri")
    cell.alignment = Alignment(horizontal=horizontal, vertical="top", wrap_text=wrap)
    if border:
        cell.border = thin_border()
    return cell


# ── Sheet 1: All Questions ────────────────────────────────────────────────────

def build_all_questions(wb: openpyxl.Workbook, results: list[dict], run_at: str):
    ws = wb.create_sheet("All Questions")

    col_widths = [5, 32, 62, 12, 14, 26, 12, 16, 80, 62, 8, 13, 45]
    cols = ["#", "Category", "Question", "Status", "Path",
            "Certified Metric", "Confidence", "Response Type",
            "Answer", "SQL Used", "Rows", "Latency (ms)", "Error"]

    # Title row
    title = f"NEP Analytics — Test Suite Results   |   Run: {run_at}   |   {len(results)} questions"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cols))
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.fill = fill(C_HEADER_DARK)
    title_cell.font = Font(bold=True, color="FFFFFFFF", size=11, name="Calibri")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 20

    # Column header row
    for ci, h in enumerate(cols, 1):
        cell = ws.cell(row=2, column=ci, value=h)
        cell.fill = fill(C_HEADER_MID)
        cell.font = header_font()
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border()
    ws.row_dimensions[2].height = 16

    # Apply column widths
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = w

    # Freeze title + header
    ws.freeze_panes = "A3"

    # Data rows
    for ri, r in enumerate(results, 3):
        status = r["status"]
        status_color = STATUS_FILL.get(status, C_WARN)
        row_bg = C_WHITE if ri % 2 == 1 else "00F2F6FA"

        path = "certified" if r.get("certified") else "sql_gen"

        values = [
            r["num"],
            r["category"],
            r["question"],
            STATUS_LABEL.get(status, status),
            path,
            r.get("metric") or "",
            "",
            r.get("response_type") or "",
            r.get("answer") or "",
            r.get("sql_used") or "",
            r.get("row_count") or "",
            r.get("latency_ms") or "",
            r.get("error") or "",
        ]

        for ci, val in enumerate(values, 1):
            bg = status_color if ci == 4 else row_bg
            h_align = "center" if ci in (1, 4, 5, 7, 8, 11, 12) else "left"
            set_cell(ws, ri, ci, val, fill_color=bg,
                     bold=(ci == 1), wrap=True, horizontal=h_align)

        # Row height: taller for long answers
        answer_len = len(str(r.get("answer") or ""))
        ws.row_dimensions[ri].height = min(max(15, answer_len // 5), 120)

    # Auto-filter on header row
    ws.auto_filter.ref = f"A2:{openpyxl.utils.get_column_letter(len(cols))}2"


# ── Sheet 2: Summary ──────────────────────────────────────────────────────────

def build_summary(wb: openpyxl.Workbook, report: dict):
    ws = wb.create_sheet("Summary")
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18

    results = report["results"]
    s = report["summary"]
    total = report["meta"]["total_questions"]
    run_at = report["meta"]["finished_at"][:19].replace("T", " ")

    latencies = [r["latency_ms"] for r in results if r["latency_ms"]]
    avg_lat = round(statistics.mean(latencies) / 1000, 1) if latencies else 0
    p95_lat = round(sorted(latencies)[int(len(latencies) * 0.95)] / 1000, 1) if latencies else 0

    def section_header(row, title):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        c = ws.cell(row=row, column=1, value=title)
        c.fill = fill(C_HEADER_DARK)
        c.font = Font(bold=True, color="FFFFFFFF", size=11, name="Calibri")
        c.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[row].height = 18

    def kv_row(row, label, value, val_fill=C_NONE):
        lc = ws.cell(row=row, column=1, value=label)
        lc.fill = fill(C_HEADER_LIGHT)
        lc.font = Font(bold=True, size=10, name="Calibri")
        lc.alignment = Alignment(horizontal="left", vertical="center")
        lc.border = thin_border()
        vc = ws.cell(row=row, column=2, value=value)
        if val_fill and val_fill != C_NONE:
            vc.fill = fill(val_fill)
        vc.font = Font(size=10, name="Calibri")
        vc.alignment = Alignment(horizontal="left", vertical="center")
        vc.border = thin_border()
        ws.row_dimensions[row].height = 16

    # ── Single-Turn Summary ───────────────────────────────────────────────────
    section_header(1, f"Single-Turn Test Summary   |   Run: {run_at}")
    kv_row(2, "Total Questions Tested", total)
    kv_row(3, "PASS", f"{s['pass']}  ({s['pass_rate_pct']}%)", C_PASS)
    kv_row(4, "Data Not Available", f"{s['data_not_available']}  ({round(s['data_not_available']/total*100,1)}%)", C_WARN)
    kv_row(5, "Clarification Needed", f"{s['clarification_needed']}  ({round(s['clarification_needed']/total*100,1)}%)", C_INFO)
    kv_row(6, "SQL Error", f"{s['sql_error']}  ({round(s['sql_error']/total*100,1)}%)", C_FAIL if s['sql_error'] else C_NONE)
    kv_row(7, "Parse Error", f"{s['parse_error']}  ({round(s['parse_error']/total*100,1)}%)", C_FAIL if s['parse_error'] else C_NONE)
    kv_row(8, "API Error", f"{s['api_error']}  ({round(s['api_error']/total*100,1)}%)", C_FAIL if s['api_error'] else C_NONE)
    kv_row(9, "Certified metric path", f"{s['certified_path']}  ({round(s['certified_path']/total*100,1)}%)")
    kv_row(10, "SQL-gen path (Claude Opus)", f"{s['sql_gen_path']}  ({round(s['sql_gen_path']/total*100,1) if total else 0}%)")
    kv_row(11, "Avg response latency", f"{avg_lat}s")
    kv_row(12, "P95 response latency", f"{p95_lat}s")

    # ── Multi-Turn Summary ────────────────────────────────────────────────────
    mt = report.get("multi_turn_summary", {})
    if mt:
        section_header(14, "Multi-Turn Scenarios Summary")
        mt_total = mt.get("total", 0)
        kv_row(15, "Total Scenarios Tested", mt_total)
        kv_row(16, "PASS (all turns passed)", f"{mt.get('pass', 0)}  ({mt.get('pass_rate_pct', 0)}%)", C_PASS)
        kv_row(17, "PARTIAL (some turns no data)", f"{mt.get('partial', 0)}  ({round(mt.get('partial',0)/mt_total*100,1) if mt_total else 0}%)", C_WARN)
        kv_row(18, "ERROR (SQL/API error in any turn)", f"{mt.get('error', 0)}  ({round(mt.get('error',0)/mt_total*100,1) if mt_total else 0}%)", C_FAIL if mt.get('error') else C_NONE)
        kv_row(19, "Clarification Needed", f"{mt.get('clarification_needed', 0)}  ({round(mt.get('clarification_needed',0)/mt_total*100,1) if mt_total else 0}%)", C_INFO if mt.get('clarification_needed') else C_NONE)
        cat_start = 21
    else:
        cat_start = 14

    # ── By Category ───────────────────────────────────────────────────────────
    section_header(cat_start, "Results by Category")
    cat_start += 1

    # Category table header
    for ci, h in enumerate(["Category", "Total", "PASS", "Data N/A", "Error"], 1):
        c = ws.cell(row=cat_start, column=ci, value=h)
        c.fill = fill(C_HEADER_MID)
        c.font = header_font()
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border()
    ws.row_dimensions[cat_start].height = 16

    by_cat = report["by_category"]
    data_row_start = cat_start + 1
    for ri, (cat, counts) in enumerate(sorted(by_cat.items()), data_row_start):
        pct = round(counts["pass"] / counts["total"] * 100) if counts["total"] else 0
        row_bg = C_ROW_ALT if ri % 2 == 0 else C_WHITE
        err = counts["error"] + counts.get("clarification", 0)
        for ci, val in enumerate([
            cat,
            counts["total"],
            f"{counts['pass']} ({pct}%)",
            counts["data_na"],
            err,
        ], 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill = fill(row_bg)
            c.font = Font(size=10, name="Calibri")
            c.alignment = Alignment(horizontal="left" if ci == 1 else "center", vertical="center")
            c.border = thin_border()
        ws.row_dimensions[ri].height = 15

    # ── Errors Log ────────────────────────────────────────────────────────────
    err_row = data_row_start + len(by_cat) + 2
    section_header(err_row, "Errors Log")
    err_row += 1

    for ci, h in enumerate(["#", "Question", "Error"], 1):
        c = ws.cell(row=err_row, column=ci, value=h)
        c.fill = fill(C_HEADER_MID)
        c.font = header_font()
        c.border = thin_border()
    ws.row_dimensions[err_row].height = 15
    err_row += 1

    errors = [r for r in results if r["status"] not in ("PASS", "DATA_NOT_AVAILABLE", "CLARIFICATION_NEEDED")]
    if errors:
        for r in errors:
            ws.cell(row=err_row, column=1, value=r["num"]).border = thin_border()
            qc = ws.cell(row=err_row, column=2, value=r["question"])
            qc.alignment = Alignment(wrap_text=True)
            qc.border = thin_border()
            ec = ws.cell(row=err_row, column=3, value=(r.get("error") or "")[:200])
            ec.fill = fill(C_FAIL)
            ec.alignment = Alignment(wrap_text=True)
            ec.border = thin_border()
            ws.row_dimensions[err_row].height = 30
            err_row += 1
    else:
        c = ws.cell(row=err_row, column=1, value="No errors")
        c.fill = fill(C_PASS)
        c.font = Font(bold=True, size=10, name="Calibri", color="FF155724")
        c.border = thin_border()


# ── Sheet 3: Multi-Turn Scenarios ────────────────────────────────────────────

SCENARIO_STATUS_FILL = {
    "PASS":                 C_PASS,
    "PARTIAL":              C_WARN,
    "ERROR":                C_FAIL,
    "CLARIFICATION_NEEDED": C_INFO,
}

SCENARIO_STATUS_LABEL = {
    "PASS":                 "PASS",
    "PARTIAL":              "PARTIAL",
    "ERROR":                "ERROR",
    "CLARIFICATION_NEEDED": "CLARIFICATION",
}


def build_multi_turn(wb: openpyxl.Workbook, report: dict):
    ws = wb.create_sheet("Multi-Turn Scenarios")

    col_widths = [8, 8, 50, 14, 16, 80, 62, 8, 14, 50]
    cols = ["Scenario", "Turn", "Question", "Status", "Response Type",
            "Answer", "SQL Used", "Rows", "Latency (ms)", "Error"]

    scenario_results = report.get("scenario_results", [])
    mt = report.get("multi_turn_summary", {})
    run_at = report["meta"]["finished_at"][:16].replace("T", " ")
    total = len(scenario_results)
    passed = mt.get("pass", 0)
    partial = mt.get("partial", 0)
    errors = mt.get("error", 0)

    # Title
    title = (f"Multi-Turn Scenarios   |   Run: {run_at}   |   "
             f"{total} scenarios  —  {passed} PASS  {partial} PARTIAL  {errors} ERROR")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cols))
    tc = ws.cell(row=1, column=1, value=title)
    tc.fill = fill(C_HEADER_DARK)
    tc.font = Font(bold=True, color="FFFFFFFF", size=11, name="Calibri")
    tc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 20

    # Column headers
    for ci, h in enumerate(cols, 1):
        c = ws.cell(row=2, column=ci, value=h)
        c.fill = fill(C_HEADER_MID)
        c.font = header_font()
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border()
    ws.row_dimensions[2].height = 16

    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = w

    ws.freeze_panes = "A3"

    ri = 3
    for scenario in scenario_results:
        overall = scenario["overall_status"]
        sc_fill = SCENARIO_STATUS_FILL.get(overall, C_WARN)
        turns = scenario["turns"]

        # Scenario header row — label in cols 1-3, status badge in col 4
        sc_label = f"{scenario['id']} — {scenario['name']}"
        for ci in range(1, len(cols) + 1):
            hc = ws.cell(row=ri, column=ci)
            hc.fill = fill("001E3A5F")
            hc.font = Font(bold=True, color="FFFFFFFF", size=10, name="Calibri")
            hc.alignment = Alignment(horizontal="left", vertical="center")
        ws.cell(row=ri, column=1).value = sc_label
        badge_cell = ws.cell(row=ri, column=4)
        badge_cell.value = SCENARIO_STATUS_LABEL.get(overall, overall)
        badge_cell.fill = fill(sc_fill)
        badge_cell.font = Font(bold=True, color="FF000000" if overall != "ERROR" else "FFFFFFFF", size=10, name="Calibri")
        badge_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[ri].height = 16
        ri += 1

        # Turn rows
        for turn in turns:
            status = turn["status"]
            turn_fill = STATUS_FILL.get(status, C_WARN)
            row_bg = "00F7F9FC"

            values = [
                scenario["id"],
                f"T{turn['turn_num']}",
                turn["question"],
                STATUS_LABEL.get(status, status),
                turn.get("response_type") or "",
                turn.get("answer") or "",
                turn.get("sql_used") or "",
                turn.get("row_count") or "",
                turn.get("latency_ms") or "",
                turn.get("error") or "",
            ]

            for ci, val in enumerate(values, 1):
                bg = turn_fill if ci == 4 else row_bg
                h_align = "center" if ci in (1, 2, 4, 5, 8, 9) else "left"
                c = ws.cell(row=ri, column=ci, value=val)
                c.fill = fill(bg)
                c.font = Font(size=10, name="Calibri")
                c.alignment = Alignment(horizontal=h_align, vertical="top", wrap_text=True)
                c.border = thin_border()

            ws.row_dimensions[ri].height = min(max(15, len(str(turn.get("answer") or "")) // 6), 100)
            ri += 1

        # Blank spacer between scenarios
        ws.row_dimensions[ri].height = 6
        ri += 1

    ws.auto_filter.ref = f"A2:{openpyxl.utils.get_column_letter(len(cols))}2"


# ── Sheet 4: Data Not Available detail ───────────────────────────────────────

def build_data_na(wb: openpyxl.Workbook, results: list[dict]):
    ws = wb.create_sheet("Data Not Available")
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 62
    ws.column_dimensions["D"].width = 62
    ws.column_dimensions["E"].width = 13

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
    tc = ws.cell(row=1, column=1, value="Data Not Available — Queries executed correctly; no matching rows in the sample dataset")
    tc.fill = fill("00856404")
    tc.font = Font(bold=True, color="FFFFFFFF", size=11, name="Calibri")
    tc.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 18

    for ci, h in enumerate(["#", "Category", "Question", "SQL Used", "Latency (ms)"], 1):
        c = ws.cell(row=2, column=ci, value=h)
        c.fill = fill(C_HEADER_MID)
        c.font = header_font()
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border()
    ws.row_dimensions[2].height = 15

    na_rows = [r for r in results if r["status"] == "DATA_NOT_AVAILABLE"]
    for ri, r in enumerate(na_rows, 3):
        bg = C_WHITE if ri % 2 == 1 else "00FFFBF0"
        for ci, val in enumerate([r["num"], r["category"], r["question"], r.get("sql_used",""), r.get("latency_ms","")], 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill = fill(bg)
            c.font = Font(size=10, name="Calibri")
            c.alignment = Alignment(horizontal="left" if ci != 1 else "center", vertical="top", wrap_text=True)
            c.border = thin_border()
        ws.row_dimensions[ri].height = 45

    ws.freeze_panes = "A3"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(REPORT_JSON, encoding="utf-8") as f:
        report = json.load(f)

    results = report["results"]
    run_at = report["meta"]["finished_at"][:16].replace("T", " ")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet

    build_all_questions(wb, results, run_at)
    build_multi_turn(wb, report)
    build_summary(wb, report)
    build_data_na(wb, results)

    wb.save(OUTPUT_XLSX)
    mt = report.get("multi_turn_summary", {})
    print(f"Report saved → {OUTPUT_XLSX}")
    print(f"  Sheets: {wb.sheetnames}")
    print(f"  Single-turn  : {len(results)} questions  |  PASS: {report['summary']['pass']}  |  Data N/A: {report['summary']['data_not_available']}  |  Errors: {report['summary']['total_errors']}")
    if mt:
        print(f"  Multi-turn   : {mt.get('total', 0)} scenarios  |  PASS: {mt.get('pass', 0)}  |  PARTIAL: {mt.get('partial', 0)}  |  ERROR: {mt.get('error', 0)}")


if __name__ == "__main__":
    main()
