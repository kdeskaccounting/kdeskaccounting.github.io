---
title: "ASC 842 Lease Accounting Excel Template (Free 3-Lease Version + Full 20-Lease Workbook)"
description: "ASC 842 lease accounting in Excel, without enterprise software: a free 3-lease template and the full 20-lease workbook. Operating, finance and short-term leases, escalating rent and free rent, journal entries, rollforward and disclosure table. No macros, no subscription."
summary: "The ASC 842 Lease Accounting Workbook handles your full lease portfolio — ROU asset calculation, lease liability amortization, escalating rent and free rent, period journal entries, balance sheet rollforward, and disclosure table — in a single Excel file you can trace and tie out."
date: 2026-03-16
lastmod: 2026-11-18
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 1
price: 249
buy_url: "https://kdeskaccounting.gumroad.com/l/phxigq"
free_url: "https://kdeskaccounting.gumroad.com/l/gljxc"
free_label: "Try free 3-lease version"
video_url: "https://github.com/kdeskaccounting/kdeskaccounting.github.io/releases/download/media-2026-09/asc842.mp4"
video_poster: "/images/products/asc842-poster.png"
youtube_url: "https://youtu.be/5lkrHbWlb4c"
tags: ["ASC 842", "lease accounting", "Excel template", "ROU asset", "lease amortization"]
compare:
  free_name: "Free 3-lease version"
  full_name: "Full workbook"
  rows:
    - ["Leases", "3", "20"]
    - ["Schedule length", "36 months", "120 months (payments up to 30 years)"]
    - ["Escalating rent, free rent, start- or end-of-month payments", "yes", "yes"]
    - ["Setup, Lease Data and Lease Schedule tabs", "yes", "yes"]
    - ["Operating and finance lease classification", "yes", "yes"]
    - ["JE Generator (your GL codes)", "no", "yes"]
    - ["Balance sheet rollforward", "no", "yes"]
    - ["Disclosure maturity table", "no", "yes"]
    - ["Reconciliation that ties to $0", "no", "yes"]
    - ["4-minute walkthrough video", "yes", "yes"]
faq:
  - q: "Does it handle both operating and finance leases?"
    a: "Yes. Each lease in Lease Data has a type dropdown: operating, finance or short-term exempt. The amortization schedule, JE Generator, and rollforward all adjust automatically."
  - q: "Does it work on a Mac?"
    a: "Yes. The workbook uses pure Excel formulas — no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac."
  - q: "What if I need to modify a lease mid-term?"
    a: "Modifications aren't automated. A modification is remeasured at the modification date, and changing a lease's inputs recalculates its whole history, so keep a copy of your closed periods before editing a lease."
  - q: "Can I use it for IFRS 16?"
    a: "The underlying PV math and amortization logic is identical. Classify all leases as Finance and the workbook produces depreciation and interest output consistent with IFRS 16 treatment. Income statement presentation and cash flow classification differ between ASC 842 and IFRS 16, but the schedule mechanics are the same."
  - q: "What if I have more than 20 leases?"
    a: "Email hello@kdeskaccounting.com — we can discuss a custom build."
---

## ASC 842 Lease Accounting Without Enterprise Software

**Stop paying for lease accounting software when all you need are schedules you can trace and tie out.**

KDesk gives controllers a structured Excel workbook for operating, finance and short-term leases: ROU asset and liability calculations, escalating rent and free rent, monthly journal entries, balance sheet rollforwards and disclosure support.

No subscription. No new software platform. No black-box calculations.

> "I need to make a change from LeaseQuery, because we didn't need such a robust software. I evaluated this Lease Accounting Workbook against the numbers from my current software and they were almost identical. I would highly recommend this template for your lease tracking needs."
>
> Paula Ward, Controller

**$249. One-time purchase. Built for teams managing up to 20 leases.**

