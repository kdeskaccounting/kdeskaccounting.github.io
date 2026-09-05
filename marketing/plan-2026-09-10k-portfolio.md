# KDesk → $10,000/month: a portfolio plan

**Date:** 2026-09-04
**Target:** $10,000/month. **Safety net cleared on the way at $4,246/month.**
**Status:** Ready. Five committed streams + one gated. Part 7 lists the research a session rate limit cut short.

---

## Context

Stephen asked for **$10,000/month in passive income within 12 months**, using maximum leverage and minimum human capital. An earlier draft of this plan quietly reduced that target to $5,000 and confined itself to the existing Gumroad catalog. He rejected it:

> *"What I want is a plan to get to $10,000 that will satisfy the safety net even if we don't get to $10k. You're trying to make it easier by reducing the target. Expand your mindset beyond our current product listing into anything that is accounting or accounting adjacent."*

**So: $10,000/month is the target.** The safety net is a milestone passed on the way, not a substitute goal.

### The safety net, defined

From `~/CommandCenter/02-COO-Report.md` (live balance sheet, 2026-07-13). Without Stephen's W-2, the household has VA disability $2,800/mo (tax-free) + Kaley ~$500/mo = **$3,300/mo** against essential burn of **$7,546/mo**.

| Milestone | Monthly | Meaning |
|---|--:|---|
| **Safety net** | **$4,246** | Essential burn covered. Quitting the W-2 to launch the practice becomes pressure-free; practice income is upside, not survival. |
| **Lifestyle** | $6,700 | Full $120k/yr household spend replaced. |
| **Target** | **$10,000** | Replaces the W-2 outright, with margin. |

### The real diagnosis

The problem is not the products, the prices, or the copy. **Stephen has exactly one distribution channel and it is the worst available one.**

Google organic search: **1.07 clicks/day, average position 28.9** — page 3, which receives 0.63% of all clicks. It is query-pull (he must wait to be searched for), it is dominated by well-funded incumbents (FinQuery, Crunchafi at 27,000 companies), and AI Overviews are cutting result click-through from 15% → 8% ([Pew, Jul 2025](https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/)). Every product decision downstream of ~30 visitors/month fails for the same reason.

**The fix is not better SEO. It is more channels — specifically channels where discovery is the platform's job, not his.**

### The two assets that make this possible

1. **A zero-human-input content factory.** `scripts/video/` turns a ~130-line YAML spec into a finished, narrated, professionally rendered Excel-walkthrough video with title cards, Ken Burns zoom aimed at the highlighted cell, local TTS, auto-generated chapters, thumbnails, covers, and a 9:16 Short. No face, no voice, no editing. **The marginal human cost of a video is one LLM generation.** At 5/week that is 260/year — a volume no individual accounting creator can match.
2. **Unlimited engineering labor.** Building five products costs roughly what building one costs *in Stephen's time*. This is what makes a portfolio rational rather than unfocused.

### Decisions taken this session

| Question | Answer |
|---|---|
| Structure | **Portfolio of 4–6 streams**, each with a different distribution channel and a hard kill date |
| Public identity | **Faceless + occasional face** — pipeline volume as the engine, his 60–90s clip monthly for credibility |
| Support burden | **Only if automatable to near-zero** — AI-handled support, exhaustive docs, deliberately narrow scope |
| Burst capacity | **Two 3–4 day bursts per month** (~24/year) |
| This fall | **CPE primary + one burst.** The Nov 1 license filing keeps priority |
| Pricing | ASC 842 $97 → **$249**, bundle $249 → **$599**. Free tier stays generous |
| Lead cluster | **ASC 606 commission capitalization**, not ASC 842 |
| Liability | "Tool, not opinion." No assurance language, no active-CPA claims, no tax advice |
| Employer | No non-compete or IP assignment — confirmed clear |
| Capital | **< $1,000 total** |

### Rejected, with reasons

