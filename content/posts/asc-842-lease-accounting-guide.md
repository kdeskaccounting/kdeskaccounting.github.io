---
title: "ASC 842 Lease Accounting: The Complete Guide for Controllers (With Excel Examples)"
date: 2026-09-02
lastmod: 2026-09-02
description: "ASC 842 lease accounting end to end: scope, classification tests, discount rate, ROU asset and lease liability, journal entries, modifications, disclosures, IFRS 16 differences, and an Excel template."
summary: "Everything a controller needs to run ASC 842 in Excel — what counts as a lease, the five classification tests, the discount rate election, initial and subsequent measurement with one worked example, the journal entries, modifications, the disclosures, and where ASC 842 splits from IFRS 16. With links to the deep-dive guides and a workbook that ties to $0."
tags: ["ASC 842", "lease accounting", "operating lease", "finance lease", "ROU asset", "lease liability", "Excel template", "GAAP", "controller"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 0
product: asc842
faq:
  - q: "What is ASC 842 in simple terms?"
    a: "ASC 842 is the US GAAP lease standard that puts nearly every lease longer than 12 months on the balance sheet as a right-of-use asset and a lease liability. Operating leases show a single straight-line lease cost on the income statement; finance leases show amortization plus interest. It replaced ASC 840, which kept operating leases off the balance sheet."
  - q: "How do you calculate the lease liability under ASC 842?"
    a: "Discount the remaining lease payments to present value at the rate implicit in the lease, or, if that rate is not readily determinable, your incremental borrowing rate. A 60-month lease at $5,000 a month discounted at 5% annually (5%/12 monthly) has an opening liability of $264,953.53."
  - q: "What is the difference between an operating lease and a finance lease under ASC 842?"
    a: "Both go on the balance sheet. A finance lease meets any one of five criteria at commencement (ownership transfer, a purchase option reasonably certain to be exercised, major part of economic life, substantially all of fair value, or a specialized asset) and is expensed as amortization plus interest. Everything else is an operating lease, expensed as a single straight-line lease cost."
  - q: "Can private companies use a risk-free discount rate under ASC 842?"
    a: "Yes. Under ASC 842-20-30-3, as amended by ASU 2021-09, a non-public entity can elect to use a risk-free rate (for example, the US Treasury rate for a comparable term) instead of the incremental borrowing rate. The election is made by class of underlying asset, and it usually produces a higher liability because the rate is lower."
  - q: "Are short-term leases on the balance sheet under ASC 842?"
    a: "Not if you elect the short-term lease exemption. Leases with a term of 12 months or less at commencement and no purchase option the lessee is reasonably certain to exercise can be kept off the balance sheet, with payments expensed straight-line. The election is made by class of underlying asset and the short-term lease cost is disclosed."
  - q: "What is the difference between ASC 842 and IFRS 16?"
    a: "IFRS 16 has a single lessee model: every lease is treated like an ASC 842 finance lease, with depreciation and interest. ASC 842 keeps the operating lease category with straight-line cost. IFRS 16 also adds a low-value asset exemption and puts the interest portion of lease payments wherever the entity classifies interest in the cash flow statement, while ASC 842 puts operating lease payments in operating activities."
---

ASC 842 is short to state and long to run. Nearly every lease longer than a year goes on the balance sheet as a right-of-use asset and a lease liability. The work is everything after that sentence: deciding what counts as a lease, classifying it, choosing a discount rate, measuring the two balances, building a schedule that survives a modification, producing entries every month, and disclosing a maturity table at year-end that ties to the general ledger.

This guide walks the whole path in the order a controller meets it, with one worked lease carried through and links to the deeper guides where the math gets specific. If you would rather watch than read, the four-minute walkthrough below runs the same numbers through the workbook tab by tab.

{{< youtube bfCMoceDcso >}}

## What ASC 842 Changed From ASC 840

Under ASC 840, an operating lease was a footnote. Rent expense hit the income statement, the future commitment sat in a disclosure, and the balance sheet showed nothing. Analysts capitalized the commitments themselves, which is roughly why the FASB issued ASC 842 in 2016: the balance sheet was missing an obligation everyone was already pricing in.

ASC 842 keeps two lessee classifications, operating and finance (the old capital lease, renamed), but puts both on the balance sheet. The classification now decides income statement shape, not recognition. A finance lease produces front-loaded amortization plus interest; an operating lease produces one straight-line lease cost. The balance sheet looks the same either way: a right-of-use asset and a lease liability split between current and non-current.

For a Series A to C SaaS company the practical scope is an office lease, a few pieces of equipment, maybe a colocation cabinet and a vehicle. Small portfolio, large balances, and an auditor who asks for the schedule first.

## Scope: What Counts as a Lease

A contract is or contains a lease if it conveys the right to control the use of an identified asset for a period of time in exchange for consideration (ASC 842-10-15). Two tests sit inside that sentence:

- **Identified asset.** The asset is explicitly or implicitly specified, and the supplier does not have a substantive right to substitute it. A specific floor of a building is identified. Capacity on a shared server farm usually is not.
- **Control.** The customer gets substantially all of the economic benefits from use and directs how and for what purpose the asset is used. If the supplier decides how the asset is operated, you have a service contract, not a lease.

Embedded leases are where this bites: a data-center colocation agreement that reserves a specific cabinet, a logistics contract that dedicates a specific truck, an equipment-plus-service bundle. Read those contracts once and document the conclusion.

### The practical expedients worth electing

Three elections do most of the simplifying:

1. **Short-term leases.** A lease with a term of 12 months or less at commencement and no purchase option the lessee is reasonably certain to exercise can stay off the balance sheet, expensed straight-line. Elect it by class of underlying asset and disclose the short-term lease cost.
2. **Non-lease components.** Common-area maintenance, utilities and service bundled into a lease payment are not lease payments. You can separate them (allocate on relative standalone price) or elect, by asset class, to combine them with the lease component and capitalize the whole payment. Combining is simpler and produces a larger liability.
3. **Portfolio approach.** Leases with similar characteristics can be accounted for as a portfolio, most usefully for the discount rate on a fleet of similar assets.

Write each election into the accounting policy memo. Auditors test elections, not intentions.

## Classification: The Five Tests

Classification happens at commencement and is reassessed only when the lease is modified (and the modification is not a separate contract) or when the lease term or a purchase-option assessment changes. A lease is a finance lease if any one of five criteria in ASC 842-10-25-2 is met:

1. Ownership transfers to the lessee by the end of the term.
2. The lease has a purchase option the lessee is reasonably certain to exercise.
3. The lease term is for the major part of the remaining economic life of the asset.
4. The present value of the payments plus any residual value guarantee equals or exceeds substantially all of the asset's fair value.
5. The asset is so specialized it has no alternative use to the lessor at the end of the term.

"Major part" and "substantially all" are not defined in the standard; the legacy 75% and 90% thresholds are the common bright lines in practice, and the workbook applies them as defaults you can override. A five-year office lease in a building with a 40-year life fails every test and is operating. A 48-month lease on production equipment with a $1 buyout meets test 2 and is finance.

Run the tests on every lease and keep the worksheet. The full walkthrough of each criterion, with a classification table and the EBITDA consequences, is in [how to classify a lease as operating or finance](/posts/operating-vs-finance-lease/).

## Lease Term, Options, and the Discount Rate

Two judgments feed every number that follows.

**Lease term** is the non-cancellable period plus any renewal periods the lessee is reasonably certain to exercise, plus termination-option periods the lessee is reasonably certain not to exercise. "Reasonably certain" is a high hurdle, evidenced by economic factors: significant leasehold improvements, relocation cost, a below-market renewal rate. A five-year lease with a five-year renewal at market rent and no improvements is a five-year term. Document the conclusion, because the auditor will ask why the renewal is or is not in.

**Discount rate.** Use the rate implicit in the lease if it is readily determinable. For a lessee it almost never is, because the lessor's residual value assumption is not observable, so the incremental borrowing rate applies: the rate you would pay to borrow, on a collateralized basis, over a similar term, an amount equal to the lease payments. That rate should reflect your credit, the term, and the currency.

Non-public entities have a shortcut. Under ASC 842-20-30-3, as amended by ASU 2021-09, a private company can elect to use a risk-free rate, typically the US Treasury rate for a comparable term, instead of an incremental borrowing rate. The election is made by class of underlying asset. The trade-off is measurable: a lower rate produces a higher liability and ROU asset, and can push a borderline lease across the 90% fair-value test into finance classification.

Whatever the rate, set it once in the register and let every schedule read it. Changing a rate cell in five places by hand is how a portfolio stops tying.

## Initial Measurement: Lease Liability and ROU Asset

At commencement, two numbers are recognized (ASC 842-20-30-1 and 30-5):

**Lease liability** = present value of the lease payments not yet paid, discounted at the rate above. Lease payments include fixed payments (less incentives receivable), variable payments that depend on an index or rate measured at the commencement rate, purchase-option and termination-penalty amounts that are reasonably certain, and amounts probable of being owed under a residual value guarantee. Variable payments that depend on usage or performance are excluded and expensed as incurred.

**Right-of-use asset** = lease liability + initial direct costs + prepaid lease payments − lease incentives received.

Initial direct costs are the incremental costs that would not have been incurred without executing the lease: broker commissions, yes; legal fees and internal time, no. A tenant improvement allowance the landlord pays you is a lease incentive and reduces the asset.

The component-by-component build, including what to do with a landlord allowance received after commencement, is in [how to calculate the right-of-use asset at commencement](/posts/right-of-use-asset-calculation-asc-842/).

### The worked lease

The sample lease that ships in the workbook, carried through the rest of this guide:

| Input | Value |
|-------|-------|
| Term | 60 months |
| Payment | $5,000 per month, in arrears |
| Discount rate | 5% annual (5% ÷ 12 monthly) |
| Initial direct costs | $2,500 |
| Incentives, prepaid rent | $0 |
| Classification | Operating (fails all five tests) |
| **Opening lease liability** | **$264,953.53** |
| **Opening ROU asset** | **$267,453.53** |

The liability is PV(5%/12, 60, −5,000). The asset is that liability plus the $2,500 of initial direct costs.

## Subsequent Measurement: Operating vs. Finance

The balance sheet math is identical for both types. The liability accretes interest at the discount rate and is reduced by payments; that part is a loan schedule. The difference is entirely in how the ROU asset amortizes and how the income statement is presented.

**Finance lease.** Amortize the ROU asset straight-line over the shorter of the useful life and the lease term (over the useful life if ownership transfers or a purchase option is reasonably certain). Recognize interest on the liability separately. Total cost is front-loaded because interest is highest when the liability is largest.

**Operating lease.** Recognize a single lease cost, straight-line over the term: total payments plus initial direct costs, less incentives, divided by the number of months. The ROU amortization each month is the plug: straight-line cost minus that month's interest accretion. Early in the lease the interest is large so the asset amortizes slowly; late in the lease it is the reverse. Total cost is flat.

Month one of the worked lease, as an operating lease:

| Month 1 | Amount |
|---------|--------|
| Beginning lease liability | $264,953.53 |
| Interest accretion (5% ÷ 12 × beginning liability) | $1,103.97 |
| Payment | $5,000.00 |
| Principal reduction | $3,896.03 |
| Ending lease liability | $261,057.50 |
| Straight-line lease cost (($300,000 + $2,500) ÷ 60) | $5,041.67 |
| ROU amortization (cost − interest) | $3,937.70 |
| Ending ROU asset | $263,515.83 |

If the same lease were classified as finance, the ROU asset would amortize at $267,453.53 ÷ 60 = $4,457.56 per month, interest of $1,103.97 would be presented separately, and month-one total cost would be $5,561.53 instead of $5,041.67, declining every month after.

Month 60 has to land on zero for both the liability and the asset. If a schedule ends with a residual balance, a rounding rule or a payment-timing assumption is wrong somewhere in month one. The column-by-column build, including the period-one checks, is in [how to build the ASC 842 amortization schedule in Excel](/posts/asc-842-amortization-schedule-excel/).

## Journal Entries at Commencement and Month One

Commencement is the same entry for either type. For the worked lease:

```
DR  Right-of-Use Asset             267,453.53
    CR  Lease Liability                        264,953.53
    CR  Cash (initial direct costs)              2,500.00
```

Month one, operating lease. One expense line; the liability reduction and the asset amortization are different numbers:

```
DR  Lease Expense                    5,041.67
DR  Lease Liability                  3,896.03
    CR  Cash                                     5,000.00
    CR  Right-of-Use Asset                       3,937.70
```

Month one, finance lease. Two expense lines:

```
DR  Interest Expense                 1,103.97
DR  Lease Liability                  3,896.03
    CR  Cash                                     5,000.00

DR  Amortization Expense             4,457.56
    CR  Accumulated Amortization — ROU           4,457.56
```

Short-term leases under the expedient skip all of this: debit lease expense, credit cash, straight-line. Terminations, early buyouts, and the full monthly set for both types with the account codes are in [ASC 842 journal entries with worked examples](/posts/asc-842-journal-entries/).

## Modifications and Remeasurement

Leases change. ASC 842-10-35 sets out two paths.

**A modification is a separate contract** if it grants an additional right of use not in the original lease and the price increase is commensurate with the standalone price of that right. Adding a second floor at market rent is a new lease with its own schedule; the original lease is untouched.

**Everything else is a modification of the existing lease.** Extending the term, changing the payments, or reducing the space means you reassess classification, update the discount rate as of the modification date, remeasure the liability at the new payments and rate, and adjust the ROU asset by the same amount. A partial termination (giving back space) reduces the asset proportionately and can produce a gain or loss.

**Remeasurement without a modification** is also required when specific triggers occur: a change in the lease term because an option assessment flips, a change in the assessment of a purchase option, a change in amounts probable under a residual value guarantee, or a contingency being resolved so that variable payments become fixed. In those cases the liability is remeasured; the discount rate is updated only when the term or the purchase-option assessment changes. A change in an index or rate alone, such as CPI resetting the rent, does not trigger remeasurement under ASC 842; the difference is expensed as variable lease cost.

**Impairment** follows ASC 360, not ASC 842. The ROU asset sits in an asset group and is tested for recoverability like any other long-lived asset. After an impairment, an operating lease loses its straight-line pattern: the written-down ROU asset amortizes straight-line and the interest accretion is presented on top, so total cost is no longer flat.

The workbook handles a modification by re-keying the modified inputs as of the modification date and recalculating forward, because the present-value formulas are not chained month to month. That is the single design choice that separates a schedule that survives a modification from one that has to be rebuilt.

## Presentation and Disclosure

**Balance sheet.** Operating and finance ROU assets and liabilities are presented or disclosed separately from each other and from other assets and liabilities (ASC 842-20-45). Liabilities are split current and non-current; the current portion is the principal reduction over the next 12 months, which is the sum of the next 12 months of payments minus the interest that will accrete over them.

**Income statement.** Operating lease cost sits in operating expenses, usually in the same line as the old rent. Finance lease amortization sits with depreciation and amortization; finance lease interest sits with interest expense. This is why finance classification raises EBITDA and operating classification does not.

**Cash flow statement.** Operating lease payments are operating activities. Finance lease principal is financing; finance lease interest is operating, the same as any other interest paid under ASC 230.

**Disclosures** (ASC 842-20-50) that the year-end package needs regardless of company size:

- Lease cost by type: operating, finance (amortization and interest separately), short-term, variable.
- Cash paid for amounts included in the measurement of lease liabilities, split by operating and financing cash flows, and non-cash ROU assets obtained in exchange for new liabilities.
- Weighted-average remaining lease term and weighted-average discount rate, separately for operating and finance leases.
- A maturity analysis of undiscounted lease payments by year for the next five years and a total thereafter, reconciled to the lease liabilities on the balance sheet by backing out imputed interest.
- The significant judgments: how the discount rate was determined, whether the risk-free election was made, which practical expedients were elected.

The maturity table is the one that takes time if the schedules live in separate files. Built from one register, it is a sum by year.

## ASC 842 vs. IFRS 16

If a parent or subsidiary reports under IFRS, the same lease produces different numbers. The five differences that matter:

| Topic | ASC 842 (US GAAP) | IFRS 16 |
|-------|-------------------|---------|
| Lessee classification | Operating and finance; classification drives income statement shape | Single model; every lease is accounted for like a finance lease |
| Income statement | Operating: one straight-line lease cost. Finance: amortization + interest | Always depreciation + interest, front-loaded |
| Exemptions | Short-term (≤ 12 months) | Short-term (≤ 12 months) and low-value assets (roughly $5,000 new) |
| Discount rate | Rate implicit, else incremental borrowing rate; private-company risk-free election | Rate implicit, else incremental borrowing rate; no risk-free election |
| Cash flow classification | Operating lease payments in operating activities; finance lease principal financing, interest operating | Principal in financing; interest per the entity's policy election |

The mechanics of the liability are the same under both, so one schedule engine serves both frameworks; the presentation layer differs. The full comparison, including how the low-value exemption is applied in practice, is in [IFRS 16 vs. ASC 842](/posts/asc-842-vs-ifrs-16/).

## Month-End Close for Leases

The lease steps that belong on the close calendar, in order:

- Confirm no new leases commenced, no modifications signed, and no options exercised in the period. Check with the office manager and legal, not only AP.
- Confirm every lease payment in the bank matches the payment column of the schedule for the period.
- Roll the schedule to the current period; verify month-one math still ties for any lease modified this period.
- Post the period entries from the schedule: operating lease cost, finance lease amortization and interest, short-term and variable lease cost.
- Tie the lease liability balance in the GL to the ending liability on the schedule, by lease and in total.
- Tie the ROU asset balance to the schedule the same way.
- Update the current versus non-current split; it moves every month.
- File the modification memo, option assessment, or impairment analysis if anything changed.

The full 42-task calendar those steps sit inside, with the reconciliation rows for deferred commissions, fixed assets, and revenue alongside leases, is in the [month-end close checklist for controllers](/posts/month-end-close-checklist-controllers/).

## Common Mistakes

1. **Missing embedded leases.** Colocation cabinets, dedicated equipment inside a service contract, and vehicles in a logistics agreement are the usual finds.
2. **Capitalizing non-lease components without electing to.** If you have not made the election, CAM and utilities are expensed, not discounted into the liability.
3. **Excluding a renewal that is reasonably certain.** Substantial leasehold improvements with a life beyond the initial term are the classic evidence the auditor will cite.
4. **Using an unsupported discount rate.** "We used 5%" is not a memo. Document how the incremental borrowing rate was built, or make the risk-free election and say so.
5. **Chained schedule formulas.** A schedule where each month references the previous month cannot absorb a modification; one changed input cascades into every later cell.
6. **Forgetting the current portion.** The current liability is not the next 12 payments. It is the principal reduction within those payments.

## Excel or Software?

Purpose-built lease software earns its cost at 50 or more leases, or when leases live in several entities and currencies. Below that, the accounting is well within Excel, provided the file is built for the month-end use case rather than a one-time calculation: one register, one discount rate cell per lease, a period selector that drives every tab, non-chained PV formulas, and a reconciliation that reads zero before anything is posted.

That is the design of the [ASC 842 Lease Accounting Workbook](/templates/asc842/): 20 leases, operating and finance, 120-month schedules per lease, a JE Generator that uses your GL codes, a rollforward split current and non-current, the maturity analysis for the footnote, and a reconciliation tab that compares the entries to the register. Every number in this guide's worked example comes from its sample data, and the [walkthrough video](/templates/asc842/#walkthrough) runs through each tab in four minutes.

**[Get the workbook — $97, one time, no subscription →](https://kdeskaccounting.gumroad.com/l/phxigq)**

Not ready to buy? [Download the free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc): the register and the schedule, capped at three leases and 36 months, so you can test the mechanics on your own leases first.

## Frequently Asked Questions

**What is ASC 842 in simple terms?**
ASC 842 is the US GAAP lease standard that puts nearly every lease longer than 12 months on the balance sheet as a right-of-use asset and a lease liability. Operating leases show a single straight-line lease cost on the income statement; finance leases show amortization plus interest. It replaced ASC 840, which kept operating leases off the balance sheet.

**How do you calculate the lease liability under ASC 842?**
Discount the remaining lease payments to present value at the rate implicit in the lease or, if that is not readily determinable, your incremental borrowing rate. A 60-month lease at $5,000 a month discounted at 5% annually (5%/12 monthly) has an opening liability of $264,953.53.

**What is the difference between an operating lease and a finance lease under ASC 842?**
Both go on the balance sheet. A finance lease meets any one of five criteria at commencement (ownership transfer, a purchase option reasonably certain to be exercised, major part of economic life, substantially all of fair value, or a specialized asset) and is expensed as amortization plus interest. Everything else is an operating lease, expensed as a single straight-line lease cost.

**Can private companies use a risk-free discount rate under ASC 842?**
Yes. Under ASC 842-20-30-3, as amended by ASU 2021-09, a non-public entity can elect to use a risk-free rate, such as the US Treasury rate for a comparable term, instead of the incremental borrowing rate. The election is made by class of underlying asset, and it usually produces a higher liability because the rate is lower.

**Are short-term leases on the balance sheet under ASC 842?**
Not if you elect the short-term lease exemption. Leases with a term of 12 months or less at commencement and no purchase option the lessee is reasonably certain to exercise can be kept off the balance sheet, with payments expensed straight-line. The election is made by class of underlying asset and the short-term lease cost is disclosed.

**What is the difference between ASC 842 and IFRS 16?**
IFRS 16 has a single lessee model: every lease is treated like an ASC 842 finance lease, with depreciation and interest. ASC 842 keeps the operating lease category with straight-line cost. IFRS 16 also adds a low-value asset exemption, and it puts the interest portion of lease payments wherever the entity classifies interest in the cash flow statement, while ASC 842 puts operating lease payments in operating activities.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
