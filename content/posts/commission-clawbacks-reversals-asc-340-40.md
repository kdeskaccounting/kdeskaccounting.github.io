---
title: "Commission Clawbacks and Reversals Under ASC 340-40: Journal Entries When a Deal Churns, Downgrades, or Was Miscalculated"
date: 2026-09-03
lastmod: 2026-09-03
description: "How to account for sales commission clawbacks and reversals under ASC 340-40: full and partial clawbacks after a customer cancels, the impairment test when a deal downgrades, what happens to the capitalized commission asset and the amortization already taken, payroll taxes you cannot recover, correcting a miscalculated commission, and the Excel register that keeps the rollforward tied."
summary: "A clawback touches three balances at once: the rep's payout, the deferred commission asset, and the amortization already expensed. One paid-and-amortizing commission is worked through a full clawback, a 50% clawback, a no-clawback cancellation, and a downgrade, with the ASC 340-40 impairment test and the entries for each."
tags: ["commission clawback", "ASC 340-40", "ASC 606", "sales commissions", "journal entries", "impairment", "deferred commissions", "Excel template"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
product: asc606
faq:
  - q: "What is the journal entry for a commission clawback?"
    a: "Debit a clawback receivable (or reduce the rep's next accrued payout) for the amount recoverable under the plan, credit the deferred commission asset for its remaining unamortized balance, and put the difference through commission expense: a credit when the recovery exceeds the unamortized asset (it recovers amortization already expensed), a debit when the recovery is smaller (the shortfall is an impairment of the asset). Employer payroll taxes on the clawed-back commission are written off; they are not recovered from the rep."
  - q: "Do you have to impair a capitalized commission when the customer cancels?"
    a: "Yes. Under ASC 340-40-35-3 the asset is impaired when its carrying amount exceeds the remaining consideration the company expects to receive for the related goods or services less the remaining direct costs. When the contract terminates there is no remaining consideration, so the unamortized balance is written off in the period of termination, net of anything the clawback recovers."
  - q: "Does a downgrade trigger an impairment of the deferred commission?"
    a: "Rarely. The test compares the unamortized asset to the consideration still expected over the amortization period. A commission of 10% of first-year value is small relative to even a reduced contract's remaining revenue, so the test usually passes and amortization continues unchanged. Re-run the test; document it; impair only if it fails."
  - q: "How do you account for a commission that was calculated wrong?"
    a: "It is an error under ASC 250, not a change in estimate. Reverse the over-accrual (debit accrued commissions, credit the deferred commission asset for the unamortized portion) and catch up the amortization difference through commission expense. If the amount is immaterial to the prior and current periods, book it in the period found as an out-of-period adjustment and document the materiality assessment; if it is material, apply the prior-period error guidance in ASC 250-10-45-23."
  - q: "Can the company recover the employer payroll taxes on a clawed-back commission?"
    a: "Not from the rep. The employer share of payroll taxes was capitalized with the commission as an incremental cost; when the commission is clawed back, the unamortized tax component is written off to expense. Whether any of it is recoverable from the tax authority is a payroll matter for your provider, not an accounting entry."
  - q: "Where does a clawback receivable sit on the balance sheet?"
    a: "As a current asset if it will be deducted from the rep's next payout or collected within a year; net against accrued commissions when the plan settles it through the next payment (a right of setoff under ASC 210-20-45-1). If the rep has left and the plan or state wage law limits recovery, assess collectibility and record an allowance."
---

A commission clawback is the entry most closes get half right. The payout side is obvious: the plan says the rep gives back the commission when the customer cancels within the window, so accrued commissions or a receivable moves. The asset side is the part that gets missed. Under ASC 340-40 that commission was capitalized and is still amortizing, and the amortization already booked has to be dealt with too. Miss it and the deferred commission asset carries a contract that no longer exists, and the reconciliation to the general ledger stops tying.

This guide takes one paid commission that is five months into a 36-month amortization and runs it through the four things that happen to commissions after the sale: a full clawback, a partial clawback, a cancellation with no clawback right, and a downgrade. Then a miscalculation correction, the payroll-tax problem, presentation, and the Excel columns that keep the rollforward honest. It follows on from [commission accrual journal entries](/posts/commission-accrual-journal-entries/), which books the original accrual and capitalization, and [how to capitalize sales commissions under ASC 606](/posts/how-to-capitalize-sales-commissions-asc-606/), which covers the rules.

## The Starting Position

- Contract signed in September: 12-month subscription, first-year ACV $60,000, two renewals expected, no renewal commission, so a 36-month amortization period
- Commission: 10% = **$6,000.00**, paid in November; employer payroll tax 7.65% = **$459.00**
- Capitalized in September: $6,459.00, amortized straight-line at $179.42 a month ($166.67 commission, $12.75 tax)
- Plan terms: 100% clawback if the customer cancels within six months of signature; recovered from the rep's next payout
- At the end of January (five months in): amortization taken $897.08; carrying amount **$5,561.92** ($5,166.67 commission component, $395.25 tax component)

The customer cancels effective January 31. What happens next depends entirely on the plan.

## Case 1: Full Clawback (100% Within the Window)

The plan entitles the company to the whole $6,000. The asset's related contract is gone, so its remaining balance cannot stay on the books (ASC 340-40-35-3). Two things are true at once: the company recovers $6,000 of cash it had partly expensed, and the $459 of payroll tax is not recoverable from the rep.

| Account | Debit | Credit |
|---|---|---|
| Commission clawback receivable (or accrued commissions, if netted against the next payout) | 6,000.00 | |
| Deferred commission asset, commission component (unamortized) | | 5,166.67 |
| Commission expense (recovery of amortization already taken on the clawed-back commission) | | 833.33 |

| Account | Debit | Credit |
|---|---|---|
| Commission expense (impairment of the non-recoverable payroll-tax component) | 395.25 | |
| Deferred commission asset, payroll-tax component | | 395.25 |

Net effect in January: the asset is cleared to zero for this contract, a $6,000 receivable exists, and commission expense shows a net credit of $438.08 (the $833.33 recovery less the $395.25 tax write-off). Over the life of the contract the company's total commission cost is $459.00, the payroll tax the plan cannot recover from the rep.

The recovery of amortization already expensed is presented here as a credit to commission expense in the period of clawback, not as a prior-period adjustment; the clawback is a new event, not an error. If your policy presents recoveries as other income instead, apply it consistently, but keep them out of revenue: a clawback is a cost recovery, not consideration from a customer.

## Case 2: Partial Clawback (50%)

Same facts, but the plan claws back 50% after month three. The company recovers $3,000. The rest of the asset is impaired because the contract is gone:

| Account | Debit | Credit |
|---|---|---|
| Commission clawback receivable | 3,000.00 | |
| Commission expense (impairment: unrecovered commission $2,166.67 + payroll tax $395.25) | 2,561.92 | |
| Deferred commission asset (entire remaining balance) | | 5,561.92 |

Debits and credits both total $5,561.92. The expense line is the unamortized balance minus what the clawback recovers; whether it is a net debit or a net credit depends only on how the recovery compares to the carrying amount.

## Case 3: Cancellation With No Clawback Right

The customer cancels in month nine, after the window closes, or the plan never had a clawback clause. Nothing is recovered from the rep. The asset is impaired in full:

| Account | Debit | Credit |
|---|---|---|
| Commission expense (impairment, ASC 340-40-35-3) | 5,561.92 | |
| Deferred commission asset | | 5,561.92 |

The table uses the January (month-five) balance so the three cases compare; at an actual month-nine cancellation the carrying amount is $6,459.00 less nine months of amortization ($1,614.75), or $4,844.25, and the entry has the same shape. Impairments under ASC 340-40 are not reversed if the customer later comes back (ASC 340-40-35-6); a re-signed contract is a new contract with its own commission.

## Case 4: Downgrade (Contract Continues at a Lower Value)

At the end of January the customer drops from $60,000 to $40,000 of annual value and stays. No clawback applies under the plan. The question is whether the asset is impaired, and the test in ASC 340-40-35-3 answers it: compare the carrying amount ($5,561.92) with the remaining consideration the company expects to receive over the amortization period, less the direct costs of providing the service that have not yet been expensed.

Remaining expected consideration: 31 months at $3,333.33 a month is $103,333, and even after deducting the direct cost of delivering the service the figure is a multiple of $5,561.92. The test passes. Nothing is impaired; amortization continues at $179.42 a month. A downgrade changes revenue, not the commission asset, unless the remaining consideration collapses below the carrying amount, which for a commission of 10% of one year's value takes a near-total downgrade.

Two situations do change the amortization: a downgrade that shortens the expected renewal horizon (the customer signals it will not renew) reduces the amortization period prospectively under ASC 340-40-35-2 as a change in accounting estimate (ASC 250-10); and a plan that reduces the commission when a customer downgrades within the window is a partial clawback: derecognize the clawed-back share of the unamortized asset against the receivable, with the difference through commission expense as in Case 2, and keep amortizing the rest because the contract continues.

## Correcting a Miscalculated Commission

The other kind of reversal has nothing to do with the customer. The rate was keyed wrong, the ACV included a one-time fee that the plan excludes, or the split between two reps was wrong. Say the September commission should have been $5,000, not $6,000, and the error is found in January.

- Over-accrual to reverse: $1,000 commission plus $76.50 payroll tax
- Amortization taken on the excess: 5 months × ($1,076.50 ÷ 36) = $149.51

| Account | Debit | Credit |
|---|---|---|
| Accrued commissions or clawback receivable (over-payment recoverable per plan) | 1,000.00 | |
| Accrued payroll taxes (if not yet remitted) or commission expense | 76.50 | |
| Deferred commission asset (unamortized excess: 1,076.50 − 149.51) | | 926.99 |
| Commission expense (amortization already taken on the excess) | | 149.51 |

Record it in the period found. It is an error under ASC 250; for a single commission it is almost always immaterial to both the prior and the current period, so it is booked as an out-of-period adjustment, but assess and document the materiality either way. Whether the $1,000 is recoverable from the rep is a plan and employment-law question, not an accounting one; if it is not recoverable, the $1,000 stays in expense.

## The Payroll-Tax Problem

The employer payroll taxes on a commission were capitalized with it because they were incremental to the contract (see the [accrual guide](/posts/commission-accrual-journal-entries/#payroll-taxes-bonuses-and-other-costs)). A clawback recovers the commission from the rep, not the employer taxes from anyone. Write the unamortized tax component off to expense in every clawback case; whether any employer tax is recoverable through a payroll correction is a question for your payroll provider, and any recovery shows up as lower payroll-tax expense in the period it is recovered, not as a reversal of this entry.

## Presentation and Collectibility

- A clawback that will be deducted from the rep's next payout is netted against accrued commissions; the liability simply goes down.
- A clawback from a rep who has left, or whose next payout is smaller than the clawback, is a receivable. Assess collectibility, record an allowance if recovery is doubtful, and check the plan's clawback clause and state wage law (some states restrict deductions from wages). That is a question for counsel; the accounting follows whatever the answer is.
- Impairments and recoveries sit in the same line as commission amortization, sales and marketing expense for most SaaS companies, so the line shows the net cost of obtaining contracts.

## The Excel Register and Rollforward

Clawbacks are where hand-built commission schedules break, because the waterfall keeps amortizing a row whose status changed. The [ASC 606 Commission Capitalization Workbook](/templates/asc606/) handles it with three columns on the register and one line on the rollforward; a hand-built schedule needs the same:

- **Status** (active, cancelled, clawed back, corrected) and **status month**: amortization stops in the status month; the waterfall formula checks both.
- **Clawback %** and **recovered amount**: drives the receivable entry and the split between recovery and impairment.
- **Rollforward line "Clawbacks and write-offs"**: the unamortized balance of every row whose status changed this month, so that opening + capitalized − amortization − clawbacks/write-offs = closing, and closing equals the general ledger.

The check that catches a missed clawback: for every row with a status month, the waterfall's amortization after that month must be zero and the unamortized balance at the status month must appear in the write-off line. If the asset rollforward ties but this check fails, a row is still amortizing a dead contract and the tie is a coincidence.

## Common Mistakes

- **Clearing the liability and forgetting the asset.** The payout side is reversed; the deferred commission keeps amortizing. The asset overstates and the reconciliation only ties because both sides are wrong.
- **Treating the recovery as revenue.** A clawback recovers a cost; it is a credit to commission expense (or other income under a consistent policy), never contract revenue.
- **Recovering the payroll tax from the rep.** Plans claw back what the rep was paid, not the employer's taxes.
- **Impairing on every downgrade.** Run the ASC 340-40-35-3 test; most downgrades pass it.
- **Reversing an impairment when the customer returns.** Not permitted under 340-40-35-6; the new contract earns its own commission.
- **Fixing a miscalculation in the original month.** It is an error, not an estimate; correct it in the period found when immaterial, and restate only when it is material.

## Related Guides

- [Commission accrual journal entries: accrual, payout, true-up, capitalization](/posts/commission-accrual-journal-entries/)
- [How to capitalize sales commissions under ASC 606 (ASC 340-40)](/posts/how-to-capitalize-sales-commissions-asc-606/)
- [SaaS deferred revenue: how to track it in Excel](/posts/saas-deferred-revenue-excel/)
- [Month-end close checklist for controllers](/posts/month-end-close-checklist-controllers/)

*This article is general information for finance professionals, not accounting, tax, or legal advice. Clawback enforceability and payroll-tax recovery depend on your plan, your state, and your payroll provider; confirm with counsel and your auditor.*
