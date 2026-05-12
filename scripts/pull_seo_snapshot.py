#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-api-python-client>=2.130",
#   "google-auth>=2.30",
#   "google-auth-oauthlib>=1.2",
#   "google-auth-httplib2>=0.2",
# ]
# ///
"""
Weekly SEO snapshot: pulls GSC + GA4 numbers and appends JSONL rows to
marketing/seo-tracking/. Designed to be invoked by a systemd user timer.

One-time setup: see scripts/README.md. You need a credentials.json from the
Google Cloud console and the API scopes consented once via setup_seo_oauth.py.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACKING_DIR = REPO_ROOT / "marketing" / "seo-tracking"
GSC_JSONL = TRACKING_DIR / "gsc-snapshots.jsonl"
GA4_JSONL = TRACKING_DIR / "ga4-snapshots.jsonl"

# Stored outside the repo (gitignored if ever copied in).
CREDS_DIR = pathlib.Path(os.environ.get("KDESK_SEO_CREDS_DIR", pathlib.Path.home() / "kdesk-analytics"))
TOKEN_FILE = CREDS_DIR / "google-token.json"

SITE_URL = "sc-domain:kdeskaccounting.com"
GA4_PROPERTY = "properties/528583005"  # GA4 property id for kdeskaccounting (from existing config)

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def load_creds() -> Credentials:
    if not TOKEN_FILE.exists():
        sys.exit(
            f"No token at {TOKEN_FILE}. Run scripts/setup_seo_oauth.py once to mint it."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        else:
            sys.exit(
                "Token invalid and no refresh token. Re-run scripts/setup_seo_oauth.py."
            )
    return creds


def pull_gsc(creds: Credentials, window_days: int = 28) -> dict:
    sc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end = dt.date.today() - dt.timedelta(days=2)  # GSC has ~2d lag
    start = end - dt.timedelta(days=window_days - 1)
    body_base = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "rowLimit": 10,
    }

    totals = sc.searchanalytics().query(
        siteUrl=SITE_URL,
        body={**body_base, "rowLimit": 1, "dimensions": []},
    ).execute()
    t_row = (totals.get("rows") or [{}])[0]
    totals_obj = {
        "clicks": t_row.get("clicks", 0),
        "impressions": t_row.get("impressions", 0),
        "ctr_pct": round(t_row.get("ctr", 0) * 100, 2),
        "avg_position": round(t_row.get("position", 0), 1),
    }

    queries = sc.searchanalytics().query(
        siteUrl=SITE_URL, body={**body_base, "dimensions": ["query"]}
    ).execute().get("rows", [])
    top_queries = [
        {
            "q": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 1),
        }
        for r in queries
    ]

    pages = sc.searchanalytics().query(
        siteUrl=SITE_URL, body={**body_base, "dimensions": ["page"]}
    ).execute().get("rows", [])
    top_pages = [
        {
            "url": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 1),
        }
        for r in pages
    ]

    # Total distinct queries — pull rowLimit=25000 over the same window
    all_queries = sc.searchanalytics().query(
        siteUrl=SITE_URL,
        body={**body_base, "dimensions": ["query"], "rowLimit": 25000},
    ).execute()
    queries_count = len(all_queries.get("rows", []))

    return {
        "pulled_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "window_days": window_days,
        "window_end": end.isoformat(),
        "totals": totals_obj,
        "queries_count": queries_count,
        "top_queries": top_queries,
        "top_pages": top_pages,
        "pulled_by": "scripts/pull_seo_snapshot.py",
    }


def pull_ga4(creds: Credentials) -> dict:
    ga = build("analyticsdata", "v1beta", credentials=creds, cache_discovery=False)
    end = dt.date.today() - dt.timedelta(days=1)

    def report(window_days: int, dimensions, metrics, order_metric=None, limit=10):
        start = end - dt.timedelta(days=window_days - 1)
        body = {
            "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "limit": limit,
        }
        if order_metric:
            body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
        return ga.properties().runReport(property=GA4_PROPERTY, body=body).execute()

    # 7d: active users, sessions
    r7 = report(7, [], ["activeUsers", "sessions"])
    active_users_7d = int(r7.get("rows", [{}])[0].get("metricValues", [{}])[0].get("value", 0)) if r7.get("rows") else 0
    sessions_7d = int(r7.get("rows", [{}])[0].get("metricValues", [{}, {}])[1].get("value", 0)) if r7.get("rows") else 0

    # 30d: total users
    r30 = report(30, [], ["totalUsers"])
    users_30d = int(r30.get("rows", [{}])[0].get("metricValues", [{}])[0].get("value", 0)) if r30.get("rows") else 0

    # Channels (7d)
    rch = report(7, ["sessionDefaultChannelGroup"], ["sessions"], order_metric="sessions")
    channels = {row["dimensionValues"][0]["value"]: int(row["metricValues"][0]["value"]) for row in rch.get("rows", [])}

    # Top pages by views (7d)
    rpages = report(7, ["pageTitle"], ["screenPageViews"], order_metric="screenPageViews")
    top_pages = [
        {"title": row["dimensionValues"][0]["value"], "views": int(row["metricValues"][0]["value"])}
        for row in rpages.get("rows", [])
    ]

    # Events (7d)
    revents = report(7, ["eventName"], ["eventCount"], order_metric="eventCount", limit=50)
    events = {row["dimensionValues"][0]["value"]: int(row["metricValues"][0]["value"]) for row in revents.get("rows", [])}

    # Key events (7d)
    rkey = report(7, [], ["keyEvents"])
    key_events_7d = int(rkey.get("rows", [{}])[0].get("metricValues", [{}])[0].get("value", 0)) if rkey.get("rows") else 0

    # Top countries (7d)
    rcountry = report(7, ["country"], ["activeUsers"], order_metric="activeUsers", limit=10)
    countries = {row["dimensionValues"][0]["value"]: int(row["metricValues"][0]["value"]) for row in rcountry.get("rows", [])}

    return {
        "pulled_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "window_days": 7,
        "window_end": end.isoformat(),
        "active_users_7d": active_users_7d,
        "sessions_7d": sessions_7d,
        "users_30d": users_30d,
        "channels_7d": channels,
        "top_pages_by_views_7d": top_pages,
        "events_7d": events,
        "key_events_7d": key_events_7d,
        "top_countries_7d": countries,
        "pulled_by": "scripts/pull_seo_snapshot.py",
    }


def append_jsonl(path: pathlib.Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def git_changes_since(timestamp_iso: str | None) -> str:
    if not timestamp_iso:
        return ""
    try:
        out = subprocess.check_output(
            ["git", "log", f"--since={timestamp_iso}", "--pretty=format:- %s", "--no-merges"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
        return out or "(no commits)"
    except subprocess.CalledProcessError:
        return ""


def last_pulled_at(path: pathlib.Path) -> str | None:
    if not path.exists():
        return None
    last_line = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last_line = line
    if not last_line:
        return None
    try:
        return json.loads(last_line).get("pulled_at")
    except json.JSONDecodeError:
        return None


def commit_and_push(date_str: str) -> None:
    subprocess.run(["git", "add", "marketing/seo-tracking/"], cwd=REPO_ROOT, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT).returncode
    if diff == 0:
        print("Nothing to commit.")
        return
    subprocess.run(
        ["git", "commit", "-m", f"SEO tracking: weekly snapshot {date_str}"],
        cwd=REPO_ROOT,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=REPO_ROOT, check=True)


def main() -> int:
    creds = load_creds()
    prev_pull = last_pulled_at(GSC_JSONL)

    gsc = pull_gsc(creds)
    ga4 = pull_ga4(creds)

    changes = git_changes_since(prev_pull)
    gsc["notable_changes"] = changes
    ga4["notes"] = changes

    append_jsonl(GSC_JSONL, gsc)
    append_jsonl(GA4_JSONL, ga4)

    if os.environ.get("KDESK_SEO_SKIP_COMMIT") != "1":
        commit_and_push(dt.date.today().isoformat())

    # Brief stdout summary (consumed by systemd journal or piped to a notifier)
    print(
        f"GSC {gsc['window_end']}: {gsc['totals']['clicks']} clicks / "
        f"{gsc['totals']['impressions']} imp / pos {gsc['totals']['avg_position']}"
    )
    print(
        f"GA4 last 7d: {ga4['active_users_7d']} users / "
        f"{ga4['key_events_7d']} key events"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
