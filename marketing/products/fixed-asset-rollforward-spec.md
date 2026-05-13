# Fixed Asset Rollforward Workbook — Product Spec v2

**Status:** v2 — synthesis of 5 reviewer panels (GAAP / Excel / UX / pricing / audit-trail). Ready for build.
**Author:** Claude, 2026-05-12
**Decision owner:** Stephen
**v1 → v2 changelog at the bottom of this doc.**

---

## Positioning

| Attribute | Decision |
|---|---|
| Product name | **Fixed Asset Rollforward Workbook** |
| Standard / framework | ASC 360 (book depreciation, US GAAP) |
| Audience | Controllers + finance managers at Series A–C SaaS companies; small private cos with 5–50 capitalized assets |
| Price (paid) | **$79 one-time, no launch promo, no bundle in V1** |
| Price (free) | $0 — limited to **5 assets × 36 months**, UoP method excluded, GL system-preset dropdown excluded |
| Excel compatibility | 2016, 365, Mac. **No VBA. No add-ins. Pure formulas + data validation.** No XLOOKUP / LET / LAMBDA / IFS / dynamic arrays. |
| Capacity (paid) | **50 assets × 120 months (10 yr)** schedule depth |
| Bundle | Not in V1. Revisit at 6+ SKUs or when ≥20% of buyers organically buy a 2nd template within 30 days. |
| Companion (free lead magnet) | **Month-End Close Checklist + Tie-Out Workbook** — ships alongside FA; replaces/augments the existing calculator as the primary email-capture magnet (Stephen's instinct preserved at $0, not a paid SKU) |

**Why $79 holds:** Competitive landscape has an *empty* middle. Etsy is $2-15 (toy: single-method, no JE, no recon). Eloquens / CFI FA templates are free. Sage Fixed Assets starts at $495/user/yr. There is no credible $50-100 branded competitor. $79 ladders cleanly with ASC 606 ($79) and stays below ASC 842 ($97).

**Positioning sentence (landing page lead):**
> "The only fixed asset workbook with an auto-reconciling audit tab, built by a SaaS controller — between toy Etsy templates and $5k/yr enterprise software."

**LTV math:** $79 + (0.35 × $97 ASC 842) + (0.18 × $79 ASC 606) + (0.22 × $49 Runway) ≈ **$138 gross / $131 net LTV per FA buyer.** Justifies $25-35 CAC ceiling. LinkedIn-narrow controller audience tests viable; Google Ads not (Sage bidders price out at $15-30 CPC).

---

## Out of scope (V1, said plainly on landing page)

- **MACRS / tax depreciation books.** This is book GAAP only.
- **Bonus depreciation (§168(k)) and §179 elections.** Tax book is out of scope. We provide a free-text "Tax book differs (memo)" column for cross-reference to your tax provision prep — that's it. **Not tax advice.**
- **Impairment testing (ASC 360-10-35-17 through -35).** Buyer is responsible for triggering-event analysis and recoverability testing. We provide a manual write-down path via Disposal Log if needed. Landing page makes this explicit.
- **Componentization (ASC 360-10-35-4).** Single asset = single schedule. Low SaaS-startup prevalence; V2 candidate via parent/child Asset ID convention.
- **Asset Retirement Obligations (ASC 410-20).** Out of scope.
- **Lessor accounting.** Out of scope.
- **Asset transfers between categories.** Workflow: re-key the asset. V2 candidate.
- **Asset revaluation upward.** GAAP prohibits this for PP&E under US GAAP — permanently excluded.

The product is **book depreciation under US GAAP only**. Honest scope = defensible scope.

---

## Architecture: 10 tabs

| # | Tab | Purpose | User input or calc? |
|---|---|---|---|
| 0 | **README** | Quickstart: which tabs, in what order, with a Loom walkthrough link | Static |
| 1 | Setup | Company, FY, period, conventions, GL codes, **Policy table**, **Closed Periods**, **Materiality threshold** | Input |
| 2 | Asset Register | 50 rows. Inputs + vouching anchors + computed opening balances | Mixed |
| 3 | Schedule | Period-by-period per-asset depreciation. Master long-form table for pivot-friendliness | Calc |
| 4 | JE Generator | Period-aggregated journal entries with **GL system preset dropdown** (Generic / QuickBooks / NetSuite / Sage Intacct / Xero) | Calc |
| 5 | Rollforward | Cost + accumulated depreciation by category, opening → closing | Calc |
| 6 | Disposal Log | Disposal events with evidence anchors + gain/loss | Input + calc |
| 7 | Change Log | Append-only ASC 250 change-in-estimate trail | Input |
| 8 | Reconciliation | Five-way tie-out + **Diagnostic** sub-section with cell-jump links | Calc |
| 9 | Audit Confirmation | Print-ready sample-of-25 export, formatted for auditor PBC list | Calc |
| 10 (hidden) | _Pivot | Pre-built PivotTable: Rows=Category, Cols=YYYY-MM, Vals=SUM(Depr), Filters=Method, Status | Calc |

Tab 0 is the README so the user lands there on first open. Tabs 7-9 are V2 additions per audit-trail review.

---

## Tab 0 — README

Top of workbook. The first thing a buyer sees on open.

Content:
1. **Quickstart 5 steps** in order: (a) Setup, (b) clear example rows from Register (rows 2-6 are gray-filled — those are mine, white = yours), (c) load your assets, (d) log disposals, (e) flip Reporting Period and check Reconciliation
2. **Loom video link** — 60-90 sec walkthrough (URL placeholder; create after build)
3. **What this is NOT** — copy the out-of-scope list verbatim from the landing page so buyer can't claim they didn't know
4. **Support contact** — hello@kdeskaccounting.com
5. **Version + change history** — date, version, what changed

---

## Tab 1 — Setup

**Company section:**
- Company name (string)
- Fiscal year start (date dropdown: 1/1, 4/1, 7/1, 10/1)
- Reporting period (month + year selector — drives JE Generator, Rollforward, Audit Confirmation)
- Performance materiality (currency, used for Significant Asset flag on Register)

**Conventions section:**
- Period-in-service convention dropdown: **Full Month (default)** / Mid-Month. *Half-Year and Mid-Quarter removed per GAAP review — those are MACRS tax conventions, not book conventions, and including them invites auditor pushback that the entity hasn't applied a systematic and rational book method (ASC 360-10-35-4).*
- Default depreciation method dropdown: Straight-Line / DDB / SYD / Units of Production

**GL accounts section (Named Ranges):**
- 6 asset accounts by category: Computer Equipment, Furniture & Fixtures, Leasehold Improvements, Machinery, Vehicles, Other
- Accumulated Depreciation
- Depreciation Expense
- Disposal Gain
- Disposal Loss

**Policy table (NEW — per audit-trail A3):**

| Category | Default Useful Life (months) | Default Method | Default Salvage % |
|---|---|---|---|
| Computer Equipment | 36 | Straight-Line | 0 |
| Furniture & Fixtures | 84 | Straight-Line | 0 |
| Leasehold Improvements | 60 (or lease remaining if shorter) | Straight-Line | 0 |
| Machinery | 84 | Straight-Line | 0 |
| Vehicles | 60 | Straight-Line | 10 |
| Other | 60 | Straight-Line | 0 |

The Register pulls these as defaults when a Category is selected (user overrideable). A **"Matches Policy?"** flag on Register surfaces deviations. The audit-trail reviewer explicitly called this out as the consistency test that "does the work for me."

**Closed Periods table (NEW — per audit-trail A4):**

| Period (Month End) | Closed Date | Closed By |
|---|---|---|
| 2026-01-31 | 2026-02-12 | Stephen Michels |
| ... | ... | ... |

Any Schedule row in a closed period is grayed-out + locked via conditional formatting. Edits to closed-period inputs trigger a Reconciliation red flag.

---

## Tab 2 — Asset Register (50 rows)

**Schema:**

| Col | Name | Type | Notes |
|---|---|---|---|
| A | Asset ID | string | Unique; data validation flags duplicates. Auto-suggestion formula: `="FA-"&TEXT(ROW()-1,"0000")` |
| B | Description | string | Free text |
| C | Category | dropdown | From CategoryList. Drives Policy table lookup. |
| D | Department / Cost Center | string OR dropdown | **NEW per UX #1 ask** — segments JE output by department. Defaults blank (suppressed in JE output if blank). |
| E | Vendor | string | For audit trail |
| F | Invoice # | string | **NEW per audit-trail A1** — for vouching |
| G | PO # | string | **NEW per audit-trail A1** — for vouching |
| H | CapEx Approver | string | **NEW per audit-trail A1** |
| I | Approval Date | date | **NEW per audit-trail A1** |
| J | Acquisition Date | date | Date of invoice / asset receipt |
| K | **In-Service Date** | date | **NEW per audit-trail C1 + UX** — ASC 360-10-30-1: depreciation starts when ready for intended use, not when acquired. **Depreciation start = MAX(In-Service Date, Opening Period).** |
| L | Cost | currency | > 0 |
| M | Salvage Value | currency | 0 ≤ x ≤ Cost |
| N | Useful Life (months) | integer | 1 ≤ x ≤ 600. Defaults from Policy table by Category. |
| O | Method | dropdown | SL / DDB / SYD / UoP. Defaults from Policy. |
| P | DDB Rate (override) | decimal | Auto = 2/N (years); user-overridable for 150% declining etc. Blank unless Method = DDB. |
| Q | Total Production Units | integer | Required if Method = UoP, blank otherwise |
| R | First Period Convention | dropdown | Full Month / Mid-Month. Defaults from Setup. |
| S | Opening Accum Depr | currency | For legacy assets pre-workbook period. Default 0. **Locked behind separate password (audit-trail C2).** |
| T | Opening Period | date | Earliest period this workbook covers. Pre-workbook depreciation captured in col S. |
| U | Depr Start Date | calc | `=MAX(In-Service Date, Opening Period)` |
| V | LHI Lease End Date | date | **NEW per GAAP P0 (LHI constraint)** — required if Category = Leasehold Improvements |
| W | LHI Renewal Reasonably Certain? | Y/N dropdown | Required if Category = Leasehold Improvements |
| X | Effective Useful Life (calc) | months | `=IF(Category="Leasehold Improvements", MIN(N, months-to-lease-end-incl-renewal), N)` |
| Y | Revised Useful Life | months | **NEW per GAAP P1 (ASC 250 change-in-estimate)** — blank unless life revised |
| Z | Revision Effective Period | date | Period from which revised life applies; prospective only |
| AA | Tax Book Differs Memo | string | **NEW per UX Q3** — free text for cross-ref to tax provision prep (e.g., "Bonus dep §168(k) on tax side"). NOT used in any calculation. |
| AB | Net Book Value | calc | Cost − running depr from Schedule − disposal adj |
| AC | Status | calc | Active / Disposed / Fully Depreciated / **Voided** (per audit-trail C3 soft-delete) |
| AD | Significant Asset? | calc | `=IF(NBV > Setup!Materiality, "SIGNIFICANT", "")` |
| AE | Matches Policy? | calc | Y if Useful Life + Method match Policy table for Category; N otherwise. **Drives consistency test for auditor.** |
| AF | Notes | string | Free text for audit trail |

**Data validation (Excel-formula-correct, per Excel reviewer):**

| Cell | Rule (Data Validation → Custom) |
|---|---|
| Asset ID | `=AND(LEN(A2)>0, COUNTIF($A$2:$A$51,A2)=1)` |
| Cost | `=L2>0` |
| Salvage | `=AND(M2>=0, M2<=L2)` |
| Useful Life | `=AND(N2>=1, N2<=600, N2=INT(N2))` |
| Acquisition Date | `=AND(ISNUMBER(J2), J2<=Setup!ReportingPeriodEnd)` |
| In-Service Date | `=AND(ISNUMBER(K2), K2>=J2)` (in-service ≥ acquisition) |
| Category / Method / Convention | List source = named range |

---

## Tab 3 — Schedule

Master table layout. 50 assets × 120 months = 6,000 row capacity (NOT 12,000 from v1; reduced per UX + Pricing converging on 120-month depth). One row per (Asset ID, Period). Sorted by Asset ID then Period Index — sort order is mandatory for Beginning NBV formula.

**Columns:**

| Col | Name | Formula |
|---|---|---|
| A | Asset ID | FK to Register, repeated per period |
| B | Period (Month End) | `=EOMONTH(Depr Start Date, Period Index − 1)` |
| C | Period Index | 1-based from Depr Start Date |
| D | Beginning NBV | **Option B running-sum** (Excel review): `=IF(C2=1, INDEX(Register.L,$K2)-INDEX(Register.S,$K2), G1*(A2=A1) + (INDEX(Register.L,$K2)-INDEX(Register.S,$K2))*(A2<>A1))` where K2 is a helper col with `MATCH(A2, Register.A, 0)` precomputed once |
| E | Method (locked) | `=INDEX(Register.O, $K2)` |
| F | Depr This Period (raw) | See per-method formulas below |
| G | Disposal Adjustment | If asset disposed this period, prorate or zero per Disposal Log + convention |
| H | Depr This Period (final) | `=MIN(MAX(0, D2-INDEX(Register.M,$K2)), F2 + G2)` — final salvage-floor wrapper |
| I | Accumulated Depreciation | Running sum since asset start |
| J | Ending NBV | `=D2 − H2` |
| K | Asset Match Idx | Helper: `=MATCH(A2, Register.A, 0)` (named `Sched_AssetIdx`) — precomputed once to avoid 5× MATCH per row |
| L | Category Period Key | `=INDEX(Register.C,$K2)&"|"&TEXT(B2,"YYYY-MM")` — drives SUMIFS rollups |
| M | JE Reference | `=A2&"-"&TEXT(B2,"YYYY-MM")` — bidirectional drill from JE Generator back to source row (audit-trail B2) |
| N | In Closed Period? | `=IF(COUNTIFS(Setup!ClosedPeriods, "<="&B2)>0, "LOCKED", "")` — for conditional formatting |

### Depreciation method formulas (corrected per GAAP + Excel reviews)

**Straight-Line:**
```
F2 = (Cost - Salvage) / EffectiveUsefulLife        # using col X (LHI-corrected life)
H2 = MIN((Cost-Salvage)/Life, MAX(0, D2-Salvage)) # final wrapper, prevents last-month over-depreciation
```

**Double-Declining Balance with one-time SL switch:**

Auto-switch logic: compute a per-asset Switch Period `t*` = smallest t where `(NBV_t − Salvage) / (Life − t + 1) ≥ NBV_t × MonthlyRate`. From t* onward, use SL on remaining basis. Implemented as a helper column on Schedule that flags whether asset has switched, then the depr formula picks the right branch:

```
DDB_amt   = D2 × Rate / 12
SL_amt    = IF(Life - C2 + 1 > 0, (D2 − Salvage) / (Life − C2 + 1), 0)
F2_raw    = IF(SwitchFlag = "SL", SL_amt, MAX(DDB_amt, SL_amt))
H2        = MIN(MAX(0, D2 − Salvage), F2_raw)   # salvage floor as outer wrapper (P0 GAAP fix)
```

SwitchFlag: once SL_amt > DDB_amt in any period, lock SL for all subsequent periods (the "one-time switch" requirement from GAAP review). Implemented via `=IF(OR(prior row SwitchFlag="SL", SL_amt>DDB_amt), "SL", "DDB")`.

**Sum-of-Years-Digits (mid-year acquisition blending):**

SYD year anchors from In-Service Date (NOT fiscal year), per GAAP review. Closed form:

```
LifeYrs    = Life / 12
SumDigits  = LifeYrs × (LifeYrs + 1) / 2
YearK      = INT((C2 − 1) / 12) + 1
Frac1      = (LifeYrs − YearK + 1) / SumDigits
Frac2      = (LifeYrs − YearK)     / SumDigits     # next year
MonthInYr  = MOD(C2 − 1, 12) + 1
F2_raw     = ((Cost − Salvage) × (Frac1 × (13 − MonthInYr) + Frac2 × (MonthInYr − 1)) / 12)
H2         = MIN(MAX(0, D2 − Salvage), F2_raw)
```

**Units of Production:**

UoP requires `Units Produced This Month` column on Schedule (input cells, default 0). Free version excludes UoP entirely (no Units Produced column, no UoP method in Register dropdown).

```
PerUnitDepr = (Cost − Salvage) / TotalProductionUnits     # from Register col Q
F2_raw      = PerUnitDepr × UnitsProducedThisMonth
H2          = MIN(MAX(0, D2 − Salvage), F2_raw)
```

### Conventions

- **Full Month (default):** First full month = month of `Depr Start Date`. Asset placed in service 2026-03-15 starts depreciating in March (full month of expense).
- **Mid-Month:** Asset placed in service 2026-03-15 → 0.5 months in March (15/30 prorated), then full from April. Disposal mid-month also prorated.

Half-Year and Mid-Quarter conventions **dropped** per GAAP review (they're MACRS tax conventions, not GAAP book conventions).

### Disposal proration formula (Excel review P0)

```
DispDate  = IFERROR(INDEX(Disposal.DispDate, MATCH(A2, Disposal.AssetID, 0)), 0)
G2 (Disposal Adjustment) =
  IF(DispDate = 0, 0,
    IF(EOMONTH(DispDate, 0) <> B2, 0,
      IF(D2 - Salvage <= 0, -F2_raw,     # already fully depreciated, zero out
        # Prorate this month only
        F2_raw * (-1 + IF(Convention = "Mid-Month", (DAY(DispDate) − 0.5) / DAY(B2), 1)))))
```

---

## Tab 4 — JE Generator

For the selected Reporting Period, generate journal entries with **GL system preset dropdown** (Generic / QuickBooks / NetSuite / Sage Intacct / Xero). Selector on Setup; column headers and required fields adjust per system.

| Entry Type | Trigger | Debit | Credit |
|---|---|---|---|
| Monthly Depreciation | Schedule rows where Period = Reporting Period AND Status = Active | Depreciation Expense (by Category, by Department) | Accumulated Depreciation |
| Asset Capitalization | Register rows where In-Service Date in Reporting Period | Asset (by Category) | Cash / AP |
| Disposal — gain | Disposal Log Date in Reporting Period AND Proceeds > NBV | Cash, Accum Depr | Asset, Gain on Disposal |
| Disposal — loss | Disposal Log Date in Reporting Period AND Proceeds < NBV | Cash, Accum Depr, Loss on Disposal | Asset |
| Disposal — at NBV | Proceeds = NBV (rare) | Cash, Accum Depr | Asset |
| Disposal — trade-in (commercial substance Y) | Disposal Type = Trade-in AND Commercial Substance = Y | Cash, Accum Depr, New Asset @ FV | Asset, Gain/Loss |
| Disposal — trade-in (commercial substance N) | Disposal Type = Trade-in AND Commercial Substance = N | New Asset @ Carryover Basis, Accum Depr | Asset, (limited Loss only — never Gain per ASC 845-10-30-3) |

**Output columns (Generic):** Date / Account / Description / Debit / Credit / **Reference (= Schedule.JE Reference = AssetID-YYYY-MM)** / Department / Memo

**Per-system column overrides:**
- NetSuite: add `Subsidiary`, `Class`, `Location`
- QuickBooks: add `Class`
- Sage Intacct: add `Department`, `Location`
- Xero: add `Tracking Category 1`, `Tracking Category 2`

Bidirectional drill: JE Reference column on Schedule (col M) mirrors JE Generator output Reference column. Auditor drilling from GL → Workbook can click reference → find source row.

---

## Tab 5 — Rollforward

Standard 3×3 rollforward (Cost, Accum Depr, NBV) × 6 categories + total. Period range selectable: month / quarter / fiscal-YTD / full-year.

|  | Computer Eq | Furniture | LHI | Machinery | Vehicles | Other | TOTAL |
|---|---|---|---|---|---|---|---|
| **Cost** Opening | SUMIFS | ... | ... | ... | ... | ... | SUM |
| Additions | SUMIFS | ... | ... | ... | ... | ... | SUM |
| Disposals | -SUMIFS | ... | ... | ... | ... | ... | SUM |
| Closing | =Opening+Additions+Disposals | ... | ... | ... | ... | ... | SUM |
| **Accum Depr** Opening | SUMIFS | ... | ... | ... | ... | ... | SUM |
| Depr Expense | SUMIFS | ... | ... | ... | ... | ... | SUM |
| Disposals | -SUMIFS | ... | ... | ... | ... | ... | SUM |
| Closing | =Opening+Expense+Disposals | ... | ... | ... | ... | ... | SUM |
| **NBV** | =Cost Closing − Accum Closing | ... | ... | ... | ... | ... | SUM |

Performance optimization: use Schedule.CategoryPeriodKey (col L) as the SUMIFS key — single criterion vs nested.

---

## Tab 6 — Disposal Log

| Col | Name | Type | Notes |
|---|---|---|---|
| A | Asset ID | dropdown from Register | Required |
| B | Disposal Date | date | Required, ≥ In-Service Date |
| C | Disposal Type | dropdown | Sale / Retirement / Trade-in / Write-off / Theft-loss |
| D | **Commercial Substance? (Y/N)** | dropdown | **NEW per GAAP P0** — required only if Type = Trade-in. Drives ASC 845-10-30 treatment. |
| E | Proceeds | currency | 0 for retirement/write-off |
| F | **Authorization (approver name)** | string | **NEW per audit-trail A5** |
| G | **Authorization Date** | date | **NEW per audit-trail A5** |
| H | **Evidence Type** | dropdown | Bill of Sale / Scrap Receipt / Write-off Memo / Insurance Claim / Police Report / Other |
| I | **Evidence Reference** | string | **NEW per audit-trail A5** — BoS#, receipt#, memo#, etc. |
| J | Counterparty | string | **NEW per audit-trail A5** |
| K | Disposal Cost | calc | Lookup from Register |
| L | Accum Depr at Disposal | calc | Lookup from Schedule at Disposal Date |
| M | NBV at Disposal | calc | K − L |
| N | Gain / (Loss) | calc | E − M |
| O | Notes | string | Free text |

---

## Tab 7 — Change Log (NEW)

Append-only log per ASC 250-10-45-17. Required for any change to a "history-sensitive" field on Register: Useful Life (N), Method (O), Opening Accum Depr (S), Category (C).

| Col | Name | Type |
|---|---|---|
| A | Asset ID | required, dropdown from Register |
| B | Field Changed | dropdown: Useful Life / Method / Opening Accum Depr / Category |
| C | Prior Value | string/number |
| D | New Value | string/number |
| E | Effective Period | date (prospective application per ASC 250) |
| F | Reason | string, required, min 20 chars |
| G | Approver | string, required |
| H | Timestamp | auto (or required manual entry) |

Reconciliation surfaces any Register edit on history-sensitive fields that lacks a Change Log entry. Opening Accum Depr (col S) on Register is **password-locked separately** from formula cells — only unlockable with a different password documented in the README.

---

## Tab 8 — Reconciliation + Diagnostic

**5-way tie-out** (each must show $0 variance):

| Check | Formula | What it proves |
|---|---|---|
| Schedule Depr Total = JE Depr Total | SUMIF(Schedule.H where Period in Reporting Period) = JE.Debits Depreciation Expense | JE aggregation matches detail |
| Schedule Accum Total = Rollforward Closing Accum | SUMIF(Schedule.I at Reporting Period end) = Rollforward.Accum Closing TOTAL | Rollforward ties to detail |
| Register Cost = Rollforward Cost Closing | SUMIF(Register.L where Status≠Voided AND not Disposed) = Rollforward.Cost Closing TOTAL | Cost balance ties |
| Register Disposal Adjustment = Disposal Log | SUMIF(Disposal.NBV) net change in Rollforward | Disposals net properly |
| NBV Math | Cost Closing − Accum Closing − Rollforward.NBV TOTAL | Final tie |

**Conditional formatting (Excel review):**
- Green `#C6EFCE` "TIES": `=ABS(variance) < 0.01`
- Yellow `#FFEB9C` "Rounding": `=AND(ABS(variance) >= 0.01, ABS(variance) <= 1)`
- Red `#FFC7CE` "VARIANCE": `=ABS(variance) > 1`

**Diagnostic sub-section (NEW per UX):**

When any check shows red, ranked likely causes appear below with cell-jump hyperlinks:

1. Disposal logged but Asset Register Status not updated → jump to Register row
2. Asset acquired after Reporting Period close → jump to Register acquisition date
3. Opening Accum Depr entered without Opening Period → jump to Register row
4. Useful Life or Method revised but no Change Log entry → jump to Change Log
5. Edit detected in a Closed Period → jump to offending row
6. New asset Category doesn't match a defined Policy row → jump to Setup Policy table

Each entry: link → cell, plus 1-sentence remediation. Cuts variance investigation from 90 minutes to 10.

---

## Tab 9 — Audit Confirmation Export (NEW)

Print-ready PBC format. User enters sample size or pastes auditor's list of Asset IDs. Tab outputs:

- Company header with reporting period
- Selected assets in table: Asset ID, Description, Category, In-Service Date, Cost, Useful Life, Method, Accum Depr through reporting period, NBV
- Signature lines: Prepared By / Date, Reviewed By / Date
- Statement of management's representation re: completeness, accuracy, supporting documentation
- Footer with auditor reference field

Saves 2 hours per audit per UX review.

---

## Tab 10 — _Pivot (hidden)

Pre-built PivotTable. Rows = Category. Columns = YYYY-MM. Values = SUM(Depr This Period Final). Filters = Method, Status. Refresh on demand. Lets buyer slice depreciation by any dimension without writing SUMIFS.

---

## Edge cases V1 must handle

1. **Asset fully depreciated before disposal.** Depr stops at NBV = Salvage. Disposal at Salvage → 0 gain/loss.
2. **Mid-period disposal.** Partial-month depr per convention. Disposal Log entry; Schedule G column prorates.
3. **Asset with opening accum depr (legacy assets).** Register col S. Schedule respects opening; Change Log required if user later revises this field.
4. **Asset acquired AND disposed same period.** Register col K + Disposal Log col B both in period. Net depr = acquisition-period proration − disposal-period proration. Edge but handled.
5. **DDB convergence.** One-time switch to SL when SL-on-remaining ≥ DDB. Locked SL once switched.
6. **Leasehold Improvements depreciation.** Effective Useful Life = MIN(input life, months to lease end including reasonably certain renewals). LHI-specific columns V/W required.
7. **Change-in-estimate (ASC 250).** Revised life applies prospectively from Revision Effective Period. Change Log entry required.
8. **Trade-in transactions.** Commercial Substance Y/N flag drives ASC 845 treatment.
9. **Negative salvage / salvage > cost.** Data validation blocks both.
10. **Asset voided (soft-delete).** Status = "Voided" excludes from JE, Rollforward, Reconciliation. Row preserved for audit.
11. **Edits in closed period.** Conditional formatting grays out + Reconciliation flags. User must explicitly unlock period in Setup to edit (with audit trail).

---

## What buyers SEE that earns "audit-ready" (marketing bullets per audit-trail B)

- **Five-way reconciliation on a single tab.** Schedule = JE = Rollforward = Register = GL. Auditor's first 30 minutes done.
- **Bidirectional JE Reference.** Drill from posted GL entry back to Schedule source row.
- **ASC 250 Change Log.** Pre-built useful-life-revision trail.
- **Policy table + deviation flag.** Pre-built consistency test for auditor sampling.
- **Significant Asset flag.** Performance materiality scoping built in.
- **Audit Confirmation Export tab.** Saves 2 hours per audit. Print-ready PBC format.
- **Vouching anchors on every asset.** Invoice #, PO #, CapEx approver, approval date.
- **Closed Periods table.** Prevents silent prior-period edits.

These are the bullets that justify $79 vs $15 Etsy templates and $495/yr Sage. Concrete features tied to auditor pain.

---

## Function library (Excel review P0)

Maximally compatible across Excel 2016 / 365 / Mac. Restrict to:

**ALLOWED:** `IF`, `IFERROR`, `IFS` (avoid — 2019+ only), `AND`, `OR`, `NOT`, `INDEX`, `MATCH`, `SUMIFS`, `COUNTIFS`, `EOMONTH`, `EDATE`, `MAX`, `MIN`, `MOD`, `INT`, `ROUND`, `SUMPRODUCT`, `TEXT`, `DATE`, `YEAR`, `MONTH`, `DAY`, `LEN`, `COUNTIF`, `ISNUMBER`, `ROW`

**FORBIDDEN:** `XLOOKUP`, `LET`, `LAMBDA`, `IFS`, dynamic array spills (`UNIQUE`, `FILTER`, `SORT`), `OFFSET` (volatile), `INDIRECT` (volatile).

---

## Named ranges (32 total)

`Co_Name, FY_Start, ReportingPeriodEnd, DefaultConvention, DefaultMethod, Materiality, GL_ComputerEq, GL_Furniture, GL_LHI, GL_Machinery, GL_Vehicles, GL_Other, GL_AccumDepr, GL_DeprExpense, GL_DispGain, GL_DispLoss, CategoryList, MethodList, ConventionList, DisposalTypeList, EvidenceTypeList, Policy_Life, Policy_Method, Policy_Salvage, ClosedPeriods, Register_AssetID, Register_Cost, Register_Salvage, Register_Life, Register_Method, Register_Category, Register_InServiceDate, Sched_AssetID, Sched_Period, Sched_Depr, Sched_AccumDepr, Sched_CatKey, Disp_AssetID, Disp_Date, Disp_Proceeds`

---

## Sheet protection map

Each tab protected with same password (documented in delivery email). Unlocked cells per tab:

| Tab | Unlocked cells |
|---|---|
| README | None (static) |
| Setup | Company/FY/period (4 cells), conventions (2), GL codes (10), Policy table (24 cells = 6 categories × 4 cols), Closed Periods table (3 cols × ~36 rows), Materiality (1) |
| Asset Register | Cols A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, V, W, Y, Z, AA, AF (all input cols; calc cols locked). **Opening Accum Depr (col S) password-locked separately** |
| Schedule | Only `Units Produced` cells (UoP method only) |
| JE Generator | Fully locked output |
| Rollforward | Fully locked |
| Disposal Log | A, B, C, D, E, F, G, H, I, J, O (skip calc cols K, L, M, N) |
| Change Log | A, B, C, D, E, F, G, H (all input — append-only via data validation requiring all fields) |
| Reconciliation | Fully locked |
| Audit Confirmation | Sample-input cells + signature cells |
| _Pivot | Hidden; refresh-only |

---

## Deliverables

- `kdesk-fixed-asset-rollforward-v1.xlsx` — paid version (50 assets × 120 months, all 4 methods, all 5 GL system presets, all 11 tabs)
- `kdesk-fixed-asset-rollforward-free-v1.xlsx` — free version (5 assets × 36 months, no UoP, JE Generator Generic only, no system-preset dropdown)
- Built deterministically via `scripts/build_fixed_asset_workbook.py` using `openpyxl`
- Quick-start guide: README tab + 1-page PDF + Loom walkthrough link
- Worked example pre-populated (5 assets across categories, gray-filled rows so user knows to clear)

---

## Decision matrix — cross-reviewer conflicts resolved

| Question | GAAP | Excel | UX | Pricing | Audit | **Decision** |
|---|---|---|---|---|---|---|
| Schedule depth | — | 180 | 120 | — | — | **120** (target audience driven) |
| Free version size | — | — | 10×60 | 5×36 | — | **5×36 + UoP excluded + dropdown excluded** (compound pressure: vol + features) |
| Half-Year convention | drop for book | — | rare include | — | — | **Drop** (GAAP audit-defensible) |
| UoP method | — | — | skip | — | — | **Keep in paid only** (mfg/vehicles buyers will use; SaaS skips) |
| Bonus dep flag | skip | — | yes as memo | — | — | **Yes as free-text memo column (col AA)** — not used in calc |
| Componentization | V2 | — | skip V1 | — | — | **Skip V1** |
| JE output format | — | dropdown preset | dropdown preset | — | — | **Dropdown preset** (5 systems) |
| Price | — | — | $79 | $79 | — | **$79 flat** |
| Launch promo | — | — | — | no | — | **No** |
| Bundle | — | — | — | revisit 6+ SKUs | — | **No V1 bundle** |
| Month-end-close product | — | — | — | free lead magnet | — | **Free MEC checklist as lead magnet alongside FA launch** |

---

## v1 → v2 changelog

**Added (P0 / P1 must-haves):**
- README as tab 0
- Policy table on Setup with deviation flag on Register (audit-trail A3)
- Closed Periods table on Setup with period-freeze CF (audit-trail A4)
- Performance Materiality + Significant Asset flag (audit-trail B5)
- **In-Service Date as separate column** on Register (ASC 360-10-30-1 — UX + audit-trail C1)
- Department / Cost Center column (UX #1 gap)
- Vouching anchors: Invoice #, PO #, CapEx Approver, Approval Date (audit-trail A1)
- LHI Lease End Date + Renewal Reasonably Certain + Effective Useful Life calc (GAAP P0 — LHI constraint)
- Revised Useful Life + Revision Effective Period columns (GAAP P1 — ASC 250 change-in-estimate)
- Tax Book Differs Memo free-text column (UX Q3 — cross-ref to tax prep, not used in calc)
- Change Log tab (GAAP P1 + audit-trail A2 + C2)
- Audit Confirmation Export tab (audit-trail B + UX)
- Diagnostic sub-section on Reconciliation (UX)
- Bidirectional JE Reference column on Schedule + JE Generator (audit-trail B2)
- _Pivot tab pre-built (Excel review P1)
- Status value "Voided" for soft-delete (audit-trail C3)
- Commercial Substance Y/N flag on Disposal Log for trade-ins (GAAP P0 — ASC 845)
- Authorization / Evidence Type / Evidence Reference / Counterparty columns on Disposal Log (audit-trail A5)
- Three-tier conditional formatting on Reconciliation (green/yellow/red, Excel review)
- 32 named ranges enumerated (Excel review)
- Function library restricted to 2016-Mac compatible set (Excel review P0)
- Beginning NBV running-sum formula (Excel review P0)
- DDB switch logic: one-time switch period + outer salvage-floor wrapper (GAAP + Excel P0)
- SL salvage-floor outer wrapper (Excel review P0)
- SYD year-anchored to in-service date with mid-year blending closed form (GAAP + Excel)
- Disposal proration formula with three sub-cases (Excel review P0)
- JE Generator system-preset dropdown (Excel + UX): Generic / QB / NetSuite / Sage / Xero

**Removed:**
- Half-Year and Mid-Quarter conventions (GAAP — not book-defensible)
- 240-month → 120-month schedule depth (UX + Pricing converge)
- Componentization (GAAP + UX agree: V2)

**Unchanged:**
- $79 price, no launch promo, no bundle V1 (all reviewers OK)
- 8 → 11 tabs (added README, Change Log, Audit Confirmation, hidden _Pivot)
- Out-of-scope list (MACRS, §179, impairment, ARO, lessor, revaluation) — explicit in landing page copy

**Strategic addition (per Pricing review):**
- Ship a separate **free** Month-End Close Checklist + Tie-Out Workbook as lead magnet alongside FA launch. Honors Stephen's instinct without diluting the paid lane.
