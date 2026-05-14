---
title: "Fixed Asset Depreciation Schedule in Excel: How to Build One From Scratch"
date: 2026-03-19
lastmod: 2026-05-13
description: "How to build a fixed asset depreciation schedule in Excel — straight-line, double-declining balance, sum-of-years methods, journal entries, and rollforward — plus a ready-made workbook if you don't want to build it from scratch."
summary: "A step-by-step guide to building a fixed asset depreciation schedule in Excel. Covers three depreciation methods with formulas, worked examples, journal entries, and the register structure you need for audit-ready reporting. Includes a link to a pre-built audit-ready workbook."
tags: ["depreciation schedule", "fixed assets", "depreciation methods", "Excel", "Excel template", "straight line depreciation", "ASC 360", "accounting"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 13
---

If you manage fixed assets at a SaaS startup, you already know the pain. Every quarter, the auditors want a depreciation schedule that ties to the GL. Every month-end, you need to book the right expense. And every time someone buys a new server, laptop fleet, or office buildout, you are the one adding rows to a spreadsheet that was never designed to scale.

This post walks through how to build a depreciation schedule in Excel from scratch. We will cover three depreciation methods with real formulas, work through a single asset example so you can compare them side by side, and then discuss the register structure you need once you have more than a handful of assets.

---

## What a Depreciation Schedule Is and Why You Need One

A depreciation schedule is a period-by-period table that shows how a fixed asset's cost is allocated to expense over its useful life. For each asset, the schedule tracks:

- **Beginning net book value** at the start of the period
- **Depreciation expense** recognized during the period
- **Accumulated depreciation** to date
- **Ending net book value** at the end of the period

You need one for three reasons:

1. **GAAP compliance.** ASC 360 requires systematic allocation of asset cost over useful life. You need a supportable method applied consistently.
2. **Audit readiness.** Auditors will ask for a fixed asset rollforward that ties accumulated depreciation on the balance sheet to depreciation expense on the income statement. A clean schedule gives them that in minutes.
3. **Month-end close efficiency.** Without a schedule, you are recalculating depreciation from scratch every period. With one, the journal entry writes itself. (If your close process needs broader help, see our [month-end close checklist for controllers](/posts/month-end-close-checklist-controllers/).)

---

## Key Inputs for Any Depreciation Schedule

Before building formulas, you need five inputs per asset:

| Input | Description | Example |
|-------|-------------|---------|
| **Asset cost** | Purchase price plus any costs to bring the asset into service | $120,000 |
| **Salvage value** | Estimated residual value at the end of useful life | $0 |
| **Useful life** | Number of years (or months) over which the asset will be depreciated | 5 years |
| **In-service date** | The date the asset was placed into service | January 1, 2026 |
| **Depreciation method** | Straight-line, double-declining balance, sum-of-years-digits, etc. | Straight-line |

We will use the same asset for all three method examples below: a $120,000 server placed in service on January 1, 2026, with a 5-year useful life and $0 salvage value.

---

## Straight-Line Depreciation

### The Formula

Straight-line is the simplest and most common method. The formula:

```
Annual Depreciation = (Cost - Salvage Value) / Useful Life
```

For our server:

```
($120,000 - $0) / 5 = $24,000 per year
```

Every year gets the same expense. Monthly, that is $2,000.

### Excel Implementation

Set up your spreadsheet with the asset inputs in a few cells, then build the schedule below.

Assume:
- `B1` = Cost ($120,000)
- `B2` = Salvage Value ($0)
- `B3` = Useful Life in years (5)

The annual depreciation formula in each year row:

```excel
=(B1-B2)/B3
```

For the full schedule, set up columns for Year, Beginning Book Value, Depreciation Expense, Accumulated Depreciation, and Ending Book Value.

In Year 1:
- Beginning Book Value: `=B1`
- Depreciation Expense: `=(B1-B2)/B3`
- Accumulated Depreciation: `=Depreciation Expense` (for Year 1)
- Ending Book Value: `=Beginning Book Value - Depreciation Expense`

In Year 2 and beyond:
- Beginning Book Value: `=Previous Year Ending Book Value`
- Depreciation Expense: `=(B1-B2)/B3`
- Accumulated Depreciation: `=Previous Accumulated + Current Depreciation`
- Ending Book Value: `=Beginning Book Value - Depreciation Expense`

Excel also has a built-in function:

```excel
=SLN(B1, B2, B3)
```

`SLN(cost, salvage, life)` returns the same $24,000.

### Worked Example

| Year | Beginning Book Value | Depreciation Expense | Accumulated Depreciation | Ending Book Value |
|------|---------------------|----------------------|--------------------------|-------------------|
| 1 | $120,000 | $24,000 | $24,000 | $96,000 |
| 2 | $96,000 | $24,000 | $48,000 | $72,000 |
| 3 | $72,000 | $24,000 | $72,000 | $48,000 |
| 4 | $48,000 | $24,000 | $96,000 | $24,000 |
| 5 | $24,000 | $24,000 | $120,000 | $0 |
| **Total** | | **$120,000** | | |

The asset fully depreciates to $0. Total expense equals the original cost. This is what auditors want to see.

---

## Double-Declining Balance (DDB)

### The Formula

DDB is an accelerated method that front-loads expense into early years. The formula:

```
Annual Depreciation = (2 / Useful Life) x Beginning Book Value
```

The rate is double the straight-line rate. For a 5-year life, straight-line rate = 20%, so DDB rate = 40%.

One important rule: you never depreciate below salvage value. In practice with $0 salvage, you switch to straight-line in the final years to fully depreciate the asset.

### Excel Implementation

The depreciation rate:

```excel
=2/B3
```

Year 1 depreciation:

```excel
=MIN(B1 * (2/B3), B1 - B2)
```

Year 2+ depreciation (where `D_prev` is the previous ending book value):

```excel
=MIN(D_prev * (2/B3), D_prev - B2)
```

The `MIN` function prevents depreciating below salvage value.

Excel's built-in function handles the switch to straight-line automatically:

```excel
=DDB(B1, B2, B3, period)
```

Where `period` is the year number (1, 2, 3, etc.).

For a smoother switch to straight-line, use `VDB` (variable declining balance):

```excel
=VDB(B1, B2, B3, period-1, period)
```

`VDB` automatically switches from declining balance to straight-line when straight-line yields a higher amount, which ensures the asset fully depreciates.

### Worked Example

| Year | Beginning Book Value | DDB Rate | Depreciation Expense | Accumulated Depreciation | Ending Book Value |
|------|---------------------|----------|----------------------|--------------------------|-------------------|
| 1 | $120,000 | 40% | $48,000 | $48,000 | $72,000 |
| 2 | $72,000 | 40% | $28,800 | $76,800 | $43,200 |
| 3 | $43,200 | 40% | $17,280 | $94,080 | $25,920 |
| 4 | $25,920 | switch | $12,960 | $107,040 | $12,960 |
| 5 | $12,960 | switch | $12,960 | $120,000 | $0 |
| **Total** | | | **$120,000** | | |

Notice that in Years 4 and 5, the DDB amount ($10,368 and $6,221) would be less than the straight-line amount over the remaining life. So we switch to straight-line: $25,920 remaining / 2 years = $12,960 per year. The asset still reaches $0.

---

## Sum-of-Years-Digits (SYD)

### The Formula

SYD is another accelerated method, but with a more predictable decline than DDB. The formula:

```
Annual Depreciation = (Remaining Life / Sum of Years Digits) x (Cost - Salvage)
```

For a 5-year life, the sum of years digits = 1 + 2 + 3 + 4 + 5 = 15.

Year 1 fraction: 5/15. Year 2: 4/15. Year 3: 3/15. And so on.

### Excel Implementation

The sum-of-years-digits denominator:

```excel
=B3*(B3+1)/2
```

For a 5-year life, that returns 15.

Year N depreciation (where `N` is the year number):

```excel
=((B3-N+1) / (B3*(B3+1)/2)) * (B1-B2)
```

Excel's built-in:

```excel
=SYD(B1, B2, B3, period)
```

Where `period` is the year number.

### Worked Example

| Year | Remaining Life | Fraction | Depreciation Expense | Accumulated Depreciation | Ending Book Value |
|------|---------------|----------|----------------------|--------------------------|-------------------|
| 1 | 5 | 5/15 | $40,000 | $40,000 | $80,000 |
| 2 | 4 | 4/15 | $32,000 | $72,000 | $48,000 |
| 3 | 3 | 3/15 | $24,000 | $96,000 | $24,000 |
| 4 | 2 | 2/15 | $16,000 | $112,000 | $8,000 |
| 5 | 1 | 1/15 | $8,000 | $120,000 | $0 |
| **Total** | | | **$120,000** | | |

Clean, predictable, and fully depreciates. SYD is less common than straight-line or DDB, but some companies prefer it for assets that lose productivity quickly.

---

## Comparison: All Three Methods Side by Side

Same asset ($120,000 server, 5-year life, $0 salvage), three methods:

| Year | Straight-Line | Double-Declining Balance | Sum-of-Years-Digits |
|------|--------------|--------------------------|---------------------|
| 1 | $24,000 | $48,000 | $40,000 |
| 2 | $24,000 | $28,800 | $32,000 |
| 3 | $24,000 | $17,280 | $24,000 |
| 4 | $24,000 | $12,960 | $16,000 |
| 5 | $24,000 | $12,960 | $8,000 |
| **Total** | **$120,000** | **$120,000** | **$120,000** |

Total expense is always the same. The only question is timing. Straight-line spreads it evenly. DDB and SYD push more expense into early years, which reduces taxable income sooner but also reduces reported earnings.

For most SaaS startups, straight-line is the default for financial reporting. But if you maintain both book and tax depreciation schedules, you may need DDB or MACRS for tax purposes alongside straight-line for GAAP.

---

## Partial-Year Conventions

Assets are rarely placed in service on January 1. When an asset goes into service mid-year, you need a convention to determine how much depreciation to recognize in the first and last years.

### Mid-Month Convention

The most precise approach. If an asset is placed in service on March 15, you get 9.5 months of depreciation in Year 1 (half of March plus April through December).

```excel
=SLN(B1, B2, B3) * (12 - MONTH(InServiceDate) + 0.5) / 12
```

### Half-Year Convention

Simpler and common for tax purposes (MACRS uses this). Regardless of when the asset is placed in service during the year, you take exactly half a year of depreciation in Year 1 and half in the final year.

```excel
=SLN(B1, B2, B3) * 0.5
```

In Year 1, this gives $12,000 instead of $24,000. The asset then takes 6 years on the schedule instead of 5 (with the final year also getting half).

### Handling Partial Years in Your Schedule

The key is to add an `In-Service Date` column and use it to calculate the first-year proration factor:

```excel
=IF(Year=1, (12-MONTH(InServiceDate)+1)/12, IF(Year=LastYear, MONTH(InServiceDate)/12, 1))
```

Multiply this factor by the full-year depreciation to get the partial-year amount. Make sure the last year picks up the remaining balance so the asset still fully depreciates.

---

## Building the Fixed Asset Register

A single-asset schedule is straightforward. The real challenge is managing 50, 100, or 200 assets across multiple categories, methods, and in-service dates.

A fixed asset register is a master table where each row represents one asset. The recommended column structure:

| Column | Purpose |
|--------|---------|
| Asset ID | Unique identifier (e.g., FA-001) |
| Description | Server, laptop, office buildout, etc. |
| Category | Computer Equipment, Furniture, Leasehold Improvements |
| In-Service Date | Date placed in service |
| Cost | Original purchase price |
| Salvage Value | Estimated residual |
| Useful Life (months) | Useful life in months for precision |
| Depreciation Method | Straight-Line, DDB, SYD |
| Monthly Depreciation | Calculated from the above inputs |
| Accumulated Depreciation | Running total through the current period |
| Net Book Value | Cost minus accumulated depreciation |
| Disposal Date | Blank until asset is retired or sold |
| Disposal Proceeds | Amount received on disposal |
| Gain/Loss on Disposal | Proceeds minus net book value at disposal |

The monthly depreciation formula for straight-line:

```excel
=IF(DisposalDate<>"", 0, (Cost-Salvage)/(Life_Months))
```

This structure lets you use `SUMIFS` to roll up depreciation expense by category, by month, or by GL account for journal entries.

---

## Journal Entries and the Rollforward Schedule

### Monthly Journal Entry

The journal entry for depreciation is the same every month (for straight-line):

| Account | Debit | Credit |
|---------|-------|--------|
| Depreciation Expense | $2,000 | |
| Accumulated Depreciation | | $2,000 |

For multiple assets, sum the monthly depreciation column in your register and book a single entry per asset category:

```excel
=SUMIFS(MonthlyDepreciation, Category, "Computer Equipment", DisposalDate, "")
```

This gives you the total monthly depreciation for all active computer equipment assets.

### Rollforward Schedule

Auditors want a rollforward that proves the balance sheet ties to the detail. The structure:

| | Computer Equipment | Furniture | Leasehold Improvements | Total |
|---|---|---|---|---|
| **Cost** | | | | |
| Opening Balance | $500,000 | $80,000 | $200,000 | $780,000 |
| Additions | $120,000 | $0 | $0 | $120,000 |
| Disposals | ($30,000) | $0 | $0 | ($30,000) |
| Closing Balance | $590,000 | $80,000 | $200,000 | $870,000 |
| **Accumulated Depreciation** | | | | |
| Opening Balance | ($200,000) | ($40,000) | ($60,000) | ($300,000) |
| Depreciation Expense | ($95,000) | ($16,000) | ($40,000) | ($151,000) |
| Disposals | $25,000 | $0 | $0 | $25,000 |
| Closing Balance | ($270,000) | ($56,000) | ($100,000) | ($426,000) |
| **Net Book Value** | **$320,000** | **$24,000** | **$100,000** | **$444,000** |

Each row in the rollforward should tie to a `SUMIFS` on the register. The closing cost balance equals the sum of all asset costs minus disposed asset costs. Accumulated depreciation equals the sum of all monthly depreciation through the reporting date.

---

## The Excel Scaling Problem

A single depreciation schedule in Excel works fine. Ten assets in a register are manageable. But things break down quickly:

- **50+ assets** with different in-service dates, methods, and useful lives means your monthly depreciation column has nested `IF` statements that are hard to audit.
- **Mid-year additions and disposals** require prorating both the first and last year, plus removing disposed assets from future periods.
- **Multiple depreciation books** (GAAP vs. tax) double your column count.
- **Category rollups** for the rollforward require careful `SUMIFS` that break when someone inserts a row.
- **Partial-period disposals** with gain/loss calculations add another layer of complexity. (For the journal entries on the disposal side — sale, retirement, trade-in under ASC 845, write-off, and casualty loss — see [Fixed Asset Disposal Journal Entries](/posts/fixed-asset-disposal-journal-entries/).)

None of these problems are unsolvable in Excel. But they require a carefully designed workbook with proper structure, validation, and protection so that a formula error in row 47 does not silently break your financial statements.

This is exactly the kind of problem we build templates to solve.

---

## The Pre-Built Alternative: Fixed Asset Rollforward Workbook

If you'd rather not build all of this from scratch, the [**Fixed Asset Rollforward Workbook**](/templates/fixed-assets/) ($79) handles everything in this post out of the box for up to 50 assets:

- Four depreciation methods (Straight-Line, Double-Declining Balance with auto-switch, Sum-of-Years, Units of Production)
- Mid-month and full-month conventions, applied per asset
- In-service date distinct from acquisition date (depreciation starts when *placed in service*, not invoiced — ASC 360-10-30-1)
- Leasehold Improvements automatically capped at the shorter of useful life or remaining lease term
- Disposal Log with gain/loss math + evidence trail (Authorization, Evidence Type, Counterparty)
- ASC 250 Change Log for useful-life and method revisions
- JE Generator with GL system presets (Generic / QuickBooks / NetSuite / Sage Intacct / Xero)
- Five-way reconciliation tab — Schedule = JE = Rollforward = Register = GL — with a diagnostic sub-section that ranks likely variance causes
- Print-ready Audit Confirmation Export tab for the auditor's PBC sample

[**Get the Workbook ($79) →**](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward)

Or [try the free 5-asset version](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free) first to see the mechanics on your own data.

---

## Related Resources

If you are building out your accounting infrastructure in Excel, these templates handle other common pain points for SaaS finance teams:

- **[ASC 606 Commission Capitalization Workbook](/templates/asc606/)** ($79) —Automates commission capitalization, amortization, and journal entries under ASC 340-40. If you are capitalizing sales commissions, this saves hours every month-end.
- **[ASC 842 Lease Accounting Workbook](/templates/asc842/)** ($97) —Full lease accounting schedule with ROU asset, lease liability, amortization, and journal entries. Handles both operating and finance leases.
- **[Startup Runway Calculator](/templates/runway/)** ($49) —Cash flow forecasting with two-rate revenue growth, departmental hiring plans, and scenario modeling for board-ready runway analysis.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
