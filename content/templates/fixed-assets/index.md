---
title: "Fixed Asset Register & Depreciation Schedule Excel Template (ASC 360)"
description: "Fixed asset register with a depreciation schedule, built for controllers. 50 assets, four depreciation methods (SL, DDB, SYD, UoP), auto-generated journal entries with GL dimension presets (QuickBooks, NetSuite, Sage Intacct, Xero), and a reconciliation tab that ties the schedule, journal entries, rollforward and register to your GL balances. No macros, no subscription."
summary: "The Fixed Asset Rollforward Workbook handles 50 capitalized assets across all four book depreciation methods — straight-line, double-declining, sum-of-years, and units of production — and produces journal entries, a category rollforward, an ASC 250 change-in-estimate log, and a reconciliation that ties the schedule, journal entries, rollforward and register to the GL balances you enter."
date: 2026-05-13
lastmod: 2026-11-24
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 2
price: 79
buy_url: "https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward"
free_url: "https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free"
free_label: "Try free 5-asset version"
video_url: "https://github.com/kdeskaccounting/kdeskaccounting.github.io/releases/download/media-2026-09/fixed-assets.mp4"
video_poster: "/images/products/fixed-assets-poster.png"
youtube_url: "https://youtu.be/I-VAym73C-M"
tags: ["fixed assets", "fixed asset register", "depreciation schedule", "ASC 360", "Excel template", "rollforward", "PP&E"]
compare:
  free_name: "Free 5-asset version"
  full_name: "Full workbook"
  rows:
    - ["Assets", "5", "50"]
    - ["Schedule length", "36 months", "120 months"]
    - ["Asset Register and Schedule tabs", "yes", "yes"]
    - ["Depreciation methods", "three (SL, DDB, SYD)", "four (adds Units of Production)"]
    - ["JE Generator with QuickBooks / NetSuite / Sage / Xero presets", "no", "yes"]
    - ["Category rollforward", "no", "yes"]
    - ["Disposal log and change log", "no", "yes"]
    - ["Reconciliation to your GL balances", "no", "yes"]
    - ["Audit confirmation export", "no", "yes"]
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
    a: "Yes. On a Leasehold Improvements row the Lease End Date cell turns red until you enter one, and there are columns for a renewal-reasonably-certain flag and the renewal term. The effective useful life is automatically capped at the shorter of your input life or the remaining lease term (including the renewal when it is reasonably certain), which is the rule under ASC 842-20-35-12. If the lease end is missing or before the in-service date, the input life is used and the Input Check column flags the row."
  - q: "Can I export journal entries to NetSuite or QuickBooks?"
    a: "Yes. A dropdown on Setup picks Generic / QuickBooks / NetSuite / Sage Intacct / Xero, and the JE Generator's three dimension column headers relabel to that system's names (Subsidiary, Class, Location, Tracking Category and so on). Account codes come from your Setup table. Map the columns to your GL's import template and paste. Depreciation entries aggregate by category; if your GL needs them split by department or cost center, split the aggregated entry manually."
  - q: "What if I need to revise a useful life mid-asset-life?"
    a: "Record the change in the Asset Register's Revised Useful Life and Revision Effective Period columns (memo fields) and in the Change Log tab. The Reconciliation tab counts any asset with a Revised Useful Life but no Change Log entry. The Schedule does not recompute from the revised life: re-key the asset under a new ID with the revised life and an opening accumulated depreciation balance equal to depreciation taken through the revision date. That gives the prospective treatment ASC 250 requires."
  - q: "What if I have more than 50 assets?"
    a: "Email hello@kdeskaccounting.com — for portfolios above 50 assets, dedicated fixed-asset software (Sage Fixed Assets, Bloomberg Tax) usually earns its cost. We can also discuss a custom build."
---

If you maintain a fixed asset register in Excel and your month-end depreciation routine takes longer than 20 minutes — or your auditor keeps asking for a clean rollforward that ties — this fixed asset register and depreciation schedule template handles the math and produces a rollforward that ties to the GL balances you enter. **$79 one-time. No subscription. No macros.**

[Get the Workbook ($79) →](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward)

A fixed asset workbook with a reconciliation tab that ties to your GL, built by a SaaS controller — between toy Etsy templates and $5,000/year enterprise software.

---

## What's in the Workbook

