# KDesk roadmap: $0 → $300/month (adopted 2026-09-03)

Living document. Claude updates the status table every Monday from the automated pulls; the rest changes only by decision (logged in `decisions/decisions.jsonl`). Source plan: repo decision 47.

## Status (updated Mondays)

| Metric | Baseline 2026-09-01 | Latest | Next trigger |
|---|---|---|---|
| Organic search sessions / day (7-day avg, GA4) | 8 | 8 | 12 → Reddit link drops + comparison post |
| Free downloads, calendar month (Gumroad) | 9 | 2 (Sept MTD, 09-03) | 15 in a month with 0 sales → pricing test #1 |
| Email list, active (MailerLite) | 16 | 16 | — |
| Full-price sales, lifetime | 0 | 0 | 1 → M1 (paid test, testimonial, product #6 probe) |
| Trailing-30-day revenue | $0 | $0 | $300 two months running → M3 |
| Target queries on page 1 (of ~25) | 0 | 0 | 5 by 2026-10-31 · 12 by 2026-12-31 |
| Referring domains | ~0 | ~0 | 10 by 2026-12-01 |

## Decisions that shape this plan (2026-09-03)

- Paid spend unlocks only **after the first full-price sale**: $100/mo cap, then $250/mo at M3.
- **Pricing tests within ±30 %** at the triggers below, each logged T2 with a 48-hour veto.
- Stephen's time: weekly LinkedIn paste **+ a Reddit account (~30 min/week) + one 60–90 s video per month** + a 5-minute weekly OK on outreach drafts.
- Rank the existing five products first; product #6 only when a content cluster proves demand. Candidates researched 2026-09-04: reconciliation pack (converts existing traffic) then deferred revenue (earns new traffic).

## The math to $300/month

Average order ≈ $80 (mix of $49–97 workbooks, occasional $249 bundle) → **$300/mo ≈ 4 sales/mo**. Two feeders:

- **Product-page visitors → purchase at 1–1.5 %.** Product pages take ~60 % of GSC clicks. 4 sales needs ~300 product-page visits/mo ≈ **15–20 organic sessions/day** (2–2.5× today).
- **Free downloads → paid at 3–5 % within 90 days** (nurture live since 09-02). 40 downloads/mo ≈ 1.5–2 sales.

| Stage | Organic/day | Downloads/mo | List | Sales/mo | Revenue/mo | Target date |
|---|---|---|---|---|---|---|
| Now | 8 | 9 | 16 | 0 | $0 | — |
| M1 first sale | 12 | 15 | 40 | 1 | ~$80 | Oct–Nov 2026 |
| M2 repeatable | 20 | 30 | 90 | 2–3 | ~$180 | Dec 2026–Jan 2027 |
| M3 target | 30 | 45 | 160 | 4+ | **$300+** | Feb–Mar 2027 |

**Page-1 ceiling on today's query set** (GSC 90d, modeled 2026-09-03 with `scripts/model_page1_revenue.py`): 670 queries → ~6,300 commercial + ~17,000 informational page-1 impressions/mo after scaling deep positions up (×3 for pos 11–20, ×6 for 21–30, ×10 beyond). At our measured CTR (~5–6 % on commercial queries at pos 8–12), 1 % of clicks converting (informational readers: 15 % reach a product page first) and $80 AOV → **~$350/mo (~$530 counting the long-tail GSC anonymizes)**; top-3 CTR → ~$1,060. The 44 commercial queries at pos 8–30 today alone are worth ~$50–150/mo. Page-1 on existing pages is necessary but only reaches $300 at the upper end; cluster expansion (new query coverage) and the free-download nurture (conversion above 1 % of clicks) supply the rest. Re-run quarterly.

SEO changes take 4–10 weeks to show (Aug traffic was 3× May after the May-31 pass). If a stage is more than 6 weeks late, the guardrails fire instead of waiting.

## How we rank higher on Google

Google ranks a page on (1) how exactly it matches the query, (2) how deep the site's coverage of the topic is, (3) how many other sites link to it. Our data shows 1 and 2 working and 3 missing: the fixed-asset page sits at position 11 for the buying query whose wording it matched ("fixed asset register with depreciation excel template") and at 70 for the one it didn't ("depreciation schedule template"); the lease cluster moved from position 35 (May) to 28 (August) after hub-and-spoke linking plus the pillar; the site has ~0 referring domains, so head terms held by Vertex42 / Smartsheet / LeaseQuery stay out of scope until links exist.

1. **Query-page fit.** One page per buying query; the exact phrase in title, H1, first sentence, one H2, image alt; never two of our pages competing for one phrase. Tracked in `marketing/seo-tracking/target-queries.json`; positions logged weekly to `target-query-positions.jsonl` by the Monday pull.
2. **Cluster depth + internal links** for all five products, the lease pattern repeated: product page (hub) + pillar + 5–8 spokes; every spoke links hub, pillar and two siblings with descriptive anchors.
3. **Links: 10–15 referring domains in 90 days.** (a) Free calculator and free workbooks listed on Excel-template roundups, "free accounting templates" posts and accounting-blog resource pages (targets in `marketing/outreach/targets.md`; Claude drafts, Stephen approves a weekly batch of ~5, sent from santiagokdesk). (b) Free quote platforms (Featured, Help a B2B Writer, Qwoted) using Stephen's sales-comp accounting background; Claude drafts answers, Stephen approves. (c) Co-branded template or guest post for the two accounting firms among downloaders. (d) Link-magnet pages pitched as tools. LinkedIn and Reddit bring traffic and branded searches, not links.
4. **Click-through.** Meta descriptions with the number or the mistake; FAQ rich results. Higher CTR at a given position pushes the position.
5. **Freshness + AI citations.** `lastmod` on every refresh, quarterly refresh of the top 10 pages, definitions and worked numbers near the top (GA4 "AI Assistant" channel already refers visitors).

**Rank milestones:** 5 target queries on page 1 by 2026-10-31 · 12 by 2026-12-31 · every product page on page 1 for its own "[topic] excel template" query by 2027-02-28 · 10 referring domains by 2026-12-01. Head terms reviewed only after 15 referring domains.

## Milestone ladder (trigger → what happens → owner)

Metrics are read every Monday by the automated pull; a trigger fires when the 7-day average (traffic) or calendar-month count (downloads/sales) crosses the line. Claude executes the row and tells Stephen only what needs his click.

**M0 — now until the first full-price sale.** The always-on backlog runs every week regardless. Sub-triggers:
- **Downloads ≥ 15 in a calendar month with 0 sales** → pricing test #1 (T2): 30-day price on the most-downloaded product's paid version (ASC 842 $97 → $69) + "Free vs Full" comparison table on every product page.
- **Organic ≥ 12/day** → Reddit link drops begin (1/wk from the aged account); comparison post "LeaseQuery / NetLease alternative for under 20 leases" (T2).
- **A business-domain download** → Claude drafts a 4-line personal email; Stephen sends from santiagokdesk (the CAE handoff).
- **60 days with ≥ 25 new downloads and 0 sales (≈ 2026-11-01)** → guardrail: tighten free caps (ASC 842 free 3 → 2 leases, schedule 36 → 24 months) and pricing test #2 on a second product. Stephen decision.

**M1 — first full-price sale.**
- Paid test: $100/mo cap, Google Ads exact-match on that product's buying queries, landing on the product page; 30 days, keep only if cost per sale < $60.
- Buyer feedback request (Claude drafts, Stephen sends) → first testimonial on the product page and listing.
- Gumroad Workflows self-publish once the $100 earnings gate clears.
- Product #6 discovery cluster: rework the March deferred-revenue post + two new posts + a free deferred-revenue schedule as an email-gated lead magnet.

**M2 — 3 sales in any 30-day window, or organic ≥ 20/day.**
- Build product #6. Research (2026-09-04, `marketing/product-6-research.md`) ranks it: **Balance Sheet Reconciliation Pack $49 first** (converts the free close checklist's downloaders, our most-downloaded item, which today has no paid upgrade; needs no new rankings), then the **Deferred Revenue Schedule Workbook $79** once its cluster shows ≥ 300 impressions/mo or ≥ 15 lead-magnet downloads/mo. Add each to the bundle (→ $299).
- Raise the best-converting workbook +20 % (T2); second Ads product.
- Second monthly video slot; Shorts cross-posted natively to LinkedIn.
- Gumroad affiliate program (20 %) offered to the accounting-firm downloaders.

**M3 — trailing-30-day revenue ≥ $300 for two consecutive months.**
- Two articles/week, ads cap $250/mo, YouTube long-form series from the article backlog, weekly CAE warm-lead routine. Re-plan.

## 12-week calendar (Sep 7 → Nov 29, 2026)

Every week: Monday scoreboard (Claude) · one fact-checked article (Claude) · Thursday LinkedIn paste (Stephen) · two Reddit comment drafts (Claude) → pastes (Stephen) · downloaders synced + nurture (automated) · one product/site improvement (Claude) · outreach batch of ~5 (Claude drafts, Stephen OKs).

| Week of | Article (cluster) | Product / site item (Claude) | Distribution | Stephen (≤ 30 min) |
|---|---|---|---|---|
| Sep 7 | Commission clawbacks & reversals (commission) | "Free vs Full" comparison table on product pages; target-query tracker; outreach batch 1 | LinkedIn #17 | Paste #17; create Reddit account (`marketing/reddit-templates/00-account-setup.md`) |
| Sep 14 | Deferred revenue rework toward "deferred revenue schedule excel template" | Free deferred-revenue schedule .xlsx as gated download (product #6 demand probe) | LinkedIn #18 | Paste #18; record video #1 ("the deferred rent gap") |
| Sep 21 | Mid-year comp plan changes: accounting + controls (commission) | Unify the 10 Gumroad listing descriptions | LinkedIn #19; video #1 on LinkedIn + YouTube | Paste #19; 2 Reddit comments |
| Sep 28 | Fixed asset register template: the columns auditors expect (fixed asset) | Internal-link audit across all posts | LinkedIn #20; first Reddit link drop if the account is 3 weeks old | Paste #20; 2 Reddit comments |
| Oct 5 | Deferred commission audit PBC checklist (commission) | "What happens after you pay" block + JE output screenshot on product pages | LinkedIn #21 | Paste #21 |
| Oct 12 | LeaseQuery / NetLease alternative under 20 leases (lease, T2) | Gumroad tags / Discover category audit | LinkedIn #22 | Paste #22; veto window; record video #2 |
| Oct 19 | Balance sheet reconciliation template (close) | Month-end-close page: reconciliation-template angle; free file refresh | LinkedIn #23; video #2 | Paste #23; 2 Reddit comments |
| Oct 26 | Lease modification vs remeasurement journal entries (lease) | Pillar refresh with links to the new lease posts | LinkedIn #24 | Paste #24 |
| Nov 2 | 13-week cash flow forecast template (runway) | Runway page retitle for "13-week cash flow"; free file gets a 13-week tab | LinkedIn #25 | Paste #25; guardrail review if still 0 sales |
| Nov 9 | Net revenue retention: formula, worked example, Excel (SaaS metrics) | SaaS Metrics page title alignment; dashboard GIF | LinkedIn #26; record video #3 | Paste #26 |
| Nov 16 | Deferred revenue waterfall journal entries (product #6 cluster) | Deferred-revenue probe read-out → build / no-build memo | LinkedIn #27; video #3 | Paste #27 |
| Nov 23 | Year-end close checklist for SaaS controllers (close, seasonal) | Q4 CTA on the close page; one holiday email to the list | LinkedIn #28 | Paste #28 |

Article order can be swapped by Monday data. Every article: product CTA, FAQ schema, 3+ sibling links, second-agent GAAP fact-check before publish, a 3-line LinkedIn draft in `marketing/linkedin-queue/`.

## Always-on backlog

- Title/description alignment for any page whose buying query sits at position 8–30 (decisions 43/45 pattern).
- Video and Short cross-posts.
- Personal follow-up drafts for business-domain downloaders.
- Product page CRO: comparison table, testimonial slot, "after you pay" block, JE Generator GIFs.
- Gumroad listing hygiene: descriptions, tags, Discover categories, bundle copy.
- Lead-magnet freshness: lean free files get the same fixes as paid files.

## Stephen's part (≈ 30 min/week + one recording/month)

1. Thursday: paste the LinkedIn draft.
2. Weekly, ~5 min: approve the outreach batch (emails and quote-platform answers; sent from santiagokdesk, nothing goes out without the OK).
3. Week of Sep 7: create the Reddit account (setup note provided); then paste two short comments a week that Claude drafts; no links for the first three weeks.
4. Monthly: record one 60–90 s clip from a script (phone is fine); Claude edits, captions, posts.
5. Send the occasional personal email to a business-domain downloader (Claude drafts).
6. Decide T2 items inside their 48-hour windows.

## Measurement and reporting

- Monday 08:15 launchd job appends GSC, GA4, Gumroad and target-query rows; Claude posts a 5-line scoreboard to the vault daily note and updates the status table above.
- Stephen is pinged only when a trigger needs his click or a guardrail fires.
- Monthly: MailerLite automation open/click report captured to `marketing/seo-tracking/mailerlite-reports.jsonl`.

## Guardrails

- No active-CPA claims, no tax advice, no CAE claims; refunds and IRS/legal correspondence Stephen-only; no outreach or posting from Stephen's accounts without his paste/OK.
- Paid spend: $0 until the first sale, then $100/mo cap, then $250/mo at M3.
- Pricing: tests within ±30 % only at the triggers above, each logged T2 with a 48-hour veto.
- Kill/pivot: 0 full-price sales by 2026-12-01 despite ≥ 40 new downloads and ≥ 12 organic/day → Stephen decision on caps, pricing structure or repositioning, with a data memo from Claude.