[Get the Workbook ($249) →](https://kdeskaccounting.gumroad.com/l/phxigq)

---

## What's in the Workbook

Eight working tabs plus an Instructions tab. You enter data in Setup and Lease Data (and, if a lease has an irregular rent schedule, the Payment Schedule). Every other tab calculates automatically.

### Setup

Company name, GL account codes, default IBR, default payment timing (beginning or end of month), the mid-month commencement convention, and the Selected Period. The JE Generator, Rollforward, Reconciliation and Dashboard all read the Selected Period. Change it once and every tab moves to that month.

### Lease Data (20-lease capacity)

One row per lease: name, type (operating, finance or short-term exempt), asset class, commencement date, term (1 to 360 months), base monthly payment, IBR, initial direct costs and lease incentives. Then the payment terms: payment timing, free-rent months, and an escalation (a percentage or a fixed dollar step every N months, 12 by default). The lease liability and ROU asset calculate from your inputs, and an Input Check column flags anything missing or out of range.

### Payment Schedule

One row per lease, one column per month, out to 360 months. Each month is filled in from Lease Data with free rent and escalations applied, and every calculation in the workbook reads from this tab. If a lease doesn't follow a neat pattern, type the actual payment over any month: typed months turn orange so you can see what was overridden.

### Lease Schedule

Pick any lease from the dropdown to see its amortization table for the first 120 months: beginning liability, interest, payment, principal, ending liability, and the ROU asset roll (single lease cost for operating leases; depreciation and interest for finance leases). Each month's closing balance is the next month's opening balance, and the liability and ROU asset both close to zero at the end of the term.

### JE Generator

Aggregated journal entries for the Selected Period, using your GL codes: operating lease cost, interest and ROU amortization; finance lease depreciation, interest and principal; short-term lease expense, including the straight-line adjustment to accrued or prepaid rent when a short-term lease has free rent or an escalation. Debits equal credits, and a lease-by-lease detail table below shows where each number comes from.

### Rollforward

Beginning balance, additions, reductions and ending balance for operating and finance lease liabilities, ROU assets and short-term accrued rent. Current versus long-term split of the liability at period end, and the ASC 842-20-50 maturity analysis: undiscounted payments by year for five years and thereafter, less imputed interest, back to the present value of the liability.

### Reconciliation

Ties the JE Generator to the lease schedules for the Selected Period: interest, payments, total expense, cash paid against the Payment Schedule, and the short-term accrued rent movement. Every variance should read $0; anything else points you to the problem.

### Dashboard

Total lease liability, net ROU assets, period expense, active lease count and operating/finance mix, with a one-line summary for every lease.

---

## A Worked Example — Office Lease, Month 1

To make the mechanics concrete: a 36-month office lease at $5,000/month paid at the end of each month, 6% IBR, no initial direct costs or incentives, no escalation.

**Opening lease liability** = PV(6%/12, 36, 5000) = **$164,355**

**ROU asset** = $164,355 (equal to liability when no IDC or incentives)

**Month 1 amortization schedule:**

| Column | Month 1 |
|--------|---------|
| Beginning liability | $164,355 |
| Interest accrual (6%/12 × $164,355) | $822 |
| Cash payment | $5,000 |
| Principal reduction | $4,178 |
| Ending liability | $160,177 |
| ROU asset amortization | $4,178 |
| Ending ROU balance | $160,177 |

**JE Generator output for Month 1:**

```
DR  Lease Expense               5,000
DR  Lease Liability             4,178
    CR  Cash                              5,000
    CR  Right-of-Use Asset                4,178
```

All of this is automatic. You enter the inputs in Lease Data; every number is calculated for every month of the term. With rent paid at the start of each month instead, or with an escalation or free rent, the workbook builds the payments on the Payment Schedule and discounts them accordingly.

---

## Finance Lease — How It Differs

Finance leases use a different income statement treatment: straight-line depreciation on the ROU asset plus front-loaded interest expense on the liability. The JE Generator handles both types automatically based on the lease classification you enter in Lease Data.

Example: $2,500/month equipment lease, 48 months, 7% IBR.

- Opening liability = PV(7%/12, 48, 2500) = $104,401
- Monthly depreciation = $104,401 ÷ 48 = $2,175
- Month 1 interest = $104,401 × 7%/12 = $609

Month 1 JE Generator output:

```
DR  Depreciation Expense        2,175
DR  Interest Expense              609
DR  Lease Liability             1,891
    CR  Accumulated Depreciation          2,175
    CR  Cash                              2,500
```

The workbook generates separate depreciation and interest lines for finance leases automatically. No manual split required.

---

## Short-Term Lease Exemption

Mark a lease as "Short-term Exempt" in Lease Data and the workbook skips ROU asset and liability recognition entirely. Expense is recognized straight-line over the term (total payments ÷ term), so free rent or an escalation on a short-term lease builds accrued or prepaid rent rather than lumpy expense. The short-term election is made per lease — you can mix short-term and capitalized leases in the same workbook.

---

## Who This Is For

- Controllers at Series A–C SaaS companies implementing ASC 842 for the first time
- Finance managers maintaining a fragile manual lease spreadsheet that breaks when leases change
- Companies with 1–20 active leases that want schedules they can trace line by line
- Teams preparing for their first audit or audit committee review
- Any finance team spending more than 2 hours per month close on lease journal entries

---

## What It Is Not

This workbook is designed for companies with up to 20 leases. If you have 50–100+ leases, purpose-built lease accounting software (iLease, LeaseQuery, Occupier) is the right tool. This workbook does not handle lessor accounting, sale-leaseback accounting, or real-time system integration. It is a standalone Excel file — there is no cloud sync, no API, no subscription.

---

## Technical Specifications

| Specification | Detail |
|---------------|---------|
| Lease capacity | 20 leases |
| Lease term | 1 to 360 months (Lease Schedule tab displays the first 120) |
| Lease types | Operating, finance and short-term exempt |
| Excel version | 2016, 365, Mac (no macros) |
| File format | .xlsx |
| Inputs | Yellow input cells; everything else is a formula |
| Price | $249 one-time |

---

## Get the Workbook

[**Get the Workbook ($249) →**](https://kdeskaccounting.gumroad.com/l/phxigq)

Not ready to buy? [Try the free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc) — the Setup, Lease Data and Lease Schedule tabs for 3 leases and 36 months, so you can check the math on your own leases. The JE Generator, rollforward, disclosure table and reconciliation are in the full workbook (see the comparison above).

---

## Frequently Asked Questions

**Does it handle both operating and finance leases?**
Yes. Each lease in Lease Data has a type dropdown: operating, finance or short-term exempt. The amortization schedule, JE Generator, and rollforward all adjust automatically.

**Does it work on a Mac?**
Yes. The workbook uses pure Excel formulas — no VBA macros, no Windows-only features. It works on Excel 2016, Excel 365, and Excel for Mac.

**What if I need to modify a lease mid-term?**
Update the inputs in Lease Data (new term, new payment, new IBR as of the modification date). The schedule recalculates from that point. You handle the remeasurement journal entry in your accounting system using the output from the JE Generator.

**Can I use it for IFRS 16?**
The underlying PV math and amortization logic is identical. Classify all leases as "Finance" and the workbook produces depreciation + interest output consistent with IFRS 16 treatment. Income statement presentation and cash flow classification differ between ASC 842 and IFRS 16, but the schedule mechanics are the same.

**What if I have more than 20 leases?**
Email [hello@kdeskaccounting.com](mailto:hello@kdeskaccounting.com) — we can discuss a custom build.
