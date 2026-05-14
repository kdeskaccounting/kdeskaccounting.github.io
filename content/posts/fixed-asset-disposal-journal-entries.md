---
title: "Fixed Asset Disposal Journal Entries: Sale, Retirement, Trade-in, and Write-off"
date: 2026-05-13
lastmod: 2026-05-13
description: "Complete guide to fixed asset disposal journal entries — sale, retirement, trade-in (ASC 845), write-off, and casualty loss. Worked examples, gain/loss math, commercial-substance test, and the audit evidence your auditor will request."
summary: "A practical walkthrough of journal entries for every type of fixed asset disposal. Covers the generic disposal pattern, then steps through sale, retirement, trade-in (with the ASC 845 commercial-substance test), write-off, and casualty loss — each with a worked example and the JE that ties out. Plus the authorization and evidence anchors auditors require."
tags: ["fixed asset disposal", "disposal journal entry", "ASC 360", "ASC 845", "asset retirement", "trade-in accounting", "asset write-off", "fixed assets", "Excel", "accounting"]
author: "KDesk Accounting"
ShowToc: true
TocOpen: true
weight: 15
---

Fixed asset disposals are where audit issues hide. The depreciation math is mechanical — once you have a schedule that ties, it stays tied month after month. Disposals are different. Every disposal is a one-off transaction with its own paperwork trail, its own gain/loss calculation, and a journal entry that varies depending on whether you sold the asset, traded it in, scrapped it, or lost it to a casualty.

Auditors know this. When they sample your fixed asset register, the disposals are what they look at hardest — proceeds, authorization, evidence of removal, and whether the entry posted the right way.

This post walks through the journal entry pattern for every disposal type a SaaS finance team is likely to encounter. We'll start with the generic structure, then work through five specific disposal types with examples and the JEs that tie out.

---

## The Generic Disposal Journal Entry

Every fixed asset disposal does four things at once on the balance sheet:

1. **Removes the asset's original cost** from the asset account (CR Asset @ cost).
2. **Removes the accumulated depreciation** booked against that asset (DR Accumulated Depreciation).
3. **Records any consideration received** — cash, a receivable, a new asset (DR Cash / Receivable / New Asset).
4. **Recognizes the gain or loss** on the disposal (CR Gain on Disposal *or* DR Loss on Disposal).

The general pattern:

| Account                        | DR     | CR     |
|--------------------------------|--------|--------|
| Cash / AR / New Asset (consideration) | XXX    |        |
| Accumulated Depreciation       | XXX    |        |
| Loss on Disposal (if loss)     | XXX    |        |
| &nbsp;&nbsp;&nbsp;Asset @ original cost                |        | XXX    |
| &nbsp;&nbsp;&nbsp;Gain on Disposal (if gain)           |        | XXX    |

The math is simple in principle: **Gain or (Loss) = Consideration Received − Net Book Value (NBV)** where NBV = original cost − accumulated depreciation through the disposal date.

The complications come from (a) what counts as "consideration received" — particularly with trade-ins, (b) how you handle accumulated depreciation when the disposal falls mid-month, and (c) the audit evidence around the disposal itself. Let's walk through each disposal type.

---

## 1. Sale — Asset Sold for Cash

This is the cleanest disposal type. You sell the asset, you receive cash, you compare proceeds to NBV, and you book the gain or loss.

**Example.** A delivery vehicle was placed in service on March 1, 2026 at a cost of $42,000 with a $4,200 salvage value, 60-month useful life, SYD depreciation. The vehicle is sold on June 15, 2027 for $32,000 cash.

- Original cost: **$42,000**
- Accumulated depreciation through June 15, 2027 (15 full periods under SYD): **$16,420** (computed against $37,800 depreciable base)
- NBV at disposal: $42,000 − $16,420 = **$25,580**
- Proceeds: **$32,000**
- Gain on disposal: $32,000 − $25,580 = **$6,420**

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| Cash                           | 32,000.00 |           |
| Accumulated Depreciation — Vehicles | 16,420.00 |           |
| &nbsp;&nbsp;&nbsp;Vehicles @ cost              |           | 42,000.00 |
| &nbsp;&nbsp;&nbsp;Gain on Disposal             |           |  6,420.00 |

