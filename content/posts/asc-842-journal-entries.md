---
title: "ASC 842 Journal Entries: A Complete Guide with Examples"
date: 2026-03-11
description: "Step-by-step ASC 842 journal entries for operating and finance leases — from initial recognition through monthly close. Includes real numbers, debit/credit format, and common mistakes."
summary: "ASC 842 journal entries trip up even experienced controllers. The initial recognition entry, the monthly operating lease expense, and the finance lease split between depreciation and interest all follow specific patterns. Here's every entry you need, with real numbers."
tags: ["ASC 842", "lease accounting", "journal entries", "operating lease", "finance lease", "GAAP"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 2
---

Getting the balance sheet recognition right under ASC 842 is one thing. Generating the correct journal entries every period — and knowing which accounts to hit — is where most finance teams slow down.

This guide covers every entry you'll need: initial recognition, monthly operating lease close, monthly finance lease close, and termination. All with real numbers.

## The Two Lease Types and Why They Matter

Under ASC 842, every lease is classified as either **operating** or **finance**. That classification drives the journal entry pattern for the entire lease term.

| | Operating Lease | Finance Lease |
|--|--|--|
| Balance sheet | ROU asset + lease liability | ROU asset + lease liability |
| P&L — expense | Single straight-line lease expense | Depreciation + interest (front-loaded) |
| Cash flow | Operating activities | Principal = financing; interest = operating |
| Typical examples | Office space, vehicles | Equipment, machinery, property you intend to own |

Both types require the same initial recognition entry. The difference shows up in the monthly entries.

---

## Initial Recognition (Commencement Date)

When a lease commences, you recognize the lease liability and ROU asset simultaneously.

**Lease liability** = present value of future lease payments, discounted at the incremental borrowing rate (IBR).

**ROU asset** = lease liability + initial direct costs (IDC) − lease incentives received

### Example

> 5-year office lease. Monthly payment: $5,000. IBR: 5%. No IDC, no incentives.
>
> Lease liability = PV(5%/12, 60, $5,000) = **$265,391**
> ROU asset = $265,391 + $0 − $0 = **$265,391**

### Entry at commencement

```
DR  Right-of-Use Asset          265,391
    CR  Lease Liability                    265,391
```

If there were prepaid rent or initial direct costs:

```
DR  Right-of-Use Asset          267,391
    CR  Lease Liability                    265,391
    CR  Cash / Prepaid Rent                 2,000
```

> **Note:** The ROU asset and lease liability are almost always equal at commencement unless you have IDC or incentives. If they're materially different, check your inputs.

---

## Monthly Operating Lease Entries

Operating leases use a **single straight-line expense** approach. The total cash payments over the lease term are divided equally across all periods, regardless of whether the actual payment is constant.

For constant monthly payments (the most common case), this means one clean entry per month:

### Monthly entry — operating lease

```
DR  Lease Expense               5,000
    CR  Lease Liability — current          Interest portion
    CR  Right-of-Use Asset                 Plug (expense − interest)
```

In practice, you split the payment between:
- **Reducing the lease liability** by the cash payment minus the interest accrual
- **Amortizing the ROU asset** as the plug to make total expense equal to the straight-line amount

Let's work through Month 1 of our example:

| Item | Month 1 |
|------|---------|
| Beginning liability | $265,391 |
| Interest (5%/12 × $265,391) | $1,106 |
| Cash payment | $5,000 |
| Principal reduction | $3,894 |
| Ending liability | $261,497 |
| Lease expense (straight-line) | $5,000 |
| ROU asset amortization (plug) | $3,894 |

### Month 1 entry

```
DR  Lease Expense               5,000
    CR  Cash                              5,000
```

*Then record the liability and ROU movement:*

```
DR  Lease Liability             3,894
    CR  Right-of-Use Asset                3,894
```

Many companies combine these into one entry:

```
DR  Lease Expense               5,000
DR  Lease Liability             3,894
    CR  Cash                              5,000
    CR  Right-of-Use Asset                3,894
```

The ROU asset balance decreases by the principal portion each month. By the end of the lease, both the liability and the ROU asset reach $0.

---

## Monthly Finance Lease Entries

Finance leases split the income statement into **two separate lines**: depreciation (straight-line over the lease term) and interest expense (front-loaded using the effective interest method).

This means total expense is higher in early periods and lower in later periods — the opposite of an operating lease, which is perfectly flat.

Using a similar example:

> 4-year equipment lease. Monthly payment: $2,500. IBR: 7%.
>
> Lease liability = PV(7%/12, 48, $2,500) = **$106,785**
> ROU asset = $106,785

### Month 1 — interest accrual

```
DR  Interest Expense            623        (106,785 × 7%/12)
    CR  Lease Liability                        623
```

### Month 1 — cash payment

```
DR  Lease Liability             2,500
    CR  Cash                              2,500
```

*(Net liability reduction = $2,500 − $623 = $1,877)*

### Month 1 — depreciation

```
DR  Depreciation Expense        2,225      (106,785 ÷ 48 months)
    CR  Accumulated Depreciation              2,225
```

Total Month 1 expense: **$623 interest + $2,225 depreciation = $2,848**

By Month 48, interest expense will be near $0 (tiny remaining balance) and total expense will be just $2,225 — noticeably lower than early periods. That front-loading is the defining characteristic of finance lease accounting.

---

## Short-Term Lease Entries (Practical Expedient)

If the lease term is 12 months or less at commencement, you can elect the short-term exemption and skip balance sheet recognition entirely.

```
DR  Lease Expense               350
    CR  Cash                              350
```

That's it. No ROU asset, no liability, no amortization schedule. Just a straight operating expense each period.

> **Important:** The election is made by **class of underlying asset**, not lease by lease. If you elect the short-term exemption for office equipment, it applies to all short-term office equipment leases.

---

## Lease Termination Entry

When a lease ends (or is terminated early), you derecognize both the ROU asset and the lease liability.

If the balances aren't equal at termination (early termination penalty, unamortized IDC, etc.), the difference hits the income statement as a gain or loss.

### Clean termination at natural end of lease

```
DR  Lease Liability             0          (fully amortized)
    CR  Right-of-Use Asset                  0          (fully amortized)
```

Both balances are $0 at natural lease end — nothing to book.

### Early termination (example)

> Lease terminated in Month 30 of a 60-month lease.
> Remaining ROU asset: $132,696. Remaining liability: $134,500. Termination penalty: $8,000.

```
DR  Lease Liability             134,500
DR  Loss on Lease Termination   6,196
    CR  Right-of-Use Asset                132,696
    CR  Cash (termination penalty)           8,000
```

---

## Lease Modification Entries

A lease modification (extended term, added space, reduced payments) may require remeasuring the lease liability and adjusting the ROU asset.

For a **modification that grants an additional right of use** (e.g., adding a floor to an office lease), treat it as a separate lease.

For **all other modifications**, remeasure the liability using updated inputs and adjust the ROU asset for the difference:

```
DR  Right-of-Use Asset          [increase]
    CR  Lease Liability                    [increase]
```

or

```
DR  Lease Liability             [decrease]
    CR  Right-of-Use Asset                [decrease]
```

Any difference that can't be absorbed by the ROU asset hits the income statement.

---

## Common Mistakes

**1. Using the rate implicit in the lease instead of the IBR**
Most lessees don't know the implicit rate. Default to the IBR unless you can calculate the implicit rate with confidence. Using the wrong rate shifts every number in the schedule.

**2. Forgetting to remeasure on variable rate leases**
If your lease payments change based on a benchmark rate (e.g., SOFR + spread), you must remeasure the liability when the rate changes.

**3. Treating operating lease ROU amortization as a separate line**
Operating lease ROU amortization is a **plug** — it's not separately disclosed. The only P&L line is "Lease Expense." Finance lease depreciation, however, is disclosed separately.

**4. Wrong cash flow classification for finance leases**
Finance lease principal payments go in **financing activities**. Interest payments go in **operating activities** (unless you use the optional policy to show them in financing). Getting this wrong throws off your cash flow statement.

**5. Not reconciling the liability rollforward to the GL**
At period end, your lease liability balance per the amortization schedule should tie exactly to the GL. If it doesn't, you have a journal entry error somewhere that will compound over time.

---

## The Reconciliation Problem

The journal entries above work cleanly for a single lease. With 5, 10, or 20 leases across different commencement dates, you need a systematic way to:

1. Track beginning and ending balances for each lease
2. Aggregate interest, depreciation, and amortization across the portfolio
3. Generate the correct journal entry amounts for the period
4. Tie everything to the balance sheet

That's exactly what the ASC 842 Lease Accounting Workbook handles — 20 leases, 120-month amortization schedule, period-level journal entry aggregation, and a reconciliation tab that confirms everything ties to $0 every month.

**[$97, one time. No subscription. Get it here →](https://kdeskaccounting.gumroad.com/l/phxigq)**

Or [try the free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc) to see it working before you buy.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](https://kdeskaccounting.gumroad.com)*
