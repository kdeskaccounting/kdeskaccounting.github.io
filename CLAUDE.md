> 🧭 **Command Center vault** — Stephen's context, goals, and decisions live in `~/CommandCenter` (this is a Mac; the `/mnt/c/` and `/home/kdeskconsulting/` paths in older notes are the Windows/Linux machines). Relevant note: `02-Projects/KDesk-Blog.md`. See `_meta/CLAUDE.md`; global rules in `~/.claude/CLAUDE.md`.

# CLAUDE.md — KDesk Accounting blog

## Read first, every session

1. **`marketing/plan-2026-09-10k-portfolio.md`** — the plan (decision 51, 2026-09-04): target **$10,000/mo**, the **$4,246/mo safety net** as the first milestone, five streams on five channels, kill criteria per stream. `marketing/roadmap-2026-09.md` ($300/mo) is superseded — its weekly cadence, fact-check rule and guardrails still apply where they don't conflict. `OPERATIONS_PLAN.md` (May 2026) is historical.
2. **`marketing/plan-2026-09-14-automation.md`** — the automation plan (2026-09-14, ledger #69–#71): how the plan of record above gets executed with less of Stephen's time (< 30 min/wk), plus a **second, separate brand** (`parksheet`, a subscription living Google Sheet). It does **not** replace the revenue plan of record. Its session runbook is **`marketing/runbooks/automation-2026-09.md`** — pipeline map, one command per stage, current phase, open vetoes, the "if X is broken do Y" table, and (Phase 1, 2026-09-15) the two GitHub Actions schedules: what runs on Actions, what only runs on the Mac and why, the exact `gh secret set` commands, the launchd handover, and the weekly selector canary. Read both before touching publishing, the video pipeline, or the venture.
3. `decisions/decisions.jsonl` — append-only ledger; every autonomous action is logged. Currently at **#71**. **#52 repricing executed 2026-09-06 (decision 61): ASC 842 $249 · ASC 606 $249 · bundle $599.** Open veto windows: **#69 marketing autonomy → T1 auto-publish** and **#70 the `parksheet` venture**, both closing **2026-09-16 12:00 PT**. **#71 (T0, executed): the 20 API-uploaded YouTube videos are locked private and must be re-uploaded — see "Credentials & external state".**
4. `~/CommandCenter/02-Projects/KDesk-Blog.md` — the vault MOC: status, next action, blockers. The venture has its own MOC, `~/CommandCenter/02-Projects/ParkSheet.md`.
5. **`marketing/runbooks/veto-executions-2026-09.md`** — step-by-step runbooks for the approved T2 actions whose veto windows close 2026-09-06/07 (repricing, RSU planner publish, ASC 340-40 kit publish) and the Monday scoreboard. In-session timers exist only while the session that set them is alive — a new session executes from the runbook.
6. The **Currently working on** section below.

## What this is

A Hugo + PaperMod static site at **https://kdeskaccounting.com**. Stephen is a CPA (10+ years sales-comp accounting, ex-CaptivateIQ). The site sells Excel templates on Gumroad ($49–249 each; $599 bundle; a $149 RSU planner and a $1,997 commission kit staged) and feeds an email list that compounds into the bigger 2026 plays (CAE → tax practice).

## Architecture

- **Framework:** Hugo (extended, 0.147+), PaperMod theme (submodule under `themes/PaperMod/`)
- **Hosting:** GitHub Pages from `kdeskaccounting/kdeskaccounting.github.io` repo
- **Domain:** kdeskaccounting.com (Cloudflare DNS, NOT proxied — resolves to GH Pages IPs)
- **CNAME:** `static/CNAME` → `kdeskaccounting.com`
- **Deploy:** push to `main` → GH Actions `.github/workflows/deploy.yml` → live in ~30s
- **Scheduled Actions:** `data-weekly.yml` (Mon 15:15 UTC — the four snapshot pulls + a CRM dry run, commits the JSONL rows) and `daily-publish.yml` (14:00 UTC — publishes the day's asset from the newest `media-daily-*` release, digest into the run summary). Shape pinned by `tests/test_workflows.py`; secrets and the Mac-only list are in `marketing/runbooks/automation-2026-09.md`.
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
  - **PENDING #69 (T2, veto closes 2026-09-16 12:00 PT) — T1 is widening.** Once the window closes unvetoed, **YouTube Shorts, TikTok, Instagram Reels, blog posts and email nurture sends become T1 auto-publish**, each gated on a **mandatory second-agent fact-check that must return PASS** (any FIX FIRST blocks the entire week's batch, not just the item). **LinkedIn and Reddit stay human-in-the-loop** — their publishers write queue cards only. Publishing routes through Upload-Post, never `youtube_publish.py` (#71). Until 2026-09-16 the old rule holds: **queues, not auto-posters.** Details: `marketing/plan-2026-09-14-automation.md` Track 2; runbook `marketing/runbooks/automation-2026-09.md`. **#70** (same window) approves the separate `parksheet` venture.
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
- **Bing Webmaster**: API key at `~/kdesk-analytics/bing-api-key.txt` (Stephen creates it: bing.com/webmasters → import from GSC → Settings → API Access). **Bing is the bigger search channel** — 2026-09-11 GA4 14d: bing/organic 105 sessions / 50 engaged vs google/organic 29 / 13. GSC is Google-only, so the scoreboard was blind to it.
- **GSC + GA4**: refresh token at `~/kdesk-analytics/google-token.json` (read-only scopes on the `gws` Desktop client; both APIs enabled on GCP project `involuted-disk-489017-r3`). GA4 property `528583005`.
- **Google Workspace** (`gws` CLI): authed as `santiagokdesk@gmail.com` — NOT smichels1@gmail.com
- **Search Console**: verified by DNS TXT (`google-site-verification=bJlwcW0aYXafivvCsvcRhgyE2UiLDwwF6WIteYQqaEU`)
- **YouTube uploads — DO NOT USE `scripts/video/youtube_publish.py` (verified 2026-09-14, ledger #71).** Uploads from this un-audited GCP project (`involuted-disk-489017-r3`) are **locked private, permanently**. The lock **cannot be appealed and cannot be flipped in YouTube Studio**; per Google support article 7300965 the affected videos **must be re-uploaded**. Passing the compliance audit only unlocks *future* uploads — it does not free the existing ones. Proof: all **20** videos the API uploaded 2026-09-05/09-07 are `private` with **0 views** in `marketing/seo-tracking/youtube-snapshots.jsonl` (2026-09-07), while the 10 uploaded through Chrome on 2026-09-02 are `public` and carrying views. **No uploads via the Data API until the audit passes**; re-upload the 20 via Upload-Post (holds audited credentials) or manually in Chrome. Read-only Data API use (`scripts/pull_youtube_snapshot.py`) is unaffected.
- **Debug Chrome** for UI-only work (Gumroad covers, MailerLite editor, manual YouTube uploads): Stephen launches with `--remote-debugging-port=9222`, profile `~/.kdesk/chrome-debug`; drive it with `scripts/video/cdp.py` or Playwright `connect_over_cdp`
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
uv run scripts/pull_bing_snapshot.py --print                    # Bing clicks/impressions/queries (Mondays; needs ~/kdesk-analytics/bing-api-key.txt)

# Render a named Short (safe — rendering is local and unaffected)
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug asc842 --variant liability

# DO NOT RUN — youtube_publish.py uploads land LOCKED PRIVATE and cannot be recovered (ledger #71).
# Anything it uploads is dead on arrival: no appeal, no Studio flip, re-upload is the only fix.
# uv run scripts/video/youtube_publish.py --kind short --slug asc842 --variant liability
# Publish through Upload-Post instead (Phase 1), or upload manually in the debug Chrome.

# List the 20 locked-private videos, whether each mp4 is ready, and re-upload once UPLOAD_POST_KEY exists (zero writes with --dry-run)
python3 scripts/video/reupload_locked.py --dry-run
```

## Mac-side notes (added 2026-09-01 — this repo is now worked from the Mac too)

- **Gumroad API** (read + write): token in `~/kdeskaccountingtemplates/.env` (`GUMROAD_ACCESS_TOKEN`). CLI: `python3 ~/kdeskaccountingtemplates/gumroad_publish.py list|sales`. Weekly money-metric pull: `python3 scripts/pull_gumroad_snapshot.py` → `marketing/seo-tracking/gumroad-snapshots.jsonl`. Note: the paid ASC 606 product (`mwmwpe`) is live but does NOT appear in the API product list.
- **Offer code `UPGRADE20`** (20% off, universal) exists on Gumroad since 2026-09-01 — for follow-up emails only, never on the site. **`HANNAREVIEW`** (100% off, 3 uses) on the ASC 842 workbook for Bill Hanna (2026-09-06). **The paid ASC 606 listing's API id is `SDeZYs5lEMPdbBtb9kL4lg==`** (hidden from `GET /products`; recovered from the editor page via CDP).
- **Hugo** is installed via Homebrew (`hugo --minify` works here). Free/paid workbook sources + Gumroad copy live in `~/kdeskaccountingtemplates/templates/<slug>/`.
- **MailerLite token / dist/ binaries / Cloudflare tokens are on the Linux box only** (`ssh wsl`, Tailscale `100.112.159.5`) — unreachable 2026-09-01. Without it or a connected Chrome, MailerLite state can't be read or changed from here.
- **GSC/GA4 API pull is LIVE (2026-09-02).** Refresh token at `~/kdesk-analytics/google-token.json` (read-only Search Console + Analytics scopes on the `gws` Desktop client; both APIs enabled on GCP project `involuted-disk-489017-r3`). Manual run: `KDESK_SEO_SKIP_COMMIT=1 uv run scripts/pull_seo_snapshot.py`. The Monday block of `~/kdesk-analytics/kdesk-daily.sh` (launchd `com.kdesk.daily-sync`, 08:15) runs it and commits both snapshot files. If the token is ever revoked: `uv run scripts/setup_seo_oauth.py ~/.config/gws/client_secret.json` (Stephen signs in as santiagokdesk).
- **YouTube Data API: READ-ONLY USE ONLY (corrected 2026-09-14, ledger #71).** Same token carries `youtube.force-ssl` + `yt-analytics.readonly` (Stephen re-consented; `scripts/setup_seo_oauth.py` requests all four scopes). Channel **KDeskAccounting `UCmurE9-rT0C4NAZiYVR4HBw`**. `scripts/pull_youtube_snapshot.py` appends `marketing/seo-tracking/youtube-snapshots.jsonl` every Monday — that still works. **`scripts/video/youtube_publish.py` is DO-NOT-USE for uploads until the audit passes.** The earlier note here ("forced PRIVATE … flip to public in Studio meanwhile") was **wrong and cost 20 videos**: uploads from an un-audited GCP project are **locked** private — Google support article 7300965 says the lock **cannot be appealed**, Studio will not change it, and the videos **must be re-uploaded**. Verified against the 2026-09-07 snapshot: the 20 API uploads are `private` / 0 views, the 10 Chrome uploads from 09-02 are `public` with views. Passing the audit only unlocks future uploads. Route publishing through **Upload-Post** (audited credentials) or upload manually in the debug Chrome; re-upload the 20 in Phase 1. Related gotcha, now moot for API uploads: `thumbnails.set` returns 403 (channel lacks custom-thumbnail permission for API uploads). `make_short.py --variant NAME` renders the named blocks under `shorts:` in each `scenes.yaml` (titles in `shorts.json`) and is unaffected. Day-2 data (from the working Chrome-uploaded batch): Shorts out-view long-form ~4:1 and 76% of views came from YouTube search.
- **Follow-up sequence + outreach drafts:** `marketing/email-sequences/free-download-followup.md`; 5 Gmail drafts created 2026-09-01 in santiagokdesk@gmail.com (not sent).
- **Video + cover pipeline** (`scripts/video/`, spec-driven): `scripts/video/.venv-tts/bin/python scripts/video/build_video.py --spec marketing/video/<slug>/scenes.yaml` (add `--frames-only` to preview, `--scenes N` to redo one) and `make_covers.py --spec …`. Six walkthroughs + posters live on GitHub release `media-2026-09`; product pages reference them via `video_url` / `video_poster`. Re-run when a workbook changes. Always `cd` to the repo root first (shell cwd drifts).
- **Gumroad file replacement works via API** (`~/kdeskaccountingtemplates/gumroad_files.py <product_id> <file> --swap`, presign flow) and bundles via `gumroad_bundle.py`; publish with `PUT /products/{id}/enable` — **the `gumroad_publish.py publish` command prints success without flipping the flag (2026-09-07); use `/enable` and re-read `published`.** **Covers/thumbnails cannot be set via API** — Chrome extension only. `GET /products` hides the paid ASC 606 (`mwmwpe`) and the bundle.
- **Lean free files** are generated by `~/kdeskaccountingtemplates/make_lean_free.py` (inputs + schedule only, "Free vs Full" first tab) and are LIVE on Gumroad for ASC 842 / ASC 606 / SaaS Metrics / Fixed Assets (2026-09-01).

## Currently working on (resume here next session)

**State as of 2026-09-04 (evening).** Strategy pivoted (decision 51): the target is **$10,000/month**; the **$4,246/month safety net** (essential burn minus VA + Kaley income — the number that makes quitting the W-2 pressure-free) is the first milestone, **never the goal — Stephen rejected a plan that lowered the target.** Plan: `marketing/plan-2026-09-10k-portfolio.md`. Diagnosis: one distribution channel (Google, 1.07 clicks/day at position 28.9); the fix is more channels, not better SEO. ASC 842 software is off the table (LeaseGuru is free / $999 self-serve; the private-company wave was 2022). Lead cluster is now **ASC 606 + equity comp**.

**The five streams:** (A) RSU withholding-gap calculator → $99–149 workbook (tax mechanics only — no personalized sell/hold) · (B) faceless YouTube at volume · (C) affiliate/referral layer (FinQuery Referral Partner, Cradle) · (D) expert networks (GLG, AlphaSights, Guidepoint …) · (E) $1,997 ASC 606 commission kit. Gated on validation: a QuickBooks/Xero app. Ladder: $2k → **$4,246** → $10k; kill criteria per stream in the plan; portfolio review **2026-12-01** (if total revenue is still $0, stop building).

**Shipped 2026-09-04 evening (decisions 53–54):** YouTube Data API live (Stephen re-consented; APIs enabled); `scripts/video/youtube_publish.py` (no browser), `scripts/pull_youtube_snapshot.py` in the Monday job, `make_short.py --variant`; **12 new Shorts uploaded via the API — ~~PRIVATE until flipped~~ LOCKED private, unrecoverable, must be re-uploaded (#71)** (URLs in `marketing/video/*/shorts.json`); 17 tests (`uv run --with pytest pytest tests/`). First channel data: 206 views in ~48 h, 76% from YouTube search, Shorts ~4:1 over long-form. **Shipped 2026-09-05 (decision 55): the free RSU withholding-gap calculator at `/rsu-tax-calculator/`** — TDD'd tax core, 2026 table pinned to primary sources, second-agent fact-check FIX FIRST → all must-fixes applied, in the nav and homepage, sign-ups tagged `interest=rsu-planner`. Also drafted (not sent): the re-engagement email to the 14 skipped downloaders (`marketing/email-sequences/re-engage-2026-09.md`) and the affiliate applications (`marketing/affiliates/applications-2026-09.md`). **Staged 2026-09-05 (decision 56, T2): the RSU Tax Planner workbook, $149** — `~/kdeskaccountingtemplates/templates/rsu-planner/` (SPEC.md, build_v1.py, 7 LibreOffice-recalculated acceptance tests in `tests/test_rsu_planner.py`, validator clean), unpublished Gumroad listing `n5PlxijnuNvTLMOLryYCUw==` (`/l/dqqhk`) with the file attached, product page **draft** at `content/templates/rsu-planner/`, covers in `static/images/products/rsu-planner-*`, walkthrough `-rfZDelJQMY` + Short `nvp8_qt5-4g` uploaded private **(locked — re-upload, #71)**, mp4 on release `media-2026-09`, file + spec backed up to the KDesk Drive folder. **Gotcha:** `thumbnails.set` via the API returns 403 (channel lacks custom-thumbnail permission for API uploads) — the publisher now warns and keeps going; posters get set in Studio. **Staged 2026-09-05 (decision 57, T2): the ASC 340-40 Commission Capitalization Kit, $1,997 (Stream E)** — `~/kdeskaccountingtemplates/templates/asc606-kit/` (SPEC.md, `build_kit.py` → six DOCX+PDF from the fact-checked commission posts + the ASC 606 workbook + README in a zip; 22 tests), unpublished Gumroad listing `JDJrWvrxH8JMkQ2fbBKS2g==` (`/l/tngbwg`) with the zip attached, product page **draft** at `content/templates/asc606-kit/`, covers `static/images/products/asc606-kit-*`, zip + spec on Drive. **Fact-check done (decision 58): FIX FIRST → all 7 must-fixes + 9 nice-to-haves applied, Kit v1.1 re-attached, 23 tests green; publishes when the veto closes** (runbook §3).

**Waiting on Stephen:**
1. **Approve or veto #69 and #70 by 2026-09-16 12:00 PT.** #69 = marketing autonomy loosened to T1 auto-publish (Shorts/TikTok/Reels/blog/email) behind a mandatory fact-check gate, LinkedIn + Reddit still manual. #70 = launching the separate `parksheet` subscription-sheet venture (30-day test first, < $100). Silence = approval; say the word and either is reverted with no work lost. *(The old item here — "flip the 12 new Shorts to public in Studio" — was impossible and has been removed: those uploads are locked, see ledger #71.)*
2. **Create an Upload-Post account and connect the KDesk YouTube channel** (free tier = 10 uploads/mo, covers YouTube + Instagram; TikTok needs the paid plan ~$16–24/mo). It holds audited credentials, which is what unblocks publishing at all. This is the gate on Phase 1.
3. **Create the venture's accounts** (only if #70 is not vetoed): a **new Google account** to own the Sheet/YouTube channel/Gumroad login, a **separate Gumroad account** (Lemon Squeezy is the fallback if Gumroad refuses a second), and **TikTok + Instagram professional accounts** — then connect all of them to Upload-Post. Nothing KDesk-branded touches this brand.
4. **Mint a Cloudflare API token** (Workers + D1 edit) for the `gumroad-ping` membership-sync Worker — the old tokens were on the dead Linux box.
5. **Submit the YouTube API Services compliance audit** (Google Support → "YouTube API Services – Audit and Quota Extension Form", project `involuted-disk-489017-r3`). Note what this does and does not do: it unlocks **future** API uploads only — it does **not** free the 20 already-locked videos, which must be re-uploaded regardless (#71).
6. ~~Repricing veto (decision 52)~~ **Executed 2026-09-06 22:20 PT (decision 61): ASC 842 $249, ASC 606 $249, bundle $599 (list $693).** **RSU Tax Planner — LIVE 2026-09-07 08:30 PT (decision 63)** at `/templates/rsu-planner/` and `/l/dqqhk`; ~~Stephen flips `-rfZDelJQMY`, `nvp8_qt5-4g`, `PUNOPlq4s08`, `dMEWoIS5DXw` public.~~ **Not possible — all four are API uploads and are locked private (#71); they must be re-uploaded.** **Commission Kit veto (decision 57):** the $1,997 listing goes live and its page publishes after **2026-09-07 11:00 PT** unless he objects — and only once the six documents' fact-check has passed (task #7).
7. Read IBM's outside-activities / conflict-of-interest policy → join 3–4 expert networks (Stream D).
8. VA 90% → 100% claim (+$1,083/mo tax-free, cuts the safety net 25%; do not touch the PTSD rating).
9. Reply on `marketing/outreach/batch-2026-09-07.md`; Reddit account; LinkedIn #17; free sign-ups (Eloquens, Featured.com, Source of Sources, Qwoted). *Done 2026-09-04: OAuth consent, the Bill Hanna DM, the customer-discovery emails.*
10. **Send the re-engagement email** to the 14 downloaders the nurture skipped — copy, recipients and merge fields in `marketing/email-sequences/re-engage-2026-09.md` (paste into a MailerLite campaign; API creation was blocked). **Submit the three affiliate applications** — `marketing/affiliates/applications-2026-09.md` (FinQuery Referral Partner first).
11. Gumroad "What's your role?" checkout question — the API accepts `custom_fields[]` and silently drops them; add it in the Gumroad editor (or via the CDP pattern) on the free listings.

**Next builds (Claude, in order):** apply the kit fact-check fixes → rebuild → re-attach (task #7) · publish the RSU Tax Planner (task #6) and then the kit when their vetoes close · cross-link the kit from the three commission posts and the ASC 606 page once live · more Shorts from the planner spec · Shorts at ~5/week · **execute repricing after the veto closes 2026-09-06 22:00 PT** (`gumroad_publish.py update`, decision 52) · port the product-specific `workflows.json` nurture copy into MailerLite via CDP · wire affiliate links + disclosure + `click_affiliate_outbound` once approvals arrive · product #6 (decision 50) only if it serves a stream.

**Weekly cadence (mechanics unchanged, new scoreboard):** Monday launchd pulls GSC + GA4 + target queries + Gumroad **+ YouTube**; the scoreboard adds subs, 28-day views and the Shorts/long-form split. **Always run the second-agent GAAP fact-check before publishing** (all four articles so far came back FIX FIRST). One LinkedIn draft per article; one outreach batch; nothing sends without Stephen.

**Recent decision context:** 42 GSC/GA4 OAuth · 44, 46, 49 the three commission/deferred-rent articles · 47 roadmap (superseded) · 48 Free-vs-Full · 50 product #6 research · **51 portfolio pivot · 52 repricing (veto open) · 53 YouTube API + publisher + weekly pull · 54 first Shorts batch (12, private) · 55 RSU calculator live · 56 RSU Tax Planner $149 staged (veto open) · 57 ASC 340-40 Commission Kit $1,997 staged (veto open) · 58 kit fact-check applied (v1.1).**

## Privacy (this repo is PUBLIC)

`github.com/kdeskaccounting/kdeskaccounting.github.io` is public. Everything tracked here is
world-readable, forever, including in history.

**Never commit a third-party email address, name+address pair, or any other customer contact
detail.** KDesk's own published addresses (`santiagokdesk@`, `@kdeskaccounting.com`) are fine —
they are meant to be findable. This is enforced, not just advised: `tests/test_no_third_party_emails.py`
scans every tracked file under `marketing/ decisions/ content/ scripts/ tests/` and fails on any
address that is not KDesk-own or an RFC 2606 reserved domain (`example.com`, `*.example`, `*.test`,
`*.invalid`). Its `ALLOWED_LITERALS` set is deliberately tiny — if you find yourself adding to it,
use a reserved domain instead.

**Where personal data lives:** `~/kdesk-analytics/private/` (dir `0700`, files `0600`), outside the
repo and never synced to git.

- `re-engage-2026-09-recipients.json` — the 14 re-engagement recipients (subscriber id, address,
  product, merge fields) plus 1 excluded. **Task 7's `send_reengage.py` reads recipients from here,
  never from the markdown.**
- `outreach-contacts.json` — outreach addresses keyed by target org/person.
- `redaction-map-2026-09-14.json` — `redaction_id -> address`, so an in-place redaction is reversible.

**The hashing scheme** (`scripts/privacy.py`): a salted SHA-256, salt at
`~/kdesk-analytics/email-hash-salt.txt` (`0600`, created on first use). Plain SHA-256 would be
reversible here — the population "people who bought an accounting template" is small enough to
enumerate — so the salt is what makes a digest a pseudonym rather than an encoding.

- State files store `email_sha256` (full digest). `scripts/sync_gumroad_to_mailerlite.py` dedupes on it.
- Prose and tables store a `<redacted:XXXXXXXX>` marker — the first 8 hex of the digest — which keeps
  a row joinable to the private files without naming anyone.
- **Back the salt up.** Lose it and every stored digest stops matching: past downloaders look new, and
  the daily sync could re-trigger the 3-email automation to real customers.

**Pending Stephen's decision:** rewriting git history to purge the addresses already committed
(ledger 76, 77). Until he decides, they remain in history, in every clone and in any fork — containment
stops new leaks, it does not undo old ones. Do not rewrite history or force-push on your own.

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
