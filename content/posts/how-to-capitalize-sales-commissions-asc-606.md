---
title: "How to Capitalize Sales Commissions Under ASC 606 (With Excel Walkthrough)"
date: 2026-03-10
description: "Step-by-step guide to capitalizing and amortizing sales commissions under ASC 606 and ASC 340-40. Includes journal entries, amortization methods, and a practical Excel approach."
tags: ["ASC 606", "ASC 340-40", "commission accounting", "deferred commissions", "revenue recognition", "SaaS accounting"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
---

If your company pays sales commissions on contracts longer than 12 months, you're probably required to capitalize those costs under **ASC 606 (ASC 340-40)**. That means you can't just expense the commission when it's paid — you need to spread it over the period of benefit.

This guide walks through exactly how to do that, step by step.

## What ASC 606 Requires for Commission Costs

ASC 340-40 (the companion standard to ASC 606) says that **incremental costs of obtaining a contract** — like sales commissions — must be capitalized as an asset and amortized over the period the entity expects to benefit from the contract.

The key criteria:

1. **The cost is incremental** — it wouldn't have been incurred without the contract (sales commissions qualify; base salary doesn't)
2. **The cost is expected to be recovered** — through future revenue from the contract
3. **The contract term exceeds 12 months** — otherwise you can use the practical expedient and expense immediately

## The Practical Expedient (When You Can Skip Capitalization)

If the amortization period would be **12 months or less**, ASC 340-40-25-4 allows you to expense the commission immediately. This is the practical expedient, and most companies use it for:

- Month-to-month contracts
- Annual contracts with no expected renewal premium
- Short-term professional services engagements

If all your contracts are annual or shorter, you may not need to capitalize at all. But if you have multi-year deals — especially common in SaaS — keep reading.

## Step 1: Identify Commissions to Capitalize

Pull your commission payment data and classify each deal:

| Deal | Contract Term | Commission | Amortization Type |
|------|--------------|------------|-------------------|
| Acme Corp | 36 months | $15,000 | Contract Term |
| Beta Inc | 6 months | $3,000 | Immediately Expensed |
| Gamma LLC | 24 months | $8,000 | Estimated Benefit Period |

- **Contract Term**: Amortize over the contract length (most common)
- **Estimated Benefit Period**: Amortize over the expected customer relationship, including renewals (requires judgment)
- **Immediately Expensed**: Practical expedient for contracts ≤ 12 months

## Step 2: Calculate Monthly Amortization

For straight-line amortization (which is what most companies use):

**Monthly Amortization = Commission Amount ÷ Amortization Period (months)**

Example: $15,000 commission on a 36-month contract = **$416.67/month**

## Step 3: Build Your Amortization Schedule

You need a month-by-month waterfall showing:

- Each deal's starting balance
- Monthly amortization amount
- Remaining deferred commission asset

This is where Excel gets tedious fast. For 10 deals, it's manageable. For 50+, you need a structured workbook with dynamic period selection — not a manual spreadsheet you rebuild every month.

## Step 4: Generate Journal Entries

Each period, you'll book two (or three) types of journal entries:

### Capitalization Entry (new commissions)
```
DR  Deferred Commission Asset    $15,000
    CR  Cash / Accrued Commissions         $15,000
```

### Amortization Entry (monthly expense)
```
DR  Commission Expense (Amortization)    $416.67
    CR  Deferred Commission Asset                  $416.67
```

### Immediate Expense Entry (practical expedient deals)
```
DR  Commission Expense    $3,000
    CR  Cash / Accrued Commissions    $3,000
```

## Step 5: Reconcile and Prepare the Rollforward

Your auditors will want a **rollforward schedule** showing:

| | Amount |
|---|---|
| Beginning Deferred Commission Balance | $XX,XXX |
| + New Capitalizations | $XX,XXX |
| − Amortization Expense | ($X,XXX) |
| = Ending Deferred Commission Balance | $XX,XXX |

This needs to tie to your general ledger balance. If it doesn't, you have a reconciliation issue to investigate before close.

## Common Mistakes

1. **Capitalizing base salary** — only incremental costs qualify. If the rep gets paid regardless of the deal, it's not incremental.
2. **Using the wrong amortization period** — contract term vs. estimated benefit period is a policy election. Be consistent and document your rationale.
3. **Forgetting deal amendments** — if a contract is extended or modified, you may need to adjust the remaining amortization.
4. **No reconciliation process** — if your JE amounts don't tie to your amortization schedule, you'll find out during the audit. Don't wait.

## The Excel Problem

Most finance teams start with a manual spreadsheet. It works for 5-10 deals. Then the contract base grows, deals renew, amendments happen, and suddenly you're spending hours every month maintaining a fragile workbook that nobody else can follow.

The options are usually:

1. **Keep the manual spreadsheet** and accept the risk
2. **Buy commission accounting software** ($30k–$100k+/year)
3. **Use a structured Excel workbook** that handles the complexity without the software price tag

If you're in the "too many deals for manual, too early for enterprise software" zone — that's exactly what we built.

## Get the Workbook

Our [ASC 606 Commission Accrual Workbook](https://kdeskaccounting.gumroad.com) handles everything in this guide:

- **50-deal capacity** with three amortization methods
- **Automated journal entries** with GL account mapping
- **Month-by-month amortization waterfall** with dynamic period selection
- **Rollforward schedule** that ties to your amortization detail
- **Reconciliation tab** — all variances should show $0
- **No macros** — pure Excel formulas, works everywhere

$79, one time. No subscription. [Get it here →](https://kdeskaccounting.gumroad.com)

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](https://kdeskaccounting.gumroad.com)*
