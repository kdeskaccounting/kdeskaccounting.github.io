> 🧭 **Command Center vault** — Stephen's context, goals, and decisions live in `~/CommandCenter` (this is a Mac; the `/mnt/c/` and `/home/kdeskconsulting/` paths in older notes are the Windows/Linux machines). Relevant note: `02-Projects/KDesk-Blog.md`. See `_meta/CLAUDE.md`; global rules in `~/.claude/CLAUDE.md`.

# CLAUDE.md — KDesk Accounting blog

## Read first, every session

1. **`marketing/roadmap-2026-09.md`** — the living plan: milestone triggers M0–M3, the 12-week calendar, the ranking program, guardrails. Its status table is updated every Monday. This supersedes `OPERATIONS_PLAN.md` (May 2026, historical).
2. `decisions/decisions.jsonl` — append-only ledger; every autonomous action is logged. Currently at #50.
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
- `content/about/`, `content/search/` — standard pages

## Custom layouts (the bits to know)

- `layouts/_default/single.html` — overrides PaperMod theme. Renders the email-capture partial AFTER content on posts only (not on /templates/, /calculator/, /about/).
- `layouts/partials/email_capture.html` — the inline email form. Posts to MailerLite. Excluded from non-posts pages.
- `layouts/partials/extend_head.html` — global `<head>` injections: Cloudflare Analytics beacon, MailerLite Universal script, GA4 Key Event handler (Gumroad outbound clicks, calculator opens, template page views), JSON-LD schema.
- `layouts/index.html`, `layouts/templates/`, `layouts/calculator/` — custom homepage + product pages + calculator.

## Marketing infrastructure (queues, not auto-posters)

- `marketing/roadmap-2026-09.md` — **the plan**. Milestone triggers, 12-week calendar, ranking program, guardrails.
- `marketing/linkedin-queue/` — 3-line post drafts, one per article. Stephen pastes; #17 and #18 are queued. Never posted autonomously.
- `marketing/outreach/` — `targets.md` (15 researched link targets, Bill Hanna at Controller Academy first), dated batch files, and the Bill Hanna note. **Nothing sends until Stephen replies with the numbers.**
- `marketing/reddit-templates/` — comment templates plus `00-account-setup.md` (Stephen creates and ages the account; no links for three weeks; never link in r/Accounting).
- `marketing/video/` — walkthrough specs, Shorts specs (`short:` blocks), YouTube URLs, plus `stephen-clips/` scripts for his monthly 60–90 s clip.
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
- **MailerLite API**: token `kdesk-mac-sync` at `~/kdesk-analytics/mailerlite-token.txt`; group "Gumroad free downloaders" `187224670039180750`
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

**State as of 2026-09-04.** The build phase is done; this is now a weekly operating cadence driven by `marketing/roadmap-2026-09.md`.

**Where the funnel actually is:** 0 full-price sales lifetime ($16.99 from pay-what-you-want), ~9 free downloads/month, ~8 organic sessions/day, 16 active email subscribers, 24 tracked buying queries with 2 on page 1. The measured page-1 ceiling on today's query set is ~$350–530/month, so ranking alone does not reach $300; cluster expansion and the free→paid nurture supply the rest.

**Weekly cadence (Claude owns unless noted):**
- **Monday:** the launchd job at 08:15 appends GSC + GA4 + target-query rows (and Gumroad on Mondays). Post a 5-line scoreboard to the vault daily note, update the roadmap status table, and state which triggers are live.
- **One fact-checked article/week** from the 12-week calendar. **Always run a second-agent GAAP fact-check before publishing** — all four articles so far came back FIX FIRST with real citation or judgment errors.
- **One site/product improvement/week** from the always-on backlog.
- **One 3-line LinkedIn draft per article** in `marketing/linkedin-queue/` (Stephen pastes; #17 and #18 are queued).
- **One outreach batch (~5)** in `marketing/outreach/`; nothing sends until Stephen replies with the numbers.

**Waiting on Stephen (nothing else is blocked):**
1. DM Bill Hanna at Controller Academy — draft ready in `marketing/outreach/controller-academy-bill-hanna.md`. Warm contact (former customer at Forter), ~340k YouTube subscribers, no ASC 842 or commission content on his blog. Highest-value link target by a distance.
2. Reply "send 2, 3, 4, 5" (or a subset) on `marketing/outreach/batch-2026-09-07.md`.
3. Create the Reddit account per `marketing/reddit-templates/00-account-setup.md`, then 2 comment pastes/week.
4. Record clip #1: script at `marketing/video/stephen-clips/01-deferred-rent-gap.md`.
5. Free sign-ups whose copy is written: Eloquens, Featured.com, Source of Sources, Qwoted.

**Next builds, in order (`marketing/product-6-research.md`, decision 50):** Balance Sheet Reconciliation Pack $49 first — the free close checklist is our most-downloaded file and has no paid upgrade, so this converts traffic we already have. Then the Deferred Revenue Schedule Workbook $79 once its cluster proves demand (free-file probe scheduled for the week of 09-14). Both gated on the M2 trigger.

**Recent decision context:** 37–41 Phase C (GSC pull, ASC 842 pillar, six Shorts, playlist, native Gumroad bundle) · 42 GSC/GA4 OAuth live · 43, 45 title alignment · 44, 46, 49 the deferred-rent and two commission articles · 47 roadmap adopted · 48 Free-vs-Full comparison tables · 50 product #6 research.

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

**What is vanity and must not be reported:** raw GA4 sessions and users (Direct is heavily bot: 2-second sessions, ~10 % engagement), GA4 revenue ($0 — Gumroad sits outside GA4), and raw key-event counts.

**Action triggers** are the milestone ladder in `marketing/roadmap-2026-09.md`. The two that need Stephen: a **business-domain download** (draft him a personal note — this is the blog→CAE handoff) and any **T2 pricing test**. Kill/pivot review is 2026-12-01 if there are 0 sales despite ≥ 40 downloads and ≥ 12 organic/day.

**Known gaps:** the blog→CAE handoff is still manual; MailerLite automation open/click rates are read by hand monthly; Gumroad's UPGRADE20 usage has no API export.
