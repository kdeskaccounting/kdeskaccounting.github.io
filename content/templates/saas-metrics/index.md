---
title: "SaaS Metrics & ARR Dashboard Excel Template"
description: "Board-ready SaaS metrics in one Excel workbook. Enter monthly MRR movements and customer counts; MRR, ARR, Net New MRR, gross churn, NRR, ARPA, CAC, LTV, LTV:CAC, CAC payback, and Magic Number calculate automatically across 24 months. No macros, no BI tool, no subscription."
summary: "The SaaS Metrics & ARR Dashboard turns monthly MRR movements and customer counts into a board-ready KPI dashboard — MRR, ARR, NRR, churn, CAC, LTV, and CAC payback — with formulas your finance team controls and can reconcile to the P&L."
date: 2026-09-01
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 4
price: 67
buy_url: "https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard"
free_url: "https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard-free"
free_label: "Try free 6-month version"
video_url: "https://github.com/kdeskaccounting/kdeskaccounting.github.io/releases/download/media-2026-09/saas-metrics.mp4"
video_poster: "/images/products/saas-metrics-poster.png"
youtube_url: "https://youtu.be/janK2YXfmFU"
tags: ["SaaS metrics", "ARR", "MRR", "Excel template", "net revenue retention", "churn", "CAC"]
faq:
  - q: "Can I add more than 24 months?"
    a: "The workbook supports 24 months out of the box. You can extend it by copying the formula pattern down; every calculation references the row above, so the chain continues cleanly."
  - q: "What if I don't track sales and marketing spend?"
    a: "Leave the S&M Spend column blank. MRR, ARR, churn, NRR, and ARPA still calculate. CAC, LTV:CAC, and CAC payback show 0 for those months instead of an error."
  - q: "Does this connect to Stripe or my billing system?"
    a: "No. This is a standalone Excel file. You enter monthly totals manually or paste them from your billing system export — which is exactly what keeps the numbers auditable and reconcilable to your revenue schedules."
  - q: "How is the free version different?"
    a: "The free version supports 6 months of data and 9 metrics. The full version supports 24 months, adds the Magic Number (sales efficiency) metric and a 24-month trend table, and ships with 12 months of sample data pre-loaded."
  - q: "Does it work on a Mac?"
    a: "Yes. Pure Excel formulas, no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac."
  - q: "Is this a one-time purchase?"
    a: "Yes. $67, one time. No subscription. Download the file and it's yours."
---

If your board deck's ARR number and your income statement disagree two days before the meeting, the fix is not a better BI tool. It is a metrics workbook that finance owns, that ties to the same monthly revenue data the financials come from. **$67, one-time purchase. No subscription. No macros.**

[Get the Workbook ($67) →](https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard)

Not ready to buy? [Try the free 6-month version](https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard-free) — same structure, 6 months of capacity.

---

## What's in the Workbook

Five tabs. You enter data in Setup and Monthly Data; everything else calculates.

### Setup

Company name, gross margin %, fiscal year start, and the period selector that drives the Dashboard. Change the selected period once and all six KPI cards move with it.

### Monthly Data (24-month capacity)

One row per month. Inputs: New MRR, Expansion MRR, Contraction MRR, Churned MRR, new customers, churned customers, and sales & marketing spend. Beginning MRR and beginning customer count auto-chain from the prior month's ending balances, so there is nothing to carry forward by hand.

### Metrics

Every calculated metric in one table, one row per month:

| Metric | Formula in the workbook |
|--------|-------------------------|
| Ending MRR | Beginning + New + Expansion − Contraction − Churned |
| ARR | Ending MRR × 12 |
| Net New MRR | New + Expansion − Contraction − Churned |
| Gross MRR churn rate | (Contraction + Churned) ÷ Beginning MRR |
| Net Revenue Retention (monthly) | (Beginning + Expansion − Contraction − Churned) ÷ Beginning |
| Net Revenue Retention (annualized) | Monthly NRR ^ 12 |
| ARPA | Ending MRR ÷ ending customers |
| CAC | S&M spend ÷ new customers |
| LTV | ARPA × gross margin ÷ monthly churn rate |
| LTV:CAC | LTV ÷ CAC |
| CAC payback (months) | CAC ÷ (ARPA × gross margin) |
| Magic Number *(full version)* | (Net New ARR in quarter) ÷ prior-quarter S&M spend |

