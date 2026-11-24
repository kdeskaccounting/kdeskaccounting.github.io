#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openpyxl>=3.1",
# ]
# ///
"""
Build the KDesk Accounting Month-End Close Checklist + Tie-Out Workbook.

Free lead-magnet companion to the paid Fixed Asset / ASC 606 / ASC 842 workbooks.

Produces:
- dist/templates/month-end-close-checklist-v1.1.xlsx

v1.1 (2026-11-24 audit fixes, MEC-1..MEC-9):
- README cross-sell names products and kdeskaccounting.com pages, no prices,
  no "audit-ready"; row 29 is the Amortization Calculator (MEC-1, MEC-5).
- "1 flag" / "N flags" (MEC-2).
- Light sample data for a fictional company so every check is visible on open;
  blank reconciliation rows show nothing instead of "OK" (MEC-3).
- Conditional-format fills carry bgColor, which is what Excel renders (MEC-6).
- Tie-out tolerance (default $1.00) replaces performance materiality as the
  reconciliation threshold (MEC-7).
- Close Calendar has 20 blank task rows and every range runs to row 200, so a
  task typed below the list is counted (MEC-8).
- Fiscal Year End and Reporting Currency feed the headers; each JE # is checked
  for debit = credit on its own; file author is KDesk Accounting; the last tab is
  "Sign-Off" (MEC-9).

v1.1 re-review (same file name; v1.1 had not shipped):
- JE Tracker "Balanced?" reads "No entries yet" (no colour) on an empty log;
  Entry Check matches JE # exactly (EXACT, no case folding or wildcards).
- Sign-Off "JE entries posted" counts distinct JE #s, not lines.
- Variance is ROUND(GL - Sub, 2); a row with one balance reads INCOMPLETE and
  the Totals variance sums the row variances.
- Sample data tells one story (task status matches recs and JEs); lease JE
  credits accretion to the liability and amortization to the ROU asset.
- README clearing steps name every sample cell; due dates and Sign-Off cope
  with a blank Period End Date (and it is date-validated).
- docProps/app.xml names KDesk Accounting, not openpyxl; the "add rows" hint
  moved out of the counted range, and rows 68-200 are auto-numbered.

Five tabs:
  1. README + Setup       Company config, tie-out tolerance, quickstart, cross-sell
  2. Close Calendar       ~40 pre-populated tasks across 5 phases (Day 1-2 .. Day 5+)
  3. Reconciliations      18 standard subledger-to-GL ties with variance + flag
  4. JE Tracker           Period JE log with per-entry and total debit=credit checks
  5. Sign-Off             Printable sign-off page summarizing the close

Function library: Excel 2016/365/Mac safe set (no XLOOKUP, LET, LAMBDA, IFS,
dynamic-array spills). All formulas tested via openpyxl re-load smoke test.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = REPO_ROOT / "dist" / "templates"

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

COLOR_NAVY = "FF1F4E78"
COLOR_WHITE = "FFFFFFFF"
COLOR_SECTION_BG = "FFD9E1F2"
COLOR_INPUT_BG = "FFFFF2CC"
COLOR_BORDER = "FFB7B7B7"
COLOR_GREEN = "FFC6EFCE"
COLOR_GREEN_FG = "FF006100"
COLOR_YELLOW = "FFFFEB9C"
COLOR_YELLOW_FG = "FF9C5700"
COLOR_RED = "FFFFC7CE"
COLOR_RED_FG = "FF9C0006"
COLOR_GRAY = "FFE7E6E6"
COLOR_GRAY_FG = "FF595959"

THIN = Side(style="thin", color=COLOR_BORDER)
BORDER_ALL = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

FILL_HEADER = PatternFill("solid", fgColor=COLOR_NAVY)
FILL_SECTION = PatternFill("solid", fgColor=COLOR_SECTION_BG)
FILL_INPUT = PatternFill("solid", fgColor=COLOR_INPUT_BG)


def cf_fill(color: str) -> PatternFill:
    """Fill for a conditional-format (differential) style.

    Excel renders a dxf solid fill from bgColor; fgColor alone is ignored (MEC-6).
    Set both so Excel and LibreOffice agree.
    """
    return PatternFill(fill_type="solid", fgColor=color, bgColor=color)

FONT_TITLE = Font(name="Calibri", size=20, bold=True, color=COLOR_NAVY)
FONT_H2 = Font(name="Calibri", size=13, bold=True, color=COLOR_NAVY)
FONT_HEADER = Font(name="Calibri", size=11, bold=True, color=COLOR_WHITE)
FONT_BODY = Font(name="Calibri", size=11)
FONT_BODY_BOLD = Font(name="Calibri", size=11, bold=True)
FONT_NOTE = Font(name="Calibri", size=10, italic=True, color=COLOR_GRAY_FG)
FONT_LINK = Font(name="Calibri", size=11, color="FF2E75B6", underline="single")

ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_LEFT_TOP = Alignment(horizontal="left", vertical="top", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

STATUS_OPTIONS = ["Not Started", "In Progress", "Done", "Blocked", "N/A"]
JE_SOURCE_OPTIONS = [
    "Manual",
    "FA Workbook (KDesk)",
    "ASC 606 Workbook (KDesk)",
    "ASC 842 Workbook (KDesk)",
    "GL System Auto",
    "Other",
]
YES_NO = ["Yes", "No", "N/A"]

# Pre-populated tasks: (phase, task, owner_default)
TASKS: list[tuple[str, str, str]] = [
    # Phase 1: Day 1-2 cutoff
    ("Day 1-2 — Cutoff & Data Collection", "Confirm all revenue recognized in the period has a corresponding invoice or contract milestone", "Revenue Accountant"),
    ("Day 1-2 — Cutoff & Data Collection", "Identify deals signed in the last 3 days — confirm period recognition", "Revenue Accountant"),
    ("Day 1-2 — Cutoff & Data Collection", "Pull deferred revenue balance from subledger and reconcile to GL", "Revenue Accountant"),
    ("Day 1-2 — Cutoff & Data Collection", "Post all vendor invoices received through last business day", "AP Accountant"),
    ("Day 1-2 — Cutoff & Data Collection", "Accrue for goods/services received but not yet invoiced (legal, consulting, cloud)", "AP Accountant"),
    ("Day 1-2 — Cutoff & Data Collection", "Confirm purchase order cutoff with operations / procurement", "AP Accountant"),
    ("Day 1-2 — Cutoff & Data Collection", "Accrue wages earned but not paid (partial pay periods)", "Payroll"),
    ("Day 1-2 — Cutoff & Data Collection", "Post payroll tax and benefits accruals", "Payroll"),
    ("Day 1-2 — Cutoff & Data Collection", "Update commission expense accruals (see ASC 606 schedule)", "Payroll / Comp"),
    ("Day 1-2 — Cutoff & Data Collection", "Pull final bank statements for the last day of the period", "Treasury"),
    ("Day 1-2 — Cutoff & Data Collection", "Post unrecorded bank items (fees, interest, wires)", "Treasury"),
    ("Day 1-2 — Cutoff & Data Collection", "Confirm all credit card charges imported and coded", "AP Accountant"),

    # Phase 2: Day 2-3 subledger
    ("Day 2-3 — Subledger Reconciliations", "AR subledger balance ties to GL", "AR Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Aged AR report reviewed — flag items >90 days for reserve analysis", "AR Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Bad debt reserve updated (if allowance method)", "AR Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Credit memos and unapplied cash resolved", "AR Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "AP subledger balance ties to GL", "AP Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Vendor statements reconciled for key vendors", "AP Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Outstanding checks reviewed for stale items (>90 days)", "AP Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Fixed asset additions and disposals posted for the period", "Fixed Asset Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Depreciation run for all assets (see FA Rollforward Workbook)", "Fixed Asset Accountant"),
    ("Day 2-3 — Subledger Reconciliations", "Accumulated depreciation ties to fixed asset subledger", "Fixed Asset Accountant"),

    # Phase 3: Day 3-4 technical schedules
    ("Day 3-4 — Technical Accounting Schedules", "Deferred commission new payments entered (see ASC 606 Workbook)", "Revenue Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Period amortization expense calculated and JE posted", "Revenue Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Deferred commission asset balance per schedule ties to GL", "Revenue Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Monthly lease JE generated per active lease (see ASC 842 Workbook)", "Technical Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Lease liability balance per amortization schedule ties to GL", "Technical Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "ROU asset balance per schedule ties to GL", "Technical Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Any new leases commenced — initial recognition entry posted", "Technical Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Prepaid schedule updated with new payments; monthly amortization posted", "Staff Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Recurring accruals posted (insurance, rent, professional fees)", "Staff Accountant"),
    ("Day 3-4 — Technical Accounting Schedules", "Prior-period one-time accruals reversed if appropriate", "Staff Accountant"),

    # Phase 4: Day 4-5 equity / tax / other
    ("Day 4-5 — Equity, Tax & Other", "Stock-based comp expense calculated and posted (RSUs, options)", "Technical Accountant"),
    ("Day 4-5 — Equity, Tax & Other", "Tax provision estimate adjusted; deferred tax true-up if needed", "Tax / Controller"),
    ("Day 4-5 — Equity, Tax & Other", "FX revaluation posted (if foreign-currency balances)", "Technical Accountant"),
    ("Day 4-5 — Equity, Tax & Other", "Inter-company eliminations posted (if multi-entity)", "Technical Accountant"),

    # Phase 5: Day 5+ statements & review
    ("Day 5+ — Statements & Review", "Trial balance pulled; debits = credits", "Controller"),
    ("Day 5+ — Statements & Review", "Balance sheet, income statement, and cash flow generated", "Controller"),
    ("Day 5+ — Statements & Review", "Flux / variance analysis vs prior period (significant items explained)", "Controller"),
    ("Day 5+ — Statements & Review", "Management review with CFO / CEO; adjustments posted", "Controller / CFO"),
    ("Day 5+ — Statements & Review", "Period locked in GL system", "Controller"),
    ("Day 5+ — Statements & Review", "Close package distributed to leadership / board", "Controller / CFO"),
]

# Pre-populated reconciliations: (account_name, source/schedule, category)
RECONCILIATIONS: list[tuple[str, str]] = [
    ("Cash — Operating Account", "Bank statement / Treasury workbook"),
    ("Cash — Money Market / Savings", "Bank statement"),
    ("Accounts Receivable", "AR aging subledger"),
    ("Allowance for Doubtful Accounts", "Reserve calculation"),
    ("Prepaid Expenses", "Prepaid amortization schedule"),
    ("Deferred Commissions (ASC 606)", "ASC 606 Commission Workbook"),
    ("Fixed Assets — Cost", "Fixed Asset Register"),
    ("Accumulated Depreciation", "FA Rollforward Workbook"),
    ("ROU Asset — Operating Leases", "ASC 842 Lease Workbook"),
    ("ROU Asset — Finance Leases", "ASC 842 Lease Workbook"),
    ("Accounts Payable", "AP aging subledger"),
    ("Accrued Liabilities", "Accrual schedule"),
    ("Accrued Payroll & Benefits", "Payroll provider report"),
    ("Lease Liability — Operating", "ASC 842 Lease Workbook"),
    ("Lease Liability — Finance", "ASC 842 Lease Workbook"),
    ("Deferred Revenue", "Revenue recognition subledger"),
    ("Common Stock & APIC", "Cap table / equity ledger"),
    ("Retained Earnings", "Roll-forward from prior period"),
]


# ---------------------------------------------------------------------------
# Sample data (MEC-3). A fictional company part-way through its May 2026 close,
# light enough to clear in a minute. Every value sits in a yellow input cell.
# ---------------------------------------------------------------------------

# Business days after Period End Date that each phase is due (WORKDAY default).
PHASE_DUE_OFFSET = {
    "Day 1-2": 2,
    "Day 2-3": 3,
    "Day 3-4": 4,
    "Day 4-5": 5,
    "Day 5+": 6,
}

# Task number (1-based) -> (status, note). Unlisted tasks stay "Not Started".
# The story: business day 3 of the May close. Cutoff is finished, the subledger
# and schedule work is mostly done, statements and review have not started.
# Each Done task that has a reconciliation or a JE has a matching Done rec / Posted JE.
SAMPLE_TASK_STATUS: dict[int, tuple[str, str | None]] = {
    **{n: ("Done", None) for n in range(1, 13)},          # Day 1-2: all done
    13: ("Done", None), 14: ("Done", None), 15: ("Done", None), 16: ("Done", None),
    17: ("In Progress", "See Reconciliations #11: AP variance"),
    18: ("Blocked", "Waiting on statement from the largest vendor"),
    19: ("Done", None), 20: ("Done", None),
    21: ("Done", "JE-0501"),
    22: ("Done", None),
    23: ("Done", None),
    24: ("Done", "JE-0502"),
    25: ("Done", None),
    26: ("Done", "JE-0503"),
    27: ("In Progress", "Tying the liability to the May schedule"),
    28: ("Done", None),
    29: ("Done", "No new leases in May"),
    30: ("Done", None),
    31: ("In Progress", "Legal fee accrual JE-0504 waiting for review"),
    36: ("N/A", "Single entity"),
}

# Reconciliation number (1-based) -> (GL balance, sub/schedule balance, status, note).
# Unlisted reconciliations are left blank and "Not Started".
SAMPLE_RECS: dict[int, tuple[float | None, float | None, str, str | None]] = {
    1: (1842310.55, 1842310.55, "Done", None),
    2: (2500000.00, 2500000.00, "Done", None),
    3: (612480.00, 612480.00, "Done", None),
    4: (18400.00, 18400.00, "Done", None),
    5: (96250.00, 96250.00, "Done", None),
    6: (241118.40, 241118.40, "Done", None),
    7: (388920.00, 388920.00, "Done", None),
    8: (142605.33, 142605.33, "Done", None),
    9: (455300.12, 455300.12, "Done", None),
    10: (None, None, "N/A", "No finance leases"),
    11: (203775.10, 198275.10, "In Progress", "Invoice posted to GL after the AP aging was pulled"),
    13: (164920.75, 164920.75, "Done", None),
    14: (None, None, "In Progress", None),
    15: (None, None, "N/A", "No finance leases"),
    16: (1326540.00, 1326540.00, "Done", None),
}

# JE lines: (date offset from period end in days, JE #, description, account, debit, credit, source, status)
SAMPLE_JES: list[tuple[int, str, str, str, float | None, float | None, str, str]] = [
    (0, "JE-0501", "May depreciation", "Depreciation Expense", 6482.00, None, "FA Workbook (KDesk)", "Posted"),
    (0, "JE-0501", "May depreciation", "Accumulated Depreciation", None, 6482.00, "FA Workbook (KDesk)", "Posted"),
    (0, "JE-0502", "May commission amortization", "Commission Expense", 14210.50, None, "ASC 606 Workbook (KDesk)", "Posted"),
    (0, "JE-0502", "May commission amortization", "Deferred Commissions", None, 14210.50, "ASC 606 Workbook (KDesk)", "Posted"),
    (0, "JE-0503", "May operating lease cost", "Lease Expense", 22000.00, None, "ASC 842 Workbook (KDesk)", "Posted"),
    (0, "JE-0503", "May operating lease cost", "Lease Liability — Operating", None, 3859.75, "ASC 842 Workbook (KDesk)", "Posted"),
    (0, "JE-0503", "May operating lease cost", "ROU Asset — Operating Leases", None, 18140.25, "ASC 842 Workbook (KDesk)", "Posted"),
    (0, "JE-0504", "Accrue May legal fees", "Professional Fees", 9500.00, None, "Manual", "Pending"),
    (0, "JE-0504", "Accrue May legal fees", "Accrued Liabilities", None, 9500.00, "Manual", "Pending"),
]

CALENDAR_SPARE_ROWS = 20      # blank, formatted task rows below the list
CALENDAR_RANGE_END = 200      # every Calendar range / name runs to this row (MEC-8)

CURRENCY_FMT = "$#,##0.00;[Red]($#,##0.00);\"–\""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def set_cell(ws, ref, value, font=None, fill=None, align=None, border=None, number_format=None):
    c = ws[ref]
    c.value = value
    if font is not None:
        c.font = font
    if fill is not None:
        c.fill = fill
    if align is not None:
        c.alignment = align
    if border is not None:
        c.border = border
    if number_format is not None:
        c.number_format = number_format
    return c


def write_table_header(ws, row, headers, start_col=1):
    for i, h in enumerate(headers):
        col = get_column_letter(start_col + i)
        set_cell(ws, f"{col}{row}", h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    ws.row_dimensions[row].height = 32


def set_col_widths(ws, widths: dict[str, float]):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def add_defined_name(wb, name, ref):
    """Workbook-level defined name. ref is like 'Setup!$B$5'."""
    dn = DefinedName(name=name, attr_text=ref)
    wb.defined_names[name] = dn


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def build_readme_setup(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "README & Setup"
    set_col_widths(ws, {"A": 4, "B": 28, "C": 50, "D": 24, "E": 24, "F": 24})
    ws.sheet_view.showGridLines = False

    # Title band
    ws.merge_cells("B2:F2")
    set_cell(ws, "B2", "Month-End Close Checklist + Tie-Out Workbook",
             font=Font(name="Calibri", size=22, bold=True, color=COLOR_WHITE),
             fill=FILL_HEADER, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[2].height = 42

    ws.merge_cells("B3:F3")
    set_cell(ws, "B3", "by KDesk Accounting — free companion to our paid workbooks. v1.1",
             font=FONT_NOTE, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[3].height = 20

    # Quickstart
    set_cell(ws, "B5", "Quickstart", font=FONT_H2)
    quickstart = [
        "1. Fill in your company info in the Setup table below (yellow cells).",
        f"2. Go to the Close Calendar tab. Review the {len(TASKS)} pre-populated tasks. Adjust Owner and Due Date for your team. Type extra tasks into the blank rows below the list, or insert rows anywhere up to row {CALENDAR_RANGE_END}; they are counted automatically.",
        "3. Work through tasks during the close. Set Status as you go: Done turns green, In Progress yellow, Blocked red, N/A gray.",
        "4. On Reconciliations, enter GL Balance and Subledger Balance for each account. Variance and the OK / FLAG column calculate against the Tie-Out Tolerance from Setup.",
        "5. Log every JE line on JE Tracker. Entry Check confirms each JE # balances on its own; the check at the bottom confirms the whole log.",
        "6. Finish on Sign-Off. The summary metrics auto-populate. Have Preparer, Reviewer, and Controller sign off, lock the period in your GL, and distribute the close package.",
    ]
    for i, line in enumerate(quickstart):
        set_cell(ws, f"B{6+i}", line, font=FONT_BODY, align=ALIGN_LEFT_TOP)
        ws.merge_cells(f"B{6+i}:F{6+i}")
        ws.row_dimensions[6+i].height = 28

    # Sample-data note (MEC-3)
    note_row = 6 + len(quickstart)
    set_cell(ws, f"B{note_row}",
             "Sample data: the file opens part-way through a May 2026 close for a fictional company (Acme Corp.) so you can see every check working. "
             "Before your first close: (1) replace the Setup values; (2) Close Calendar: set every Status to Not Started and clear the Notes column "
             "(Owner holds role names, so replace them with your team); (3) Reconciliations: clear the GL and Sub/Schedule balances, Preparer, "
             "Reviewer and Notes, and set every Status to Not Started; (4) JE Tracker: clear every yellow cell from Date to Status.",
             font=Font(name="Calibri", size=11, bold=True, color=COLOR_YELLOW_FG), align=ALIGN_LEFT_TOP)
    ws.merge_cells(f"B{note_row}:F{note_row}")
    ws.row_dimensions[note_row].height = 62

    # Setup table
    setup_row = 14
    set_cell(ws, f"B{setup_row}", "Setup", font=FONT_H2)
    setup_fields = [
        ("Company Name", "Acme Corp.", "text"),
        ("Fiscal Year End (MM-DD)", "12-31", "text"),
        ("Current Period (e.g., May 2026)", "May 2026", "text"),
        ("Period End Date", dt.date(2026, 5, 31), "date"),
        ("Tie-Out Tolerance ($)", 1, "currency"),
        ("Reporting Currency", "USD", "text"),
        ("Period Locked in GL?", "No", "yesno"),
    ]
    set_cell(ws, f"B{setup_row+1}", "Field", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    set_cell(ws, f"C{setup_row+1}", "Value", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    ws.merge_cells(f"C{setup_row+1}:D{setup_row+1}")
    ws.row_dimensions[setup_row+1].height = 28

    value_cells = {}
    for i, (label, default, kind) in enumerate(setup_fields):
        r = setup_row + 2 + i
        set_cell(ws, f"B{r}", label, font=FONT_BODY_BOLD, border=BORDER_ALL, align=ALIGN_LEFT)
        cell = set_cell(ws, f"C{r}", default, font=FONT_BODY, fill=FILL_INPUT, border=BORDER_ALL, align=ALIGN_LEFT)
        ws.merge_cells(f"C{r}:D{r}")
        if kind == "date":
            cell.number_format = "yyyy-mm-dd"
        elif kind == "currency":
            cell.number_format = "$#,##0.00"
        value_cells[label] = f"C{r}"
        ws.row_dimensions[r].height = 22

    # Tolerance note beside the field (MEC-7)
    tol_ref = value_cells["Tie-Out Tolerance ($)"]
    set_cell(ws, f"E{tol_ref[1:]}", "A subledger should agree to the GL to the cent. Raise this only for rounding.",
             font=FONT_NOTE, align=ALIGN_LEFT)
    ws.merge_cells(f"E{tol_ref[1:]}:F{tol_ref[1:]}")

    # Yes/No validation on Period Locked
    yn_dv = DataValidation(type="list", formula1=f'"{",".join(YES_NO)}"', allow_blank=False)
    yn_dv.add(value_cells["Period Locked in GL?"])
    ws.add_data_validation(yn_dv)

    # Period End must be a real date (a blank or text date breaks the due dates)
    ped_dv = DataValidation(type="date", operator="greaterThan", formula1="1", allow_blank=True,
                            showErrorMessage=True, errorTitle="Period End Date",
                            error="Enter a date, e.g. 2026-05-31.")
    ped_dv.add(value_cells["Period End Date"])
    ws.add_data_validation(ped_dv)

    # Tolerance must be a non-negative number
    tol_dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=False,
                            showErrorMessage=True, errorTitle="Tie-Out Tolerance",
                            error="Enter a dollar amount of 0 or more.")
    tol_dv.add(tol_ref)
    ws.add_data_validation(tol_dv)

    def absref(label: str) -> str:
        ref = value_cells[label]
        return f"'README & Setup'!${ref[0]}${ref[1:]}"

    # Defined names — these are what the other sheets reference
    add_defined_name(wb, "CompanyName", absref("Company Name"))
    add_defined_name(wb, "FiscalYearEnd", absref("Fiscal Year End (MM-DD)"))
    add_defined_name(wb, "CurrentPeriod", absref("Current Period (e.g., May 2026)"))
    add_defined_name(wb, "PeriodEndDate", absref("Period End Date"))
    add_defined_name(wb, "TieOutTolerance", absref("Tie-Out Tolerance ($)"))
    add_defined_name(wb, "ReportingCurrency", absref("Reporting Currency"))
    add_defined_name(wb, "PeriodLocked", absref("Period Locked in GL?"))

    # Cross-sell (MEC-1, MEC-5): product names and kdeskaccounting.com, no prices.
    cta_row = setup_row + 2 + len(setup_fields) + 2
    set_cell(ws, f"B{cta_row}", "Need more depth?", font=FONT_H2)
    set_cell(ws, f"C{cta_row}", "Our workbooks for the technical schedules. Details at kdeskaccounting.com.",
             font=FONT_NOTE, align=ALIGN_LEFT)
    ws.merge_cells(f"C{cta_row}:F{cta_row}")
    upsells = [
        ("ASC 606 Commission Accrual Workbook", "Capitalize and amortize sales commissions: deal schedule, JE generator, rollforward", "https://kdeskaccounting.com/templates/asc606/"),
        ("ASC 842 Lease Accounting Workbook", "Operating and finance leases: amortization schedule, JE generator, ROU rollforward", "https://kdeskaccounting.com/templates/asc842/"),
        ("Fixed Asset Rollforward Workbook", "Asset register, depreciation schedule, JE generator, rollforward", "https://kdeskaccounting.com/templates/fixed-assets/"),
        ("Amortization Calculator (free, in your browser)", "ASC 842 lease and ASC 606 commission amortization estimates in seconds", "https://kdeskaccounting.com/calculator/"),
    ]
    for i, (name, desc, url) in enumerate(upsells):
        r = cta_row + 1 + i
        set_cell(ws, f"B{r}", name, font=FONT_BODY_BOLD, align=ALIGN_LEFT)
        set_cell(ws, f"C{r}", desc, font=FONT_BODY, align=ALIGN_LEFT)
        ws.merge_cells(f"C{r}:E{r}")
        link_cell = set_cell(ws, f"F{r}", "Open →", font=FONT_LINK, align=ALIGN_CENTER)
        link_cell.hyperlink = url
        ws.row_dimensions[r].height = 30

    # Footer note
    footer_row = cta_row + 2 + len(upsells) + 1
    set_cell(ws, f"B{footer_row}", "Not legal, tax, or audit advice. Use within your firm's policies and your auditor's expectations.", font=FONT_NOTE, align=ALIGN_LEFT)
    ws.merge_cells(f"B{footer_row}:F{footer_row}")


def build_close_calendar(wb: Workbook) -> None:
    ws = wb.create_sheet("Close Calendar")
    set_col_widths(ws, {"A": 4, "B": 6, "C": 32, "D": 56, "E": 22, "F": 14, "G": 16, "H": 32})
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B6"

    # Title band
    ws.merge_cells("B2:H2")
    set_cell(ws, "B2", "Close Calendar", font=Font(name="Calibri", size=18, bold=True, color=COLOR_WHITE),
             fill=FILL_HEADER, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[2].height = 36

    ws.merge_cells("B3:H3")
    set_cell(ws, "B3", '=CONCATENATE("Period: ",CurrentPeriod,"  |  Company: ",CompanyName,"  |  Due dates default to business days after Period End Date (overwrite any)  |  Add tasks anywhere in rows 6-200")',
             font=FONT_NOTE, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[3].height = 20

    start_row = 6
    task_end = start_row + len(TASKS) - 1
    spare_end = task_end + CALENDAR_SPARE_ROWS
    rng_end = CALENDAR_RANGE_END

    # Summary sits ABOVE the table (row 4, frozen) so the list can grow downward (MEC-8)
    set_cell(ws, "C4", "Totals", font=FONT_BODY_BOLD, align=ALIGN_RIGHT)
    D = f"D{start_row}:D{rng_end}"
    G = f"G{start_row}:G{rng_end}"
    set_cell(ws, "D4", f'=CONCATENATE(COUNTA({D}), " tasks total  |  ", COUNTIF({G},"Done"), " done  |  ", COUNTIF({G},"In Progress"), " in progress  |  ", COUNTIF({G},"Blocked"), " blocked  |  ", COUNTIF({G},"N/A"), " N/A")',
             font=FONT_BODY_BOLD, align=ALIGN_LEFT, fill=FILL_SECTION, border=BORDER_ALL)
    ws.merge_cells("D4:H4")
    ws.row_dimensions[4].height = 28

    headers = ["#", "Phase", "Task", "Owner", "Due Date", "Status", "Notes"]
    write_table_header(ws, 5, headers, start_col=2)

    for i, (phase, task, owner) in enumerate(TASKS):
        r = start_row + i
        offset = next(v for k, v in PHASE_DUE_OFFSET.items() if phase.startswith(k + " "))
        status, note = SAMPLE_TASK_STATUS.get(i + 1, ("Not Started", None))
        set_cell(ws, f"B{r}", i + 1, font=FONT_BODY, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"C{r}", phase, font=FONT_BODY, align=ALIGN_LEFT_TOP, border=BORDER_ALL)
        set_cell(ws, f"D{r}", task, font=FONT_BODY, align=ALIGN_LEFT_TOP, border=BORDER_ALL)
        set_cell(ws, f"E{r}", owner, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"F{r}", f'=IF(ISNUMBER(PeriodEndDate),WORKDAY(PeriodEndDate,{offset}),"")', font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL, number_format="yyyy-mm-dd")
        set_cell(ws, f"G{r}", status, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"H{r}", note, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT_TOP, border=BORDER_ALL)
        ws.row_dimensions[r].height = 36

    # Blank rows for the team's own tasks (counted by every summary)
    for r in range(task_end + 1, spare_end + 1):
        set_cell(ws, f"B{r}", f'=IF(D{r}="","",ROW()-{start_row - 1})', font=FONT_BODY, align=ALIGN_CENTER, border=BORDER_ALL)
        for col, align in (("C", ALIGN_LEFT_TOP), ("D", ALIGN_LEFT_TOP), ("E", ALIGN_LEFT), ("F", ALIGN_CENTER), ("G", ALIGN_CENTER), ("H", ALIGN_LEFT_TOP)):
            set_cell(ws, f"{col}{r}", None, font=FONT_BODY, fill=FILL_INPUT, align=align, border=BORDER_ALL,
                     number_format="yyyy-mm-dd" if col == "F" else None)
        ws.row_dimensions[r].height = 28

    status_range = f"G{start_row}:G{rng_end}"
    status_dv = DataValidation(type="list", formula1=f'"{",".join(STATUS_OPTIONS)}"', allow_blank=True)
    status_dv.add(status_range)
    ws.add_data_validation(status_dv)

    ws.conditional_formatting.add(status_range, CellIsRule(operator="equal", formula=['"Done"'], fill=cf_fill(COLOR_GREEN), font=Font(color=COLOR_GREEN_FG, bold=True)))
    ws.conditional_formatting.add(status_range, CellIsRule(operator="equal", formula=['"In Progress"'], fill=cf_fill(COLOR_YELLOW), font=Font(color=COLOR_YELLOW_FG, bold=True)))
    ws.conditional_formatting.add(status_range, CellIsRule(operator="equal", formula=['"Blocked"'], fill=cf_fill(COLOR_RED), font=Font(color=COLOR_RED_FG, bold=True)))
    ws.conditional_formatting.add(status_range, CellIsRule(operator="equal", formula=['"N/A"'], fill=cf_fill(COLOR_GRAY), font=Font(color=COLOR_GRAY_FG, italic=True)))

    # Defined names used by Sign-Off — run to row 200 so added tasks count (MEC-8)
    add_defined_name(wb, "TaskStatus", f"'Close Calendar'!$G${start_row}:$G${rng_end}")
    add_defined_name(wb, "TaskList", f"'Close Calendar'!$D${start_row}:$D${rng_end}")

    # Rows past the formatted spare rows are still counted; number them too (N-7).
    # The "add tasks" hint lives in the row-3 subtitle and the README, not in the range.
    for r in range(spare_end + 1, rng_end + 1):
        ws[f"B{r}"] = f'=IF(D{r}="","",ROW()-{start_row - 1})'
        ws[f"B{r}"].font = FONT_BODY
        ws[f"B{r}"].alignment = ALIGN_CENTER


def build_reconciliations(wb: Workbook) -> None:
    ws = wb.create_sheet("Reconciliations")
    set_col_widths(ws, {"A": 4, "B": 6, "C": 34, "D": 34, "E": 18, "F": 18, "G": 16, "H": 16, "I": 16, "J": 18, "K": 18, "L": 40})
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B6"

    ws.merge_cells("B2:L2")
    set_cell(ws, "B2", "Reconciliations (Subledger → GL Tie-Out)", font=Font(name="Calibri", size=18, bold=True, color=COLOR_WHITE),
             fill=FILL_HEADER, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[2].height = 36

    ws.merge_cells("B3:L3")
    set_cell(ws, "B3", '=CONCATENATE("Period: ",CurrentPeriod,"  |  Currency: ",ReportingCurrency,"  |  Tie-out tolerance: ",TEXT(TieOutTolerance,"#,##0.00"),"  |  OK or FLAG once both balances are entered; INCOMPLETE if only one is")',
             font=FONT_NOTE, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[3].height = 20

    headers = ["#", "Account", "Source / Schedule", "GL Balance", "Sub/Schedule Balance",
               "Variance", "Within Tolerance?", "Status", "Preparer", "Reviewer", "Notes"]
    write_table_header(ws, 5, headers, start_col=2)

    start_row = 6
    for i, (account, source) in enumerate(RECONCILIATIONS):
        r = start_row + i
        gl, sub, status, note = SAMPLE_RECS.get(i + 1, (None, None, "Not Started", None))
        done_by = ("Staff Acct.", "Controller") if status == "Done" else (("Staff Acct.", None) if status == "In Progress" else (None, None))
        set_cell(ws, f"B{r}", i + 1, font=FONT_BODY, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"C{r}", account, font=FONT_BODY, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"D{r}", source, font=FONT_BODY, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"E{r}", gl, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_RIGHT, border=BORDER_ALL, number_format=CURRENCY_FMT)
        set_cell(ws, f"F{r}", sub, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_RIGHT, border=BORDER_ALL, number_format=CURRENCY_FMT)
        # Blank until both balances are entered, so an untouched row is not "OK" (MEC-3)
        set_cell(ws, f"G{r}", f'=IF(COUNT(E{r}:F{r})<2,"",ROUND(E{r}-F{r},2))', font=FONT_BODY_BOLD, align=ALIGN_RIGHT, border=BORDER_ALL, number_format=CURRENCY_FMT)
        set_cell(ws, f"H{r}", f'=IF(COUNT(E{r}:F{r})=0,"",IF(COUNT(E{r}:F{r})=1,"INCOMPLETE",IF(ABS(G{r})<=TieOutTolerance,"OK","FLAG")))', font=FONT_BODY_BOLD, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"I{r}", status, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"J{r}", done_by[0], font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"K{r}", done_by[1], font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"L{r}", note, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT_TOP, border=BORDER_ALL)
        ws.row_dimensions[r].height = 26

    end_row = start_row + len(RECONCILIATIONS) - 1

    status_dv = DataValidation(type="list", formula1=f'"{",".join(STATUS_OPTIONS)}"', allow_blank=False)
    status_dv.add(f"I{start_row}:I{end_row}")
    ws.add_data_validation(status_dv)

    flag_range = f"H{start_row}:H{end_row}"
    ws.conditional_formatting.add(flag_range, CellIsRule(operator="equal", formula=['"OK"'], fill=cf_fill(COLOR_GREEN), font=Font(color=COLOR_GREEN_FG, bold=True)))
    ws.conditional_formatting.add(flag_range, CellIsRule(operator="equal", formula=['"FLAG"'], fill=cf_fill(COLOR_RED), font=Font(color=COLOR_RED_FG, bold=True)))
    ws.conditional_formatting.add(flag_range, CellIsRule(operator="equal", formula=['"INCOMPLETE"'], fill=cf_fill(COLOR_YELLOW), font=Font(color=COLOR_YELLOW_FG, bold=True)))

    rec_status_range = f"I{start_row}:I{end_row}"
    ws.conditional_formatting.add(rec_status_range, CellIsRule(operator="equal", formula=['"Done"'], fill=cf_fill(COLOR_GREEN), font=Font(color=COLOR_GREEN_FG, bold=True)))
    ws.conditional_formatting.add(rec_status_range, CellIsRule(operator="equal", formula=['"In Progress"'], fill=cf_fill(COLOR_YELLOW), font=Font(color=COLOR_YELLOW_FG, bold=True)))
    ws.conditional_formatting.add(rec_status_range, CellIsRule(operator="equal", formula=['"Blocked"'], fill=cf_fill(COLOR_RED), font=Font(color=COLOR_RED_FG, bold=True)))
    ws.conditional_formatting.add(rec_status_range, CellIsRule(operator="equal", formula=['"N/A"'], fill=cf_fill(COLOR_GRAY), font=Font(color=COLOR_GRAY_FG, italic=True)))

    add_defined_name(wb, "RecFlags", f"Reconciliations!$H${start_row}:$H${end_row}")
    add_defined_name(wb, "RecVariance", f"Reconciliations!$G${start_row}:$G${end_row}")
    add_defined_name(wb, "RecStatus", f"Reconciliations!$I${start_row}:$I${end_row}")

    sum_row = end_row + 2
    set_cell(ws, f"C{sum_row}", "Totals", font=FONT_BODY_BOLD, align=ALIGN_RIGHT)
    set_cell(ws, f"D{sum_row}", "GL Total", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION)
    set_cell(ws, f"E{sum_row}", f"=SUM(E{start_row}:E{end_row})", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL, number_format=CURRENCY_FMT)
    set_cell(ws, f"F{sum_row}", f"=SUM(F{start_row}:F{end_row})", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL, number_format=CURRENCY_FMT)
    set_cell(ws, f"G{sum_row}", f"=SUM(G{start_row}:G{end_row})", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL, number_format=CURRENCY_FMT)
    flags = f'COUNTIF(H{start_row}:H{end_row},"FLAG")'
    set_cell(ws, f"H{sum_row}", f'={flags}&IF({flags}=1," flag"," flags")', font=FONT_BODY_BOLD, align=ALIGN_CENTER, fill=FILL_SECTION, border=BORDER_ALL)
    ws.row_dimensions[sum_row].height = 28


def build_je_tracker(wb: Workbook) -> None:
    ws = wb.create_sheet("JE Tracker")
    set_col_widths(ws, {"A": 4, "B": 6, "C": 14, "D": 12, "E": 32, "F": 30, "G": 16, "H": 16, "I": 24, "J": 16, "K": 16, "L": 14, "M": 18})
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B6"

    ws.merge_cells("B2:M2")
    set_cell(ws, "B2", "Journal Entry Tracker", font=Font(name="Calibri", size=18, bold=True, color=COLOR_WHITE),
             fill=FILL_HEADER, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[2].height = 36

    ws.merge_cells("B3:M3")
    set_cell(ws, "B3", '=CONCATENATE("Period: ",CurrentPeriod,"  |  One row per JE line; give every line of an entry the same JE #. Entry Check tests each JE # on its own.")',
             font=FONT_NOTE, align=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[3].height = 20

    headers = ["#", "Date", "JE #", "Description", "Account", "Debit", "Credit", "Source", "Preparer", "Reviewer", "Status", "Entry Check"]
    write_table_header(ws, 5, headers, start_col=2)

    start_row = 6
    rows = 50
    end_row = start_row + rows - 1
    D = f"$D${start_row}:$D${end_row}"
    Gr = f"$G${start_row}:$G${end_row}"
    Hr = f"$H${start_row}:$H${end_row}"

    for r in range(start_row, end_row + 1):
        k = r - start_row
        sample = SAMPLE_JES[k] if k < len(SAMPLE_JES) else None
        if sample:
            off, je, desc, acct, dr, cr, src, st = sample
            date = dt.date(2026, 5, 31) + dt.timedelta(days=off)
            prep, rev = "Staff Acct.", ("Controller" if st == "Posted" else None)
        else:
            date = je = desc = acct = dr = cr = src = st = prep = rev = None
        set_cell(ws, f"B{r}", k + 1, font=FONT_BODY, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"C{r}", date, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL, number_format="yyyy-mm-dd")
        set_cell(ws, f"D{r}", je, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"E{r}", desc, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"F{r}", acct, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"G{r}", dr, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_RIGHT, border=BORDER_ALL, number_format=CURRENCY_FMT)
        set_cell(ws, f"H{r}", cr, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_RIGHT, border=BORDER_ALL, number_format=CURRENCY_FMT)
        set_cell(ws, f"I{r}", src, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"J{r}", prep, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"K{r}", rev, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"L{r}", st, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL)
        # Per-entry debit = credit (MEC-9): two offsetting one-sided entries no longer pass
        set_cell(ws, f"M{r}",
                 f'=IF(AND(D{r}="",COUNT(G{r}:H{r})=0),"",IF(D{r}="","No JE #",'
                 f'IF(ROUND(SUMPRODUCT(--EXACT({D},D{r}),{Gr})-SUMPRODUCT(--EXACT({D},D{r}),{Hr}),2)=0,"OK","Out of balance")))',
                 font=FONT_BODY_BOLD, align=ALIGN_CENTER, border=BORDER_ALL)
        ws.row_dimensions[r].height = 22

    source_dv = DataValidation(type="list", formula1=f'"{",".join(JE_SOURCE_OPTIONS)}"', allow_blank=True)
    source_dv.add(f"I{start_row}:I{end_row}")
    ws.add_data_validation(source_dv)

    je_status_dv = DataValidation(type="list", formula1='"Pending,Posted,Reversed,Voided"', allow_blank=True)
    je_status_dv.add(f"L{start_row}:L{end_row}")
    ws.add_data_validation(je_status_dv)

    je_status_range = f"L{start_row}:L{end_row}"
    ws.conditional_formatting.add(je_status_range, CellIsRule(operator="equal", formula=['"Posted"'], fill=cf_fill(COLOR_GREEN), font=Font(color=COLOR_GREEN_FG, bold=True)))
    ws.conditional_formatting.add(je_status_range, CellIsRule(operator="equal", formula=['"Pending"'], fill=cf_fill(COLOR_YELLOW), font=Font(color=COLOR_YELLOW_FG, bold=True)))
    ws.conditional_formatting.add(je_status_range, CellIsRule(operator="equal", formula=['"Reversed"'], fill=cf_fill(COLOR_GRAY), font=Font(color=COLOR_GRAY_FG, italic=True)))
    ws.conditional_formatting.add(je_status_range, CellIsRule(operator="equal", formula=['"Voided"'], fill=cf_fill(COLOR_GRAY), font=Font(color=COLOR_GRAY_FG, italic=True)))

    check_range = f"M{start_row}:M{end_row}"
    ws.conditional_formatting.add(check_range, CellIsRule(operator="equal", formula=['"OK"'], fill=cf_fill(COLOR_GREEN), font=Font(color=COLOR_GREEN_FG, bold=True)))
    ws.conditional_formatting.add(check_range, CellIsRule(operator="equal", formula=['"Out of balance"'], fill=cf_fill(COLOR_RED), font=Font(color=COLOR_RED_FG, bold=True)))
    ws.conditional_formatting.add(check_range, CellIsRule(operator="equal", formula=['"No JE #"'], fill=cf_fill(COLOR_RED), font=Font(color=COLOR_RED_FG, bold=True)))

    sum_row = end_row + 2
    set_cell(ws, f"E{sum_row}", "Sanity Check:", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL)
    set_cell(ws, f"F{sum_row}", "Sum of Debits / Credits / Difference", font=FONT_NOTE, align=ALIGN_LEFT, fill=FILL_SECTION, border=BORDER_ALL)
    set_cell(ws, f"G{sum_row}", f"=SUM(G{start_row}:G{end_row})", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL, number_format=CURRENCY_FMT)
    set_cell(ws, f"H{sum_row}", f"=SUM(H{start_row}:H{end_row})", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL, number_format=CURRENCY_FMT)
    set_cell(ws, f"I{sum_row}", f"=G{sum_row}-H{sum_row}", font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL, number_format=CURRENCY_FMT)

    flag_row = sum_row + 1
    bad = f'COUNTIF(M{start_row}:M{end_row},"Out of balance")+COUNTIF(M{start_row}:M{end_row},"No JE #")'
    has = f'COUNT(G{start_row}:H{end_row})>0'
    ok_expr = f'AND(ROUND(I{sum_row},2)=0,{bad}=0)'
    set_cell(ws, f"E{flag_row}", "Balanced?", font=FONT_BODY_BOLD, align=ALIGN_RIGHT)
    set_cell(ws, f"F{flag_row}", f'=IF(NOT({has}),"No entries yet",IF({ok_expr},"✓ Debits = Credits","✗ OUT OF BALANCE"))', font=FONT_BODY_BOLD, align=ALIGN_LEFT, border=BORDER_ALL)
    bal_cell = f"F{flag_row}"
    # Empty log: no colour (N-1)
    ws.conditional_formatting.add(bal_cell, FormulaRule(formula=[f'AND({has},{ok_expr})'], fill=cf_fill(COLOR_GREEN), font=Font(color=COLOR_GREEN_FG, bold=True)))
    ws.conditional_formatting.add(bal_cell, FormulaRule(formula=[f'AND({has},NOT({ok_expr}))'], fill=cf_fill(COLOR_RED), font=Font(color=COLOR_RED_FG, bold=True)))
    ws.row_dimensions[sum_row].height = 28
    ws.row_dimensions[flag_row].height = 24

    add_defined_name(wb, "JENum", f"'JE Tracker'!$D${start_row}:$D${end_row}")
    add_defined_name(wb, "JEStatus", f"'JE Tracker'!$L${start_row}:$L${end_row}")
    add_defined_name(wb, "JECheck", f"'JE Tracker'!$M${start_row}:$M${end_row}")
    add_defined_name(wb, "JEAmounts", f"'JE Tracker'!$G${start_row}:$H${end_row}")
    add_defined_name(wb, "JEDebitTotal", f"'JE Tracker'!$G${sum_row}")
    add_defined_name(wb, "JECreditTotal", f"'JE Tracker'!$H${sum_row}")
    add_defined_name(wb, "JEDifference", f"'JE Tracker'!$I${sum_row}")


def build_signoff(wb: Workbook) -> None:
    ws = wb.create_sheet("Sign-Off")
    set_col_widths(ws, {"A": 4, "B": 30, "C": 26, "D": 26, "E": 26, "F": 26})
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True

    ws.merge_cells("B2:F2")
    set_cell(ws, "B2", "Month-End Close Sign-Off", font=Font(name="Calibri", size=20, bold=True, color=COLOR_WHITE),
             fill=FILL_HEADER, align=Alignment(horizontal="center", vertical="center"))
    ws.row_dimensions[2].height = 44

    ws.merge_cells("B3:F3")
    set_cell(ws, "B3", '=CONCATENATE(CompanyName,"  |  Period: ",CurrentPeriod,"  |  Period End: ",IF(ISNUMBER(PeriodEndDate),TEXT(PeriodEndDate,"yyyy-mm-dd"),"(not set)"),"  |  FYE ",FiscalYearEnd,"  |  ",ReportingCurrency)',
             font=FONT_H2, align=ALIGN_CENTER)
    ws.row_dimensions[3].height = 28

    set_cell(ws, "B5", "Close Metrics", font=FONT_H2)
    metrics = [
        ("Tasks total",            "=COUNTA(TaskList)"),
        ("Tasks completed",        '=COUNTIF(TaskStatus,"Done")'),
        ("Tasks in progress",      '=COUNTIF(TaskStatus,"In Progress")'),
        ("Tasks blocked",          '=COUNTIF(TaskStatus,"Blocked")'),
        ("Tasks N/A",              '=COUNTIF(TaskStatus,"N/A")'),
        ("Reconciliation flags",   '=COUNTIF(RecFlags,"FLAG")'),
        ("Reconciliations done",   '=COUNTIF(RecStatus,"Done")'),
        # Distinct JE # with at least one Posted line (N-2). Pure SUMPRODUCT/COUNTIFS, no IF.
        ("JE entries posted",      '=SUMPRODUCT((JEStatus="Posted")*(JENum<>"")/(COUNTIFS(JENum,JENum,JEStatus,"Posted")+(JEStatus<>"Posted")+(JENum="")))'),
        ("JE lines failing Entry Check", '=COUNTIF(JECheck,"Out of balance")+COUNTIF(JECheck,"No JE #")'),
        ("JE debit = credit?",     '=IF(COUNT(JEAmounts)=0,"No entries yet",IF(AND(ROUND(JEDifference,2)=0,COUNTIF(JECheck,"Out of balance")+COUNTIF(JECheck,"No JE #")=0),"Yes","No — investigate"))'),
    ]
    for i, (label, formula) in enumerate(metrics):
        r = 6 + i
        set_cell(ws, f"B{r}", label, font=FONT_BODY_BOLD, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"C{r}", formula, font=FONT_BODY_BOLD, align=ALIGN_RIGHT, fill=FILL_SECTION, border=BORDER_ALL)
        ws.merge_cells(f"C{r}:D{r}")
        ws.row_dimensions[r].height = 22

    gate_row = 6 + len(metrics) + 1
    set_cell(ws, f"B{gate_row}", "Period Locked in GL?", font=FONT_BODY_BOLD, align=ALIGN_LEFT, border=BORDER_ALL)
    set_cell(ws, f"C{gate_row}", '=IF(PeriodLocked="","",PeriodLocked)', font=FONT_BODY_BOLD, align=ALIGN_CENTER, fill=FILL_SECTION, border=BORDER_ALL)
    ws.merge_cells(f"C{gate_row}:D{gate_row}")
    set_cell(ws, f"E{gate_row}", "Set on README & Setup", font=FONT_NOTE, align=ALIGN_LEFT)

    fs_row = gate_row + 1
    set_cell(ws, f"B{fs_row}", "Financial statements attached?", font=FONT_BODY_BOLD, align=ALIGN_LEFT, border=BORDER_ALL)
    set_cell(ws, f"C{fs_row}", "No", font=FONT_BODY_BOLD, align=ALIGN_CENTER, fill=FILL_INPUT, border=BORDER_ALL)
    ws.merge_cells(f"C{fs_row}:D{fs_row}")

    pkg_row = fs_row + 1
    set_cell(ws, f"B{pkg_row}", "Close package distributed?", font=FONT_BODY_BOLD, align=ALIGN_LEFT, border=BORDER_ALL)
    set_cell(ws, f"C{pkg_row}", "No", font=FONT_BODY_BOLD, align=ALIGN_CENTER, fill=FILL_INPUT, border=BORDER_ALL)
    ws.merge_cells(f"C{pkg_row}:D{pkg_row}")

    yn_dv = DataValidation(type="list", formula1=f'"{",".join(YES_NO)}"', allow_blank=False)
    yn_dv.add(f"C{fs_row}")
    yn_dv.add(f"C{pkg_row}")
    ws.add_data_validation(yn_dv)

    excp_row = pkg_row + 2
    set_cell(ws, f"B{excp_row}", "Exception List (unresolved items, post-close follow-ups)", font=FONT_H2)
    for i in range(6):
        r = excp_row + 1 + i
        set_cell(ws, f"B{r}", i + 1, font=FONT_BODY, align=ALIGN_CENTER, border=BORDER_ALL)
        set_cell(ws, f"C{r}", None, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        ws.merge_cells(f"C{r}:F{r}")
        ws.row_dimensions[r].height = 22

    sig_row = excp_row + 1 + 6 + 2
    set_cell(ws, f"B{sig_row}", "Signatures", font=FONT_H2)

    sig_header_row = sig_row + 1
    write_table_header(ws, sig_header_row, ["Role", "Name", "Date", "Signature"], start_col=2)
    ws.merge_cells(f"E{sig_header_row}:F{sig_header_row}")

    sig_roles = ["Preparer", "Reviewer", "Controller / CFO"]
    for i, role in enumerate(sig_roles):
        r = sig_header_row + 1 + i
        set_cell(ws, f"B{r}", role, font=FONT_BODY_BOLD, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"C{r}", None, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        set_cell(ws, f"D{r}", None, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_CENTER, border=BORDER_ALL, number_format="yyyy-mm-dd")
        set_cell(ws, f"E{r}", None, font=FONT_BODY, fill=FILL_INPUT, align=ALIGN_LEFT, border=BORDER_ALL)
        ws.merge_cells(f"E{r}:F{r}")
        ws.row_dimensions[r].height = 32

    footer_row = sig_header_row + 1 + len(sig_roles) + 2
    set_cell(ws, f"B{footer_row}",
             "Not legal, tax, or audit advice. Use within your firm's policies and your auditor's expectations.  •  kdeskaccounting.com",
             font=FONT_NOTE, align=ALIGN_CENTER)
    ws.merge_cells(f"B{footer_row}:F{footer_row}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_workbook(out_path: pathlib.Path) -> None:
    wb = Workbook()
    build_readme_setup(wb)
    build_close_calendar(wb)
    build_reconciliations(wb)
    build_je_tracker(wb)
    build_signoff(wb)

    wb.active = 0
    # MEC-9: file metadata
    wb.properties.creator = "KDesk Accounting"
    wb.properties.lastModifiedBy = "KDesk Accounting"
    wb.properties.title = "Month-End Close Checklist + Tie-Out Workbook v1.1"
    wb.properties.created = dt.datetime(2026, 11, 24, 12, 0, 0)
    wb.properties.modified = dt.datetime(2026, 11, 24, 12, 0, 0)
    # Excel recalculates on open (LibreOffice too) — the file ships formulas without cached values
    wb.calculation.fullCalcOnLoad = True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    _neutral_app_xml(out_path)


def _neutral_app_xml(path: pathlib.Path) -> None:
    """openpyxl hard-codes docProps/app.xml as "Microsoft Excel Compatible / Openpyxl"; replace it."""
    import zipfile
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
           '<Application>KDesk Accounting</Application><Company>KDesk Accounting</Company></Properties>')
    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = app.encode() if item.filename == "docProps/app.xml" else zin.read(item.filename)
            zout.writestr(item, data)
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(DIST / "month-end-close-checklist-v1.1.xlsx"))
    args = ap.parse_args()

    out = pathlib.Path(args.output)
    build_workbook(out)
    print(f"Wrote {out}  ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
