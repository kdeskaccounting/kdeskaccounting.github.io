---
title: "Startup Burn Rate Formula: How to Calculate It in Excel (With Template)"
date: 2026-03-19
description: "Learn the startup burn rate formula for gross and net burn, build a dynamic calculator in Excel, and download a ready-made template."
summary: "Burn rate is the single number that tells you how long your startup can survive. This guide walks through the gross and net burn formulas, shows you how to build a dynamic burn rate model in Excel with real cell references, and flags the mistakes that make most spreadsheet models dangerously optimistic."
tags: ["startup burn rate calculator", "burn rate formula", "Excel", "Excel template", "cash flow", "SaaS accounting", "startup finance"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 10
---

If you manage cash at a SaaS startup, burn rate is the number your CEO asks about in every board deck and every Monday standup. It sounds simple —total cash out minus total cash in —but the spreadsheet you build around it determines whether your runway estimate is trustworthy or dangerously optimistic.

This guide covers the exact formulas, a worked example with real numbers, and the modeling choices that separate a back-of-napkin guess from something you can hand to your board.

---

## What Is Burn Rate (Gross vs. Net)

There are two versions of burn rate, and you need both.

**Gross burn rate** is your total cash operating expenditures in a period, ignoring revenue entirely. It answers: "If every customer disappeared tomorrow, how fast would we bleed cash?"

```excel
Gross Burn Rate = Total Cash Operating Expenses (per month)
```

**Net burn rate** is gross burn minus cash revenue. It answers: "At our current trajectory, how much cash are we actually consuming each month?"

```excel
Net Burn Rate = Total Cash Operating Expenses - Total Cash Revenue (per month)
```

A company spending $200,000/month with $60,000/month in cash collections has a gross burn of $200,000 and a net burn of $140,000. Those are meaningfully different numbers, and your board expects to see both.

**Runway** follows directly:

```excel
Runway (months) = Current Cash Balance / Net Burn Rate
```

We cover runway modeling in depth in [How to Calculate Startup Runway](/posts/how-to-calculate-startup-runway/). This post focuses on getting the burn rate inputs right.

---

## How to Calculate Burn Rate in Excel —Step by Step

Here is a minimal burn rate model you can build in a blank workbook in fifteen minutes. We will extend it into a dynamic model in a later section.

### Layout

| Row | Column A | Column B | Column C |
|-----|----------|----------|----------|
| 1 | **Burn Rate Calculator** | | |
| 3 | Starting Cash Balance | $2,000,000 | |
| 4 | Monthly Expenses | $200,000 | |
| 5 | Monthly Revenue | $60,000 | |
| 7 | Gross Burn Rate | *(formula)* | |
| 8 | Net Burn Rate | *(formula)* | |
| 9 | Runway (months) | *(formula)* | |

### Formulas

Put your inputs in `B3:B5` (yellow fill, unlocked). Then:

```excel
B7 =B4
```

Gross burn is simply your total monthly expenses.

```excel
B8 =B4-B5
```

Net burn subtracts revenue from expenses. If your revenue exceeds expenses, net burn is negative —you are cash-flow positive.

```excel
B9 =IF(B8<=0, "Cash flow positive", B3/B8)
```

The `IF` guard prevents a misleading negative runway number when net burn is zero or negative.

This is the static version. It gives you a single snapshot. The problem is that burn rate is not static —and pretending it is will get you in trouble.

---

## Worked Example: Month-by-Month Burn Schedule

Let us take those same inputs and project them forward over twelve months, assuming expenses and revenue both grow.

**Assumptions:**

- Starting cash: $2,000,000
- Month 1 expenses: $200,000, growing 3% per month (new hires ramping)
- Month 1 revenue: $60,000, growing 8% per month (sales pipeline converting)

| Month | Expenses | Revenue | Net Burn | Ending Cash |
|-------|----------|---------|----------|-------------|
| 1 | $200,000 | $60,000 | $140,000 | $1,860,000 |
| 2 | $206,000 | $64,800 | $141,200 | $1,718,800 |
| 3 | $212,180 | $69,984 | $142,196 | $1,576,604 |
| 4 | $218,545 | $75,583 | $142,963 | $1,433,641 |
| 5 | $225,102 | $81,629 | $143,472 | $1,290,169 |
| 6 | $231,855 | $88,160 | $143,695 | $1,146,474 |
| 7 | $238,810 | $95,212 | $143,598 | $1,002,876 |
| 8 | $245,975 | $102,829 | $143,146 | $859,730 |
| 9 | $253,354 | $111,056 | $142,299 | $717,432 |
| 10 | $260,955 | $119,940 | $141,015 | $576,417 |
| 11 | $268,783 | $129,535 | $139,248 | $437,168 |
| 12 | $276,847 | $139,898 | $136,949 | $300,219 |

Notice what happens: net burn peaks around month 6 and then starts declining as revenue growth outpaces expense growth. A flat burn rate assumption of $140,000/month would have told you runway is about 14 months. The dynamic model shows you still have cash at month 12, but it also shows the peak burn period where you are most vulnerable.

### Excel formulas for the monthly schedule

Assume Month 1 starts in row 2, with headers in row 1. Column layout: A = Month, B = Expenses, C = Revenue, D = Net Burn, E = Ending Cash.

```excel
B2 =200000
B3 =B2*(1+0.03)
```

```excel
C2 =60000
C3 =C2*(1+0.08)
```

```excel
D2 =B2-C2
D3 =B3-C3
```

```excel
E2 =2000000-D2
E3 =E2-D3
```

Copy rows 3 through 13 down to fill twelve months. The growth rate percentages (3% and 8%) should be pulled from named input cells, not hardcoded in the formula —that way you can run scenarios instantly.

---

## Why a Flat Burn Rate Is Misleading

Most burn rate calculations you see online use a single number: "We burn $140k/month." That figure is accurate for exactly one month. Here is why it breaks down:

**Expenses ramp.** Every new hire you onboard increases payroll. Office leases step up. AWS bills grow with usage. If you are a Series A startup planning to double headcount, your month-12 expenses will look nothing like month-1.

**Revenue grows (hopefully).** SaaS revenue compounds. If you are growing MRR at 10% month-over-month, your net burn rate is declining even if gross burn rises. A flat model misses the inflection point entirely.

**One-time costs distort the average.** A $50,000 security audit or a $30,000 conference sponsorship in one month does not represent your ongoing burn. You need to separate recurring operating expenses from one-time items, or your trailing average will be wrong.

The fix is a dynamic model that separates expense growth from revenue growth and lets you toggle assumptions. That is what we build next.

---

## How to Build a Dynamic Burn Rate Model

A production-quality burn rate model needs five things:

### 1. Input panel with growth rates

Dedicate a section (or a separate Setup sheet) to assumptions:

```excel
Starting Cash Balance       $2,000,000
Monthly Operating Expenses  $200,000
Monthly Cash Revenue        $60,000
Expense Growth Rate (mo)    3.0%
Revenue Growth Rate (mo)    8.0%
Reporting Frequency         Monthly
```

Every one of these should be a named range or a fixed cell reference. Nothing downstream should contain a hardcoded number.

### 2. Period generation with frequency logic

If your board wants quarterly reporting, you need the model to aggregate automatically. Use a frequency toggle:

```excel
=IF($C$6="Monthly", 1, IF($C$6="Quarterly", 3, 12))
```

Then compound growth rates by the number of months per period:

```excel
=B_prev * (1 + ExpenseGrowthRate) ^ PeriodMonths
```

### 3. Cumulative cash waterfall

Each period's ending cash feeds the next period's opening cash:

```excel
Opening Cash (Period N) = Ending Cash (Period N-1)
Ending Cash (Period N)  = Opening Cash (Period N) - Net Burn (Period N)
```

This is a rollforward. The closing balance must equal the next period's opening balance —if it does not, your model has a structural error.

### 4. Runway detection

Add a row that flags the first period where ending cash goes negative:

```excel
=IF(E2<=0, "OUT OF CASH", "")
```

Or calculate the exact month using interpolation:

```excel
=IF(E2>0, "", "Cash runs out in Month "&A2-1&" + "&TEXT(E_prev/(E_prev-E2),"0.0")&" months")
```

### 5. Scenario analysis

At minimum, build three columns: Base, Downside, and Upside. Change the revenue growth rate and expense growth rate for each scenario. Your board will ask for this —have it ready.

| Scenario | Expense Growth | Revenue Growth | Runway |
|----------|---------------|----------------|--------|
| Base | 3% | 8% | 16 months |
| Downside | 5% | 4% | 11 months |
| Upside | 2% | 12% | 22 months |

The spread between downside and upside is the information your CEO actually needs for fundraising timing.

---

## Common Mistakes

**Confusing MRR with cash.** Monthly Recurring Revenue is an accrual metric. If you bill annually and recognize monthly, your cash collections in month 1 are twelve times your MRR. Use actual cash receipts in your burn model, not recognized revenue. If you need help with the revenue recognition side, the [ASC 606 Commission Capitalization Workbook](/templates/asc606/) handles the accrual-to-cash bridge for commission expenses.

**Ignoring one-time costs.** That $80,000 security deposit on your new office, the $40,000 legal bill for your Series B docs —these hit cash but are not part of your recurring burn. Strip them out of the trailing average or flag them separately. Otherwise your "burn rate" jumps 30% in one month and your board panics.

**Not stress-testing the downside.** Every burn rate model should answer: "What if revenue growth stalls for three months?" If your model only has one scenario, you are not modeling —you are hoping. Build at least a base and a downside case.

**Using trailing averages without context.** A three-month trailing average of net burn is useful, but only if those three months are representative. If you just closed a large annual deal, your trailing cash receipts are inflated. Normalize for timing.

**Forgetting non-cash lease and compensation costs.** If you have operating leases under [ASC 842](/templates/asc842/) or stock-based compensation, those hit your P&L but not your cash. Make sure your burn rate model uses cash expenses, not GAAP expenses. The difference can be material at a startup with significant equity comp.

---

## Skip the Build: Use the Runway Calculator Template

Everything described above —the input panel, dynamic growth rates, monthly/quarterly/annual frequency toggle, scenario analysis, and automatic runway detection —is already built, tested, and audit-ready in the [KDesk Startup Runway Calculator](/templates/runway/).

What you get:

- **Setup sheet** with all assumptions in one place (starting cash, expenses, revenue, two-phase growth rates, reporting frequency)
- **Monthly projection** that compounds expenses and revenue separately, with a cash waterfall that flags exactly when you hit zero
- **Dashboard** with gross burn, net burn, runway in months, and a month-by-month schedule
- **Pre-built formulas** with null-safety, error handling, and locked formula cells so your team cannot accidentally break the model
- **Works in Excel and Google Sheets** —no macros, no plugins

**Price: $49** —less than one hour of controller time to build it from scratch.

[Get the Startup Runway Calculator ($49) →](/templates/runway/)

Want to test the layout first? Grab the [free version](https://kdeskaccounting.gumroad.com/l/runway-calculator-free) with limited periods, then upgrade when you need the full model.

---

## Related Resources

- [How to Calculate Startup Runway](/posts/how-to-calculate-startup-runway/) —deep dive on runway modeling, including fundraising timing and scenario planning
- [ASC 606 Commission Capitalization Workbook](/templates/asc606/) ($79) —automates the commission expense accrual and amortization schedule that feeds into your burn rate
- [ASC 842 Lease Accounting Workbook](/templates/asc842/) ($97) —handles lease liability and ROU asset schedules, so you can separate cash rent from GAAP lease expense in your burn model
- [Browse all templates →](/templates/)

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
