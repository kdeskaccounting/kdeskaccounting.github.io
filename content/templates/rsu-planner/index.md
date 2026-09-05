---
title: "RSU Tax Planner — Excel Workbook for Vest-by-Vest Withholding Gaps"
description: "Excel workbook that lays out every RSU grant and vest for 2026–2030: what payroll withholds at 22%, what the same dollars are taxed at your marginal rate, the gap, the federal safe-harbor test, and equal quarterly installments. Built on IRS Rev. Proc. 2025-32 and Publication 15 (2026). No macros, no subscription."
summary: "Every grant, every vest, five years — the April shortfall before April, the safe-harbor amount, and what it would take per quarter or per paycheck to reach it. Tax mechanics on compensation, not advice."
draft: true
date: 2026-09-05
lastmod: 2026-09-05
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 6
price: 149
buy_url: "https://kdeskaccounting.gumroad.com/l/dqqhk"
free_url: "/rsu-tax-calculator/"
free_label: "Use the free calculator first"
video_url: "https://github.com/kdeskaccounting/kdeskaccounting.github.io/releases/download/media-2026-09/rsu-planner.mp4"
video_poster: "/images/products/rsu-planner-poster.png"
video_caption: "Watch the 4-minute walkthrough — every tab, the sample grants, no login."
tags: ["RSU", "equity compensation", "tax planning", "withholding", "estimated taxes", "Excel template", "personal finance"]
compare:
  free_name: "Free web calculator"
  full_name: "RSU Tax Planner workbook"
  rows:
    - ["Tax year", "2026, one lump sum", "2026–2030, every vest"]
    - ["Grants and vests", "one total", "20 grants · up to 240 vests"]
    - ["Federal gap: 22% withheld vs. marginal rate", "yes", "yes, per year and per vest"]
    - ["37% rate over $1M supplemental wages", "yes", "yes, tracked cumulatively by year"]
    - ["Safe-harbor test (90% / prior-year 100–110%)", "this year", "every year"]
    - ["Equal quarterly installments with due dates", "no", "yes"]
    - ["Per-paycheck W-4 Step 4(c) equivalent", "no", "yes"]
    - ["Social Security, Medicare and Additional Medicare by payroll rule", "Additional Medicare only", "yes, per vest"]
    - ["Shares sold to cover and net shares delivered", "no", "yes"]
    - ["Dashboard, chart, printable summary", "no", "yes"]
    - ["Saves your data", "no — runs in your browser", "yes — it's your file"]
faq:
  - q: "How is this different from the free calculator?"
    a: "The free calculator answers this year, for one lump sum of RSU income. The workbook lays out every grant and every vest across 2026–2030, tracks the $1 million supplemental-wage line cumulatively, shows Social Security and Medicare per vest, turns the safe-harbor amount into equal quarterly installments with due dates, and gives a per-paycheck W-4 Step 4(c) equivalent. It is also a file you keep and update."
  - q: "Which filing statuses does it support?"
    a: "Single and married filing jointly, with tax-year-2026 brackets and standard deductions from IRS Rev. Proc. 2025-32. Head of household and married filing separately are not included in v1 because their brackets and thresholds differ."
  - q: "What happens for 2027 and later years?"
    a: "The IRS publishes each year's brackets the previous autumn. Until then the workbook applies the 2026 tables to later years and says so. The tables live on one sheet you can update when the new figures are released."
  - q: "Does it tell me whether to sell shares or how much to pay?"
    a: "No. It computes withholding arithmetic on compensation: what payroll withholds, what the same income is taxed at your marginal rate, the gap, and the amounts that would reach the federal safe harbor. Whether to sell, hold or cover shares, and how to handle estimated payments or withholding elections, are decisions to make with a qualified tax professional."
  - q: "Does it work on a Mac or in Google Sheets?"
    a: "Excel 2016+, Microsoft 365 and Excel for Mac, and it recalculates correctly in LibreOffice — that is how the release build is tested. Google Sheets is not tested."
  - q: "Is this tax advice?"
    a: "No. It is an educational estimate built from published federal parameters. It does not consider your full situation — other income, credits, AMT, ESPP or options — and it may be wrong for yours."
---

## What the workbook does

Restricted stock units are taxed as ordinary income when they vest, and most employers withhold a flat **22%** on that income. Stacked on top of a salary the same dollars are usually taxed at 24%, 32%, 35% or 37%, so a balance builds toward April. The [free calculator](/rsu-tax-calculator/) shows the size of that gap for one year. This workbook shows it **for every grant, every vest and every year through 2030** — and what it would take, per quarter or per paycheck, to reach the federal safe harbor.

## Eight sheets

- **Setup** — filing status, salary and growth, pre-tax deductions, planning date, state rates, prior-year tax for the safe-harbor alternative, default share price, selected year.
- **Grants** — up to 20 grants: shares, first vest, frequency, number of vests, optional price override.
- **Vest Schedule** — every vest: date, shares, income, federal withholding at 22% (37% over the $1 million supplemental line, tracked cumulatively), state, Social Security to the wage base, Medicare and Additional Medicare by payroll rule, shares sold to cover, net shares delivered, and each vest's share of the year's gap.
- **Tax Year Summary** (2026–2030) — taxable income, federal tax by bracket, tax on the RSU slice and its effective rate, what payroll withholds, the federal and state gap, the 90% and prior-year safe-harbor tests, additional payments that would reach them, and a per-paycheck W-4 Step 4(c) equivalent.
- **Quarterly Plan** — the selected year's safe-harbor amount as four equal installments against cumulative withholding, with the April 15 / June 15 / September 15 / January 15 due dates.
- **Dashboard** — the year's shortfall, effective rate, withheld vs. owed chart by year, next vest, and employer-stock concentration shown as a fact.
- **Instructions** and a hidden **_Lists** sheet holding every rate and bracket, with its source.

## Built on verified parameters

Federal brackets and standard deductions are tax-year-2026 values from IRS Rev. Proc. 2025-32; the 22% and 37% supplemental rates, the $184,500 Social Security wage base and the Medicare rates are from Publication 15 (2026). The release build is recalculated in LibreOffice and checked against the same worked examples the free calculator publishes — $180,000 of salary plus $120,000 of vests produces $36,200.25 of tax on the RSU slice, $26,400 withheld, and a $9,800.25 gap.

## What it does not do

Other income, credits, the Alternative Minimum Tax, ESPP or stock options, head-of-household or married-filing-separately brackets, and the annualized-income installment method. It does not tell you whether to sell, hold or cover shares. *Educational estimate, not tax, legal or investment advice — work with a qualified tax professional for decisions.*
