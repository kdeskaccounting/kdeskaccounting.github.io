#!/usr/bin/env python3
"""Cross-post a published Short to the Hugo site as content/shorts/<date>-<slug>.md.

Runs after a video publisher returns a url: the post embeds that url. With no video_url
there is nothing to embed, so it queues rather than publishing an empty page.
Hugo resolves layouts by `type`, so the frontmatter sets type: "shorts" explicitly
(see CLAUDE.md: `layout:` alone silently falls back to _default/single.html).
The iframe is raw HTML inside markdown, which renders because hugo.toml sets
markup.goldmark.renderer.unsafe = true. Its wrapper class `.kd-short-embed` is styled in
assets/css/extended/custom.css (9:16, capped so a vertical video does not fill a desktop
screen); the width/height attributes carry the same ratio for the moment before CSS loads.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import urllib.parse

from publishers.base import REPO, Publisher, PublishResult, card_slug, slug_holds_a_secret

SITE_BASE = "https://kdeskaccounting.com"
# The intrinsic size the browser reserves for the player before any CSS has loaded. The
# stylesheet (.kd-short-embed in assets/css/extended/custom.css) then makes it fluid, but
# without these attributes the iframe defaults to 300x150 - a letterboxed sliver for a
# vertical video, and a layout shift when the CSS lands. 315x560 is exactly 9:16.
EMBED_WIDTH = 315
EMBED_HEIGHT = 560
_PATH_MARKERS = ("/shorts/", "/embed/", "/live/")
# An explicit allow-list, never a suffix match (the same rule session.Site.alt_hosts follows):
# 'youtube.com.evil.test' and 'notyoutube.com' must not read as YouTube.
_YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})


def video_id(url: str) -> str | None:
    """The YouTube id behind a /shorts/, /embed/ or youtu.be/ url, or a watch?v= query.

    Parsed rather than string-sliced: Upload-Post returns the watch?v= form (see the
    documented success body), and a naive `url.split("?")[0]` scan drops the id entirely
    for exactly that shape — the site post would then embed an empty player.

    The host must be YouTube. Without that check any `?v=` yielded an "id", so an Instagram
    permalink threaded in by publish.py would have been embedded in a YouTube player.
    """
    if not url:
        return None
    parts = urllib.parse.urlsplit(str(url))
    if (parts.hostname or "").lower() not in _YOUTUBE_HOSTS:
        return None
    v = urllib.parse.parse_qs(parts.query).get("v")
    if v and v[0]:
        return v[0]
    path = parts.path.rstrip("/")
    for marker in _PATH_MARKERS:
        if marker in path:
            return path.rsplit("/", 1)[-1] or None
    if (parts.hostname or "").lower() == "youtu.be":
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
             f'title="{html.escape(title, quote=True)}" '
             f'width="{EMBED_WIDTH}" height="{EMBED_HEIGHT}" '
             f'frameborder="0" allowfullscreen '
             f'loading="lazy"></iframe>\n</div>')
    tags = ", ".join(json.dumps(t) for t in meta.get("tags", []))
    description = meta.get("description", "")
    # PaperMod renders `summary` on list pages and `description` in the meta tag, and every
    # hand-written post in content/posts/ carries both. description is the first line;
    # summary is the whole caption flattened to one line unless meta names its own.
    summary = meta.get("summary") or " ".join(description.split())
    front = "\n".join([
        "---",
        f"title: {json.dumps(meta.get('title', slug))}",
        f"date: {date.isoformat()}",
        'type: "shorts"',
        f"description: {json.dumps(description.splitlines()[0] if description else '')}",
        f"summary: {json.dumps(summary)}",
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
        video_url = meta.get("video_url")
        if not video_url:
            return PublishResult(platform="site", ok=False, url=None, queued_path=None,
                                 detail="meta has no video_url — publish the video first, "
                                        "then re-run publish.py --platform site")
        # Presence is not enough. publish.py threads whatever url the first video publisher
        # returned into meta, so this can be an Instagram permalink — which would render
        # <iframe src=".../embed/">, an empty player, reported as a success.
        if not video_id(video_url):
            return PublishResult(platform="site", ok=False, url=None, queued_path=None,
                                 detail=(f"no YouTube video id in video_url {video_url!r} — "
                                         "the embed would be an empty player; publish to "
                                         "YouTube first, or paste the post by hand"))
        # card_slug quietly falls back to the asset name for a slug holding a credential.
        # That is right for a private queue card and wrong here: this slug becomes a public
        # URL, so publishing something Stephen did not name would be worse than refusing.
        if slug_holds_a_secret(meta.get("slug") or ""):
            return PublishResult(platform="site", ok=False, url=None, queued_path=None,
                                 detail="the slug in meta.json contains a credential — "
                                        "refusing to put it in a public URL; rename it")
        slug = card_slug(meta, asset)
        path = post_path(self.repo, self.today, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(post_markdown(self.today, slug, meta), encoding="utf-8")
        return PublishResult(platform="site", ok=True,
                             url=f"{SITE_BASE}/shorts/{self.today.isoformat()}-{slug}/",
                             queued_path=None, detail=f"wrote {path.relative_to(self.repo)}")
