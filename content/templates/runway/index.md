---
title: "Startup Runway Calculator — Excel Template"
description: "A 12 to 48-month startup runway calculator in Excel. Scenario modeling (Base, Optimistic, Pessimistic), KPI dashboard, and five input tabs for financing, revenue, and expenses. No macros, one-time purchase."
summary: "The Startup Runway Calculator tells you how many months of cash you have — under your base case, an optimistic scenario, and a pessimistic one. Five input tabs, KPI dashboard, and up to 48 months of projections in a single Excel file."
lastmod: 2026-11-24
date: 2026-03-18
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 3
price: 49
buy_url: "https://kdeskaccounting.gumroad.com/l/runway-calculator"
free_url: "https://kdeskaccounting.gumroad.com/l/runway-calculator-free"
free_label: "Try free 12-month version"
video_url: "https://github.com/kdeskaccounting/kdeskaccounting.github.io/releases/download/media-2026-09/runway.mp4"
video_poster: "/images/products/runway-poster.png"
youtube_url: "https://youtu.be/G0CbfPkmgTY"
tags: ["startup", "runway", "burn rate", "cash flow", "Excel template", "financial model", "founder"]
compare:
  free_name: "Free 12-month version"
  full_name: "Full workbook"
  rows:
    - ["Forecast window", "12 months", "12, 24, 36 or 48 months"]
    - ["Input rows per tab", "5", "20"]
    - ["Scenarios", "Base only", "Base, Optimistic, Pessimistic"]
    - ["Runway, cash-zero date and breakeven dashboard", "yes", "yes"]
    - ["Peak cash and total capital required", "yes", "yes"]
    - ["4-minute walkthrough video", "yes", "yes"]
faq:
  - q: "Does it handle variable payment schedules?"
    a: "Yes. Each expense, financing and CapEx line has a frequency dropdown (Monthly, Quarterly, Annual, One-Time) and an Occurrences field; leave Occurrences blank to run to the end of the forecast. Revenue lines have a frequency and an optional End Month. A quarterly expense only hits cash flow every 3 months; a one-time payment hits once and stops."
  - q: "Can I model a future fundraise?"
    a: "Yes. Add a row to the Financing tab with the expected raise amount and the month you expect to receive it. The dashboard immediately shows your extended runway. Owner Draw and Loan Repayment rows subtract cash; every other financing type adds it."
  - q: "Does it work on a Mac?"
    a: "Yes. Pure Excel formulas — no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac."
  - q: "What is the difference between gross burn and net burn?"
    a: "Gross burn is what you spend: fixed plus variable costs, shown side by side on the Forecast Summary. The Burn Rate column on the Forecast Summary and the Dashboard is revenue minus those costs, so it shows how much the business loses (or makes) each month before financing and CapEx."
  - q: "Can I add more than 20 input rows?"
    a: "Email hello@kdeskaccounting.com for a custom build."
---

If you're raising a round, preparing a board update, or just trying to answer "how long do we have?" — this workbook gives you a defensible answer in minutes. **$49, one-time purchase. No subscription. No macros.**

