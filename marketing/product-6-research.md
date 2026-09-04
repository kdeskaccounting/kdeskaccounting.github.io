# Product #6: candidate research (2026-09-04)

Method note: the session's web-search budget was exhausted, so this uses (a) Google autocomplete breadth as a relative demand proxy, calibrated against the four markets we already sell into, (b) 180 days of our own Search Console data, (c) competition and brand-fit reasoning. No paid keyword tool. Treat the revenue figures as tiers, not forecasts. Re-check with a proper volume tool before committing build time.

## Calibration: what "enough demand" looks like

Autocomplete suggestion count for the core buying phrase, in markets we already sell into:

| Known market | Suggestions | Our GSC impressions / 90d |
|---|---|---|
| fixed asset register excel | 10 | 1,202 |
| month end close checklist excel | 9 | 660 |
| asc 842 excel template | 8 | 4,716 (whole cluster) |
| saas metrics dashboard excel | 5 | ~150 |
| commission accrual excel | 0 | 1,013 (cluster; the template phrasing barely exists) |

So a score of 6+ is a real template market; 0–3 means people do not search for it as a spreadsheet, whatever the accounting topic's importance.

## Candidates

| Candidate | Core phrase | "free" variant | Accounting-grade phrase | Brand fit | Verdict |
|---|---|---|---|---|---|
| Deferred revenue schedule | 8 | 3 | waterfall 8, rollforward 6 | Excellent | **Shortlist 1** |
| Balance sheet reconciliation | 10 | 5 | prepaid expense reconciliation 10 | Excellent | **Shortlist 2** |
| Prepaid expense amortization | 7 | 5 | JE phrasing 0 | Good | **Shortlist 3 (as content + free file)** |
| 13-week cash flow forecast | 6 | 4 | "model" 10 | Moderate (treasury, not technical accounting) | Add a tab to Runway, already scheduled Nov 2 |
| Accrued expenses | 10 | — | — | Weak: queries are payroll/PTO accruals, not close accruals | Reject |
| Intercompany reconciliation | 10 | — | — | Wrong ICP (multi-entity enterprise); hard to make generic | Reject |
| Flux / variance analysis | 5 | — | — | Polluted ("flux balance analysis", cash flow) | Reject |
| Debt / effective interest | 3 | — | — | Consumer loan-amortization space owned by Vertex42, Microsoft, banks | Reject |
| ARR bridge / bookings | 3 | — | — | Fold into SaaS Metrics instead | Reject |
| Audit PBC tracker | 2 | — | — | Real pain, no search demand; make it a post | Reject as product |
| Capitalized software (ASC 350-40) | 0 | — | — | Good fit, no template demand | Reject |
| Stock comp (ASC 718) | 0 | — | — | Carta owns the space; no template demand | Reject |
| CECL / allowance | 0 | — | — | Wrong ICP (lenders) | Reject |
| Bonus accrual | 0 | — | — | No demand | Reject |

## The two mechanisms, and why the ranking is not just keyword volume

- **Deferred revenue earns new traffic.** New cluster, new queries, 4–10 weeks to rank, and it is the revenue side of the same customer contracts whose cost side we already sell (ASC 606 commissions). Strongest bundle logic of any candidate.
- **A balance sheet reconciliation pack converts traffic we already have.** The free month-end close checklist is our most-downloaded item (6 of 23 lifetime downloads) and it is the only free product with **no paid upgrade**. Every one of those downloaders hits a dead end. Fixing that needs no new traffic at all.

Indicative page-1 revenue, using the site's own measured average of ~39 page-1 impressions per commercial query, 5 % CTR, 1 % conversion:

| | Commercial queries a mature cluster would hold | Page-1 impr/mo | Sales/mo | Revenue/mo at $79 |
|---|---|---|---|---|
| Deferred revenue | 15–25 | 600–1,000 | 0.3–0.5 | $25–40 |
| Reconciliation pack | 15–25 | 600–1,000 | 0.3–0.5 | $25–40, **plus** conversion of existing close-checklist downloaders |

Neither is a $300/month product on its own. Both add roughly a third of the target, and the reconciliation pack adds it sooner because it does not wait on rankings.

## Shortlist

### 1. Deferred Revenue Schedule Workbook ($79) — build when the M2 trigger fires

Contents: Setup tab (period selector, revenue accounts); Contract Data (customer, ACV, term, billing schedule, start/end); a 60-month recognition waterfall by contract with monthly, quarterly and annual billing patterns; deferred revenue rollforward (opening + billings − recognized = closing); a contract-liability vs contract-asset split; JE Generator (invoice, recognition, unbilled) with GL presets; reconciliation that ties the waterfall to the GL and to the billing system; a short-term vs long-term deferred revenue split for the balance sheet.

Content cluster first (three posts before the build): rework the existing March post toward "deferred revenue schedule excel template"; "deferred revenue waterfall: how to build one in Excel"; "deferred revenue journal entries: billing, recognition, and the unbilled case". Then a free 6-contract version as the demand probe, which is already on the calendar for the week of September 14.

### 2. Balance Sheet Reconciliation Pack ($49) — the faster money

Contents: one workbook, one tab per recurring reconciliation with the same structure (GL balance, supporting schedule, variance, materiality flag, preparer/reviewer sign-off, aging of reconciling items): cash, AR, prepaid, fixed assets, accrued liabilities, deferred revenue, deferred commissions, lease liabilities, intercompany, equity. Plus a summary dashboard that shows which accounts tie and which do not, and a carry-forward of unresolved items.

Why it is worth doing even though the free close checklist exists: the checklist tells you *which* accounts to reconcile; this does the reconciling. It is the natural $49 upgrade for people who already downloaded the free file, and it links every other product we sell (each schedule feeds a row).

Content cluster: "balance sheet reconciliation: what ties to what" (scheduled Oct 19), "prepaid expense reconciliation", "the reconciling items your auditor will ask about".

### 3. Prepaid expense amortization — content and a free file, not a product

Demand is real (7 and 10 on the reconciliation phrasing) but the schedule is 20 minutes of work for a controller, so willingness to pay is low. Best use: a free prepaid amortization schedule as a lead magnet that feeds the reconciliation pack, plus one post. Do not build a paid product for it.

## Recommendation

Build **both** shortlist items, reconciliation pack first. It needs no new rankings, it upgrades our most-downloaded free file, and it is a smaller build (one structure repeated, no new math). Deferred revenue follows once its cluster shows the demand the September 14 probe is designed to measure.

Open question for a proper keyword tool before the build: monthly volume for "deferred revenue schedule excel template" and "balance sheet reconciliation template", and whether the reconciliation queries are dominated by *bank* reconciliation (a different, bookkeeping-level intent we should not chase).
