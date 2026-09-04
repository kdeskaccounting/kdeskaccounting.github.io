# Reddit account: 10-minute setup (Stephen) + the aging rules

**Why:** Reddit threads in r/Accounting and r/excel rank on Google for the exact questions our articles answer, and controllers ask there. A new account that drops links gets removed and shadowbanned; an account that has answered questions for three weeks does not. Stephen owns the account; Claude drafts every comment; nothing is posted without Stephen pasting it.

## Setup (once, ~10 minutes)

1. Create the account at reddit.com in your normal browser (not the debug profile), with a personal email, not santiagokdesk. Do not use "KDesk" or "CPA" in the username: the license is inactive and brand handles get treated as spam. Suggested handles: `revrec_closer`, `saas_controller_notes`, `month_end_mike` (pick anything you'd be comfortable being identified with later).
2. Profile: no link in the bio for now. One line is enough: "Sales-comp and technical accounting, SaaS. Excel more than I'd like."
3. Turn on two-factor auth (Settings → Safety & Privacy).
4. Join, in this order: **r/Accounting**, **r/excel**, **r/FPandA**, **r/SaaS**, **r/Bookkeeping**. Browse each for five minutes so the account has history before it comments.
5. Send Claude the username so drafts can match the voice (nothing else is needed; Claude never logs in).

## Aging rules (weeks 1–3, from the account creation date)

- Two comments a week, drafted by Claude from `marketing/reddit-templates/` Version A (no links). Paste, adjust one phrase so it reads like you, post.
- Answer only where the question is genuinely one we know cold (ASC 842, commissions / 340-40, fixed assets, close process, SaaS metrics, runway). Skip anything tax, anything personal-finance, anything about a specific employer.
- Upvote a few good answers in the same threads. Never downvote competitors.
- No links, no mention of the site, no "I built a template for this" until week 4. If someone asks "where can I get one?", reply "DM me" and Claude drafts the DM.

## After week 3

- One link drop a week at most, only where a moderator-tolerated subreddit allows resources (r/excel and r/SaaS tolerate a free-tool link inside a full answer; **r/Accounting does not**: never link there).
- The link is always the free version or the free calculator, never a paid page.
- Claude tracks every comment in `marketing/reddit-templates/log.jsonl` (date, thread, sub, link yes/no, outcome) so the cadence stays under the radar.

## What Claude sends you each week

A short note with two threads (URL, the question, the drafted answer, and one line on why the thread is worth it). Paste both, reply "done", and that is the week.
