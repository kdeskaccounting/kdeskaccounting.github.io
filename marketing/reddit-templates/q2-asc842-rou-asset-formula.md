# Reddit template — ASC 842 ROU asset formula

**Use when:** OP is confused about what goes into the ROU asset, asks for the formula, or has a ROU/liability mismatch.

**Subs:** r/Accounting (NO link), r/Controller, r/FPandA, r/CPA, r/CFO

**Tier:** T0 for r/Accounting. T1 elsewhere when account is aged.

---

## Version A — no link

The ROU asset and lease liability are equal at commencement only if there are no initial direct costs (IDC), prepaid rent, or lease incentives. The moment any of those exist, they diverge.

The formula:

```
ROU asset = Lease liability
          + Initial direct costs (commissions, legal, etc. paid to obtain the lease)
          + Prepaid rent (any payment made before commencement)
          − Lease incentives received (tenant improvement allowances, free rent, etc.)
```

A few things that trip people up:

- **Tenant improvement allowances**: if the landlord pays you cash, it's a clear reduction to ROU. If the landlord does the improvements directly and they're real-estate-of-the-landlord, you don't book the allowance at all — there's no asset change to recognize.
- **Free rent periods**: not an incentive. Already captured in the lease liability PV calculation through the lower effective payment schedule.
- **Broker commissions**: IDC. Add to ROU.

After commencement, ROU and liability evolve separately. Operating lease: ROU is the residual that produces straight-line expense. Finance lease: ROU is depreciated straight-line independent of the liability amortization.

If your ROU and liability are still equal in month 12 of an operating lease, something's wrong with your schedule.

## Version B — with link (aged account, non-restrictive subs)

The ROU asset and lease liability are equal at commencement ONLY if there are no IDC, prepaid rent, or incentives. The moment any of those exist, they diverge.

```
ROU asset = Lease liability + IDC + Prepaid rent − Incentives received
```

What trips people up: tenant improvement allowances paid in cash reduce ROU; allowances delivered as real-estate-of-the-landlord don't. Broker commissions are IDC. Free rent isn't an incentive — it's already in the PV calculation.

After commencement, ROU and liability evolve separately. Operating: ROU is the residual that produces straight-line expense. Finance: ROU depreciates straight-line independent of the liability.

Wrote up the full calculation with worked examples and the entries that produce the right balance sheet: https://kdeskaccounting.com/posts/right-of-use-asset-calculation-asc-842/