[Get the Workbook ($49) →](https://kdeskaccounting.gumroad.com/l/runway-calculator)

---

## What's in the Workbook

Ten tabs, each with a specific job. You enter data on Setup, the five input tabs and Scenario Assumptions; the Dashboard and Forecast Summary calculate automatically.

### Instructions

Quick-start guide, field reference, and the definitions behind every card. Start here to understand how the model is structured before entering data.

### Dashboard

Pick the scenario here — Base, Optimistic, or Pessimistic — and six KPI cards recalculate, all within the selected forecast window:

- **Months of Runway** — how many months until cash goes below zero (or "No cash-out" if it never does in the window)
- **Cash Zero Date** — the calendar month when cash runs out
- **Month 1 Burn Rate** — revenue minus fixed and variable costs in the first month (shown negative while you're burning; excludes financing and CapEx)
- **Peak Cash Balance** — the highest cash balance reached in the forecast window
- **Breakeven** — the first month operating cash flow (revenue minus fixed and variable costs) turns positive *and stays positive* through the end of the forecast window, so a one-off spike doesn't count
- **Total Capital Required** — how far below zero your cash balance goes in the window: the extra cash you'd need to get through it ($0 if you never run out)

Below the cards is a chart-ready table of date, revenue, burn, net cash and end cash balance. The cards show your currency symbol from Setup (amounts are not converted), and a banner says whether your inputs passed the Input Check.

### Setup

Company name, forecast start month, forecast window (12, 24, 36 or 48 months) and currency symbol. Starting cash is entered as a one-time inflow on the Financing tab. Setup also holds the **Input Check**: it counts text typed into number cells (the Dashboard cards show "Check inputs" until it's fixed) and rows that are left out because they have no name or frequency, or a Start Month after the forecast window.

### Financing Inputs

Up to 20 financing events — starting cash, equity rounds, loan draws, grants. Each row: label, type, amount, start month, frequency and occurrences. Inflow, Debt/Loan, Equity Round, Grant and Other add cash; **Owner Draw and Loan Repayment subtract it** (enter every amount as a positive number).

### Revenue Inputs

Up to 20 revenue streams. Each row: start month, optional end month, initial amount, frequency, two-rate growth (an initial annual rate for a ramp period, then a mature annual rate, compounded monthly), and an optional monthly cap.

### Fixed Expenses

Up to 20 fixed cost lines — payroll, rent, insurance, SaaS subscriptions. Start month, amount, frequency and occurrences. These don't vary with revenue.

### Variable Expenses

Up to 20 variable cost lines — hosting, COGS, commissions, customer success costs — with the same two-rate growth as revenue and an optional end month.

### CapEx

Up to 20 capital expenditure items — equipment purchases, leasehold improvements, large one-time investments. These show as discrete cash outflows in the forecast.

### Scenario Assumptions

Three scenarios, each four editable multipliers: revenue, variable costs, fixed costs and CapEx. The sample's Optimistic case is revenue 25% higher (variable costs 5% higher); Pessimistic is revenue 35% lower (variable costs 5% lower). A blank multiplier counts as 1.0.

### Forecast Summary

Month-by-month revenue, fixed costs, variable costs, financing, CapEx, burn, net cash and end cash balance for the selected scenario, up to 48 months. There is no separate opening-cash column: your starting balance is the month-1 financing line.

---

## A Worked Example: 17 Months of Runway

A seed-stage SaaS startup has $600,000 in the bank and a team of three. The forecast starts January 2027 and runs 36 months. This is the sample data that comes in the workbook, so you can check every number yourself.

**Inputs**
- Seed round: $600,000 (one-time, month 1)
- Fixed costs: $46,000/month (payroll $40,000, rent $3,500, software $1,500, bookkeeping and legal $1,000)
- Laptops and equipment: $6,000 (one-time, month 1)
- Subscription revenue: starts in month 3 at $7,000/month and grows 250% a year for the first 12 months, then 100% a year
- Hosting and cost of revenue: starts at $1,000/month and grows with revenue

**Dashboard (Base)**
- Months of Runway: **17**
- Cash Zero Date: **June 2028**
- Month 1 Burn Rate: **($46,000)**
- Breakeven (operating cash flow positive from here on): **May 2029**
- Total Capital Required: **$118,029**, the extra cash needed to get through to breakeven

Switch the Dashboard dropdown to **Pessimistic** (revenue 35% lower):
- Months of Runway: **14**, cash runs out **March 2028**
- Total Capital Required: **$436,996** within the 36-month forecast (cash is still falling at the end of it)

Switch to **Optimistic** (revenue 25% higher):
- **No cash-out**: breakeven moves up to **January 2029** and the $600,000 is enough

All three scenarios recalculate the moment you change the dropdown on the Dashboard.

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
|---------------|---------|
| Forecast window | 12, 24, 36, or 48 months (dropdown) |
| Input rows per tab | 20 (free version: 5) |
| Scenarios | Base, Optimistic, Pessimistic (free version: Base) |
| Excel version | 2016, 365, Mac (no macros) |
| File format | .xlsx |
| Formula protection | Locked formula cells, unlocked input cells, number validation on numeric inputs |
| Price | $49 one-time |

---

## Get the Workbook

[**Get the Workbook ($49) →**](https://kdeskaccounting.gumroad.com/l/runway-calculator)

Not ready to buy? Try the free 12-month version — the same tabs, limited to 5 input rows per tab, a 12-month window and the Base scenario. Its sample starts with $400,000: the dashboard shows cash running out in November 2027 (10 months of runway) and $57,648 of additional capital required within the 12-month window.

[Try the free version →](https://kdeskaccounting.gumroad.com/l/runway-calculator-free)

---

## Frequently Asked Questions

**Does it handle variable payment schedules?**
Yes. Each expense, financing and CapEx line has a frequency dropdown (Monthly, Quarterly, Annual, One-Time) and an Occurrences field; leave Occurrences blank to run to the end of the forecast. Revenue lines have a frequency and an optional End Month. A quarterly expense only hits cash flow every 3 months; a one-time payment hits once and stops.

**Can I model a future fundraise?**
Yes. Add a row to the Financing tab with the expected raise amount and the month you expect to receive it. The dashboard immediately shows your extended runway. Owner Draw and Loan Repayment rows subtract cash; every other financing type adds it.

**Does it work on a Mac?**
Yes. Pure Excel formulas — no VBA macros, no Windows-only features. Works on Excel 2016, Excel 365, and Excel for Mac.

**What's the difference between gross burn and net burn?**
Gross burn is what you spend: fixed plus variable costs, shown side by side on the Forecast Summary. The Burn Rate column on the Forecast Summary and the Dashboard is revenue minus those costs, so it shows how much the business loses (or makes) each month before financing and CapEx.

**Can I add more than 20 input rows?**
Email [hello@kdeskaccounting.com](mailto:hello@kdeskaccounting.com) for a custom build.
