---
title: "Right-of-Use Asset: How to Calculate and Record It Under ASC 842"
date: 2026-03-16
description: "How to calculate the right-of-use (ROU) asset at lease commencement under ASC 842 — including initial direct costs, prepaid rent, and lease incentives. With journal entries and common mistakes."
summary: "The ROU asset at commencement equals the lease liability plus initial direct costs plus prepaid rent minus lease incentives received. Most teams get the lease liability right but miss the adjustments. Here's how to calculate it correctly."
tags: ["ASC 842", "right-of-use asset", "ROU asset", "lease accounting", "Excel template", "GAAP", "journal entries"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 7
---

When a lease commences under ASC 842, you recognize a right-of-use (ROU) asset on the balance sheet. Most finance teams calculate the lease liability correctly. The ROU asset is where adjustments get missed — and those omissions show up at audit.

The formula is straightforward:

```
ROU Asset = Lease Liability + Initial Direct Costs + Prepaid Rent − Lease Incentives Received
```

---

## The ROU Asset Formula

```
ROU Asset at Commencement = Lease Liability
                           + Initial Direct Costs (IDC)
                           + Prepaid Rent
                           − Lease Incentives Received
```

---

## Component 1 — The Lease Liability

The lease liability is the present value of all future lease payments, discounted at the IBR.

**Example:** 36-month office lease, $5,000/month, 6% IBR.

```
=PV(6%/12, 36, -5000)  →  $164,029
```

---

## Component 2 — Initial Direct Costs (IDC)

Initial direct costs are **incremental costs of obtaining a lease** that would not have been incurred if the lease had not been obtained.

**Costs that qualify:** Legal fees paid to negotiate and execute the lease, broker commissions paid to obtain the lease.

**Costs that do NOT qualify:** Internal legal staff time, general overhead, due diligence costs, IT setup, moving costs, tenant buildout.

**Journal entry — recording IDC at commencement** (assuming $2,000 in legal fees):

```
DR  Right-of-Use Asset          2,000
    CR  Cash (or Accounts Payable)        2,000
```

**Running example:** ROU asset after IDC = $164,029 + $2,000 = $166,029.

---

## Component 3 — Prepaid Rent

Prepaid rent is any lease payment made at or before lease commencement. At commencement, the prepaid rolls into the ROU asset:

```
DR  Right-of-Use Asset          169,029   (164,029 + 2,000 + 5,000 − 0)
    CR  Lease Liability                    164,029
    CR  Prepaid Rent                         5,000
```

**Running example:** ROU asset after IDC and prepaid = $171,029.

---

## Component 4 — Lease Incentives Received

Lease incentives reduce the ROU asset. The most common example: a **tenant improvement allowance (TIA)**.

When you receive the TIA:

```
DR  Cash                        10,000
    CR  Lease Incentive Obligation         10,000
```

At commencement, the incentive obligation reduces the ROU asset:

```
DR  Right-of-Use Asset          161,029   (164,029 + 2,000 + 5,000 − 10,000)
DR  Lease Incentive Obligation  10,000
    CR  Lease Liability                    164,029
    CR  Prepaid Rent                         5,000
```

**Running example:** Final ROU asset = **$161,029**.

---

## Operating vs. Finance — Does It Change the ROU Asset?

**No.** The initial ROU asset calculation is identical for operating and finance leases. The difference is in **amortization**:

| | Operating Lease | Finance Lease |
|--|--|--|
| ROU asset amortization | Plug (makes total expense = straight-line payment) | Straight-line over lease term |
| Income statement | Single "Lease Expense" line | Separate "Depreciation" + "Interest Expense" |
| Total expense pattern | Flat (same every period) | Front-loaded (higher early, lower late) |

---

## Common Mistakes

**1. Forgetting IDC entirely.** Legal fees to obtain the lease are often coded directly to legal expense. Any third-party incremental cost should be in the asset.

**2. Missing lease incentives (especially TIAs).** Tenant improvement allowances are ubiquitous in commercial office leases. If you received a TIA and didn't reduce the ROU asset, your opening balance is overstated.

**3. Capitalizing non-incremental costs.** Internal legal staff time, facility setup, IT infrastructure — these don't qualify.

**4. Using the wrong discount rate.** The IBR should be specific to the lease term and the lessee's credit profile.

**5. Double-counting prepaid rent.** If your first month's rent is embedded in the PV calculation as a Period 1 payment of $0, don't also add it as prepaid rent.

---

## The Full Initial Recognition Journal Entry

Combining all four components (36-month lease, $5,000/month, 6% IBR, $2,000 IDC, $5,000 prepaid, $10,000 TIA):

```
DR  Right-of-Use Asset          161,029
DR  Lease Incentive Obligation   10,000
    CR  Lease Liability                    164,029
    CR  Cash (IDC)                           2,000
    CR  Prepaid Rent                         5,000
```

After this entry: Lease liability = $164,029, ROU asset = $161,029. Both reach $0 at month 36.

---

## Tracking It Over the Lease Life

The [ASC 842 Lease Accounting Workbook](/templates/asc842/) handles the full calculation — ROU asset opening balance including IDC, prepaid, and incentives; 120-month amortization schedule per lease; period journal entry aggregation — for up to 20 leases in a single file.

[**Get the Workbook ($97) →**](https://kdeskaccounting.gumroad.com/l/phxigq)

[Try the free 3-lease version →](https://kdeskaccounting.gumroad.com/l/gljxc)

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
