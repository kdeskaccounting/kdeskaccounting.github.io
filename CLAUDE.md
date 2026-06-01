> 🧭 **Command Center vault** — Stephen's context, goals, and decisions live in `/mnt/c/CommandCenter`. Relevant note: `02-Projects/KDesk-Blog.md`. See `_meta/CLAUDE.md`; global rules in `~/.claude/CLAUDE.md`.

# CLAUDE.md — KDesk Accounting blog

## Read first, every session

1. `OPERATIONS_PLAN.md` in this repo — strategic plan (drafted 2026-05-10, mostly still current; Move 2 done, Move 1/3/4 in progress)
2. Stephen's overall vision: `/home/kdeskconsulting/kdesk-workspace/CLAUDE.md` (2026 exit plan, CAE, decision filter)
3. Latest entries in `decisions/decisions.jsonl` — every autonomous action gets logged here
4. Memory: `~/.claude/projects/-home-kdeskconsulting-kdeskaccounting-blog/memory/next_session.md` — the punch list for what's next

## What this is

A Hugo + PaperMod static site at **https://kdeskaccounting.com**. Stephen is a CPA (10+ years sales-comp accounting, ex-CaptivateIQ). The site sells Excel templates on Gumroad ($49-97 each) and feeds an email list that compounds into the bigger 2026 plays (CAE → tax practice).

## Architecture

- **Framework:** Hugo (extended, 0.147+), PaperMod theme (submodule under `themes/PaperMod/`)
- **Hosting:** GitHub Pages from `kdeskaccounting/kdeskaccounting.github.io` repo
- **Domain:** kdeskaccounting.com (Cloudflare DNS, NOT proxied — resolves to GH Pages IPs)
- **CNAME:** `static/CNAME` → `kdeskaccounting.com`
- **Deploy:** push to `main` → GH Actions `.github/workflows/deploy.yml` → live in ~30s
- **Email backend:** MailerLite (free tier, account `2340006`); form action posts to `https://assets.mailerlite.com/jsonp/2340006/forms/187224873250063752/subscribe`
- **Analytics:** GA4 `G-1ZJZEE0G75` + Cloudflare Web Analytics beacon

## Content layout

- `content/posts/` — 13 blog posts (ASC 606, ASC 842 family, runway, SaaS metrics, depreciation, month-end close)
- `content/templates/` — 3 product/template landing pages (asc606, asc842, runway), each with FAQ schema + Product JSON-LD
- `content/calculator/` — free browser-side calculator (zero-friction lead magnet)
- `content/about/`, `content/search/` — standard pages

## Custom layouts (the bits to know)

- `layouts/_default/single.html` — overrides PaperMod theme. Renders the email-capture partial AFTER content on posts only (not on /templates/, /calculator/, /about/).
- `layouts/partials/email_capture.html` — the inline email form. Posts to MailerLite. Excluded from non-posts pages.
- `layouts/partials/extend_head.html` — global `<head>` injections: Cloudflare Analytics beacon, MailerLite Universal script, GA4 Key Event handler (Gumroad outbound clicks, calculator opens, template page views), JSON-LD schema.
- `layouts/index.html`, `layouts/templates/`, `layouts/calculator/` — custom homepage + product pages + calculator.

## Marketing infrastructure (queues, not auto-posters)

- `marketing/linkedin-queue/` — LinkedIn post drafts. 00 is the launch announcement; 01-03 are weekly distribution drafts pending Stephen's voice approval. Remaining 10 to be drafted after voice approval.
- `marketing/reddit-templates/` — Reddit comment templates with Version A (no link, r/Accounting-safe) and Version B (with link, for aged accounts in permissive subs). 3 drafted, 7 to go.
- Neither directory auto-posts. They're queues for Stephen to draw from manually OR for me to post via CDP once an account is set up and aged.

## Decision log + tier framework

`decisions/decisions.jsonl` — append-only ledger of autonomous actions:

