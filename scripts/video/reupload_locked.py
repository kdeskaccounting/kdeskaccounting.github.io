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
is reported as NO METADATA rather than a resolvable item; live mode refuses to upload it
(title-less would mean uploading blank), queues a manual card instead, and counts it as failed.

Three more failure shapes get the same "never silently lose the asset" treatment:
- A missing local mp4 also queues a manual card (marketing/publish-queue/manual/) with the
  exact re-render or download command, instead of just printing and moving on.
- Upload-Post can accept an upload asynchronously and still not have a url after the bounded
  poll in publishers/upload_post.py; that PublishResult says DO NOT RE-UPLOAD. Re-running this
  script must not attempt that item again, so its request_id is persisted on the record
  (`pending_request_id`) and every later scan()/run reports and skips it.
- update_record() writes atomically (temp file + os.replace) so a mid-write crash never
  corrupts a record that 19 other re-uploads still depend on being readable.
Stdlib only at import time.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402

RECORD_FILES = ("youtube.json", "short.json", "shorts.json")
RELEASE_TAG = "media-2026-09"
_REQUEST_ID_RE = re.compile(r"request_id[:\s]+([\w-]+)")


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
    pending_request_id: str | None = None    # set once an Upload-Post async accept times out


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
    if not base.exists():
        return out
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
                    old_url=entry["url"], video_id=entry.get("video_id", ""),
                    pending_request_id=entry.get("pending_request_id")))
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
    """The publish() payload, built exactly the way youtube_publish.py built it originally.

    Brief defect (fixed here): the Task 4 brief's meta_for used item.description verbatim and
    tags=[] unconditionally, which silently dropped short_description()'s TAIL (the disclaimer
    + site link every Short carried) and every Short's TAGS[slug] + ["Shorts"]. A walkthrough's
    description already ran through walkthrough_description() in scan()'s fallback (or was
    read verbatim off the record), so it needs no extra wrapping here — only its TAGS.
    """
    import youtube_publish as yp

    slug = f"{item.slug}-{item.key}" if item.key else item.slug
    if item.kind == "youtube":
        description = item.description
        tags = yp.TAGS.get(item.slug, [])
    else:
        description = yp.short_description(item.description)
        tags = yp.TAGS.get(item.slug, []) + ["Shorts"]
    return {"slug": slug, "title": item.title, "description": description,
            "privacy": "public", "product": item.slug, "tags": tags}


def _video_id_from_url(url: str) -> str:
    """The id YouTube assigned the new upload — the ?v= query param when present (the
    watch?v= shape Upload-Post's success body documents), else the last path segment
    (youtu.be/<id>, .../shorts/<id>). Reuses publishers.site.video_id, which already parses
    both shapes correctly (it exists so a naive path-only split doesn't drop the id for a
    watch?v= url, which previously turned into the literal string "watch")."""
    from publishers.site import video_id as parse_video_id

    return parse_video_id(url) or url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]


def _atomic_write_json(path: pathlib.Path, data: dict) -> None:
    """Write `data` to `path` via a same-directory temp file + os.replace.

    os.replace is atomic on the same filesystem, so a crash or exception between the temp
    write and the replace leaves the original file exactly as it was — never a half-written
    record. 19 other locked videos' state lives in sibling files that must stay readable even
    if this one write fails.
    """
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def update_record(item: LockedVideo, new_url: str) -> dict:
    data = json.loads(item.rec_path.read_text(encoding="utf-8"))
    entry = data[item.key] if item.key else data
    entry["replaced_url"] = entry.get("url")
    entry["url"] = new_url
    entry["via"] = "upload-post"
    entry["video_id"] = _video_id_from_url(new_url)
    entry.pop("pending_request_id", None)
    _atomic_write_json(item.rec_path, data)
    return entry


