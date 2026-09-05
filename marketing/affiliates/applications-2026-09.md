# Affiliate / referral applications — Stream C (drafted 2026-09-05)

**Why this stream exists:** a visitor who wants *software* rather than a spreadsheet is worth $0 to us today.
A referral pays $100–800 per conversion versus ~$80 for a template sale, with zero fulfilment, support or
liability, and it keeps paying during dormant weeks. Plan: `marketing/plan-2026-09-10k-portfolio.md`, Stream C.

**Stephen does the sign-ups (they need the account owner); Claude wires the links, disclosure and tracking.**
~15 minutes total. Forward each approval email (or the referral link/terms) and I take it from there.

---

## 1. FinQuery — Referral Partner track (highest priority)
- Where: https://finquery.com/partners/ → **Referral Partner** ("Refer FinQuery and earn commission").
- Why they'll say yes: we rank for the ASC 842 queries their buyers type, and our visitors who outgrow a
  spreadsheet are exactly LeaseGuru / LeaseQuery prospects. We are not a competitor — we sell Excel.
- Application blurb (paste):
  > KDesk Accounting (kdeskaccounting.com) publishes ASC 842 and ASC 606 technical content and Excel
  > workbooks for controllers and technical accounting managers, plus a YouTube channel of workbook
  > walkthroughs. Our ASC 842 pages and lease calculator attract finance teams evaluating how to handle
  > lease accounting; a meaningful share need software rather than a spreadsheet. We'd like to refer those
  > readers to LeaseGuru and LeaseQuery through a clearly disclosed referral link on our ASC 842 product
  > page, our ASC 842 guide, our lease calculator and our video descriptions. Run by Stephen Michels,
  > 10+ years in technical accounting.
- Ask for: referral link or partner code, commission terms, cookie window, any brand/claims guidelines.

## 2. Cradle (cradleaccounting.com)
- Where: no public partner page found — use the site's contact/demo form, subject "Referral partnership".
- Why: $99/mo self-serve, 30-day trial — the natural fit for our 3–10 lease visitors. Small enough to say
  yes to an unknown partner and to offer a simple per-signup bounty.
- Blurb: same as above, swapping the product names; propose "a disclosed referral link on our ASC 842 pages
  and lease calculator; happy to start on a per-paid-signup bounty and adjust from data".

## 3. iLeasePro / iLeaseXpress (ileasepro.com)
- Where: contact form → "Referral or affiliate program?". $149/mo self-serve, no card for trial.
- Same blurb. Lower priority; take whatever terms are offered.

## 4. Adjacent programs for the RSU / equity-comp audience (Stream A) — apply once the calculator is live
- Tax software and brokerages with published affiliate programs (apply through their networks; typical
  $10–50 per conversion). Add after `/rsu-tax-calculator/` has traffic — applications want a live page.

---

## What Claude wires once approved (T1, logged)
1. A secondary CTA under the product CTA on `/templates/asc842/`, the ASC 842 guide, and `/calculator/`:
   "Need dedicated software instead? LeaseGuru is free up to 2 leases." (link) — honest, not salesy.
2. **Disclosure line on every page carrying a referral link** (FTC): "KDesk may earn a referral fee if you
   sign up through this link. It doesn't change what you pay." Also in YouTube descriptions.
3. GA4 event `click_affiliate_outbound` (partner, source_page) in `layouts/partials/extend_head.html`.
4. A row for referral clicks/conversions in the Monday scoreboard once the partner dashboards exist.

## Guardrails
- Never present a referral as a recommendation from a CPA (license inactive) — it's "software people use
  when the spreadsheet stops being enough".
- No comparison claims we haven't verified on the vendor's own site (verified 2026-09-04: LeaseGuru free to
  2 leases / $999 to 10 / $1,750 to 15; Cradle $99/mo Small; iLeaseXpress $149/mo).
