# Free-download → paid follow-up sequence

**Status:** Drafted 2026-09-01. Nothing here sends automatically. Paste into MailerLite (automation: *Joins "KDesk Accounting subscribers"*) or Gumroad (*Emails → Workflows → trigger: purchase of a free product*). Gumroad workflows are the better home because every free download already lands there with the buyer's email; MailerLite only sees site-form signups.

**Why this exists:** All-time Gumroad = 23 downloads, 13 people, 0 full-price sales. The free workbooks are good enough to be the product unless something turns the download into a decision. This sequence is that something. The `UPGRADE20` code (20% off, universal, created 2026-09-01) is the nudge; it is only distributed through these emails, never on the site.

**Update 2026-09-01 — lean free files + bundle + videos.** The free downloads are now *inputs + schedule only* (JE Generator, Rollforward, Reconciliation and Dashboard tabs are gone from the free files), so the "over the free version" bullets below are literal: those tabs exist only in the paid file. Every product page now has a 4-minute walkthrough video (`/templates/<slug>/#walkthrough`) — link it in Email 2 instead of describing the JE. The bundle is the second offer in Email 3 for anyone who downloaded two or more free files.

**Discount links (Gumroad applies the code automatically):**

| Product | Paid | With UPGRADE20 |
|---|---|---|
| **SaaS Controller Bundle (all 5, $249 vs $371)** | https://kdeskaccounting.gumroad.com/l/saas-controller-bundle | https://kdeskaccounting.gumroad.com/l/saas-controller-bundle/UPGRADE20 |
| ASC 842 Lease Accounting Workbook | https://kdeskaccounting.gumroad.com/l/phxigq | https://kdeskaccounting.gumroad.com/l/phxigq/UPGRADE20 |
| ASC 606 Commission Accrual Workbook | https://kdeskaccounting.gumroad.com/l/mwmwpe | https://kdeskaccounting.gumroad.com/l/mwmwpe/UPGRADE20 |
| Fixed Asset Rollforward Workbook | https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward | https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward/UPGRADE20 |
| SaaS Metrics & ARR Dashboard | https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard | https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard/UPGRADE20 |
| Startup Runway Calculator | https://kdeskaccounting.gumroad.com/l/runway-calculator | https://kdeskaccounting.gumroad.com/l/runway-calculator/UPGRADE20 |

**Voice rules:** open on the reader's situation, one concrete number or mechanic per email, no emojis, no "hope this helps", sign as Stephen. Never claim active CPA licensure. Never give tax advice. Every email has a real reply-to.

---

## Automated sequence (per free product; ASC 842 shown, swap the bracketed bits per product)

### Email 1 — Day 0 (immediately after download)

**Subject:** Your ASC 842 workbook — two things before you open it

```
Hi {{ first_name | default: "there" }},

Thanks for grabbing the free ASC 842 workbook. Two things that save people time on first open:

1. Start on the Setup tab. Enter your IBR default and fiscal year start before you touch the Lease Data tab — every schedule reads from Setup, and changing it later re-keys nothing.

2. On the Lease Schedule tab, pick "HQ Office Lease" in the selector. Month 1 should show a beginning liability of 264,953.53 and interest of 1,103.97. If the schedule is all zeros, your Excel is recalculating manually (Formulas → Calculation Options → Automatic).

The free version is capped at 3 leases and 36 months. If you want to see how a modification or termination flows through the JE Generator on your own portfolio, that's what the full version is for — 20 leases, 120 months, same file structure:
https://kdeskaccounting.gumroad.com/l/phxigq

If you have a lease that doesn't fit the register (variable payments, sale-leaseback, sublease), reply and tell me what it is. I read every reply.

— Stephen
KDesk Accounting
https://kdeskaccounting.com
```

### Email 2 — Day 3

**Subject:** The lease entry that most spreadsheets get wrong

```
Hi {{ first_name | default: "there" }},

Quick one. The month-1 operating lease entry trips up more controllers than the PV math does, because the expense and the liability reduction are two different numbers:

  DR  Lease Expense            5,000
  DR  Lease Liability          4,180
      CR  Cash                          5,000
      CR  Right-of-Use Asset            4,180

($5,000/month, 36 months, 6% IBR: opening liability $164,029, month-1 interest $820, so the liability drops by $4,180 and the ROU asset amortizes by the same $4,180 to keep expense straight-line.)

The full walkthrough — initial recognition, monthly close for both lease types, and termination — is here:
https://kdeskaccounting.com/posts/asc-842-journal-entries/

And the 4-minute video of the workbook producing exactly this entry, tab by tab:
https://kdeskaccounting.com/templates/asc842/#walkthrough

The workbook's JE Generator produces exactly this entry for every lease in the register, for whichever period you select in Setup.

— Stephen
```

### Email 3 — Day 7

**Subject:** 20% off the full ASC 842 workbook (this week only)

