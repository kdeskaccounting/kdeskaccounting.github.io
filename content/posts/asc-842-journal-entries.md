---
title: "ASC 842 Journal Entries: Operating and Finance Lease Examples"
date: 2026-03-11
lastmod: 2026-05-31
description: "ASC 842 journal entries with real numbers — initial recognition, monthly operating lease expense, monthly finance lease (depreciation + interest), and termination. Side-by-side debit/credit examples for both lease types."
summary: "ASC 842 journal entries trip up even experienced controllers. The initial recognition entry, the monthly operating lease expense, and the finance lease split between depreciation and interest all follow specific patterns. Here's an ASC 842 lease accounting example with every entry you need, with real numbers."
tags: ["ASC 842", "lease accounting", "journal entries", "operating lease", "finance lease", "Excel template", "GAAP"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 2
faq:
  - q: "What is the journal entry for a lease under ASC 842?"
    a: "At commencement you debit the right-of-use asset and credit the lease liability for the present value of the payments. Each month, an operating lease books a single straight-line lease expense, while a finance lease books separate interest and depreciation entries."
  - q: "How are operating and finance lease journal entries different?"
    a: "An operating lease records one straight-line lease expense each period. A finance lease splits the cost into interest expense (effective-interest method) and depreciation of the ROU asset, producing a front-loaded total expense."
  - q: "What is the journal entry when a lease terminates early?"
    a: "You derecognize the remaining right-of-use asset and lease liability. Any difference between the two balances, plus any termination penalty paid, is recorded as a gain or loss on lease termination."
  - q: "Do you record interest separately on an operating lease under ASC 842?"
    a: "No. Interest is computed internally to amortize the liability, but it is not presented separately. The income statement shows only a single straight-line lease expense; the ROU amortization is a plug that makes total expense equal the straight-line payment."
---

Getting the balance sheet recognition right under ASC 842 is one thing. Generating the correct journal entries every period — and knowing which accounts to hit — is where most finance teams slow down.

This guide covers every entry you'll need: initial recognition, monthly operating lease close, monthly finance lease close, and termination. All with real numbers.

## The Two Lease Types and Why They Matter

Under ASC 842, every lease is classified as either **operating** or **finance** — see [how to classify a lease using the five tests](/posts/operating-vs-finance-lease/). That classification drives the journal entry pattern for the entire lease term.

| | Operating Lease | Finance Lease |
|--|--|--|
| Balance sheet | ROU asset + lease liability | ROU asset + lease liability |
| P&L — expense | Single straight-line lease expense | Depreciation + interest (front-loaded) |
| Cash flow | Operating activities | Principal = financing; interest = operating |
| Typical examples | Office space, vehicles | Equipment, machinery, property you intend to own |

Both types require the same initial recognition entry. The difference shows up in the monthly entries. (Reporting under IFRS? [IFRS 16 vs ASC 842](/posts/asc-842-vs-ifrs-16/) — IFRS treats every lease like a finance lease, so use the finance-lease entries below and skip the operating section.)

---

## Initial Recognition (Commencement Date)

When a lease commences, you recognize the lease liability and ROU asset simultaneously.

**Lease liability** = present value of future lease payments, discounted at the incremental borrowing rate (IBR).

**ROU asset** = lease liability + initial direct costs (IDC) − lease incentives received. (See [how to calculate the ROU asset](/posts/right-of-use-asset-calculation-asc-842/) for the full breakdown.)

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
DR  Lease Liability             3,894
    CR  Right-of-Use Asset                3,894
    CR  Cash                              5,000
```

The ROU asset balance decreases by the principal portion each month. By the end of the lease, both the liability and the ROU asset reach $0.

---

## Monthly Finance Lease Entries

Finance leases split the income statement into **two separate lines**: depreciation (straight-line over the lease term) and interest expense (front-loaded using the effective interest method).

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

### Month 1 — depreciation

```
DR  Depreciation Expense        2,225      (106,785 ÷ 48 months)
    CR  Accumulated Depreciation              2,225
```

Total Month 1 expense: **$623 interest + $2,225 depreciation = $2,848**

By Month 48, interest expense will be near $0 and total expense will be just $2,225 — noticeably lower than early periods.

---

## Short-Term Lease Entries (Practical Expedient)

If the lease term is 12 months or less at commencement, you can elect the short-term exemption and skip balance sheet recognition entirely.

```
DR  Lease Expense               350
    CR  Cash                              350
```

No ROU asset, no liability, no amortization schedule. Just a straight operating expense each period.

---

## Lease Termination Entry

When a lease ends (or is terminated early), you derecognize both the ROU asset and the lease liability. If the balances aren't equal at termination, the difference hits the income statement as a gain or loss.

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

## Common Mistakes

**1. Using the rate implicit in the lease instead of the IBR**
Most lessees don't know the implicit rate. Default to the IBR unless you can calculate the implicit rate with confidence.

**2. Forgetting to remeasure on variable rate leases**
If your lease payments change based on a benchmark rate, you must remeasure the liability when the rate changes.

**3. Treating operating lease ROU amortization as a separate line**
Operating lease ROU amortization is a **plug** — it's not separately disclosed. The only P&L line is "Lease Expense."

**4. Wrong cash flow classification for finance leases**
Finance lease principal payments go in **financing activities**. Interest payments go in **operating activities**.

**5. Not reconciling the liability rollforward to the GL**
At period end, your lease liability balance per the amortization schedule should tie exactly to the GL.

---

## Frequently Asked Questions

**What is the journal entry for a lease under ASC 842?**
At commencement you debit the right-of-use asset and credit the lease liability for the present value of the payments. Each month, an operating lease books a single straight-line lease expense, while a finance lease books separate interest and depreciation entries.

**How are operating and finance lease journal entries different?**
An operating lease records one straight-line lease expense each period. A finance lease splits the cost into interest expense (effective-interest method) and depreciation of the ROU asset, producing a front-loaded total expense.

**What is the journal entry when a lease terminates early?**
You derecognize the remaining right-of-use asset and lease liability. Any difference between the two balances, plus any termination penalty paid, is recorded as a gain or loss on lease termination.

**Do you record interest separately on an operating lease under ASC 842?**
No. Interest is computed internally to amortize the liability, but it is not presented separately. The income statement shows only a single straight-line lease expense; the ROU amortization is a plug that makes total expense equal the straight-line payment.

---

## The Reconciliation Problem

The journal entries above all pull from the same [lease amortization schedule](/posts/asc-842-amortization-schedule-excel/), and they work cleanly for a single lease. With 5, 10, or 20 leases across different commencement dates, you need a systematic way to aggregate interest, depreciation, and amortization — and tie everything to the balance sheet.

That's exactly what the ASC 842 Lease Accounting Workbook handles — 20 leases, 120-month amortization schedule, period-level journal entry aggregation, and a reconciliation tab that confirms everything ties to $0 every month.

**[$97, one time. No subscription. Get it here →](https://kdeskaccounting.gumroad.com/l/phxigq)**

Or [try the free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc) to see it working before you buy.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
