---
title: "Right-of-Use Asset: How to Calculate and Record It Under ASC 842"
date: 2026-03-18
description: "How to calculate the right-of-use (ROU) asset at lease commencement under ASC 842 — including initial direct costs, prepaid rent, and lease incentives. With journal entries and common mistakes."
summary: "The ROU asset at commencement equals the lease liability plus initial direct costs plus prepaid rent minus lease incentives received. Most teams get the lease liability right but miss the adjustments. Here's how to calculate it correctly."
tags: ["ASC 842", "right-of-use asset", "ROU asset", "lease accounting", "GAAP", "journal entries"]
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

For most leases, there are no adjustments and the ROU asset equals the lease liability. But when there are initial direct costs, prepaid rent, or lease incentives — common in office leases — getting those components right matters.

---

## The ROU Asset Formula

```
ROU Asset at Commencement = Lease Liability
                           + Initial Direct Costs (IDC)
                           + Prepaid Rent
                           − Lease Incentives Received
```

Each component has a specific definition under ASC 842. Let's work through each one.

---

## Component 1 — The Lease Liability

The lease liability is the present value of all future lease payments, discounted at the incremental borrowing rate (IBR).

**Example:** 36-month office lease, $5,000/month, 6% IBR.

```
=PV(6%/12, 36, -5000)  →  $164,029
```

The lease liability = $164,029. This is the starting point for the ROU asset.

For a full walkthrough of the PV calculation and monthly amortization, see [ASC 842 Amortization Schedule: How to Build One in Excel](/posts/asc-842-amortization-schedule-excel/).

---

## Component 2 — Initial Direct Costs (IDC)

Initial direct costs are **incremental costs of obtaining a lease** that would not have been incurred if the lease had not been obtained.

**Costs that qualify as IDC:**
- Legal fees paid directly to negotiate and execute the lease
- Broker commissions paid to obtain the lease
- Any other incremental transaction cost paid to a third party

**Costs that do NOT qualify:**
- Internal legal staff time (not incremental — the cost exists regardless of the lease)
- General overhead allocated to the lease transaction
- Due diligence costs incurred before deciding to lease
- IT setup, moving costs, or tenant buildout

The distinction is strict: if the cost would have been incurred even if you didn't sign the lease, it's not IDC.

**Journal entry — recording IDC at commencement:**

Assuming $2,000 in qualifying legal fees paid at signing:

```
DR  Right-of-Use Asset          2,000
    CR  Cash (or Accounts Payable)        2,000
```

This adds $2,000 to the ROU asset basis. It amortizes over the lease term as part of the ROU asset, not separately.

**Running example:** ROU asset after IDC = $164,029 + $2,000 = $166,029.

---

## Component 3 — Prepaid Rent

Prepaid rent is any lease payment made at or before lease commencement. The most common scenario: your landlord requires the first month's rent before you get keys.

**Example:** First month's rent of $5,000 paid 2 weeks before the lease start date.

Before commencement, you'd record:

```
DR  Prepaid Rent (asset)        5,000
    CR  Cash                              5,000
```

At commencement, the prepaid rolls into the ROU asset:

```
DR  Right-of-Use Asset          169,029   (164,029 + 2,000 + 5,000 − 0)
    CR  Lease Liability                    164,029
    CR  Prepaid Rent                         5,000
```

The ROU asset absorbs the prepaid rent because it represents your right to use the asset over the full lease term, including the period covered by the prepaid.

**Running example:** ROU asset after IDC and prepaid = $164,029 + $2,000 + $5,000 = $171,029.

---

## Component 4 — Lease Incentives Received

Lease incentives reduce the ROU asset. The most common example in commercial real estate: a **tenant improvement allowance (TIA)** — cash the landlord gives you to build out the space.

**Example:** $10,000 TIA received from the landlord at commencement.

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

**Note on rent-free periods:** If your lease includes a period of free rent at the start, this is typically already captured in the PV calculation — the cash payment for those periods is $0, which is reflected in the present value. You don't add back the rent-free benefit as a separate incentive adjustment unless the landlord paid you cash or made improvements on your behalf.

**Running example:** Final ROU asset = $164,029 + $2,000 + $5,000 − $10,000 = **$161,029**.

---

## Operating vs. Finance — Does It Change the ROU Asset?

