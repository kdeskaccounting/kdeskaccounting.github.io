---
title: "How to Build a SaaS Metrics Dashboard in Excel"
date: 2026-03-19
description: "Build a SaaS metrics dashboard in Excel that tracks MRR, ARR, churn, NRR, CAC, and LTV with formulas your finance team can audit."
summary: "Your board deck needs SaaS metrics. Your investors want them monthly. Here is how to build a SaaS metrics dashboard in Excel that finance actually controls — with formulas, worked examples, and the common mistakes that make dashboards unreliable."
tags: ["SaaS metrics", "ARR", "MRR", "SaaS dashboard", "Excel", "Excel template", "SaaS accounting", "churn"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 14
---

Most SaaS companies build their metrics dashboard in a BI tool owned by sales ops or RevOps. Finance inherits the numbers, spots errors, and spends the last two days before board meetings reconciling ARR to the general ledger.

There is a better way. If your finance team owns the SaaS metrics dashboard — built in Excel, tied to your actual revenue data — you eliminate the reconciliation gap entirely. The numbers in your board deck match the numbers in your financials because they come from the same source.

This post walks through the eight metrics every SaaS finance team should track, the Excel formulas behind each one, and a worked example you can follow to build your own dashboard from scratch.

---

## Why Finance Should Own the SaaS Metrics Dashboard

Sales ops cares about bookings. Finance cares about recognized revenue. When these two teams maintain separate dashboards, the numbers diverge — sometimes materially.

A finance-owned SaaS metrics dashboard solves three problems:

1. **Reconciliation to GAAP revenue.** MRR and ARR tie directly to your revenue schedules, not to CRM contract values.
2. **Auditability.** Every number traces to a formula. No black-box SQL queries or dashboard filters that change the denominator.
3. **Board-ready accuracy.** When the CFO presents ARR growth, it matches the P&L. No footnotes explaining why the dashboard says one thing and the financials say another.

If your company follows ASC 606 for revenue recognition, you already have the underlying data. The dashboard is just a structured summary layer on top of it. (If you need help with ASC 606 commission capitalization schedules, see our [ASC 606 Commission Workbook](/templates/asc606/).)

---

## The 8 Metrics Every SaaS Finance Team Tracks

### 1. MRR (Monthly Recurring Revenue)

MRR is the foundation. Every other metric derives from it.

**Definition:** The sum of all recurring subscription revenue, normalized to a monthly amount.

```excel
=SUMPRODUCT((CustomerTable[Status]="Active")*(CustomerTable[Monthly Amount]))
```

If some customers pay annually, normalize first:

```excel
=IF(CustomerTable[Billing Cycle]="Annual", CustomerTable[Contract Value]/12, CustomerTable[Contract Value])
```

**Key rule:** MRR includes only recurring amounts. Exclude one-time implementation fees, overages billed in arrears, and professional services. If it would not repeat next month under the same contract terms, it is not MRR.

### 2. ARR (Annual Recurring Revenue)

```excel
=MRR*12
```

Simple — but the nuance matters. ARR is a run-rate assumption: if nothing changed, this is what you would collect over twelve months. It is not a forecast. It is not trailing twelve-month revenue. When your board asks for ARR, they want `MRR * 12` as of a point in time.

**Do not** annualize a single strong month and call it ARR. Use the ending MRR for the period.

### 3. Net New MRR

Net New MRR decomposes MRR movement into its four components:

```excel
=New MRR + Expansion MRR - Contraction MRR - Churned MRR
```

In Excel, set up a monthly input table with these four columns:

| Month | New MRR | Expansion MRR | Contraction MRR | Churned MRR | Net New MRR |
|-------|---------|---------------|-----------------|-------------|-------------|
| Jan-26 | $8,000 | $2,500 | $1,000 | $1,500 | $8,000 |
| Feb-26 | $6,500 | $3,000 | $800 | $2,000 | $6,700 |

The Net New MRR formula for each row:

```excel
=B2+C2-D2-E2
```

And ending MRR for each month:

```excel
=Prior Month Ending MRR + Net New MRR
```

This decomposition is what makes the dashboard useful. A flat MRR number hides whether you are growing fast with high churn or growing slowly with excellent retention.

### 4. Gross Revenue Churn Rate

**Definition:** The percentage of MRR lost to downgrades and cancellations in a given period, relative to starting MRR.

```excel
=(Contraction MRR + Churned MRR) / Beginning MRR
```

In a monthly dashboard:

```excel
=(D2+E2)/G1
```

Where G1 is the prior month's ending MRR.

**Benchmark:** Best-in-class SaaS companies target gross revenue churn under 1% per month (under 12% annualized). Enterprise-heavy businesses often achieve under 0.5%.

### 5. Net Revenue Retention (NRR)

NRR is the single most important metric for a SaaS business. It answers: for every dollar of MRR I had twelve months ago, how much do I have now — from the same customers?

```excel
=(Beginning MRR + Expansion MRR - Contraction MRR - Churned MRR) / Beginning MRR
```

For a monthly calculation:

```excel
=(G1+C2-D2-E2)/G1
```

To annualize monthly NRR:

```excel
=Monthly NRR^12
```

**Benchmark:** An NRR above 100% means your existing customers are growing faster than they are churning. Top SaaS companies report 110-130%. Below 90% is a serious problem.

### 6. CAC (Customer Acquisition Cost)

```excel
=(Total Sales & Marketing Spend) / (New Customers Acquired)
```

In Excel:

```excel
=SUM(SalesMarketing[Spend]) / COUNTIFS(CustomerTable[Start Date],">="&StartDate, CustomerTable[Start Date],"<="&EndDate)
```

**Important:** Include fully loaded costs — salaries, commissions, ad spend, tools, events. If your sales team earns commissions that you capitalize under ASC 340-40, include the gross commission amount in CAC (not the amortized expense). The capitalization treatment affects your P&L, but CAC should reflect cash economics.

For commission capitalization schedules that handle this correctly, see the [ASC 606 Commission Workbook](/templates/asc606/).

### 7. LTV (Customer Lifetime Value)

```excel
=ARPA / Monthly Gross Revenue Churn Rate
```

Where ARPA is Average Revenue Per Account (monthly):

```excel
=Total MRR / COUNT(Active Customers)
```

A more precise version adjusts for gross margin:

```excel
=(ARPA * Gross Margin %) / Monthly Gross Revenue Churn Rate
```

In Excel, if ARPA is in cell B20, gross margin in B21, and monthly churn in B22:

```excel
=(B20*B21)/B22
```

With a $500 ARPA, 80% gross margin, and 2% monthly churn, LTV = ($500 * 0.80) / 0.02 = **$20,000**.

### 8. LTV:CAC Ratio

```excel
=LTV / CAC
```

**Interpretation:**

| LTV:CAC | What It Means |
|---------|---------------|
| < 1.0x | Losing money on every customer. Stop spending. |
| 1.0 - 3.0x | Unprofitable or marginal. Improve retention or reduce CAC. |
| 3.0 - 5.0x | Healthy. This is the target range for most SaaS businesses. |
| > 5.0x | Either very efficient or underinvesting in growth. |

A related metric is **CAC Payback Period** — how many months it takes to recover the acquisition cost:

```excel
=CAC / (ARPA * Gross Margin %)
```

At $10,000 CAC, $500 ARPA, and 80% margin: payback = 25 months. That is on the edge — most investors want to see under 18 months.

---

## Building the Dashboard Structure in Excel

A clean SaaS metrics dashboard in Excel needs three layers:

### Input Layer (Monthly Data Tab)

One row per month. This is where actuals get entered or pasted from your billing system.

| Column | Field | Source |
|--------|-------|--------|
| A | Month | Date series |
| B | Beginning Customers | Prior month ending |
| C | New Customers | Billing system |
| D | Churned Customers | Billing system |
| E | Ending Customers | =B+C-D |
| F | Beginning MRR | Prior month ending |
| G | New MRR | Billing system |
| H | Expansion MRR | Billing system |
| I | Contraction MRR | Billing system |
| J | Churned MRR | Billing system |
| K | Ending MRR | =F+G+H-I-J |
| L | S&M Spend | GL / P&L |

### Calculation Layer (Metrics Tab)

Each metric as a formula referencing the input layer. No hardcoded numbers.

```excel
' ARR
=K2*12

' Gross Churn Rate (monthly)
=(I2+J2)/F2

' NRR (monthly)
=(F2+H2-I2-J2)/F2

' NRR (annualized)
=((F2+H2-I2-J2)/F2)^12

' CAC
=L2/C2

' ARPA
=K2/E2

' LTV (gross margin adjusted)
=(K2/E2*GrossMargin)/((I2+J2)/F2)

' LTV:CAC
=LTV/CAC
```

### Summary Layer (Dashboard Tab)

Current month KPIs at the top. Twelve-month trend table below. This is what goes into the board deck.

---

## Worked Example: 12 Months at a $500K ARR Company

Here is a realistic twelve-month dataset for a SaaS company starting at roughly $42K MRR ($500K ARR):

| Month | Beg MRR | New | Expansion | Contraction | Churned | End MRR | ARR |
|-------|---------|-----|-----------|-------------|---------|---------|-----|
| Jan | $41,000 | $5,000 | $1,500 | $500 | $1,200 | $45,800 | $549,600 |
| Feb | $45,800 | $4,200 | $2,000 | $600 | $1,000 | $50,400 | $604,800 |
| Mar | $50,400 | $6,000 | $1,800 | $400 | $1,500 | $56,300 | $675,600 |
| Apr | $56,300 | $5,500 | $2,200 | $700 | $1,300 | $62,000 | $744,000 |
| May | $62,000 | $4,800 | $2,500 | $500 | $1,800 | $67,000 | $804,000 |
| Jun | $67,000 | $7,000 | $3,000 | $600 | $2,000 | $74,400 | $892,800 |
| Jul | $74,400 | $5,200 | $2,800 | $800 | $1,500 | $80,100 | $961,200 |
| Aug | $80,100 | $6,500 | $3,200 | $700 | $2,200 | $86,900 | $1,042,800 |
| Sep | $86,900 | $5,800 | $2,600 | $500 | $1,800 | $93,000 | $1,116,000 |
| Oct | $93,000 | $7,200 | $3,500 | $600 | $2,500 | $100,600 | $1,207,200 |
| Nov | $100,600 | $6,000 | $3,000 | $800 | $2,000 | $106,800 | $1,281,600 |
| Dec | $106,800 | $8,000 | $3,800 | $700 | $2,500 | $115,400 | $1,384,800 |

**Summary metrics for December:**

- **MRR:** $115,400
- **ARR:** $1,384,800
- **Net New MRR:** $8,600
- **Gross Churn Rate:** (700 + 2,500) / 106,800 = **3.0%** monthly
- **NRR (monthly):** (106,800 + 3,800 - 700 - 2,500) / 106,800 = **100.6%**
- **NRR (annualized):** 100.6%^12 = **107.4%**

This company more than doubled ARR in twelve months. The monthly gross churn of 3.0% in December is elevated — annualized, that is roughly 31%, which means nearly a third of revenue needs to be replaced each year just to stay flat. The saving grace is strong expansion revenue keeping NRR above 100%.

---

## Common Mistakes That Break SaaS Dashboards

**Mixing bookings with revenue.** A signed $120K annual contract is a booking. MRR is $10K starting when the subscription activates and revenue recognition begins. If your dashboard pulls from CRM closed-won dates instead of subscription start dates, your MRR will be wrong.

**Ignoring contraction.** Many dashboards only track new MRR and churned MRR, lumping downgrades into churn. This overstates your churn rate and makes expansion look smaller than it is. Track all four components separately.

**Annualizing one good month.** If you closed a large deal in March, your March MRR spike does not mean your ARR permanently jumped. ARR is a point-in-time snapshot, but presenting it without context is misleading. Always show ARR alongside the trailing three-month trend in Net New MRR.

**Excluding professional services customers from churn.** If a customer bought your software plus implementation services and later drops the software, that is churn — even if they are still paying for services. Only recurring revenue counts.

**Not reconciling to GAAP revenue.** Your MRR dashboard and your income statement should be reconcilable. The difference should be explainable: one-time fees, usage overages, timing differences between billing and revenue recognition. If you cannot reconcile them, one of them is wrong.

---

## Why This Gets Hard at Scale

A single-tab Excel dashboard works well up to about fifty customers and one product line. Beyond that, you run into real structural challenges:

**Cohort tracking.** To calculate true NRR, you need to track each monthly cohort of customers and their MRR over time. This requires a matrix (cohorts as rows, months as columns) that grows every month.

**Multiple products and pricing tiers.** When customers can subscribe to different products with different billing cycles, normalizing everything to a single MRR figure requires careful logic. A customer who upgrades from Product A to Product B might look like churn on one product and new MRR on another.

**Mid-month changes.** A customer who upgrades on the 15th contributes half a month of the old rate and half of the new rate. Pro-rating in Excel is doable but tedious to maintain manually.

**Multi-entity and multi-currency.** If you operate internationally, you need to decide whether MRR is calculated in local currency or translated to a reporting currency — and at what exchange rate.

These are the exact problems that turn a simple spreadsheet into a maintenance burden. For companies approaching this complexity, having a structured workbook with pre-built cohort tracking, automated decomposition formulas, and reconciliation checks saves dozens of hours per month.

We are building a **SaaS Metrics & ARR Dashboard** workbook that handles all of this — cohort-level tracking, multi-product support, automated NRR calculations, and a board-ready summary tab. If you want early access, email hello@kdeskaccounting.com.

---

## Related Resources

If you are building out your finance tech stack in Excel, these may be useful:

- **[How to Calculate Startup Runway](/posts/how-to-calculate-startup-runway/)** — a detailed walkthrough of runway modeling, burn rate calculations, and scenario planning. Pairs well with the metrics dashboard for board presentations.
- **[Month-End Close Checklist for Controllers](/posts/month-end-close-checklist-controllers/)** — the process that feeds your dashboard with clean monthly data.
- **[ASC 606 Commission Workbook](/templates/asc606/)** ($79) — automates commission capitalization under ASC 340-40, which directly affects your CAC calculations.
- **[ASC 842 Lease Accounting Workbook](/templates/asc842/)** ($97) — if your SaaS company has office leases, this handles the ROU asset and liability schedules that show up on your balance sheet.
- **[Startup Runway Calculator](/templates/runway/)** ($49) — turns your MRR growth assumptions and burn rate into a month-by-month cash forecast.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
