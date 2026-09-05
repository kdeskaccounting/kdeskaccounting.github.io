#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client>=2.140", "google-auth>=2.30", "google-auth-httplib2>=0.2"]
# ///
"""
Weekly YouTube snapshot → marketing/seo-tracking/youtube-snapshots.jsonl (one row per run).

  uv run scripts/pull_youtube_snapshot.py            # append a row
  uv run scripts/pull_youtube_snapshot.py --print    # also pretty-print the summary

Per-video lifetime stats come from the Data API (near-real-time); channel analytics (views, watch time,
subscribers gained, traffic sources) come from the YouTube Analytics API over a trailing 28-day window
ending yesterday — that API lags ~48 h. Token: ~/kdesk-analytics/google-token.json (setup_seo_oauth.py).
Runs in the Monday block of ~/kdesk-analytics/kdesk-daily.sh; the existing `git add marketing/seo-tracking/*.jsonl` commits it.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "marketing/seo-tracking/youtube-snapshots.jsonl"
TOKEN = pathlib.Path.home() / "kdesk-analytics/google-token.json"
SHORT_MAX_SECONDS = 60
_ISO = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


# ---------- pure helpers (tests/test_pull_youtube_snapshot.py) ----------
def iso_duration_seconds(iso: str) -> int:
    h, m, s = _ISO.fullmatch(iso).groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)


def summarize_videos(items: list[dict]) -> list[dict]:
    rows = []
    for v in items:
        st = v.get("statistics", {}); dur = v["contentDetails"]["duration"]
        rows.append(dict(id=v["id"], title=v["snippet"]["title"][:70], published=v["snippet"]["publishedAt"][:10],
                         privacy=v["status"]["privacyStatus"], dur=dur, seconds=iso_duration_seconds(dur),
                         views=int(st.get("viewCount", 0)), likes=int(st.get("likeCount", 0)), comments=int(st.get("commentCount", 0))))
    rows.sort(key=lambda r: -r["views"])
    return rows


def build_snapshot(channel: dict, rows: list[dict], analytics: dict | None, window) -> dict:
    st = channel.get("statistics", {})
    return dict(pulled_at=dt.datetime.now().isoformat(timespec="seconds"), source="youtube_data_api_v3",
                channel_id=channel["id"], channel_title=channel["snippet"]["title"],
                subscribers=int(st.get("subscriberCount", 0)), total_views=int(st.get("viewCount", 0)), video_count=int(st.get("videoCount", 0)),
                shorts_views=sum(r["views"] for r in rows if r["seconds"] <= SHORT_MAX_SECONDS),
                longform_views=sum(r["views"] for r in rows if r["seconds"] > SHORT_MAX_SECONDS),
                videos=rows, analytics_window=list(window), analytics=analytics)


# ---------- API ----------
def _creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials.from_authorized_user_file(str(TOKEN))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request()); TOKEN.write_text(creds.to_json())
    return creds


def pull() -> dict:
    from googleapiclient.discovery import build
    creds = _creds(); yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ch = yt.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]; ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]; tok = r.get("nextPageToken")
        if not tok: break
    items = []
    for i in range(0, len(ids), 50):
        items += yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids[i:i + 50])).execute()["items"]
    end = dt.date.today() - dt.timedelta(days=1); start = end - dt.timedelta(days=27); window = (start.isoformat(), end.isoformat())
    analytics = None
    try:
        yta = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        a = yta.reports().query(ids="channel==MINE", startDate=window[0], endDate=window[1],
                                metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes,shares").execute()
        if a.get("rows"):
            analytics = dict(zip([h["name"] for h in a["columnHeaders"]], a["rows"][0]))
            ts = yta.reports().query(ids="channel==MINE", startDate=window[0], endDate=window[1], metrics="views",
                                     dimensions="insightTrafficSourceType", sort="-views").execute()
            analytics["traffic_sources"] = {r[0]: int(r[1]) for r in ts.get("rows", [])}
    except Exception as e:  # noqa: BLE001 — analytics is best-effort; the Data API row still lands
        print("analytics unavailable:", str(e)[:200], file=sys.stderr)
    return build_snapshot(ch, summarize_videos(items), analytics, window)


def main() -> int:
    snap = pull()
    with OUT.open("a") as f: f.write(json.dumps(snap) + "\n")
    a = snap["analytics"] or {}
    print(f"YouTube: {snap['video_count']} videos · {snap['subscribers']} subs · lifetime views shorts {snap['shorts_views']} / long {snap['longform_views']}"
          f" · 28d views {a.get('views', '?')} · watch min {a.get('estimatedMinutesWatched', '?')} → appended {OUT.name}")
    if "--print" in sys.argv:
        for r in snap["videos"]: print(f"  {r['views']:>6}  {r['seconds']:>4}s  {r['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
