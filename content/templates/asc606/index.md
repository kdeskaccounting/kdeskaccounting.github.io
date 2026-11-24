---
title: "ASC 606 Commission Capitalization Excel Template"
description: "Excel workbook for capitalizing and amortizing sales commissions under ASC 340-40. Handles 50 deals, three amortization methods, cancellations and clawbacks, automated journal entries, rollforward, and reconciliation. No macros, no subscription."
summary: "The ASC 606 Commission Accrual Workbook handles your full deferred commission asset — capitalization, amortization schedule, period journal entries, and rollforward — in a single Excel file."
lastmod: 2026-11-24
date: 2026-03-16
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 2
price: 249
buy_url: "https://kdeskaccounting.gumroad.com/l/mwmwpe"
free_url: "https://kdeskaccounting.gumroad.com/l/cjexre"
free_label: "Try free 5-deal version"
video_url: "https://github.com/kdeskaccounting/kdeskaccounting.github.io/releases/download/media-2026-09/asc606.mp4"
video_poster: "/images/products/asc606-poster.png"
youtube_url: "https://youtu.be/qS52iaaD51U"
tags: ["ASC 606", "ASC 340-40", "commission accounting", "deferred commissions", "Excel template", "SaaS accounting"]
compare:
  free_name: "Free 5-deal version"
  full_name: "Full workbook"
  rows:
    - ["Deals", "5", "50"]
    - ["Amortization schedule", "24 months", "60 months"]
    - ["Setup, Commission Data and Amortization Schedule tabs", "yes", "yes"]
    - ["Three amortization bases (term, benefit period, expedient)", "yes", "yes"]
    - ["Cancel Date + Clawback % columns and an input check on every row", "yes", "yes"]
    - ["JE Generator (four entries, including cancellations / clawbacks)", "no", "yes"]
    - ["Deferred commission rollforward", "no", "yes"]
    - ["Reconciliation that ties to $0", "no", "yes"]
    - ["Dashboard", "no", "yes"]
    - ["4-minute walkthrough video", "yes", "yes"]
faq:
  - q: "Does it handle variable commission rates?"
    a: "Yes. Each deal row has its own deal amount and commission rate, and the commission is deal amount × rate — there's no fixed rate applied across the portfolio. Enter the rate that produces the commission actually paid on that deal."
  - q: "What if my contracts have renewal terms?"
    a: "Use the Estimated Benefit Period amortization type. Set the default period (original term plus expected renewals) on Setup, or give a deal its own Benefit Period Override in Commission Data. The workbook amortizes over that full period."
  - q: "Does it work on a Mac?"
    a: "Yes. Pure Excel formulas — no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac."
  - q: "What if a deal gets cancelled or amended?"
    a: "For a cancellation, enter the Cancel Date (and the Clawback % if the plan recovers the commission) on the original deal row. Amortization runs through the cancel month, the unamortized balance is released that month, and JE-004 books the clawback receivable and the net expense or recovery. For an upsell, add a new deal row for the additional commission. Don't enter negative rows: the Input Check flags them and leaves them out of the totals."
  - q: "What is the difference between Contract Term and Estimated Benefit Period?"
    a: "Contract Term amortizes over the stated contract length. Estimated Benefit Period amortizes over the expected customer relationship, including anticipated renewals. Which one applies follows the facts rather than a free policy choice: if renewal commissions are commensurate with the initial commission, the contract term; if they are lower or absent, the expected period of benefit."
  - q: "What if I have more than 50 deals?"
    a: "Email hello@kdeskaccounting.com — we can discuss a custom build."
---

If you're capitalizing sales commissions for the first time, or your current spreadsheet breaks every time a deal renews or cancels, this workbook handles the math and produces a rollforward that ties to the GL. **$249, one-time purchase. No subscription. No macros.**

