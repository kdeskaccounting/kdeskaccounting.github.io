---
title: "How to Calculate Startup Runway (With Excel Template)"
date: 2026-03-18
description: "How to calculate startup runway — the formula, what counts as burn, how to build a month-by-month cash model in Excel, and what to do when the number is lower than you expected."
summary: "Runway is simple to define and surprisingly easy to miscalculate. Here's the formula, how to avoid the common errors, and how to build a scenario model that gives you a defensible number for investors and the board."
tags: ["startup", "runway", "burn rate", "cash flow", "Excel template", "financial model", "SaaS finance"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 8
---

Every founder and finance lead at a startup needs one number: how many months until cash runs out? Getting that number wrong — or not having a model that updates it reliably — is one of the most common and preventable finance failures in early-stage companies.

This guide covers how to calculate runway correctly, how to build the Excel model, and how to think about scenarios when the number is tighter than you'd like.

---

## The Basic Runway Formula

```
Runway (months) = Current Cash Balance ÷ Net Monthly Burn Rate
```

**Net burn rate** = total monthly cash outflows − total monthly cash inflows

If you have $1.8M in the bank and you're spending $100k/month while bringing in $40k/month in revenue:

- Net burn = $100k − $40k = $60k/month
- Runway = $1,800,000 ÷ $60,000 = **30 months**

This is the static calculation. It's useful for a quick gut check, but it assumes your burn rate never changes — and it never doesn't change.

---

## Gross Burn vs. Net Burn

**Gross burn rate** — total cash going out the door each month (payroll, rent, software, services). Doesn't net against revenue.

**Net burn rate** — gross burn minus cash inflows (revenue, interest, other). This is the number that determines when you run out of money.

Early-stage investors typically ask about both. Gross burn shows cost structure; net burn shows the actual cash consumption rate.

> *A startup with $200k gross burn and $120k in revenue has $80k net burn. That's a very different position from a company with $200k gross burn and $20k revenue — even though the gross burn is identical.*

---

## Why Static Runway Calculations Lie

The simple formula breaks down because burn rates change:

1. **Revenue grows** (or doesn't) — your net burn narrows or widens over time
2. **Headcount changes** — a new hire adds $15k–$30k/month in fully-loaded cost overnight
3. **Seasonality** — quarterly software renewals, annual insurance, marketing campaigns
4. **Capital events** — a new equity round or debt draw changes your cash balance on a specific date
5. **Variable costs** — customer success, hosting, and COGS scale with revenue

A static calculation gives you one number. A month-by-month model gives you a curve — and the curve tells you things the single number doesn't.

---

## Building the Month-by-Month Model in Excel

A proper runway model has five categories:

### 1. Starting Cash
Your current bank balance as of the model start date. Include all accounts you can draw on.

### 2. Financing Inflows
Equity raises, debt draws, grants, tax credits. Enter these as one-time inflows in the month you expect to receive them. For a planned raise, model it in the month you expect close — not when you start talking to investors.

### 3. Revenue
Break this out by stream if you have multiple. For each line: starting amount, annual growth rate, and frequency. A simple ARR model: enter current MRR and a 40% annual growth rate, and the model calculates each month's revenue automatically.

### 4. Fixed Costs
Payroll (your largest cost), rent, SaaS subscriptions, professional fees. Enter each as a monthly, quarterly, or annual item.

### 5. Variable Costs
COGS, hosting/infrastructure costs that scale with usage, sales commissions, customer success headcount. These should be tied to revenue assumptions, not entered as fixed numbers.

### The Cash Flow Waterfall

Each month's calculation:

```
Opening Cash
+ Financing Inflows
+ Revenue
− Fixed Costs
− Variable Costs
− CapEx
= Closing Cash
```

The closing cash in Month N becomes the opening cash in Month N+1. When closing cash first hits zero, that's your cash-out date.

---

## Scenario Planning: The Most Important Part

A single runway number is fragile. Investors, boards, and good finance people want to know: *what if?*

Build three scenarios:

**Base case** — your honest forecast. Not conservative, not aggressive. What you actually expect given what you know today.

**Pessimistic** — growth is slower, a key customer churns, hiring takes longer. How long do you have if things go moderately worse? This isn't your worst case — it's a realistic downside.

**Optimistic** — a big deal closes, growth accelerates, a raise comes in. When does cash flow positive in this scenario?

The three scenarios should differ primarily in revenue growth assumptions and major deal timing. Costs are usually more predictable.

> *If your pessimistic case shows less than 12 months of runway, you should be fundraising or cutting costs now — not in 6 months when the runway is down to 6 months.*

---

## Interpreting the Output

### Months of Runway
18+ months = comfortable position. 12–18 months = start fundraising. Under 12 months = urgency.

### Cash Zero Date
More useful than "months of runway" for board presentations. "We have 14 months" lands differently than "we run out in May 2027."

### Breakeven Month
The first month net cash flow is positive. Some companies reach this before they need to raise again; others raise first.

### Net Burn Rate
Every $10k reduction in monthly burn adds roughly 2 weeks of runway at typical burn levels. Run the numbers before making headcount or spending decisions.

---

## What to Do When Runway Is Shorter Than Expected

If the model shows under 18 months in your base case:

**Option 1: Fundraise now.** Start conversations before you're at 12 months. Closing a round from 18 months is easier than closing at 8 months.

**Option 2: Reduce burn.** A 20% cost reduction often extends runway by 40–60% because operating leverage kicks in. Run the scenario in the model before making decisions.

**Option 3: Accelerate revenue.** Model what happens if you close the two big deals in your pipeline. If closing them puts you past breakeven, that changes the strategy.

**Option 4: Add non-dilutive capital.** Venture debt, revenue-based financing, grants, tax credits. Enter these in the Financing tab and see how they shift the cash-out date.

Usually the answer is some combination. The model is the tool for testing them without committing.

---

## The Excel Approach

Most founders start with a simple spreadsheet: one row per cost, one column per month. It works until it doesn't — which happens when you have 20+ cost lines, multiple revenue streams with different growth rates, seasonal items, and you want to run three scenarios without copy-pasting the whole model three times.

At that point, you need a structured workbook:

- **Separate input tabs per category** (financing, revenue, fixed costs, variable costs, CapEx)
- **Scenario selector** — one dropdown changes the entire model
- **Dashboard** — KPI cards you can drop into a board deck
- **Cash flow waterfall** — month-by-month detail you can filter and analyze

The [Startup Runway Calculator](/templates/runway/) is exactly this. Enter your numbers once, flip between scenarios with a dropdown, and get a board-ready dashboard automatically.

$49, one time. [Get it here →](/templates/runway/)

Or try the free 12-month version — same structure, limited to 5 input rows per tab.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
