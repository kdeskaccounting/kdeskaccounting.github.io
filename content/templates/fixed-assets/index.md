---
title: "Fixed Asset Depreciation Schedule Excel Template"
description: "Audit-ready fixed asset rollforward workbook for controllers. 50 assets, four depreciation methods (SL, DDB, SYD, UoP), auto-generated journal entries with GL system presets (QuickBooks, NetSuite, Sage, Xero), and a five-way reconciliation tab. No macros, no subscription."
summary: "The Fixed Asset Rollforward Workbook handles 50 capitalized assets across all four book depreciation methods — straight-line, double-declining, sum-of-years, and units of production — and produces journal entries, a category rollforward, an ASC 250 change-in-estimate log, and a five-way reconciliation your auditor opens first."
date: 2026-05-13
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 2
price: 79
buy_url: "https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward"
free_url: "https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free"
free_label: "Try free 5-asset version"
tags: ["fixed assets", "depreciation", "ASC 360", "Excel template", "rollforward", "PP&E"]
faq:
  - q: "Does it handle straight-line, declining balance, and sum-of-years methods?"
    a: "Yes. Each asset has a method dropdown — Straight-Line, Double-Declining Balance with auto-switch to SL, Sum-of-Years-Digits, or Units of Production. The schedule, JE Generator, and rollforward adjust automatically."
  - q: "Does it work on a Mac?"
    a: "Yes. The workbook uses pure Excel formulas — no VBA macros, no Windows-only features, no dynamic-array spills. Works on Excel 2016, Excel 365, and Excel for Mac."
  - q: "Does it cover MACRS or tax depreciation?"
    a: "No. This is a book-depreciation workbook under US GAAP (ASC 360). MACRS, §168(k) bonus depreciation, and §179 elections are out of scope. A free-text 'Tax book differs (memo)' column lets you cross-reference each asset to your tax provision prep, but the workbook does not compute tax depreciation."
  - q: "Does it handle impairment?"
    a: "No. ASC 360-10-35 recoverability testing and impairment measurement are the buyer's responsibility. If a triggering event exists, perform impairment testing separately and record the write-down via the Disposal Log or a manual entry."
  - q: "What about Leasehold Improvements depreciated over a lease term?"
    a: "Yes. When you select 'Leasehold Improvements' as the category, the workbook prompts for the lease end date and a renewal-reasonably-certain flag. The effective useful life is automatically capped at the shorter of your input life or the remaining lease term — the rule under ASC 842-20-35-12."
  - q: "Can I export journal entries to NetSuite or QuickBooks?"
    a: "Yes. The JE Generator has a dropdown for Generic / QuickBooks / NetSuite / Sage Intacct / Xero, and the output columns adjust to each system's required fields (Subsidiary, Class, Tracking Category, etc.). Copy-paste into your GL system's import. Note: depreciation entries currently aggregate by Category; if you need entries split by Department / cost center for your GL, post the aggregated entry from the JE Generator and split manually, or wait for the V1.1 update which adds Category × Department aggregation."
  - q: "What if I need to revise a useful life mid-asset-life?"
    a: "The Asset Register has Revised Useful Life and Revision Effective Period columns where you record the change, and the Change Log tab keeps the audit trail. Reconciliation flags any edit to useful life that doesn't have a corresponding Change Log entry. **V1 limitation:** the Schedule does not yet automatically recompute depreciation against the revised life — you record the change in the Register + Change Log, then either manually adjust the Schedule or re-key the asset under a new ID with the revised life and an opening accumulated depreciation balance equal to depreciation taken through the revision date. ASC 250 prospective treatment is correct either way; the V1.1 update will automate this."
  - q: "What if I have more than 50 assets?"
    a: "Email hello@kdeskaccounting.com — for portfolios above 50 assets, dedicated fixed-asset software (Sage Fixed Assets, Bloomberg Tax) usually earns its cost. We can also discuss a custom build."
---

If you maintain a fixed asset register in Excel and your month-end depreciation routine takes longer than 20 minutes — or your auditor keeps asking for a clean rollforward that ties — this workbook handles the math correctly and produces audit-ready output. **$79 one-time. No subscription. No macros.**

[Get the Workbook ($79) →](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward)

The only fixed asset workbook with an auto-reconciling audit tab, built by a SaaS controller — between toy Etsy templates and $5,000/year enterprise software.

---

## What's in the Workbook

Eleven tabs, each with a specific job. You enter data on Setup, the Asset Register, and the Disposal Log; every other tab calculates automatically.

### README

