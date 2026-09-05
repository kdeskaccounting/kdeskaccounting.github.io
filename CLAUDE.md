> 🧭 **Command Center vault** — Stephen's context, goals, and decisions live in `~/CommandCenter` (this is a Mac; the `/mnt/c/` and `/home/kdeskconsulting/` paths in older notes are the Windows/Linux machines). Relevant note: `02-Projects/KDesk-Blog.md`. See `_meta/CLAUDE.md`; global rules in `~/.claude/CLAUDE.md`.

# CLAUDE.md — KDesk Accounting blog

## Read first, every session

1. **`marketing/plan-2026-09-10k-portfolio.md`** — the plan (decision 51, 2026-09-04): target **$10,000/mo**, the **$4,246/mo safety net** as the first milestone, five streams on five channels, kill criteria per stream. `marketing/roadmap-2026-09.md` ($300/mo) is superseded — its weekly cadence, fact-check rule and guardrails still apply where they don't conflict. `OPERATIONS_PLAN.md` (May 2026) is historical.
2. `decisions/decisions.jsonl` — append-only ledger; every autonomous action is logged. Currently at #56. Open veto windows: **#52 repricing → 2026-09-06 22:00 PT**, **#56 RSU Tax Planner $149 → 2026-09-07 08:00 PT**.
3. `~/CommandCenter/02-Projects/KDesk-Blog.md` — the vault MOC: status, next action, blockers.
4. The **Currently working on** section below.

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

- `content/posts/` — 18 blog posts in five clusters: lease/ASC 842 (pillar + 5 spokes), commission/ASC 606 (capitalization, accrual, clawbacks), fixed assets, close, SaaS metrics/runway
- `content/templates/` — 6 product pages + `bundle/`, each with FAQ schema, Product JSON-LD, a walkthrough video and a `compare:` block (Free vs Full table)
- `content/calculator/` — free browser-side calculator (zero-friction lead magnet)
- `content/rsu-tax-calculator/` — free RSU withholding-gap calculator (Stream A lead magnet, live 2026-09-05). Tax core in `static/js/rsu-tax.js` (ESM, tested: `node --test --test-reporter=tap tests/js/*.test.mjs`; TABLE_2026 pinned to Rev. Proc. 2025-32 / Pub 15). Any change to tax numbers or copy goes through the second-agent fact-check first (T3).
- `content/about/`, `content/search/` — standard pages

## Custom layouts (the bits to know)

- `layouts/_default/single.html` — overrides PaperMod theme. Renders the email-capture partial AFTER content on posts only (not on /templates/, /calculator/, /about/).
- `layouts/partials/email_capture.html` — the inline email form. Posts to MailerLite. Excluded from non-posts pages.
- `layouts/partials/extend_head.html` — global `<head>` injections: Cloudflare Analytics beacon, MailerLite Universal script, GA4 Key Event handler (Gumroad outbound clicks, calculator opens, template page views), JSON-LD schema.
- `layouts/index.html`, `layouts/templates/`, `layouts/calculator/`, `layouts/rsu-calculator/` — custom homepage + product pages + the two calculators. **New tool pages must set `type: "<layout dir>"` in frontmatter** — Hugo resolves layouts by type (defaults to the section), so `layout:` alone silently falls back to `_default/single.html` with an empty body. Verify the built body (`grep -o id=… public/…`) and drive it with Playwright before publishing.

## Marketing infrastructure (queues, not auto-posters)

- `marketing/plan-2026-09-10k-portfolio.md` — **the plan** ($10k/mo, five-stream portfolio, kill criteria). `marketing/roadmap-2026-09.md` — the superseded $300/mo roadmap; still the reference for the weekly cadence and guardrails.
- `marketing/linkedin-queue/` — 3-line post drafts, one per article. Stephen pastes; #17 and #18 are queued. Never posted autonomously.
- `marketing/outreach/` — `targets.md` (15 researched link targets, Bill Hanna at Controller Academy first), dated batch files, and the Bill Hanna note. **Nothing sends until Stephen replies with the numbers.**
- `marketing/reddit-templates/` — comment templates plus `00-account-setup.md` (Stephen creates and ages the account; no links for three weeks; never link in r/Accounting).
- `marketing/video/` — walkthrough specs, Shorts specs (legacy `short:` block + named `shorts:` variants per `scenes.yaml`, titles in `shorts.json`), YouTube URLs (`youtube.json` / `short.json` / `shorts.json`), plus `stephen-clips/` scripts for his monthly 60–90 s clip.
- `marketing/seo-tracking/` — append-only JSONL: GSC, GA4, Gumroad, MailerLite sync, and `target-query-positions.jsonl` (24 buying queries, logged weekly).
- `marketing/product-6-research.md` — what to build next and why.

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

