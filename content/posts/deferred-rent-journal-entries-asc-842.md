---
title: "Deferred Rent Journal Entries Under ASC 842: Where Straight-Line Rent Went (With an Excel Schedule)"
date: 2026-09-03
lastmod: 2026-09-03
description: "Deferred rent journal entries before and after ASC 842: how straight-line rent created the deferred rent liability under ASC 840, why that account now lives inside the ROU asset, the transition entry, where deferred rent still exists (short-term leases and lessors), and how to build the straight-line rent schedule in Excel."
summary: "Under ASC 840, escalating rent and free months produced a deferred rent liability. Under ASC 842 the same difference sits inside the right-of-use asset. One worked lease shows both sets of entries, proves they tie to the cent, and gives you the Excel formulas."
tags: ["deferred rent", "straight-line rent", "ASC 842", "ASC 840", "operating lease", "journal entries", "lease accounting", "Excel template"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
product: asc842
faq:
  - q: "What is the journal entry for deferred rent?"
    a: "Under legacy ASC 840, each month you debited rent expense for the straight-line amount, credited cash for the amount actually paid, and booked the difference to a deferred rent liability (a credit when straight-line expense exceeded cash, a debit when cash exceeded it). Under ASC 842 a lessee no longer records a separate deferred rent account for an operating lease: the monthly entry debits lease expense for the straight-line cost, adjusts the lease liability for interest and cash, and credits the right-of-use asset for the difference."
  - q: "Does deferred rent still exist under ASC 842?"
    a: "Not as a separate lessee liability for leases on the balance sheet. At transition the deferred rent balance was folded into the right-of-use asset, and afterwards the same economic difference shows up as the gap between the lease liability and the ROU asset (on a lease with no initial direct costs, incentives, or impairment). Deferred (accrued) rent still exists for short-term leases accounted for under the practical expedient, and lessors still carry a straight-line rent receivable on operating leases."
  - q: "How do you calculate straight-line rent?"
    a: "Add up every fixed payment over the lease term, including free months at zero and scheduled escalations, and divide by the number of months in the term. A 36-month lease with one free month, $5,000 a month in year one, and 3% annual escalations totals $180,454, so straight-line rent is $5,012.61 a month."
  - q: "How is a rent-free period accounted for under ASC 842?"
    a: "The free months are part of the lease term, so they are inside the straight-line cost and inside the lease liability. The lessee recognizes the same straight-line cost in a free month as in a paid month; because no cash goes out, interest accretes and the lease liability rises slightly that month before the payments start bringing it down."
  - q: "What happened to deferred rent at ASC 842 transition?"
    a: "For an existing operating lease, ASC 842-10-65-1(m) measures the initial right-of-use asset as the lease liability (measured under 842-10-65-1(l)) adjusted for prepaid or accrued rent, unamortized lease incentives, initial direct costs, impairment, and any exit-cost liability. A deferred rent (accrued rent) credit balance reduces the ROU asset. The transition entry debits the ROU asset, debits deferred rent to clear it, and credits the lease liability."
  - q: "Is deferred rent a current or non-current liability?"
    a: "Under ASC 840 it was split by when the difference would reverse, and most of it was non-current. Under ASC 842 the question goes away for lessees because the balance is inside the ROU asset; the lease liability itself is split between current and non-current based on the principal due within twelve months."
---

If you searched for the deferred rent journal entry, you probably have a lease with escalating rent or a few free months and a close to finish. The short version: under the old standard, ASC 840, the difference between straight-line rent expense and cash paid went to a deferred rent liability. Under ASC 842, which every US GAAP company now applies, that account no longer exists for a lessee's balance-sheet leases. The same difference is still there, to the cent, but it lives inside the right-of-use asset.

This guide shows both sets of entries on one lease, proves they reconcile, covers the transition entry that moved deferred rent into the ROU asset, lists the places where deferred rent still exists, and gives you the Excel formulas for the straight-line schedule.

*This guide is one part of the [complete ASC 842 lease accounting guide](/posts/asc-842-lease-accounting-guide/), which covers scope, classification, measurement, entries, modifications, and disclosure.*

## Why Deferred Rent Existed Under ASC 840

ASC 840 kept operating leases off the balance sheet but still required rent expense to be recognized on a straight-line basis over the lease term (ASC 840-20-25-1). Any lease with a rent holiday, scheduled escalations, or a tenant improvement allowance therefore had rent expense that did not match cash. The plug was deferred rent:

- **Free months and escalations** pushed straight-line expense above cash early in the term, building a **deferred rent liability** (a credit balance) that unwound in the later, more expensive months.
- **Tenant improvement allowances** received from the landlord were recorded as a separate deferred rent credit (a lease incentive) and amortized as a reduction of rent expense over the term.
- **Prepaid rent** ran the other way: cash ahead of expense produced an asset.

The monthly entry was mechanical:

| Account | Debit | Credit |
|---|---|---|
| Rent expense (straight-line amount) | X | |
| Cash (contractual payment) | | Y |
| Deferred rent liability (difference) | | X − Y |

When the contractual payment later exceeded the straight-line amount, the deferred rent line flipped to a debit and the liability ran down to zero at the end of the term.

## The Worked Lease

Every number below comes from one lease so you can trace it:

- 36-month office lease, commencing January 1
- Month 1 is rent-free
- $5,000 a month for the rest of year one, $5,150 in year two (3% escalation), $5,304.50 in year three
- Payments in arrears at each month end
- Incremental borrowing rate 6% (0.5% a month)
- No initial direct costs, no incentives, no prepaid rent

Total fixed payments: $0 + (11 × $5,000) + (12 × $5,150) + (12 × $5,304.50) = **$180,454.00**. Straight-line rent: $180,454.00 ÷ 36 = **$5,012.61** a month.

### ASC 840: the deferred rent schedule

| Month | Straight-line expense | Cash paid | Difference | Deferred rent balance |
|---|---|---|---|---|
| 1 (free) | 5,012.61 | 0.00 | +5,012.61 | 5,012.61 |
| 2 | 5,012.61 | 5,000.00 | +12.61 | 5,025.22 |
| 12 | 5,012.61 | 5,000.00 | +12.61 | 5,151.33 |
| 13 | 5,012.61 | 5,150.00 | −137.39 | 5,013.94 |
| 24 | 5,012.61 | 5,150.00 | −137.39 | 3,502.67 |
| 25 | 5,012.61 | 5,304.50 | −291.89 | 3,210.78 |
| 36 | 5,012.61 | 5,304.50 | −291.89 | 0.00 |

The month-one entry under ASC 840 was a debit to rent expense of $5,012.61 and a credit to deferred rent of $5,012.61, with no cash. Month two debited rent expense $5,012.61, credited cash $5,000.00, and credited deferred rent $12.61. From month 13 the deferred rent line became a debit. Note the shape: the liability peaks at the end of year one at $5,151.33 and is exactly zero after the last payment.

## What ASC 842 Did With It

ASC 842 puts the lease on the balance sheet. At commencement the lessee records a lease liability equal to the present value of the unpaid lease payments and a right-of-use asset equal to that liability plus prepaid rent and initial direct costs, less lease incentives received (ASC 842-20-30-1 and 842-20-30-5). Free months and escalations are inside the payment stream, so they are inside the liability.

For an operating lease the income statement still shows a single straight-line lease cost (ASC 842-20-25-6). The mechanics behind that number changed. Each month:

1. Interest accretes on the lease liability at the discount rate.
2. Cash reduces the liability.
3. Straight-line lease cost is recognized.
4. The ROU asset is amortized by the plug: straight-line cost minus that month's interest.

On the worked lease the liability at commencement is the present value of the 36 payments at 0.5% a month: **$164,160.38**. With no incentives or initial direct costs, the ROU asset starts at the same amount.

### ASC 842: the operating lease schedule

| Month | Straight-line cost | Interest on liability | Cash | ROU amortization (plug) | Lease liability, end | ROU asset, end |
|---|---|---|---|---|---|---|
| 1 (free) | 5,012.61 | 820.80 | 0.00 | 4,191.81 | 164,981.18 | 159,968.57 |
| 2 | 5,012.61 | 824.91 | 5,000.00 | 4,187.70 | 160,806.09 | 155,780.87 |
| 12 | 5,012.61 | 611.39 | 5,000.00 | 4,401.22 | 117,889.60 | 112,738.27 |
| 24 | 5,012.61 | 332.25 | 5,150.00 | 4,680.36 | 61,632.63 | 58,129.96 |
| 36 | 5,012.61 | 26.39 | 5,304.50 | 4,986.22 | 0.00 | 0.00 |

Two checks worth running on any schedule. Total cost over the term is 36 × $5,012.61 (unrounded, $5,012.611…) = $180,454.00, which equals total cash. And total interest ($16,293.62) plus total ROU amortization ($164,160.38) also equals $180,454.00. Both the liability and the ROU asset land on zero in month 36.

### The month-one entries under ASC 842

Month one, the free month. No cash moves, but interest still accrues, so the liability rises:

| Account | Debit | Credit |
|---|---|---|
| Lease expense (operating) | 5,012.61 | |
| Lease liability (interest accretion) | | 820.80 |
| Right-of-use asset (amortization plug) | | 4,191.81 |

Month two, the first paid month:

| Account | Debit | Credit |
|---|---|---|
| Lease expense (operating) | 5,012.61 | |
| Lease liability (cash less interest: 5,000.00 − 824.91) | 4,175.09 | |
| Cash | | 5,000.00 |
| Right-of-use asset (5,012.61 − 824.91) | | 4,187.70 |

Debits and credits both total $9,187.70. Many companies book this as two entries, one for the payment against the liability and one for the straight-line cost, which is how the [ASC 842 journal entries guide](/posts/asc-842-journal-entries/) presents it. The net effect is identical.

### The proof: deferred rent is the gap between the liability and the ROU asset

Compare the two schedules at the same dates:

| Month | Lease liability | ROU asset | Liability − ROU asset | ASC 840 deferred rent |
|---|---|---|---|---|
| 12 | 117,889.60 | 112,738.27 | 5,151.33 | 5,151.33 |
| 24 | 61,632.63 | 58,129.96 | 3,502.67 | 3,502.67 |
| 36 | 0.00 | 0.00 | 0.00 | 0.00 |

That is not a coincidence. The ROU asset is amortized by straight-line cost less interest, while the liability is reduced by cash less interest, so the difference between the two balances is cumulative straight-line cost less cumulative cash: the old deferred rent balance. ASC 842-20-35-3(b) says the same thing in Codification language: after commencement the operating lease ROU asset equals the liability adjusted for prepaid or accrued lease payments (plus unamortized initial direct costs and lease incentives, and less impairment, none of which this lease has). Deferred rent did not disappear under ASC 842. It was netted into the asset. When an auditor asks why the ROU asset is smaller than the liability on an operating lease, this is the answer.

## The Transition Entry

Companies that adopted ASC 842 with an existing deferred rent balance had to clear it. For an operating lease in place at the adoption date, ASC 842-10-65-1(l) measures the lease liability at the present value of the remaining minimum rental payments, and 842-10-65-1(m) measures the initial ROU asset as that liability adjusted for prepaid or accrued lease payments, the remaining balance of any lease incentives received, unamortized initial direct costs, and certain impairment and exit-cost balances. A deferred rent credit is accrued rent, so it reduces the ROU asset.

Suppose the worked lease had been running under ASC 840 and the company adopted ASC 842 at the start of month 25, when deferred rent stood at $3,502.67. The remaining 12 payments discounted at 6% give a lease liability of $61,632.63 (in practice the rate is the one established at the application date, so the tie to an as-if-ASC-842 schedule is exact only when that rate matches). The ROU asset is $61,632.63 − $3,502.67 = $58,129.96, the same figure the ASC 842 schedule shows at that date:

| Account | Debit | Credit |
|---|---|---|
| Right-of-use asset | 58,129.96 | |
| Deferred rent liability (cleared) | 3,502.67 | |
| Lease liability | | 61,632.63 |

No equity adjustment is needed on this lease because straight-line cost was already correct under ASC 840; the entry only reclassifies. A tenant improvement allowance still being amortized at transition follows the same path: the unamortized incentive balance reduces the ROU asset, and the straight-line cost going forward is lower because that balance is part of the remaining cost spread over the remaining term.

## Where Deferred Rent Still Exists

Three places still produce a straight-line-versus-cash difference that needs its own account:

- **Short-term leases under the practical expedient.** A lease of 12 months or less with no purchase option the lessee is reasonably certain to exercise can stay off the balance sheet (ASC 842-20-25-2). Its payments are still recognized on a straight-line basis over the term, so a free first month or a mid-term step-up creates accrued rent exactly as under ASC 840. Most companies label it accrued or deferred rent and keep it current.
- **Lessors with operating leases.** A lessor recognizes operating lease income on a straight-line basis over the term (ASC 842-30-25-11), assuming collectibility of the payments is probable. When cash lags straight-line income, the difference is a straight-line rent receivable, often still called deferred rent receivable. The lessor's monthly entry debits cash for the amount collected, debits the straight-line rent receivable for the shortfall, and credits rental income for the straight-line amount.
- **Leases outside the standard's balance-sheet model** for other reasons, such as a lease not yet commenced where the lessee has made payments (prepaid rent), which is an asset until commencement and then folds into the ROU asset.

Under IFRS 16 the question largely goes away for lessees: every lease on the balance sheet is treated like an ASC 842 finance lease, with front-loaded interest plus straight-line depreciation and no straight-line lease cost. Only the short-term and low-value exemptions (IFRS 16.6) still expense payments straight-line, so accrued rent can arise there. The [ASC 842 vs. IFRS 16 comparison](/posts/asc-842-vs-ifrs-16/) covers the differences.

## Building the Straight-Line Rent Schedule in Excel

The whole thing fits in one sheet with the annual rate in cell B1, the commencement date in B2, the opening ROU asset in J2, and one row per month starting in row 3. Use these columns:

| Column | Content | Formula (row 3) |
|---|---|---|
| A | Month number | `1`, then `=A3+1` |
| B | Date | `=EDATE($B$2,A3-1)` |
| C | Contractual cash payment | typed input, including `0` for free months |
| D | Straight-line cost | `=SUM($C$3:$C$38)/COUNT($C$3:$C$38)` |
| E | Cumulative difference (ASC 840 deferred rent) | `=D3-C3` in row 3, then `=E3+D4-C4` and fill down |
| F | Opening lease liability | `=NPV($B$1/12,$C$3:$C$38)` in row 3, then `=I3` in row 4 and fill down |
| G | Interest | `=F3*$B$1/12` (format to cents; do not round, or the last row will not land on zero) |
| H | ROU amortization | `=D3-G3` |
| I | Closing lease liability | `=F3+G3-C3` |
| J | Closing ROU asset | `=J2-H3` |
| K | Check | `=I3-J3-E3`, which is zero every row when J2 equals the opening liability (no initial direct costs, prepaid rent, or incentives); otherwise it shows a constant equal to those adjustments |

Three notes on the formulas:

- `NPV` assumes payments at period end, which matches the worked lease. For payments in advance, discount each payment one period less (multiply the NPV by `(1+$B$1/12)`) or build the discount factors explicitly; a payment made on the commencement date itself is excluded from the liability and added to the ROU asset instead (ASC 842-20-30-1 and 842-20-30-5).
- Fix the range in column D to the exact term so an extra row of payments does not silently change the straight-line amount. That is the single most common error in hand-built schedules.
- Only fixed payments and in-substance fixed payments belong in column C. A CPI-based escalation is a variable payment: it enters the measurement at the index in effect at commencement (ASC 842-10-30-5(b)), later index changes are not remeasured on their own (842-10-35-5), and the differences hit expense as incurred rather than the straight-line base (842-20-25-6(b)).

The free version of the [ASC 842 Lease Accounting Workbook](/templates/asc842/) builds this schedule for three leases from a Setup tab and a Lease Data tab, including free months and escalations, so you can compare your hand-built sheet against it. The full workbook adds the journal entry generator, the rollforward, and the reconciliation that ties the liability and ROU asset to the general ledger every close.

## Common Mistakes

- **Carrying a deferred rent liability after adopting ASC 842.** If the lease is on the balance sheet, that balance belongs inside the ROU asset. A surviving deferred rent account usually means the transition entry was booked against equity or the ROU asset was set equal to the liability without the adjustment.
- **Leaving free months out of the term.** The lease term starts on the commencement date, when the lessor makes the asset available for use, not when rent starts. Free months are inside both the straight-line cost and the liability.
- **Treating index-based escalations as fixed.** Fixed 3% step-ups are in the straight-line base. CPI adjustments are not; they are variable payments recognized as incurred.
- **Booking a tenant improvement allowance as income.** It is a lease incentive: it reduces the lease payments used to measure the liability, reduces the ROU asset, and lowers straight-line cost over the term.
- **Skipping interest in a free month.** No cash does not mean no interest. The liability grows in a rent-free month, which is why the month-one entry above credits the liability.
- **Straight-lining over the wrong term.** Renewal options the lessee is reasonably certain to exercise extend the term for both the straight-line cost and the liability. Change the term and both schedules change.

## Related Guides

- [ASC 842 journal entries: operating and finance lease examples](/posts/asc-842-journal-entries/)
- [How to build an ASC 842 amortization schedule in Excel](/posts/asc-842-amortization-schedule-excel/)
- [Right-of-use asset calculation under ASC 842](/posts/right-of-use-asset-calculation-asc-842/)
- [Operating lease vs. finance lease: how to classify each](/posts/operating-vs-finance-lease/)
- [The complete ASC 842 lease accounting guide](/posts/asc-842-lease-accounting-guide/)

*This article is general information for finance professionals, not accounting, tax, or legal advice. Confirm treatment for your facts with your auditor.*
