---
title: "How to Capitalize Sales Commissions Under ASC 606 (With Excel Walkthrough)"
date: 2026-03-10
lastmod: 2026-09-01
description: "Step-by-step guide to capitalizing and amortizing sales commissions under ASC 606 and ASC 340-40. Which costs qualify, the practical expedient, contract term vs. expected customer life, journal entries, the rollforward your auditor asks for, and a practical Excel approach."
summary: "Most finance teams know they need to capitalize commissions under ASC 606 — but deciding which costs qualify, picking the amortization period, and building the actual schedule is where things break down. Here's a step-by-step walkthrough with worked numbers, journal entries, and a practical Excel approach."
tags: ["ASC 606", "ASC 340-40", "commission accounting", "deferred commissions", "revenue recognition", "SaaS accounting", "Excel template"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 1
product: asc606
faq:
  - q: "Do I have to capitalize sales commissions under ASC 606?"
    a: "Yes, if the commission is an incremental cost of obtaining a contract and you expect to recover it (ASC 340-40-25-1). The one exception is the practical expedient: if the amortization period would be one year or less, you may expense the commission as incurred (ASC 340-40-25-4)."
  - q: "Over what period do you amortize capitalized commissions?"
    a: "Over the period the entity expects to benefit from the contract. If the commission paid on renewal is commensurate with the initial commission, amortize over the initial contract term. If renewal commissions are lower or zero, the benefit period extends into expected renewals — commonly the expected customer life."
  - q: "What is the practical expedient for commission costs?"
    a: "ASC 340-40-25-4 lets you expense incremental costs of obtaining a contract as incurred if the amortization period would otherwise be one year or less. It is an accounting policy election, applied consistently, and typically covers month-to-month and annual contracts with commensurate renewal commissions."
  - q: "Are payroll taxes on commissions capitalized?"
    a: "Employer payroll taxes and similar fringe costs that are incurred only because the commission was paid are incremental, and many companies capitalize them alongside the commission. Base salary, quota-based bonuses that are not tied to a specific contract, and recoverable draws are not capitalized. Document the policy either way."
  - q: "What is the journal entry to capitalize a sales commission?"
    a: "Debit Deferred Commission Asset (or Capitalized Contract Costs) and credit Accrued Commissions or Cash for the commission earned. Each month, debit Commission Expense and credit Deferred Commission Asset for that period's amortization."
---

Under ASC 606, the cost of winning a multi-year SaaS contract does not hit the P&L the month the rep gets paid. It goes on the balance sheet and unwinds over the period the contract benefits the company. The rule is short. The mechanics — deciding which costs qualify, picking the amortization period, building a schedule that ties to the general ledger every month — are where finance teams get stuck.

This guide walks through exactly how to do that, step by step, with the numbers.

## What ASC 606 Requires for Commission Costs

ASC 340-40 (the companion standard to ASC 606, "Other Assets and Deferred Costs — Contracts with Customers") says that the **incremental costs of obtaining a contract** — sales commissions being the textbook case — must be capitalized as an asset if the entity expects to recover them (ASC 340-40-25-1), then amortized on a systematic basis consistent with the transfer of the goods or services to which the asset relates (ASC 340-40-35-1).

Three criteria drive the analysis:

1. **The cost is incremental** — it would not have been incurred if the contract had not been obtained. A commission paid on signature qualifies. A rep's base salary does not; it is paid whether or not the deal closes.
2. **The cost is expected to be recovered** — through the revenue from that contract (and, where relevant, anticipated renewals).
3. **The amortization period exceeds 12 months** — otherwise the practical expedient lets you expense the cost as incurred.

### Which costs qualify

| Cost | Capitalize? | Why |
|------|-------------|-----|
| Commission to the closing rep on a new deal | Yes | Incremental, directly tied to the contract |
| Commission to the sales manager or SDR on the same deal | Usually yes | Incremental if it is paid only because this contract closed |
| Employer payroll taxes on the commission | Commonly yes | Incurred only because the commission was paid; policy election, document it |
| Base salary | No | Paid regardless of contract outcome |
| Quota-attainment or pooled bonuses | Judgment | Not capitalized if the bonus depends on aggregate performance rather than a specific contract |
| Recoverable draws against future commissions | No | Not incremental until earned |
| Commissions on renewals | Yes, evaluated separately | Each renewal commission is its own asset with its own amortization period |

## The Practical Expedient (When You Can Skip Capitalization)

If the amortization period would be **one year or less**, ASC 340-40-25-4 allows you to expense the commission as incurred. This is a policy election, applied consistently. It typically covers:

- Month-to-month and other short-term contracts
- Annual contracts where the renewal commission is commensurate with the initial commission (so the benefit period is the one-year term)
- Short-term professional services engagements

If all your contracts are annual and you pay the same commission rate on renewals, you may not need to capitalize at all. If you have multi-year deals — or annual deals with reduced or zero renewal commissions — keep reading.

## Step 1: Identify Commissions to Capitalize

Pull the commission payout data from your comp system for the period and classify each deal. The classification is what determines the amortization schedule:

| Deal | Contract term | Renewal commission | Commission | Amortization basis | Period |
|------|--------------|-------------------|------------|-------------------|--------|
| Acme Corp | 36 months | Commensurate | $15,000 | Contract term | 36 mo |
| Beta Inc | 6 months | n/a | $3,000 | Practical expedient | Expensed |
| Gamma LLC | 12 months | None on renewal | $8,000 | Expected customer life | 48 mo |

- **Contract term** — amortize over the contract length. Use this when renewal commissions are *commensurate* with the initial commission, because the initial commission only "bought" the initial term.
- **Expected customer life (estimated benefit period)** — amortize over the anticipated relationship including renewals. Use this when renewal commissions are lower than the initial commission (or zero), because the initial commission also bought the renewals. This requires judgment: support it with churn data and document the estimate.
- **Practical expedient** — expense immediately when the amortization period would be 12 months or less.

The commensurate-versus-not-commensurate question (discussed at length by the FASB's Transition Resource Group) is the single biggest judgment in commission accounting. If your plan pays 10% on new business and 10% on renewals, contract term is defensible. If it pays 10% on new business and 2% on renewals, auditors will expect an expected-customer-life analysis.

## Step 2: Calculate Monthly Amortization

For straight-line amortization:

**Monthly amortization = Capitalized commission ÷ Amortization period (months)**

| Deal | Capitalized | Period | Monthly amortization |
|------|-------------|--------|---------------------|
| Acme Corp | $15,000 | 36 | $416.67 |
| Gamma LLC | $8,000 | 48 | $166.67 |
| Beta Inc | — | expensed | — |

Straight-line is appropriate when the service transfers ratably, which is the case for most subscription contracts. If the pattern of transfer is not ratable (usage-based or heavily front-loaded arrangements), the amortization pattern should follow the transfer pattern.

## Step 3: Build the Amortization Waterfall

The waterfall is the working schedule: one row per deal, one column per month, showing the amortization that hits each period plus the remaining asset balance. For the two capitalized deals above, both commencing in January:

| Deal | Capitalized | Jan | Feb | Mar | … | Balance at Mar 31 |
|------|-------------|-----|-----|-----|---|------------------|
| Acme Corp | $15,000 | $416.67 | $416.67 | $416.67 | … | $13,750.00 |
| Gamma LLC | $8,000 | $166.67 | $166.67 | $166.67 | … | $7,500.00 |
| **Total** | **$23,000** | **$583.34** | **$583.34** | **$583.34** | … | **$21,250.00** |

Each month's column total is that month's amortization journal entry. Each row's remaining balance is that deal's contribution to the deferred commission asset on the balance sheet.

This is where Excel gets tedious fast. Ten deals with one commencement date is manageable. Fifty deals commencing in different months, with different amortization periods and a few mid-term amendments, is a schedule you rebuild every month — unless the workbook has dynamic period selection so the whole file rolls forward when you change one cell.

## Step 4: Generate Journal Entries

Each period you book two or three entries.

### Capitalization entry (new commissions earned in the period)
```
DR  Deferred Commission Asset            23,000.00
    CR  Accrued Commissions (or Cash)              23,000.00
```

Capitalize when the commission is *earned* — typically when the contract is signed and the obligation to pay exists — not when the rep is paid. If your plan pays on cash collection, you still accrue the liability and the asset at signature.

### Amortization entry (monthly expense)
```
DR  Commission Expense (Amortization)       583.34
    CR  Deferred Commission Asset                    583.34
```

### Immediate expense entry (practical expedient deals)
```
DR  Commission Expense                    3,000.00
    CR  Accrued Commissions (or Cash)               3,000.00
```

Present amortization of capitalized commissions in the same line as other sales compensation (sales and marketing expense), not as amortization of intangibles.

## Step 5: Reconcile and Prepare the Rollforward

Your auditors will want a **rollforward** of the deferred commission asset each period, and it needs to tie to the general ledger balance to the penny:

| | Q1 |
|---|---|
| Beginning deferred commission balance | $0.00 |
| + New capitalizations | $23,000.00 |
| − Amortization expense | ($1,750.02) |
| − Impairment / write-offs | $0.00 |
| = Ending deferred commission balance | $21,249.98 |

Two reconciliations sit behind this:

1. **Schedule to GL** — the ending balance on the waterfall equals the GL balance in the deferred commission account. If it does not, the JE was booked from a different version of the schedule than the one you are looking at.
2. **Capitalizations to the comp system** — the commissions you capitalized equal the commissions your compensation system says were earned on eligible deals. This is the reconciliation that goes wrong most often, because RevOps changes plan rules without telling accounting. Reconcile to the payout report *exactly*, then explain every difference (clawbacks, splits, draws) rather than plugging it.

Also present current versus non-current: the portion of the asset that will amortize within 12 months is current; the rest is non-current.

## Impairment and Contract Changes

ASC 340-40-35-3 requires an impairment loss when the carrying amount of the asset exceeds the remaining consideration the entity expects to receive, less the direct costs of providing the service. In practice this comes up when a customer churns early or downgrades: write the remaining unamortized commission off to expense in the period the change becomes probable.

Contract modifications work the other way. If a customer extends or upsizes mid-term and a new commission is paid, that commission is a new asset amortized over its own benefit period. Do not restart the original asset's schedule.

## Common Mistakes

1. **Capitalizing base salary or non-incremental bonuses.** Only costs that exist because the contract exists qualify.
2. **Defaulting to contract term when renewal commissions are not commensurate.** This understates the asset and front-loads expense. Auditors check the renewal rate in the comp plan.
3. **Ignoring the practical expedient entirely.** If everything is annual with commensurate renewals, you are building schedules you do not need.
4. **Forgetting deal amendments and early terminations.** Amendments create new assets; terminations trigger impairment. Both need a process, not a memory.
5. **No reconciliation to the comp system.** If the capitalized amount does not tie to what the compensation system paid, the schedule is wrong, and you will find out during the audit.
6. **Rebuilding the schedule every month.** A schedule that is re-keyed each close is a schedule that drifts. Build it once with dynamic period selection.

## The Excel Problem

Most finance teams start with a manual spreadsheet. It works for 5–10 deals. Then the contract base grows, deals renew, amendments happen, and suddenly you are spending hours every month maintaining a fragile workbook that nobody else can follow.

The options are usually:

1. **Keep the manual spreadsheet** and accept the risk
2. **Buy commission accounting software** ($30k–$100k+/year)
3. **Use a structured Excel workbook** that handles the complexity without the software price tag

If you are in the "too many deals for manual, too early for enterprise software" zone, that is exactly what we built. You can also run a single deal through the [free ASC 606 commission calculator](/calculator/) in your browser to see the schedule shape before you build anything.

## Get the Workbook

The [ASC 606 Commission Accrual Workbook](/templates/asc606/) handles everything in this guide:

- **50-deal capacity** with all three amortization bases — contract term, expected customer life, practical expedient
- **Month-by-month amortization waterfall** with dynamic period selection
- **Automated journal entries** with GL account mapping
- **Rollforward schedule** that ties to your amortization detail, split current and non-current
- **Reconciliation tab** — all variances should show $0
- **No macros** — pure Excel formulas, works on Windows and Mac

$79, one time. No subscription. [Get it here →](https://kdeskaccounting.gumroad.com/l/mwmwpe)

Or [try the free 5-deal version](https://kdeskaccounting.gumroad.com/l/cjexre) before you buy — same tabs, same formulas, limited to 5 deals and 24 months.

## Frequently Asked Questions

**Do I have to capitalize sales commissions under ASC 606?**
Yes, if the commission is an incremental cost of obtaining a contract and you expect to recover it (ASC 340-40-25-1). The exception is the practical expedient: if the amortization period would be one year or less, you may expense the commission as incurred (ASC 340-40-25-4).

**Over what period do you amortize capitalized commissions?**
Over the period the entity expects to benefit from the contract. If the renewal commission is commensurate with the initial commission, amortize over the initial contract term. If renewal commissions are lower or zero, the benefit period extends into expected renewals — commonly the expected customer life.

**What is the practical expedient for commission costs?**
ASC 340-40-25-4 lets you expense incremental costs of obtaining a contract as incurred if the amortization period would otherwise be one year or less. It is a policy election applied consistently, and typically covers month-to-month and annual contracts with commensurate renewal commissions.

**Are payroll taxes on commissions capitalized?**
Employer payroll taxes and similar fringe costs incurred only because the commission was paid are incremental, and many companies capitalize them alongside the commission. Base salary, quota-based bonuses not tied to a specific contract, and recoverable draws are not capitalized. Document the policy either way.

**What is the journal entry to capitalize a sales commission?**
Debit Deferred Commission Asset (or Capitalized Contract Costs) and credit Accrued Commissions or Cash for the commission earned. Each month, debit Commission Expense and credit Deferred Commission Asset for that period's amortization.

## Related Guides

- [SaaS Deferred Revenue: How to Track It in Excel](/posts/saas-deferred-revenue-excel/) — the revenue side of the same contracts; the commission asset and the contract liability should move together.
- [How to Build a SaaS Metrics Dashboard in Excel](/posts/saas-metrics-dashboard-excel/) — capitalized commissions change the timing of S&M expense, which changes CAC. Keep the two consistent.
- [Month-End Close Checklist for Controllers](/posts/month-end-close-checklist-controllers/) — where the deferred commission rollforward sits in the close calendar.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