The tab you land on first. A five-step quickstart, a link to a short walkthrough video, and the full out-of-scope list so you know exactly what this workbook does and what it doesn't.

### Setup

Company, fiscal year, reporting period selector, GL account codes by category, and a **Policy table** where you record your defaults — Computer Equipment 36 months, Furniture 84 months, etc. Every downstream tab reads from Setup. Change the reporting period once; the entire workbook shifts. A **Closed Periods** table lets you lock prior months so a stray edit doesn't silently restate audited periods.

### Asset Register (50-asset capacity)

One row per asset. Inputs include vouching anchors auditors will ask for the moment they select a sample — **Invoice #, PO #, CapEx Approver, Approval Date** — alongside the inputs that drive the math: acquisition date, in-service date (depreciation actually starts when the asset is *placed in service*, not when invoiced — ASC 360-10-30-1), cost, salvage, useful life, method, department/cost center, and a notes column for the audit trail.

Two flags surface automatically:

- **"Matches Policy?"** — compares the asset's useful life and method against the Setup Policy table. Deviations are visible at a glance, which is the consistency test your auditor performs manually.
- **"Significant Asset"** — any asset whose NBV exceeds the performance materiality threshold you set on Setup gets pre-flagged. Your auditor tests these 100%; pre-flagging them does the scoping work.

### Schedule (120-month per asset, master long-form)

For each asset, period by period: beginning NBV, depreciation this period, accumulated depreciation, ending NBV. Sorted by Asset ID then period — the running-sum structure means no cascading errors when a single input changes.

The four methods all run cleanly:

- **Straight-Line** — equal monthly expense; floored at salvage.
- **Double-Declining Balance** — DDB rate per the asset's useful life, with a one-time automatic switch to straight-line once SL-on-remaining-life exceeds DDB. Standard GAAP practice; no manual switch required.
- **Sum-of-Years-Digits** — full closed-form blending for mid-year acquisitions; SYD years anchored to in-service date.
- **Units of Production** — per-unit depreciation × units produced this month. Useful for fleet vehicles and production equipment.

Leasehold Improvements get a special treatment: the **effective useful life** is automatically capped at the shorter of your input life or the remaining lease term, including any renewal that's reasonably certain.

### JE Generator with GL system presets

Six journal entry types aggregated for the selected reporting period: monthly depreciation by category and department, asset capitalizations, disposals at gain, disposals at loss, disposals at NBV, and trade-ins (with a commercial-substance flag that drives ASC 845 treatment).

A dropdown on Setup switches the JE Generator output to your GL system's required column format:

- **Generic** — Date / Account / Description / Debit / Credit / Reference / Department
- **NetSuite** — adds Subsidiary, Class, Location
- **QuickBooks** — adds Class
- **Sage Intacct** — adds Department, Location
- **Xero** — adds Tracking Category 1 / 2

Every JE row has a **Reference** column linking back to the Schedule source row, so an auditor drilling from your posted GL entry can find the exact period and asset that produced it.

### Balance Sheet Rollforward

Standard cost + accumulated depreciation rollforward by category: opening balance + additions − disposals = closing balance, then accumulated depreciation opening + expense − disposal-removal = closing, then NBV. Each cell ties to a `SUMIFS` against the Schedule and Disposal Log, so what you see on the rollforward is exactly what you'll defend at audit.

### Disposal Log

One row per disposal, with the evidence trail your auditor will request: Disposal Date, Type (Sale / Retirement / Trade-in / Write-off / Theft-loss), Authorization (approver + date), Evidence Type (Bill of Sale / Scrap Receipt / Write-off Memo / Insurance Claim / Police Report), Evidence Reference, Counterparty. Gain or loss is computed against the NBV at disposal — automatically.

Trade-ins have an extra dropdown for **Commercial Substance Y/N**, which drives whether the new asset comes in at fair value (with gain/loss) or carryover basis per ASC 845-10-30-3.

### Change Log

The ASC 250-10-45-17 trail. Any change to a history-sensitive field — useful life, method, opening accumulated depreciation, category — gets logged with prior value, new value, effective period, reason, and approver. Reconciliation flags any silent edit on the Register that lacks a Change Log entry. This is the difference between a clean audit and a restatement.

### Reconciliation + Diagnostic

**Five tie-outs on a single tab.** Schedule depreciation total = JE Generator total. Schedule accumulated total = Rollforward closing. Register cost = Rollforward cost closing. Disposal Log adjustments = Rollforward disposal lines. NBV = Cost closing − Accumulated closing. Each row shows **green** ($0 variance), **yellow** (rounding ≤$1), or **red** (variance >$1, investigate).

