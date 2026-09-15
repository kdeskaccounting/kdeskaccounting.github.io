# Runbook — the automation engine (2026-09)

**Companion to `marketing/plan-2026-09-14-automation.md` (the spec).** That plan is reasoning; this is the
card you work from. Read this at the start of any session that touches publishing, the video pipeline, or
the `parksheet` venture.

**Scripts marked "(Phase 2)" do not exist yet.** They are named here with the exact paths the plan assigns
them so that the runbook does not have to be rewritten when they land. If a command below fails with "no such
file", check the phase marker before debugging. Everything without a marker is built and tested today —
Phase 1 landed on 2026-09-15, including the two GitHub Actions schedules below.

---

## Current state — read this first

| | |
|---|---|
| **Phase** | **1 built, not yet live.** Phase 0 (documentation + ledger) and every Phase 1 script are done and tested. What remains is Stephen's: the five repository secrets below, an Upload-Post account, and the first Saturday render batch. |
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
| Weekly plan + fact-check (the only LLM steps) | Claude Code scheduled routine (cloud) | Saturday (Phase 2) |
| Render (TTS, ffmpeg, Playwright cards) | **this Mac**, one weekly batch → GitHub release `media-daily-<ISO week>` (e.g. `media-daily-2026-W38`) | Saturday |
| Publish | GitHub Actions `daily-publish.yml` | daily 07:00 PT |
| Data pulls + CRM dry run | GitHub Actions `data-weekly.yml` | Mon 08:15 PT |
| Live CRM sync, re-engagement sends, the emailed digest | **this Mac** (all three need `gws`) | daily / on demand |
| Digest | Actions → run summary; **Mac → Gmail + vault daily note** | daily 07:30 PT |

Publishing reads assets from the GitHub release, so a sleeping Mac never breaks the daily cadence.
`daily-publish.yml` resolves the **newest** `media-daily-*` release rather than computing this week's tag —
the ISO week rolls over on Monday while the batch that produced the media ran on the Saturday before — and
refuses a release more than 8 days old, so a skipped batch fails loudly instead of re-publishing last week.

---

## One command per stage

Run from the repo root — shell cwd drifts, and several scripts resolve paths relative to it.

```bash
# ── 0. Orientation ────────────────────────────────────────────────────────────
python3 scripts/ledger.py --tail 5         # what happened last, and what vetoes are open
gh run list --limit 5                      # did the scheduled jobs pass

# ── 1. Weekly plan: 7 scene specs + 1 blog post + 1 reference page ────────────
python3 scripts/content/plan_week.py --week 2026-W39 --dry-run     # (Phase 2) agent: content-planner, T0

# ── 2. THE GATE — must print PASS before anything below runs ──────────────────
python3 scripts/content/factcheck.py --week 2026-W39               # (Phase 2) agent: factchecker

# ── 3. Render (Mac only; the venv is required for TTS) ────────────────────────
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug daily-2026-W39-01
scripts/video/.venv-tts/bin/python scripts/video/build_video.py --spec marketing/video/<slug>/scenes.yaml
scripts/video/.venv-tts/bin/python scripts/video/build_video.py \
  --spec marketing/video/card-demo/scenes.yaml --frames-only      # `card` scene kind, no TTS

# ── 4. Publish (T1 after 2026-09-16; ALWAYS --dry-run first) ──────────────────
python3 scripts/publishers/publish.py --capabilities               # which platforms are actually connected
python3 scripts/publishers/publish.py --platform youtube,tiktok,instagram \
  --asset <mp4> --meta <json> --dry-run                            # one entry point, exit 0 ok / 1 queued / 2 error
python3 scripts/publishers/publish.py --platform site --asset <mp4> --meta <json>   # cross-post + embed
python3 scripts/video/reupload_locked.py --dry-run                 # the 20 locked videos (#71), Upload-Post
python3 scripts/content/emit_pages.py --week 2026-W39              # (Phase 2) blog + LLM-citable reference page

# ── 5. Human-only surfaces — these write CARDS, they never post ───────────────
python3 scripts/publishers/linkedin.py --week 2026-W39             # (Phase 2) → marketing/linkedin-queue/
python3 scripts/publishers/reddit.py   --week 2026-W39             # (Phase 2) → marketing/reddit-queue/

# ── 6. Full chain, zero side effects ──────────────────────────────────────────
python3 scripts/content/run_daily.py --dry-run                     # (Phase 2) the one entry point per brand

# ── 7. Sales + digest ─────────────────────────────────────────────────────────
python3 scripts/sales/crm_sync.py --dry-run                        # private Google Sheet CRM (live needs gws)
python3 scripts/sales/send_reengage.py --dry-run                   # the 14 re-engagement emails, veto-gated
python3 scripts/content/weekly_digest.py --week 2026-W39 --dry-run # (Phase 2)
python3 scripts/digest.py --dry-run                                # compose only
python3 scripts/digest.py --send --vault                           # Mac only: Gmail 07:30 + vault daily note

# ── 8. Venture (repo ~/parksheet) ─────────────────────────────────────────────
python3 scripts/update_sheet.py --week 2026-W39 --dry-run          # diff vs live sheet, writes nothing
python3 scripts/membership_sync.py --dry-run                       # (Phase 4) Drive grant/revoke it would do

# ── 9. Chrome, only for one-time setup ────────────────────────────────────────
python3 scripts/browser/ensure_chrome.py                           # launches or verifies debug Chrome
python3 scripts/browser/session.py --check gumroad mailerlite      # logged-in status per site
python3 scripts/video/gumroad_covers_ui.py --check                 # read-only; exits 0 with no changes

# ── 10. What still works today, unchanged ─────────────────────────────────────
KDESK_SEO_SKIP_COMMIT=1 uv run scripts/pull_seo_snapshot.py
python3 scripts/pull_gumroad_snapshot.py
uv run scripts/pull_youtube_snapshot.py --print                    # READ-only YouTube API use is fine
# ^ --print is read straight out of sys.argv (this script has no argparse), so an unknown flag is
#   silently ignored rather than rejected. data-weekly.yml therefore runs it with NO flags, and
#   tests/test_workflows.py enforces that: a flag may only be passed to a script whose --help lists it.
uv run scripts/pull_bing_snapshot.py --print
uv run --with pytest pytest tests/
```