**No.** The initial ROU asset calculation is identical for operating and finance leases. Both use the same formula:

```
ROU Asset = Lease Liability + IDC + Prepaid Rent − Incentives
```

The difference is in **amortization**:

| | Operating Lease | Finance Lease |
|--|--|--|
| ROU asset amortization | Plug (makes total expense = straight-line payment) | Straight-line over lease term |
| Income statement | Single "Lease Expense" line | Separate "Depreciation" + "Interest Expense" |
| Total expense pattern | Flat (same every period) | Front-loaded (higher early, lower late) |

Month 1 comparison using identical inputs ($161,029 ROU, 36-month term, 6% IBR, $5,000/month):

| | Operating | Finance |
|--|--:|--:|
| Depreciation / ROU amortization | $4,180 (plug) | $4,473 (straight-line: $161,029 ÷ 36) |
| Interest expense | — (included in lease expense) | $820 |
| Total expense | $5,000 | $5,293 |

Finance lease total expense is higher in early months because the interest is recognized separately and the ROU amortization is straight-line rather than a plug.

---

## Common Mistakes

**1. Forgetting IDC entirely.**
Legal fees to obtain the lease are often coded directly to legal expense. If you expensed them rather than capitalizing them as IDC, your ROU asset is understated. Auditors routinely ask for invoices related to lease execution — any third-party incremental cost should be in the asset.

**2. Missing lease incentives (especially TIAs).**
Tenant improvement allowances are ubiquitous in commercial office leases. If you received a TIA and didn't reduce the ROU asset, your opening balance is overstated. Check your lease agreement for any landlord contributions to buildout.

**3. Capitalizing non-incremental costs.**
Internal legal staff time, facility setup, IT infrastructure — these don't qualify. Adding them inflates the ROU asset and overstates amortization expense over the lease term.

**4. Using the wrong discount rate.**
The IBR should be specific to the lease term and the lessee's credit profile. Using a generic corporate borrowing rate for a 3-year lease when your actual borrowing rate for 3-year debt is different will shift every number in the amortization schedule.

**5. Double-counting prepaid rent.**
If your first month's rent is embedded in the PV calculation as a Period 1 payment of $0 (some leases structure it this way), don't also add it as prepaid rent. Prepaid rent is only the amount paid *before* the commencement date that is *not already reflected* in the PV of future payments.

---

## The Full Initial Recognition Journal Entry

Combining all four components for our running example (36-month lease, $5,000/month, 6% IBR, $2,000 IDC, $5,000 prepaid, $10,000 TIA):

| Component | Amount |
|-----------|--------|
| Lease liability (PV) | $164,029 |
| + Initial direct costs | $2,000 |
| + Prepaid rent | $5,000 |
| − Lease incentives (TIA) | ($10,000) |
| **ROU Asset** | **$161,029** |

**Combined commencement entry:**

```
DR  Right-of-Use Asset          161,029
DR  Lease Incentive Obligation   10,000
    CR  Lease Liability                    164,029
    CR  Cash (IDC)                           2,000
    CR  Prepaid Rent                         5,000
```

This is the entry your accountant posts on the commencement date. After this entry:

- Lease liability = $164,029 (declines as principal payments are made)
- ROU asset = $161,029 (amortizes to $0 at month 36)
- Lease incentive obligation = $0 (absorbed into ROU asset)
- Prepaid rent = $0 (rolled into ROU asset)

---

## Tracking It Over the Lease Life

After initial recognition, the ROU asset amortizes each period alongside the lease liability. By the end of the lease term, both balances reach $0.

For one lease, this is manageable in a manual spreadsheet. For a portfolio of 5–20 leases with different commencement dates, IDC, incentives, and occasional modifications, maintaining the schedules manually becomes a material time commitment each close.

The [ASC 842 Lease Accounting Workbook](/templates/asc842/) handles the full calculation — ROU asset opening balance including IDC, prepaid, and incentives; 120-month amortization schedule per lease; period journal entry aggregation — for up to 20 leases in a single file.

[**Get the Workbook ($97) →**](https://kdeskaccounting.gumroad.com/l/phxigq)

[Try the free 3-lease version →](https://kdeskaccounting.gumroad.com/l/gljxc)

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](https://kdeskaccounting.gumroad.com)*
