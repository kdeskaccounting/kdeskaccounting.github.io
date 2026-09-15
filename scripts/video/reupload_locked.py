#!/usr/bin/env python3
"""Re-publish, through Upload-Post, every video that the YouTube Data API locked private.

Verified 2026-09-14: 20 records across marketing/video/*/{youtube,short,shorts}.json carry
"via": "data-api". Those uploads are locked private with 0 views and cannot be appealed
(support.google.com/youtube/answer/7300965) — they have to be re-uploaded by a scheduler
holding audited credentials. This drives scripts/publishers/youtube.py for each one with
the original title and description, then rewrites the record with the new url and
"via": "upload-post", keeping the old url under "replaced_url".

  python3 scripts/video/reupload_locked.py --dry-run          # list every item and its mp4
  python3 scripts/video/reupload_locked.py [--slug asc842] [--limit 5]

mp4 resolution order: scripts/video/build/<slug>/<name>.mp4 (local renders), then any mp4
downloaded from the GitHub release media-2026-09 into that same folder:
  gh release download media-2026-09 --pattern '<slug>.mp4' --dir scripts/video/build/<slug>

marketing/video/<slug>/youtube.json (the long-form walkthroughs) never stored a title or
description — youtube_publish.py's walkthrough_job() built them fresh from META/LINKS and the
scenes.yaml chapters every run instead of persisting them. scan() rebuilds them the same way
(youtube_publish.META for the title and blurb, chapters()+walkthrough_description() over
scenes.yaml/durations.json for the full description when both are on disk, else the blurb
alone). A slug missing from META has no fallback at all: its LockedVideo.title stays "" and
--dry-run prints it as NO METADATA rather than a resolvable item; main() refuses to upload it
live (title-less would mean uploading blank) and counts it as failed instead.
Stdlib only at import time.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402

RECORD_FILES = ("youtube.json", "short.json", "shorts.json")
RELEASE_TAG = "media-2026-09"


@dataclasses.dataclass(frozen=True)
class LockedVideo:
    rec_path: pathlib.Path
    key: str | None          # variant name inside shorts.json, else None
    slug: str
    kind: str                # "youtube" | "short" | "shorts"
    title: str
    description: str
    old_url: str
    video_id: str


def _locked(entry: dict) -> bool:
    return isinstance(entry, dict) and entry.get("via") == "data-api" and bool(entry.get("url"))


def _walkthrough_fallback(repo: pathlib.Path, slug: str) -> tuple[str, str] | None:
    """Rebuild a missing walkthrough title/description the way youtube_publish.py built them
    at upload time (it never persisted them to youtube.json). Returns None when `slug` is not
    in youtube_publish.META at all — there is nothing to fall back to, and the caller must
    treat that record as having no usable metadata rather than inventing one.

    The full chapters-based description needs scenes.yaml + durations.json on disk and PyYAML
    to parse the former; when either is missing (as in a test fixture, or the tests-only
    stdlib environment where PyYAML itself is absent) this degrades to the blurb alone rather
    than raising — a shorter real description beats crashing scan() or uploading blank.
    """
    import youtube_publish as yp  # scripts/video/youtube_publish.py; stdlib-only at import time

    meta = yp.META.get(slug)
    if not meta:
        return None
    title, blurb = meta
    description = blurb
    links = yp.LINKS.get(slug)
    scenes_path = pathlib.Path(repo) / "marketing" / "video" / slug / "scenes.yaml"
    durations_path = (pathlib.Path(repo) / "scripts" / "video" / "build" / slug
                       / "audio" / "durations.json")
    if links and scenes_path.exists() and durations_path.exists():
        try:
            import yaml  # lazy: absent in the stdlib-only test environment
            spec = yaml.safe_load(scenes_path.read_text(encoding="utf-8"))
            durs = json.loads(durations_path.read_text(encoding="utf-8"))
            page, free = links
            chapters_text = yp.chapters(spec, durs)
            description = yp.walkthrough_description(
                blurb, f"https://kdeskaccounting.com/templates/{page}/", free, chapters_text)
        except Exception:  # noqa: BLE001 — a best-effort upgrade; the blurb is still a real description
            description = blurb
    return title, description


def scan(repo: pathlib.Path = REPO) -> list[LockedVideo]:
    out: list[LockedVideo] = []
    base = pathlib.Path(repo) / "marketing" / "video"
    for slug_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for name in RECORD_FILES:
            path = slug_dir / name
            if not path.exists():
                continue
            kind = name.removesuffix(".json")
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.items() if kind == "shorts" else [(None, data)]
            for key, entry in items:
                if not _locked(entry):
                    continue
                title = entry.get("title", "")
                description = entry.get("description", "")
                if kind == "youtube" and not title:
                    fallback = _walkthrough_fallback(repo, slug_dir.name)
                    if fallback is not None:
                        title, description = fallback
                out.append(LockedVideo(
                    rec_path=path, key=key, slug=slug_dir.name, kind=kind,
                    title=title, description=description,
                    old_url=entry["url"], video_id=entry.get("video_id", "")))
    return out


def expected_mp4_name(slug: str, kind: str, key: str | None) -> str:
    if kind == "youtube":
        return f"{slug}.mp4"
    if kind == "short":
        return f"{slug}-short.mp4"
    return f"{slug}-short-{key}.mp4"


def resolve_mp4(repo: pathlib.Path, item: LockedVideo) -> pathlib.Path | None:
    candidate = (pathlib.Path(repo) / "scripts" / "video" / "build" / item.slug
                 / expected_mp4_name(item.slug, item.kind, item.key))
    return candidate if candidate.exists() else None


def meta_for(item: LockedVideo) -> dict:
    slug = f"{item.slug}-{item.key}" if item.key else item.slug
    return {"slug": slug, "title": item.title, "description": item.description,
            "privacy": "public", "product": item.slug, "tags": []}


def update_record(item: LockedVideo, new_url: str) -> dict:
    data = json.loads(item.rec_path.read_text(encoding="utf-8"))
    entry = data[item.key] if item.key else data
    entry["replaced_url"] = entry.get("url")
    entry["url"] = new_url
    entry["via"] = "upload-post"
    entry["video_id"] = new_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    item.rec_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-upload the locked-private Data-API videos.")
    ap.add_argument("--slug", help="only this product slug")
    ap.add_argument("--limit", type=int, help="stop after N uploads (Upload-Post free tier is 10/mo)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = [i for i in scan(REPO) if not a.slug or i.slug == a.slug]
    print(f"{len(items)} locked-private record(s) with via=data-api")
    if a.dry_run:
        for item in items:
            mp4 = resolve_mp4(REPO, item)
            where = str(mp4.relative_to(REPO)) if mp4 else (
                f"MISSING — gh release download {RELEASE_TAG} --pattern "
                f"'{expected_mp4_name(item.slug, item.kind, item.key)}' "
                f"--dir scripts/video/build/{item.slug}")
            title_line = (f"title: {item.title[:80]}" if item.title else
                          f"NO METADATA — {item.rec_path.relative_to(REPO)} has no title and "
                          f"none could be reconstructed from youtube_publish.META")
            print(f"  {item.slug:<15} {item.kind:<8} {str(item.key):<12} {item.old_url}\n"
                  f"      -> {where}\n      {title_line}")
        return 0

    from publishers.youtube import YouTubePublisher
    pub = YouTubePublisher(repo=REPO)
    done = failed = 0
    for item in items:
        if not item.title:
            failed += 1
            print(f"  {item.slug}/{item.key or item.kind}: NO METADATA — "
                  f"{item.rec_path.relative_to(REPO)} has no title and none could be "
                  f"reconstructed from youtube_publish.META; skipping rather than uploading blank")
            continue
        if a.limit is not None and done >= a.limit:
            print(f"stopping at --limit {a.limit}")
            break
        mp4 = resolve_mp4(REPO, item)
        if mp4 is None:
            failed += 1
            print(f"  {item.slug}/{item.key or item.kind}: no local mp4 — "
                  f"gh release download {RELEASE_TAG} --pattern "
                  f"'{expected_mp4_name(item.slug, item.kind, item.key)}' "
                  f"--dir scripts/video/build/{item.slug}")
            continue
        result = pub.publish(mp4, meta_for(item), dry_run=False)
        if result.ok and result.url:
            update_record(item, result.url)
            done += 1
            print(f"  {item.slug}/{item.key or item.kind}: {item.old_url} -> {result.url}")
        else:
            failed += 1
            print(f"  {item.slug}/{item.key or item.kind}: QUEUED {result.queued_path} "
                  f"({result.detail})")
    ledger.append(
        action=(f"Re-uploaded {done} of {len(items)} locked-private YouTube videos through "
                f"Upload-Post ({failed} queued or missing an mp4). The Data-API uploads were "
                f"locked private with 0 views and cannot be appealed; the records now carry "
                f'"via": "upload-post" with the old url under "replaced_url".'),
        tier=1, status="executed",
        reasoning=("Google: a locked-private upload from an unverified API project must be "
                   "re-uploaded. Upload-Post holds audited credentials, so its uploads are public."),
        files=sorted({str(i.rec_path.relative_to(REPO)) for i in items}))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