All live on **this Mac** unless noted:

- **Gumroad API** (read + write): `GUMROAD_ACCESS_TOKEN` in `~/kdeskaccountingtemplates/.env`
- **MailerLite API**: token `kdesk-mac-sync` at `~/kdesk-analytics/mailerlite-token.txt`; groups "Gumroad free downloaders" `197511890037901111` and "KDesk Accounting subscribers" `187224670039180750`; custom field `interest` (id `1461362`) tags RSU-calculator sign-ups (`fields[interest]=rsu-planner`). Automation email bodies are not readable/editable via API (UI or CDP only). Creating campaigns via API was blocked by the auto-mode classifier — draft copy lives in `marketing/email-sequences/`, Stephen sends.
- **GSC + GA4**: refresh token at `~/kdesk-analytics/google-token.json` (read-only scopes on the `gws` Desktop client; both APIs enabled on GCP project `involuted-disk-489017-r3`). GA4 property `528583005`.
- **Google Workspace** (`gws` CLI): authed as `santiagokdesk@gmail.com` — NOT smichels1@gmail.com
- **Search Console**: verified by DNS TXT (`google-site-verification=bJlwcW0aYXafivvCsvcRhgyE2UiLDwwF6WIteYQqaEU`)
- **Debug Chrome** for UI-only work (Gumroad covers, MailerLite editor, YouTube Studio): Stephen launches with `--remote-debugging-port=9222`, profile `~/.kdesk/chrome-debug`; drive it with `scripts/video/cdp.py` or Playwright `connect_over_cdp`
- **Linux box only** (`ssh wsl`, Tailscale `100.112.159.5`, unreachable since 2026-09-01): Cloudflare API tokens, `dist/` binaries. Nothing current depends on it.

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
TOKEN=$(cat ~/kdesk-analytics/mailerlite-token.txt)
curl -s -H "Authorization: Bearer $TOKEN" https://connect.mailerlite.com/api/subscribers | python3 -m json.tool

# Weekly pulls (the launchd job runs these Mondays 08:15; KDESK_SEO_SKIP_COMMIT=1 to test)
KDESK_SEO_SKIP_COMMIT=1 uv run scripts/pull_seo_snapshot.py   # GSC + GA4 + target-query positions
python3 scripts/pull_gumroad_snapshot.py                       # downloads, sales, revenue
uv run scripts/model_page1_revenue.py                          # page-1 revenue ceiling (quarterly)
uv run scripts/pull_youtube_snapshot.py --print                # YouTube views, Shorts vs long-form, 28d analytics (Mondays)

