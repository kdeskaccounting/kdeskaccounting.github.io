---
title: "Commission Accrual Journal Entries: Monthly Accrual, Payout, True-Up, and the ASC 340-40 Capitalization Step"
date: 2026-09-03
lastmod: 2026-09-03
description: "How to book sales commission accruals at month end: when a commission is earned, the accrued commissions entry, the payout and true-up entries, clawbacks, payroll taxes, and how the accrual interacts with capitalizing commissions under ASC 340-40. One worked month with every entry, plus the Excel schedule that reconciles the liability and the deferred commission asset."
summary: "Commission accrual and commission capitalization are two different entries that most closes tangle together. One worked month shows the accrual when the commission is earned, the capitalization of the same dollars as a contract cost asset, the payout, the true-up when a deal falls through, and the monthly amortization, with the Excel schedule that ties all of it to the general ledger."
tags: ["commission accrual", "accrued commissions", "journal entries", "ASC 340-40", "ASC 606", "sales compensation", "month-end close", "Excel template"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
product: asc606
faq:
  - q: "What is the journal entry to accrue sales commissions?"
    a: "When the commission is earned under the plan but not yet paid, debit the cost side and credit accrued commissions (a current liability). If the commission is an incremental cost of obtaining a customer contract that you expect to recover, the debit goes to a deferred commission asset under ASC 340-40; otherwise, or if you use the one-year practical expedient, the debit goes to commission expense. Employer payroll taxes on the commission are accrued the same way."
  - q: "When is a sales commission earned for accounting purposes?"
    a: "When the rep has met the plan's conditions so that the company has an obligation to pay, and the amount can be estimated. For most SaaS plans that is when the customer contract is signed (booked). Payment timing, such as paying after the first invoice is collected, does not change when the liability is recorded; it changes when the liability is settled."
  - q: "Do you capitalize accrued commissions or paid commissions?"
    a: "Capitalization under ASC 340-40 follows the cost, not the cash. The asset is recognized when the commission liability is recognized, so an accrued but unpaid commission on a signed contract is capitalized in the month it is earned. Paying it later only reduces the accrued liability."
  - q: "How do you record a commission clawback?"
    a: "Reverse what was originally booked. If the commission was accrued and capitalized but not yet paid, debit accrued commissions and credit the deferred commission asset for the unamortized amount. If it was already paid and the plan gives the company a clawback right, the reversal becomes a receivable from the rep or a reduction of the next payout, and any amortization already recognized on the reversed portion is adjusted through commission expense. If it was paid and there is no clawback right, there is no receivable; the unamortized balance is an impairment charge to commission expense under ASC 340-40-35-3."
  - q: "Are employer payroll taxes on commissions capitalized under ASC 340-40?"
    a: "Yes, when the tax is triggered by the commission. The FASB staff's view (TRG Agenda Ref 23, Issue 6, January 2015, restated in FASB Revenue Recognition Implementation Q&A No. 74) is that fringe benefits incurred as a direct result of a capitalized commission, such as employer payroll taxes, are incremental and are capitalized with it; benefits that would be incurred anyway are not. It is not a policy election, so document the conclusion and the materiality assessment."
  - q: "What is the difference between accrued commissions and deferred commissions?"
    a: "Accrued commissions is a liability: what the company owes reps for commissions earned and not yet paid. Deferred commissions (capitalized contract costs) is an asset: the commissions recognized as an asset under ASC 340-40 and amortized over the period the company benefits from the contract. The same commission dollar creates both on the day it is earned, and they then move independently, the liability when cash is paid and the asset when amortization runs."
---

Every SaaS close has a commission entry, and most of them are two entries pretending to be one. The first is the **accrual**: the company owes its reps for commissions earned this month, whether or not payroll has paid them. The second is the **capitalization**: under ASC 340-40 most of those same dollars are an asset, not an expense, and get amortized over the period the customer contract benefits the company. Tangle them and you get the classic audit findings: commissions expensed in the month paid instead of the month earned, an asset that does not reconcile to anything, and a payroll liability nobody can support.

This guide books one month end to end. It covers when a commission is earned, the accrual entry, the capitalization decision, the payout, the true-up when a deal falls through, payroll taxes, the monthly amortization, and the Excel schedule that reconciles the liability and the asset to the general ledger. For the capitalization rules themselves, start with [how to capitalize sales commissions under ASC 606](/posts/how-to-capitalize-sales-commissions-asc-606/); this article is about the entries around them.

## When Is a Commission Earned?

The accrual question is a liability question. A commission is accrued when it is probable the company has incurred an obligation to pay it and the amount can be reasonably estimated (ASC 450-20-25-2). The plan document decides when that happens, and it usually says one of three things:

- **Earned on booking.** The rep is entitled to the commission when the customer signs. This is the most common SaaS plan and the cleanest to account for: accrue in the month of signature.
- **Earned on invoicing or collection.** The plan pays only after the customer is invoiced or the cash is collected. The obligation still traces to the signed contract, and if the contract passed Step 1 of ASC 606 you have already concluded collection is probable, so the condition is expected to be met (TRG Agenda Ref 23, Issues 3 and 4). Accrue when the contract is signed, at the amount you expect to pay, and true it up if collection fails. Waiting until cash arrives understates the liability for one to three months every quarter.
- **Earned on attainment.** Quarterly or annual plans with accelerators pay a rate that depends on cumulative quota attainment. Accrue monthly at the blended rate you expect the rep to finish the period at, applied to cumulative bookings to date, and true up at period end. The FASB staff accepted either this estimate or capitalizing at the rate actually earned when each threshold is crossed (TRG Agenda Ref 23, Issue 5); either way, document the expected attainment and its basis.

In every case the trigger for the entry is *earned*, not *paid*. Payroll timing is settlement, and settlement never decides expense recognition.

## The Worked Month

The example uses one rep on a simple plan so every entry can be traced:

- Plan: 10% of first-year annual contract value, earned when the customer contract is signed, paid through payroll in the month after the customer's first invoice is collected
- Employer payroll taxes on commissions: 7.65%, below the wage base
- September signings: four new-logo contracts with first-year ACV of $40,000, $25,000, $60,000, and $35,000, total $160,000
- Commissions earned in September: 10% × $160,000 = **$16,000.00**; employer payroll tax on that amount: **$1,224.00**
- Each contract is a 12-month subscription; the company expects two renewals on average and pays no commission on renewals, so the ASC 340-40 amortization period is 36 months (more on that below)
- In October, the $35,000 customer cancels before its first invoice, and the plan says no commission is owed. The other three are collected and the rep is paid in November.

### Entry 1: month-end accrual (September 30)

The commissions are earned, so the liability exists. Because they are incremental costs of obtaining contracts the company expects to recover, and the amortization period exceeds one year, they are capitalized rather than expensed (ASC 340-40-25-1; the one-year practical expedient in 340-40-25-4 does not apply):

| Account | Debit | Credit |
|---|---|---|
| Deferred commission asset (capitalized contract costs) | 16,000.00 | |
| Deferred commission asset, payroll tax component | 1,224.00 | |
| Accrued commissions | | 16,000.00 |
| Accrued payroll taxes | | 1,224.00 |

If the company had elected the practical expedient (amortization period of one year or less) or the commission were not incremental, the debits would go to commission expense instead. The credits do not change: the liability is the same either way.

Two things this entry deliberately does not do. It does not wait for the November payroll, and it does not put anything through commission expense yet. Expense starts with amortization.

### Entry 2: monthly amortization (September 30)

The asset is amortized on a systematic basis consistent with the transfer of the services to which it relates (ASC 340-40-35-1). With a 36-month expected benefit period and straight-line amortization beginning in the month of signature, September's amortization on the new cohort is ($16,000.00 + $1,224.00) ÷ 36 = **$478.44**:

| Account | Debit | Credit |
|---|---|---|
| Commission expense (amortization of contract costs) | 478.44 | |
| Deferred commission asset | | 478.44 |

Companies that start amortization the month after signature, or at the contract start date, will show this entry one month later. Either convention is acceptable if it reflects when the customer starts receiving the service and is applied consistently. The full workbook's [amortization waterfall](/posts/how-to-capitalize-sales-commissions-asc-606/#step-3-build-the-amortization-waterfall) handles the mid-month and half-month variants.

### Entry 3: true-up for the cancelled deal (October 31)

The $35,000 customer cancelled before invoicing and no commission is owed. The rep was never paid, so the liability is simply reversed, and the capitalized cost that no longer has a contract behind it is written off. Commission on the deal was $3,500.00, plus $267.75 payroll tax, total $3,767.75, of which one month of amortization ($104.66) already ran in September.

| Account | Debit | Credit |
|---|---|---|
| Accrued commissions | 3,500.00 | |
| Accrued payroll taxes | 267.75 | |
| Deferred commission asset (unamortized: 3,767.75 − 104.66) | | 3,663.09 |
| Commission expense (reverse September amortization on the deal) | | 104.66 |

Had the rep already been paid, the $3,500.00 debit would instead be a receivable from the rep or a deduction from the next payout, and the plan's clawback language decides which; the $267.75 employer-tax component is written off to commission expense rather than recovered (see [commission clawbacks and reversals](/posts/commission-clawbacks-reversals-asc-340-40/)). If the rep was paid and the plan has no clawback right, there is no receivable at all; the unamortized balance is an impairment charge to commission expense (ASC 340-40-35-3). The asset side is otherwise identical. This is the entry most closes skip: the accrual gets reversed at payout, but the asset keeps amortizing a commission that was never paid.

October's amortization on the three surviving contracts is ($12,500.00 + $956.25) ÷ 36 = **$373.78**, booked the same way as Entry 2.

### Entry 4: payout through payroll (November)

The three surviving commissions are paid. The entry settles the liability; it touches neither the asset nor expense:

| Account | Debit | Credit |
|---|---|---|
| Accrued commissions | 12,500.00 | |
| Accrued payroll taxes | 956.25 | |
| Cash (via payroll, gross of employee withholding) | | 13,456.25 |

Payroll systems split the cash credit between net pay and withholding payables; the point for the commission schedule is that the debit clears the accrual to zero for the September cohort. If it does not, either the accrual was wrong or a plan change happened in between, and the difference is the true-up you need to explain.

### The reconciliation at November 30

For the September cohort, three balances should tie to three schedules:

| Balance | Amount | Supported by |
|---|---|---|
| Accrued commissions, September cohort | 0.00 | Payout register |
| Deferred commission asset, September cohort | 12,334.91 | Waterfall: 13,456.25 capitalized − 3 months × 373.78 (September's 478.44 less the 104.66 reversed on the cancelled deal is 373.78, then October and November at 373.78) |
| Commission expense, September cohort, September to November | 1,121.34 | 478.44 − 104.66 + 373.78 + 373.78 |

Asset plus cumulative expense equals cash paid: 12,334.91 + 1,121.34 = 13,456.25. That identity, **capitalized cost = unamortized asset + cumulative amortization**, is the check that catches a broken waterfall faster than anything else.

## Payroll Taxes, Bonuses, and Other Costs

- **Employer payroll taxes** triggered by a capitalized commission are themselves incremental. The FASB staff's view (TRG Agenda Ref 23, Issue 6, January 2015, restated in FASB Revenue Recognition Implementation Q&A No. 74) is that fringe benefits incurred as a direct result of the commission, such as employer payroll taxes, are capitalized with it, allocated benefits are not, and this is not a policy election. Capitalizing the associated payroll taxes is common SaaS practice. Write the conclusion down; auditors ask.
- **Manager overrides, SDR bonuses paid per contract, and bonuses earned solely by hitting a cumulative bookings quota** are incremental and follow the same path as the rep's commission; the FASB staff rejected expensing threshold-based commissions (TRG Agenda Ref 23, Issue 5; TRG Memo 57). Bonuses based on a mix of factors such as profitability or individual performance reviews (ASC 340-40-55-2 to 55-4), salaries, and non-recoverable draws are not incremental and are expensed as incurred (ASC 340-40-25-3).
- **Renewal commissions** are capitalized when earned and amortized over the renewal period. They also set the amortization period of the original commission: if the renewal commission is commensurate with the original, reasonably proportional to contract value, the original is amortized over the initial term only; if it is smaller or there is none, the original is amortized over the expected benefit period including anticipated renewals (ASU 2014-09 paragraph BC309; TRG Agenda Refs 23 and 57). Our 36-month example assumes renewals pay nothing.
- **Recoverable draws and advances** are a receivable from the rep (or a prepaid commission) until earned, provided the company has an enforceable right to recover them and recovery is probable; when commission is earned against the draw, reclassify it to the deferred commission asset if incremental. Non-recoverable draws are compensation expense as incurred. Auditors routinely challenge the receivable where draws are forgiven at termination or state wage law limits recovery.

## The Excel Schedule

The accrual and the asset need two linked schedules and one reconciliation. The layout below is the one the [ASC 606 Commission Capitalization Workbook](/templates/asc606/) uses; a hand-built version needs the same columns.

**Commission register** (one row per deal): deal ID, rep, customer, signature date, first-year ACV, rate, commission, payroll tax, capitalized amount (commission plus tax when the capitalize flag is on), capitalize flag (incremental and over one year), amortization months, status (active, cancelled, clawed back), month earned, month paid, month reversed. Keep a parallel rollforward for the payroll-tax component, or the schedule will not tie to the accrued payroll taxes account the entries above book.

**Accrued commissions rollforward** (one row per month):

| Column | Formula |
|---|---|
| Opening accrued commissions | prior month closing |
| Add: earned this month | `=SUMIFS(Register[Commission],Register[MonthEarned],ThisMonth)` |
| Less: paid this month | `=SUMIFS(Register[Commission],Register[MonthPaid],ThisMonth)` (do not filter on status, or a deal clawed back later drops out of a prior month's history) |
| Less: reversed this month | `=SUMIFS(Register[Commission],Register[MonthReversed],ThisMonth)` |
| Closing accrued commissions | opening + earned − paid − reversed, which must equal the GL balance |

**Deferred commission asset rollforward** (one row per month):

| Column | Formula |
|---|---|
| Opening asset | prior month closing |
| Add: capitalized | `=SUMIFS(Register[Capitalized],Register[MonthEarned],ThisMonth)` |
| Less: amortization | sum of the waterfall column for the month |
| Less: write-offs on cancelled or impaired contracts | unamortized balance of deals reversed this month |
| Closing asset | opening + capitalized − amortization − write-offs, which must equal the GL balance |

Two identities close the loop: capitalized to date = closing asset + cumulative amortization + cumulative write-offs, and earned to date = paid + reversed + closing accrual. The first is gross of reversed deals, so its cumulative amortization (1,226.00 on the worked cohort: 478.44 + 373.78 + 373.78) is larger than the income statement figure (1,121.34) because Entry 3's 104.66 reversal is booked to expense rather than netted in the rollforward. If either identity fails, find the deal, not the formula; it is almost always a status flag that was changed without a month.

## Controls and What the Auditor Will Ask For

Commission accrual is a routine key control in a SaaS close because it combines an estimate, a related-party-adjacent payment, and a capitalized asset. The prepared-by-client list is predictable:

1. The commission plan documents in effect for the period, with the earn and pay triggers highlighted
2. The register of contracts signed in the period tied to the bookings report
3. The commission calculation by rep, tied to the register
4. The accrued commissions rollforward tied to the general ledger and to the subsequent payout register
5. The capitalization policy memo: what is incremental, the practical expedient election, the amortization period and its support (renewal history), payroll tax treatment
6. The deferred commission asset rollforward and waterfall tied to the general ledger
7. Evidence of the impairment review under ASC 340-40-35-3 when contracts are cancelled or renewals fall short of the estimate

Keep the accrual and the asset in the same workbook. An auditor who can trace one commission from the plan to the register to the accrual to the payout to the asset to the waterfall in one file spends an hour on commissions instead of a week.

## Common Mistakes

- **Accruing at payout.** Booking commissions when payroll pays them shifts expense and the liability one to three months late every quarter and is the single most common commission finding.
- **Reversing the accrual but not the asset.** A cancelled deal clears the liability at true-up while the capitalized cost keeps amortizing. The write-off in Entry 3 is the fix.
- **Expensing what should be capitalized, or capitalizing what should not.** The test is incremental to the contract (ASC 340-40-25-2 and 25-3), not who receives the money.
- **Ignoring payroll taxes.** The accrual and the asset are both understated by the employer tax rate if the tax is left to payroll.
- **Amortizing over the contract term when renewals are expected.** The period is the expected benefit period, which is longer than the initial term when renewals are likely and renewal commissions are not commensurate (ASC 340-40-35-1; ASU 2014-09 paragraph BC309; TRG Agenda Refs 23 and 57).
- **No estimate documentation for attainment-based plans.** An accrual at an assumed attainment rate is an estimate; the auditor needs the rate, the basis, and the true-up history.

## Related Guides

- [How to capitalize sales commissions under ASC 606 (ASC 340-40)](/posts/how-to-capitalize-sales-commissions-asc-606/)
- [SaaS deferred revenue: how to track it in Excel](/posts/saas-deferred-revenue-excel/), the revenue side of the same contracts
- [Month-end close checklist for controllers](/posts/month-end-close-checklist-controllers/)
- [SaaS metrics dashboard in Excel](/posts/saas-metrics-dashboard-excel/), where CAC picks up the commission expense

*This article is general information for finance professionals, not accounting, tax, or legal advice. Commission plans, payroll tax treatment, and the capitalization policy should be confirmed with your auditor and payroll provider.*
