# KDesk Accounting — decisions log

Append-only ledger of autonomous actions taken by Claude Code on the marketing/distribution side of KDesk Accounting. Schema mirrors `/home/kdeskconsulting/digitalproducts/data/digitalproducts.db` decisions_log but flat-file so we don't need SQLite at this scale.

## Format

`decisions.jsonl` — one JSON object per line:

```json
{"id": 1, "ts": "2026-05-10T22:38:06-0700", "tier": 1, "status": "executed", "action": "wired GA4 Key Events for outbound Gumroad clicks", "reasoning": "GA4 baseline showed 0 key events; cannot measure conversions without instrumentation", "files": ["layouts/partials/extend_head.html"], "veto_window_close": null, "stephen_reviewed": false}
```

`status` is one of `executed` · `in_progress` · `planned` · `approved` · `pending_veto` · `vetoed`. Write every row with `scripts/ledger.py`'s `append()` — it allocates the id under a lock, stamps the time and enforces the schema.

### Answering an earlier decision: `approves` / `vetoes`

Two optional fields, **written only when present**, let a LATER entry answer an earlier T2 veto window by id — the only way to do it in an append-only file:

```json
{"id": 85, "ts": "2026-09-15T20:34:34-0700", "tier": 0, "status": "executed", "action": "Stephen re-confirmed his approval of #69 … and #70 …", "reasoning": "…", "files": ["scripts/ledger.py"], "veto_window_close": null, "stephen_reviewed": false, "approves": [69, 70]}
```

- **`approves: [69, 70]`** — Stephen said yes. The gate (`veto_gate` / `t2_window_open` in `scripts/ledger.py`, used by `publish.py`, `schedule_week.py` and `send_reengage.py`) then treats those ids as open **without waiting for `veto_window_close` to elapse**. Only accepted on a row whose status is `approved` or `executed`: it records an approval that happened, not a plan to ask for one.
- **`vetoes: [69]`** — he said no. Closes those ids again **even if the window has already elapsed**.
- **Only a LATER entry answers.** The answering row's id must be **strictly greater** than the id it answers (ids are allocated in file order here, so id order *is* file order; `ts` is not consulted — it is a string a hand-written row can set to anything). So an entry cannot approve **itself** — which is what a T2 row asking for its own veto window would be doing — and an old entry cannot pre-authorise a decision that had not been made yet. A row says no about *itself* with `"status": "vetoed"`.
- **The last answering entry in the file wins**, because in an append-only log "later in the file" is the only record of "said more recently". An approval can be taken back by a veto written after it, and that veto reversed by a fresh approval after that.
- **A field the reader cannot read answers nothing.** `append()` refuses to write anything but a list of plain ints, so `"approves": "69"` or `[69, "70"]` can only arrive by hand; the gate reads what it can and stays shut for the rest, and an id naming an entry that does not exist authorises nothing.
- Write them through `ledger.append(..., approves=[...], vetoes=[...])`, never by hand. **Prose does not move the gate:** entry #81 recorded the same approval in words and nothing unlocked, which is why #85 exists.

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