- **T0:** auto-execute, log only. Site copy tweaks, SEO meta edits, queue refills.
- **T1:** auto-execute, surface in daily digest. New blog posts (when fact-checker passes), social cross-posts, pricing micro-tests (±$1).
- **T2:** act + 48-hour Stephen veto window. Pricing changes >10%, new product line claims, partner outreach, competitive comparisons.
- **T3:** hard gate — never bypass. CPA-license claims (Stephen's WA license is inactive), tax/legal advice in content, refunds, IRS/FASB correspondence, anything an Etsy/auditor/legal email asks about, claims about CAE before CAE ships.

## How to operate

- **Code style:** Hugo templates — keep partials small. Tailwind-free; we use the kd-* prefix for custom CSS classes already established in `assets/css/`.
- **Editing posts:** posts use frontmatter (title, date, description, tags, ShowToc, etc.). Add `Lastmod` when materially editing.
- **Branching:** small changes can land directly on main (they auto-deploy). For significant marketing changes or experiments, use `feature/...` branches and merge when ready.
- **Never commit:** API tokens, env vars, build artifacts (`public/`, `.hugo_build.lock` already in `.gitignore`).

## Credentials & external state

- MailerLite API token: `/home/kdeskconsulting/kdesk-analytics/mailerlite-token.txt` (full account access; treat as secret)
- MailerLite metadata: `/home/kdeskconsulting/kdesk-analytics/mailerlite-form.json`
- Cloudflare API tokens (for both joyfoldshop.com + kdeskaccounting.com zones): `/home/kdeskconsulting/digitalproducts/.env`
- Google Workspace MCP: authed as `santiagokdesk@gmail.com` (NOT smichels1@gmail.com — different account)
- Search Console: verified via DNS TXT (`google-site-verification=bJlwcW0aYXafivvCsvcRhgyE2UiLDwwF6WIteYQqaEU`)

## Useful commands

```bash
# Local preview
hugo server --port 1313

# Production build (Actions runs this on push to main)
hugo --minify

# Read decisions log
tail -20 decisions/decisions.jsonl | python3 -c 'import sys,json; [print(f"{json.loads(l)[\"id\"]:>3} T{json.loads(l)[\"tier\"]} {json.loads(l)[\"status\"]:>10} {json.loads(l)[\"action\"][:90]}") for l in sys.stdin]'

# Check live deploy status
gh run list --limit 3

# MailerLite API: list subscribers
TOKEN=$(cat /home/kdeskconsulting/kdesk-analytics/mailerlite-token.txt)
curl -s -H "Authorization: Bearer $TOKEN" https://connect.mailerlite.com/api/subscribers | python3 -m json.tool
```

## Currently working on (resume here next session)

See `~/.claude/projects/-home-kdeskconsulting-kdeskaccounting-blog/memory/next_session.md`. Punch list highlights:

1. **Finish welcome email body in MailerLite** (5 min UI or API retry tomorrow). Automation `Welcome — free templates pack` exists but body is empty. Subscribers still get MailerLite's default double-opt-in confirmation, so launch is not blocked.
2. **Stephen reviews voice** on the 3 LinkedIn + 3 Reddit drafts; once approved I batch-write the rest.
3. **Reddit account creation** + aging schedule (Stephen 10 min for account + sandboxed Chrome profile, then 3 weeks of helpful-comment aging before any link drops).
4. **Internal link graph audit** across 13 posts (T0, autonomous when other work clears).

## Hard gates (never bypass)

1. CPA license claims: Stephen's WA license is **inactive**. Content must never imply active CPA practice/licensure or constitute tax advice.
2. CAE positioning: never imply CAE has clients, a waitlist, or is shippable until Stephen confirms. Currently building MVP.
3. Tax/legal/IRS correspondence: escalate to Stephen, never auto-respond.
4. Refunds and anything financial: Stephen-only.
5. Strategic pivots (channel ditch, ecosystem change): Stephen-only.

## What changed in the last session (2026-05-10 → 2026-05-12)

- Marketing foundation shipped: email capture + GA4 Key Events + MailerLite wiring + decision log + marketing queues
- Welcome automation half-built (body is the known gap)
- LinkedIn launch announcement drafted and queued
- Site state correctly assessed (initial audit was on stale local clone; corrected after `git pull`)
- Channel strategy locked: LinkedIn + Reddit only

## Metrics I own  (report up to the Command Center COO report)

This project owns the funnel KPIs that roll into `/mnt/c/CommandCenter/02-COO-Report.md` + `01-Dashboard.md`.
Run the weekly pull (Monday) and update `marketing/seo-tracking/*.jsonl`.

**THE ONE metric:** **Confirmed ORGANIC email subscribers** (net-new/wk + cumulative). Now **0**
(4 total MailerLite subs = 3 API-imported Gumroad downloaders + 1 Stephen test). This is the funnel's
dead link — until it climbs, nothing else here is working, no matter how good impressions look. The list
is the compounding asset that feeds CAE (a captured email = a repeatable CAE prospect at ~$0 marginal cost).

**Also owned (and what's vanity):**
- Organic Search sessions (de-botted ~61/28d) — NOT raw GA4 sessions (~398 is ~80% bot Direct: 2s, 9.7% engagement). **Raw sessions/users + GA4 revenue ($0, Gumroad sits outside GA4) + "34 key events" (≈1 visitor) are VANITY — do not report.**
- Lease-cluster avg position (operating-vs-finance-lease, asc-842-journal-entries, asc-842-vs-ifrs-16) — ~64% of impressions, sit at pos ~35 (page 4) → 0 clicks. Highest-leverage SEO lever.
- Sitewide GSC CTR (0.04% — the distribution bottleneck, the bridge between ranking and clicks).
- Gumroad downloads (free) + paid + revenue ($15 to date). Manual read (no API).
- GA4 `email_signup` event vs MailerLite confirmations — the leak diagnostic (submit vs confirm).

**Data sources (real paths):**
- MailerLite group `187224670039180750`; token at `/home/kdeskconsulting/kdesk-analytics/mailerlite-token.txt`; API `connect.mailerlite.com/api/subscribers` (filter active, exclude manual imports + santiagokdesk).
- GA4 property `p528583005` + GSC → log to `marketing/seo-tracking/ga4-snapshots.jsonl` and `gsc-snapshots.jsonl` (append-only).
- Gumroad: manual logged-in dashboard read (no API export wired yet).

**Cadence:** weekly (Monday) — last-7d + last-28d pull.

**Action triggers (raise to Stephen):**
- 0 net-new organic subs for 2 weeks while organic sessions >0 → **P1: diagnose the form** (double-opt-in friction, empty welcome-email body, form visibility). The binding constraint.
- Lease cluster not improving toward pos 15–20 by ~2026-06-28 → escalate to Phase 2 SEO (content depth / pillar page — gated on Stephen as new content).
- GSC `email_signup` >0 but MailerLite confirmed organic =0 → fix the confirmation flow (finish welcome-email body / consider single opt-in).
- A **business-domain** Gumroad lead (e.g. the csibas.com downloader) → flag as a **CAE/consulting warm lead** for personal follow-up. This is the actual blog→CAE handoff and it's currently uninstrumented.

**Outstanding automation:** the weekly GA4/GSC pull (systemd timer + OAuth via `scripts/setup_seo_oauth.py`)
is BUILT but NOT enabled — Stephen's one-time ~10-min OAuth step unblocks the time series. The MailerLite
welcome-email body is still empty (silent conversion killer). The blog→CAE handoff has no instrumentation.
- Email backend: MailerLite free tier