```
Hi {{ first_name | default: "there" }},

A week ago you downloaded the free 3-lease version. If you've been keying more than three leases into it, or copying the schedule tab to get past month 36, here's the shortcut:

The full ASC 842 Lease Accounting Workbook is $97. This link takes 20% off through {{ date + 7 days }}:
https://kdeskaccounting.gumroad.com/l/phxigq/UPGRADE20

What you get over the free version:
  • 20 leases (vs 3) and a 120-month schedule per lease (vs 36)
  • JE Generator — six period entries with your GL codes, debits = credits check
  • Balance sheet rollforward split current / non-current, tied to the JE Generator
  • Reconciliation tab — JE Generator vs. lease register, every variance $0
  • Disclosure maturity analysis, footnote-ready

Running more than leases in Excel? All five workbooks together are $249 instead of $371, same 20% off with the code:
https://kdeskaccounting.gumroad.com/l/saas-controller-bundle/UPGRADE20

Same file structure as the free version, so anything you've already entered copies straight across.

If it's not the right fit, no problem — the free version stays yours. Reply if a feature is missing and you'd buy if it were there; that's how the fixed-asset workbook got its disposal log.

— Stephen
KDesk Accounting
```

### Product-swap table for emails 1–3

| Free product | Cap to mention | Paid link | "over the free version" bullets |
|---|---|---|---|
| ASC 606 free (5 deals / 24 mo) | 5 deals, 24 months | /l/mwmwpe/UPGRADE20 | 50 deals; 60-month waterfall; all three amortization bases incl. expected customer life; rollforward split current/non-current |
| Fixed asset free (5 assets) | 5 assets | /l/fixed-asset-rollforward/UPGRADE20 | 50 assets; four methods; JE presets for QBO/NetSuite/Sage/Xero; disposal log; five-way reconciliation; audit confirmation export |
| SaaS metrics free (6 mo) | 6 months, 9 metrics | /l/saas-metrics-dashboard/UPGRADE20 | 24 months; Magic Number; 24-month trend table; 12 months sample data |
| Runway free (12 mo) | 12 months, 5 rows/tab | /l/runway-calculator/UPGRADE20 | 48-month window; 20 rows per tab; Base/Optimistic/Pessimistic scenarios |
| Month-end close (free, no paid twin) | — | pick the paid workbook that matches the reconciliation rows they'd use most: ASC 842 for lease rows, ASC 606 for deferred commissions, FA for fixed assets | — |

For the month-end close download, Email 2 should be the "which reconciliation breaks most often" note, and Email 3 offers the matching technical workbook with UPGRADE20.

---

## One-off outreach to existing downloaders (send manually from santiagokdesk@gmail.com)

These people already downloaded and never heard from us again (except csibas.com, contacted 2026-05-30). Gmail drafts were created 2026-09-01 for the five business-domain leads; review, personalize the first line if you know anything about the company, and send. Free-mail downloaders (gmail/yahoo/naver) can get the same note via a MailerLite broadcast once they're imported.

| Downloaded | Email | What they took | Draft angle |
|---|---|---|---|
| 2026-06-02 | operations@schlam.com | ASC 842 free (via storefront) | Ops team at an industrial firm → equipment/vehicle leases; finance-lease classification |
| 2026-07-22 | melissa.deters@orion.com | ASC 842 free (via storefront) | Larger company; likely evaluating vs. lease software; 20-lease cap honesty |
| 2026-08-10 | pfelesina@team-tristar.com | Month-end close ($1 paid) | Paid $1 = engaged; ask which reconciliation row is the pain, offer the matching workbook |
| 2026-08-13 | wkohler@naeda.com | All six free files | Collector; ask which one they actually opened; single UPGRADE20 link to the store |
| 2026-08-21 | scott@stratacloudaccountants.com | ASC 842 free | Accounting firm → multi-client use; that's also a CAE-adjacent conversation |

**Template (ASC 842 variant):**

```
Subject: Your ASC 842 download — anything not fit?

Hi [First name],

You downloaded the free ASC 842 lease workbook from KDesk a few weeks ago. I'm the one who built it, and I'm curious whether it handled your leases or whether something didn't fit — a variable-payment lease, a modification mid-term, a lease with an incentive.

If it did the job and you've hit the 3-lease cap, this link takes 20% off the full 20-lease / 120-month version:
https://kdeskaccounting.gumroad.com/l/phxigq/UPGRADE20

If it didn't fit, reply and tell me what broke. That's genuinely more useful to me than the sale.

— Stephen Michels
KDesk Accounting · kdeskaccounting.com
```

---

## Measurement

Log every send and reply in `marketing/seo-tracking/email-broadcasts.jsonl` (create on first send). The number that matters: **free → paid conversions within 14 days of download**, tracked by `UPGRADE20` uses (`times_used` on the offer code via the Gumroad API) and by `scripts/pull_gumroad_snapshot.py` (`paid_full_price`).


---

## Delivery status (2026-09-02)

- **Gumroad Workflows:** all five free→paid workflows are built (trigger = purchase of the free product; emails at 0 / 3 / 7 days; copy in `workflows.json`) but Gumroad refuses to publish until the account has **$100 in earnings and a payout** ($16.99 today). They publish themselves the day that threshold is crossed — nothing to rebuild.
- **MailerLite fallback (the path that works now):** one automation, trigger *joins group "Gumroad free downloaders"*, three emails using merge fields `{$product_name} {$free_cap} {$paid_url} {$page_url} {$price} {$full_desc}` so one sequence is product-specific. `scripts/sync_gumroad_to_mailerlite.py` pulls Gumroad free downloads and upserts them with those fields (run it Mondays with the snapshot, or daily via launchd). It needs a MailerLite API token: creating one in the UI requires ticking MailerLite's API-terms checkbox, which Claude does not tick without Stephen's OK.
- **MailerLite welcome email** (site form promise): body now set from `welcome-email.html` via the new Custom HTML editor.