---

## GitHub Actions — the two schedules

Both live in `.github/workflows/` alongside the untouched Hugo deploy (`deploy.yml`). Their shape is pinned by
`tests/test_workflows.py`, so an edit that breaks a cron, a guard or a pathspec fails the suite before it ever
reaches a runner.

| Workflow | Cron (UTC) | Local | Does |
|---|---|---|---|
| `data-weekly.yml` | `15 15 * * 1` | Mon 08:15 PDT | GSC/GA4 + target queries, Gumroad, YouTube, Bing pulls · `crm_sync.py --dry-run` · commits the JSONL rows |
| `daily-publish.yml` | `0 14 * * *` | 07:00 PDT | Downloads the day's asset from the newest `media-daily-*` release, publishes YouTube/TikTok/Instagram, writes the digest into the run summary |

Both crons are pinned to **PDT**. Between the November and March changeovers they run an hour early (07:15 and
06:00 local) — acceptable for a data pull and a morning publish, and cheaper than two schedules.

Both take `workflow_dispatch` with `dry_run` defaulting to **true**, so a manual run never publishes or commits
by accident:

```bash
gh workflow run data-weekly.yml   -f dry_run=true
gh workflow run daily-publish.yml -f dry_run=true -f slug=2026-09-15
gh run list --limit 5
gh run view --log-failed
```

### Set the Actions secrets (one time, from the Mac)

Every value already exists locally; nothing here is ever committed. `-f` / `--repo` keeps it explicit so this
cannot be pasted against the wrong repo.

```bash
R=kdeskaccounting/kdeskaccounting.github.io

gh secret set GOOGLE_TOKEN_JSON --repo "$R" < ~/kdesk-analytics/google-token.json
gh secret set MAILERLITE_TOKEN  --repo "$R" < ~/kdesk-analytics/mailerlite-token.txt

gh secret set GUMROAD_ACCESS_TOKEN --repo "$R" \
  --body "$(grep -m1 '^GUMROAD_ACCESS_TOKEN=' ~/kdeskaccountingtemplates/.env | cut -d= -f2- | tr -d "\"'")"

# Optional, and COMMENTED OUT on purpose: ~/kdesk-analytics/bing-api-key.txt does not exist yet, so
# running this line today sets the secret to nothing, which is worse than leaving it unset. Stephen
# mints the key first (bing.com/webmasters → Settings → API Access → API Key), saves it to that path
# 0600, and only then uncomments this. Until the secret exists the Bing step is SKIPPED, not failed.
# gh secret set BING_API_KEY --repo "$R" < ~/kdesk-analytics/bing-api-key.txt

# From https://www.upload-post.com/ after connecting YouTube, TikTok and Instagram.
gh secret set UPLOAD_POST_KEY --repo "$R"        # prompts, so the key never reaches shell history

gh secret list --repo "$R"
```

Each workflow preflights its own required secrets and **exits 2 naming the missing one** — so a forgotten
secret costs one legible line, not a stack trace from inside a Google token refresh four steps later.
`BING_API_KEY` is the only optional one.

### What still only runs on the Mac, and why

- **`scripts/sales/crm_sync.py`** (live) — needs the `gws` CLI and its santiagokdesk credentials under
  `~/.config/gws/`, which is a local Homebrew install. CI runs `--dry-run`, which still proves the Gumroad and
  MailerLite pulls and the diff.
- **`scripts/sales/send_reengage.py`** — same `gws` dependency, plus the recipients live in
  `~/kdesk-analytics/private/` and never enter this repo.
