---
title: "LeaseQuery or Excel? How to Tell Which Your Lease Portfolio Needs"
date: 2026-11-19
lastmod: 2026-11-19
description: "A LeaseQuery alternative for small lease portfolios: when an Excel workbook is enough for ASC 842, when lease accounting software earns its subscription, where LeaseGuru fits, and how to test one against the other with a real lease."
summary: "Lease accounting software is built for large portfolios that change often. If you have a handful of leases that rarely change, an Excel workbook may do the same job. Here is how to tell which side you are on, and how to check the numbers before you switch."
tags: ["LeaseQuery alternative", "lease accounting software", "ASC 842", "lease accounting", "Excel template", "LeaseGuru", "FinQuery"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
product: asc842
images: ["/images/og/asc842.png"]
faq:
  - q: "Is there a cheaper alternative to LeaseQuery for a small lease portfolio?"
    a: "Two are worth a look. LeaseGuru is FinQuery's own product for small portfolios: free for up to 2 leases, with paid plans for 10 and 15 leases. An Excel workbook is the other. The KDesk ASC 842 workbook covers up to 20 leases for a one-time $249. Software gives you the vendor's controls and support; a workbook gives you formulas you can read and no subscription."
  - q: "Can I do ASC 842 lease accounting in Excel?"
    a: "Yes, if the portfolio is small and stable. Excel handles the present value, the amortization schedule, the journal entries and the rollforward. What it does not give you is a system audit trail, user access controls or automatic handling of lease modifications, so those become your own review and version-control steps."
  - q: "Will an Excel workbook match the numbers from my lease accounting software?"
    a: "It should come within a few dollars once the conventions match. Differences usually come from payment timing (start or end of the month), how a mid-month start is treated, and whether interest accrues by month or by actual days. Run one real lease through both and compare the opening liability and the first month of interest."
  - q: "How many leases is too many for a spreadsheet?"
    a: "There is no line in the standard. The KDesk workbook holds 20 leases. Past that, or if your leases are modified often, lease accounting software is the better tool."
---

Lease accounting software is built for companies with large portfolios that change often. Plenty of companies paying for it have six leases and one renewal a year.

If that is you, this page is about whether an Excel workbook would do the same job. It covers what LeaseQuery is built for, when to stay on it, when a workbook is enough, and how to check the numbers on a real lease before you decide.

## What LeaseQuery Is Built For

LeaseQuery is lease accounting software from FinQuery. The company took the FinQuery name in February 2024 and kept LeaseQuery as the name of the lease product.

Its product page lists what you would expect from a system built for scale:

- ASC 842, IFRS 16, GASB 87 and GASB 96, with dual-standard reporting
- An audit trail with lease change history, and SOC 1 Type 2 reports on its controls
- Role-based access, read-only access for auditors, and locked journal entries
- Integrations with ERP and general ledger systems
- Multi-currency remeasurement and translation

Pricing is by quote.

If you need most of that list, you need the software. The question is whether you do.

## When to Stay on Lease Software

Stay where you are if any of these describe you:

- **You have more than 20 leases**, or expect to within a year.
- **Your leases change often.** Every modification has to be remeasured at the modification date. Software does that inside the system. In a spreadsheet you do it by hand.
- **You report under GASB**, or under two standards at once.
- **Your auditors rely on system controls.** A spreadsheet has no audit trail and no user permissions. Your controls become a reviewer's sign-off and a saved copy of each closed period.
- **You are a lessor**, or you have sale-leasebacks or leases in foreign currencies.
- **You want lease entries posted to the ledger automatically.**

## When Excel Is Enough

A workbook fits when the portfolio is small and quiet:

- 20 leases or fewer
- Fixed rent, with or without escalations and free-rent months
- Changes are rare: a renewal or a new lease once or twice a year
- One or two people prepare the entries, and someone else reviews them
- You would like to see every formula behind every number

The [KDesk ASC 842 workbook](/templates/asc842/) is built for that case. You enter each lease once: commencement date, term, payment, discount rate, payment timing, escalations and free rent. It produces the amortization schedule, the monthly journal entries with your GL codes, the balance sheet rollforward, the maturity table for the disclosure, and a reconciliation that should read $0. It costs $249 once.

It does not automate modifications. It does not handle lessor accounting or sale-leasebacks, and it does not connect to your ledger. If you need those, see the list above.

## The Middle Option: LeaseGuru

FinQuery sells a smaller product called LeaseGuru for small portfolios, and it belongs in this comparison.

LeaseGuru is free for up to 2 leases. Paid plans cover 10 leases or 15 leases, and 15 is the ceiling for a single company. When this page was written, FinQuery's site showed the 10-lease plan at $999 a year in one place and $1,099 in another, and the 15-lease plan at $1,750 and $1,925. Check [their page](https://finquery.com/guru/) for the current price.

| | LeaseQuery | LeaseGuru | KDesk workbook |
|---|---|---|---|
| Leases | Unlimited | 2 free; 10 or 15 paid | 20 |
| Price | By quote | Free, or about $1,000 to $1,925 a year | $249 once |
| Standards | ASC 842, IFRS 16, GASB 87 and 96 | ASC 842, IFRS 16 | ASC 842 |
| Lease modifications | Calculated in the system | Amend the lease in the system | Done by hand |
| Controls | Audit trail, SOC 1 Type 2 reports, user roles | Auditor access | Your own review and saved copies |
| Where the numbers live | The vendor's system | The vendor's system | An Excel file you own |

If you have one or two leases, LeaseGuru's free plan is hard to beat. Between 3 and 20 leases, the choice is between a yearly subscription with a vendor behind it and a one-time workbook you run yourself.

## How to Test One Against the Other

You can check a workbook against your current software in about half an hour, before you spend anything.

1. Download the [free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc) of the workbook.
2. Enter one real lease: commencement date, term, monthly payment, discount rate, and whether rent is paid at the start or the end of the month. Add any escalation or free-rent months.
3. Compare three numbers with your software: the opening lease liability, the first month's interest, and the liability at a month end you have already closed. The free version shows the first 36 months of each lease.

If the numbers are a few dollars apart, the cause is usually a convention:

- **Payment timing.** Rent paid at the start of the month discounts differently from rent paid at the end. The workbook has a setting for this.
- **Mid-month starts.** Systems differ on how they treat a lease that begins on the 15th. The workbook has a setting for this too.
- **Day counts.** The workbook accrues interest by month, at the annual rate divided by 12. A system that counts actual days will show a slightly different liability each month. The payments are the same either way.

A controller did exactly this test before buying:

> "I need to make a change from LeaseQuery, because we didn't need such a robust software. I evaluated this Lease Accounting Workbook against the numbers from my current software and they were almost identical. I would highly recommend this template for your lease tracking needs."
>
> Paula Ward, Controller

## If You Decide to Switch

Three things to do before the subscription ends:

1. **Export everything.** Save the schedules, journal entries and disclosure reports for every closed period. You will want them for the audit.
2. **Compare balances at the cutover date.** Set up every lease in the workbook and compare its lease liability and right-of-use asset with your ledger at the month you plan to switch. Expect small differences from the conventions above.
3. **Talk to your auditor first.** Tell them what is changing and agree how to treat any difference at cutover before you book anything.

## Related Guides

- [ASC 842 Lease Accounting: The Complete Guide](/posts/asc-842-lease-accounting-guide/)
- [ASC 842 Amortization Schedule: How to Build One in Excel](/posts/asc-842-amortization-schedule-excel/)
- [ASC 842 Journal Entries](/posts/asc-842-journal-entries/)
- [The ASC 842 Lease Accounting Workbook](/templates/asc842/)

*LeaseQuery and LeaseGuru are products of FinQuery, LLC. KDesk Accounting is not affiliated with FinQuery. Product details and prices above come from FinQuery's website in November 2026 and may have changed.*