| Option | Why not |
|---|---|
| **ASC 842 micro-SaaS** | **LeaseGuru (FinQuery) is FREE to 2 leases and $999/yr to 10** — self-serve, "CPA-approved," with the exact feature set proposed ([finquery.com/leaseguru](https://finquery.com/leaseguru/)). Cradle $99/mo, iLeaseXpress $149/mo. No gap exists. ASC 842 is also late-cycle: private-company adoption was fiscal years beginning after Dec 15, 2021 |
| More Excel templates | `marketing/product-6-research.md`: each new workbook is worth ~$25–40/mo. $10k would need ~250 of them |
| Paid membership | 17 subscribers. At a spectacular 10% take, $29/mo × 1.7 = $49/mo. Content treadmill scales workload with revenue |
| CPA-firm licensing as primary | Crunchafi already has 750+ firms. 3–9 month cycles, partner approval, pure outbound — the motion Stephen avoids |
| Paid ads | Hard gate: $0 until first sale (decision 47), and capital is <$1,000 |

### The failure mode this plan is built to avoid

CAE was killed 2026-07-14 at ~90% build with **zero customer outreach**. Stephen's own post-mortem: *"Distribution, not building, was the wall... A working factory with no demand isn't a business."*

**Every stream below is therefore defined by its distribution channel first and its product second.** A stream with no answer to "how does the buyer find this?" does not get built.

---

## The ladder

Each tier funds and de-risks the next. The safety net falls at Tier 2.

| Tier | Monthly | What it takes | When |
|---|--:|---|---|
| **T1 — first dollars** | $0 → $2,000 | Streams with no build and no traffic dependency | Months 1–3 |
| **T2 — SAFETY NET** | $2,000 → **$4,246** | Content channels reach monetization threshold | Months 4–9 |
| **T3 — target** | $4,246 → **$10,000** | The scalable platform-distributed product compounds | Months 10–18 |

---

## Part 1 — The five streams

Each is defined by its **distribution channel first**. Every one is a different channel, so they fail independently.

---

### Stream A — The RSU tax-gap product · **the biggest find in this session**

> **Status 2026-09-05:** the free calculator is **live at `/rsu-tax-calculator/`** (decision 55) — fact-checked, tested, in the nav. Next: the paid vest-by-vest planner workbook; an RSU Short once the pipeline can render web pages.

**Channel:** SEO (winnable here, unlike ASC 842) + LLM citation + YouTube. **Audience is orders of magnitude larger than "controllers who need lease templates."**

Verified market structure — it is **barbelled with nothing in the middle**:

| Band | What exists | Equity-comp modeling? |
|---|---|---|
| **$0** | Secfi, EquityFTW, ESO Fund, EquityBee, myStockOptions free calculators | Single-shot only. All are lead-gen for a financing or advisory sale |
| **$95–149/yr** | Copilot $95 · Monarch ~$99 · YNAB $109 · Tiller $99 · ProjectionLab $129 | **None of them model equity compensation at all.** YNAB doesn't even track investments |
| **$150–255/mo** | RightCapital, StockOpter | **Advisor-only.** Cannot be sold to the end user |
| **$7,200/yr** | Secfi Wealth flat fee; Brooklyn Fi 1% AUM + tax fees | Full advisory relationship |

**Nobody sells a self-serve product in the $49–300 band that chains the four steps:** vest schedule → **22% federal supplemental withholding vs. an actual 32/35/37% marginal rate** → the resulting April shortfall and safe-harbor estimate → concentration as a % of net worth. No tool found markets **the withholding gap itself** as its headline calculation — and that gap is what produces a surprise five-figure April bill for someone earning $300k+.

**Why Stephen specifically:** he is a CPA who *lives this* — IBM RSUs, $54,279 unvested on his own balance sheet — and he has already built the personal-finance machinery (SimpleFIN sync at **$15/year**, automated balance sheet, net-worth tracking). The product is largely his own system, generalized.

**Shape:** free calculator on-site (link magnet + LLM bait + the SEO play) → paid workbook/tool at **$99–149**.

**Regulatory line — verified against the statute, not summarized from memory.** 15 U.S.C. § 80b-2(a)(11) reaches advice about "the value of securities or … the advisability of investing in, purchasing, or selling securities," including through "publications or writings." Exclusion **(D)** protects "the publisher of any bona fide … business or financial publication of general and regular circulation," and *Lowe v. SEC*, 472 U.S. 181 (1985) draws the line at impersonality: *"The mere fact that a publication contains advice and comment about specific securities does not give it the personalized character that identifies a professional investment adviser."*

- **Safe:** tax mechanics — withholding vs. marginal rate, the shortfall, safe-harbor estimates, §83(b), W-2 coding. This is arithmetic on compensation; the securities are merely the payment vehicle.
- **Line:** displaying concentration % is fact. Attaching a target ("should be under 20%") starts to look like advice on the advisability of selling.
- **Off-limits:** sell-to-cover vs. hold recommendations, and anything personalized to a named user's holdings.
- **Do not rely on the CPA exclusion (B).** It requires the advice be "solely incidental to the practice of his profession" — a standalone product sold for separate compensation is the exact fact pattern that defeats it, and Stephen's license is inactive besides.

**Honest risk found in the same research:** the middle of the market may be empty for economic reasons, not oversight. Someone facing a $40k shortfall is a highly qualified lead for a $7,200/yr advisor, so everyone already in this market rationally gives the calculator away. A $99 tool cannibalizes a $7,200 sale — for them. For Stephen, who wants product revenue rather than advisory clients, that asymmetry is the opportunity.

**And unlike the accounting blog, this stream genuinely compounds with the practice.** A high-income W-2 employee with equity comp is precisely the tax client his own MOC targets ("HNW individuals, professionals"). The ASC 842 audience never was.

---

### Stream B — YouTube at volume, faceless

**Channel:** algorithmic push, not query-pull. Nobody has to search for him.

**The structural edge:** `scripts/video/` turns a ~130-line YAML into a finished narrated tutorial with chapters, thumbnails, and a 9:16 Short. Marginal human cost ≈ one LLM generation. **At 5/week that's 260 videos/year** — a volume no individual accounting creator can match, in a niche where CPMs are high and every competitor edits by hand.

Two content lines: technical accounting (existing catalog) and the RSU/equity-comp consumer angle (much larger audience). Revenue: AdSense + affiliate + funnel into Streams A and E.

**Blocking unlock:** the Google token carries only `webmasters.readonly` + `analytics.readonly` — **no YouTube scopes**. Publishing currently depends on Stephen's debug Chrome driving Studio via Playwright, and **12 published videos have zero analytics captured**. One OAuth re-consent adds YouTube Data API v3 upload + analytics: publishing becomes autonomous and the measurement blackout ends. Cheapest structural unlock in the plan.

---

### Stream C — Affiliate / referral layer

**Channel:** monetizes every other stream's traffic at 5–10×. Today a visitor who wants software rather than a spreadsheet is worth **$0**.

FinQuery runs an explicit Referral Partner track ([finquery.com/partners](https://finquery.com/partners/)); Cradle is small enough to say yes to an unknown partner; the RSU audience routes to tax software and brokerages. B2B SaaS referral typically pays 10–20% of first-year ACV — a $999/yr LeaseGuru referral ≈ $100–200; larger vendors $300–800.

Zero build, zero support, zero liability, perfect dormancy tolerance. **Do this regardless of what else happens.**

---

### Stream D — Expert networks

**Channel:** demand-pull. They find him; there is no marketing and no traffic requirement.

A rare profile: CPA + 10 yrs sales-compensation accounting + **ex-CaptivateIQ Reporting Lead** + current IBM. Investors and consultancies pay for exactly this when diligencing the ICM category (CaptivateIQ, Xactly, Varicent, Spiff, Everstage). GLG, AlphaSights, Guidepoint, Third Bridge, Dialectica, Coleman. Typical niche-practitioner rates $200–600/hr at 1–4 hrs/month. Dormancy-tolerant by construction — decline calls during dark weeks.

**Hard gate before signing up: read IBM's outside-activities / conflict-of-interest policy in writing.** Then never discuss IBM, IBM customers, or competitor compensation data — category dynamics only.

---

### Stream E — The ASC 606 commission kit · $1,997

**Channel:** his existing SEO (`deferred commissions asc 606` is his **highest-impression non-brand query**, 436 impressions/90d) + LinkedIn + the sales-comp community.

His rarest expertise, and the only cluster where the competitive set below Big-4 advisory ($50k+) is genuinely empty — unlike ASC 842. High ticket is the correct answer at 30 visitors/month: **one sale a month is $2,000.**

Contents are mostly assembly of existing assets: the ASC 606 workbook, plus a **technical accounting memo template** (the deliverable auditors actually request, and the piece nobody else sells), the amortization-basis decision framework documented to auditor standard, clawback handling (ASC 340-40-35), an auditor PBC package, and one faceless 90-minute walkthrough.

**Liability posture:** templates and documentation, never an opinion. No assurance language, no active-CPA claim. LLC + E&O bound before the *second* sale, funded by the first.

---

### Gated, not committed — the platform app (QuickBooks / Xero)

Highest ceiling of anything considered: platform-provided discovery, ~$20–30/mo price points, and QBO handles lease schedules, prepaid amortization, and fixed-asset depreciation badly or not at all — all of which Stephen already owns as working Excel logic. **300–500 users would be $10,000/month on its own.**

**But the research that would justify it died to a session rate limit.** Unverified: whether those gaps are actually unserved, Intuit's security-review and insurance requirements, revenue share, time to approval, and real discovery volume. It also carries the largest support burden of any option.

**Treat as a Tier 3 candidate, validated first, built only if Tiers 1–2 prove the portfolio works.**

---

## Part 2 — The shared engine

One knowledge spec, six outputs: **workbook · video · Short · article · course lecture · LLM-citable reference page.** Built once by me, expressed across every channel. This is what makes five streams cost roughly what one costs *in Stephen's time*.

Instrumentation to add: YouTube Data API (12 assets, zero data), a MailerLite reports feed, and affiliate dashboards.

---

## Part 3 — The ladder, with arithmetic

| Tier | Monthly | Streams carrying it | Window |
|---|--:|---|---|
| **T1 — first dollars** | $0 → **$2,000** | C (affiliate) · D (expert networks) · A v1 shipped · repricing | Months 1–3 |
| **T2 — SAFETY NET** | $2,000 → **$4,246** | B monetized · A through the Q4/April season · E selling · **VA claim +$1,083** | Months 4–9 |
| **T3 — target** | $4,246 → **$10,000** | Whichever stream showed traction gets the scalable build; everything else killed | Months 10–18 |

**How $10k closes** (estimates, not forecasts — the RPM and conversion inputs are unverified):

| Stream | Monthly |
|---|--:|
| B — YouTube, ~300k views/mo at accounting-niche RPM | ~$3,600 |
| A — RSU tool, ~40 sales/mo at $99 (seasonally spiky) | ~$3,960 |
| E — one ASC 606 kit per month | ~$2,000 |
| D — expert networks | ~$1,500 |
| C — affiliate | ~$800 |
| **Total** | **~$11,860** |

The arithmetic closes. That is more than the template business could ever do — its verified ceiling was $350–530/month with *every query on page 1*.

### Honest probability

| Month 12 | P | |
|---|--:|---|
| Under $500/mo | ~30% | Dormancy wins, or no channel catches |
| $500–2,000/mo | ~35% | Some streams land; below the safety net |
| $2,000–4,250/mo | ~20% | Approaching safety |
| **Above $4,246 (safety net)** | **~15%** | |
| $10,000/mo | ~5% at M12, ~15–20% by M18–24 | |

**$10k in 12 months is unlikely. $10k by month 18–24 is a real possibility, and the safety net is a genuine month-12-to-18 outcome.** The portfolio structure is what makes those numbers non-trivial: five independent shots beat one, and none of them requires beating FinQuery at Google.

---

## Part 4 — Sequencing

**Fall (now → Nov 1): CPE is primary. One burst for this.**
I build continuously; the burst is for launches and approvals only. Ships in the fall: repricing, affiliate applications, the RSU free calculator + paid v1, the ASC 606 kit assembly, YouTube volume restart.

**Nov–Jan:** RSU tool through its natural Q4/April demand season. YouTube to monetization threshold. E selling.
**Feb+:** kill the losers; put every remaining burst behind whatever caught. Validate the platform app.

---

## Part 5 — What only Stephen can do

Small, and mostly one-time:

1. **OAuth re-consent** adding YouTube scopes — unblocks autonomous publishing *and* ends the analytics blackout. ~5 minutes.
2. **Read IBM's outside-activities/COI policy**, then sign up to 3–4 expert networks. ~1 hour, once.
3. **Send the customer-discovery email** — 6 business-domain downloaders + 17 subscribers. **Five personalized drafts have sat unsent in santiagokdesk@gmail.com since 2026-09-01.** ~20 minutes.
4. **DM Bill Hanna** (Controller Academy, ~340k subs, former customer, drafted since 09-03).
5. Affiliate program signups (his identity), and the monthly 60–90s clip.
6. Keep the debug Chrome logged in until the YouTube API replaces it.

---

## Part 6 — Kill criteria

Each stream gets a date and a number. No stream survives on hope.

| Stream | Kill if, by | Unless |
|---|---|---|
| A — RSU tool | 90 days post-launch: <5 sales | free-calculator traffic is growing |
| B — YouTube | 6 months: <1,000 subs or <10k views/mo | watch time trending up |
| C — affiliate | never — cost is zero | — |
| D — expert networks | 3 months: no calls after applying to 4 | — |
| E — ASC 606 kit | 6 months: 0 sales | qualified inbound exists |

**Portfolio-level:** if by **2026-12-01** total revenue is still $0 across all streams, stop building and reassess — that is the CAE pattern repeating.

**Leading indicator, checked 2026-10-15:** if the customer-discovery email still hasn't been sent, nothing else matters. *"Distribution, not building, was the wall."*

---

## Part 7 — Research still owed (rate limit)

Validate before committing burst time:

- **Platform app viability** — QBO/Xero gaps, security review, insurance, revenue share, discovery volume
- **YouTube RPM** in accounting/finance, and faceless-vs-talking-head performance in the niche
- **Course marketplace economics** (Udemy revenue share and realistic earnings)
- **Sales-comp / ICM niche** — his rarest expertise, unexamined as a market
- **myStockOptions.com membership price** — the nearest paid analogue to Stream A; tells us what that market bears

---

## Part 8 — Files and records

| File | Change |
|---|---|
| `marketing/roadmap-2026-09.md` | Superseded. The $300/mo ladder and the "$97 → $69" trigger both go; price moves **up** |
| `decisions/decisions.jsonl` | #51 strategy pivot (T2, 48-hr veto) · #52 repricing (T2) · #53 affiliate (T1) · #54 new product line (T2) |
| `~/CommandCenter/02-Projects/KDesk-Blog.md` | New target, thesis, next action |
| `~/CommandCenter/05-Decisions/2026-09-04-kdesk-portfolio-pivot.md` | Decision note: why, alternatives rejected, reversibility |
| `CLAUDE.md` | "Currently working on" + metrics ladder |
| New: `content/rsu-calculator/` + `layouts/rsu-calculator/` | Stream A, following the proven 485-line calculator pattern |

---

## Verification

```bash
# Prices live
python3 ~/kdeskaccountingtemplates/gumroad_publish.py list

# New calculator builds and deploys
hugo --minify && gh run list --limit 3

# Weekly data still flowing (launchd com.kdesk.daily-sync, Mondays 08:15)
KDESK_SEO_SKIP_COMMIT=1 uv run scripts/pull_seo_snapshot.py
python3 scripts/pull_gumroad_snapshot.py

# After OAuth re-consent — proves the YouTube unlock landed
python3 -c "import json;print(json.load(open('$HOME/kdesk-analytics/google-token.json'))['scopes'])"
```

**The four numbers that decide everything, read 2026-12-01:**

| Metric | Now | Target |
|---|--:|--:|
| **Total revenue, all streams** | **$16.99 lifetime** | **> $0/mo, any stream** |
| Full-price sales | 0 | ≥1 |
| YouTube subs / monthly views | unknown (no data) | measurable at all |
| Expert-network calls completed | 0 | ≥1 |