The **Diagnostic sub-section** ranks six likely variance causes — disposal logged but Register Status not updated, opening accumulated depreciation entered without an opening period, edit detected in a closed period — and gives you a cell-jump hyperlink for each. Variance investigation drops from 90 minutes to 10.

### Audit Confirmation Export

Print-ready PBC format. When your auditor sends their sample of 25 asset IDs, paste them in and the tab outputs a formatted population list (Asset ID, Description, Category, In-Service Date, Cost, Useful Life, Method, Accumulated Depreciation, Net Book Value) with company header, signature lines, and footer. Saves two hours per audit.

---

## A Worked Example — $2,599 MacBook, Straight-Line, 3 Years

To make the mechanics concrete: a $2,599 MacBook Pro placed in service on 2026-01-15 with a 36-month useful life and $0 salvage value. Default convention: Full Month. This is `FA-0001` in the example data pre-populated in the workbook — open the file and you'll see the same numbers.

| Column | Month 1 (Jan 2026) |
|--------|---------|
| Beginning NBV | $2,599.00 |
| Depreciation This Period | $72.19 ($2,599 ÷ 36) |
| Accumulated Depreciation | $72.19 |
| Ending NBV | $2,526.81 |

**JE Generator output for January 2026:**

```
DR  Depreciation Expense — Computer Equipment    72.19
    CR  Accumulated Depreciation                            72.19
```

The reference column on this entry reads `FA-0001-2026-01`, which links straight back to row 1 of the Schedule. If your CFO or your auditor asks why depreciation expense was $72.19 in January, the answer is one click away.

By month 36 (December 2028), the asset has $2,599.00 accumulated depreciation and $0 NBV. It stays on the Register until you log a disposal — at which point the gain/loss is computed against the $0 NBV and a closing entry hits the GL.

---

## Double-Declining Balance — How It Differs

DDB front-loads expense, then automatically switches to Straight-Line on remaining basis once SL would produce a higher monthly expense than DDB. You don't manage the switch; the workbook does.

Example: $10,000 piece of equipment, 5-year life, 0 salvage, DDB method.

- Year 1 DDB: $10,000 × 40% = $4,000 → ends at NBV $6,000
- Year 2 DDB: $6,000 × 40% = $2,400 → ends at NBV $3,600
- Year 3 DDB: $3,600 × 40% = $1,440. But SL-on-remaining = ($3,600 − 0) / 3 = $1,200. **DDB still wins ($1,440).**
- Year 4 DDB: $2,160 × 40% = $864. SL-on-remaining = ($2,160 − 0) / 2 = $1,080. **SL now wins.** Workbook switches.
- Year 4 expense: $1,080. Year 5 expense: $1,080. Asset reaches NBV $0 cleanly.

The Schedule's `Switch Flag` column makes the switch visible. Once switched, the asset stays on SL — no flip-back. Standard GAAP practice.

---

## Who This Is For

- Controllers at Series A–C SaaS companies preparing for or in their first financial statement audit
- Finance managers maintaining a homegrown Excel asset register that breaks every time someone capitalizes a new fleet
- Companies with 5–50 active capitalized assets needing audit-defensible schedules
- Any controller spending more than 30 minutes per month-end booking depreciation and tying the rollforward

---

## What It Is Not

This workbook is **book depreciation under US GAAP only**. It does not compute MACRS or tax depreciation, does not handle §168(k) bonus depreciation or §179 elections, does not perform ASC 360-10-35 impairment testing, does not handle componentized depreciation (single asset = single schedule), and does not handle Asset Retirement Obligations under ASC 410-20. It does not include lessor accounting and cannot revalue an asset upward (GAAP prohibits this for US PP&E).

If your portfolio exceeds 50 assets, dedicated fixed-asset software earns its cost. If you need a tax-book schedule for the deferred tax provision, build that separately — the workbook includes a "Tax book differs (memo)" free-text column so you can cross-reference, but it does not compute tax depreciation.

---

## Technical Specifications

| Specification | Detail |
|---------------|---------|
| Asset capacity | 50 assets (paid), 5 assets (free) |
| Schedule length | 120 months per asset (paid), 36 months (free) |
| Depreciation methods | Straight-Line, Double-Declining Balance, Sum-of-Years-Digits, Units of Production (paid only) |
| Conventions | Full Month (default), Mid-Month |
| GL system presets | Generic, QuickBooks, NetSuite, Sage Intacct, Xero (paid only) |
| Excel version | 2016, 365, Mac (no macros, no VBA, no dynamic arrays) |
| File format | .xlsx |
| Formula protection | Locked formula cells, unlocked input cells, separate password on Opening Accumulated Depreciation |
| Price | $79 one-time |

