# Reddit template — runway / net vs gross burn

**Use when:** OP asks how to calculate runway, what burn rate to report to board, why the runway team's number doesn't match the CFO's.

**Subs:** r/FPandA, r/SaaSFinance, r/Startups, r/CFO (no r/Accounting — this is a CFO-side topic)

**Tier:** T0 by default. T1 with link OK in these subs once aged.

---

## Version A — no link

Runway is "cash on hand / monthly net burn." Three things people get wrong that break the number:

1. **Gross vs net burn.** Gross burn is total cash out. Net burn is gross minus cash collected. If you have $200K MRR and $400K monthly OPEX, your gross burn is $400K and your net burn is $200K. Boards want net. Internal financial planning needs both — gross tells you the worst-case scenario if revenue zeroes.

2. **One-time vs recurring burn.** A quarterly contract renewal ($30K SaaS bill, annual legal retainer, etc.) isn't burn — it's deferred OPEX that shows up as a spike in one month. If you average those into "monthly burn," you understate burn in 11 months and panic in 1. Better: model month-by-month, smooth the recurring spikes into accrued-vendor reserves.

3. **Cash-only vs working capital.** A startup with $1M cash and $400K AR isn't really a $1M runway company — and a startup with $1M cash and $400K AP isn't either. Real liquidity is cash + AR − AP. The board number can be cash-only; the operating number should not be.

Most useful artifact: a month-by-month bridge that shows starting cash, AR collection, payroll, AP, and ending cash. Not a single runway number. A 12-month "average runway" can hide a 6-month cliff in month 4.

## Version B — with link (aged account)

Same body as Version A, then at the end:

I wrote up the full month-by-month build with formulas (and a free 12-month Excel version) here if it's useful: https://kdeskaccounting.com/posts/how-to-calculate-startup-runway/
