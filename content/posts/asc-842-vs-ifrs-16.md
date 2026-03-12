---
title: "ASC 842 vs IFRS 16: Key Differences Every Controller Should Know"
date: 2026-03-11
description: "ASC 842 and IFRS 16 both put leases on the balance sheet, but the details diverge in ways that matter. Here's a side-by-side breakdown of classification, discount rates, exemptions, and P&L treatment."
summary: "Both standards eliminate off-balance-sheet operating leases, but ASC 842 and IFRS 16 diverge on lease classification, discount rates, short-term exemptions, and income statement presentation. If you report under both — or are switching — here's what actually differs."
tags: ["ASC 842", "IFRS 16", "lease accounting", "GAAP", "IFRS", "controller"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 3
---

ASC 842 (US GAAP) and IFRS 16 (international) were designed in parallel and share the same core principle: leases go on the balance sheet. But the two standards diverge in several important ways — some minor, some significant enough to change how you structure leases and present results.

Here's a practical side-by-side breakdown.

---

## The Big Picture: What's the Same

Before the differences, what's aligned:

- **Both require a right-of-use (ROU) asset and lease liability** for most leases at commencement
- **Both use present value of future payments** discounted at the appropriate rate
- **Both have a short-term exemption** (≤12 months)
- **Both apply to lessees** — lessor accounting differs more significantly but is less commonly impacted
- **Both require disclosure** of maturity analysis, weighted-average rates, and future lease obligations

If you've implemented one, the conceptual framework transfers to the other.

---

## Difference 1: Lease Classification

This is the biggest practical difference.

### ASC 842 (US GAAP)
Leases are classified as either **operating** or **finance** based on five criteria (similar to the old capital lease tests under ASC 840):

1. Transfer of ownership by end of lease
2. Purchase option the lessee is reasonably certain to exercise
3. Lease term is for the **major part** of the asset's remaining economic life (typically ≥75%)
4. Present value of payments is **substantially all** of the asset's fair value (typically ≥90%)
5. Asset is specialized with no alternative use to the lessor

If any criterion is met → **finance lease**. Otherwise → **operating lease**.

### IFRS 16
**IFRS 16 does not distinguish between operating and finance leases for lessees.** All leases (above the thresholds) are treated like finance leases: depreciation + interest, front-loaded expense, financing cash flow for principal.

The only exception is the short-term and low-value asset exemptions (see below).

### Why it matters

Under US GAAP, a company with mostly operating leases reports a **single flat lease expense line** — straightforward, non-volatile. Under IFRS 16, that same company reports **depreciation + interest** — EBITDA goes up (lease expense moves below EBITDA), but profit is front-loaded in early lease years.

This is why some companies that report under both standards show different EBITDA figures — and why analysts make adjustments when comparing GAAP vs IFRS companies.

---

## Difference 2: Discount Rate

### ASC 842
Use the **rate implicit in the lease** if readily determinable. If not (usually the case), use the **incremental borrowing rate (IBR)** — the rate the lessee would pay to borrow funds at a similar term and collateral.

Private companies have a practical expedient to use the **risk-free rate** instead of the IBR, which simplifies the calculation at the cost of a larger liability.

### IFRS 16
Same hierarchy: implicit rate first, then IBR. No risk-free rate option for private companies.

However, IFRS 16 provides more guidance on portfolio-level IBR determination, which can simplify implementation for companies with many similar leases.

### Practical impact

For most companies, the IBR is similar under both standards since it's based on the same economic reality — the company's borrowing cost. The difference shows up mainly for private companies that elect the risk-free rate expedient under ASC 842.

---

## Difference 3: Short-Term and Low-Value Exemptions

### ASC 842
One exemption: **short-term leases** (term of 12 months or less at commencement). Election is made by **class of underlying asset**.

No low-value exemption.

### IFRS 16
Two exemptions:

1. **Short-term leases** — same as ASC 842, ≤12 months
2. **Low-value asset leases** — assets with a value when new of approximately **$5,000 USD or less** (IASB guidance). Common examples: laptops, small office equipment, phones. Election is lease-by-lease (not by class).

The low-value exemption is a meaningful simplification for companies with many small equipment leases. Under ASC 842, every one of those leases technically requires recognition unless it's also short-term.

---

## Difference 4: Income Statement Presentation

### ASC 842

| Lease type | P&L presentation |
|------------|-----------------|
| Operating | Single **lease expense** line, straight-line |
| Finance | **Depreciation** (straight-line) + **Interest expense** (effective interest) |

Operating leases show a flat expense. Finance leases front-load expense.

### IFRS 16

Since all leases are treated as finance leases:

- **Depreciation** of the ROU asset (straight-line over lease term or useful life, whichever is shorter)
- **Interest expense** on the lease liability (effective interest method)

Total expense is front-loaded for every lease. This increases EBITDA (depreciation and interest sit below EBITDA) but reduces early-period net income.

---

## Difference 5: Cash Flow Classification

### ASC 842

| Payment type | Cash flow classification |
|-------------|------------------------|
| Operating lease payments | **Operating activities** |
| Finance lease — principal | **Financing activities** |
| Finance lease — interest | **Operating activities** (or financing if policy election) |

### IFRS 16

| Payment type | Cash flow classification |
|-------------|------------------------|
| Lease liability — principal | **Financing activities** |
| Lease liability — interest | **Operating** or **financing** (policy choice) |
| Short-term / low-value | **Operating activities** |

The key difference: under IFRS 16, **all** lease principal payments are financing outflows, which reduces operating cash flow compared to an equivalent company under ASC 842 with operating leases.

This matters when comparing cash flow metrics across companies on different standards.

---

## Difference 6: Sale-Leaseback Transactions

This gets technical, but it's worth flagging.

Under **ASC 842**, a sale-leaseback qualifies as a sale only if it meets the performance obligation criteria under ASC 606. If it qualifies, the gain or loss on the sale is recognized (with some constraints).

Under **IFRS 16**, a sale-leaseback qualifies as a sale only if the transfer meets the IFRS 15 definition of a sale. If it qualifies, the seller-lessee recognizes only the portion of gain or loss relating to the rights transferred to the buyer-lessor.

The practical difference: IFRS 16 limits gain recognition more explicitly for retained rights, which can affect real estate-heavy companies doing sale-leaseback financing.

---

## Side-by-Side Summary

| | ASC 842 (US GAAP) | IFRS 16 |
|--|--|--|
| Lessee classification | Operating or Finance | Single model (all "finance-like") |
| Short-term exemption | ≤12 months, by asset class | ≤12 months, by asset class |
| Low-value exemption | None | ~$5,000 USD, lease-by-lease |
| Discount rate | IBR (or risk-free for private) | IBR |
| Operating lease P&L | Single flat expense | N/A — all depreciation + interest |
| Finance lease P&L | Depreciation + interest | Depreciation + interest |
| Operating lease cash flow | Operating activities | Financing (principal) |
| Effective date | 2019 (public), 2022 (private) | 2019 |

---

## If You Report Under Both Standards

If your company files under US GAAP and has IFRS subsidiaries (or vice versa), the most common reconciling items are:

1. **Reclassification of operating leases** — leases that are operating under ASC 842 become finance-like under IFRS 16, changing EBITDA and cash flow presentation
2. **Discount rate differences** — if using risk-free rate under ASC 842 but IBR under IFRS 16, liability balances will differ
3. **Low-value asset derecognition** — IFRS entities may not have liability/ROU for assets under $5k that US GAAP entities do

Most multi-standard companies maintain separate lease schedules for each framework rather than trying to reconcile from a single model.

---

## Building the Schedule

Whether you're under ASC 842, IFRS 16, or both, the underlying math — PV of payments, amortization waterfall, ROU asset rollforward — is the same. The difference is in presentation and classification.

The [ASC 842 Lease Accounting Workbook](https://kdeskaccounting.gumroad.com) is structured around US GAAP but the amortization math and journal entry logic is compatible with IFRS 16 as well. Operating leases can be treated with the finance lease tab if needed for IFRS reporting.

**[$97, one time. No subscription. Get it here →](https://kdeskaccounting.gumroad.com)**

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](https://kdeskaccounting.gumroad.com)*