def mark_pending(item: LockedVideo, request_id: str) -> dict:
    """Record that Upload-Post accepted this upload asynchronously and never confirmed a url.

    Leaves url/via untouched (the old Data-API upload is still what's live) so `_locked()`
    keeps finding the record on the next scan — but with pending_request_id set, scan()/main()
    skip it instead of re-uploading, which would double-post a video that may already be live.
    """
    data = json.loads(item.rec_path.read_text(encoding="utf-8"))
    entry = data[item.key] if item.key else data
    entry["pending_request_id"] = request_id
    _atomic_write_json(item.rec_path, data)
    return entry


def pending_request_id_from_detail(detail: str) -> str | None:
    """The request_id inside an async "accepted but never confirmed, DO NOT RE-UPLOAD"
    PublishResult detail (see publishers/upload_post.py poll_status), or None for an ordinary
    failure. There is no structured field for it — base.PublishResult carries only
    platform/ok/url/queued_path/detail — so this is a regex over the one place it appears.
    """
    m = _REQUEST_ID_RE.search(detail or "")
    return m.group(1) if m else None


def _gh_release_command(item: LockedVideo) -> str:
    return (f"gh release download {RELEASE_TAG} --pattern "
            f"'{expected_mp4_name(item.slug, item.kind, item.key)}' "
            f"--dir scripts/video/build/{item.slug}")


def _regen_command(item: LockedVideo) -> str:
    """The command that actually (re)renders item's mp4 locally, as opposed to downloading a
    copy already on the GitHub release."""
    if item.kind == "youtube":
        return (f"scripts/video/.venv-tts/bin/python scripts/video/build_video.py "
                f"--spec marketing/video/{item.slug}/scenes.yaml")
    variant = f" --variant {item.key}" if item.key else ""
    return f"scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug {item.slug}{variant}"


def _queue_manual_card(repo: pathlib.Path, item: LockedVideo, why: str, steps: list[str]) -> pathlib.Path:
    """Write a paste-ready "why + numbered steps" card for a pre-publish problem this script
    found itself (missing metadata, missing mp4) — the "queues, not silent failures" rule
    applies here just as much as to an actual publish() failure. Uses the same
    scripts/browser/session.py helpers base.Publisher.queue() builds its own cards from.
    """
    from browser import session
    from publishers.base import sanitize_slug

    label = f"{item.slug}-{item.key}" if item.key else f"{item.slug}-{item.kind}"
    body = session.queue_card_markdown(
        "manual", f"re-upload {item.slug}/{item.key or item.kind}", why, steps)
    return session.write_queue_card(repo, "manual", sanitize_slug(label) or "untitled", body)


