---
title: "Month-End Close Checklist + Tie-Out Workbook (Free Excel Template)"
description: "Free Excel workbook for SaaS controllers: 42-task close calendar across 5 phases, 18 subledger-to-GL reconciliations with materiality flag, 50-row JE tracker with debit=credit sanity check, and a printable sign-off page that auto-tabulates close metrics. Built by a CPA. No macros."
summary: "A free 5-tab Excel workbook that holds your entire month-end close in one place — 42 pre-populated tasks, 18 standard subledger reconciliations, JE log with sanity check, and printable sign-off with auto-tabulated close metrics."
date: 2026-05-26
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 5
price: 0
buy_url: "https://kdeskaccounting.gumroad.com/l/month-end-close-checklist"
free_url: "https://kdeskaccounting.gumroad.com/l/month-end-close-checklist"
free_label: "Download — Free"
tags: ["month-end close", "controller", "reconciliation", "Excel template", "close checklist", "tie-out", "journal entries"]
faq:
  - q: "Is this actually free?"
    a: "Yes. The Gumroad listing is Pay What You Want with a $0 minimum. The suggested price is $5 — if the workbook saves you time, that's appreciated, but you can download for free."
  - q: "Does it work on a Mac?"
    a: "Yes. Pure Excel formulas — no VBA macros, no Windows-only features, no dynamic-array spills. Works on Excel 2016, Excel 365, and Excel for Mac."
  - q: "Why is this free when your other workbooks are paid?"
    a: "This workbook is structural — it holds your close together but does not compute the technical accounting schedules. Our paid workbooks (ASC 606 Commission Accrual at $79, ASC 842 Lease Accounting at $97, Fixed Asset Rollforward at $79) handle the math-heavy areas that take controllers the longest. The free Close Checklist is the scaffolding; the paid workbooks are the engines."
  - q: "Can I customize the pre-populated task list?"
    a: "Yes. The 42 tasks are starter content drawn from a typical SaaS controller's close. Add rows for tasks specific to your company (board reporting, KPI calculations, cap-table updates), delete rows that don't apply, change Owner/Due Date for your team. The Sign-Off summary counts whatever's in the Calendar."
  - q: "How does the materiality flag on Reconciliations work?"
    a: "You set a Performance Materiality dollar amount on the Setup tab (default $50,000). Each reconciliation calculates Variance = GL minus Subledger, then the 'Within Materiality?' column shows 'OK' (green) when ABS(Variance) is at or below your threshold, or 'FLAG' (red) when it exceeds it. The Sign-Off page counts total flags so you see at a glance if any tie-out needs investigation."
  - q: "What's the JE Tracker for?"
    a: "It's a log of every journal entry posted during the close — Date, JE Number, Description, Account, Debit, Credit, Source (Manual / KDesk workbook / GL system / Other), Preparer, Reviewer, Status. The Source dropdown helps you track entries that came from your scheduled workbooks (FA depreciation, ASC 606 amortization, ASC 842 monthly entries) separately from manual adjustments. The sanity check at the bottom catches any one-sided entry — Sum(Debits) must equal Sum(Credits)."
  - q: "Can I share this with my team?"
    a: "Yes — free for individual and team use within your company. Multiple accountants can work the same file (one prepares, one reviews) or each team member can hold their own copy with their assigned tasks. Please don't redistribute or resell — share the kdeskaccounting.com link with colleagues instead."
  - q: "Does this replace FloQast / BlackLine / Numeric?"
    a: "No. Close-management software gives you workflow, access controls, real-time multi-user collaboration, integration to your GL, evidence storage, and SOX-compliant audit trails. This workbook does none of that — it's an Excel file. If you're an early-stage SaaS company without a software budget for close management, this is a solid stopgap. If you're growing past 25-30 reconciliations or have SOX requirements, evaluate the dedicated tools."
---

A complete month-end close workbook in five tabs — free. Built by a CPA who has run SaaS close cycles at multiple companies and got tired of rebuilding the same checklist in Notion / Google Docs / Smartsheet every time. **Free. Pay What You Want on Gumroad.**

