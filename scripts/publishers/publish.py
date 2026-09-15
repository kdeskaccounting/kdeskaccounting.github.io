#!/usr/bin/env python3
"""One entry point for every publisher.

  python3 scripts/publishers/publish.py --platform youtube --asset X.mp4 --meta meta.json [--dry-run]
  python3 scripts/publishers/publish.py --platform youtube,instagram,site --asset X.mp4 --meta meta.json
  python3 scripts/publishers/publish.py --capabilities

meta.json: {"slug": "...", "title": "...", "description": "...", "privacy": "public",
            "tags": ["..."], "product": "asc842", "video_url": "(filled by a video publisher)"}

Exit code 0 only when every requested platform published. A queued card is a non-zero exit
on purpose: the daily job must surface it in the digest.

Everything printed or written to the ledger goes through session.redact_secrets first;
PublishResult already masks its own detail and url, and this is the second belt.
"""
from __future__ import annotations

import argparse
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
from publishers.youtube import YouTubePublisher  # noqa: E402

PUBLISHERS: dict[str, type] = {"youtube": YouTubePublisher, "tiktok": TikTokPublisher,
                               "instagram": InstagramPublisher, "site": SitePublisher}
VIDEO_PLATFORMS = ("youtube", "tiktok", "instagram")


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


def main(argv: list[str] | None = None, *, repo: pathlib.Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publish one asset to one or more platforms.")
    ap.add_argument("--platform", help="comma-separated: " + ", ".join(PUBLISHERS))
    ap.add_argument("--asset", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true")
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
        ap.error("--platform, --asset and --meta are required unless --capabilities is given")
    # Fail on the caller's own mistake before any publisher runs, rather than half way
    # through a platform list with a traceback.
    for label, path in (("--asset", a.asset), ("--meta", a.meta)):
        if not path.exists():
            ap.error(f"{label} not found: {path}")

    meta = load_meta(ap, a.meta)
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
