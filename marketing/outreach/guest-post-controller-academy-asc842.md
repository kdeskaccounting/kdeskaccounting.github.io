# ASC 842 Lease Accounting Explained via Example (With a Free Excel Workbook)

*Guest post for Controller Academy · draft 2026-09-06, revised after independent GAAP review · ~1,700 words · Bill edits and owns; byline as he prefers. Author line at the end. Course CTA placeholders in [brackets].*

If you are a controller, the schedule most likely to be maintained by hand — and most likely to be wrong — is the lease schedule. ASC 842 moved nearly every lease onto the balance sheet, and with it came a monthly routine of present values, interest accretion and right-of-use amortization that many teams still run in a spreadsheet someone built years ago. This post walks through the fundamentals, the steps, and one complete example you can reproduce in a free Excel workbook, so the schedule stops being a mystery and becomes a reconciliation.

## Understanding the Fundamentals of ASC 842

Under ASC 842, a lessee recognizes two things for essentially every lease longer than twelve months: a **lease liability** — the present value of the payments not yet made — and a **right-of-use (ROU) asset**, which starts at the liability and is adjusted for prepaid rent, initial direct costs and lease incentives. That is the change from the old standard, ASC 840: operating leases used to live in a footnote; now they live on the balance sheet.

Two classifications remain. A **finance lease** is, in substance, a purchase financed by the lessor — the lessee recognizes interest on the liability and amortization of the ROU asset separately, so expense is front-loaded. An **operating lease** stays a rental in the income statement: a single, generally straight-line lease cost every month, even though the liability still accretes interest and the ROU asset still amortizes on the balance sheet.

Three elections matter for most private companies. The **short-term lease** election made by class of underlying asset, keeps leases of twelve months or less (with no purchase option the lessee is reasonably certain to exercise) off the balance sheet entirely. The **discount rate**: when the rate implicit in the lease is not readily determinable, the lessee uses its incremental borrowing rate, and a lessee that is not a public business entity — most private companies — may instead elect a risk-free rate by class of underlying asset. And the choice not to separate lease and non-lease components (common area maintenance, for instance), which simplifies the accounting at the cost of a larger liability.

## The Five Steps to Account for a Lease Under ASC 842

1. **Identify the lease and its term.** A contract contains a lease when it conveys the right to control an identified asset for a period in exchange for consideration. The lease term is the noncancellable period plus renewal periods the lessee is reasonably certain to exercise (and periods covered by termination options it is reasonably certain not to exercise, or by options the lessor controls).
2. **Classify it.** A lease is a finance lease if any one of five criteria is met: ownership transfers by the end of the term; a purchase option is reasonably certain to be exercised; the term is for a major part of the asset's remaining economic life; the present value of payments (plus any residual value guarantee) is substantially all of the asset's fair value; or the asset is so specialized it has no alternative use to the lessor. Otherwise it is an operating lease. Many companies adopt bright lines — 75 percent of economic life, 90 percent of fair value — as a reasonable application of those criteria and document them in a policy.
3. **Measure the lease liability.** Present value of the remaining lease payments, discounted at the rate implicit in the lease if known, otherwise the incremental borrowing rate (or the risk-free rate election). Fixed payments, in-substance fixed payments, and payments that depend on an index or rate measured at commencement are in; usage-based variable payments are out and expensed as incurred.
4. **Measure the ROU asset.** The liability, plus any payments made at or before commencement, plus initial direct costs, minus lease incentives received.
5. **Account for it each month, then disclose.** For an operating lease: a single straight-line lease cost (total payments plus initial direct costs, spread over the term), with the liability reduced by the payment less the interest accretion, and the ROU asset reduced by the difference between the straight-line cost and that interest. For a finance lease: interest on the liability and straight-line amortization of the ROU asset as two separate expenses. Then the disclosures: weighted-average remaining term and discount rate, lease cost by type, cash paid, and a maturity analysis of the liability by year.

## Applying ASC 842: A Real-World Example

**The scenario.** A company signs a 36-month office lease at **$5,000 per month**, payable at the end of each month, with no initial direct costs and no incentives. The rate implicit in the lease is not readily determinable, so it uses its incremental borrowing rate of **5.0 percent**. None of the five finance-lease criteria is met, so it is an operating lease.

**The clueless accountant's approach.** Book $5,000 of rent expense each month as it is paid and stop there. The income statement looks right, and the balance sheet is missing a liability of roughly $167,000 and an asset of the same size — a fact the auditors will find in about ten minutes, along with the covenant ratios that moved when they fixed it. The slightly more sophisticated mistake: recording a liability equal to the sum of the remaining payments, $180,000, with no discounting, which overstates both sides by about $13,000 — the imputed interest that the maturity-analysis reconciliation is supposed to back out — and leaves nothing to accrete.

