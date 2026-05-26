# MailerLite email blast — Month-End Close Checklist launch

**Status:** Draft. Paste into MailerLite when Gumroad URL is live.
**Audience:** "KDesk Accounting subscribers" group (whole list — small but valid; first proper broadcast after launch sequence).
**Send timing:** 9:00 AM Stephen's local time on a Tuesday or Wednesday (highest B2B-finance open rates).
**Suggested A/B test:** if MailerLite free tier supports — test two subject lines on a 20% split.

---

## Subject line options (pick one)

1. **`New free workbook: Month-End Close Checklist + Tie-Out`** ← recommended (clear, specific, "free" up front)
2. `The 42-task close checklist I wish I'd had at my first controller job`
3. `Free: 5-tab Excel workbook to run your entire month-end close`

## Preview text (50-90 chars)

`42 tasks, 18 reconciliations, JE tracker, printable sign-off — free on Gumroad.`

---

## Body

```
Hey {{ subscriber.first_name | default: "there" }},

You signed up for KDesk Accounting templates a while back — thanks for being on the list. Quick update: there's a new free workbook ready.

It's a complete month-end close workbook in five tabs:

  • Close Calendar — 42 pre-populated tasks across 5 phases (cutoff, subledger recs, technical schedules, equity/tax, statements & review)
  • Reconciliations — 18 standard subledger-to-GL ties (Cash, AR, AP, prepaids, fixed assets, leases, deferred revenue, equity) with auto materiality flag
  • JE Tracker — 50-row log with debit=credit sanity check
  • Sign-Off — printable certification with auto-tabulated close metrics
  • README + Setup — company config + materiality threshold

It's free. Pay What You Want on Gumroad, $0 minimum. If it saves you time the suggested $5 is appreciated but not required.

Download it here:
https://kdeskaccounting.gumroad.com/l/TBD-MEC-FREE

The full long-form guide (the same 42 tasks with technical accounting context for each phase) is on the blog:
https://kdeskaccounting.com/posts/month-end-close-checklist-controllers/

Why free? This is the structural workbook that holds your close together — it doesn't compute the technical schedules. Those live in the paid workbooks (ASC 606 commission accrual, ASC 842 leases, fixed asset rollforward). If you've already got those, the close checklist is the scaffolding that ties them together. If you don't yet, the free workbook is a complete starting point on its own.

Hit reply if any of the 42 tasks look wrong or if you've got a category I missed — I read every reply.

— Stephen
KDesk Accounting
https://kdeskaccounting.com

---
You're receiving this because you subscribed to KDesk Accounting at kdeskaccounting.com.
One-click unsubscribe: {{ unsubscribe }}
```

---

## Post-send checklist

- [ ] Confirm Gumroad URL swapped in (TBD-MEC-FREE → real slug)
- [ ] Verify MailerLite tracks opens + clicks (default ON for free tier)
- [ ] 48h after send: check open rate + click-through rate against the prior launch broadcast (no benchmark yet — this is the first proper broadcast)
- [ ] If any replies arrive, respond personally within 24h. Every reply at this stage matters
- [ ] Snapshot open / click stats to `marketing/seo-tracking/email-broadcasts.jsonl` (create the file if needed)

## What NOT to do

- Don't blast a second time within 7 days
- Don't add the FA paid workbook upsell here — that's a separate broadcast later
- Don't include LinkedIn / Reddit copy in the email — keep the email focused on the one CTA
