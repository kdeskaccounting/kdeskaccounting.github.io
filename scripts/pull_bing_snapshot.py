#!/usr/bin/env python3
"""Pull Bing Webmaster Tools stats into marketing/seo-tracking/bing-snapshots.jsonl.

Why this exists: GA4 shows Bing organic out-delivering Google organic roughly
3.6:1 on sessions and 3.8:1 on engaged sessions (2026-09-11), but every metric
we report comes from Search Console, which is Google only. This closes that gap.

Setup (one time, Stephen):
  1. https://www.bing.com/webmasters — sign in, "Import from Google Search
     Console" (kdeskaccounting.com is already GSC-verified by DNS TXT), or add
     the site and verify by DNS/meta tag.
  2. Settings -> API Access -> API Key -> generate.
  3. Save it:  echo '<key>' > ~/kdesk-analytics/bing-api-key.txt && chmod 600 ~/kdesk-analytics/bing-api-key.txt

Run:  uv run scripts/pull_bing_snapshot.py [--print]
API docs: https://learn.microsoft.com/en-us/bingwebmaster/getting-access
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY_FILE = pathlib.Path.home() / "kdesk-analytics" / "bing-api-key.txt"
OUT = REPO_ROOT / "marketing" / "seo-tracking" / "bing-snapshots.jsonl"
SITE = "https://kdeskaccounting.com"
BASE = "https://ssl.bing.com/webmaster/api.svc/json/"

# The 24 buying queries we track in Google; mirrored here so the two sources are
# comparable. Kept in sync with marketing/seo-tracking/target-query-positions.jsonl.
TARGET_QUERY_FILE = REPO_ROOT / "marketing" / "seo-tracking" / "target-query-positions.jsonl"


def load_key() -> str:
    if not KEY_FILE.exists():
        sys.exit(
            f"No Bing API key at {KEY_FILE}.\n"
            "Create one at https://www.bing.com/webmasters -> Settings -> API Access,\n"
            f"then: echo '<key>' > {KEY_FILE} && chmod 600 {KEY_FILE}"
        )
    return KEY_FILE.read_text(encoding="utf-8").strip()


def call(method: str, key: str, **params) -> object:
    qs = urllib.parse.urlencode({"siteUrl": SITE, "apikey": key, **params})
    url = f"{BASE}{method}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode("utf-8")).get("d")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"Bing API {method} failed: HTTP {e.code} {detail}")


def ms_date(v) -> str:
    """Bing returns /Date(1694390400000)/ — turn it into YYYY-MM-DD."""
    if isinstance(v, dict):
        v = v.get("DateTime") or v.get("Date") or ""
    s = str(v)
    if s.startswith("/Date(") and s.endswith(")/"):
        ms = int(s[6:-2].split("+")[0].split("-")[0] or 0)
        return dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
    return s[:10]


def target_queries() -> list[str]:
    if not TARGET_QUERY_FILE.exists():
        return []
    last = [l for l in TARGET_QUERY_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not last:
        return []
    try:
        return sorted(json.loads(last[-1]).get("positions", {}).keys())
    except json.JSONDecodeError:
        return []


def pull() -> dict:
    key = load_key()

    traffic = call("GetRankAndTrafficStats", key) or []
    daily = [
        {"date": ms_date(r.get("Date")), "clicks": r.get("Clicks", 0), "impressions": r.get("Impressions", 0)}
        for r in traffic
    ]
    daily.sort(key=lambda r: r["date"])
    recent = daily[-28:]
    clicks = sum(r["clicks"] for r in recent)
    impressions = sum(r["impressions"] for r in recent)

    qstats = call("GetQueryStats", key) or []
    queries = sorted(
        (
            {
                "q": q.get("Query", {}).get("Value") if isinstance(q.get("Query"), dict) else q.get("Query"),
                "clicks": q.get("Clicks", 0),
                "impressions": q.get("Impressions", 0),
                "avg_impression_position": q.get("AvgImpressionPosition"),
                "avg_click_position": q.get("AvgClickPosition"),
            }
            for q in qstats
        ),
        key=lambda r: (-(r["clicks"] or 0), -(r["impressions"] or 0)),
    )

    pages = call("GetPageStats", key) or []
    top_pages = sorted(
        (
            {"page": p.get("Query"), "clicks": p.get("Clicks", 0), "impressions": p.get("Impressions", 0)}
            for p in pages
        ),
        key=lambda r: (-(r["clicks"] or 0), -(r["impressions"] or 0)),
    )[:15]

    tracked = target_queries()
    by_q = {(r["q"] or "").lower(): r for r in queries}
    target_positions = {
        t: {
            "position": by_q[t.lower()].get("avg_impression_position"),
            "impressions": by_q[t.lower()]["impressions"],
            "clicks": by_q[t.lower()]["clicks"],
        }
        for t in tracked
        if t.lower() in by_q
    }

    return {
        "pulled_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "bing_webmaster_api",
        "site": SITE,
        "window_days": len(recent),
        "window_end": recent[-1]["date"] if recent else None,
        "totals": {
            "clicks": clicks,
            "impressions": impressions,
            "ctr_pct": round(clicks / impressions * 100, 2) if impressions else 0.0,
        },
        "daily": recent,
        "queries_count": len(queries),
        "top_queries": queries[:25],
        "top_pages": top_pages,
        "target_queries_found": len(target_positions),
        "target_queries_tracked": len(tracked),
        "target_positions": target_positions,
        "pulled_by": "scripts/pull_bing_snapshot.py",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="show", action="store_true", help="print the snapshot")
    args = ap.parse_args()

    snap = pull()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, separators=(",", ":")) + "\n")

    t = snap["totals"]
    print(
        f"Bing {snap['window_end']}: {t['clicks']} clicks / {t['impressions']} imp / "
        f"CTR {t['ctr_pct']}% over {snap['window_days']}d · "
        f"{snap['target_queries_found']}/{snap['target_queries_tracked']} target queries seen"
    )
    if args.show:
        print(json.dumps(snap, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
