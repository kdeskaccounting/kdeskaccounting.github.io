# KDesk Accounting — Operational Plan

*Drafted by Claude Code 2026-05-10, after reviewing this repo + `~/kdesk-workspace/CLAUDE.md`*

## The problem in one sentence

You shipped 13 SEO blog posts in 9 days in March, then zero in 52 days. The infrastructure is good; the engine stalled. Google rewards consistency over heroics, and CAE (your Priority 1 per `kdesk-workspace/CLAUDE.md`) needs the funnel running, not stalled.

## What's already built and working

- 13 published SEO posts targeting high-intent accounting keywords (burn rate, runway, ASC 842 JEs, ROU asset, IFRS 16 comparison, SaaS deferred revenue, commission capitalization, etc.)
- Three template product pages (ASC 606 commission, ASC 842 lease, Runway)
- Hugo PaperMod site with calculator page, GA4, Cloudflare Analytics, sticky header, dark mode, JSON-LD product + FAQ schema, sub-1s page load
- GitHub Pages auto-deploy via Actions
- Gumroad backend with at least 4 templates ($49–97 price points)

## What's not built (the operational gaps)

1. **No content cadence engine.** Posts ship when Stephen has energy, then they don't.
2. **CAE waitlist isn't wired in.** Every visitor hits a templates CTA. The actual mission per `kdesk-workspace/CLAUDE.md` is CAE — you're missing the funnel terminus that matters most.
3. **Existing 13 posts aren't distributed.** They sit on Google. LinkedIn, Reddit r/Accounting, r/FPandA, dev.to, HackerNoon — zero presence.
4. **No email list.** Every blog visitor leaves without becoming a captured lead. You can't pre-launch CAE without a list.
5. **No autonomous decision framework.** Every operational action requires Stephen at the keyboard.

---

## The 4 high-leverage moves

### Move 1: Weekly autonomous SEO content engine
**Priority: P1 — biggest unlock**

Build `/new-post` orchestrator in this repo, mirroring the pattern from `~/digitalproducts/.claude/commands/new-theme.md`:

