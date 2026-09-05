#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client>=2.140", "google-auth>=2.30", "google-auth-httplib2>=0.2", "pyyaml>=6"]
# ///
"""
Publish walkthroughs and Shorts to YouTube through the Data API v3 (no browser, no CDP session).

  uv run scripts/video/youtube_publish.py --kind walkthrough --slug asc842 [--privacy private|public] [--dry-run]
  uv run scripts/video/youtube_publish.py --kind short --slug asc842 [--variant je] [--dry-run]

Token: ~/kdesk-analytics/google-token.json (scripts/setup_seo_oauth.py; needs youtube.force-ssl).
Records: marketing/video/<slug>/youtube.json (walkthrough), short.json (legacy Short), shorts.json (named variants).
Idempotent — an entry with a recorded `url` is skipped.

Note: videos uploaded via the API from an un-audited Google Cloud project are forced to PRIVATE by YouTube
regardless of the requested privacyStatus. Until the project passes the YouTube API compliance audit, flip
them to public in Studio (select all → Visibility) — the upload, thumbnail, metadata and playlist are still
handled here.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
BUILD = REPO / "scripts/video/build"
MV = REPO / "marketing/video"
IMG = REPO / "static/images/products"
TOKEN = pathlib.Path.home() / "kdesk-analytics/google-token.json"

TITLE_MAX, DESC_MAX = 100, 5000
TAIL = ("\n\nBuilt by KDesk Accounting for controllers and finance managers at SaaS companies. Not tax or legal advice.\n"
        "https://kdeskaccounting.com")

META = {
 "asc842": ("ASC 842 Lease Accounting Excel Template — Full Walkthrough (JEs, Rollforward, Reconciliation)",
            "Tab-by-tab walkthrough of the KDesk ASC 842 Lease Accounting Workbook on its real sample data: 20 leases, operating and finance, 120-month amortization schedules, a JE Generator with your GL codes, balance sheet rollforward, maturity analysis, and a reconciliation that ties to $0. Pure Excel, no macros, Windows and Mac."),
 "asc606": ("ASC 606 Commission Capitalization Excel Template — Walkthrough (ASC 340-40 Waterfall, JEs)",
            "Tab-by-tab walkthrough of the KDesk ASC 606 Commission Accrual Workbook: 50 deals, three amortization bases (contract term, estimated benefit period, practical expedient), a 60-month amortization waterfall, JE Generator, deferred commission asset rollforward, and a reconciliation that ties to $0. Pure Excel, no macros."),
 "fixed-assets": ("Fixed Asset Depreciation & Rollforward Excel Template — Walkthrough (SL, DDB, SYD, UoP, JEs)",
            "Tab-by-tab walkthrough of the KDesk Fixed Asset Rollforward Workbook: 50 assets, four depreciation methods, 120-month schedules, a JE Generator with QuickBooks / NetSuite / Sage Intacct / Xero presets, disposal log, category rollforward, and a five-way reconciliation (Schedule = JE = Rollforward = Register = GL). Pure Excel, no macros."),
 "saas-metrics": ("SaaS Metrics Dashboard Excel Template — MRR, ARR, NRR, Churn, CAC, LTV (Full Walkthrough)",
            "Tab-by-tab walkthrough of the KDesk SaaS Metrics & ARR Dashboard: seven monthly inputs, 24 months auto-chained, 11 metrics (MRR, ARR, Net New MRR, gross churn, NRR, ARPA, CAC, LTV, LTV:CAC, CAC payback, Magic Number) and a board-ready dashboard that reconciles to recognized revenue. Pure Excel, no macros."),
 "runway": ("Startup Runway Calculator Excel Template — Runway, Cash-Zero Date, Breakeven (Walkthrough)",
            "Tab-by-tab walkthrough of the KDesk Startup Runway Calculator: 12 to 48-month cash forecast from five input tabs, two-rate revenue growth, Base / Optimistic / Pessimistic scenario multipliers, and a dashboard with months of runway, cash-zero date, peak cash and breakeven. Pure Excel, no macros."),
 "month-end-close": ("Free Month-End Close Checklist Excel Template — 42 Tasks, 18 Reconciliations (Walkthrough)",
            "Walkthrough of the free KDesk Month-End Close Checklist + Tie-Out Workbook: a 42-task close calendar in five phases, 18 subledger-to-GL reconciliations with a materiality flag, a JE tracker with a debits = credits check, and a printable sign-off page. Free, pay what you want."),
}
LINKS = {"asc842": ("asc842", "https://kdeskaccounting.gumroad.com/l/gljxc"), "asc606": ("asc606", "https://kdeskaccounting.gumroad.com/l/cjexre"),
         "fixed-assets": ("fixed-assets", "https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free"),
         "saas-metrics": ("saas-metrics", "https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard-free"),
         "runway": ("runway", "https://kdeskaccounting.gumroad.com/l/runway-calculator-free"),
         "month-end-close": ("month-end-close", "https://kdeskaccounting.gumroad.com/l/month-end-close-checklist")}
TAGS = {"asc842": ["ASC 842", "lease accounting", "Excel template", "journal entries", "controller"],
        "asc606": ["ASC 606", "ASC 340-40", "sales commissions", "deferred commissions", "Excel template"],
        "fixed-assets": ["fixed assets", "depreciation schedule", "fixed asset register", "Excel template"],
        "saas-metrics": ["SaaS metrics", "MRR", "ARR", "NRR", "CAC", "LTV", "Excel dashboard"],
        "runway": ["startup runway", "burn rate", "cash forecast", "Excel template"],
        "month-end-close": ["month end close", "close checklist", "reconciliation", "Excel template", "free"]}


# ---------- pure helpers (tested in tests/test_youtube_publish.py) ----------
def chapters(spec: dict, durations: dict) -> str:
    t, out = 0.0, []
    for i, sc in enumerate(spec["scenes"]):
        kind = sc.get("kind")
        name = "Intro" if kind == "title" else ("Get the workbook" if kind == "outro" else sc.get("caption", sc.get("sheet", "")))
        out.append(f"{int(t // 60)}:{int(t % 60):02d} {name}")
        t += max(3.0, float(durations.get(str(i), 0)) + 0.7)
    return "\n".join(out)


def walkthrough_description(blurb: str, page_url: str, free_url: str, chapters_text: str) -> str:
    return f"{blurb}\n\nProduct page + free version: {page_url}\nFree download: {free_url}\n\nChapters:\n{chapters_text}{TAIL}"


def short_description(desc: str) -> str:
    return desc + TAIL


def video_body(title: str, description: str, tags: list, privacy: str = "private") -> dict:
    return {"snippet": {"title": title[:TITLE_MAX], "description": description[:DESC_MAX], "tags": list(tags), "categoryId": "27"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}


def needs_upload(record: dict) -> bool:
    return not record.get("url")


def is_quota_error(exc: BaseException) -> bool:
    s = str(exc)
    return "quotaExceeded" in s or "uploadLimitExceeded" in s


# ---------- API (lazy imports so the pure helpers stay importable without google libs) ----------
def _service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(str(TOKEN))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request()); TOKEN.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(yt, mp4: pathlib.Path, body: dict) -> str:
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(mp4), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status: print(f"  upload {int(status.progress() * 100)}%", flush=True)
    return resp["id"]


def set_thumbnail(yt, video_id: str, png: pathlib.Path) -> None:
    from googleapiclient.http import MediaFileUpload
    yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(png), mimetype="image/png")).execute()


def add_to_playlist(yt, video_id: str, playlist_id: str) -> None:
    yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": playlist_id,
                              "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()


# ---------- jobs ----------
def walkthrough_job(slug: str, privacy: str):
    import yaml
    spec = yaml.safe_load(open(MV / slug / "scenes.yaml")); durs = json.load(open(BUILD / slug / "audio/durations.json"))
    title, blurb = META[slug]; page, free = LINKS[slug]
    desc = walkthrough_description(blurb, f"https://kdeskaccounting.com/templates/{page}/", free, chapters(spec, durs))
    rec_path = MV / slug / "youtube.json"; rec = json.load(open(rec_path)) if rec_path.exists() else {}
    playlist = json.load(open(MV / "playlist.json")).get("id") if (MV / "playlist.json").exists() else None
    return dict(mp4=BUILD / slug / f"{slug}.mp4", body=video_body(title, desc, TAGS.get(slug, []), privacy), thumb=IMG / f"{slug}-poster.png",
                playlist=playlist, rec_path=rec_path, rec=rec, key=None, url_fmt="https://youtu.be/{}")


def short_job(slug: str, variant: str | None, privacy: str):
    from short_variants import short_paths
    if variant is None:
        rec_path = MV / slug / "short.json"; store = json.load(open(rec_path)); rec = store; key = None
    else:
        rec_path = MV / slug / "shorts.json"; store = json.load(open(rec_path)) if rec_path.exists() else {}
        if variant not in store: raise SystemExit(f"{rec_path} has no entry {variant!r} (need title + description)")
        rec = store[variant]; key = variant
    mp4 = short_paths(BUILD / slug, slug, variant).final
    return dict(mp4=mp4, body=video_body(rec["title"], short_description(rec["description"]), TAGS.get(slug, []) + ["Shorts"], privacy),
                thumb=None, playlist=None, rec_path=rec_path, rec=rec, store=store, key=key, url_fmt="https://youtube.com/shorts/{}")


def run(job: dict, dry_run: bool) -> int:
    if not needs_upload(job["rec"]):
        print(f"already published: {job['rec']['url']}"); return 0
    print(f"{job['mp4'].name}: {job['body']['snippet']['title']}  [{job['body']['status']['privacyStatus']}]")
    if dry_run:
        print("  (dry-run) exists:", job["mp4"].exists(), "| thumb:", job["thumb"], "| playlist:", job["playlist"])
        print("  description:\n   ", job["body"]["snippet"]["description"].replace("\n", "\n    ")[:600]); return 0
    if not job["mp4"].exists(): raise SystemExit(f"missing {job['mp4']} — render it first")
    yt = _service()
    try:
        vid = upload_video(yt, job["mp4"], job["body"])
        if job["thumb"] and job["thumb"].exists(): set_thumbnail(yt, vid, job["thumb"])
        if job["playlist"]: add_to_playlist(yt, vid, job["playlist"])
    except Exception as e:  # noqa: BLE001
        if is_quota_error(e):
            print("YouTube quota exhausted — re-run tomorrow; nothing recorded.", file=sys.stderr); return 3
        raise
    url = job["url_fmt"].format(vid)
    job["rec"].update({"url": url, "video_id": vid, "uploaded": time.strftime("%Y-%m-%d %H:%M"), "via": "data-api"})
    if job.get("store") is not None and job["key"] is not None: job["store"][job["key"]] = job["rec"]; payload = job["store"]
    else: payload = job["rec"]
    json.dump(payload, open(job["rec_path"], "w"), indent=1)
    print("  ->", url); return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["walkthrough", "short"], required=True); ap.add_argument("--slug", required=True)
    ap.add_argument("--variant", default=None, help="named Short under shorts.json / scenes.yaml `shorts:`")
    ap.add_argument("--privacy", choices=["private", "public", "unlisted"], default="private")
    ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    job = walkthrough_job(a.slug, a.privacy) if a.kind == "walkthrough" else short_job(a.slug, a.variant, a.privacy)
    return run(job, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
