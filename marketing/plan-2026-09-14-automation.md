<!-- Approved automation plan of 2026-09-14 (source: ~/.claude/plans/i-just-airdropped-a-ticklish-toucan.md). -->
<!-- Verbatim copy; the original plan file is the spec and is not edited here. -->
<!-- `marketing/plan-2026-09-10k-portfolio.md` remains the revenue plan of record ($10k/mo, five streams, portfolio review 2026-12-01); this plan is how that plan gets executed and adds a second brand. -->

# Automate KDesk product, marketing, and sales + launch a subscription-sheet venture

**Date:** 2026-09-14 · **Source:** airdropped TikTok "Google Sheets/Docs made me $103,765 in 2025" (creator "jackson", 4 min) · **Owner:** Claude Code (Fable orchestrates, Opus subagents build) · **Stephen's time target after setup:** < 30 min/week

---

## Context

Stephen watched a creator explain how a living Google Sheet, sold as a cheap monthly membership and marketed with one short faceless video a day, became recurring five-figure monthly income. He sees the overlap with KDesk Accounting and asked for a plan that borrows the concepts and automates product, marketing, and sales as far as possible, outsourcing heavy work to Opus subagents.

KDesk today (verified 2026-09-14 from `~/CommandCenter` and `~/kdeskaccounting.github.io`): eight one-off Gumroad workbooks ($149–$1,997), a Hugo site, MailerLite nurture, a spec-driven faceless video factory (`scripts/video/`), Monday analytics pulls on launchd, a T0–T3 autonomy ledger, and **$16.99 lifetime revenue with zero full-price sales**. Every post and send still waits on Stephen ("queues, not auto-posters"). Plan of record is `marketing/plan-2026-09-10k-portfolio.md` ($10k/mo target, $4,246/mo safety-net milestone, five streams A–E, portfolio review 2026-12-01).

### What the video teaches, and what transfers

