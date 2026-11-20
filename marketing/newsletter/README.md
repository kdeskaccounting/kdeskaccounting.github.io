# The weekly email: one worked journal entry a week

**Status (2026-11-19):** the sign-up is live on `main`. The one-time note went to all 18
downloaders who had had no email. The two who downloaded the free ASC 606 file before September got
the standard line, not the "download it again" line: their file had tabs the current free file no
longer has. Issue 1 is scheduled in MailerLite for Tuesday 2026-11-24, 15:00 UTC
(7:00 AM Pacific), on Stephen's go. Issues 2 to 4 are drafts.

## The promise

One short email a week: a real situation, the numbers, the entry and the tie-out. The sign-up form
says exactly that, so the cadence is a promise. Four issues are written before the form goes live,
which keeps a month of buffer between the promise and the next deadline.

## Who gets it

- People who sign up through the site form (MailerLite group "KDesk Accounting subscribers").
- **Not** the "Gumroad free downloaders" group. They asked for a file, not a newsletter. They get one
  invitation (`one-time-note-2026-11.md`) and join only if they say yes.

## How an issue ships

1. Draft in this folder (`issue-NN-slug.md`), one topic, 200 to 300 words.
2. Second-agent fact-check, the same gate as every T1 send: arithmetic, balanced entries, every
   standard cited. Any FIX FIRST blocks the send.
3. Stephen reads it. He is the authority on the accounting.
4. Sent from MailerLite as a regular campaign in the Custom HTML editor, to the group "KDesk
   Accounting subscribers", Tuesdays at 15:00 UTC. Build the email with
   `/usr/bin/python3 ~/kdesk-analytics/newsletter/build_issue.py issue-NN-slug.md`, then use
   Import HTML to upload the ZIP it writes. The script lives outside this repo because it reads
   the footer's postal address from MailerLite's account settings at build time, so the address
   is never written here. Send a test to the account's own inbox before scheduling.

`kdeskaccounting.com` is an authenticated sending domain in MailerLite (2026-11-19), so campaigns
and automations go out From `hello@kdeskaccounting.com`, signed by the domain. MailerLite now
refuses a Gmail sender on campaigns. The DNS side, in Cloudflare: a CNAME `litesrv._domainkey` to
`litesrv._domainkey.mlsend.com`, `include:_spf.mlsend.com` added to the one SPF record (keep
`include:_spf.mx.cloudflare.net` for Email Routing), and a `mailerlite-domain-verification` TXT
record at the root.

Every automation email carries its own sender address, set on the email step in the workflow
editor (Sender email). Setting the account's default sender does not change them. On 2026-11-20
MailerLite disabled the Gumroad follow-up automation ("Needs repair: The email domain is not
authenticated") because its three emails still used the Gmail address; all four automation emails
(three follow-ups and the welcome email) now use `hello@kdeskaccounting.com`. If it happens again:
fix the sender on each email step, save, and activate. People whose send failed do not restart by
being re-added to the group; use the automation's Activity page, filter Failed, tick them, then
Actions, "Re-add to the sequence", "last step that they failed".

The same topic is that week's article and KDesk Short, so one piece of work feeds three places.

## Rules

- No CPA wording anywhere (the licence is inactive).
- No tax or legal advice. These are accounting mechanics with the standard cited.
- Entries balance, and every number in the prose matches the entry.
- People who get the one-time note stay out of the MailerLite automation group unless they sign up,
  so "you will not hear from me again" stays true.
- Some people who got the note are members of the "Gumroad free downloaders" group but never entered
  its follow-up sequence. When that automation is reactivated in MailerLite, always choose "No, only
  add new subscribers". Adding existing members would break the promise above.
- No recipient addresses in this repo. The list for the one-time note lives in
  `~/kdesk-analytics/private/`.

## Issues

| # | File | Topic | Fact-check |
|---|---|---|---|
| 1 | `issue-01-accrue-and-reverse.md` | An accrual with no invoice, and its reversal | 2026-11-19: PASS after one fix |
| 2 | `issue-02-fixed-asset-sold-at-a-loss.md` | Disposal of a fixed asset below book value | 2026-11-19: PASS |
| 3 | `issue-03-operating-lease-month-one.md` | Month one of an operating lease under ASC 842 | 2026-11-19: PASS |
| 4 | `issue-04-capitalizing-a-commission.md` | Capitalizing and amortizing a sales commission under ASC 340-40 | 2026-11-19: PASS after one fix |