[Download the Workbook (Free) →](https://kdeskaccounting.gumroad.com/l/month-end-close-checklist)

This is the scaffolding that holds your close together. The technical schedules (commissions, leases, fixed assets) belong in dedicated workbooks — links at the bottom — but the close itself runs on a checklist, a reconciliation set, a JE log, and a sign-off. That's what this workbook is.

---

## What's in the Workbook

Five tabs. You enter data on Setup, Close Calendar, Reconciliations, and JE Tracker; the Sign-Off page auto-summarizes everything.

### README + Setup

The first tab. Six-step quickstart and the inputs that drive everything else: Company Name, Current Period, Fiscal Year End, Performance Materiality threshold, Reporting Currency, Period Locked status. Yellow cells are your inputs; every other tab reads from these via defined names.

### Close Calendar

**42 pre-populated tasks across 5 phases:**

- **Day 1-2 — Cutoff & Data Collection** (12 tasks) — revenue cutoff, AP cutoff, payroll accruals, bank/CC reconciliation
- **Day 2-3 — Subledger Reconciliations** (10 tasks) — AR aging, AP aging, fixed asset additions/disposals, depreciation run
- **Day 3-4 — Technical Accounting Schedules** (10 tasks) — deferred commissions (ASC 606), lease accounting (ASC 842), prepaid amortization, accrued liabilities
- **Day 4-5 — Equity, Tax & Other** (4 tasks) — stock comp, tax provision, FX revaluation, intercompany
- **Day 5+ — Statements & Review** (6 tasks) — trial balance, financial statements, flux analysis, management review, period lock, close package

Each task has Owner, Due Date, Status (Not Started / In Progress / Done / Blocked / N/A), and Notes. Status dropdown drives conditional formatting — completed tasks turn green, blocked turn red, in-progress turn yellow, N/A grays out. The footer summary tells you at a glance: "32 tasks total | 28 done | 2 in progress | 1 blocked | 1 N/A."

Add or delete rows for your team. The Sign-Off summary counts whatever's in the Calendar.

### Reconciliations (Subledger → GL Tie-Out)

**18 standard reconciliations** pre-populated. For each one:

- **Account** — the line on your balance sheet
- **Source / Schedule** — where the supporting balance comes from (subledger, schedule, workbook, statement)
- **GL Balance** — what your GL says (input)
- **Sub / Schedule Balance** — what the supporting workpaper says (input)
- **Variance** — GL minus Sub (formula)
- **Within Materiality?** — "OK" (green) if ABS(Variance) ≤ your Setup materiality threshold, "FLAG" (red) if above
- **Status** — Not Started / In Progress / Done / Blocked / N/A
- **Preparer / Reviewer / Notes** — sign-off and documentation

The 18 pre-populated accounts cover the standard balance sheet:

| Asset side | Liability + Equity side |
|---|---|
| Cash — Operating Account | Accounts Payable |
| Cash — Money Market / Savings | Accrued Liabilities |
| Accounts Receivable | Accrued Payroll & Benefits |
| Allowance for Doubtful Accounts | Lease Liability — Operating |
| Prepaid Expenses | Lease Liability — Finance |
| Deferred Commissions (ASC 606) | Deferred Revenue |
| Fixed Assets — Cost | Common Stock & APIC |
| Accumulated Depreciation | Retained Earnings |
| ROU Asset — Operating Leases | |
| ROU Asset — Finance Leases | |

Footer row sums total GL, total Sub, total Variance, and FLAG count.

### JE Tracker

**50-row journal entry log.** Columns: Date, JE Number, Description, Account, Debit, Credit, Source (dropdown: Manual / FA Workbook / ASC 606 Workbook / ASC 842 Workbook / GL System Auto / Other), Preparer, Reviewer, Status (Pending / Posted / Reversed / Voided).

Two safeguards at the bottom:
1. **Sum of Debits** vs **Sum of Credits** vs **Difference** — three running totals so you see your aggregate exposure
2. **"Balanced?" flag** — formula evaluates `IF(ROUND(Difference,2)=0, "✓ Debits = Credits", "✗ OUT OF BALANCE")`. Conditional formatting turns the cell green when balanced, red when not. A one-sided JE shows up immediately.

The Source dropdown lets you track which workbook produced which entry — useful if you're using our paid ASC 606 / ASC 842 / FA workbooks and want to keep their auto-generated entries separate from manual adjustments.

### Sign-Off

**Printable certification page.** Header shows Company, Period, Period End Date — all pulled from Setup. Then 9 close metrics that auto-tabulate from the other tabs:

- Tasks total / completed / in progress / blocked / N/A
- Reconciliation flags (count of FLAGs)
- Reconciliations done (count of Done status)
- JE entries posted (count of Posted status)
- JE debit = credit? (Yes / No — investigate)

Plus three close gates: Period Locked in GL? • Financial statements attached? • Close package distributed? — each a Yes/No/N/A dropdown.

Then an exception list (6 rows for unresolved items, post-close follow-ups), and a signature block for Preparer, Reviewer, and Controller / CFO with Name, Date, Signature columns.

Set up for portrait fit-to-page printing. Print it, sign it, file it.

---

## How a Typical Close Runs With This Workbook

**Day -1 (last business day of the month):** Open the file. Update Current Period on Setup. Skim the Close Calendar — assign Owner and Due Date for each task to the right person on your team.

**Day 1-3:** Your team works through Day 1-3 tasks. Each person updates their Status column as they go. Blocked items go red — visible in the Sunday status meeting.

**Day 3-4:** Technical accountants work the ASC 606 / ASC 842 / FA schedules (in those workbooks if you have them). As JEs get posted, log them in the JE Tracker. The Source dropdown distinguishes workbook-generated entries from manual ones. Sanity check stays green.

**Day 4-5:** Once all subledger JEs are posted, run Reconciliations. Pull GL balance from your accounting system; pull Sub/Schedule balance from each supporting workpaper. The FLAG column tells you where to investigate.

**Day 5-6:** Controller reviews. Open Sign-Off — the metrics show the state of the close at a glance. Address any blockers and flags. Get sign-offs. Lock the period.

---

## What This Workbook Is Not

A close-management software replacement. If your company is past 25-30 reconciliations, has SOX requirements, needs real-time multi-user collaboration, or wants evidence storage tied to each task — evaluate FloQast, BlackLine, or Numeric. This is an Excel file. It doesn't have access controls, audit trails, or workflow.

A technical-accounting computation tool. It does not amortize commissions, generate lease schedules, or run depreciation. Those live in the dedicated workbooks linked below.

Multi-entity. The Setup is single-company. Multi-entity consolidation, intercompany eliminations, and FX revaluation are out of scope.

---

## The Three Paid Workbooks This One Holds Together

If you're tired of rebuilding the technical schedules from scratch each month:

| Workbook | What it does | Price |
|---|---|---|
| **[ASC 606 Commission Accrual Workbook](/templates/asc606/)** | Capitalizes and amortizes sales commissions under ASC 340-40. 50 deals, three amortization methods, JE generator, rollforward, reconciliation. | $79 |
| **[ASC 842 Lease Accounting Workbook](/templates/asc842/)** | ROU asset, lease liability, amortization schedule for operating + finance leases. 20 leases, six-category JE generator. | $97 |
| **[Fixed Asset Rollforward Workbook](/templates/fixed-assets/)** | 50 capitalized assets, four depreciation methods, JE generator with GL system presets, five-way reconciliation. | $79 |

Or run them all on a free browser-based estimate first: **[Free Amortization Calculator →](/calculator/)**

---

## Get the Workbook

[**Download the Workbook (Free) →**](https://kdeskaccounting.gumroad.com/l/month-end-close-checklist)

Pay What You Want on Gumroad. $0 minimum. $5 suggested if it saves you time.

---

## Related reading

- **[Month-End Close Checklist for Controllers (full guide)](/posts/month-end-close-checklist-controllers/)** — the long-form version of the workbook's task list, with technical accounting context for each phase