Ten tabs, each with a specific job (plus a hidden `_Pivot` tab of long-form data for your own pivot tables). You enter data on Setup, the Asset Register, the Disposal Log and the Change Log (plus monthly units for Units of Production assets on the Schedule, and your GL balances on the Reconciliation); the other tabs calculate.

### README

The tab you land on first. A five-step quickstart, the conventions the math uses, a link to the walkthrough video, and the full out-of-scope list so you know exactly what this workbook does and what it doesn't.

### Setup

Company, fiscal year start, reporting period (a month-end date), performance materiality, GL account codes by category, and a **Policy table** where you record your capitalization policy — Computer Equipment 36 months, Furniture 84 months, etc. Every downstream tab reads from Setup. Change the reporting period once; the entire workbook shifts. A **Closed Periods** table marks booked months LOCKED on the Schedule so you can see which periods are already closed. It does not freeze them: change an input and closed months recalculate, so compare to what you booked before re-posting.

### Asset Register (50-asset capacity)

One row per asset. Inputs include vouching anchors auditors will ask for the moment they select a sample — **Invoice #, PO #, CapEx Approver, Approval Date** — alongside the inputs that drive the math: acquisition date, in-service date (depreciation starts when the asset is *placed in service*, not when invoiced), cost, salvage, useful life (up to 120 months, the schedule length), method, convention, department/cost center, and a notes column.

Each asset keeps its own convention. **Opening Accum Depr** and **Opening Period** are only for existing assets you load part-way through their life; leave Opening Period blank for everything else and the schedule starts at the in-service date. Because each row carries its own settings, rolling the fiscal year forward never restates prior years.

Three flags surface automatically:

- **"Matches Policy?"** — compares the asset's useful life and method against the Setup Policy table. Deviations are visible at a glance, which is the consistency test your auditor performs manually.
- **"Significant Asset"** — any asset whose NBV exceeds the performance materiality threshold you set on Setup gets pre-flagged for your auditor's scoping.
- **Input Check** — flags a leasehold improvement with a missing lease end date (or one before the in-service date), an opening balance without an Opening Period, and a life that runs past the 120-month schedule.

### Schedule (120 months per asset, master long-form)

For each asset, period by period: beginning NBV, depreciation this period, accumulated depreciation, ending NBV. Sorted by Asset ID then period — the running-sum structure means no cascading errors when a single input changes.

The four methods:

- **Straight-Line** — equal monthly expense; floored at salvage.
- **Double-Declining Balance** — the annual DDB rate applied to the NBV at the start of each asset year and spread evenly over its 12 months, with a one-time automatic switch to straight-line once SL on the remaining life is larger. No manual switch required.
- **Sum-of-Years-Digits** — years counted from the in-service date; each month gets one twelfth of that year's fraction.
- **Units of Production** — per-unit depreciation × units produced this month. Useful for fleet vehicles and production equipment.

Conventions: **Full Month** (a full month in the in-service and disposal months) or **Mid-Month** (half a month in each). Time-based methods are trued up in the last month of the effective life, so the asset reaches salvage exactly at the end of its life.

Leasehold Improvements get a special treatment: the **effective useful life** is automatically capped at the shorter of your input life or the remaining lease term, including any renewal that's reasonably certain.

### JE Generator with GL dimension presets

Journal entries for the selected reporting period, with account codes from your Setup table: monthly depreciation by category, capitalization of assets placed in service that month, and disposals (sale, retirement, trade-in, write-off, theft-loss) with the gain or loss.

A dropdown on Setup relabels the JE Generator's three dimension column headers to your GL system's names; map the rest to your import template:

- **Generic** — Date / Account / Description / Debit / Credit / Reference / Department / Memo
- **NetSuite** — adds Subsidiary, Class, Location
- **QuickBooks** — adds Class
- **Sage Intacct** — adds Department, Location
- **Xero** — adds Tracking Category 1 / 2

Each depreciation entry is referenced by period and category (`DEPR-2026-01-COM`), and the Schedule's JE Reference column (`FA-0001-2026-01`) shows the asset rows that make it up — so you can trace a posted GL entry back to the assets that produced it.

### Balance Sheet Rollforward

Standard cost + accumulated depreciation rollforward by category: opening balance + additions − disposals = closing balance, then accumulated depreciation opening + expense − disposal-removal = closing, then NBV. Each cell ties to a `SUMIFS` against the Schedule, the Register and the Disposal Log.

### Disposal Log