Total debits = $48,420. Total credits = $48,420. Entry balances.

If the vehicle had been sold for $20,000 instead, the entry flips:

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| Cash                           | 20,000.00 |           |
| Accumulated Depreciation — Vehicles | 16,420.00 |           |
| Loss on Disposal               |  5,580.00 |           |
| &nbsp;&nbsp;&nbsp;Vehicles @ cost              |           | 42,000.00 |

Same mechanics, different sign on the gain/loss line.

**Audit evidence required.** Bill of sale, deposit confirmation showing the proceeds hit your bank account, signed disposal authorization (typically COO or CFO for assets above your materiality threshold), and the counterparty's name and address.

---

## 2. Retirement — Asset Scrapped with No Proceeds

A retirement is what you book when an asset reaches end of life and is disposed of for nothing — scrapped, discarded, or simply taken offline. There's no cash. If the asset was fully depreciated, the entry zeros it out and there's no P&L impact. If there's residual NBV at retirement, the remaining NBV becomes a loss.

**Example A — Fully depreciated asset retired.** A $8,000 server bought January 2021 with 60-month useful life, straight-line, was fully depreciated by January 2026. The server is retired and hauled away in May 2026 with no proceeds.

- Original cost: $8,000
- Accumulated depreciation: $8,000 (fully depreciated)
- NBV: $0
- Proceeds: $0
- Gain/Loss: $0

| Account                        | DR       | CR       |
|--------------------------------|----------|----------|
| Accumulated Depreciation — Servers | 8,000.00 |          |
| &nbsp;&nbsp;&nbsp;Servers @ cost               |          | 8,000.00 |

Clean reversal. No income statement impact.

**Example B — Retirement with residual NBV.** A $8,000 server retired with $2,000 of NBV still on the books (only $6,000 accumulated depreciation because it was retired early).

| Account                        | DR       | CR       |
|--------------------------------|----------|----------|
| Accumulated Depreciation — Servers | 6,000.00 |          |
| Loss on Disposal               | 2,000.00 |          |
| &nbsp;&nbsp;&nbsp;Servers @ cost               |          | 8,000.00 |

The residual NBV becomes an immediate loss. This is the right answer under ASC 360-10-40-3 — once you decide to dispose of an asset rather than continue using it, you stop depreciating and write off the remainder.

**Audit evidence required.** Scrap receipt or destruction certificate, authorization signed by the asset owner or department head, and a notation in the asset register stating the reason for early retirement (technology refresh, equipment failure, etc.).

---

## 3. Trade-in — Asset Exchanged for a New Asset (ASC 845)

Trade-ins are the disposal type most commonly mis-booked. The complication is ASC 845, which governs nonmonetary exchanges. The accounting depends entirely on whether the exchange has **commercial substance**, defined in ASC 845-10-30-4 as an exchange where future cash flows are expected to change significantly as a result of the swap.

**The commercial-substance test.** Ask two questions:

1. Does the configuration (risk, timing, amount) of future cash flows of the **new** asset differ significantly from the configuration of the **old** asset's future cash flows?
2. Is the fair value of the asset received different from the carrying amount of the asset surrendered?

