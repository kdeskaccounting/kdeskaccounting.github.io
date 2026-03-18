---
title: "Startup Runway Calculator — Excel Template"
description: "A 12 to 48-month startup runway calculator in Excel. Scenario modeling (Base, Optimistic, Pessimistic), KPI dashboard, and five input tabs for financing, revenue, and expenses. No macros, one-time purchase."
summary: "The Startup Runway Calculator tells you exactly how many months of cash you have — under your base case, an optimistic scenario, and a pessimistic one. Five input tabs, KPI dashboard, and up to 48 months of projections in a single Excel file."
date: 2026-03-18
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 3
tags: ["startup", "runway", "burn rate", "cash flow", "Excel template", "financial model", "founder"]
---

If you're raising a round, preparing a board update, or just trying to answer "how long do we have?" — this workbook gives you a defensible answer in minutes. **$49, one-time purchase. No subscription. No macros.**

[Get the Workbook ($49) →](https://kdeskaccounting.gumroad.com)

---

## What's in the Workbook

Eight tabs, each with a specific job. You enter data across five input tabs; every output tab calculates automatically.

### Instructions

Field reference, quick-start guide, and key formula explanations. Start here to understand how the model is structured before entering data.

### Setup

Company name, starting cash balance, forecast start date, and forecast window (12, 24, 36, or 48 months). Select your scenario from the dropdown — Base, Optimistic, or Pessimistic — and the entire workbook shifts. Every input tab has separate Base/Optimistic/Pessimistic columns for each line item.

### Dashboard

Six KPI cards calculated automatically from your inputs:

- **Months of Runway** — how many months until cash reaches zero
- **Cash Zero Date** — the calendar month when cash runs out (or "No cash-out" if projections stay positive)
- **Monthly Burn Rate** — average net cash outflow per month in the selected scenario
- **Peak Cash** — the highest cash balance reached in the forecast window
- **Breakeven Month** — the first month net cash flow is positive
- **Total Capital Required** — cumulative shortfall from current cash to survive the forecast window

### Financing Tab

Up to 20 financing events — equity raises, debt draws, grants, or other cash inflows. Each row: name, amount, month of receipt, and frequency. Useful for modeling future fundraising rounds or debt facilities.

### Revenue Tab

Up to 20 revenue streams. Each row: starting amount, annual growth rate, growth cap (optional monthly ceiling), frequency (monthly, quarterly, annual, one-time), and number of occurrences.

### Fixed Expenses

Up to 20 fixed cost lines — payroll, rent, insurance, SaaS subscriptions. Amount, frequency, and occurrences. These don't vary with revenue.

### Variable Expenses

Up to 20 variable cost lines — hosting, COGS, commissions, customer success costs that scale with revenue.

### CapEx

Up to 20 capital expenditure items — equipment purchases, leasehold improvements, large one-time investments. These show as discrete cash outflows in the forecast.

### Cash Flow Projection

Month-by-month waterfall: opening cash + financing inflows + revenue − fixed costs − variable costs − CapEx = closing cash. Select this table in Excel to insert a native chart showing cash balance over time.

---

## A Worked Example — 18-Month Runway

A Series A startup with $2.5M in the bank, $180k/month in fixed costs, $80k/month in current revenue growing at 40% annually.

**Base case inputs:**
- Starting cash: $2,500,000
- Monthly revenue (Month 1): $80,000 | Annual growth rate: 40%
- Fixed costs: $180,000/month
- Variable costs: $12,000/month

**Dashboard output (Base):**
- Months of Runway: **18**
- Cash Zero Date: **September 2027**
- Monthly Burn Rate: **$97,000** (net)
- Breakeven Month: **Month 22**

Switch the dropdown to Pessimistic (20% annual growth):
- Months of Runway: **14**
- Cash Zero Date: **May 2027**

Switch to Optimistic (65% annual growth):
- Months of Runway: **24+** (cash-flow positive before end of window)

All three scenarios calculate instantly from a single dropdown change in Setup.

---

## Who This Is For

- Founders preparing for a fundraise who need to show runway to investors
- Controllers and finance managers building the operating forecast
- CFOs managing cash through a lean period and modeling scenarios
- Any operator who needs to answer "how long is our runway?" without hiring a CFO

---

## What It Is Not

This workbook models cash in and cash out — it is not a three-statement financial model. It doesn't calculate GAAP revenue recognition, deferred revenue, or accrual-basis P&L. It answers one question well: how long does our cash last?

---

## Technical Specifications

| Specification | Detail |
|---------------|--------|
| Forecast window | 12, 24, 36, or 48 months (dropdown) |
| Input rows per tab | 20 (paid version) |
| Scenarios | Base, Optimistic, Pessimistic |
| Excel version | 2016, 365, Mac (no macros) |
| File format | .xlsx |
| Formula protection | Locked formula cells, unlocked input cells |
| Price | $49 one-time |

---

## Get the Workbook

[**Get the Workbook ($49) →**](https://kdeskaccounting.gumroad.com)

Not ready to buy? Try the free 12-month version — same structure, limited to 5 input rows per tab and a 12-month window. See how the dashboard and scenario logic work before committing.

[Try the free version →](https://kdeskaccounting.gumroad.com)

> **Note:** Direct purchase links will be updated once the Gumroad listings are live. In the meantime, browse [kdeskaccounting.gumroad.com](https://kdeskaccounting.gumroad.com) to check availability.

---

## Frequently Asked Questions

**Does it handle variable payment schedules?**
Yes. Each revenue and expense line has a frequency dropdown (Monthly, Quarterly, Annual, One-Time) and an occurrences field. A quarterly expense only hits cash flow every 3 months; a one-time payment hits once and stops.

**Can I model a future fundraise?**
Yes. Add a row to the Financing tab with the expected raise amount and the month you expect to receive it. The dashboard will immediately show your extended runway.

**Does it work on a Mac?**
Yes. Pure Excel formulas — no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac.

**What's the difference between gross burn and net burn?**
The workbook shows net burn rate — total cash outflows minus total cash inflows per month. Gross burn is outflows only (before revenue). Both are visible in the cash flow projection table.

**Can I add more than 20 input rows?**
Email [hello@kdeskaccounting.com](mailto:hello@kdeskaccounting.com) for a custom build.