One row per disposal, with the evidence trail your auditor will request: Disposal Date, Type (Sale / Retirement / Trade-in / Write-off / Theft-loss), Authorization (approver + date), Evidence Type (Bill of Sale / Scrap Receipt / Write-off Memo / Insurance Claim / Police Report), Evidence Reference, Counterparty. Accumulated depreciation runs through the end of the disposal month, and the gain or loss is computed against the NBV at disposal — automatically.

Trade-ins record a **Commercial Substance Y/N** flag for your memo. The JE Generator posts the standard sale entry either way; book the new asset separately (see the FAQ).

### Change Log

The ASC 250-10-45-17 trail. Any change to a history-sensitive field — useful life, method, opening accumulated depreciation, category — gets logged with prior value, new value, effective period, reason, and approver. The Reconciliation tab counts any asset with a Revised Useful Life entered on the Register but no Change Log entry.

### Reconciliation + Diagnostic

**Seven checks across five sources** — Schedule, JE Generator, Rollforward, Register and GL. Schedule depreciation = JE Generator; Schedule accumulated depreciation = Rollforward closing; Register cost = Rollforward closing cost; Register NBV = Rollforward NBV; and Rollforward cost, accumulated depreciation and YTD depreciation expense = the GL balances you type from your trial balance. Each row shows **green** (TIES), **yellow** (rounding ≤ $1, or a GL balance still to enter), or **red** (variance, investigate).

The **Diagnostic sub-section** lists seven likely causes when a check is red, with a live count for most of them — disposals dated after the period, assets placed in service after it, opening balances without an opening period, revisions without a Change Log entry, leasehold improvements without a valid lease end, off-policy assets — and a cell-jump link for each.

### Audit Confirmation Export

Print-ready PBC format. When your auditor sends their sample, paste the asset IDs into column A (room for all 50) and the tab fills in Description, Category, In-Service Date, Cost, Useful Life, Method, Accumulated Depreciation, Net Book Value and Status at the reporting period, with a company header, management representation and sign-off lines. An ID that isn't on the Register says so.

---

## A Worked Example — $2,599 MacBook, Straight-Line, 3 Years

To make the mechanics concrete: a $2,599 MacBook Pro placed in service on 2026-01-15 with a 36-month useful life and $0 salvage value, Full Month convention. This is `FA-0001` in the example data pre-populated in the workbook — open the file and you'll see the same numbers.

| Column | Month 1 (Jan 2026) |
|--------|---------|
| Beginning NBV | $2,599.00 |
| Depreciation This Period | $72.19 ($2,599 ÷ 36) |
| Accumulated Depreciation | $72.19 |
| Ending NBV | $2,526.81 |