If yes to either, the exchange has commercial substance. Most trade-ins for genuinely different assets — old laptop fleet for a new server rack, old vehicle for a different vehicle class — pass this test easily. Like-kind trades (one model of laptop for the next year's model, used in the same workflow) often **don't** pass it.

**Why it matters:** with commercial substance, you account for the exchange at **fair value** and recognize the full gain or loss. Without it, you account at **carryover basis** — the new asset is recorded at the NBV of the old asset (plus any cash paid), and no gain is recognized.

**Example C — Trade-in with commercial substance.** Old delivery vehicle: cost $30,000, accumulated depreciation $24,000, NBV $6,000. Traded for a new vehicle with a sticker price of $40,000. Dealer credits $10,000 for the trade-in, you pay $30,000 cash. The new vehicle is a larger cargo van with different operational economics, so the exchange has commercial substance.

- Fair value of old vehicle (trade-in credit): $10,000
- NBV of old vehicle: $6,000
- Gain on disposal: $10,000 − $6,000 = $4,000
- New vehicle recorded at fair value: $30,000 cash + $10,000 trade-in = **$40,000**

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| New Vehicle @ FV               | 40,000.00 |           |
| Accumulated Depreciation — Vehicles | 24,000.00 |           |
| &nbsp;&nbsp;&nbsp;Old Vehicle @ cost            |           | 30,000.00 |
| &nbsp;&nbsp;&nbsp;Cash                          |           | 30,000.00 |
| &nbsp;&nbsp;&nbsp;Gain on Disposal              |           |  4,000.00 |

Entry balances at $64,000 on each side.

**Example D — Same trade-in, no commercial substance.** Same numbers, but the new vehicle is a near-identical replacement (like-kind, similar utility, similar future cash flows). Per ASC 845-10-30-3, no gain is recognized; the new vehicle is recorded at carryover basis.

- Carryover basis: NBV of old ($6,000) + cash paid ($30,000) = **$36,000**

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| New Vehicle (carryover basis)  | 36,000.00 |           |
| Accumulated Depreciation — Vehicles | 24,000.00 |           |
| &nbsp;&nbsp;&nbsp;Old Vehicle @ cost            |           | 30,000.00 |
| &nbsp;&nbsp;&nbsp;Cash                          |           | 30,000.00 |

No gain recognized, even though the dealer credited $10,000. The book treatment ignores the dealer's trade-in valuation when commercial substance is absent.

**Important asymmetry:** even without commercial substance, **losses** are still recognized if NBV exceeds fair value. ASC 845 doesn't shield you from loss recognition. The "no gain recognition" rule applies one direction only.

**Audit evidence required.** Trade-in agreement showing the dealer's valuation, fair-value documentation (independent appraisal, comparable sale data, or a bill of sale for a similar asset), and a memo documenting the commercial-substance assessment. This last one is the most-missed audit anchor. Your auditor will ask why you concluded the way you did.

---

## 4. Write-off — Asset Impaired or Destroyed

A write-off is what you book when an asset becomes unusable without producing proceeds — damaged beyond repair, technologically obsolete and unsellable, or rendered useless by an environmental event short of casualty (a server room flood, for example).

The journal entry pattern is similar to a retirement, but with a P&L line for the entire NBV:

**Example.** Laptop fleet purchased January 2026 for $12,000, depreciated $9,000 by November 2026, then destroyed in a server room flood. No insurance recovery.

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| Accumulated Depreciation — Computer Equipment | 9,000.00  |           |
| Loss on Disposal — Write-off   | 3,000.00  |           |
| &nbsp;&nbsp;&nbsp;Computer Equipment @ cost     |           | 12,000.00 |

The remaining NBV ($3,000) becomes a loss on disposal in the period of the write-off.

If you later receive insurance proceeds for the destroyed assets, that's a **separate** journal entry — DR Cash, CR Insurance Recovery (or CR Loss on Disposal in the same period if the insurance lands within the same close). Don't combine the two into a single entry; auditors want them separable.

**Audit evidence required.** Damage report, photo evidence, insurance claim documentation if applicable, and signed authorization for the write-off from the appropriate authority (typically CFO for material write-offs).

---

## 5. Casualty Loss / Theft

Casualty loss and theft are accounting-wise the same as a write-off but typically route through a **Casualty Loss** account rather than a routine Loss on Disposal, depending on your chart of accounts. The line distinction matters because casualty losses are reported separately on the income statement and disclosed in MD&A if material.

**Example.** Machinery worth $15,000 (cost), $5,000 accumulated depreciation, stolen from the warehouse. NBV at theft = $10,000. Insurance receivable confirmed at $8,000.

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| Accumulated Depreciation — Machinery | 5,000.00  |           |
| Insurance Receivable           | 8,000.00  |           |
| Casualty Loss                  | 2,000.00  |           |
| &nbsp;&nbsp;&nbsp;Machinery @ cost              |           | 15,000.00 |

When the insurance pays, you reverse the receivable: DR Cash $8,000, CR Insurance Receivable $8,000.

If you have no insurance, the entire NBV becomes the casualty loss:

| Account                        | DR        | CR        |
|--------------------------------|-----------|-----------|
| Accumulated Depreciation — Machinery | 5,000.00  |           |
| Casualty Loss                  | 10,000.00 |           |
| &nbsp;&nbsp;&nbsp;Machinery @ cost              |           | 15,000.00 |

**Audit evidence required.** Police report (for theft), insurance claim filing, evidence of insurance carrier acceptance (for the receivable side), and a memo describing the event.

---

## Three Disposal Pitfalls That Cause Audit Findings

A few common mistakes that show up in audit findings around disposals:

**1. Forgetting partial-period depreciation up to the disposal date.** If your convention is Full Month, an asset disposed of on June 15 still earns June depreciation. If your convention is Mid-Month, depreciation stops mid-month. Whatever your policy is, apply it consistently — and document the convention in your asset policy table. The NBV at disposal must reflect depreciation through the actual disposal date, not the prior month-end.

**2. Deleting the disposed asset row from the register.** This destroys the audit trail. Auditors will sample disposals during fieldwork and ask to vouch back to the register. If the row is gone, you're scrambling to reproduce documentation. The correct approach: keep the row in the register, mark the asset's status as Disposed, and post the disposal entry separately on the Disposal Log. The asset register row gets "soft-deleted," not removed.

**3. Trade-in commercial-substance assessment skipped entirely.** This is the most common ASC 845 violation in practice. Companies book trade-ins at the dealer's trade-in valuation (recognizing gain) without ever testing whether the exchange has commercial substance. For many like-kind SaaS trades — laptop refresh, server replacement with the same configuration — commercial substance is absent and any "gain" should not be recognized. The fix is a one-paragraph memo at disposal time documenting your assessment. It takes five minutes; skipping it can cost a restatement.

---

## How the Fixed Asset Rollforward Workbook Handles Disposals

The [Fixed Asset Rollforward Workbook](/templates/fixed-assets/) ships with a dedicated Disposal Log tab that handles all five disposal types automatically. For each disposal you enter:

- Asset ID (dropdown linked to the Register)
- Disposal date and disposal type (Sale, Retirement, Trade-in, Write-off, Theft-loss)
- Commercial Substance flag (Y/N/N/A) for trade-ins — drives the ASC 845 treatment
- Proceeds, Authorization name and date, Evidence Type, Evidence Reference, Counterparty

The workbook automatically calculates Disposal Cost, Accumulated Depreciation at disposal, NBV at disposal, and Gain/(Loss). The JE Generator then renders the disposal entry — DR Cash, DR Accum Depr, CR Asset @ cost, and either DR Loss or CR Gain — period-gated so only in-period disposals appear in the export.

The Reconciliation tab has a dedicated check for the disposal NBV total tying to the Disposal Log sum, which catches missing-row or stale-date errors before they hit the GL.

If you're managing a register with more than a handful of disposals per year, the workbook handles the bookkeeping mechanics so you can focus on the audit evidence side. [Get the workbook for $79](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward), or [try the free 5-asset version](https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free) first to see how the Disposal Log feeds the JE Generator and Reconciliation on your own data.

---

For the depreciation math behind the NBV calculation — how you arrive at the accumulated depreciation balance at disposal date — see [Fixed Asset Depreciation Schedule in Excel: How to Build One From Scratch](/posts/fixed-asset-depreciation-schedule-excel/). For broader month-end close coverage, the [month-end close checklist for controllers](/posts/month-end-close-checklist-controllers/) walks the full close workflow including fixed-asset and disposal procedures.