[Get the Workbook ($249) →](https://kdeskaccounting.gumroad.com/l/mwmwpe)

---

## What's in the Workbook

Eight tabs, each with a specific job. You enter data on Setup and Commission Data (plus an optional period revenue on the Dashboard); every other tab calculates automatically. Formula cells are locked and input cells are unlocked on every sheet.

### Instructions

The ASC 340-40 rules the workbook follows, a quick-start guide with a link to each tab, and tips for amendments, payroll taxes and impairment.

### Setup

Company name, fiscal year start (it drives a fiscal period label such as FY2026 P01), the Selected Period that every tab follows, the default Estimated Benefit Period, and GL account codes. Change the Selected Period once; the entire workbook shifts. GL account codes are configurable — your journal entries reference your actual chart of accounts, not hardcoded placeholders.

### Commission Data (50-deal capacity)

One row per deal. Inputs: sales rep, deal ID, close date, deal amount, commission rate, contract term (months) and amortization type; optional Benefit Period Override, Cancel Date and Clawback %. The commission is deal amount × rate. Three amortization types supported:

- **Immediately Expensed** — the practical expedient, available only when the amortization period would be one year or less
- **Contract Term** — amortize over the stated contract length (most common)
- **Estimated Benefit Period** — amortize over the expected customer relationship, including anticipated renewals

The monthly amortization, status and remaining balance calculate automatically. An **Input Check** column tests every row (missing or invalid dates, amounts and terms, a rate over 100%, negative rows, a cancel date before the close date, a clawback outside 0–100%); a flagged row is left out of every total until it reads OK.

### Amortization Schedule (60 months)

Monthly amortization for each deal for the 60 months starting at the Selected Period, with the total deferred asset balance and the balances released on cancellation underneath. Amortization starts the month after the close month and runs through the cancel month for cancelled deals.

### JE Generator

Four summary journal entries for the Selected Period, rounded to cents:

1. **JE-001 Capitalization** — DR Deferred Commission Asset / CR Commissions Payable
2. **JE-002 Immediate expense** — DR Commission Expense / CR Commissions Payable
3. **JE-003 Amortization** — DR Commission Expense / CR Deferred Commission Asset
4. **JE-004 Cancellations and clawbacks** — DR Clawback Receivable (Clawback % × commission) / CR Deferred Commission Asset (the unamortized balance), with the difference to Commission Expense

GL account codes flow from Setup, and a balance check confirms debits equal credits. Below the entries, a control-total section shows the beginning asset, each movement and the ending asset.

### Reconciliation

Checks each posting entry back to Commission Data and the Amortization Schedule, the sum of deal balances against the schedule's asset balance, debits against credits, and the number of rows flagged by the Input Check. Every variance should be $0; if one isn't, this tab shows where.

### Rollforward

Month by month: beginning balance, capitalized, amortized, released on cancellation, ending balance, and a check against the schedule — the movement schedule you hand over when someone asks how the balance got there.

### Dashboard

Capitalized to date, this period's amortization, the deferred asset balance, active deals, the average amortization period, deals by amortization type, and a 60-month trend.

---

## A Worked Example — Three-Deal Capitalization

Three deals close on January 15, 2026, each at a 10% commission rate:

| Deal | Deal amount | Commission | Contract Term | Type |
|------|-----------:|-----------:|--------------|------|
| Acme Corp (3-yr SaaS) | $150,000 | $15,000 | 36 months | Contract Term |
| Beta Inc (1-yr contract, commensurate renewals) | $30,000 | $3,000 | 12 months | Immediately Expensed |
| Gamma LLC (renewal expected) | $80,000 | $8,000 | 24 months | Estimated Benefit Period, override 36 months |

**JE Generator output for January 2026 (the close month):** capitalization and immediate expense only — amortization starts the month after close.

```
JE-001  DR  1810 Deferred Commission Asset   23,000.00
            CR  2150 Commissions Payable               23,000.00
JE-002  DR  6020 Commission Expense           3,000.00
            CR  2150 Commissions Payable                3,000.00
```

**February 2026, the first amortization month:**

| Deal | Monthly Amortization | Remaining Asset |
|------|--------------------:|----------------:|
| Acme Corp | $416.67 | $14,583.33 |
| Beta Inc | — (expensed in January) | — |
| Gamma LLC | $222.22 | $7,777.78 |

```
JE-003  DR  6020 Commission Expense             638.89
            CR  1810 Deferred Commission Asset            638.89
```

The deferred asset goes from $23,000.00 to $22,361.11, and every Reconciliation variance reads $0.

**Then a cancellation.** The workbook's sample data includes the Kit's clawback illustration: a $6,000 commission closed in September 2025 on a 36-month contract, cancelled in January 2026 with a 100% clawback. In January, JE-004 debits Clawback Receivable $6,000.00, credits the Deferred Commission Asset for the $5,333.33 unamortized balance, and credits Commission Expense $666.67 — the amortization already expensed, now recovered. The asset for that deal goes to zero the same month.

All amounts are automatic. You enter the deal inputs; the workbook handles the rest across all 50 deals and all reporting periods.

---

## The Practical Expedient

ASC 340-40-25-4 allows immediate expensing of commissions when the amortization period would be one year or less. A 12-month contract qualifies only when renewals earn a commensurate commission; if renewals earn less or nothing, the period of benefit is longer and the expedient doesn't apply. Mark a qualifying deal as "Immediately Expensed" and the workbook routes the commission directly to period expense — no asset capitalization, no amortization schedule. The Input Check warns when the expedient is used on a contract longer than 12 months.

---

## Who This Is For

- Controllers at Series A–C SaaS companies implementing ASC 606 deferred commission accounting for the first time
- Finance managers maintaining a fragile manual spreadsheet that breaks when deals renew or amend
- Companies with 1–50 active deals needing amortization schedules that reconcile to the GL
- Teams preparing for their first audit or audit committee review
- Any finance team spending more than 2 hours per month close on commission accounting

---

## What It Is Not

This workbook handles the commission cost side of ASC 606 (ASC 340-40) — the asset capitalization and amortization. It does not handle revenue recognition under ASC 606 (the 5-step model, SSP allocation, contract modifications, or variable consideration). It is a standalone Excel file — there is no cloud sync, no API, no subscription.

---

## Technical Specifications

| Specification | Detail |
|---------------|---------|
| Deal capacity | 50 deals |
| Schedule length | 60 months |
| Amortization types | Immediately Expensed, Contract Term, Estimated Benefit Period |
| Cancellations | Cancel Date + Clawback % per deal (JE-004) |
| Excel version | 2016, 365, Mac (no macros) |
| File format | .xlsx |
| Formula protection | Locked formula cells, unlocked input cells |
| Price | $249 one-time |

---

## Get the Workbook

[**Get the Workbook ($249) →**](https://kdeskaccounting.gumroad.com/l/mwmwpe)

Not ready to buy? [Try the free 5-deal version](https://kdeskaccounting.gumroad.com/l/cjexre) — the Setup, Commission Data (with the cancellation and clawback columns) and Amortization Schedule tabs for 5 deals and 24 months, so you can check the schedule on your own deals. The JE Generator, rollforward, reconciliation and dashboard are in the full workbook (see the comparison above).

---

## Frequently Asked Questions

**Does it handle variable commission rates?**
Yes. Each deal row has its own deal amount and commission rate, and the commission is deal amount × rate — there's no fixed rate applied across the portfolio. Enter the rate that produces the commission actually paid on that deal.

**What if my contracts have renewal terms?**
Use the "Estimated Benefit Period" amortization type. Set the default period (original term + expected renewals) on Setup, or give a deal its own Benefit Period Override in Commission Data. The workbook amortizes over that full period.

**Does it work on a Mac?**
Yes. Pure Excel formulas — no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac.

**What if a deal gets cancelled or amended?**
For a cancellation, enter the Cancel Date (and the Clawback % if the plan recovers the commission) on the original deal row. Amortization runs through the cancel month, the unamortized balance is released that month, and JE-004 books the clawback receivable and the net expense or recovery. For an upsell, add a new deal row for the additional commission. Don't enter negative rows: the Input Check flags them and leaves them out of the totals.

**What's the difference between Contract Term and Estimated Benefit Period?**
Contract Term amortizes over the stated contract length. Estimated Benefit Period amortizes over the expected customer relationship, including anticipated renewals. Which one applies follows the facts rather than a free policy choice: if renewal commissions are commensurate with the initial commission, the contract term; if they are lower or absent, the expected period of benefit. Document the conclusion and apply it consistently.

**What if I have more than 50 deals?**
Email [hello@kdeskaccounting.com](mailto:hello@kdeskaccounting.com) — we can discuss a custom build.

## Adopting ASC 340-40 for the first time, or facing an audit?

The [ASC 340-40 Commission Capitalization Kit](/templates/asc606-kit/) ($1,997) bundles this workbook with the documentation auditors typically ask for: a technical accounting memo template and completed example, an amortization-basis decision framework, a clawback and reversal policy, a month-end close procedure, and an auditor PBC package with a disclosure footnote template.