---

## Get the Workbook

[**Get the Workbook ($79) →**](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward)

Not ready to buy? [Try the free 5-asset version](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free) — same structure, limited to 5 assets and 36 months. See how the Schedule, JE Generator, and Reconciliation work on your own data before committing.

---

## Frequently Asked Questions

**Does it handle straight-line, declining balance, and sum-of-years methods?**
Yes. Each asset has a method dropdown — Straight-Line, Double-Declining Balance with auto-switch to SL, Sum-of-Years-Digits, or Units of Production. The schedule, JE Generator, and rollforward adjust automatically.

**Does it work on a Mac?**
Yes. The workbook uses pure Excel formulas — no VBA macros, no Windows-only features, no dynamic-array spills. Works on Excel 2016, Excel 365, and Excel for Mac.

**Does it cover MACRS or tax depreciation?**
No. This is a book-depreciation workbook under US GAAP (ASC 360). MACRS, §168(k) bonus depreciation, and §179 elections are out of scope. A free-text "Tax book differs (memo)" column lets you cross-reference each asset to your tax provision prep, but the workbook does not compute tax depreciation.

**Does it handle impairment?**
No. ASC 360-10-35 recoverability testing and impairment measurement are the buyer's responsibility. If a triggering event exists, perform impairment testing separately and record the write-down via the Disposal Log or a manual entry.

**What about Leasehold Improvements depreciated over a lease term?**
Yes. When you select "Leasehold Improvements" as the category, the workbook prompts for the lease end date, a renewal-reasonably-certain flag, and the renewal term in months. The effective useful life is automatically capped at the shorter of your input life or the remaining lease term (including the renewal term when reasonably certain) — the rule under ASC 842-20-35-12.

**Can I export journal entries to NetSuite or QuickBooks?**
Yes. The JE Generator has a dropdown for Generic / QuickBooks / NetSuite / Sage Intacct / Xero, and the output columns adjust to each system's required fields (Subsidiary, Class, Tracking Category, etc.). Copy-paste into your GL system's import. **V1 limitation:** depreciation entries aggregate by Category. If you need entries split by Department / cost center for your GL, post the aggregated entry from the JE Generator and split manually. The V1.1 update will add Category × Department aggregation.

**What if I need to revise a useful life mid-asset-life?**
The Asset Register has Revised Useful Life and Revision Effective Period columns where you record the change, and the Change Log tab keeps the audit trail. Reconciliation flags any edit to useful life that doesn't have a corresponding Change Log entry. **V1 limitation:** the Schedule does not yet automatically recompute depreciation against the revised life — you record the change in the Register + Change Log, then either manually adjust the Schedule or re-key the asset under a new ID with the revised life and an opening accumulated depreciation balance. ASC 250 prospective treatment is correct either way; the V1.1 update will automate this.

**What about trade-in transactions (ASC 845)?**
The Disposal Log has a Disposal Type dropdown that includes "Trade-in" and a Commercial Substance Y/N flag. **V1 limitation:** the JE Generator emits the standard sale-pattern disposal entry regardless of trade-in type. For trade-in transactions with commercial substance, recognize gain/loss at fair value via the JE Generator's standard disposal entry, then book the new asset at fair value via a separate capitalization entry. For trade-ins without commercial substance (ASC 845-10-30-3), book the new asset at carryover basis via a manual entry — the V1.1 update will automate both paths.

**What does V1 NOT do that I should know about up front?**
- Department-segmented JE entries (depreciation rolls up by Category only; you split by department manually if needed)
- Automatic Schedule recomputation on useful-life revision (you record the change; you manually adjust depreciation prospectively)
- Trade-in JE patterns for ASC 845 (standard disposal entry produced; manual adjustment for new-asset side)
- MACRS / tax depreciation
- ASC 360-10-35 impairment testing
- Componentized asset depreciation
- Asset Retirement Obligations (ASC 410-20)
- Lessor accounting

These are all clearly out of scope. V1.1 will close the first three. The remaining items are deliberate scope limits — for those, a dedicated fixed-asset system (Sage Fixed Assets, Bloomberg Tax) or a tax provision workbook is the right tool.

**What if I have more than 50 assets?**
Email [hello@kdeskaccounting.com](mailto:hello@kdeskaccounting.com) — for portfolios above 50 assets, dedicated fixed-asset software (Sage Fixed Assets, Bloomberg Tax) usually earns its cost. We can also discuss a custom build.