Null-safe throughout: months with no data show blank, not `#DIV/0!`.

### Dashboard

Six KPI cards for the selected period — Ending MRR, ARR, Net New MRR, NRR, Gross Churn, LTV:CAC — plus a 24-month trend table. Screenshot it straight into the board deck, or insert a native Excel chart from the trend table.

### Instructions

Quick start, field reference, and metric definitions with the benchmarks investors actually use (NRR above 100%, LTV:CAC of 3:1 or better, CAC payback under 12–18 months).

---

## A Worked Example — One Month

Beginning MRR $100,000 across 80 customers. During the month: $12,000 new MRR from 8 new customers, $4,000 expansion, $1,500 contraction, $3,000 churned from 2 lost customers. S&M spend $40,000. Gross margin 78%.

| Metric | Result |
|--------|--------|
| Ending MRR | $111,500 |
| ARR | $1,338,000 |
| Net New MRR | $11,500 |
| Gross MRR churn | 4.5% |
| NRR (monthly) | 99.5% |
| Ending customers | 86 |
| ARPA | $1,297 |
| CAC | $5,000 |
| CAC payback | 4.9 months |

You enter seven numbers; the workbook produces the rest, and next month's beginning balances are already populated.

---

## Why Finance Should Own This File

Sales ops dashboards count bookings. Finance counts recognized revenue. When the two live in different tools, ARR drifts from the P&L and someone spends the last two days before the board meeting reconciling them. Building the metrics off the same monthly revenue data that feeds the financials removes the gap — the full walkthrough is in [How to Build a SaaS Metrics Dashboard in Excel](/posts/saas-metrics-dashboard-excel/).

---

## Who This Is For

- Controllers and finance managers at Series A–C SaaS companies ($3M–$50M revenue)
- Finance teams that need board-ready metrics without a BI tool or a RevOps dependency
- Founders who want to see unit economics from real numbers, not a CRM pipeline
- Advisors and investors who want one standardized metrics file across portfolio companies

## What It Is Not

This is a single-product, single-currency monthly model. It does not do cohort-level retention matrices, multi-product MRR normalization, mid-month proration, or multi-currency translation. If you are past roughly 50 customers with several pricing tiers, you will eventually want a database-backed metrics layer — this workbook is the auditable bridge until then.

---

## Technical Specifications

| Specification | Detail |
|---------------|---------|
| Data capacity | 24 months (free version: 6) |
| Metrics | 11 (free version: 9) |
| Sample data | 12 months pre-loaded |
| Excel version | 2016, 365, Mac (no macros) |
| File format | .xlsx |
| Formula protection | Locked formula cells, unlocked yellow input cells |
| Price | $67 one-time |

---

## Get the Workbook

[**Get the Workbook ($67) →**](https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard)

Not ready to buy? [Try the free 6-month version](https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard-free) first. Same tabs, same formulas, 6 months of capacity.

---

## Frequently Asked Questions

**Can I add more than 24 months?**
The workbook supports 24 months out of the box. Extend it by copying the formula pattern down; every calculation references the row above, so the chain continues cleanly.

**What if I don't track sales and marketing spend?**
Leave the S&M Spend column blank. MRR, ARR, churn, NRR, and ARPA still calculate. CAC, LTV:CAC, and CAC payback show 0 for those months instead of an error.

**Does this connect to Stripe or my billing system?**
No. It is a standalone Excel file. Enter monthly totals or paste them from your billing export — that is what keeps the numbers auditable and reconcilable to your revenue schedules.

**How is the free version different?**
The free version supports 6 months of data and 9 metrics. The full version supports 24 months, adds the Magic Number metric and a 24-month trend table, and ships with 12 months of sample data.

**Does it work on a Mac?**
Yes. Pure Excel formulas, no VBA, no Windows-only features. Excel 2016, 365, and Excel for Mac.

**Is this a one-time purchase?**
Yes. $67, one time. No subscription.