**JE Generator output with the reporting period set to January 2026** (the sample's other January asset is the leasehold improvement, which takes a half month under Mid-Month):

```
DR  6200  Monthly depreciation — Computer Equipment        72.19
DR  6200  Monthly depreciation — Leasehold Improvements   708.33
    CR  1599  Accumulated Depreciation                              780.52
```

The Computer Equipment line is referenced `DEPR-2026-01-COM`, and the Schedule row behind it carries `FA-0001-2026-01`. If your CFO or your auditor asks why computer depreciation was $72.19 in January, the answer is one filter away.

By month 36 (December 2028), the asset has $2,599.00 accumulated depreciation and $0 NBV. It stays on the Register until you log a disposal — at which point the gain/loss is computed against the $0 NBV and a closing entry hits the GL.

---

## Double-Declining Balance — How It Differs

DDB front-loads expense, then automatically switches to Straight-Line on remaining basis once SL would produce a higher expense than DDB. You don't manage the switch; the workbook does.

Example: $10,000 piece of equipment, 5-year life, 0 salvage, DDB method.

- Year 1 DDB: $10,000 × 40% = $4,000 → ends at NBV $6,000
- Year 2 DDB: $6,000 × 40% = $2,400 → ends at NBV $3,600
- Year 3 DDB: $3,600 × 40% = $1,440. But SL-on-remaining = ($3,600 − 0) / 3 = $1,200. **DDB still wins ($1,440).**
- Year 4 DDB: $2,160 × 40% = $864. SL-on-remaining = ($2,160 − 0) / 2 = $1,080. **SL now wins.** Workbook switches.
- Year 4 expense: $1,080. Year 5 expense: $1,080. Asset reaches NBV $0 cleanly.

Each year's amount is spread evenly over its 12 months ($333.33 a month in year 1). The Schedule's `Switch Flag` column makes the switch visible. Once switched, the asset stays on SL — no flip-back.

---

## Who This Is For

- Controllers at Series A–C SaaS companies preparing for or in their first financial statement audit
- Finance managers maintaining a homegrown Excel asset register that breaks every time someone capitalizes a new fleet
- Companies with 5–50 active capitalized assets needing schedules that reconcile to the GL
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
| Schedule length | 120 months per asset (paid), 36 months (free); useful life up to 120 months |
| Depreciation methods | Straight-Line, Double-Declining Balance, Sum-of-Years-Digits (paid and free), Units of Production (paid only) |
| Conventions | Full Month (default), Mid-Month (half a month in the in-service and disposal months) |
| GL dimension presets | Generic, QuickBooks, NetSuite, Sage Intacct, Xero (paid only) |
| Excel version | 2016, 365, Mac (no macros, no VBA, no dynamic arrays) |
| File format | .xlsx |
| Formula protection | Locked formula cells, unlocked input cells (including Opening Accumulated Depreciation) |
| Price | $79 one-time |

---

## Get the Workbook

[**Get the Workbook ($79) →**](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward)

Not ready to buy? [Try the free 5-asset version](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free) — the Register and Schedule for 5 assets and 36 months with three depreciation methods (SL, DDB, SYD), so you can check the math on your own assets. Units of Production, the JE Generator, rollforward, disposal log and reconciliation are in the full workbook (see the comparison above).

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
Yes. On a Leasehold Improvements row the Lease End Date cell turns red until you enter one, and there are columns for a renewal-reasonably-certain flag and the renewal term in months. The effective useful life is automatically capped at the shorter of your input life or the remaining lease term (including the renewal term when reasonably certain) — the rule under ASC 842-20-35-12. If the lease end is missing or before the in-service date, the input life is used and the Input Check column flags the row.

**Can I export journal entries to NetSuite or QuickBooks?**
Yes. A dropdown on Setup picks Generic / QuickBooks / NetSuite / Sage Intacct / Xero, and the JE Generator's three dimension column headers relabel to that system's names (Subsidiary, Class, Location, Tracking Category and so on). Account codes come from your Setup table. Map the columns to your GL's import template and paste. Depreciation entries aggregate by category; if your GL needs them split by department or cost center, split the aggregated entry manually.

**What if I need to revise a useful life mid-asset-life?**
Record the change in the Asset Register's Revised Useful Life and Revision Effective Period columns (memo fields) and in the Change Log tab. The Reconciliation tab counts any asset with a Revised Useful Life but no Change Log entry. The Schedule does not recompute from the revised life: re-key the asset under a new ID with the revised life and an opening accumulated depreciation balance equal to depreciation taken through the revision date. That gives the prospective treatment ASC 250 requires.

**What about trade-in transactions (ASC 845)?**
The Disposal Log has a Disposal Type dropdown that includes "Trade-in" and a Commercial Substance Y/N flag. The JE Generator posts the standard sale-pattern disposal entry regardless of trade-in type. For trade-ins with commercial substance, the standard disposal entry recognizes the gain or loss; then book the new asset at fair value as a separate capitalization. For trade-ins without commercial substance (ASC 845-10-30-3), book the new asset at carryover basis with a manual entry.

**What does it NOT do that I should know about up front?**
- Department-segmented JE entries (depreciation rolls up by category; you split by department manually if needed)
- Automatic Schedule recomputation on useful-life revision (you record the change and re-key the asset)
- Trade-in JE patterns for ASC 845 (standard disposal entry produced; book the new asset yourself)
- MACRS / tax depreciation
- ASC 360-10-35 impairment testing
- Componentized asset depreciation
- Asset Retirement Obligations (ASC 410-20)
- Lessor accounting

The first three have workarounds described above. The rest are deliberate scope limits — for those, a dedicated fixed-asset system (Sage Fixed Assets, Bloomberg Tax) or a tax provision workbook is the right tool.

**What if I have more than 50 assets?**
Email [hello@kdeskaccounting.com](mailto:hello@kdeskaccounting.com) — for portfolios above 50 assets, dedicated fixed-asset software (Sage Fixed Assets, Bloomberg Tax) usually earns its cost. We can also discuss a custom build.
