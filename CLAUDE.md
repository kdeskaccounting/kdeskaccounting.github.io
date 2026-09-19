> 🧭 **Command Center vault** — Stephen's context, goals, and decisions live in `~/CommandCenter` (this is a Mac; the `/mnt/c/` and `/home/kdeskconsulting/` paths in older notes are the Windows/Linux machines). Relevant note: `02-Projects/KDesk-Blog.md`. See `_meta/CLAUDE.md`; global rules in `~/.claude/CLAUDE.md`.

# CLAUDE.md — KDesk Accounting blog

## Read first, every session

1. **`marketing/plan-2026-09-10k-portfolio.md`** — the plan (decision 51, 2026-09-04): target **$10,000/mo**, the **$4,246/mo safety net** as the first milestone, five streams on five channels, kill criteria per stream. `marketing/roadmap-2026-09.md` ($300/mo) is superseded — its weekly cadence, fact-check rule and guardrails still apply where they don't conflict. `OPERATIONS_PLAN.md` (May 2026) is historical.
2. **`marketing/plan-2026-09-14-automation.md`** — the automation plan (2026-09-14, ledger #69–#71): how the plan of record above gets executed with less of Stephen's time (< 30 min/wk), plus a **second, separate brand** (`parksheet`, a subscription living Google Sheet). It does **not** replace the revenue plan of record. Its session runbook is **`marketing/runbooks/automation-2026-09.md`** — pipeline map, one command per stage, current phase, open vetoes, the "if X is broken do Y" table, and (Phase 1, 2026-09-15) the two GitHub Actions schedules: what runs on Actions, what only runs on the Mac and why, the exact `gh secret set` commands, the launchd handover, and the weekly selector canary. Read both before touching publishing, the video pipeline, or the venture.
3. `decisions/decisions.jsonl` — append-only ledger; every autonomous action is logged. Currently at **#85** (85 entries, ids contiguous 1–85). **#52 repricing executed 2026-09-06 (decision 61): ASC 842 $249 · ASC 606 $249 · bundle $599.** **#83 (T0): TikTok publishes through Chrome, not Upload-Post — `scripts/publishers/tiktok_web.py` + `schedule_week.py`, every selector still UNVERIFIED until he logs in.** **#84 (T0): `kind: media` scenes — Earth/Commons footage with a card overlay, watermark zone kept clear (`scripts/video/media.py`).** Open veto windows: **none.** **#69 marketing autonomy → T1 auto-publish** and **#70 the `parksheet` venture** are **APPROVED** — Stephen approved both on 2026-09-15 (prose in **#81**, machine-readable in **#85**, which carries `approves: [69, 70]` and is what the gates actually read), so publishing is unlocked *now* rather than at the old 2026-09-16 12:00 PT close. **That unlock is a capability, not a go: he wants to see one finished video and the ParkSheet sheet before the first live publish.** **#71 (T0, executed): the 20 API-uploaded YouTube videos are locked private and must be re-uploaded — see "Credentials & external state".**
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
  - **APPROVED #69 (T2, approved early 2026-09-15 by #85) — T1 has widened.** **YouTube Shorts, TikTok, Instagram Reels, blog posts and email nurture sends are T1 auto-publish**, each gated on a **mandatory second-agent fact-check that must return PASS** (any FIX FIRST blocks the entire week's batch, not just the item). **LinkedIn and Reddit stay human-in-the-loop** — their publishers write queue cards only. Publishing routes through Upload-Post, never `youtube_publish.py` (#71). The old "queues, not auto-posters" rule no longer gates the code — but **Stephen still wants to see one finished video and the ParkSheet sheet before the first live publish**, so the first run is his call, not the gate's. Details: `marketing/plan-2026-09-14-automation.md` Track 2; runbook `marketing/runbooks/automation-2026-09.md`. **#70** (same window, same approval) approves the separate `parksheet` venture.
  - **How a window is answered.** A T2 row carries `veto_window_close`; the gate (`scripts/ledger.py` → `veto_gate` / `t2_window_open`, used by `publish.py`, `schedule_week.py` and `send_reengage.py`) opens when **either** that window has elapsed unvetoed **or** a **later** entry's `approves` names the id. The ledger is append-only, so an early approval cannot edit the original row — it is a new entry carrying `approves: [69, 70]` (that is #85). The symmetric `vetoes: [69]` closes a window again, even one that has already elapsed, and **the last answering entry in the file wins**. **Only a later entry answers:** an **approval** needs a strictly greater id (so nothing approves itself and no old row pre-authorises a later decision), while a **veto** counts from the answered row onwards (id ≥), so a self-veto still closes the gate — a stop is never ignored on a technicality. Write both through `ledger.append(..., approves=[...], vetoes=[...])`, never by hand; `approves` is only accepted on a row whose status is `approved` or `executed`. A prose-only entry does **not** move the gate — that was the bug #81 exposed.
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
- **Debug Chrome** for UI-only work (Gumroad covers, MailerLite editor, manual YouTube uploads, **TikTok scheduling**): Stephen launches with `--remote-debugging-port=9222`, profile `~/.kdesk/chrome-debug`; drive it with `scripts/video/cdp.py` or Playwright `connect_over_cdp`. **TikTok:** Upload-Post reaches it only on the paid plan (declined 2026-09-15), so the week's Shorts are scheduled through TikTok Studio in this profile — `scripts/publishers/tiktok_web.py`, semi-supervised on a Saturday, never an Actions job (ToS grey area; runbook section "TikTok (Chrome, Saturday)"). The profile is **not** logged in to TikTok yet: sign in once with **Use QR code** at <https://www.tiktok.com/tiktokstudio>.
- **Linux box only** (`ssh wsl`, Tailscale `100.112.159.5`, unreachable since 2026-09-01): Cloudflare API tokens, `dist/` binaries. Nothing current depends on it.

## Useful commands

```bash
# Local preview
hugo server --port 1313

# Production build (Actions runs this on push to main)
hugo --minify

# The test suite. This exact command, and nothing but pytest + the standard library is
# available inside it — so every module a test imports must import cleanly with stdlib alone
# (put `import requests` / `yaml` / `playwright` / `openpyxl` INSIDE the function that needs it).
uv run --with pytest pytest tests/ -q

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

# Render a Short from a spec that lives anywhere on disk (--slug and --spec are mutually
# exclusive; the spec's own `slug:` key names the build directory under scripts/video/build/)
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --spec /path/to/scenes.yaml

# The `card` scene kind — a 9:16 card rendered from a scene's own data, no workbook, no
# LibreOffice recalculation. A spec whose scenes are ALL cards needs no Excel file at all,
# which is what makes a data Short (a ranking, a countdown, a what-changed list) cheap.
#   - kind: card
#     template: ranked_list | countdown | changed
#     data: {heading, subheading, items: [...]}
# ranked_list/countdown take up to 8 rows of {rank, label, value} (value "" drops the value
# column); `changed` takes up to 5 rows of {label, value} where value is a whole sentence.
# Past those caps cards.card_html raises rather than render type too small to read on a
# phone. Worked example of all three: marketing/video/card-demo/scenes.yaml.
#   - kind: card
#     template: calendar_heatmap | wait_curve        # the data-graphic pair (2026-09-16)
#     data: {heading, subheading, items: [...], footer}
# calendar_heatmap takes up to 42 {label, value, highlight} cells laid out 7 across — a month
# of crowd scores, value 1-10 mapped onto cards.HEATMAP_RAMP, `highlight: true` ringing one
# day in the brand accent. An out-of-range score is CLAMPED for both the colour and the
# printed number (99 colours and prints as 10), and a score the card cannot read as a number
# prints nothing rather than inventing one. wait_curve takes up to 16 {label, value} points plus
# `annotation: {label, index}`, and draws an inline SVG line with that point circled; the
# index is clamped, a flat series is safe, and there is no charting library (this file is
# stdlib-only). Both honour `box`/`fill`/`transparent` like every other template, so they
# work as a media overlay and under captions. ParkSheet builds their `data:` blocks in
# parksheet/graphics.py; nothing here knows about crowd scores.
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --spec marketing/video/card-demo/scenes.yaml

# The `media` scene kind — real footage or a still, under an optional card overlay. Same
# workbook-free deal as `card`: a spec whose scenes are all card/media needs no Excel file.
#   - kind: media
#     src: media/earth/magic-kingdom.mp4   # repo-relative to the SPEC FILE's own repo root
#                                          # (nearest .git / pyproject.toml above it), or
#                                          # absolute. .mp4/.mov/.m4v or .jpg/.jpeg/.png.
#     motion: punch | push | pan_left | pan_right | burst | kenburns | hold | clip
#             # the five new ones are image-only and (unless the scene blur-fills) pre-scale
#             # to 2x and run zoompan on a 2160x3840 canvas; kenburns is unchanged and is
#             # what every older spec uses
#             # default: kenburns for a still, clip for footage
#       clip      play it, trimmed to the narration (+0.6 s like cards), looped if shorter.
#                 VIDEO ONLY — on a still it hangs ffmpeg forever (0 bytes out), so it is
#                 refused.
#       kenburns  slow 1.0 -> 1.08 zoom. STILLS ONLY — zoompan counts INPUT frames, so on
#                 footage it silently encodes a freeze frame; refused.
#       hold      both kinds. On a still: one static frame. On a VIDEO: plays the clip
#                 through ONCE, then freezes the last frame for the rest of the scene.
#       punch     1.00 -> 1.15, cubic ease-out over 9 frames, then dead still. The shove.
#       push      1.00 -> 1.10, linear across the whole beat. The slow one.
#       pan_left  a fixed 1.12 crop travelling edge to edge, left or right.
#       pan_right
#       burst     a 4-frame hit to 1.08, settled back to 1.03 by frame 12. For a whoosh.
#                 STILLS ONLY, all five, and for the same reason kenburns is: they are
#                 zoompans. Each covers to 2x the render size first and runs zoompan onto
#                 media.ZOOMPAN_W x ZOOMPAN_H before the lanczos downscale — zoompan
#                 truncates x/y to whole INPUT pixels, so at the rates kenburns uses it
#                 freezes for up to 9 frames and then jumps one; the pre-scale halves that.
#                 kenburns keeps its own chain byte for byte, so no existing render moves.
#                 EXCEPT under a blur fill: a landscape source (or `fill: blur`) is
#                 composited at the render size first and the motion then runs on that
#                 finished 1296x2304 frame, so it gets none of the pre-scale's benefit and
#                 stutters the way kenburns does. A landscape hero that wants a punch should
#                 say `fill: crop` with a `focus:`, which puts it back on the 2x path.
#     Bad kind/motion pairings are rejected by media.check_motion, and the whole spec is
#     validated by media.validate_spec BEFORE anything renders — so a typo on scene 7 costs
#     nothing, instead of surfacing after six scenes have been narrated and encoded.
#     credit: "Imagery: Google Earth, Maxar Technologies"   # REQUIRED when src is a still
#     overlay: {template: …, data: {…}}    # optional; the `card` contract unchanged
#     fill: crop            # optional; crop | blur. Absent: the source's ratio decides
#                           # (media.BLUR_FILL_RATIO), which is today's behaviour.
#     focus: [0.50, 0.42]   # optional; what to keep when cropping. Default [0.5, 0.5].
#     beats:                # optional; TWO OR MORE sub-shots sharing this scene's one WAV.
#                           # Only the picture cuts — the narration and the caption cues are
#                           # untouched, because it is still one scene and one encode.
#       - {src: media/photos/a.jpg, seconds: 2.6, motion: punch,
#          crop: {zoom: 1.00, fx: 0.50, fy: 0.50},
#          credit: "Photo: Pexels",      # THIS PICTURE's own credit, not the scene's
#          credit_line: "Photo by A on Pexels (CC0)"}   # the long form; nothing reads it yet
#       - {src: media/photos/b.jpg, seconds: 2.4, motion: push,
#          crop: {zoom: 1.30, fx: 0.28, fy: 0.32}, credit: "Photo: Pexels"}
#                           # `seconds` is an ESTIMATE (the author counts words before
#                           # narrate.py has run); make_short.beat_spans rescales them to the
#                           # scene's real encoded duration so they sum to it exactly.
#                           # media only — `beats:` on a card scene is refused by name.
# By default the SOURCE's shape decides the fill: at or below media.BLUR_FILL_RATIO (0.8) it is
# scaled and cropped to FILL the 9:16 frame — no letterbox bars — and above it the whole picture
# is fitted inside the frame over a blurred, darkened copy of itself. `fill:` overrides that per
# scene: `fill: crop` makes a landscape hero fill the frame instead of sitting at ~35% of its
# height over blur, and `focus: [fx, fy]` aims the crop (fractions of the overflow; [0.5, 0.5]
# is the centre crop and emits the chain it always did, so nothing existing moves). Only the
# axis that actually OVERFLOWS moves: a source wider than 9:16 overflows horizontally only, so
# `fx` aims it and `fy` multiplies zero — `focus: [0.50, 0.42]` on a landscape hero is still a
# centre-height crop, and `fy` only bites on a source TALLER than 9:16. Both keys are validated
# in the media preflight, so a bad value stops the run before anything renders.
# `beats:` is the fix for the defect the v4 change set exists to remove — day 3 held ONE still
# for 32 s. The same scene as beats is nineteen pictures, none on screen for more than three
# seconds, against the same narration. Each beat becomes its own ffmpeg input and its own
# motion chain (the crop, the 2x pre-scale and the blur fill all behave exactly as they do for
# a whole scene), and the chains are joined by the `concat` FILTER inside one graph — so it is
# still one encode, one part and one WAV. Three things are load-bearing and all three were
# measured, not assumed: every chain ends at the render size, in `format=yuv420p` and at
# `setsar=1`, because concat refuses inputs that disagree on size, pixel format or SAR (a JPEG
# decodes yuvj444p and an .mp4 yuv420p: mixing them without this is `Error reinitializing
# filters!`, exit 234, no output file); and each chain closes on `trim=duration=,setpts=` or
# concat inherits zoompan's `d=` frame count and the beats overrun their WAV.
# Each beat's `src` and `motion` are its OWN — the motion is checked against THAT file's kind
# in the preflight and defaults per kind, so `punch` on an .mp4 beat is refused by name — and
# `crop: {zoom, fx, fy}` re-frames the source before it is covered, which is how several beats
# can be several shots of ONE photograph. Footage is never re-framed: a video beat's crop is
# dropped (`hold` is the one motion both kinds take, so it is the one that can arrive carrying
# a still's crop). The renderer refuses a one-entry list (one picture IS the scene) and any
# beat longer than make_short.MAX_PICTURE_S (6.0 s) — the estimate in the preflight, and then
# the RESCALED span once the narration's real length is known, because two 3.0 s beats are
# both legal and are two ten-second pictures against a 20 s narration.
# ATTRIBUTION follows the pictures. Under `beats:` the scene's own `src:` is never rendered, so
# each beat is asked for its OWN `credit:` — a licensed still borrowed into an uncredited
# footage scene is licensed on its own line — falling back to the scene's `credit:` when the
# beat has none (every spec written before the key existed). A still beat with no credit on
# either is refused in the preflight, by scene and beat index. The scene still burns ONE plate:
# media.scene_credits() is the scene's credit plus its beats', deduplicated and kept in
# first-appearance order, joined with ` · ` — five Pexels beats are one line, a Commons still
# beside them is a second. Verified in Chrome: three credits wrap to four lines that grow
# UPWARD inside media.credit_box and stay clear of the Earth Studio watermark zone. A scene
# with no `beats:` renders the plate it always rendered, and the graph it always built, input
# order included.
# A spec may also carry top-level `credits: [str]` and `disclaimer: str`. NOT YET WIRED: the
# renderer parses them and `cards.spec_credits(spec)` formats them (plus each media scene's own
# `credit:`) into a Credits block for a description, but NOTHING calls it yet — there is no end
# credits plate and no publisher hook. Only the per-scene `credit:` is actually burned in.
# Worked example of all of it: marketing/video/media-demo/scenes.yaml, which is deliberately a
# MIXED spec (media, card, media) because card and media parts must encode to the same stream
# for the `-c:v copy` concat to join them. Its two placeholder assets are synthetic and
# committed; marketing/video/media-demo/assets/generate.py remakes them.
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --spec marketing/video/media-demo/scenes.yaml

# How two parts MEET, and how much silence sits in the join (2026-09-18). All three keys are
# OPTIONAL and every existing spec — and every golden — renders byte-identically without them.
#   transitions:            # optional; absent == {join: fade}, today's 0.3 s dips to black
#     join: cut             # cut | fade   (xfade is a known value and refuses: not built)
#   short:
#     scene_pad: 0.10       # optional; frames held after the narration, default 0.25
#   tts:
#     lead_in_s: 0.05       # optional; silence prepended to every scene WAV, default 0.3
# `join: fade` fades every part from and to black over 0.3 s, so frame 0 is black and every
# join is black meeting black — `scdet` finds ZERO cuts in such a file. `join: cut` drops both
# `fade=` clauses (make_short.fade_steps is the only place that string is built); the parts
# still encode identically, so the concat demuxer still stream-copies them. `join: xfade` is
# accepted as a NAME and then refused: it needs every part as its own ffmpeg input with an
# explicit offset, which replaces the concat stream copy — make_short.xfade_offsets() is the
# arithmetic that rewrite will need. The silence a viewer hears at a join is this scene's
# `scene_pad` plus the NEXT scene's `lead_in_s`: 0.25 + 0.3 = 0.55 s at the defaults, 0.15 s
# at the v4 pair above. `lead_in_s` is deliberately NOT in narrate.py's cache key: it changes
# no byte the provider generates, so a key that included it would have invalidated every meta
# written before it landed. The per-scene meta records it and the cache-hit branch compares it,
# defaulting to 0.3 so older metas stay hits. CHANGING IT IS NOT FREE: a changed lead-in misses
# the cache and RE-SYNTHESIZES every scene, which on ElevenLabs is a billed request each — the
# provider's mp3 is unlinked after decoding, so there is nothing to re-decode locally. Pick it
# once per spec; do not tune it by trial on an ElevenLabs voice.

# SOUND (2026-09-19). A music bed under the narration, ducked out of the way by the voice
# itself, plus a whoosh on each structural beat boundary. OPTIONAL and off by default: with no
# `audio:` block the final pass emits exactly the chain it always emitted
# (`[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]`, or the same `-af` on the uncaptioned stream
# copy) and every golden and existing Short is byte-identical.
#   audio:                  # optional; absent == today's plain loudnorm and nothing else
#     bed:
#       src: media/audio/mixkit-forest-treasure-138.mp3
#       lufs: -13.2         # REQUIRED: the asset's measured integrated loudness
#       target_lufs: -22    # bed level BEFORE ducking
#       fade_in: 0.6
#       fade_out: 1.2
#     duck: {threshold: 0.03, ratio: 8, attack: 5, release: 300}   # ~10-11 dB, measured
#     sfx:
#       on_cut: media/audio/mixkit-cinematic-whoosh-1492.wav
#       gain_db: -6
#       lead: 0.20          # start this far before the boundary so it peaks on it
#       beats: 3            # whooshes land on the 2 boundaries between 3 beats, not on cuts
#     master: {lufs: -16, tp: -1.5, lra: 11}
# The whole mix rides the pass that already re-encodes the audio, so it costs almost nothing:
# measured at 3.4 s for 43.6 s of output with `-c:v copy`. The graph is make_short.audio_steps
# and every stage earns its place — two of them are traps:
#   * `sidechaincompress` is `[main][sidechain]`: the BED is the main and the VOICE is the key.
#     Reversed, it ducks the narration under the music.
#   * `amix=...:normalize=0` is essential. With the default normalize=1 ffmpeg divides every
#     input by the input count, so ADDING A WHOOSH quietly drops the voice by 6 dB.
#   * `dropout_transition=0` stops amix ramping gain when the short SFX inputs end.
#   * `alimiter=limit=0.97` goes BEFORE loudnorm, so one whoosh-plus-voice transient cannot
#     force loudnorm into a big negative offset.
#   * `adelay` is milliseconds PER CHANNEL: `adelay=2747|2747` for stereo.
# `bed.lufs` is REQUIRED and is measured ONCE, at vetting time, into the asset's manifest row —
# the gain is `target_lufs - lufs`. A one-pass `loudnorm` on the bed inside the render is
# dynamic, so the mix would depend on where the loop lands. The bed is `-stream_loop -1` and
# `atrim`ed to the FINISHED runtime (the sum of the encoded parts, which INCLUDES the closing
# CTA plate — `sum(scenes[].seconds)` in cuts.json is short by the plate's 1.5 s and a bed cut
# to it would fade out before the last picture). The whooshes go on `beat_boundaries()` — the
# cut nearest each of the `beats - 1` divisions of the runtime — NOT on every cut: a whoosh on
# all sixteen picture changes is a cartoon, and the ear habituates to it by the third.
# `bed.lufs` is checked, not just required: ebur128 reports NEGATIVE LUFS, so a positive one
# is a sign flip (`lufs: 13.2` for a -13.2 asset gains the bed -35.2 dB and ships a Short with
# an inaudible bed, rc 0, no word said), and a computed gain past +/-30 dB
# (make_short.BED_GAIN_LIMIT_DB) is a typo in one of the two numbers. `sfx.beats` must be 2 or
# more — `beats - 1` boundaries means one beat places no whoosh at all. `duck:`, `master:` and
# `sfx:` without a `bed:` are refused: there is no bed-less path through the mix, so they would
# be read and then ignored.
# A missing bed or sfx file REFUSES the render by name: a Short meant to carry music that came
# out silent is indistinguishable from one that never asked for any. Audio is fetched BY HAND;
# nothing here downloads it. The bed and sfx inputs are queued AFTER the caption PNGs so no
# overlay's input index moves. Measured on the round-1 day-3 build (rc 0, 3.4 s): I -16.4 LUFS,
# LRA 1.8 LU, and the quietest 5% window went from -37.7 dBFS to -26.5 with 0.0% of windows
# below -60. Levels and the duck sweep: ParkSheet docs/research/2026-09-19-production-techniques.md
# section 5.

# NEVER DRAW IN THE BOTTOM-RIGHT 55% x 12% OF A FRAME (x >= 0.45, y >= 0.88). That is where
# Google Earth Studio burns its attribution watermark ("Google Earth" plus a data-provider
# line), and the imagery terms require it to stay visible — covering it is a licence breach,
# not a layout preference. MEASURED 2026-09-16 on the first real Earth Studio portrait render
# (1080x1920, cloud video, Attribution Position bottom-right at its maximum offsets): the
# "Google Earth" wordmark sits at x 0.495-0.815, y 0.909-0.933, and the provider line under it
# reaches y 0.955. Earth Studio will not push it further right or lower on a portrait canvas.
# The mark is anchored bottom-right but is NOT in the corner — it starts at mid-width and stops
# 4.5% of the height above the bottom edge — so the old 20% x 8% corner zone (x >= 0.80,
# y >= 0.92) covered the corner and almost none of the mark. The rule is
# media.WATERMARK_W_FRAC / WATERMARK_H_FRAC and everything derives from it: the credit plate is
# anchored bottom-LEFT and now stops at x 0.438 (~0.38w wide, so a real credit wraps to two
# lines — that is fine and tested), the card overlay's bottom edge stops at y 0.868, leaving
# the card ~47% of the frame. tests/test_media.py checks the boxes never intersect the zone or
# the measured mark, and tests/test_media_scene_e2e.py checks the PNGs Chrome actually drew are
# transparent there and that the narrowed credit plate stays inside its box — so a CSS tweak
# that dodges the constants still fails. A still must carry a `credit:` (footage can credit
# itself on screen; a still cannot) and build_video/make_short refuse the render without one.

# Word-timed ("karaoke") burned-in captions — per spec (2026-09-15). OFF unless a spec asks, Captions render in ALL CAPS via CSS `text-transform: uppercase` (Stephen, 2026-09-16); cue text and words.json stay as spoken.
# so every existing Short and every golden is unchanged. Only marketing/video/media-demo turns
# them on today; ParkSheet sets the same key from its own `cards.build_spec` (that repo is not
# edited from here — the key below is the whole contract).
#   captions:
#     enabled: true
#     accent: "#ffe234"     # HEX ONLY — it is interpolated into CSS unescaped, and refused
#                           # otherwise. The spoken word wears it; the rest of the cue is white.
#     position: center      # top | center | lower   (default: top). The top band sits on the
#                           # blurred letterbox of a media scene rather than on the picture.
#                           # A `kind: card` scene OVERRIDES this back to the top band (the
#                           # card is drawn below it); make_short says so on stdout.
#     size: large           # default | large  (default: default). `default` IS the day-3
#                           # geometry — band 0.16 of the frame, type 0.30 of the band, one
#                           # line — and every existing Short renders byte-identically under
#                           # it. `large` is 0.185 / 0.347 over two lines: 92.1 px -> 123.2 px.
#     pop: 1.14             # scale the lit word; 1.0 (default) emits no extra CSS at all
#     hook_seconds: 3.0     # cues starting before this take a 2-word / 14-char cap
# --captions / --no-captions on make_short.py override the block either way.
#
# A cue is a PHRASE, not a sentence: <= 3 words and <= 20 characters, broken at a sentence end
# always and at a comma once it has two words (inside the `hook_seconds` window: 2 words and
# 14 characters). Type is sized to the cue's LONGEST WORD as well as its character count —
# CSS cannot break inside a word and the caption page is overflow:hidden.
# A cue holds the screen until the next one starts
# (capped at 2.2 s of silence) so the top of the frame never flickers, and inside a cue word k
# is lit from its own start until the NEXT word's start. Rules and geometry: scripts/video/
# captions.py, ported from kdeskgames/word-chain/video/captions.mjs.

# The HOOK PLATE (2026-09-19). The feed judges frame 0, and frame 0 has to carry subject +
# big text. A separate title scene would cost a scene's worth of a <= 59 s runtime; one
# transparent full-frame PNG in the pass that is ALREADY overlaying captions costs one extra
# ffmpeg input and nothing else. OPTIONAL — absent, the graph, the inputs and the output are
# byte-identical to what they were.
#   short:
#     plate:                # optional; needs captions: {enabled: true}
#       text: HIDDEN MICKEYS
#       kicker: EPCOT       # optional, in the caption accent, above the headline
#       seconds: 1.4        # (0, 4.0]; the plate's window, from t=0
#       position: center    # top | center | lower  (default: center; captions.POSITIONS)
# The plate is input 1 of the caption pass, overlaid full-frame at (0, 0) and gated to
# `enable='between(t,0,SECONDS)'`; the word PNGs shift to inputs 2..n
# (make_short.caption_filter). ALL CAPS like every caption, white headline at 0.097 of the
# frame height over a 0.027 kicker in the accent, both on a dark stroke with
# `paint-order: stroke fill` (captions.PLATE_*_FRAC).
# EVERY CAPTION CUE STARTING INSIDE THE PLATE'S WINDOW IS DROPPED (captions.drop_inside): the
# plate IS the hook text, and a word-by-word caption running underneath it is two texts on the
# one frame the viewer reads fastest. A plate on a spec with captions OFF is REFUSED, not
# silently ignored — the uncaptioned join is a stream copy with nowhere to put an overlay.
#
# NO WORD OF `text:` MAY EXCEED 7 CHARACTERS (captions.PLATE_MAX_WORD_CHARS, derived from
# PLATE_HEADLINE_PX_FRAC / FONT_EM_PER_CHAR / SAFE_X_FRAC and refused BY NAME at preflight).
# Unlike a cue, the plate has no step-down: it burns one fixed type size on an
# overflow:hidden page that cannot break inside a word, so an 8-character word is CLIPPED at
# the frame edge rather than shrunk. "HIDDEN MICKEYS" clears it by one character. Move a long
# word to the `kicker:`, which is a fifth of the size.
# A PLATE OVER A `kind: card` FIRST SCENE IS SKIPPED, with a line on stdout: that card IS the
# frame-0 text, and the plate — which places itself on captions.BAND_CENTER_FRAC, knowing
# nothing of scene 0's layout — would print the Short's biggest type through the card's own
# copy. Nothing is drawn and no cue is dropped, so the word-by-word captions carry the hook.

# The closing CTA plate is now OPTIONAL. A `short:` block with a `cta:` renders exactly as it
# always has. A block with `signoff:` and NO `cta:` renders with no terminal plate at all --
# that is ParkSheet's script v2 (2026-09-16): a <= 6-word sign-off spoken OVER the payoff
# frame rather than a plate after it, because the plate spends the highest-retention second
# of the Short on an ask and no platform's ranking documentation rewards one. ParkSheet's
# spec therefore carries `short: {hook, scenes, signoff}`. --end-card / --no-end-card on
# make_short.py override the spec either way; --end-card on a spec with no `cta:` raises,
# because there is no copy to put on the plate. Decision-relevant for this repo: every
# existing KDesk spec carries `cta:`, so nothing here changes. `signoff:` is narration copy
# that ParkSheet writes into its own scene text; make_short does not read the key.
#
# TIMINGS come from `scene_NN.words.json`, which narrate.py now writes beside every scene WAV:
# [{"text","start","end"}] in seconds against the FINISHED WAV — after the silence trim and the
# 0.3 s lead-in, because that is the audio make_short concatenates. ElevenLabs supplies them
# from /v1/text-to-speech/{voice}/with-timestamps (same body, JSON back with audio_base64 +
# alignment), so there is no second billed request. KOKORO CAVEAT: its MTokens carry
# start_ts/end_ts only when the ENGLISH G2P ran (lang_code "a"/"b"); any other language writes
# `null` and that scene renders uncaptioned with one line saying so. The words file is part of
# the cache — a scene cached before this existed re-synthesizes once (free on Kokoro, one
# request on ElevenLabs); the cache KEY did not change.
#
# WHERE THEY SIT: a band centred on 22% of the frame height, inside the Shorts safe zone
# (middle 80% of the width, nothing below 75% of the height), so nowhere near the Earth Studio
# attribution corner. It shrinks — then lifts — to clear a media scene's card overlay
# (media.overlay_box). A scene whose OWN layout owns the top of the frame is skipped rather
# than overprinted, out loud: that means every full-frame `kind: card` scene and every legacy
# sheet/pan scene (whose hook band starts at y=0). Captions are for imagery, not for a card
# that is already all text.
#
# A `kind: card` scene is NOT skipped: the CARD moves instead, into the frame below the band
# (make_short.card_box_under_captions -> cards.card_html's `box`/`fill`), so a card-only data
# Short is captioned too. Only the legacy sheet/pan layout is skipped, because its hook band
# really does start at y=0. Captions off = no box passed = the full-frame card, byte-identical.
#
# HOW: one transparent PNG per spoken word (this ffmpeg has no drawtext), composited with
# `overlay ... enable='between(t,a,b)'` in the pass that ALREADY concatenates the parts — that
# concat was a `-c:v copy`, so a captioned Short costs exactly one re-encode, loudnorm and all,
# not a second pass. Scene offsets are measured from the encoded parts (one ffprobe each) so a
# frame of rounding per scene cannot drift the highlight off the syllable.
# A captioned render writes scripts/video/build/<slug>/short/captions.json — the plan it
# actually burned in (band, accent, one row per word window with its cue, lit word and PNG).
# It answers "which word was on screen at 12.3 s?", and tests/test_captions_e2e.py reads it to
# check the real render against real pixels; those two tests SKIP until the demo below has been
# rendered in this checkout, so render it before trusting a green suite on caption geometry.
# EVERY render — captions or not — also writes scripts/video/build/<slug>/short/cuts.json:
# the renderer's own cut list (`join`, `duration_s`, `cuts`, and a row per scene with its beat
# spans). `scdet` cannot see a dip-to-black join — it finds ZERO cuts on the published day-3
# Short — so this file is what any cadence check should read; the pixel detectors are smoke
# tests. `cuts` is absolute seconds, every picture change after frame 0 — part boundaries and
# beat boundaries alike; a scene row's `beats` are the spans it was cut into. The closing CTA
# plate has no scene index and so no row, but its join IS in `cuts`: read `duration_s` for the
# runtime, never the sum of the rows, which is short by the plate.
scripts/video/.venv-tts/bin/python scripts/video/make_short.py \
  --spec marketing/video/media-demo/scenes.yaml            # captions: on in that spec
scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug asc842 --no-captions

# Narration provider — per spec (2026-09-15). No `tts:` block, or a legacy top-level
# `voice: am_michael`, still means Kokoro (local, free), so every existing spec is unchanged.
#   tts:
#     provider: elevenlabs           # or kokoro
#     voice: pNInz6obpgDQGcFmaJgB    # ElevenLabs voice_id; for kokoro, the Kokoro voice name
#     model: eleven_multilingual_v2  # flash/turbo bill 0.5 credit/char, everything else 1
#     stability: 0.5                 # optional voice_settings; these two are the defaults
#     similarity_boost: 0.75
# Key: ELEVENLABS_API_KEY, else ~/kdesk-analytics/elevenlabs-api-key.txt (0600). Never printed —
# every error string goes through session.redact_secrets first. NO KEY = one loud stderr line and
# Kokoro narrates instead, so dry runs and CI keep working; each scene's meta JSON records
# `provider_used`. An ElevenLabs HTTP failure (401/402/429/5xx) exits 2 rather than mixing voices
# in one video — pass --allow-fallback to narrate only the failed scenes locally, and a transport
# error (dropped connection, timeout) is handled the same way. The cache key covers provider/
# voice/model/voice_settings/text, so unchanged text is never re-billed.
# `--speed` is a KOKORO control: ElevenLabs takes a rate only inside voice_settings, so on an
# elevenlabs spec any --speed but 1.0 is refused unless the spec carries a matching `tts.speed`
# (otherwise a stray flag re-bills a whole spec for byte-identical audio), and the top-level
# speed is not part of the ElevenLabs cache key.

# Prove the ElevenLabs path BEFORE spending credits: does the configured voice_id exist? (exit 0/2)
scripts/video/.venv-tts/bin/python scripts/video/narrate.py --spec <spec> --tts-check

# Refuse to render at all unless narration resolves to the named provider — exit 2 before any
# synthesis, before the output directory is even created. Use it on every PAID batch: without
# it a deleted key file renders the whole run in Kokoro and exits 0, and the only trace is one
# stderr line nobody reads in a scheduled job. --allow-fallback still wins per scene.
scripts/video/.venv-tts/bin/python scripts/video/narrate.py --spec <spec> --out <dir> \
  --require-provider elevenlabs

# What a render would cost: per-scene character counts, the total, the credit estimate. No network.
scripts/video/.venv-tts/bin/python scripts/video/narrate.py --spec <spec> --dry-run

# DO NOT RUN — youtube_publish.py uploads land LOCKED PRIVATE and cannot be recovered (ledger #71).
# Anything it uploads is dead on arrival: no appeal, no Studio flip, re-upload is the only fix.
# uv run scripts/video/youtube_publish.py --kind short --slug asc842 --variant liability
# Publish through Upload-Post instead (Phase 1), or upload manually in the debug Chrome.

# List the 20 locked-private videos, whether each mp4 is ready, and re-upload once UPLOAD_POST_KEY exists (zero writes with --dry-run)
python3 scripts/video/reupload_locked.py --dry-run

# TikTok via Chrome (Upload-Post's TikTok needs the paid plan Stephen declined, 2026-09-15).
# Semi-supervised, Mac-only, Saturday — never an Actions job. Runbook: "TikTok (Chrome, Saturday)".
python3 scripts/browser/session.py --check tiktok                  # is the debug Chrome still logged in?
python3 scripts/publishers/tiktok_web.py --check                   # read-only: every Studio anchor resolves
python3 scripts/publishers/publish.py --platform tiktok_web --asset <mp4> --meta <json> \
  --schedule 2026-09-21T14:00:00-07:00 --dry-run                   # one post; the offset is REQUIRED
# The week's batch: day-N.mp4 + day-N.json in DIR onto the week's days at 14:00 Pacific.
# Idempotent — a day already on the posts list is skipped. 0 all ok / 1 any queued / 2 hard error.
python3 scripts/publishers/schedule_week.py --week 2026-W39 --assets-dir <DIR>   # dry run: the DEFAULT
python3 scripts/publishers/schedule_week.py --week 2026-W39 --assets-dir <DIR> --hour 14:00 --go
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

**Phase 1 of the automation engine is built and tested (2026-09-15); it is not yet live.**
Work from the runbook, not from this section: **`marketing/runbooks/automation-2026-09.md`** —
pipeline map, one command per stage, current phase, open vetoes, the "if X is broken do Y"
table, the two GitHub Actions schedules, the `gh secret set` commands and the launchd handover.
The reasoning behind it is `marketing/plan-2026-09-14-automation.md`; the revenue plan of record
is still `marketing/plan-2026-09-10k-portfolio.md` ($10k/mo, five streams, review 2026-12-01).

**What Phase 1 shipped:** the ledger writer · a reusable Chrome/CDP session layer with
per-site preflight and queue cards · the Upload-Post publisher stack (`youtube` · `tiktok` ·
`instagram` · `site`) behind one `publish.py` · the locked-video re-upload driver · the `card`
scene kind for data Shorts · the private Google-Sheet CRM sync · the veto-gated re-engagement
sender · the daily digest · `data-weekly.yml` and `daily-publish.yml`.

**Three things gate going live.** (1) ~~Ledger #69's veto window~~ **CLEARED 2026-09-15: #85
approves #69 and #70**, so `publish.py`, `schedule_week.py` and `send_reengage.py` report the
gate open and no longer exit 2. There is still no override flag — the unlock is a ledger entry,
not a switch — and **Stephen wants to see one finished video and the ParkSheet sheet before the
first live publish**. (2) Stephen's
Upload-Post account with the KDesk channel connected, plus the repository secrets in the runbook.
(3) The first Saturday render batch on the Mac, which is where the mp4s come from.

**Weekly cadence:** Monday launchd pulls GSC + GA4 + target queries + Gumroad + YouTube; the
scoreboard adds subs, 28-day views and the Shorts/long-form split. **Always run the second-agent
GAAP fact-check before publishing** — all four articles so far came back FIX FIRST. One LinkedIn
draft per article; one outreach batch; nothing sends without Stephen.

**Waiting on Stephen:**
1. ~~Approve or veto #69 and #70 by 2026-09-16 12:00 PT.~~ **DONE 2026-09-15 — both APPROVED (#81 in prose, #85 as the `approves: [69, 70]` entry the gates read).** #69 = marketing autonomy loosened to T1 auto-publish (Shorts/TikTok/Reels/blog/email) behind a mandatory fact-check gate, LinkedIn + Reddit still manual. #70 = launching the separate `parksheet` subscription-sheet venture (30-day test first, < $100). **What is still his: one finished video and the ParkSheet sheet to review before the first live publish.** A change of mind is an entry with `vetoes: [69]` (or 70), which closes the gate again. *(The old item here — "flip the 12 new Shorts to public in Studio" — was impossible and has been removed: those uploads are locked, see ledger #71.)*
2. **Create an Upload-Post account and connect the KDesk YouTube channel** (free tier = 10 uploads/mo, covers YouTube + Instagram; TikTok needs the paid plan ~$16–24/mo). It holds audited credentials, which is what unblocks publishing at all. This is the gate on Phase 1.
3. **Create the venture's accounts** (only if #70 is not vetoed): a **new Google account** to own the Sheet/YouTube channel/Gumroad login, a **separate Gumroad account** (Lemon Squeezy is the fallback if Gumroad refuses a second), and **TikTok + Instagram professional accounts** — then connect all of them to Upload-Post. Nothing KDesk-branded touches this brand.
4. **Mint a Cloudflare API token** (Workers + D1 edit) for the `gumroad-ping` membership-sync Worker — the old tokens were on the dead Linux box.
5. **Submit the YouTube API Services compliance audit** (Google Support → "YouTube API Services – Audit and Quota Extension Form", project `involuted-disk-489017-r3`). Note what this does and does not do: it unlocks **future** API uploads only — it does **not** free the 20 already-locked videos, which must be re-uploaded regardless (#71).
6. ~~Repricing veto (decision 52)~~ **Executed 2026-09-06 22:20 PT (decision 61): ASC 842 $249, ASC 606 $249, bundle $599 (list $693).** **RSU Tax Planner — LIVE 2026-09-07 08:30 PT (decision 63)** at `/templates/rsu-planner/` and `/l/dqqhk`; ~~Stephen flips `-rfZDelJQMY`, `nvp8_qt5-4g`, `PUNOPlq4s08`, `dMEWoIS5DXw` public.~~ **Not possible — all four are API uploads and are locked private (#71); they must be re-uploaded.** **Commission Kit veto (decision 57):** the $1,997 listing goes live and its page publishes after **2026-09-07 11:00 PT** unless he objects — and only once the six documents' fact-check has passed (task #7).
7. Read IBM's outside-activities / conflict-of-interest policy → join 3–4 expert networks (Stream D).
8. VA 90% → 100% claim (+$1,083/mo tax-free, cuts the safety net 25%; do not touch the PTSD rating).
9. Reply on `marketing/outreach/batch-2026-09-07.md`; Reddit account; LinkedIn #17; free sign-ups (Eloquens, Featured.com, Source of Sources, Qwoted). *Done 2026-09-04: OAuth consent, the Bill Hanna DM, the customer-discovery emails.*
10. **Send the re-engagement email** to the 14 downloaders the nurture skipped. The sender exists now — `scripts/sales/send_reengage.py` reads the recipients from the private store (`~/kdesk-analytics/private/`, 0600), renders the tracked copy in `marketing/email-sequences/re-engage-2026-09.md` and sends one message at a time through `gws`. It refused to send until #69 was answered; **#85 answered it (approved), so the gate is open** — `--dry-run` still renders all 14 and sends nothing, and it is what to run first. **Submit the three affiliate applications** — `marketing/affiliates/applications-2026-09.md` (FinQuery Referral Partner first).
11. Gumroad "What's your role?" checkout question — the API accepts `custom_fields[]` and silently drops them; add it in the Gumroad editor (or via the CDP pattern) on the free listings.

**Next builds (Claude, in order):** #69 is approved (#85), so the gate is open — first live `publish.py` run from the Saturday batch, **after Stephen has seen one finished video and the sheet**, then the re-engagement send (`send_reengage.py --dry-run` first, always) · reconcile the Actions artifact's ledger rows into the Mac's copy · re-upload the 20 locked videos through Upload-Post (`reupload_locked.py`, free tier is 10/mo so it takes two months) · Shorts at ~5/week, including card-only data Shorts · cross-link the ASC 340-40 kit from the three commission posts and the ASC 606 page · Phase 2 items live in the runbook, not here.

**Recent decision context:** the ledger is the record — `python3 scripts/ledger.py --tail 10`. The ones that still shape the work: **51** portfolio pivot · **52/61** repricing executed (ASC 842 $249 · ASC 606 $249 · bundle $599) · **63** RSU Tax Planner live · **69/70** approved early by **#85** (`approves: [69, 70]`; the gates read that field, not prose) · **71** the YouTube uploads are locked and must be re-uploaded · **76–79** the privacy containment rounds (public repo: addresses and the CRM sheet id out of tracked files).

## Privacy (this repo is PUBLIC)

`github.com/kdeskaccounting/kdeskaccounting.github.io` is public. Everything tracked here is
world-readable, forever, including in history.

**Never commit a third-party email address, name+address pair, or any other customer contact
detail.** KDesk's own published addresses (`santiagokdesk@`, `@kdeskaccounting.com`) are fine —
they are meant to be findable. This is enforced, not just advised: `tests/test_no_third_party_emails.py`
scans **every tracked file in the repo, repo-wide** — not a hand-listed set of directories, because
the third leak sat in a directory the directory-listed version of the test did not look at — and
fails on any address that is not KDesk-own or an RFC 2606 reserved domain (`example.com`,
`*.example`, `*.test`, `*.invalid`). Its `ALLOWED_LITERALS` set is deliberately tiny — if you find
yourself adding to it, use a reserved domain instead.

**KDesk-own means exactly two domains: `kdeskaccounting.com` and `kdeskconsulting.com`** (plus the
`kdeskaccounting.gumroad.com` storefront). `kdesk.com` is **not** ours — it sat in the test's
`OWN_DOMAINS` on resemblance alone until 2026-09-15, which was a standing permission to publish
every address at a domain that could belong to anyone. An entry there needs ownership *and* a
tracked file that uses it.

**No private handle in a tracked file either.** A Google file id — a spreadsheet, document or
Drive folder handle — is the whole access story for the file it names, and a *folder* handle is
an index of everything ever put in it. `tests/test_no_private_ids.py` fails on two shapes, and
only these two: a base64url token mixing case and digits that is **40+ characters within 100
characters of the word "sheet"**, or **33+ characters within 100 characters of a Google
document/spreadsheet/Drive-folder URL** (the URL is the evidence that a shorter token opens a
private file; a folder id is commonly 33). It is not a general secret scanner — a handle with
neither kind of context next to it goes unnoticed.

The private "KDesk CRM" sheet's id lives only in `~/kdesk-analytics/crm-sheet-id.txt` (0600);
anything tracked refers to the sheet by title. Four handles have already had to be redacted in
place: the CRM sheet id out of ledger entry 75 (entry 79), and a Doc handle, its Drive folder
handle and two outreach notes' Doc handles (entry 80). Redacted handles become
`<redacted-doc:XXXXXXXX>` — `privacy.handle_hash`, which unlike `email_hash` does **not**
lowercase, because a Drive id is case-significant — with the originals in
`~/kdesk-analytics/private/redaction-map-2026-09-14.json`, so the edits are reversible.

Two things to know before redacting the next one. The sheet id got out through the **digest**,
which re-emits ledger lines into `$GITHUB_STEP_SUMMARY`, a public workflow log — so a tracked
audit log is a leak with a delivery mechanism attached. And the window rule is **order-dependent**:
shortening one handle to a marker can pull a second token into the same URL's 100-character
window, so a redaction pass must iterate to a fixed point (that is how entry 66's second handle
was found, after the first pass declared itself done).

**One scrubber, one `gws` seam.** `scripts/gws.py` owns both: `run()` keeps only the FIRST line of
`gws` stderr (it echoes the request it choked on, `--json` body and all), and `scrub()` masks known
credentials, elides base64-shaped runs of 40+ characters (and 33+ next to a Google document URL)
and swaps every remaining address for a `<redacted:XXXXXXXX>` marker. Anything that becomes a queue card, a ledger line, stdout or CI
output goes through it.

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
