#!/usr/bin/env python3
"""Cross-post a published Short to the Hugo site as content/shorts/<date>-<slug>.md.

Runs after a video publisher returns a url: the post embeds that url. With no video_url
there is nothing to embed, so it queues rather than publishing an empty page.
Hugo resolves layouts by `type`, so the frontmatter sets type: "shorts" explicitly
(see CLAUDE.md: `layout:` alone silently falls back to _default/single.html).
The iframe is raw HTML inside markdown, which renders because hugo.toml sets
markup.goldmark.renderer.unsafe = true.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import urllib.parse

from publishers.base import REPO, Publisher, PublishResult

SITE_BASE = "https://kdeskaccounting.com"
_PATH_MARKERS = ("/shorts/", "/embed/", "/live/")


def video_id(url: str) -> str | None:
    """The YouTube id behind a /shorts/, /embed/ or youtu.be/ url, or a watch?v= query.

    Parsed rather than string-sliced: Upload-Post returns the watch?v= form (see the
    documented success body), and a naive `url.split("?")[0]` scan drops the id entirely
    for exactly that shape — the site post would then embed an empty player.
    """
    if not url:
        return None
    parts = urllib.parse.urlsplit(str(url))
    v = urllib.parse.parse_qs(parts.query).get("v")
    if v and v[0]:
        return v[0]
    path = parts.path.rstrip("/")
    for marker in _PATH_MARKERS:
        if marker in path:
            return path.rsplit("/", 1)[-1] or None
    if parts.netloc.rsplit("@", 1)[-1].lower().endswith("youtu.be"):
        tail = path.strip("/").split("/")[0]
        return tail or None
    return None


def post_path(repo: pathlib.Path, date: dt.date, slug: str) -> pathlib.Path:
    return pathlib.Path(repo) / "content" / "shorts" / f"{date.isoformat()}-{slug}.md"


def post_markdown(date: dt.date, slug: str, meta: dict) -> str:
    vid = video_id(meta.get("video_url", "")) or ""
    title = str(meta.get("title", ""))
    embed = (f'<div class="kd-short-embed">\n'
             f'  <iframe src="https://www.youtube.com/embed/{html.escape(vid, quote=True)}" '
             f'title="{html.escape(title, quote=True)}" frameborder="0" allowfullscreen '
             f'loading="lazy"></iframe>\n</div>')
    tags = ", ".join(json.dumps(t) for t in meta.get("tags", []))
    description = meta.get("description", "")
    front = "\n".join([
        "---",
        f"title: {json.dumps(meta.get('title', slug))}",
        f"date: {date.isoformat()}",
        'type: "shorts"',
        f"description: {json.dumps(description.splitlines()[0] if description else '')}",
        f"tags: [{tags}]",
        f"product: {json.dumps(meta.get('product', ''))}",
        f"video_url: {json.dumps(meta.get('video_url', ''))}",
        'author: "KDesk Accounting"',
        "ShowToc: false",
        "---",
        "",
    ])
    return f"{front}{embed}\n\n{description}\n"


class SitePublisher(Publisher):
    platform = "site"

    def __init__(self, *, repo: pathlib.Path | None = None, today: dt.date | None = None) -> None:
        super().__init__(repo=repo if repo is not None else REPO)
        self.today = today or dt.date.today()

    def capabilities(self) -> dict:
        return {"platform": "site", "transport": "filesystem",
                "content_dir": str(self.repo / "content" / "shorts"),
                "base_url": SITE_BASE}

    def preflight(self) -> PublishResult | None:
        return None

    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        if not meta.get("video_url"):
            return PublishResult(platform="site", ok=False, url=None, queued_path=None,
                                 detail="meta has no video_url — publish the video first, "
                                        "then re-run publish.py --platform site")
        slug = meta.get("slug", asset.stem)
        path = post_path(self.repo, self.today, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(post_markdown(self.today, slug, meta), encoding="utf-8")
        return PublishResult(platform="site", ok=True,
                             url=f"{SITE_BASE}/shorts/{self.today.isoformat()}-{slug}/",
                             queued_path=None, detail=f"wrote {path.relative_to(self.repo)}")