- **`scripts/digest.py --send --vault`** — `--send` needs `gws`; `--vault` needs `~/CommandCenter`, and the
  vault is local. `daily-publish.yml` writes the same markdown into the run summary instead, and its
  `send_digest` input is the switch for the day a non-`gws` Gmail path exists.
- **The ledger.** For KDesk **the Mac commits the ledger** — `daily-publish.yml` has `contents: read` and never
  pushes. Its publish stdout and any queue cards leave as a workflow artifact
  (`kdesk-publish-<slug>-<run id>`); download it, then append the ledger rows locally.
- **Rendering** (`build_video.py`, `make_short.py`) — LibreOffice, Kokoro TTS and the Playwright Chromium
  shell, and `scripts/video/build/` is gitignored so the mp4s exist nowhere else. The Mac renders on Saturday
  and pushes the `media-daily-<ISO week>` release the daily job reads.
- **Every Chrome driver** (`scripts/browser/`, the two Gumroad UI scripts) — spec Chrome rule 1: Chrome is
  never on the recurring path.

### Turning off the old launchd Monday block

`~/kdesk-analytics/kdesk-daily.sh` still runs the same four pulls every Monday under launchd
(`com.kdesk.daily-sync`, 08:15). Until that block is removed, **both it and `data-weekly.yml` append a row to
the same JSONL files** — two rows per Monday, and two pushes racing on the same branch.

Once `data-weekly.yml` has committed **one clean Monday**, remove the Monday branch from that script (keep the
daily MailerLite sync, which Actions does not do). Back it up first and check the result:

```bash
cp ~/kdesk-analytics/kdesk-daily.sh ~/kdesk-analytics/kdesk-daily.sh.bak-$(date +%F)
# edit out the Monday block only
zsh -n ~/kdesk-analytics/kdesk-daily.sh
```

That file lives outside this repo, so no session edits it as a side effect of anything else — it is Stephen's
one manual step, and it is the only thing standing between the handover and double-counted snapshots.

### Weekly selector canary (spec Chrome rule 8)

While the debug Chrome is up on a Monday:

```bash
python3 scripts/browser/ensure_chrome.py
python3 scripts/browser/session.py --check gumroad mailerlite
scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --check
scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check
```

Any drift shows up here, in the digest, before a driver is actually needed.

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

### `daily-publish.yml` exits 2 at "Resolve the media release and the slug"

Two different messages, two different causes — read which one it printed.

1. **"no media-daily-* release exists"** — the Saturday Mac render batch has never run. Render the week, then
   upload the assets and their publish meta to a release tagged `media-daily-<ISO week>` (`date -u +%G-W%V`,
   e.g. `media-daily-2026-W38`). Until then this failure every morning is the correct, legible one — do not
   fake a release to turn the run green.
2. **"newest media release is N days old; the Saturday batch did not run"** — a release exists but nobody
   rendered this week. The guard is 8 days (7 from Saturday to Saturday, plus a day of slack). **Do not raise
   the threshold.** Without it the job would cheerfully re-publish last week's seven assets as new, green every
   morning, and nobody would notice for a month.

Either way the digest step still runs (`if: always()`), so the run summary tells you what else is open.

### `daily-publish.yml` fails at "Fail the run if nothing published and nothing queued"

Every publish step is `continue-on-error`, so this is the step that turns "all three platforms failed and
none of them queued a card" into a red run instead of a green one with an empty summary.

1. Download the run's artifact (`kdesk-publish-<slug>-<run id>`) — `publish-stdout.txt` has the per-platform
   line and the reason.
2. A **QUEUED** line is not this failure: a queued platform wrote a card, and a card is a legitimate outcome.
   This fires only when there were zero successes **and** zero cards, which means the publisher did not even
   get as far as its own fallback.
3. Usual causes in order: `UPLOAD_POST_KEY` revoked or out of quota (free tier is 10 uploads/mo); the asset or
   meta file missing from the release (publish.py exits 2 on a bad `--asset`/`--meta`); Upload-Post itself down.
4. **Do not fall back to `scripts/video/youtube_publish.py`** — that is what created 20 dead videos (#71).

### A scheduled job exits 2 at "Preflight the secrets"

The message names the missing repository secret and the `gh secret set` line that fixes it — run that line
from the Mac (see "Set the Actions secrets" above), then re-dispatch with `-f dry_run=true` before letting the
schedule pick it up. `BING_API_KEY` never causes this: it is optional, and an unset key skips the Bing step.

### The Monday snapshots have two rows

Both `data-weekly.yml` and the launchd Monday block in `~/kdesk-analytics/kdesk-daily.sh` ran. Nothing is
corrupt — the JSONL files are append-only and every reader takes the latest row — but the deltas in the digest
will read as zero. Do the handover in "Turning off the old launchd Monday block" and leave the duplicate rows
where they are; the ledger's rule is that nothing is deleted.

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
