---
title: "ASC 842 Amortization Schedule: How to Build One in Excel"
date: 2026-03-16
description: "Step-by-step guide to building an ASC 842 lease amortization schedule in Excel. Covers PV calculation, monthly columns, running balances, and the maintenance problem at scale."
summary: "Building an ASC 842 amortization schedule in Excel is manageable for one lease. With five or more, the manual approach breaks down fast. Here's exactly how the schedule works — and what it takes to maintain it at scale."
tags: ["ASC 842", "lease accounting", "amortization schedule", "Excel", "Excel template", "lease amortization", "GAAP"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 6
---

Every lease you capitalize under ASC 842 needs an amortization schedule — a period-by-period table showing exactly how the lease liability and ROU asset move from commencement to zero. For one lease, building it in Excel takes a few hours. For five or more, maintaining it every close becomes a significant problem.

This guide walks through exactly how the schedule works, step by step, with a concrete example you can follow.

---

## What an ASC 842 Amortization Schedule Does

The amortization schedule tracks two balance sheet items simultaneously from lease commencement to lease end:

1. **Lease liability** — starts at the present value of all future payments and declines each period as principal is paid down
2. **ROU (right-of-use) asset** — starts at the lease liability (adjusted for IDC and incentives) and amortizes to zero at lease end

Both balances must reach exactly $0 at the end of the lease term. If they don't, something is wrong with your inputs or formulas.

The schedule also generates the numbers that feed your journal entries, your balance sheet rollforward, and your ASC 842 disclosure footnotes.

---

## Data Inputs You Need

Before building the schedule, collect these inputs for each lease:

| Input | What it drives |
|-------|---------------|
| Commencement date | Period 1 date, determines when amortization starts |
| Lease term (months) | Number of rows in the schedule |
| Monthly payment | Cash payment column; used in PV calculation |
| Incremental borrowing rate (IBR) | Interest accrual each period; PV of payments |
| Initial direct costs (IDC) | Added to opening ROU asset |
| Lease incentives received | Subtracted from opening ROU asset |
| Prepaid rent | Added to opening ROU asset |
| Lease type (operating or finance) | Determines ROU amortization method |

If you don't know the IBR, it's the rate your company would pay to borrow a similar amount over a similar term with similar collateral — typically obtained from your bank or estimated from your recent borrowing rates.

---

## Step 1 — Calculate the Opening Lease Liability

The opening lease liability is the present value of all future lease payments, discounted at the IBR.

Excel formula:

```
=PV(IBR/12, lease_term_months, -monthly_payment)
```

**Example:** 36-month office lease, $5,000/month payment, 6% IBR.

```
=PV(6%/12, 36, -5000)  →  $164,029
```

A few things to note:

- The payment must be negative in the PV formula (it's a cash outflow). If you omit the negative sign, Excel returns a negative liability — a common error.
- The undiscounted sum of all payments = $5,000 × 36 = $180,000. The present value = $164,029. The difference ($15,971) is the imputed interest you'll recognize over the lease term.
- For leases with variable payments, use the in-substance fixed payment amounts per ASC 842-20-30-5.

---

## Step 2 — Calculate the Opening ROU Asset

The ROU asset at commencement equals:

```
ROU Asset = Lease Liability + Initial Direct Costs + Prepaid Rent − Lease Incentives Received
```

For our example with $2,000 in IDC and a $3,000 tenant improvement allowance (TIA):

```
ROU Asset = $164,029 + $2,000 + $0 − $3,000 = $163,029
```

When there are no IDC, prepaid rent, or incentives — which is most office and vehicle leases — the ROU asset equals the lease liability at commencement. That's the simple case.

---

## Step 3 — Build the Monthly Schedule Columns

The schedule has 10 columns. Build one row per period, from Period 1 through Period N (where N = lease term in months).

| Column | What it calculates |
|--------|-------------------|
| Period | Sequential number (1, 2, 3…) |
| Date | Commencement date + period − 1 months |
| Beginning Liability | Period 1: opening PV; subsequent periods: prior period ending liability |
| Interest Accrual | Beginning Liability × IBR/12 |
| Cash Payment | Fixed monthly payment (from inputs) |
| Principal Reduction | Cash Payment − Interest Accrual |
| Ending Liability | Beginning Liability + Interest Accrual − Cash Payment |
| Beginning ROU Balance | Period 1: opening ROU asset; subsequent periods: prior ending ROU |
| ROU Amortization | Operating: same as Principal Reduction (plug to straight-line); Finance: ROU asset ÷ lease term |
| Ending ROU Balance | Beginning ROU − ROU Amortization |

**Critical distinction — ROU amortization method by lease type:**

- **Operating lease:** ROU amortization = Principal Reduction. This is the plug that makes total lease expense (interest + ROU amortization) equal the straight-line monthly payment. The income statement shows a single flat "Lease Expense" line.
- **Finance lease:** ROU amortization = ROU asset ÷ lease term (straight-line). The income statement shows separate "Depreciation Expense" and "Interest Expense" lines, with total expense front-loaded.

---

## Step 4 — Verify Period 1 Math

For the example lease ($5,000/month, 36 months, 6% IBR, $163,029 opening ROU):

| Column | Period 1 value |
|--------|---------------|
| Period | 1 |
| Date | Commencement date |
| Beginning Liability | $164,029 |
| Interest Accrual | $164,029 × 6%/12 = $820 |
| Cash Payment | $5,000 |
| Principal Reduction | $5,000 − $820 = $4,180 |
| Ending Liability | $164,029 + $820 − $5,000 = $159,849 |
| Beginning ROU | $163,029 |
| ROU Amortization | $4,180 (operating lease plug) |
| Ending ROU | $163,029 − $4,180 = $158,849 |

Your Period 1 journal entry (operating lease):

```
DR  Lease Expense               5,000
DR  Lease Liability             4,180
    CR  Cash                              5,000
    CR  Right-of-Use Asset                4,180
```

If these numbers match, your schedule is set up correctly. If the interest accrual or principal reduction are off, check your IBR input (it should be the annual rate, not monthly — divide by 12 in the formula).

For the full set of monthly entries — operating vs. finance, plus termination — see [ASC 842 Journal Entries: A Complete Guide with Examples](/posts/asc-842-journal-entries/).

---

## Step 5 — Running to Period 36

Each row references the prior row for beginning balances. The liability declines as principal payments exceed interest. In the final periods:

| Period | Beginning Liability | Interest | Payment | Principal | Ending Liability |
|--------|--------------------:|--------:|--------:|----------:|----------------:|
| 34 | $14,637 | $73 | $5,000 | $4,927 | $9,710 |
| 35 | $9,710 | $49 | $5,000 | $4,951 | $4,759 |
| 36 | $4,759 | $24 | $4,783 | $4,759 | $0 |

In the final period, the payment is slightly less than $5,000 due to rounding. The ending liability in Period 36 should be exactly $0. Same for the ending ROU balance.

---

## The Disclosure Numbers Your Auditors Want

ASC 842 requires a maturity analysis of lease liabilities in the footnotes. The schedule generates this directly — sum the cash payment column by year:

| Maturity bucket | Calculation | Amount |
|----------------|-------------|--------|
| Within 1 year | Periods 1–12 cash payments | $60,000 |
| 1–3 years | Periods 13–36 cash payments | $120,000 |
| 3–5 years | Periods 37–60 cash payments | — |
| Beyond 5 years | Periods 61+ cash payments | — |
| Total undiscounted | Sum of all payments | $180,000 |
| Less: imputed interest | Total − PV | ($15,971) |
| **Total lease liability** | **PV of payments** | **$164,029** |

The total lease liability in the maturity analysis should tie exactly to the balance sheet.

---

## Why Manual Excel Schedules Break at Scale

Building the schedule for one lease takes a few hours. Maintaining it across 5–20 leases creates five specific failure modes:

**1. Multiple commencement dates.** Each lease starts on a different date and has a different term. Building one Schedule tab per lease creates a fragile workbook that's hard to aggregate for the journal entry and disclosure.

**2. Lease modifications.** A lease extension or payment change requires remeasuring the liability. If your schedule uses chained row references, a modification mid-schedule requires manually rebuilding all subsequent rows.

**3. Period-close aggregation.** Your JE Generator needs the total interest, depreciation, and principal across all leases for the selected period. Manually summing across 10 separate schedule tabs takes 30–60 minutes per close and is error-prone.

**4. Audit traceability.** Auditors want to trace each balance sheet line back to the underlying schedule. With a manual workbook, this tracing is manual and slow.

**5. Error compounding.** Chained formulas mean one wrong input in Period 1 propagates through all 120 periods. Non-chained PV formulas calculate each period independently, so errors don't compound.

---

## Build It Yourself or Use a Pre-Built Workbook

If you have one or two leases and stable terms, building this in Excel is a reasonable half-day project. Follow the steps in this guide, test the final-period zero balance, and document your IBR assumption.

If you have 5–20 leases, different commencement dates, or lease modifications in your history, the maintenance burden of a manual schedule adds up fast. The [ASC 842 Lease Accounting Workbook](/templates/asc842/) handles 20 leases with 120-month schedules per lease, non-chained PV formulas, period-level JE aggregation, and a reconciliation tab — all in one Excel file.

[**Get the Workbook ($97) →**](https://kdeskaccounting.gumroad.com/l/phxigq)

[Try the free 3-lease version →](https://kdeskaccounting.gumroad.com/l/gljxc)

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
