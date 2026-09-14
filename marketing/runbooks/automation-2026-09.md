# Runbook — the automation engine (2026-09)

**Companion to `marketing/plan-2026-09-14-automation.md` (the spec).** That plan is reasoning; this is the
card you work from. Read this at the start of any session that touches publishing, the video pipeline, or
the `parksheet` venture.

**Scripts marked "(Phase 1)" or "(Phase 2)" do not exist yet.** They are named here with the exact paths the
plan assigns them so that the runbook does not have to be rewritten when they land. If a command below fails
with "no such file", check the phase marker before debugging.

---

## Current state — read this first

| | |
|---|---|
| **Phase** | **0 → 1.** Phase 0 (documentation + ledger) is done. Phase 1 is blocked on Stephen's accounts. |
| **Open vetoes** | **#69** (marketing autonomy → T1 auto-publish) and **#70** (the `parksheet` venture), both close **2026-09-16 12:00 PT**. |
| **Autonomy in force until 2026-09-16** | The OLD rule: **queues, not auto-posters.** Nothing publishes without Stephen. Do not auto-publish on the strength of #69 before the window closes. |
| **Autonomy after 2026-09-16 (if unvetoed)** | T1 auto-publish for **YouTube Shorts · TikTok · Instagram Reels · blog posts · email nurture**, each behind the fact-check gate. **LinkedIn and Reddit stay human** — queue cards only, forever, not just for now. |
| **YouTube** | 🔴 **`scripts/video/youtube_publish.py` is DO-NOT-USE for uploads** (ledger #71). 20 locked videos await re-upload. |
| **Blocked on Stephen** | Upload-Post account + KDesk channel connected · venture Google/Gumroad/TikTok/IG accounts · Cloudflare API token · YouTube audit form. See CLAUDE.md "Waiting on Stephen". |
| **Plan of record (unchanged)** | `marketing/plan-2026-09-10k-portfolio.md` — $10k/mo, five streams, portfolio review 2026-12-01. This runbook does not replace it. |

---

## Pipeline map

One engine, two brands. KDesk publishes accounting content; `parksheet` publishes theme-park content. Same
stages, same scripts, different spec and different accounts.

```
  spec ──► PRODUCT ──► weekly changelog ──► MARKETING ──► publishers ──► SALES/CRM ──► digest
   │         │               │                  │             │              │            │
KDesk:   templates/<slug>/SPEC.md      plan_week → factcheck → render    Upload-Post   CRM sheet   Gmail 07:30 PT
parksheet: sheet/spec.yaml + data pulls   (Opus)     (GATE)    (Mac)     site · email   nurture    + vault daily note
```

Two invariants:

1. **The fact-check gate is between planning and rendering.** Nothing renders and nothing publishes until a
   clean-context Opus `factchecker` returns **PASS**. This is not advisory.
2. **Chrome is never on the recurring path.** Every scheduled job is API-only. Chrome drivers are for
   one-time setup, run inside a Mac session. If a recurring step would need Chrome, redesign it or queue it
   to Stephen.

### Where each stage runs

| Stage | Runs on | Cadence |
|---|---|---|
| Weekly plan + fact-check (the only LLM steps) | Claude Code scheduled routine (cloud) | Saturday |
| Render (TTS, ffmpeg, Playwright cards) | **this Mac**, one weekly batch → GitHub release `media-daily-YYYY-WW` | Saturday |
| Publish, data pulls, membership sync | GitHub Actions | daily 07:00 PT / Mon 08:15 / hourly |
| Digest | Actions → Gmail + vault daily note | daily 07:30 PT |

Publishing reads assets from the GitHub release, so a sleeping Mac never breaks the daily cadence.

---

## One command per stage

Run from the repo root — shell cwd drifts, and several scripts resolve paths relative to it.

```bash
# ── 0. Orientation ────────────────────────────────────────────────────────────
tail -3 decisions/decisions.jsonl          # what happened last, and what vetoes are open
gh run list --limit 5                      # did the scheduled jobs pass

# ── 1. Weekly plan: 7 scene specs + 1 blog post + 1 reference page ────────────
python3 scripts/content/plan_week.py --week 2026-W39 --dry-run     # (Phase 1) agent: content-planner, T0

# ── 2. THE GATE — must print PASS before anything below runs ──────────────────
python3 scripts/content/factcheck.py --week 2026-W39               # (Phase 1) agent: factchecker

# ── 3. Render (Mac only; the venv is required for TTS) ────────────────────────
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug daily-2026-W39-01
scripts/video/.venv-tts/bin/python scripts/video/build_video.py --spec marketing/video/<slug>/scenes.yaml
python3 scripts/video/render_sheets.py --spec …                    # card scenes (Phase 1: `card` scene kind)

# ── 4. Publish (T1 after 2026-09-16; ALWAYS --dry-run first) ──────────────────
python3 scripts/publishers/youtube.py   --asset <mp4> --dry-run    # (Phase 1) via Upload-Post
python3 scripts/publishers/tiktok.py    --asset <mp4> --dry-run    # (Phase 1) Upload-Post PAID tier
python3 scripts/publishers/instagram.py --asset <mp4> --dry-run    # (Phase 1)
python3 scripts/publishers/site.py --week 2026-W39                 # (Phase 1) cross-post + embed
python3 scripts/content/emit_pages.py --week 2026-W39              # (Phase 1) blog + LLM-citable reference page

# ── 5. Human-only surfaces — these write CARDS, they never post ───────────────
python3 scripts/publishers/linkedin.py --week 2026-W39             # (Phase 1) → marketing/linkedin-queue/
python3 scripts/publishers/reddit.py   --week 2026-W39             # (Phase 1) → marketing/reddit-queue/

# ── 6. Full chain, zero side effects ──────────────────────────────────────────
python3 scripts/content/run_daily.py --dry-run                     # (Phase 1) the one entry point per brand

# ── 7. Sales + digest ─────────────────────────────────────────────────────────
python3 scripts/sales/crm_sync.py --dry-run                        # (Phase 1) private Google Sheet CRM
python3 scripts/content/weekly_digest.py --week 2026-W39 --dry-run # (Phase 1)
python3 scripts/digest.py                                          # (Phase 1) Gmail 07:30 + vault daily note

# ── 8. Venture (repo ~/parksheet, Phase 1) ────────────────────────────────────
python3 scripts/update_sheet.py --week 2026-W39 --dry-run          # diff vs live sheet, writes nothing
python3 scripts/membership_sync.py --dry-run                       # shows the Drive grant/revoke it would do

# ── 9. Chrome, only for one-time setup ────────────────────────────────────────
python3 scripts/browser/ensure_chrome.py                           # (Phase 1) launches or verifies debug Chrome
python3 scripts/browser/session.py --check gumroad mailerlite      # (Phase 1) logged-in status per site
python3 scripts/video/gumroad_covers_ui.py --check                 # read-only; exits 0 with no changes

# ── 10. What still works today, unchanged ─────────────────────────────────────
KDESK_SEO_SKIP_COMMIT=1 uv run scripts/pull_seo_snapshot.py
python3 scripts/pull_gumroad_snapshot.py
uv run scripts/pull_youtube_snapshot.py --print                    # READ-only YouTube API use is fine
uv run scripts/pull_bing_snapshot.py --print
uv run --with pytest pytest tests/
```

---

## If X is broken, do Y

### The debug Chrome is not running

*Symptom:* connection refused on `localhost:9222`; `cdp.py` or any `*_ui.py` driver dies immediately.

1. Check first, don't assume: `curl -s http://localhost:9222/json/version`.
2. If it answers, Chrome is up and the problem is elsewhere — go to the next section.
3. If it does not: run `python3 scripts/browser/ensure_chrome.py` (Phase 1), which launches
   `/Applications/Google Chrome.app` with `--user-data-dir=~/.kdesk/chrome-debug --remote-debugging-port=9222`.
   Until that script exists, launch it by hand with exactly those flags.
4. **Use that profile and only that profile.** `~/.kdesk/chrome-debug` is where the Gumroad / MailerLite /
   Google logins live. A fresh profile looks identical and is logged into nothing.
5. **Never** put a Chrome step on a scheduled job to "fix" this. If the recurring path needed Chrome, the
   design is wrong — redesign it or queue it to Stephen.

### Chrome is running but not logged in

*Symptom:* the driver's preflight sees a redirect to a login page, or a selector that only exists when
signed out.

1. **Fail closed. Do not retry, and never type a password or touch 2FA.**
2. Write the queue card: `marketing/publish-queue/manual/<date>-login-<site>.md`, naming the site, the URL,
   and the exact step that remains.
3. Exit non-zero and append one structured line to `decisions/decisions.jsonl`.
4. Tell Stephen in the digest. He logs in once, in that profile, and it persists.

### Upload-Post fails (down, quota, credentials, or a platform rejects)

1. **Do not fall back to `scripts/video/youtube_publish.py`.** That is what created 20 dead videos (#71).
   There is no emergency exception to this.
2. The publisher's `queue()` fallback writes a paste-ready card to
   `marketing/publish-queue/<platform>/<date>-<slug>.md` — caption, hashtags, the asset path or release URL,
   and the target account. Stephen (or a later session) posts it manually.
3. Log the failure to the ledger (T0) with the platform, the error, and the card path.
4. Check the obvious causes in order: free-tier quota is **10 uploads/mo** and covers Instagram + YouTube
   only — **TikTok requires the paid plan** (~$16–24/mo); then credentials/reconnect; then the platform's
   own status.
5. If it stays broken for more than one cycle, the documented second option is **Blotato ($29/mo)**. Swapping
   is a publisher-module change, not a pipeline change — that is the point of the queue fallback.

### The fact-check comes back FIX FIRST

1. **The whole week's batch is blocked.** Not just the flagged item — the batch. Do not render, do not
   publish, do not "publish the clean ones meanwhile."
2. Apply **every must-fix**. Nice-to-haves are optional; must-fixes are not.
3. **Re-run the gate from a clean context.** A fact-checker that has already seen its own corrections is not
   a second opinion. Re-running in the same context does not count as a pass.
4. Only a **PASS** unblocks the batch. Then render, then publish.
5. Log the FIX FIRST and the resolution to the ledger, and surface both in the digest — the failure rate of
   this gate is a real quality signal. (Every article fact-checked so far has come back FIX FIRST at least
   once; treat a first-pass PASS as suspicious, not as luck.)
6. If a must-fix touches a **T3** area — CPA-licensure framing, tax or legal advice, a claim about CAE — stop
   and escalate to Stephen. Do not soften the wording and proceed.

### A Chrome driver's selectors have drifted

1. The weekly `--check` canary should catch this in the Monday job before anything needs the driver.
2. Use the **Claude-in-Chrome extension to explore** the live page and find the new anchor or the XHR the app
   actually calls.
3. **Encode the fix in the Playwright script and its `--check`.** The extension is the exploration tool, never
   the repeatable path.
4. Prefer the app's own JSON endpoint over its DOM: the logged-in profile carries the cookies, so
   `page.request` / in-page `fetch()` can call it. Record once with a Playwright HAR, find the XHR that
   saves, replay it. Clicks are the fallback.
5. Site-specific selectors live in one `selectors_<site>.py` so a UI change is a one-file fix.

### A weekly data pull needs human judgment, a login, a paid API, or a scrape that breaks ToS

**Drop the feature. Do not soften it.** This is a hard rule for the venture's weekly update, and the reason
the niche passed its gates in the first place.

---

## Agents (`.claude/agents/`)

| Agent | Does | Tools |
|---|---|---|
| `content-planner` | the week's 7 scene specs + blog post + reference page | full |
| `factchecker` | **the gate.** PASS / FIX FIRST, clean context, read-only | read-only + web |
| `sheet-data-researcher` | proves a data source is public, stable, license-clean | read-only + web |
| `outreach-writer` | partner/outreach drafts (T2, never sent) | full |
| `digest-writer` | the daily digest | full |
| `builder` | implements one numbered task in a worktree, TDD | all |

**None of them may publish, send, or spend.** They return drafts and diffs; the orchestrating session
publishes, and only after the gate. T3 gates apply to every agent without exception.

---

## Hard gates — never bypass, in any phase, for any agent

1. No CPA-licensure claim. Stephen's WA license is **inactive**; content must never imply active practice.
2. No tax or legal advice. Mechanics only.
3. No IRS / FASB / auditor / legal correspondence — escalate to Stephen.
4. No refunds or anything financial — Stephen only.
5. No strategic pivots — Stephen only.
6. No claims about CAE before CAE ships.
7. The venture must not drift into financial advice either. It plans trips; it does not advise on money.
8. **Attribution is mandatory** wherever queue-times.com data appears: "Powered by Queue-Times.com".