| Video concept | Transfers to KDesk? | How this plan uses it |
|---|---|---|
| Product = a living Google Sheet, shared by **view link**, not a download | Partly. KDesk's buyers want the Excel file. | Keep KDesk workbooks one-off. Use the living-sheet model for the **new venture** (Track 1B). |
| Sell it as a **subscription** on Gumroad ($4–90/mo), zero fixed cost | Yes, Gumroad memberships exist and Stephen already has the API. | Venture launches at $5–9/mo on Gumroad; Stan/Lemon Squeezy is the documented escape hatch at scale. |
| Validate the idea from your own best content or **Google Trends** | Yes. | Niche research (below) + `trendspyg` for weekly trend pulls; Bing/GSC/YouTube data seed KDesk's topics. |
| **Give part away free**; the weekly update is the content | Yes, and it is the answer to the earlier rejection of a "$29/mo content treadmill": if a script writes the update and the update *is* the day's video, the treadmill is automated. | Free public mirror of part of the sheet + free lean workbooks; every weekly diff seeds 7 Shorts + 1 post. |
| **Post a 7–59 s video every day**, faceless is fine | Yes, the pipeline exists; the missing piece is autonomous multi-platform publishing. | Track 2 builds the daily engine and loosens autonomy to T1 (Stephen's choice). |
| Consumer scale (3,000 subs × $4) | **No** for KDesk (B2B, tiny audience). | KDesk prices for prosumer scale; the venture picks a consumer niche with a real free/paid gap. |

### Decisions Stephen made today (AskUserQuestion, 2026-09-14)

1. **Autonomy:** auto-publish YouTube Shorts, TikTok, Instagram Reels, blog posts, and email nurture after the fact-check gate (T1, daily digest). **LinkedIn and Reddit stay human-in-the-loop.** This is a T2 change to the ledger rules and gets its own decision note.
2. **Product model:** adopt the living-sheet subscription as a **new stream**, but Stephen wants it **distinct from KDesk Accounting**, in a high-demand / low-supply niche the plan picks ("personal finance, likely crowded, or video games, or whatever"). So it is a **separate venture** that shares KDesk's automation engine, not Stream F inside KDesk.
3. **Platforms:** YouTube Shorts, TikTok, Instagram Reels (not LinkedIn video).

### Critical finding: the API-uploaded YouTube videos are dead

Verified 2026-09-14 against Google's help page (support.google.com/youtube/answer/7300965) and the 2026-09-07 snapshot in `marketing/seo-tracking/youtube-snapshots.jsonl`: all **20 videos uploaded via the Data API since 2026-09-05 are locked private with 0 views**; the 10 uploaded through Chrome on 2026-09-02 are public and getting views. Google: locked-private uploads from an unverified API project **cannot be appealed and must be re-uploaded**. Passing the audit only unlocks future uploads. The "flip in Studio" step in the repo's CLAUDE.md never worked. **Action in Phase 1:** stop `youtube_publish.py` uploads; re-upload the 20 files through a scheduler that holds audited credentials (Upload-Post) or manually; update CLAUDE.md and the ledger.

---

## Architecture: one engine, two brands

```
spec (YAML/JSON)  ──►  PRODUCT  ──►  weekly changelog  ──►  MARKETING  ──►  publishers  ──►  SALES/CRM  ──►  digest
  KDesk: templates/<slug>/SPEC.md      changelog/YYYY-WW.json   plan_week → factcheck → render   youtube/tiktok/ig via   CRM sheet, nurture,   Gmail to Stephen +
  Venture: sheet/spec.yaml + data pulls                          (Opus)      (Opus)     (Mac)     Upload-Post; site; email   drafts, churn sync   vault daily note
```

- **Scheduler:** GitHub Actions for deterministic scripts (always on; the Mac is not; the Linux box is gone). One Claude Code scheduled routine (cloud) for the two LLM steps (weekly planning + fact-check). Rendering stays on the Mac in one weekly batch pushed to a GitHub release; publishing reads from the release, so a sleeping Mac never breaks the daily cadence.
- **Publishing:** **Upload-Post** (researched 2026-09-14: free tier 10 uploads/mo covers IG + YouTube; TikTok needs the paid plan, ~$16–24/mo). It holds audited YouTube/TikTok/Meta credentials, which sidesteps the YouTube audit and TikTok's unaudited-app "SELF_ONLY/private only" restriction. Fallback: Blotato ($29/mo). Every publisher implements `--dry-run` and a `queue()` fallback that writes a paste-ready card to `marketing/publish-queue/<platform>/`.
- **Access control for the venture's sheet:** Gumroad handles money and identity; **Google Drive handles access** (per-email `permissions.create` role=reader on `sale`, `permissions.delete` on `subscription_ended`, not on `cancellation`). Hard ceiling 200 explicit viewers per file, so shard into mirrored copies or move to a Worker-rendered page past ~150 members. Weekly script writes **static values**, not live GOOGLEFINANCE formulas (viewers see stale volatile cells).
- **Fact-check gate:** a clean-context Opus agent must return PASS before anything renders or publishes. Any FIX FIRST blocks the whole week's batch. Same gate for the venture's weekly data diff.
- **Ledger:** every autonomous action appends to `decisions/decisions.jsonl` (existing schema). T3 gates unchanged (no CPA claim, no tax/legal advice, refunds, IRS/FASB correspondence, strategic pivots).

---

## Chrome automation: how it stays repeatable

Chrome is only needed where an API is missing: Gumroad covers/thumbnails and the checkout question, Gumroad membership creation (if the API probe fails), the MailerLite campaign/automation editor. YouTube Studio drops out entirely (Upload-Post). Today's pattern (`scripts/video/cdp.py`, `gumroad_covers_ui.py`, `gumroad_workflows_ui.py`) works but is brittle: it assumes Stephen launched the debug Chrome and is logged in, waits with fixed sleeps, and pins CSS/xpath chains that break on any UI change. The plan replaces it with eight rules, implemented once in `scripts/browser/` and reused by every driver.

1. **Chrome is never on the recurring path.** Every scheduled job (Actions, hourly sync, daily publish) is API-only. Chrome drivers run only for one-time or rare setup steps, inside a Claude session on the Mac. If a recurring step would need Chrome, it is redesigned or queued to Stephen.
2. **Scripts own the browser lifecycle.** `scripts/browser/ensure_chrome.py` checks `http://localhost:9222/json/version`; if absent, launches `/Applications/Google Chrome.app` with `--user-data-dir=~/.kdesk/chrome-debug --remote-debugging-port=9222` (the profile already exists and holds the Gumroad/MailerLite/Google logins). Login happens once, by Stephen, and persists in the profile; scripts never type passwords or handle 2FA.
3. **Preflight per site, fail closed.** `session.py` opens the site's dashboard URL and detects a redirect to login. Not logged in → write a queue card (`marketing/publish-queue/manual/<date>-login-<site>.md`), exit non-zero, log to the ledger. Never retry blindly.
4. **Declarative, idempotent drivers.** Desired state lives in a file (`covers.json`, `workflows.json`, `membership.yaml`, `checkout-questions.yaml`). Each driver = `read_state(page) → diff(desired) → apply(missing only) → read_state again → assert`. Re-running with nothing to do is a no-op that prints the verified state. `gumroad_workflows_ui.py` already does half of this; it becomes the template.
5. **Drive the app's own JSON endpoints before its DOM.** Because the logged-in Chrome carries the cookies, `page.request` and in-page `fetch()` can call the internal endpoints the web app itself uses (this is how the hidden ASC 606 product id was recovered). Pattern: record once with Playwright HAR (`record_har_path`), identify the XHR that saves, replay it with `page.request.post`. Clicks are the fallback, not the default. First target: MailerLite campaign creation via its web-app endpoint, since the public API is classifier-blocked.
6. **Condition waits and semantic selectors.** No `wait_for_timeout`; use `expect(locator).to_be_visible()`, `wait_for_url`, `wait_for_response(lambda r: "/save" in r.url)`. Selectors are `get_by_role` / `get_by_label` / `get_by_text` first; anything site-specific lives in one `selectors_<site>.py` so a UI change is a one-file fix.
7. **Every run leaves evidence.** Playwright tracing on (`trace.zip` per run under `scripts/browser/runs/<date>/`), screenshot on failure, one structured result line to the ledger, one retry maximum, then a queue card with the exact remaining manual step.
8. **Weekly selector canary.** A read-only `--check` mode for every driver (opens the page, asserts its anchors resolve, changes nothing) runs in the Monday job while the debug Chrome is up; drift is reported in the digest before a driver is needed, not when it fails.

**Exploration vs codification.** The Claude-in-Chrome extension (available in sessions) is the exploration tool: when a driver breaks, I use it to inspect the live page and find the new anchor or XHR, then encode the fix in the Playwright script and its `--check`. The extension is never the repeatable path itself.

**Verification for this section:** `python3 scripts/browser/ensure_chrome.py && python3 scripts/browser/session.py --check gumroad mailerlite` prints a logged-in status per site; `python3 scripts/video/gumroad_covers_ui.py --check` exits 0 with no changes; running any driver twice produces identical state output and no second ledger action.

---

## Track 1 — PRODUCT

### 1A. KDesk catalog: `make product` (Build Once, Sell Many, deterministically)

New `scripts/product_pipeline.py` + `Makefile` in `~/kdeskaccountingtemplates`, keyed on a hash of `templates/<slug>/SPEC.md`:

`build_*.py` → `pytest tests/test_<slug>.py` → validator → `make_lean_free.py` → `gumroad_files.py --swap` (paid + free listings) → Hugo product page regen (`content/templates/<slug>/`) → `make_covers.py` → `build_video.py` → `make_short.py --variant …` → ledger entry.

- `make product SLUG=rsu-planner DRY=1` prints the plan, touches nothing.
- Tier T0 when only mechanics changed; T2 if price or claims change.
- Encode the known gotcha: publish via `PUT /products/{id}/enable` and re-read `published` (the `gumroad_publish.py publish` command lies).
- Reuse: `~/kdeskaccountingtemplates/gumroad_publish.py`, `gumroad_files.py`, `gumroad_bundle.py`, `make_lean_free.py`; `scripts/video/build_video.py`, `make_short.py`, `make_covers.py`, `render_sheets.py`.

### 1B. The subscription-sheet venture (distinct brand)

**Niche:** see "Niche selection" below (filled from the 2026-09-14 Opus research). **Shape** regardless of niche:

- **Identity:** a new Google account owns the Sheet, the YouTube channel, and the Gumroad login (the video's literal step 1). Stephen creates it once. If Gumroad refuses a second account, Lemon Squeezy (5% + $0.50, merchant of record) is the fallback; Stripe Payment Links is the last resort (Stephen becomes the tax filer).
- **Repo:** new `~/<venture-slug>/` with `CLAUDE.md` (vault pointer), `sheet/spec.yaml`, `scripts/update_sheet.py`, `scripts/publishers/` (shared with KDesk via a small installable package `kdesk_engine/` extracted from `scripts/video/` + publishers; until extraction, call KDesk's scripts by path with `--spec`), `changelog/`, `tests/`.
- **Sheet:** tabs `This Week` (the diff, append-only), `Rankings/Tracker` (the paid core), `Free Preview` (mirrored to the public sheet), `How to use`. Weekly script: pull public data → normalize → diff vs last week → write static values via `gws sheets spreadsheets.values.batchUpdate` to master + public mirror → emit `changelog/YYYY-WW.json` (seed for 7 Shorts + 1 post) → export PNG cards for the videos.
- **Pricing:** $5–9/mo, ~$50–90/yr, 7-day free trial (Gumroad supports it). Free tier = public mirror with a subset + last week's diff. Gumroad fee at $9/mo ≈ 15.6%; revisit platform at ~100 members.
- **Access sync:** Cloudflare Worker `workers/gumroad-ping/` receives Gumroad `resource_subscriptions` (sale, subscription_ended, refund) → D1 → `scripts/membership_sync.py` (Actions, hourly) grants/revokes Drive permissions, serialized (Drive rejects concurrent permission ops). Non-Google emails get the Gumroad gated Content tab with the embedded mirror.
- **Hard rule:** if a week's update needs human judgment or data behind a login/paid API/ToS-violating scrape, that feature is dropped, not softened.
- **Kill criterion:** < 25 paying members 90 days after launch, unless free-mirror traffic is growing week over week.

### Niche selection (Opus research, 2026-09-14; 19 candidates scored on 7 criteria)

Two criteria were treated as **gates**: a free, ToS-clean, stable public data source, and a real paid-supply gap. Most of the obvious niches die on one of them (verified against each platform's terms):

- **Fantasy football:** Sleeper API is non-commercial only; FantasyPros gives rankings away.
- **Credit-card bonuses:** Doctor of Credit already publishes exactly this sheet for free.
- **LEGO retiring sets:** BrickLink's API terms forbid paywalling its data; Brick Tracker is free.
- **Concerts / presales:** Ticketmaster API forbids commercial resale.
- **Game deals / Game Pass:** Deku Deals, IsThereAnyDeal, and CheapShark are free and excellent.
- **HYSA / CD rates:** no free bank-APY API; Bankrate and NerdWallet own the free tier.
- **Pokémon TCG price movers:** best demand and affiliate economics, but clean commercial price data costs ~€29/mo and the market is correcting. Held as candidate #3.
- **Grants and funding deadlines:** widest verified price umbrella (GrantWatch charges $49/mo for public Grants.gov data, which has a free no-key API), but "free money" short-form content is scam-adjacent under TikTok policy and the audience is close to KDesk's. Held as candidate #2.

**Recommendation: the theme-park crowd and trip-planning sheet** (Orlando + Anaheim first, regional parks later). Scored 32/35, the only candidate passing both gates cleanly.

- **Data (verified, no auth, no cost):** `api.themeparks.wiki/v1` (schedules, entities, live waits, 75+ destinations) and `queue-times.com/parks/{id}/queue_times.json` (80+ parks, 5-minute refresh, attribution "Powered by Queue-Times.com" required). The crowd forecast is computed by our script from wait-time history, which is squarely Stephen's data skillset.
- **Sheet tabs:** `Best Day to Go` (rolling 12-month crowd score per park) · `This Week's Changes` (hours revisions, refurb closures, reopenings) · `Ride Closures & Refurbs` · `Ticket & Hotel Price Watch` · `Festival/Event Calendar` · `Rope-Drop Order` (ranked by historical wait curve) · `Changelog`.
- **Free vs paid:** free public mirror = next 30 days, Magic Kingdom only. Paid = all parks, 12 months, price watch, rope-drop order. **$6/mo or $45/yr.**
- **Daily video formats:** "Worst day to go to EPCOT in March" · "3 rides closing next week" · "Cheapest Disney week left in 2027" · "Top 5 shortest-wait rides right now." All render from the weekly diff as card scenes.
- **Affiliate hook (may out-earn the subscription):** Undercover Tourist (authorized Disney/Universal ticket reseller; $5/sale scaling to 6%), hotels via Booking/Expedia, park gear via Amazon. Thrill Data runs a free competitor funded entirely this way.
- **Why the gap is real:** TouringPlans sells an app and algorithm ($14.95/yr), Thrill Data publishes charts, Etsy sells static Disney planner spreadsheets by the thousand. Nobody sells a weekly-refreshed sheet you plan the trip in, and a static copy goes stale in seven days, which is the retention mechanic.
- **Biggest risk:** price ceiling. TouringPlans at $14.95/yr has 16 years of data. The market may clear at free-plus-affiliate, which is what Thrill Data does. The 30-day test below answers this before the paid sheet is built.
- **Unverified:** no follower counts for comparable faceless accounts could be retrieved; day-90 expectations (2k–10k followers, $0–300 MRR) are a hypothesis, not a forecast.

**30-day test (< $100, mostly $12 for a domain):** days 1–3 write the puller and publish only the free mirror tab; days 4–30 one video per day rendered from the sheet diff, bio link to a $6/mo Gumroad **pre-order** for the full sheet plus one Undercover Tourist link. **Day-30 gates:** median of the top 3 videos ≥ 5k views, ≥ 15 paid pre-orders, ≥ 1 affiliate conversion. Two of three → build the paid sheet (Phase 2). Fewer → pivot to free sheet + affiliate only, or re-run the test with candidate #2 (grants). Working name and handles are chosen in Phase 0 by Stephen.

---

## Track 2 — MARKETING (the daily engine)

One entry point per brand: `scripts/content/run_daily.py`.

| # | Stage | Script | Who | Tier |
|---|---|---|---|---|
| 1 | Weekly plan: 7 scene specs + 1 blog post + 1 LLM-citable reference page | `scripts/content/plan_week.py` | Opus **content-planner** | T0 (drafts) |
| 2 | Fact-check every spec (GAAP/tax for KDesk; data accuracy + claims for the venture) | `scripts/content/factcheck.py` | Opus **factchecker** (clean context) | **Gate** |
| 3 | Render 7 Shorts + cards (new `card` scene kind: HTML → Playwright PNG, alongside the existing workbook-range renderer) | `make_short.py`, `render_sheets.py` | Mac, weekly batch → GitHub release `media-daily-YYYY-WW` | T0 |
| 4 | Publish YouTube Short / TikTok / Reel | `scripts/publishers/{youtube,tiktok,instagram}.py` via Upload-Post | Actions, daily 07:00 PT | **T1** |
| 5 | Cross-post to the site as a post with embed; emit blog + reference page | `scripts/publishers/site.py`, `emit_pages.py` | Actions | T1 |
| 6 | LinkedIn / Reddit | `publishers/linkedin.py`, `reddit.py` write queue cards only | Stephen pastes | human |
| 7 | Weekly digest to the list | `scripts/content/weekly_digest.py` | Actions | T1 |

- **Backlog:** `marketing/content/backlog.jsonl` seeded from the week's changelog, `target-queries.json`, GSC + **Bing** rows (Bing beats Google 3.6:1), and the top prior Shorts from `youtube-snapshots.jsonl`. Venture backlog seeds from its weekly diff + `trendspyg` pulls.
- **MailerLite campaigns are API-blocked.** Order of attempts: script call to the `campaigns` endpoint once more (the block was a chat-tool classifier) → CDP-drive the editor with the existing `scripts/video/cdp.py` pattern → send from `santiagokdesk@gmail.com` via `gws` while the list is under ~200.
- **YouTube:** stop `youtube_publish.py` uploads immediately; route through Upload-Post. Re-upload the 20 locked videos. Keep the audit form submission on Stephen's list because it also lifts the restriction for direct uploads later.
- **Stephen's monthly 60–90 s face clip** stays as a credibility asset for KDesk only.

## Track 3 — SALES

- **CRM = a private Google Sheet per brand** ("KDesk CRM", "<Venture> CRM") written by `scripts/sales/crm_sync.py` via `gws`. Never in the public repo. Row: email · first_seen · source (gumroad-free / gumroad-paid / mailerlite / calculator / member) · domain · is_business (reuse the freemail logic in `pull_gumroad_snapshot.py`) · interest · stage · MRR · last_touch · next_action. Tabs `People`, `Events`, `Pipeline`, `Scoreboard`.
- **Automations:** welcome + free→paid nurture (exists, T1) · re-engagement to the 14 skipped downloaders (`marketing/email-sequences/re-engage-2026-09.md`, T1 send) · business-domain download → personalized Gmail **draft** (pattern of ledger #67; auto-send only if Stephen opts in later) · affiliate link insertion + disclosure (`scripts/sales/affiliate_links.py`, T1) · partner/outreach batches drafted by Opus **outreach-writer** (T2) · Bill Hanna follow-up (drafted 2026-09-10, unsent; Stephen sends) · membership churn sync (T0) · scoreboard extended with MRR, active members, churn, trial→paid rate (extend `pull_gumroad_snapshot.py`).
- **Venture sales:** entirely self-serve; the only "sales" work is the free-trial → paid email (Gumroad's built-in) and a cancel-survey link. No CRM outreach for a $9 product.

## Track 4 — ORCHESTRATION

- **GitHub Actions** (site repo + venture repo): `sheet-weekly.yml` (Sun 06:00 PT), `daily-publish.yml` (07:00 PT), `data-weekly.yml` (Mon 08:15 PT; moves the four `pull_*_snapshot.py` jobs + `crm_sync.py` off launchd), `membership-sync.yml` (hourly). Secrets: `GUMROAD_ACCESS_TOKEN`, `MAILERLITE_TOKEN`, `GOOGLE_TOKEN_JSON`, `BING_API_KEY`, `CF_API_TOKEN`, `UPLOAD_POST_KEY`. Local files stay authoritative.
- **Claude Code scheduled routine** (cloud), Saturdays: `plan_week.py` + `factcheck.py` for both brands, opens the week's PR. Only job with an LLM in the loop.
- **Mac weekly batch** (Saturday, when a session runs anyway): render → GitHub release. Phase 3 tests moving Kokoro TTS + ffmpeg + Playwright onto an Actions runner.
- **Digest:** `scripts/digest.py` → one Gmail to Stephen at 07:30 PT (what published, what's queued for him, MRR/members/churn delta, FIX FIRST items, open veto windows) + append to `~/CommandCenter/01-Daily/YYYY-MM-DD.md`.
- **Opus subagent roster** (definitions in `.claude/agents/*.md` in each repo; each states inputs, outputs, and that it may not publish): `content-planner`, `factchecker`, `sheet-data-researcher` (validates a data source is public, stable, license-clean), `outreach-writer`, `digest-writer`, `builder` (implements a numbered task from this plan in a worktree, TDD, returns a diff summary). Fable dispatches, reviews, and integrates; independent tasks run in parallel worktrees.
- **Session runbook:** `marketing/runbooks/automation-2026-09.md` in the site repo and `RUNBOOK.md` in the venture repo, both added to the "read first" list.

---

## Phases (each ends live and measurable)

| Phase | Sessions | Ends with |
|---|---|---|
| **0 — Foundations** (this week) | 0.5 | Ledger entries: T1 loosening (T2, 48 h veto), venture launch (T2), YouTube-lock finding (T0). Vault: decision note `05-Decisions/2026-09-14-subscription-sheet-venture.md`, new MOC `02-Projects/<Venture>.md`, KDesk MOC `next-action` updated, decision-log rows. Subagent files, runbooks, Actions secrets. This context repo: `context/subscription-sheet-venture.md` + INDEX row. |
| **1 — First dollars + stop the bleeding** (≤ 2 weeks) | 3–4 | Upload-Post connected; 20 locked videos re-uploaded public; API uploads disabled. Venture 30-day test starts: Google account, the free mirror sheet populated by `update_sheet.py` (Magic Kingdom, next 30 days), $6/mo Gumroad pre-order listing, Undercover Tourist link, first 7 card-style Shorts published daily. KDesk: re-engagement email sent, affiliate applications submitted, Bill Hanna follow-up sent (Stephen), CRM sheet live, `make product` green in dry-run. |
| **2 — The weekly engine** | 2–3 | `sheet-weekly.yml` on Actions with two consecutive Sunday changelogs untouched by humans; `run_daily.py` live for both brands; fact-check gate enforced; digest arriving daily. **Day-30 gate read:** if 2 of 3 pass, build the full paid sheet (all parks, 12 months, price watch) and convert pre-orders; otherwise pivot per the niche section. |
| **3 — Distribution width** | 2 | TikTok + Reels via Upload-Post paid tier; blog + reference pages auto-generated; weekly list digest sending; render moved to Actions if feasible. |
| **4 — Sales + scale** | 2 | Churn Worker live (a cancel revokes Drive access within 24 h); business-domain auto-drafts; scoreboard with MRR/churn; decide sharding vs Worker-rendered page; portfolio review prep for 2026-12-01. |

**Dispatch pattern per phase:** Fable writes numbered task briefs from this plan; each brief goes to an Opus `builder` in its own worktree (TDD, dry-run first); a separate Opus reviewer checks the diff against the brief; Fable merges and appends the ledger entry.

## What only Stephen does

**One-time (~90 min total):** approve the T1 loosening and the venture (48 h veto) · create the venture's Google account + Gumroad account (or approve Lemon Squeezy) · create TikTok + Instagram professional accounts for the venture and connect them plus YouTube to Upload-Post · mint a Cloudflare API token · submit the YouTube API audit form · submit affiliate applications · read IBM's COI policy (Stream D).
**Weekly (~15–25 min):** skim the daily digest and veto anything wrong · paste one LinkedIn post · reply to inbound buyer email.
**Monthly (~15 min):** the 60–90 s KDesk face clip.

## Verification

```bash
# Product
make product SLUG=rsu-planner DRY=1                          # prints plan, writes nothing
uv run --with pytest pytest tests/                            # KDesk tests stay green
python3 scripts/update_sheet.py --week 2026-W39 --dry-run     # venture: diff vs live sheet, no writes
gws sheets spreadsheets.values.get --params '{"spreadsheetId":"<id>","range":"This Week!A1:E8"}'

# Marketing
python3 scripts/content/plan_week.py --week 2026-W39 --dry-run
python3 scripts/content/factcheck.py --week 2026-W39          # must print PASS before render
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug daily-2026-W39-01
python3 scripts/publishers/youtube.py --asset <mp4> --dry-run
python3 scripts/content/run_daily.py --dry-run                # full chain, zero side effects

# Sales / orchestration
python3 scripts/sales/crm_sync.py --dry-run
curl -X POST <worker-url> -d 'resource_name=subscription_ended&email=test@example.com'   # → D1 row
python3 scripts/membership_sync.py --dry-run                  # shows grant/revoke it would do
gh run list --limit 5 && gh workflow view daily-publish.yml
tail -3 decisions/decisions.jsonl
```

**Live proofs:** Phase 1 = a Gumroad membership with `recurrence` set and one test purchase by Stephen (refunded); the 20 re-uploaded videos show `public` in the next snapshot. Phase 2 = two consecutive Sunday changelogs with no human edit. Phase 3 = 7 consecutive daily publishes on all three platforms. Phase 4 = a cancel that revokes Drive access within 24 h.

## Risks and kill criteria

1. **Gumroad membership creation via API is unverified.** Phase 1 step 1 is a probe; fallback is the Gumroad editor (5 min of Stephen) or the existing CDP pattern (`gumroad_workflows_ui.py`).
2. **Third-party scheduler dependency** (Upload-Post). Mitigation: pluggable publishers with queue fallback; Blotato as the second option; no long-term contract.
3. **Content quality drift at volume.** The fact-check gate is non-bypassable; a FIX FIRST blocks the whole batch.
4. **Regulatory line (T3)** for anything KDesk publishes about tax; the venture must not drift into financial advice either.
5. **Consumer-niche expectations.** No verified daily faceless account in Stephen's niches was found; the venture's 30-day test decides before more build.
6. **Stephen's bandwidth.** CPE stays primary through Nov 1; Phases 0–2 ask only for the list above.
7. **"Building instead of distributing" (the CAE failure).** Phase 1 sends email and submits applications before Phase 2 builds the engine. Kill rules: venture < 25 members at 90 days; KDesk portfolio review 2026-12-01 unchanged (if total revenue is still $0, stop building).
8. **Costs:** Upload-Post ~$16–24/mo once TikTok is added, Cloudflare Workers free tier, trendspyg free. Total well under the < $1,000 capital rule; no paid ads.

## Documentation this plan produces

- Vault: decision note + decision-log row + new project MOC + KDesk MOC update + today's daily note.
- Site repo: `CLAUDE.md` corrections (YouTube lock; autonomy tiers), runbook, `.claude/agents/`.
- Venture repo: `CLAUDE.md`, `RUNBOOK.md`, `sheet/spec.yaml`.
- This context repo: `context/subscription-sheet-venture.md` (model, niche rationale, engine map) + `INDEX.md` row.