def live_run(items: list[LockedVideo], repo: pathlib.Path, pub, *, limit: int | None = None) -> dict:
    """Drive `pub.publish()` for each item that can actually be attempted.

    Never uploads a title-less item (NO METADATA), never re-attempts a pending async upload,
    and never silently drops a missing mp4 — each of those three instead queues a manual card
    and counts toward `failed`. `--limit` bounds real upload attempts the same way in every
    case: once `limit` have succeeded, every remaining item (regardless of its own state) is
    reported as "not processed" rather than touched.

    Returns {"done": int, "failed": int, "rewritten": set[str]} — `rewritten` holds only the
    record paths (relative to `repo`) actually mutated (a real re-upload or a newly-pending
    request), which is exactly what belongs in the ledger's `files`, not every item scanned.
    Also appends one ledger entry for the whole run, scoped to that same `rewritten` set.
    """
    done = failed = 0
    rewritten: set[str] = set()
    for idx, item in enumerate(items):
        label = f"{item.slug}/{item.key or item.kind}"
        if limit is not None and done >= limit:
            remaining = ", ".join(f"{r.slug}/{r.key or r.kind}" for r in items[idx:])
            print(f"stopping at --limit {limit}; not processed: {remaining}")
            break
        if item.pending_request_id:
            failed += 1
            print(f"  {label}: PENDING {item.pending_request_id} — check status, do not re-upload")
            continue
        if not item.title:
            card = _queue_manual_card(
                repo, item,
                why=(f"{item.rec_path.relative_to(repo)} has no stored title and none could be "
                     f"reconstructed from youtube_publish.META — Upload-Post requires one."),
                steps=[f"Add a title and description to {item.rec_path.relative_to(repo)}"
                       + (f" (key {item.key!r})" if item.key else ""),
                       "Re-run python3 scripts/video/reupload_locked.py"])
            failed += 1
            print(f"  {label}: NO METADATA — queued {card.relative_to(repo)}")
            continue
        mp4 = resolve_mp4(repo, item)
        if mp4 is None:
            card = _queue_manual_card(
                repo, item,
                why=f"No local mp4 for {label} under scripts/video/build/{item.slug}/.",
                steps=[_gh_release_command(item), _regen_command(item),
                       "Re-run python3 scripts/video/reupload_locked.py"])
            failed += 1
            print(f"  {label}: no local mp4 — queued {card.relative_to(repo)}")
            continue
        result = pub.publish(mp4, meta_for(item), dry_run=False)
        if result.ok and result.url:
            update_record(item, result.url)
            rewritten.add(str(item.rec_path.relative_to(repo)))
            done += 1
            print(f"  {label}: {item.old_url} -> {result.url}")
            continue
        rid = pending_request_id_from_detail(result.detail)
        if rid:
            mark_pending(item, rid)
            rewritten.add(str(item.rec_path.relative_to(repo)))
            failed += 1
            print(f"  {label}: PENDING {rid} — check status, do not re-upload")
        else:
            failed += 1
            print(f"  {label}: QUEUED {result.queued_path} ({result.detail})")
    ledger.append(
        action=(f"Re-uploaded {done} of {len(items)} locked-private YouTube videos through "
                f"Upload-Post ({failed} queued, pending or missing an mp4/title). The Data-API "
                f"uploads were locked private with 0 views and cannot be appealed; rewritten "
                f'records now carry "via": "upload-post" (or a pending_request_id) with the '
                f'old url under "replaced_url".'),
        tier=1, status="executed",
        reasoning=("Google: a locked-private upload from an unverified API project must be "
                   "re-uploaded. Upload-Post holds audited credentials, so its uploads are "
                   "public. files is scoped to records actually rewritten, not every item "
                   "scanned, so the ledger reflects real side effects only."),
        files=sorted(rewritten))
    return {"done": done, "failed": failed, "rewritten": rewritten}


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-upload the locked-private Data-API videos.")
    ap.add_argument("--slug", help="only this product slug")
    ap.add_argument("--limit", type=int, help="stop after N uploads (Upload-Post free tier is 10/mo)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = [i for i in scan(REPO) if not a.slug or i.slug == a.slug]
    print(f"{len(items)} locked-private record(s) with via=data-api")
    if a.dry_run:
        would_upload = 0
        for idx, item in enumerate(items):
            if a.limit is not None and would_upload >= a.limit:
                remaining = ", ".join(f"{r.slug}/{r.key or r.kind}" for r in items[idx:])
                print(f"stopping at --limit {a.limit}; not processed: {remaining}")
                break
            if item.pending_request_id:
                print(f"  {item.slug:<15} {item.kind:<8} {str(item.key):<12} {item.old_url}\n"
                      f"      PENDING {item.pending_request_id} — check status, do not re-upload")
                continue
            if not item.title:
                print(f"  {item.slug:<15} {item.kind:<8} {str(item.key):<12} {item.old_url}\n"
                      f"      NO METADATA — {item.rec_path.relative_to(REPO)} has no title and "
                      f"none could be reconstructed from youtube_publish.META")
                continue
            mp4 = resolve_mp4(REPO, item)
            where = str(mp4.relative_to(REPO)) if mp4 else f"MISSING — {_gh_release_command(item)}"
            print(f"  {item.slug:<15} {item.kind:<8} {str(item.key):<12} {item.old_url}\n"
                  f"      -> {where}\n      title: {item.title[:80]}")
            if mp4 is not None:
                would_upload += 1
        return 0

    from publishers.youtube import YouTubePublisher
    pub = YouTubePublisher(repo=REPO)
    result = live_run(items, REPO, pub, limit=a.limit)
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
