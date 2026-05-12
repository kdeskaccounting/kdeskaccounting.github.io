# SEO + Analytics tracking history

Time-series record of every GSC + GA4 pull. Append-only — never edit prior rows.

## Files

- `gsc-snapshots.jsonl` — one JSON record per Google Search Console pull. Captures totals, top queries, top pages, and notes on what changed.
- `ga4-snapshots.jsonl` — one JSON record per Google Analytics 4 pull. Captures sessions / users / channel mix / top pages / event counts.

## Cadence

- **Weekly** — every Monday morning (Pacific). Pull last-7d + last-28d numbers.
- **Ad hoc** — after any significant change (new post, title rewrite, internal-linking pass, social campaign) to attribute movement.

## Schema (gsc-snapshots.jsonl)

```json
{
  "pulled_at": "2026-05-12T03:15:00-07:00",
  "window_days": 28,
  "window_end": "2026-05-09",
  "totals": {"clicks": 1, "impressions": 2446, "ctr_pct": 0.04, "avg_position": 29.1},
  "indexing": {"indexed_pages": 33, "not_indexed_pages": 6},
  "top_queries": [
    {"q": "deferred commissions asc 606", "clicks": 0, "impressions": 138, "position": 29.2}
  ],
  "top_pages": [
    {"url": "https://...", "clicks": 1, "impressions": 271, "position": 7.6}
  ],
  "notable_changes": "What shipped since the last pull",
  "pulled_by": "claude+playwright via santiagokdesk@gmail.com browser session"
}
```

## Schema (ga4-snapshots.jsonl)

```json
{
  "pulled_at": "2026-05-12T03:22:00-07:00",
  "window_days": 7,
  "window_end": "2026-05-11",
  "active_users": 77,
  "sessions": null,
  "users_30d": 170,
  "channels": {"Direct": 66, "Organic Search": 9, "Referral": 2, "Unassigned": 2},
  "top_pages_by_views": [{"title": "...", "views": 40}],
  "events_7d": {"page_view": 80, "scroll": 14, "click_gumroad_outbound": 0},
  "key_events_7d": 0,
  "top_countries": {"US": 52, "CN": 10, "SG": 7},
  "notes": "What's notable in this pull"
}
```

## How a pull happens today

Manual via the open Chrome session under `santiagokdesk@gmail.com`:

1. GSC → Performance → 28 days → Queries tab → record top 10 + totals
2. GSC → Performance → 28 days → Pages tab → record top 10
3. GA4 home → record 7d / 30d cards + channels + top pages + event list
4. Append rows to the two JSONL files
5. Commit

## How a pull should eventually happen

Headless via the GSC Search Analytics API and the GA4 Data API, run as a scheduled Claude routine every Monday 9am PT. Requires:

- A GCP project with the Search Console API and Analytics Data API enabled
- OAuth client + refresh token stored as a credential file outside the repo
- A small Python script (`scripts/pull_gsc.py`, `scripts/pull_ga4.py`) that the schedule fires

Until that's wired, the Monday schedule routine prompts Claude to drive the authed browser when Stephen is next at the keyboard.
