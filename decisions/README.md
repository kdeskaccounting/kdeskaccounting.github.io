# KDesk Accounting — decisions log

Append-only ledger of autonomous actions taken by Claude Code on the marketing/distribution side of KDesk Accounting. Schema mirrors `/home/kdeskconsulting/digitalproducts/data/digitalproducts.db` decisions_log but flat-file so we don't need SQLite at this scale.

## Format

`decisions.jsonl` — one JSON object per line:

```json
{"id": 1, "ts": "2026-05-10T22:38:06-0700", "tier": 1, "status": "executed", "action": "wired GA4 Key Events for outbound Gumroad clicks", "reasoning": "GA4 baseline showed 0 key events; cannot measure conversions without instrumentation", "files": ["layouts/partials/extend_head.html"], "veto_window_close": null, "stephen_reviewed": false}
```

## Tiers

- **T0** — Auto-execute, log only. Site copy tweaks, SEO meta edits, queue refills, A/B title rotations.
- **T1** — Auto-execute, surfaced in next daily/weekly digest. New blog post publishes (when fact-checker passes), social cross-posts of existing content, pricing micro-tests (±$1).
- **T2** — Act + 48-hour Stephen veto window. Pricing changes >10%, new product line claims, partner outreach, anything touching competitive comparisons or product positioning.
- **T3** — Hard gate, never execute. Anything involving Stephen's CPA license, tax/legal advice in content, refunds, IRS/FASB correspondence, claims about CAE before CAE ships, anything an Etsy/auditor/legal email asks about.

## Hard gates (the agent NEVER bypasses)

1. Stephen's CPA license is described as **inactive WA**. Content must never imply active CPA licensure or "this is tax advice."
2. CAE positioning — never imply CAE is shippable / has clients / has a waitlist until Stephen confirms.
3. No content that contradicts the operating-principles in `~/kdesk-workspace/CLAUDE.md` (deterministic > aspirational; margin > revenue; systems > heroics; etc).
4. No paid spend without explicit approval.
5. Tax / legal / IRS correspondence — escalate immediately.