**The good accountant's approach.** Start with the present value. Thirty-six payments of $5,000 discounted at 5.0 percent per year — 5% ÷ 12, about 0.4167 percent per month — is a lease liability of **$166,828.51**. With no prepaid rent, initial direct costs or incentives, the ROU asset at commencement is the same **$166,828.51**. The single monthly lease cost is total payments of $180,000.00 divided by 36, or **$5,000.00** — the payment itself, because there is nothing else to spread.

Month one, then, has three moving parts. Interest accretion on the liability is $166,828.51 × (5% ÷ 12) = **$695.12**. The payment of $5,000.00 covers that interest and reduces the liability by the remaining **$4,304.88**, leaving **$162,523.63**. And the ROU asset amortizes by the straight-line cost less the interest, **$4,304.88**, to **$162,523.63** — in this simple case the same amount as the principal reduction, so the two balances decline in step and reach zero together at month 36. Add initial direct costs, prepaid rent or an incentive and they separate, which is where hand-built schedules usually go wrong.

The month-one entry for an operating lease is:

| Account | Debit | Credit |
|---|---|---|
| Operating lease cost | 5,000.00 | |
| Lease liability (principal portion of the payment) | 4,304.88 | |
| Cash | | 5,000.00 |
| Right-of-use asset (amortization) | | 4,304.88 |

The entry balances by construction. What is special here is that the liability debit and the ROU credit are the same number, which happens only because the straight-line cost equals the payment. Add initial direct costs or an incentive and the two lines differ — the entry still balances; the difference is the initial direct cost or incentive amortization running through the asset — which is exactly when a hand-built schedule tends to break.

The first three months of the schedule:

| Month | Beg. liability | Interest (5%/12) | Principal | End. liability | Beg. ROU asset | ROU amortization | End. ROU asset |
|---|---|---|---|---|---|---|---|
| 1 | 166,828.51 | 695.12 | 4,304.88 | 162,523.63 | 166,828.51 | 4,304.88 | 162,523.63 |
| 2 | 162,523.63 | 677.18 | 4,322.82 | 158,200.81 | 162,523.63 | 4,322.82 | 158,200.81 |
| 3 | 158,200.81 | 659.17 | 4,340.83 | 153,859.98 | 158,200.81 | 4,340.83 | 153,859.98 |

Two properties of this table are worth checking on any lease schedule you inherit. First, with level payments in arrears, interest falls every month because the liability falls (a rent holiday or steep escalation can push it up for a few months first); a schedule that shows level interest for the whole term is amortizing the wrong way. Second, with level payments and no initial direct costs or incentives, the ROU asset equals the liability every month; a schedule where they differ under those facts has an error. Once initial direct costs, prepaid rent, incentives or uneven payments enter, the two balances diverge by a predictable amount — prepaid or accrued rent, plus unamortized initial direct costs, less unamortized incentives (ASC 842-20-35-3) — and that reconciling difference is what an auditor traces when the two balances are disclosed.

## Tying Leases Into the Month-End Close

The schedule earns its keep in the close, not at commencement. Three ties are enough:

- **Liability rollforward:** opening balance plus interest accretion minus payments equals closing balance, and the closing balance equals the general ledger.
- **ROU rollforward:** opening balance minus amortization (plus any new leases or modifications) equals closing balance, and it equals the general ledger.
- **Expense flux:** for operating leases the cost is flat by design, so any movement in the lease cost line is a new lease, a modification or remeasurement, a termination, variable lease cost (a CPI reset or usage-based rent), an impairment — or an error — and a flux analysis that says so in one sentence is the fastest review an auditor ever does.

Add the maturity analysis — the undiscounted payments due in each of the next five years and thereafter, reconciled to the discounted liability — and the disclosure footnote writes itself from the same file.

## Mastering ASC 842: Resources and Next Steps

Rebuild the example yourself: the free three-lease version of the KDesk ASC 842 workbook (kdeskaccounting.com/templates/asc842/) takes the payment, term and rate above and produces the schedule, so you can check the $166,828.51 and the $695.12 rather than take them on faith. The full guide to the standard, including finance-lease mechanics, modifications and the disclosure set, is at kdeskaccounting.com/posts/asc-842-lease-accounting-guide/.

[Controller Academy CTA — Bill's choice, e.g. the lease-accounting or month-end-close lesson in The Controller Academy (10 CPE credits).]

*Stephen Michels has spent ten years in sales-compensation and technical accounting, including as reporting lead at CaptivateIQ, and builds Excel workbooks for controllers at KDesk Accounting.*
