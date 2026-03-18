---
title: "ASC 842 vs IFRS 16: Key Differences Every Controller Should Know"
date: 2026-03-11
description: "ASC 842 and IFRS 16 both put leases on the balance sheet, but the details diverge in ways that matter. Here's a side-by-side breakdown of classification, discount rates, exemptions, and P&L treatment."
summary: "Both standards eliminate off-balance-sheet operating leases, but ASC 842 and IFRS 16 diverge on lease classification, discount rates, short-term exemptions, and income statement presentation. If you report under both — or are switching — here's what actually differs."
tags: ["ASC 842", "IFRS 16", "lease accounting", "GAAP", "IFRS", "Excel template", "controller"]
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

---

## Difference 1: Lease Classification

This is the biggest practical difference.

### ASC 842 (US GAAP)
Leases are classified as either **operating** or **finance** based on five criteria:

1. Transfer of ownership by end of lease
2. Purchase option the lessee is reasonably certain to exercise
3. Lease term is for the **major part** of the asset's remaining economic life (typically ≥75%)
4. Present value of payments is **substantially all** of the asset's fair value (typically ≥90%)
5. Asset is specialized with no alternative use to the lessor

If any criterion is met → **finance lease**. Otherwise → **operating lease**.

### IFRS 16
**IFRS 16 does not distinguish between operating and finance leases for lessees.** All leases (above the thresholds) are treated like finance leases: depreciation + interest, front-loaded expense, financing cash flow for principal.

### Why it matters

Under US GAAP, a company with mostly operating leases reports a **single flat lease expense line** — straightforward, non-volatile. Under IFRS 16, that same company reports **depreciation + interest** — EBITDA goes up, but profit is front-loaded in early lease years.

---

## Difference 2: Discount Rate

### ASC 842
Use the **rate implicit in the lease** if readily determinable. If not (usually the case), use the **incremental borrowing rate (IBR)**. Private companies have a practical expedient to use the **risk-free rate** instead of the IBR.

### IFRS 16
Same hierarchy: implicit rate first, then IBR. No risk-free rate option for private companies.

---

## Difference 3: Short-Term and Low-Value Exemptions

### ASC 842
One exemption: **short-term leases** (term of 12 months or less at commencement). Election is made by **class of underlying asset**. No low-value exemption.

### IFRS 16
Two exemptions:

1. **Short-term leases** — same as ASC 842, ≤12 months
2. **Low-value asset leases** — assets with a value when new of approximately **$5,000 USD or less**. Election is lease-by-lease.

---

## Difference 4: Income Statement Presentation

### ASC 842

| Lease type | P&L presentation |
|------------|------------------|
| Operating | Single **lease expense** line, straight-line |
| Finance | **Depreciation** (straight-line) + **Interest expense** (effective interest) |

### IFRS 16

Since all leases are treated as finance leases: **Depreciation** of the ROU asset + **Interest expense** on the lease liability. Total expense is front-loaded for every lease.

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

## Building the Schedule

Whether you're under ASC 842, IFRS 16, or both, the underlying math — PV of payments, amortization waterfall, ROU asset rollforward — is the same. The difference is in presentation and classification.

The [ASC 842 Lease Accounting Workbook](https://kdeskaccounting.gumroad.com/l/phxigq) is structured around US GAAP but the amortization math and journal entry logic is compatible with IFRS 16 as well.

**[$97, one time. No subscription. Get it here →](https://kdeskaccounting.gumroad.com/l/phxigq)**

Or [try the free 3-lease version](https://kdeskaccounting.gumroad.com/l/gljxc) before you buy.

---

*KDesk Accounting builds audit-ready Excel tools for finance teams. [Browse all templates →](/templates/)*
