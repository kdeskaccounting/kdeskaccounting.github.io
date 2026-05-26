# Gumroad listing copy — Month-End Close Checklist + Tie-Out Workbook

**Paste into Gumroad product editor. Single FREE listing (PWYW $0, suggested $5).**

---

## Free PWYW listing

**Product title:**
```
Month-End Close Checklist + Tie-Out Workbook (Excel)
```

**Tagline / short description (Gumroad subheading, ~140 chars):**
```
Free Excel workbook for SaaS controllers: 42-task close calendar, 18-row subledger tie-out, JE tracker, printable sign-off. PWYW.
```

**Cover image alt text:**
```
Screenshot of the Month-End Close Checklist Workbook showing the Close Calendar tab with color-coded status flags and the Reconciliations tab
```

**Pricing:**
```
Pay what you want
Suggested: $5
Minimum: $0 (free)
```

**Full description (renders as Markdown on Gumroad product page):**

```
A complete month-end close workbook for SaaS controllers and accounting managers — free. Five tabs, 42 pre-populated tasks, 18 standard subledger reconciliations, a 50-row journal entry log with debit=credit sanity check, and a printable sign-off page.

If you maintain your close in scattered email threads, a Google Doc, or a personal checklist that lives in someone's head — this gives you a single workbook that holds the whole close.

## What's in the workbook

### Tab 1 — README + Setup
Six-step quickstart. Set your company name, current period, fiscal year end, performance materiality threshold, reporting currency, and period-lock status. Every downstream tab reads from these inputs.

### Tab 2 — Close Calendar
**42 pre-populated tasks across 5 phases** (Day 1-2 cutoff, Day 2-3 subledger reconciliations, Day 3-4 technical accounting schedules, Day 4-5 equity/tax/other, Day 5+ statements & review). Each task has Owner, Due Date, Status (Not Started / In Progress / Done / Blocked / N/A), and Notes columns. Status dropdown drives conditional formatting — green when done, red when blocked. Add or delete rows for your team.

### Tab 3 — Reconciliations (Tie-Out)
**18 standard subledger-to-GL reconciliations** pre-populated: Cash, AR, Allowance for Doubtful Accounts, Prepaids, Deferred Commissions, Fixed Assets, Accumulated Depreciation, ROU Assets (operating + finance), AP, Accrued Liabilities, Accrued Payroll, Lease Liabilities, Deferred Revenue, Common Stock & APIC, Retained Earnings. Variance = GL minus Subledger. The "Within Materiality?" column auto-flags variances above your Setup threshold. Preparer/Reviewer/Status fields for documentation.

### Tab 4 — JE Tracker
**50-row journal entry log** with Date, JE Number, Description, Account, Debit, Credit, Source, Preparer, Reviewer, Status. Sanity check at the bottom: Sum of Debits minus Sum of Credits, with a "Balanced?" formula that flips green when zero and red when one-sided.

### Tab 5 — Sign-Off
**Printable certification page** with company/period header and 9 close metrics that auto-tabulate from the other tabs:
- Tasks total / completed / in progress / blocked / N/A
- Reconciliation flags
- Reconciliations done
- JE entries posted
- JE debit = credit?

Plus exception list (6 rows), period-lock indicator, financial-statements-attached and close-package-distributed flags, and a signature block for Preparer, Reviewer, and Controller/CFO.

## Why this is free

This is a lead magnet. We sell three deeper Excel workbooks for the technical schedules that take the longest at close:

- [ASC 606 Commission Accrual Workbook](https://kdeskaccounting.gumroad.com/l/mwmwpe) — $79
- [ASC 842 Lease Accounting Workbook](https://kdeskaccounting.gumroad.com/l/phxigq) — $97
- [Fixed Asset Rollforward Workbook](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward) — $79

The Month-End Close Checklist is the scaffolding that holds all of them together. Take it free; if it saves you time, the paid workbooks save you more.

## Technical specifications

- 5 tabs, ~20 KB file size
- 14 workbook-level defined names (lightweight, no fragility)
- Excel 2016 / 365 / Mac compatible
- Pure formulas — no VBA, no macros, no dynamic-array spills
- All input cells highlighted in yellow

## Out of scope (and clearly so)

This is a structural close workbook, not technical-accounting math. It does NOT compute commission amortization, lease ROU/liability schedules, or fixed asset depreciation — those are in the dedicated paid workbooks above. It does NOT handle multi-entity consolidation, intercompany eliminations, FX revaluation, or flux/variance analysis. It does NOT enforce SOX-compliant access controls (it's a free Excel file; if you need workflow software, look at FloQast, BlackLine, or Numeric).

## Built by a CPA

Built by Stephen Michels — 10+ years in technical accounting (CaptivateIQ alum) and the operator behind KDesk Accounting's ASC 606, ASC 842, and Fixed Asset workbooks. WA CPA license (currently inactive); this is a template, not professional advice.

## What you get

- `month-end-close-checklist-v1.xlsx` (5 tabs, 42 pre-populated tasks, 18 reconciliations)
- Quickstart README embedded in the workbook
- Companion links to the paid ASC 606 / ASC 842 / FA workbooks

## License

Free for individual and team use within your company. Do not redistribute or resell. If you find this useful, share the KDesk Accounting site link with a colleague: https://kdeskaccounting.com
```

---

## Suggested Gumroad tags

```
month-end close, controller, accounting, excel template, close checklist, subledger reconciliation, journal entries, SaaS finance, audit, free template
```

## Suggested Gumroad categories

```
Business & Money → Accounting
Software & Development → Productivity
```

## Post-publish swap-in

When the Gumroad URL is live, sed-swap `TBD-MEC-FREE` to the real product slug across:
- `content/templates/month-end-close/index.md`
- `content/posts/month-end-close-checklist-controllers.md`
- `layouts/index.html` (homepage product card)
- `layouts/partials/footer.html`
- `layouts/partials/email_capture.html`
- `marketing/email-blasts/2026-05-26-month-end-close.md`