- **Researcher subagent:** scans Google "People Also Ask" for `[ASC 606|ASC 842|commission|deferred revenue|SaaS finance|month-end close]` long-tails, Reddit r/Accounting hot threads, ranks by search-volume-per-difficulty
- **Writer subagent:** drafts 1500–2500 word post in the KDesk CPA-to-CPA voice (no fluff, walks through with JE examples, ends with template + CAE CTAs)
- **Fact-checker subagent:** verifies citations against FASB codification (the killer differentiator — most AI accounting content has subtle ASC misquotes that destroy credibility with the target audience)
- **Publisher subagent:** generates Hugo Markdown with front matter + schema, commits, pushes, Action deploys
- **Distributor subagent:** drafts LinkedIn excerpt + Reddit-comment-ready snippet (does not auto-post to social — that's T2)

**Tier framework:**
- T1 (act + log): Routine posts on researched keywords with clean fact-check
- T2 (act + 48-hr veto): Posts touching specific GAAP positions, product claims, or competitive comparisons
- T3 (escalate, never auto-ship): Posts answering "what should I do" tax/legal questions

**Cadence:** 2 posts/week target = 8/month = 96/year. Versus the current trailing 13.

**Effort to build:** 1 evening of focused autonomous work.

---

### Move 2: CAE waitlist as the funnel terminus
**Priority: P1 — should ship in ≤1 hour**

Right now every post drives to Gumroad templates ($49–79 one-time). That serves the side-revenue thesis but not the 2026 exit plan. Every commission/ASC-606 post should have a dual CTA:

```
Primary:  CAE waitlist (the deterministic engine, not the workbook)
Secondary: ASC 606 commission template ($79 on Gumroad)
```

**What to build:**
- `/cae` Hugo page with positioning copy (lean on existing kdesk-workspace CAE description: "deterministic ASC 606 subledger for SaaS using CaptivateIQ — not consulting, not staff aug, a productized financial control system")
- ConvertKit (or MailerLite, or self-hosted) form integration — email + role + CIQ user yes/no
- One-line CTA injection across the 13 existing posts
- Hugo partial template so all new posts get it automatically

The waitlist becomes the CAE pre-launch audience. Every blog visitor you've had for the last 8 weeks could have been captured but wasn't.

**Effort to build:** ~1 hour autonomous, including the retrofit sweep across all 13 posts.

---

### Move 3: Distribute the existing 13 posts (one-time backfill)
**Priority: P2 — high leverage, low effort, easy win**

You have 13 posts that almost nobody on LinkedIn or Reddit has seen. One-time backfill campaign:

- **LinkedIn:** 13 posts, scheduled one per week, distilled as a 200-word excerpt + link. 13 weeks of "free" content from your CPA personal brand. Drives both KDesk and CAE awareness.
- **Reddit r/Accounting, r/FPandA, r/SaaS:** comment-ready snippets that answer specific recurring questions, linking back when contextually appropriate. NOT cold drops — the difference between value-add and spam.
- **dev.to + HackerNoon cross-posts** for the SaaS-metrics + runway posts (different audience: dev/PM-side finance folks who own runway models).

**Tier:** All distribution as T1 (act + log). LinkedIn copy gets drafted autonomously; Stephen reviews the weekly batch in the digest if desired but doesn't have to.

**Effort to build:** ~2 hours autonomous to draft the 13 LinkedIn variants + 13 Reddit comment templates + 5 dev.to cross-posts.

---

### Move 4: Tier-controlled decision log for KDesk operations
**Priority: P2 — required for the others to run autonomously**

Same `decisions_log` schema pattern as `~/digitalproducts/data/digitalproducts.db`, scoped for KDesk:

- **T0:** SEO post publishes, social cross-posts, A/B test rotations
- **T1:** New template ships from inventory, pricing adjustments within ±10%, email campaign sends
- **T2:** New product line announcements, partnership outreach (Cordion, EdgePursuit referrals per kdesk-workspace), competitive copy claims
- **T3:** Anything touching client funds, tax/legal advice in posts, refunds over $50, IRS or FASB correspondence, anything an Etsy/auditor/legal email asks about

Daily 18:00 digest to Slack. Same 48-hour veto window for T2.

**Effort to build:** ~2 hours autonomous, including SQLite schema, slash commands, and Slack wiring.

---

## What we should NOT do (decision filter applied)

Per `kdesk-workspace/CLAUDE.md` operating principles + decision filter, reject:

- **Podcast / video content.** Requires Stephen to record on schedule. High chaos, violates the morning-routine constraint.
- **Cold outreach to accountants.** Low conversion, mission drift toward consulting/staff-aug (explicitly non-negotiable per CAE positioning).
- **More products before existing ones have marketing.** "Build Once, Sell Many" — the existing 4 templates + the planned CAE are more SKUs than the current funnel can monetize.
- **Twitter/X presence.** CPA audience doesn't live there. LinkedIn is the right CPA channel.
- **A second blog / niche site.** Mission drift. KDesk Accounting is the umbrella.

---

## Recommended sequence

| When | Move | Hours | Who |
|---|---|---|---|
| **Tonight or tomorrow AM** | Move 2: CAE waitlist + retrofit existing 13 posts | ~1 | Claude Code autonomous |
| **Wednesday evening** | Move 1 scaffold: `/new-post` pipeline + fact-checker harness | ~3 | Claude Code autonomous |
| **Thursday morning** | First auto-generated post draft for Stephen review (T2 first time) | 0 | Auto, Stephen reviews |
| **Friday or Monday** | First T1 auto-publish goes live | 0 | Auto |
| **By next Monday** | Move 3: 13-post LinkedIn batch drafted + scheduled | ~2 | Claude Code autonomous |
| **By 2026-05-25** | Move 4: tier framework + decision log live | ~2 | Claude Code autonomous |
| **2026-06-01 onward** | Weekly auto-post cadence sustained, weekly KDesk digest in Slack | 0 | Auto |

**Total Stephen time required across the build:** ~30 minutes spread across approval checkpoints. **Total Claude Code time:** ~10 hours autonomous.

---

## How this serves the 2026 exit plan

Per the decision filter in `kdesk-workspace/CLAUDE.md`, this work:

- ✅ **Increases probability of 2026 exit:** CAE waitlist is the most direct funnel to Priority 1
- ✅ **Increases margin:** zero marginal cost on auto-generated SEO content vs. hiring writers ($300–800/post elsewhere)
- ✅ **Increases leverage:** content compounds in Google over time; same post drives traffic for 12+ months
- ✅ **Preserves lifestyle constraints:** zero Stephen labor required after build; no recording, no live performance, no client-juggling
- ✅ **Reduces cognitive load:** daily digest replaces "what should I write this week" decision fatigue

The one risk to flag: **fact-checker quality.** AI-generated accounting content with even one bad ASC citation will torch credibility with the controllers/CFOs who are your target. The fact-checker subagent has to be ruthless — if it can't verify a citation against a real FASB source, the post gets blocked or flagged for Stephen review. This is the technical bar to clear before Move 1 can go T1.

---

## Open questions for Stephen

1. **Email backend:** ConvertKit ($15/mo), MailerLite (free up to 1k), or self-hosted via the existing Cloudflare stack? Recommend ConvertKit — best CPA-audience deliverability and a clean API.
2. **Posting cadence:** 1/week (safe) or 2/week (aggressive)? Recommend starting 1/week, validating fact-checker quality, then scaling to 2/week after ~4 weeks.
3. **LinkedIn auto-post vs. draft-only:** LinkedIn has limited official API access; for personal posts it's draft-and-paste. Should we wire to Buffer/Hypefury for actual auto-post, or just generate drafts for Stephen to paste each Monday? Recommend drafts-only for the first 4 weeks — voice tuning matters.

---

*Drop me a thumbs-up on the sequence and I'll start with Move 2 tomorrow.*
