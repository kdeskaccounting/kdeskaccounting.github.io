# Re-engagement email — the 14 downloaders the nurture skipped (drafted 2026-09-05, NOT SENT)

**Why:** decision 35 activated the free→paid automation as "new subscribers only", so 14 of 15 Gumroad
downloaders never received any email. This one-off closes that gap and doubles as customer discovery
(the reply question). Stephen sends it; Claude does not send email to the list.

**Status:** copy ready. Creating the MailerLite group + campaign draft via API was blocked by the
session's permission classifier (an outbound email to real subscribers) — so do it in the MailerLite UI:
Campaigns → Create → Regular → paste subject + body → recipients = the group below (or "Gumroad free
downloaders" minus zainabzafar2225@gmail.com, who is already inside the live 3-email sequence).

**Sender:** KDesk Accounting · santiagokdesk@gmail.com (same as the automations).
**Merge fields already on every subscriber:** `{$product_name}` `{$page_url}` `{$paid_url}` `{$price}` `{$free_cap}`.
**Timing note:** if sent after the repricing veto closes (2026-09-06 22:00 PT, decision 52) you can add
"the full versions go up in price this week" — do not say it before the price actually changes.

## Subject
Quick question about the {$product_name} you downloaded

## Body
Hi —

Earlier this year you grabbed the free **{$product_name}** from KDesk. Two things have changed since, and I have one question.

1. **The free file got leaner and the full version got a walkthrough.** The product page now has a Free-vs-Full table and a four-minute tab-by-tab video: {$page_url}
2. **20% off the full workbook this week** with code **UPGRADE20**: {$paid_url}/UPGRADE20

**The question:** what did you actually use the free file for — a real close, an audit request, a model for something else, or did it not fit? Reply with one line. It decides what I build next, and I read every reply.

— Stephen
KDesk Accounting · Poulsbo, WA

*You're getting this because you downloaded a free KDesk workbook on Gumroad. Reply "stop" and I'll remove you.*

## Recipients (14 — MailerLite subscriber id · email · product)
| id | email | product | domain |
|---|---|---|---|
| 197511901860595582 | ljusper01@gmail.com | month-end close checklist | free-mail (PH) |
| 197511901124494555 | kimjum1@naver.com | month-end close checklist | free-mail (KR) |
| 197511900414608737 | scott@stratacloudaccountants.com | ASC 842 lease workbook | **accounting firm** |
| 197511899790705978 | creativengatia@gmail.com | month-end close checklist | free-mail (KE) |
| 197511899123812225 | wkohler@naeda.com | ASC 842 lease workbook | **trade association** |
| 197511898025953018 | pfelesina@team-tristar.com | month-end close checklist | business |
| 197511897049728944 | tem.p.email5055@gmail.com | month-end close checklist | throwaway |
| 197511896323065826 | melissa.deters@orion.com | ASC 842 lease workbook | business |
| 197511895635199304 | alextduong@gmail.com | ASC 606 commission workbook | free-mail |
| 197511894834086996 | monica.hargraves@gmail.com | ASC 606 commission workbook | free-mail |
| 197511894082258015 | operations@schlam.com | ASC 842 lease workbook | business (role acct) |
| 188942545572595161 | dtsygankov@yahoo.com | ASC 842 lease workbook | free-mail ($15 PWYW) |
| 188942545022092738 | eehighsmith@gmail.com | ASC 606 commission workbook | free-mail |
| 188942544445375778 | rmcgrew@csibas.com | ASC 842 lease workbook | business |

Excluded: 197693384562837309 zainabzafar2225@gmail.com (entered the live sequence 2026-09-03).

## Also noted while here
- Gumroad's `PUT /products/{id}` returns `success: true` for `custom_fields[]` and then drops them — the
  "What's your role?" checkout question is **UI-only** (same as covers). Add it in the Gumroad editor or via
  the debug-Chrome CDP script pattern (`scripts/video/gumroad_covers_ui.py`).
- The automation email bodies are not readable via the API (empty `content`), so porting the richer
  product-specific copy from `workflows.json` into MailerLite is also a UI/CDP job.
