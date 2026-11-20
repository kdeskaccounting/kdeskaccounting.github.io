---
title: "LeaseQuery or Excel? How to Tell Which Your Lease Portfolio Needs"
date: 2026-11-19
lastmod: 2026-11-19
description: "A LeaseQuery alternative for small lease portfolios: when an Excel workbook is enough for ASC 842, when lease accounting software is worth its cost, where LeaseGuru fits, and how to test one against the other with a real lease."
summary: "Lease accounting software earns its cost on large portfolios that change often. If you have a handful of leases that rarely change, an Excel workbook may do the same job. Here is how to tell which side you are on, and how to check the numbers before you switch."
tags: ["LeaseQuery alternative", "lease accounting software", "ASC 842", "lease accounting", "Excel template", "LeaseGuru", "FinQuery"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
# Ranked first on /posts/ and the home page at Stephen's request, 2026-11-19 ("for now").
# It shares weight 1 with the ASC 606 commissions guide; Hugo breaks the tie by date, newest first.
# To drop it back down the list, delete the weight line.
weight: 1
product: asc842
images: ["/images/og/asc842.png"]
faq:
  - q: "Is there a LeaseQuery alternative for a small lease portfolio?"
    a: "Two are worth a look. LeaseGuru is FinQuery's own product for small portfolios: free for up to 2 leases, with paid plans for 10 and 15 leases. An Excel workbook is the other. The KDesk ASC 842 workbook covers up to 20 leases for a one-time $249. Software gives you a hosted system; a workbook gives you formulas you can read and no subscription."
  - q: "Can I do ASC 842 lease accounting in Excel?"
    a: "Yes, if the portfolio is small and stable. Excel handles the present value, the amortization schedule, the journal entries and the rollforward. What it does not give you is a system audit trail, role-based access or automatic handling of lease modifications, so those become your own review and version-control steps."
  - q: "Will an Excel workbook match the numbers from my lease accounting software?"
    a: "It should come close once the conventions match. Differences usually come from payment timing (start or end of the month), how a mid-month start is treated, and whether interest accrues by month or by actual days. A day-count difference grows with the size of the lease. Run one real lease through both and compare the opening liability and the first month of interest."
  - q: "How many leases is too many for a spreadsheet?"
    a: "There is no line in the standard. The KDesk workbook holds 20 leases, and we can discuss a larger build. At 50 leases or more, or if your leases are modified often, lease accounting software is the better tool."
---

Lease accounting software earns its cost on large portfolios that change often. If you have six leases and one renewal a year, you may be paying for more than you use.

This page is about whether an Excel workbook would do the same job for you. It covers what LeaseQuery does, when to stay on it, when a workbook is enough, and how to check the numbers on a real lease before you decide.

## What LeaseQuery Does

LeaseQuery is lease accounting software from FinQuery. The company took the FinQuery name in February 2024 and kept LeaseQuery as the name of the lease product. FinQuery says it supports portfolios from a single contract to thousands.

Its product page lists, among other features:

- Compliance for ASC 842, IFRS 16, FRS 102, GASB 87, GASB 96 and SFFAS 54, with dual-standard reporting
- An audit trail with lease change history, and SOC 1 Type 2 reports on its controls
- Role-based access, read-only access for auditors, and locked journal entries
- Integrations with ERP and general ledger systems
- Multi-currency remeasurement and translation

Pricing is on request.

If you need most of that list, you need the software.

## When to Stay on Lease Software

Stay where you are if any of these describe you:

- **You have 50 leases or more.** The workbook holds 20. If you are a little over that, [email us](mailto:hello@kdeskaccounting.com) about a larger build before you decide.
- **Your leases change often.** A modification that is not accounted for as a separate contract has to be remeasured as of its effective date. Software does that inside the system. In a spreadsheet you do it by hand.
- **You report under GASB**, or under two standards at once.
- **Your auditors rely on system controls.** A spreadsheet has no system audit trail and no role-based access. At a minimum, your controls become a reviewer's sign-off and a saved copy of each closed period.
- **You are a lessor**, or you have sale-leasebacks, or you need multi-currency remeasurement.
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

LeaseGuru is free for up to 2 leases. Paid plans cover 10 leases or 15 leases, and 15 is the ceiling for a single company. It is self-service. When this page was written, FinQuery's site showed the 10-lease plan at $999 a year in one place and $1,099 in another, and the 15-lease plan at $1,750 and $1,925. Check [their page](https://finquery.com/leaseguru/) for the current price.

| | LeaseQuery | LeaseGuru | KDesk workbook |
|---|---|---|---|
| Leases | Unlimited | 2 free; 10 or 15 paid | 20 |
| Price | On request | Free, or $999 to $1,925 a year | $249 once |
| Standards | ASC 842, IFRS 16, FRS 102, GASB 87, GASB 96, SFFAS 54 | ASC 842, IFRS 16 | ASC 842 |
| Lease modifications | Calculated in the system | Amend the lease in the system | Done by hand |
| Controls | Audit trail, SOC 1 Type 2 reports, role-based access | Guest access on paid plans | Your own review and saved copies |
| Where the numbers live | FinQuery's cloud system | FinQuery's cloud system | An Excel file on your computer |

If you have one or two leases, LeaseGuru's free plan is hard to beat. Between 3 and 15 leases, the choice is between a yearly subscription to a hosted system and a one-time workbook you run yourself. Above 15, FinQuery also sells LeaseQuery Essential for portfolios of 25 leases and under, with pricing on request.

## How to Test One Against the Other

You can check a workbook against your current software before you spend anything.

1. Download the [free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc) of the workbook.
2. Enter one real lease: commencement date, term, monthly payment, discount rate, and whether rent is paid at the start or the end of the month. Add any escalation or free-rent months.
3. Compare three numbers with your software: the opening lease liability, the first month's interest, and the liability at a month end you have already closed. The free version shows the first 36 months of each lease.

If the numbers are slightly apart, the cause is usually a convention:

- **Payment timing.** Rent paid at the start of the month discounts differently from rent paid at the end. The workbook has a setting for this.
- **Mid-month starts.** Systems differ on how they treat a lease that begins on the 15th. The workbook has a setting for this too.
- **Day counts.** The workbook accrues interest by month, at the annual rate divided by 12. A system that counts actual days will show different interest from month to month, and the gap grows with the size of the lease. The payments are the same either way.

A controller compared the workbook with her software before buying:

> "I need to make a change from LeaseQuery, because we didn't need such a robust software. I evaluated this Lease Accounting Workbook against the numbers from my current software and they were almost identical. I would highly recommend this template for your lease tracking needs."
>
> Paula Ward, Controller

## If You Decide to Switch

Three things to do before you leave your current system:

1. **Export everything.** Save the schedules, journal entries and disclosure reports for every closed period. You will want them for the audit.
2. **Compare balances at the cutover date.** Set up every lease in the workbook and compare its lease liability and right-of-use asset with your ledger at the month you plan to switch. Expect small differences from the conventions above.
3. **Talk to your auditor first.** Tell them what is changing and agree how to treat any difference at cutover before you book anything.

## Related Guides

- [ASC 842 Lease Accounting: The Complete Guide](/posts/asc-842-lease-accounting-guide/)
- [ASC 842 Amortization Schedule: How to Build One in Excel](/posts/asc-842-amortization-schedule-excel/)
- [ASC 842 Journal Entries](/posts/asc-842-journal-entries/)
- [The ASC 842 Lease Accounting Workbook](/templates/asc842/)

*LeaseQuery and LeaseGuru are products of FinQuery, LLC. KDesk Accounting is not affiliated with FinQuery. Product details and prices above come from FinQuery's website in November 2026 and may have changed.*
