#!/usr/bin/env python3
"""One entry point for every publisher.

  python3 scripts/publishers/publish.py --platform youtube --asset X.mp4 --meta meta.json [--dry-run]
  python3 scripts/publishers/publish.py --platform youtube,instagram,site --asset X.mp4 --meta meta.json
  python3 scripts/publishers/publish.py --platform tiktok_web --asset X.mp4 --meta meta.json \
      --schedule 2026-09-21T14:00:00-07:00
  python3 scripts/publishers/publish.py --capabilities
  python3 scripts/publishers/publish.py --whoami        # which Upload-Post profile would we post as?

meta.json: {"slug": "...", "title": "...", "description": "...", "privacy": "public",
            "tags": ["..."], "product": "asc842", "video_url": "(filled by a video publisher)",
            "schedule_at": "(optional ISO 8601 with offset; --schedule overrides it)"}

Exit code 0 only when every requested platform published. A queued card is a non-zero exit
on purpose: the daily job must surface it in the digest.

A live run is gated on ledger entry 69, the T2 decision that authorises auto-publishing:
unless that decision is authorised — its veto window has closed unvetoed, or a later entry's
`approves` names it (entry 85 did, on 2026-09-15) — any non-dry-run publish refuses with exit
2 and publishes nothing. There is no override flag; the unlock is a ledger entry. --dry-run is
never gated, because it writes nothing.

Everything printed or written to the ledger goes through session.redact_secrets first;
PublishResult already masks its own detail and url, and this is the second belt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402

from browser.session import redact_secrets  # noqa: E402
from publishers import upload_post  # noqa: E402
from publishers.instagram import InstagramPublisher  # noqa: E402
from publishers.site import SitePublisher  # noqa: E402
from publishers.tiktok import TikTokPublisher  # noqa: E402
from publishers import tiktok_web  # noqa: E402  (--schedule validation)
from publishers.tiktok_web import TikTokWebPublisher  # noqa: E402
from publishers.youtube import YouTubePublisher  # noqa: E402

PUBLISHERS: dict[str, type] = {"youtube": YouTubePublisher, "tiktok": TikTokPublisher,
                               "tiktok_web": TikTokWebPublisher,
                               "instagram": InstagramPublisher, "site": SitePublisher}
# Platforms whose result url is a public permalink worth embedding in the site post.
# tiktok_web is deliberately absent: it returns the TikTok Studio content URL (a scheduled
# post has no public URL yet), and embedding that would put a 404 behind a reader's click.
VIDEO_PLATFORMS = ("youtube", "tiktok", "instagram")
# The T2 decision that authorises auto-publishing at all: 2026-09-14, "marketing autonomy
# loosened to T1 auto-publish for five surfaces", veto window 2026-09-16 12:00 PT — approved
# early by entry 85 on 2026-09-15, which is what opens this gate today. Until a decision is
# answered the standing rule is "queues, not auto-posters", so a live publish refuses. The
# ledger rows this script writes cite the decision by number; they must not be written while
# it is still pending.
VETO_ENTRY = 69


def whoami() -> int:
    """Print the Upload-Post profiles this key can see, and the profile we would send as."""
    pub = YouTubePublisher()
    key = pub.api_key()
    if not key:
        print("no UPLOAD_POST_KEY in the environment — nothing to ask", file=sys.stderr)
        return 1
    try:
        status, payload = upload_post.list_profiles(key)
    except Exception as exc:  # noqa: BLE001 — a probe must not traceback
        print(pub.mask(f"{type(exc).__name__}: {exc}"), file=sys.stderr)
        return 1
    print(pub.mask(f"HTTP {status} {json.dumps(payload, sort_keys=True)}"))
    print(f"would send user={pub.profile_name()!r} "
          f"(override with UPLOAD_POST_PROFILE)")
    return 0 if status < 300 else 1


def load_meta(ap: argparse.ArgumentParser, path: pathlib.Path) -> dict:
    """Read meta.json, or exit 2 with a one-line message. Never a traceback."""
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        ap.error(f"--meta {path} is not valid JSON: {exc}")
    except OSError as exc:
        ap.error(f"--meta {path} could not be read: {exc}")
    if not isinstance(meta, dict):
        ap.error(f"--meta {path} must be a JSON object, got {type(meta).__name__}")
    return meta


def veto_gate(now: dt.datetime | None = None, *,
              entry_id: int = VETO_ENTRY) -> tuple[bool, str]:
    """May we publish yet? (may_act, why), straight from the shared ledger helper.

    No local copy of the rule and, deliberately, no override flag: an --i-accept-veto-risk
    is the thing that gets typed once at 2 a.m. and then committed to a workflow file. If
    the window has not closed, the answers are --dry-run or wait.
    """
    return ledger.t2_window_open(entry_id, now or dt.datetime.now().astimezone())


def main(argv: list[str] | None = None, *, repo: pathlib.Path | None = None,
         now: dt.datetime | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publish one asset to one or more platforms.")
    ap.add_argument("--platform", help="comma-separated: " + ", ".join(PUBLISHERS))
    ap.add_argument("--asset", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--schedule", metavar="ISO",
                    help="schedule the post for this instant instead of publishing now — "
                         "ISO 8601 WITH an offset (2026-09-21T14:00:00-07:00). Only "
                         "tiktok_web honours it today; capabilities() reports which do.")
    ap.add_argument("--capabilities", action="store_true", help="print each publisher's state and exit")
    ap.add_argument("--whoami", action="store_true",
                    help="list the Upload-Post profiles and their connected accounts, then exit")
    a = ap.parse_args(argv)
    kw = {} if repo is None else {"repo": repo}

    if a.capabilities:
        for name, cls in PUBLISHERS.items():
            print(f"{name:<10} {json.dumps(cls(**kw).capabilities(), sort_keys=True)}")
        return 0
    if a.whoami:
        return whoami()
    if not (a.platform and a.asset and a.meta):
        ap.error("--platform, --asset and --meta are required unless "
                 "--capabilities or --whoami is given")
    # Fail on the caller's own mistake before any publisher runs, rather than half way
    # through a platform list with a traceback.
    for label, path in (("--asset", a.asset), ("--meta", a.meta)):
        if not path.exists():
            ap.error(f"{label} not found: {path}")
    # Same reason: a bad --schedule must fail here, with the caller's own mistake named,
    # rather than half way down a platform list — or worse, inside a publisher, where it
    # would become a queue card that blames the browser.
    if a.schedule:
        try:
            tiktok_web.parse_schedule(a.schedule)
        except tiktok_web.ScheduleError as exc:
            ap.error(f"--schedule {exc}")

    # The gate comes before meta is even read: a refused run must not reach the work, and
    # its message must be the refusal, not a JSON parse error from a file it should not have
    # opened. --dry-run performs zero writes, so there is nothing for a veto to protect
    # against and it stays ungated — it is what a refused caller is told to run.
    if not a.dry_run:
        ok, why = veto_gate(now)
        if not ok:
            print(f"REFUSING: ledger entry {VETO_ENTRY} {why}. Auto-publishing is authorised "
                  f"by that T2 decision alone; until its window closes unvetoed this repo's "
                  f"rule is 'queues, not auto-posters'. Re-run with --dry-run to see exactly "
                  f"what it would have published.", file=sys.stderr)
            return 2

    meta = load_meta(ap, a.meta)
    if a.schedule:
        meta["schedule_at"] = a.schedule
    rc = 0
    for name in [p.strip() for p in a.platform.split(",") if p.strip()]:
        if name not in PUBLISHERS:
            print(f"unknown platform {name!r}; known: {', '.join(PUBLISHERS)}", file=sys.stderr)
            rc = max(rc, 2)
            continue
        result = PUBLISHERS[name](**kw).publish(a.asset, meta, a.dry_run)
        target = result.url or result.queued_path or "(dry-run)"
        print(redact_secrets(
            f"{name:<10} {'ok  ' if result.ok else 'QUEUED'} {target}  {result.detail}"))
        if result.url and name in VIDEO_PLATFORMS:
            meta["video_url"] = meta.get("video_url") or result.url
        if a.dry_run:
            continue
        ledger.append(
            action=redact_secrets(
                f"Published {a.asset.name} to {name}: "
                f"{result.url or 'QUEUED ' + str(result.queued_path)}. {result.detail}"),
            tier=1, status="executed",
            reasoning=("T1 auto-publish after the fact-check gate (2026-09-14 autonomy decision); "
                       "a failure queues a paste-ready card instead of dropping the post."),
            files=[str(result.queued_path)] if result.queued_path else [])
        if not result.ok:
            rc = max(rc, 1)          # never downgrade an unknown-platform 2 to a queued 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
