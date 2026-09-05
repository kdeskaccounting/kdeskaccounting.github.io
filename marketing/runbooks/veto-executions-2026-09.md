# Runbooks — the approved T2 actions waiting on their veto windows (written 2026-09-05)

In-session timers exist for each of these (session-only; they die with the session). If a new session is
running at the time, execute from here. Nothing below sends email or posts publicly on Stephen's behalf; each
step is an approved decision whose 48-hour veto window has closed unless he objected in the meantime.
**Always `cd` explicitly or use absolute paths — the shell cwd drifts.**

## 1 · Repricing — decision 52 · window closes Sun 2026-09-06 22:00 PT
1. `cd ~/kdeskaccountingtemplates` (token in `.env`). ASC 842 workbook `Gp9nwTmverZnmQqvQe_afg==` $97 → **$249**
   (`price` 24900); SaaS Controller Bundle `WAKdGcEmy476e-5fWioVsQ==` $249 → **$599** (59900) — via
   `python3 gumroad_publish.py update --id <id> --config <json>` or a direct `PUT /v2/products/<id>` with `price`.
2. Paid ASC 606 (`/l/mwmwpe`) is hidden from `GET /products`; find its id via `GET /v2/sales` product_id fields or
   the debug Chrome; if not found, leave it at $79 and note it.
3. Site: `price:` in `content/templates/asc842/index.md` and `bundle/index.md` (+ `asc606` if repriced); "$97" /
   "$249" / "$79" mentions in those pages' FAQ and compare copy, `layouts/calculator/single.html` CTAs, and the
   homepage; `hugo --minify`; commit + push; verify live.
4. Records: append a decision "repricing executed" with the NEXT free id (don't edit #52's line; #58 is the kit fact-check outcome); CLAUDE.md "Currently at" + Stephen's
   list item 3; vault daily note line.

## 2 · RSU Tax Planner publish — decision 56 · window closes Mon 2026-09-07 08:00 PT (task #6)
1. `cd ~/kdeskaccountingtemplates && python3 gumroad_publish.py publish --id n5PlxijnuNvTLMOLryYCUw==`; confirm
   `published: true` at https://kdeskaccounting.gumroad.com/l/dqqhk.
2. `draft: false` in `content/templates/rsu-planner/index.md`; hugo build; commit + push; curl
   https://kdeskaccounting.com/templates/rsu-planner/ until 200.
3. Homepage / templates list pick-up if not automatic; on `/rsu-tax-calculator/` add the product link to the CTA
   (keep the email capture).
4. Append a decision (next free id) "RSU Tax Planner published"; CLAUDE.md; vault. Ask Stephen to flip `-rfZDelJQMY`, `nvp8_qt5-4g`, `PUNOPlq4s08`,
   `dMEWoIS5DXw` public in Studio.

## 3 · ASC 340-40 Commission Kit publish — decision 57 · window closes Mon 2026-09-07 11:00 PT (task #7)
**Gate:** the second-agent fact-check of the six documents returned PASS, or every must-fix was applied in
`~/kdeskaccountingtemplates/templates/asc606-kit/build_kit.py`, tests green
(`uv run --with pytest --with python-docx pytest tests/test_asc606_kit.py -q`), dist rebuilt
(`uv run --with python-docx python templates/asc606-kit/build_kit.py`) and the zip re-attached
(`python3 gumroad_files.py JDJrWvrxH8JMkQ2fbBKS2g== templates/asc606-kit/dist/ASC340-40_Commission_Kit_v1.zip`).
**Gate status 2026-09-05 15:40 PT: satisfied** — the independent review returned FIX FIRST, every must-fix and nice-to-have was applied (Kit v1.1, decision 58), 23 tests green, zip re-attached. Arithmetic independently recomputed: 33/33 figures reproduce. Only the veto window remains.
1. `python3 gumroad_publish.py publish --id JDJrWvrxH8JMkQ2fbBKS2g==` (https://kdeskaccounting.gumroad.com/l/tngbwg).
2. `draft: false` in `content/templates/asc606-kit/index.md`; cross-link the kit from the three commission posts
   and from `content/templates/asc606/index.md`; hugo build; commit + push; verify live.
3. Append a decision (next free id) "kit published"; CLAUDE.md; vault; plan Stream E status. Ask Stephen to flip `U16RwefK0Pc` and
   `72PLil0VmQw` public.
If the gate does not hold, do not publish — report what's outstanding.

## 4 · Monday scoreboard — Mon 2026-09-07 ~08:45 PT
After launchd `com.kdesk.daily-sync` (08:15) appends the weekly rows (verify; run `uv run scripts/pull_youtube_snapshot.py`
if the YouTube row is missing), post 5–7 lines to `~/CommandCenter/01-Daily/2026-09-07.md`: Google clicks/day and
organic sessions/day; free downloads MTD and full-price sales lifetime (THE metric); subscribers; target queries on
page 1 of 24 with deltas; YouTube subs / 28-day views / Shorts share; revenue vs the ladder ($2k → $4,246 safety net
→ $10k); open/closed decision windows; what Stephen still has to flip or send. Commit + push the vault. Never present
the safety net as the target.