# Publish to YouTube via the Data API (lands PRIVATE until the GCP project passes YouTube's API audit — flip in Studio)
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug asc842 --variant liability   # render a named Short
uv run scripts/video/youtube_publish.py --kind short --slug asc842 --variant liability [--dry-run]
```

## Mac-side notes (added 2026-09-01 — this repo is now worked from the Mac too)

- **Gumroad API** (read + write): token in `~/kdeskaccountingtemplates/.env` (`GUMROAD_ACCESS_TOKEN`). CLI: `python3 ~/kdeskaccountingtemplates/gumroad_publish.py list|sales`. Weekly money-metric pull: `python3 scripts/pull_gumroad_snapshot.py` → `marketing/seo-tracking/gumroad-snapshots.jsonl`. Note: the paid ASC 606 product (`mwmwpe`) is live but does NOT appear in the API product list.
- **Offer code `UPGRADE20`** (20% off, universal) exists on Gumroad since 2026-09-01 — for follow-up emails only, never on the site.
- **Hugo** is installed via Homebrew (`hugo --minify` works here). Free/paid workbook sources + Gumroad copy live in `~/kdeskaccountingtemplates/templates/<slug>/`.
- **MailerLite token / dist/ binaries / Cloudflare tokens are on the Linux box only** (`ssh wsl`, Tailscale `100.112.159.5`) — unreachable 2026-09-01. Without it or a connected Chrome, MailerLite state can't be read or changed from here.
- **GSC/GA4 API pull is LIVE (2026-09-02).** Refresh token at `~/kdesk-analytics/google-token.json` (read-only Search Console + Analytics scopes on the `gws` Desktop client; both APIs enabled on GCP project `involuted-disk-489017-r3`). Manual run: `KDESK_SEO_SKIP_COMMIT=1 uv run scripts/pull_seo_snapshot.py`. The Monday block of `~/kdesk-analytics/kdesk-daily.sh` (launchd `com.kdesk.daily-sync`, 08:15) runs it and commits both snapshot files. If the token is ever revoked: `uv run scripts/setup_seo_oauth.py ~/.config/gws/client_secret.json` (Stephen signs in as santiagokdesk).
- **YouTube Data API is LIVE (2026-09-04).** Same token now carries `youtube.force-ssl` + `yt-analytics.readonly` (Stephen re-consented; `scripts/setup_seo_oauth.py` requests all four scopes). Channel **KDeskAccounting `UCmurE9-rT0C4NAZiYVR4HBw`**. `scripts/video/youtube_publish.py` uploads + sets thumbnail/metadata/playlist with no browser; `scripts/pull_youtube_snapshot.py` appends `marketing/seo-tracking/youtube-snapshots.jsonl` every Monday. **Gotcha:** API uploads from this un-audited GCP project are forced PRIVATE until the YouTube API compliance audit passes — flip to public in Studio meanwhile. `make_short.py --variant NAME` renders the named blocks under `shorts:` in each `scenes.yaml` (titles in `shorts.json`). Day-2 data: Shorts out-view long-form ~4:1 and 76% of views came from YouTube search.
- **Follow-up sequence + outreach drafts:** `marketing/email-sequences/free-download-followup.md`; 5 Gmail drafts created 2026-09-01 in santiagokdesk@gmail.com (not sent).
- **Video + cover pipeline** (`scripts/video/`, spec-driven): `scripts/video/.venv-tts/bin/python scripts/video/build_video.py --spec marketing/video/<slug>/scenes.yaml` (add `--frames-only` to preview, `--scenes N` to redo one) and `make_covers.py --spec …`. Six walkthroughs + posters live on GitHub release `media-2026-09`; product pages reference them via `video_url` / `video_poster`. Re-run when a workbook changes. Always `cd` to the repo root first (shell cwd drifts).
- **Gumroad file replacement works via API** (`~/kdeskaccountingtemplates/gumroad_files.py <product_id> <file> --swap`, presign flow) and bundles via `gumroad_bundle.py`; publish with `PUT /products/{id}/enable`. **Covers/thumbnails cannot be set via API** — Chrome extension only. `GET /products` hides the paid ASC 606 (`mwmwpe`) and the bundle.
- **Lean free files** are generated by `~/kdeskaccountingtemplates/make_lean_free.py` (inputs + schedule only, "Free vs Full" first tab) and are LIVE on Gumroad for ASC 842 / ASC 606 / SaaS Metrics / Fixed Assets (2026-09-01).

## Currently working on (resume here next session)

**State as of 2026-09-04 (evening).** Strategy pivoted (decision 51): the target is **$10,000/month**; the **$4,246/month safety net** (essential burn minus VA + Kaley income — the number that makes quitting the W-2 pressure-free) is the first milestone, **never the goal — Stephen rejected a plan that lowered the target.** Plan: `marketing/plan-2026-09-10k-portfolio.md`. Diagnosis: one distribution channel (Google, 1.07 clicks/day at position 28.9); the fix is more channels, not better SEO. ASC 842 software is off the table (LeaseGuru is free / $999 self-serve; the private-company wave was 2022). Lead cluster is now **ASC 606 + equity comp**.

**The five streams:** (A) RSU withholding-gap calculator → $99–149 workbook (tax mechanics only — no personalized sell/hold) · (B) faceless YouTube at volume · (C) affiliate/referral layer (FinQuery Referral Partner, Cradle) · (D) expert networks (GLG, AlphaSights, Guidepoint …) · (E) $1,997 ASC 606 commission kit. Gated on validation: a QuickBooks/Xero app. Ladder: $2k → **$4,246** → $10k; kill criteria per stream in the plan; portfolio review **2026-12-01** (if total revenue is still $0, stop building).

**Shipped 2026-09-04 evening (decisions 53–54):** YouTube Data API live (Stephen re-consented; APIs enabled); `scripts/video/youtube_publish.py` (no browser), `scripts/pull_youtube_snapshot.py` in the Monday job, `make_short.py --variant`; **12 new Shorts uploaded via the API — PRIVATE until flipped** (URLs in `marketing/video/*/shorts.json`); 17 tests (`uv run --with pytest pytest tests/`). First channel data: 206 views in ~48 h, 76% from YouTube search, Shorts ~4:1 over long-form. **Shipped 2026-09-05 (decision 55): the free RSU withholding-gap calculator at `/rsu-tax-calculator/`** — TDD'd tax core, 2026 table pinned to primary sources, second-agent fact-check FIX FIRST → all must-fixes applied, in the nav and homepage, sign-ups tagged `interest=rsu-planner`. Also drafted (not sent): the re-engagement email to the 14 skipped downloaders (`marketing/email-sequences/re-engage-2026-09.md`) and the affiliate applications (`marketing/affiliates/applications-2026-09.md`). **Staged 2026-09-05 (decision 56, T2): the RSU Tax Planner workbook, $149** — `~/kdeskaccountingtemplates/templates/rsu-planner/` (SPEC.md, build_v1.py, 7 LibreOffice-recalculated acceptance tests in `tests/test_rsu_planner.py`, validator clean), unpublished Gumroad listing `n5PlxijnuNvTLMOLryYCUw==` (`/l/dqqhk`) with the file attached, product page **draft** at `content/templates/rsu-planner/`, covers in `static/images/products/rsu-planner-*`, walkthrough `-rfZDelJQMY` + Short `nvp8_qt5-4g` uploaded private, mp4 on release `media-2026-09`, file + spec backed up to the KDesk Drive folder. **Gotcha:** `thumbnails.set` via the API returns 403 (channel lacks custom-thumbnail permission for API uploads) — the publisher now warns and keeps going; posters get set in Studio.

**Waiting on Stephen:**
1. **Flip the 12 new Shorts to public** — YouTube Studio → Content → Shorts → select the 12 private → Edit → Visibility → Public (~30 s). Repeat for API uploads until the audit passes.
2. **Submit the YouTube API Services compliance audit** (Google Support → "YouTube API Services – Audit and Quota Extension Form", project `involuted-disk-489017-r3`) — permanently lifts the forced-private restriction on API uploads.
3. **Repricing veto (decision 52):** ASC 842 $249 / bundle $599 / ASC 606 $249 executes after **2026-09-06 22:00 PT** unless he objects. **RSU Tax Planner veto (decision 56):** the $149 listing goes live, the page flips `draft: false`, and he flips the walkthrough (`-rfZDelJQMY`) and Short (`nvp8_qt5-4g`) public after **2026-09-07 08:00 PT** unless he objects — task #6.
4. Read IBM's outside-activities / conflict-of-interest policy → join 3–4 expert networks (Stream D).
5. VA 90% → 100% claim (+$1,083/mo tax-free, cuts the safety net 25%; do not touch the PTSD rating).
6. Reply on `marketing/outreach/batch-2026-09-07.md`; Reddit account; LinkedIn #17; free sign-ups (Eloquens, Featured.com, Source of Sources, Qwoted). *Done 2026-09-04: OAuth consent, the Bill Hanna DM, the customer-discovery emails.*
7. **Send the re-engagement email** to the 14 downloaders the nurture skipped — copy, recipients and merge fields in `marketing/email-sequences/re-engage-2026-09.md` (paste into a MailerLite campaign; API creation was blocked). **Submit the three affiliate applications** — `marketing/affiliates/applications-2026-09.md` (FinQuery Referral Partner first).
8. Gumroad "What's your role?" checkout question — the API accepts `custom_fields[]` and silently drops them; add it in the Gumroad editor (or via the CDP pattern) on the free listings.

**Next builds (Claude, in order):** publish the RSU Tax Planner when the veto closes (task #6) · a second RSU Short variant from the planner spec · ASC 606 kit assembly (technical memo template, PBC package) · Shorts at ~5/week · **execute repricing after the veto closes 2026-09-06 22:00 PT** (`gumroad_publish.py update`, decision 52) · port the product-specific `workflows.json` nurture copy into MailerLite via CDP · wire affiliate links + disclosure + `click_affiliate_outbound` once approvals arrive · product #6 (decision 50) only if it serves a stream.

**Weekly cadence (mechanics unchanged, new scoreboard):** Monday launchd pulls GSC + GA4 + target queries + Gumroad **+ YouTube**; the scoreboard adds subs, 28-day views and the Shorts/long-form split. **Always run the second-agent GAAP fact-check before publishing** (all four articles so far came back FIX FIRST). One LinkedIn draft per article; one outreach batch; nothing sends without Stephen.

**Recent decision context:** 42 GSC/GA4 OAuth · 44, 46, 49 the three commission/deferred-rent articles · 47 roadmap (superseded) · 48 Free-vs-Full · 50 product #6 research · **51 portfolio pivot · 52 repricing (veto open) · 53 YouTube API + publisher + weekly pull · 54 first Shorts batch (12, private) · 55 RSU calculator live · 56 RSU Tax Planner $149 staged (veto open).**

## Hard gates (never bypass)

1. CPA license claims: Stephen's WA license is **inactive**. Content must never imply active CPA practice/licensure or constitute tax advice.
2. CAE positioning: never imply CAE has clients, a waitlist, or is shippable until Stephen confirms. Currently building MVP.
3. Tax/legal/IRS correspondence: escalate to Stephen, never auto-respond.
4. Refunds and anything financial: Stephen-only.
5. Strategic pivots (channel ditch, ecosystem change): Stephen-only.

## History (condensed)

- **May 2026** — marketing foundation: email capture, GA4 key events, MailerLite wiring, decision log, marketing queues, lease-cluster SEO pass (traffic tripled by August).
- **2026-09-01** — conversion pass: dead upgrade links fixed, product CTAs + FAQ schema, six faceless walkthrough videos, lean free files, the $249 bundle, covers v2, the 3-email sequence.
- **2026-09-02** — Phase B and C: MailerLite welcome + free→paid automations active, daily sync, six YouTube walkthroughs, six Shorts, public playlist, native Gumroad bundle, ASC 842 pillar page, GSC/GA4 API pull live.
- **2026-09-03/04** — roadmap to $300/month adopted; target-query tracker; Free-vs-Full tables; three new articles; outreach program; product #6 research.

## Metrics I own  (report up to the Command Center COO report)

This project owns the funnel KPIs that roll into `~/CommandCenter/02-COO-Report.md` + `01-Dashboard.md`. The Monday pull is automated (launchd `com.kdesk.daily-sync`, 08:15); the roadmap's status table is the reporting surface.

**THE ONE metric: `paid_full_price` in `marketing/seo-tracking/gumroad-snapshots.jsonl`.** Still **0** lifetime. Everything else is a leading indicator of it. ($16.99 lifetime revenue is pay-what-you-want, not a sale.)

**The ladder beneath it, with current values (2026-09-04):**

| Metric | Source | Now | Where it needs to go |
|---|---|---|---|
| Organic sessions/day (7d avg) | GA4 `channels_7d.Organic Search` | ~8 | 12 → 20 → 30 |
| Free downloads / calendar month | Gumroad API | ~9 | 15 → 30 → 45 |
| Active email subscribers | MailerLite | 16 | 40 → 90 → 160 |
| Target queries on page 1 (of 24) | `target-query-positions.jsonl` | 2 | 5 by 10-31, 12 by 12-31 |
| Referring domains | manual / outreach log | ~0 | 10 by 2026-12-01 |
| Full-price sales / month | Gumroad API | 0 | 1 → 3 → 4+ |
| YouTube subs · 28d views · Shorts share of views | `youtube-snapshots.jsonl` | 0 · 75 · 87% | 1,000 subs + 4,000 watch-hours (monetization threshold) |
| Total recurring revenue, all streams | plan ladder | $0 | $2k → **$4,246 safety net** → $10k |

**What is vanity and must not be reported:** raw GA4 sessions and users (Direct is heavily bot: 2-second sessions, ~10 % engagement), GA4 revenue ($0 — Gumroad sits outside GA4), and raw key-event counts.

**Action triggers** are the stream kill criteria and the $2k → $4,246 → $10k ladder in `marketing/plan-2026-09-10k-portfolio.md`. The ones that need Stephen: a **business-domain download** (draft him a personal note), any **T2 pricing change**, and the **2026-12-01 portfolio review** (stop building if total revenue across all streams is still $0).

**Known gaps:** the blog→CAE handoff is still manual; MailerLite automation open/click rates are read by hand monthly; Gumroad's UPGRADE20 usage has no API export.
