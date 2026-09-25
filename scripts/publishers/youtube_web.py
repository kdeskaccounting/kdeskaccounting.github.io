#!/usr/bin/env python3
"""Publish a Short to the ParkSheet channel through YouTube Studio's web uploader.

  scripts/video/.venv-tts/bin/python scripts/publishers/youtube_web.py --check
  scripts/video/.venv-tts/bin/python scripts/publishers/youtube_web.py --dry-run \
      --asset ~/parksheet/build/release/2026-W38/day-6.mp4 \
      --meta  ~/parksheet/build/release/2026-W38/day-6.json
  scripts/video/.venv-tts/bin/python scripts/publishers/youtube_web.py --go \
      --asset ~/parksheet/build/release/2026-W40/day-1.mp4 \
      --meta  ~/parksheet/build/release/2026-W40/day-1.json
  scripts/video/.venv-tts/bin/python scripts/publishers/publish.py --platform youtube_web \
      --asset ~/parksheet/build/release/2026-W40/day-1.mp4 \
      --meta  ~/parksheet/build/release/2026-W40/day-1.json

`--go` is required for a real post from this module's own CLI, and `publish.py --dry-run`
refuses this platform: rehearse with `youtube_web.py --dry-run`, which is the only dry run
that knows it is allowed to upload and then clean up after itself.

**SESSION ONLY — never from GitHub Actions, never on a cron.** This drives a logged-in
browser session, which is a grey area in YouTube's terms: it runs beside Stephen in the
daily Chrome session, one post at a time, and every failure stops and asks rather than
retrying. Chrome rule 1. There is no workflow file for it and there must not be one.

**Why not the API, and why not Upload-Post.** Uploads through the YouTube Data API on this
account are locked to `private` and stay there, so the API is barred for publishing
(`scripts/video/youtube_publish.py` carries the same warning). Upload-Post's free tier is ten
uploads a month, which a daily Short plus Instagram exhausts inside a fortnight, and Stephen
declined the paid plan. On 2026-09-25 he ruled that YouTube and Instagram posting move into
the daily Chrome session — so this is Studio-in-Chrome, the same shape as
`scripts/publishers/tiktok_web.py`. The Upload-Post transport stays registered as `youtube`
and is untouched; this one is `youtube_web`.

**Shape** (spec Chrome rule 4 — the same read → diff → apply → re-read → assert the Gumroad
and TikTok drivers use):

    am I ParkSheet? ─► no ─► refuse, touch nothing
                    └► yes ─► read the content list ─► this title already there? ─► skip, ok
                                                    └► no ─► upload, fill, Public, Publish
                                                             ─► re-read ─► assert Public

**The channel guard is not decoration.** The debug Chrome profile also holds Stephen's
personal YouTube channel, and Studio remembers whichever was last used. Posting a ParkSheet
Short to the personal channel is not something a later run can undo, so every entry point —
`--check`, a dry run and a live publish alike — reads the channel name first and refuses on
anything but ParkSheet.

**Idempotency** is the rest of the safety story. Re-running a day, or resuming after a crash,
must never put the same video on the channel twice, so the title read comes first and a post
that was submitted but could not be verified is **not** retried.

**What --dry-run does.** Everything a live run does except the final Publish click: it opens
the uploader, uploads the mp4 for real, fills the title and description, answers "made for
kids", walks Details → Video elements → Initial check → Visibility and selects Public — then
closes the uploader (YouTube silently saves a draft) and DELETES that draft from the content
list, and asserts the list is back to what it was. Deleting the draft is possible and is
verified: row menu → "Delete forever" → tick the acknowledgement → "Delete draft video"
(counted live 2026-09-25). If the draft cannot be deleted the run queues a card naming the
draft, because a leftover draft on the channel is the one thing a dry run must never leave.

Playwright is only ever imported inside `session.open_page`, so this module imports with the
standard library alone (CLAUDE.md "Useful commands": the test suite has nothing else).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from browser import selectors_youtube as S  # noqa: E402
from browser import session  # noqa: E402
from publishers import base  # noqa: E402
from publishers.base import REPO, Publisher, PublishResult  # noqa: E402

PLATFORM = "youtube_web"
SITE = "youtube"
# Both YouTube transports queue into one folder: to Stephen a card is "a YouTube post that
# needs a human", and which publisher wrote it is a detail inside the card.
QUEUE_SUBDIR = "youtube"
# Below this, a "title" is a stub that would prefix-match half the channel. A title this short
# means the meta is wrong, and skipping every day of the week is the failure mode.
MIN_TITLE_LEN = 12
# How a content row says "this title is cut off". Live on 2026-09-25 the row carried the full
# 86-character title, so this is a safety net rather than the normal path — but the direction
# it protects is the expensive one: a truncated row that failed an equality test would be read
# as "not posted yet" and the video would go up twice.
ELLIPSIS = ("…", "...")


class WrongChannel(RuntimeError):
    """Studio is signed in as some other channel. Never retried, never worked around."""


class ScrapeError(RuntimeError):
    """The content list rendered, but no row's title could be read.

    Distinct from "the channel has no videos": rows exist, so the markup drifted. Reading that
    as an empty list is what would upload a second copy of a video that is already live.
    """


class SessionLost(RuntimeError):
    """A navigation landed on the sign-in wall part-way through the flow."""


class FormFieldError(RuntimeError):
    """A field would not take its value, or a step would not advance — the markup has drifted."""


class TitleTooLong(ValueError):
    """`meta.title` is longer than YouTube allows. Refused, never truncated."""


class RowNotPublished(RuntimeError):
    """A row with this title is on the content list, but it is not a published public video.

    The skip has to be a CLOSED door. "A row with this title exists" is not the same claim as
    "this day is already up": a Private, Unlisted or Scheduled row, or a visibility cell that
    reads "" because the selector drifted, would all have returned ok "already published" —
    and the day would then be silently skipped for ever, with no video on the channel and
    nothing anywhere saying so. Only PUBLIC_VISIBILITY_TEXT is a skip; everything else raises
    and a human decides.
    """


class AmbiguousList(RuntimeError):
    """The content list truncated a title, so "is this day already up?" cannot be answered.

    Fails closed rather than guessing in either direction: prefix-matching a truncated row
    would let one ParkSheet day stand in for another that shares its "Hidden Detail Monday — "
    opening, and ignoring it would upload a video that is already live.
    """


class DraftInTheWay(RowNotPublished):
    """A draft of this exact title is already on the channel.

    Its own type, and never a skip: a draft is not a published video, so reporting "already
    published" would mean this day never goes up — and uploading anyway would leave two copies
    of it in the content list, one of them invisible to the idempotency read. A human decides
    whether to publish that draft or delete it.
    """


class DraftNotRemoved(RuntimeError):
    """A dry run uploaded a video and could not delete the draft it left behind.

    Its own type because it is the one dry-run failure that has changed the channel: the card
    it raises has to name the draft so Stephen can delete it by hand.
    """


class VerificationFailed(RuntimeError):
    """The Publish click went through but the video is not on the content list as Public.

    Deliberately its own type: this is the one failure that must NOT be retried. The video may
    be live already, and a second pass would upload it again.
    """


# --------------------------------------------------------------------------- pure helpers

def _norm(text) -> str:
    """Whitespace-collapsed, lowercased. For MATCHING titles and for error prose — never for
    verifying a field's contents: it cannot tell a paragraph from the same words on nine
    lines, which is the whole of what `fill_box` has to check."""
    return " ".join(str(text or "").split()).strip().lower()


def _lines(text) -> str:
    """`text` with CRLF/CR folded to LF and the ends trimmed. Exact otherwise.

    The only normalisation a read-back may apply: a contenteditable can hand a CRLF back where
    a bare LF went in, and the trailing newline a browser appends is not a lost line. Anything
    else — a missing break, a collapsed blank line — has to fail.
    """
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def title_of(meta: dict) -> str:
    """The title YouTube gets — Stephen's own copy, verbatim.

    Deliberately NOT assembled from tags or trimmed to fit: the meta files are written by the
    ParkSheet renderer with the title already inside YouTube's limit, and a title this driver
    edited would no longer be the one the fact-check pass approved.
    """
    return str(meta.get("title") or "").strip()


def description_of(meta: dict) -> str:
    """The description YouTube gets, verbatim — it carries the required attribution lines.

    Queue-Times, ThemeParks.wiki, the photo credits and the "not affiliated" disclaimer are
    licence conditions, not copy. Nothing here rewrites, reorders or appends to them; tags are
    NOT folded in the way the TikTok caption folds them, because YouTube has its own tag field
    and a hashtag wall in the description is not what the renderer wrote.
    """
    return str(meta.get("description") or "").rstrip()


def check_title(title: str) -> None:
    """Refuse a title YouTube would reject or that cannot identify a post, before anything opens."""
    if len(title) > S.TITLE_MAX:
        raise TitleTooLong(
            f"title is {len(title)} characters; YouTube allows {S.TITLE_MAX}. Refusing to "
            f"truncate it — the title is Stephen's approved copy, so fix it in the meta file: "
            f"{title!r}")
    if len(_norm(title)) < MIN_TITLE_LEN:
        raise TitleTooLong(
            f"title {title!r} is too short to identify a video ({len(_norm(title))} < "
            f"{MIN_TITLE_LEN} characters); it could not be skipped safely on a re-run")


def title_matches(row: dict, title: str) -> bool:
    """Is this content-list row the video `title` names?

    Equality, not a prefix test. The row's `#video-title` was read at full length live on
    2026-09-25, so equality is the honest comparison and it cannot confuse two ParkSheet days
    whose titles share the "Hidden Detail Monday — " prefix.

    A row YouTube itself marked as cut off with an ellipsis is NOT a match — not even when the
    target title starts with it. Prefix-matching a truncated row is the substring hole it looks
    like: two ParkSheet days open "Hidden Detail Monday — ", so a row truncated inside that
    prefix would stand in for either. A truncated row that COULD be this title is instead an
    ambiguous read, and `refuse_if_ambiguous` stops the run rather than answering it wrongly in
    one direction or the other.
    """
    want = _norm(title)
    if len(want) < MIN_TITLE_LEN:
        return False
    return any(c == want and not is_truncated(c) for c in row_titles(row))


def is_truncated(candidate: str) -> bool:
    """Did YouTube cut this string off? (It carries a trailing ellipsis.)"""
    return str(candidate or "").endswith(ELLIPSIS)


def could_be_truncated_title(row: dict, title: str) -> bool:
    """Is any string in `row` a truncated version of `title`?

    Deliberately generous about what counts: the point is to notice that the list CANNOT answer
    "is this day already up", so a near miss must count as ambiguous rather than be argued away.
    """
    want = _norm(title)
    for candidate in row_titles(row):
        if not is_truncated(candidate):
            continue
        stem = candidate.rstrip("….").strip()
        if len(stem) >= MIN_TITLE_LEN and want.startswith(stem):
            return True
    return False


def refuse_if_ambiguous(rows, title: str) -> None:
    """Stop when a row is truncated in a way that might be `title`.

    Both answers are wrong when the list will not show a full title: reporting "already
    published" skips a day that may never have gone up, and reporting "not there" uploads a
    video that may already be live. Live on 2026-09-25 the rows carried their titles whole
    (86 characters, untruncated), so this should never fire — which is exactly why it must be
    loud if it ever does.
    """
    for row in rows or ():
        if could_be_truncated_title(row, title):
            raise AmbiguousList(
                f"the content list shows a truncated title that could be {title!r} "
                f"(the row reads {row.get('title')!r}). Refusing to decide whether this day is "
                f"already published from a title YouTube cut off: skipping would drop the day "
                f"and uploading would risk a second copy. Look at {S.CONTENT_URL} by hand.")


def row_titles(row: dict) -> tuple[str, ...]:
    """Every string in a row that could be its title, normalised, best guess first.

    `title` is the `#video-title` node and is what matches in practice. The row's other lines
    are offered as well because a row is a duration badge, a title, a description snippet, a
    visibility word, a date and three counters, and which of those innerText puts where is
    YouTube's decision rather than ours. A candidate still has to EQUAL the target title, so
    offering more of them loosens nothing.
    """
    out = [row.get("title") or ""]
    out += [str(x) for x in (row.get("lines") or [])]
    seen, ordered = set(), []
    for candidate in (_norm(x) for x in out):
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return tuple(ordered)


def find_video(rows, title: str):
    return next((r for r in rows if title_matches(r, title)), None)


def is_public(row: dict) -> bool:
    return _norm(row.get("visibility")) == _norm(S.PUBLIC_VISIBILITY_TEXT)


def is_draft(row: dict) -> bool:
    """True for a row that is NOT published — "Draft", or the transitional "Pending".

    Both words, because a row that has just been closed out of the uploader reads "Pending"
    for a minute or two before it settles to "Draft" (caught live 2026-09-25, when a dry run
    read "Pending" and refused to clean up after itself). Treating only "Draft" as a draft is
    what left a video on the channel that the run had promised to remove.
    """
    return _norm(row.get("visibility")) in {_norm(t) for t in S.DRAFT_VISIBILITY_TEXTS}


def video_id_from(text) -> str | None:
    """The 11-character video id out of any YouTube link in `text`, or None.

    Read from the uploader's own "Video link https://youtube.com/shorts/<id>" line rather than
    from a markup node, so it survives a relayout — and it is there from the moment the upload
    lands, which is why the id can be captured BEFORE the Publish click and still be reported
    when the confirmation afterwards is what fails.
    """
    m = re.search(S.VIDEO_LINK_RE, str(text or ""))
    return m.group(1) if m else None


def watch_url(video_id) -> str:
    return S.WATCH_URL.format(video_id=video_id) if video_id else S.CONTENT_URL


def check_rows_sane(payload):
    """Unwrap {count, rows}, or refuse when the row selector matched rows that carry no title.

    `count` is what the row selector matched; `rows` is the subset that had text. The two are
    reported separately for one reason: a page of skeletons reads as "the channel has no
    videos", which uploads a duplicate of everything. count > 0 with rows empty is therefore
    the ambiguous case, and it fails closed.
    """
    if isinstance(payload, dict):
        count, rows = int(payload.get("count") or 0), list(payload.get("rows") or [])
    else:                       # a bare list: every element carried text by construction
        rows = list(payload or [])
        count = len(rows)
    rows = [r for r in rows if _norm(r.get("title")) or _norm(r.get("text"))]
    if count and not rows:
        raise ScrapeError(
            f"the Studio content list matched {count} row(s) but not one of them carried any "
            f"text, so no existing video can be recognised. Either the list markup changed "
            f"(fix selectors_youtube.VIDEO_ROW / ROW_TITLE) or the read raced the render. "
            f"Refusing to continue, because treating this as 'nothing is posted' would upload "
            f"a duplicate of the video.")
    return rows


def rows_js() -> str:
    """JS: {count, rows} — what the row selector matched, and the ones carrying text.

    Both numbers, never just the survivors: `check_rows_sane` needs to know that rows existed
    but read empty, which is the difference between "the channel is empty" and "the markup
    moved". Filtering first would make that guard unreachable.

    Built by concatenating repr()d constants rather than an f-string — the 2026-09-14 Gumroad
    outage was an f-string segment spliced onto a plain one, where `}}` stayed two literal
    braces. Every selector is resolved inside a try so that one selector the browser will not
    parse cannot throw the whole read away; an exception here would read to the caller as
    "the list would not load".
    """
    return ("() => { let els = [];"
            " try { els = [...document.querySelectorAll(" + repr(S.VIDEO_ROW) + ")]; }"
            " catch (e) { els = []; }"
            " const rows = els.map(r => {"
            " let t = null, a = null, v = null;"
            " try { t = r.querySelector(" + repr(S.ROW_TITLE) + "); } catch (e) {}"
            " try { a = r.querySelector(" + repr(S.ROW_LINK) + "); } catch (e) {}"
            " try { v = r.querySelector(" + repr(S.ROW_VISIBILITY) + "); } catch (e) {}"
            " const text = (r.innerText || '');"
            " const lines = text.split('\\n').map(x => x.trim()).filter(Boolean)"
            ".slice(0, " + repr(S.ROW_MAX_LINES) + ");"
            " return {title: (t ? t.textContent.trim() : ''),"
            " visibility: (v ? (v.innerText || '').trim() : ''),"
            " href: (a ? a.getAttribute('href') : ''),"
            " lines: lines,"
            " text: text.replace(/\\s+/g, ' ').trim().slice(0, 400)}; })"
            ".filter(r => r.title || r.text);"
            " return {count: els.length, rows: rows}; }")


def rows_ready_js() -> str:
    """JS predicate: has the list settled — a row WITH TEXT, or the empty-tab copy?

    This is the distinction that decides whether an upload is safe. "No rows yet" during
    hydration and "this tab has no videos" look identical in a single read, and only one of
    them means it is safe to upload. A bare element count is not the test: a skeleton row
    matches the row selector while the real rows are still loading. When neither condition
    appears the wait times out, which queues a card.
    """
    return ("() => { let els = [];"
            " try { els = [...document.querySelectorAll(" + repr(S.VIDEO_ROW) + ")]; }"
            " catch (e) { els = []; }"
            " for (const r of els) if (((r.innerText || '').trim()).length) return true;"
            " const t = ((document.body && document.body.innerText) || '').toLowerCase();"
            " return t.includes(" + repr(S.CONTENT_EMPTY_TEXT) + "); }")


def enabled_js(selector: str) -> str:
    """JS predicate: `selector` exists and is not aria-disabled.

    Studio's buttons are custom elements, so `is_enabled()` reads the host element rather than
    the `aria-disabled` the app actually sets — which is why the Initial-check wait asks the
    DOM the question the app answers.
    """
    return ("() => { const b = document.querySelector(" + repr(selector) + ");"
            " return !!b && b.getAttribute('aria-disabled') !== 'true'"
            " && !b.hasAttribute('disabled'); }")


def row_present_js(title: str) -> str:
    """JS predicate: a content row whose title equals `title` is on the page right now.

    Needed because navigating back to a tab re-renders the list, and Studio paints the rows it
    already had before it paints a draft that was created seconds ago — so a single read after
    the navigation finds the two published Shorts, calls the list settled, and reports the
    draft as already gone (seen live 2026-09-25, run youtube_web-dry-run-120019, which left
    the draft on the channel).

    The title goes in as a JSON string literal, which is a valid JS one: it survives the em
    dashes and apostrophes ParkSheet titles are full of, where a repr() would not.
    """
    return ("() => { const want = " + json.dumps(_norm(title)) + ";"
            " const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();"
            " let els = [];"
            " try { els = [...document.querySelectorAll(" + repr(S.VIDEO_ROW) + ")]; }"
            " catch (e) { els = []; }"
            " for (const r of els) { let t = null;"
            " try { t = r.querySelector(" + repr(S.ROW_TITLE) + "); } catch (e) {}"
            " if (t && norm(t.textContent) === want) return true; }"
            " return false; }")


def row_absent_js(title: str) -> str:
    """JS predicate: no content row on the page is titled `title` any more.

    The negation is wrapped as `!((fn)())` rather than `!(fn)()`: the latter parses as
    `(!(fn))()`, which calls a boolean.
    """
    return "() => !((" + row_present_js(title) + ")())"


def timed_out(exc) -> bool:
    """True for Playwright's TimeoutError, which is not the builtin one of the same name."""
    return "Timeout" in type(exc).__name__ or "Timeout" in str(exc)


def plan_lines(asset: pathlib.Path, meta: dict) -> list[str]:
    """What a dry run reports. Pure: it reads the meta, never the browser."""
    title, desc = title_of(meta), description_of(meta)
    return [f"would publish {pathlib.Path(asset).name} to the "
            f"{S.CHANNEL_NAME} channel as a public Short",
            f"title ({len(title)}/{S.TITLE_MAX}): {title}",
            f"description: {len(desc)} characters, "
            f"{len(desc.splitlines())} lines (attribution kept verbatim)",
            # Deliberately not "…key: the exact title": session.redact_secrets treats
            # `key: <word>` as a credential and masked the sentence to "key: ***" in the
            # 12:07 run. The wording is the fix; loosening the redactor is not.
            f"skips if that exact title is already on {S.CONTENT_URL}"]


def manual_steps(asset: pathlib.Path, meta: dict) -> list[str]:
    """The exact remaining manual step, for the queue card (spec Chrome rule 7)."""
    title = title_of(meta)
    return [
        "Run: python3 scripts/browser/ensure_chrome.py",
        f"Open {S.STUDIO_URL} and CHECK THE CHANNEL FIRST — the top-right avatar must be "
        f"'{S.CHANNEL_NAME}', not Stephen's personal channel; switch channels if it is not",
        f"Check {S.CONTENT_URL} before doing anything else: if a video titled below is "
        f"already there, this day is done and nothing should be uploaded",
        f"Otherwise Create -> {S.UPLOAD_MENU_ITEM_TEXT}, and upload this file: "
        f"{pathlib.Path(asset).resolve()}",
        f"Title (paste exactly): {title}",
        "Description (paste exactly from the meta file — it carries the Queue-Times, "
        "ThemeParks.wiki and photo-credit lines that the licences require): "
        f"{pathlib.Path(meta.get('_meta_path') or '(the day-N.json next to the mp4)')}",
        f"Audience: '{S.KIDS_NO_NAME}'",
        f"Next through {', '.join(S.STEP_NAMES[1:])}, set Visibility to Public, then Publish",
        f"If a row with this title is there but reads {S.DRAFT_VISIBILITY_TEXT!r} or "
        f"{S.DRAFT_PENDING_TEXT!r}, that is a half-finished upload from a failed run: either "
        f"finish it or delete it (row menu -> {S.DELETE_MENU_ITEM_TEXT}) before uploading again",
        f"Confirm the video is listed as {S.PUBLIC_VISIBILITY_TEXT} at {S.CONTENT_URL}",
        "DO NOT re-run this publisher for this day until you have looked at that list — the "
        "upload may have gone through after the failure, and a second run would post it twice",
    ]


# ------------------------------------------------------------------------- the --check probes

# What a probe row means (same vocabulary as tiktok_web's canary):
#   LIVE          — must be on the page right now; absent means the anchor drifted, exit 1.
#   POST_FILE     — only exists once YouTube has taken a video, and selecting a file starts a
#                   real upload. Reported as "post-file only", never as a failure.
#   POST_PUBLISH  — only exists once something has actually been published. Same treatment.
#   ROWS          — checkable only once the channel HAS a video on that tab.
LIVE, POST_FILE, POST_PUBLISH, ROWS = "live", "post-file", "post-publish", "rows"


def check_probes() -> tuple[tuple[str, str, str, str, str], ...]:
    """(page url, label, kind, value, stage) for every anchor `--check` resolves, read-only.

    A table rather than code so the canary and the driver cannot disagree about what "the
    anchors resolve" means, and so a new anchor is one row.
    """
    return (
        (S.STUDIO_URL, "channel name", "css", S.CHANNEL_NAME_TEXT, LIVE),
        (S.STUDIO_URL, "avatar menu", "css", S.AVATAR_BUTTON, LIVE),
        (S.CONTENT_SHORTS_URL, "table header", "css", S.CONTENT_PAGE_READY, LIVE),
        (S.CONTENT_SHORTS_URL, "video rows", "css", S.VIDEO_ROW, ROWS),
        (S.CONTENT_SHORTS_URL, "row title", "css", S.ROW_TITLE, ROWS),
        (S.CONTENT_SHORTS_URL, "row visibility", "css", S.ROW_VISIBILITY, ROWS),
        (S.CONTENT_VIDEOS_URL, "empty state", "body", S.CONTENT_EMPTY_TEXT, LIVE),
        (S.UPLOAD_DIALOG_URL, "upload dialog", "css", S.UPLOAD_DIALOG, LIVE),
        (S.UPLOAD_DIALOG_URL, "file input", "css", S.FILE_INPUT, LIVE),
        (S.UPLOAD_DIALOG_URL, "select files", "css", S.SELECT_FILES_BUTTON, LIVE),
        (S.UPLOAD_DIALOG_URL, "dialog close", "css", S.DIALOG_CLOSE_BUTTON, LIVE),
        (S.UPLOAD_DIALOG_URL, "title box", "css", S.TITLE_BOX, POST_FILE),
        (S.UPLOAD_DIALOG_URL, "description box", "css", S.DESCRIPTION_BOX, POST_FILE),
        (S.UPLOAD_DIALOG_URL, "kids radio", "role-radio", S.KIDS_NO_NAME, POST_FILE),
        (S.UPLOAD_DIALOG_URL, "next button", "css", S.NEXT_BUTTON, POST_FILE),
        (S.UPLOAD_DIALOG_URL, "publish button", "css", S.DONE_BUTTON, POST_FILE),
        (S.UPLOAD_DIALOG_URL, "public radio", "css", S.PUBLIC_RADIO, POST_FILE),
        (S.UPLOAD_DIALOG_URL, "anyone-can-see", "role", S.GOT_IT_BUTTON_TEXT, POST_PUBLISH),
    )


# The anchor each page is waited on before anything is counted. Without it the probe races the
# render and reports a slow page as drift, which is how a canary stops being read.
PAGE_READY = {
    S.STUDIO_URL: S.STUDIO_PAGE_READY,
    # The column header, never the row selector: an empty tab has no rows, and waiting on one
    # would report "this channel has no Shorts" as "the page never loaded".
    S.CONTENT_SHORTS_URL: S.CONTENT_PAGE_READY,
    S.CONTENT_VIDEOS_URL: S.CONTENT_PAGE_READY,
    S.UPLOAD_DIALOG_URL: S.UPLOAD_PAGE_READY,
}


def _resolve(page, kind: str, value: str):
    """A locator for one probe row. Resolving only — nothing here clicks or types."""
    if kind == "css":
        return page.locator(value)
    if kind == "role":
        # exact=True is load-bearing. Playwright matches an accessible name as a
        # case-insensitive SUBSTRING by default, which is how tiktok_web's canary once
        # reported a Post button on a page that had none.
        return page.get_by_role("button", name=value, exact=True)
    if kind == "role-radio":
        return page.get_by_role("radio", name=value, exact=True)
    return page.get_by_text(value, exact=True)


def _probe_count(page, kind: str, value: str) -> int:
    """How many times one probe row resolves. Read-only by construction."""
    if kind == "body":
        # The empty-tab copy is stored lowercased because that is how rows_ready_js tests it,
        # and get_by_text(exact=True) is case-SENSITIVE — probing it as a locator would report
        # the live "No content available" as missing. Same test as the driver makes.
        return ((page.inner_text("body") or "").lower()).count(value)
    return _resolve(page, kind, value).count()


# --------------------------------------------------------------------------- the publisher

class YouTubeWebPublisher(Publisher):
    """YouTube Studio's web uploader, driven in the logged-in debug Chrome."""

    platform = PLATFORM
    # There is no way to rehearse a web uploader without handing it a file, so this dry run
    # really uploads and then deletes the draft. publish.py reads this and refuses --dry-run
    # for this platform, because its own contract is that --dry-run writes nothing.
    dry_run_writes = True

    def __init__(self, *, repo: pathlib.Path | None = None, check_fn=None) -> None:
        super().__init__(repo=repo if repo is not None else REPO)
        self._check_fn = check_fn or (lambda: session.check(SITE))
        self._status = None
        # The page currently being driven, so queue() can put a screenshot on the card.
        self._page = None
        # True once Publish has been clicked for the attempt in flight. Reset per _do_publish
        # call; while set, nothing is retried (see _do_publish).
        self._submitted = False
        # The video id read out of the uploader, so a failure after the click can still say
        # which video to go and look at.
        self._video_id = None
        # True once a file has been handed to Studio for the attempt in flight. From that
        # moment a draft EXISTS, so "I cannot see one" is a failure to look hard enough, not
        # evidence that nothing was created.
        self._uploaded = False

    # -- contract ---------------------------------------------------------------------

    def capabilities(self) -> dict:
        return {"platform": self.platform,
                "transport": "chrome-debug",
                "cdp_url": session.CDP_URL,
                "channel": S.CHANNEL_NAME,
                "channel_id": S.CHANNEL_ID,
                "scheduling": False,        # Studio offers it; this driver publishes now only
                "title_max": S.TITLE_MAX,
                "studio_url": S.STUDIO_URL,
                "content_url": S.CONTENT_URL,
                "recurring_job": False,     # rule 1: Chrome is never on the recurring path
                "dry_run_uploads": True,    # a dry run really uploads, then deletes the draft
                "unverified": list(S.UNVERIFIED),
                "queue_dir": str(self.queue_dir())}

    def queue_dir(self) -> pathlib.Path:
        """Where this publisher's failure cards and their mp4s land."""
        return self.repo / "marketing" / "publish-queue" / QUEUE_SUBDIR

    def status(self):
        """The login preflight, once per publisher instance.

        Cached because a batch makes one instance and posts several days, and each check is a
        page open. It is not a hole: every navigation inside the driver re-classifies the URL
        it landed on, and the channel guard re-reads the channel name on every run.
        """
        if self._status is None:
            self._status = self._check_fn()
        return self._status

    def preflight(self) -> PublishResult | None:
        status = self.status()
        if status.ok:
            return None
        return PublishResult(
            platform=self.platform, ok=False, url=None, queued_path=None,
            detail=(f"YouTube Studio preflight failed: {status.detail} (requested "
                    f"{status.requested_url}, landed on {status.final_url}). Nothing was "
                    f"uploaded."))

    def publish(self, asset, meta: dict, dry_run: bool) -> PublishResult:
        """Route a dry run into the browser instead of short-circuiting it.

        The base class answers `dry_run` with a sentence and no browser, which is right for a
        transport whose dry run has nothing to learn. Here it would be a lie: the whole point
        of this dry run is to prove the uploader still takes a real file and that the draft it
        leaves can be removed again, and none of that can be known without driving it.
        """
        asset = pathlib.Path(asset)
        if not asset.exists():
            raise FileNotFoundError(f"asset not found: {asset}")
        if not dry_run:
            return super().publish(asset, meta, dry_run)
        blocked = self.preflight()
        if blocked is not None:
            return dataclasses.replace(blocked, detail="dry-run REFUSED: " + blocked.detail)
        try:
            check_title(title_of(meta))
        except TitleTooLong as exc:
            return PublishResult(platform=self.platform, ok=False, url=None, queued_path=None,
                                 detail=f"dry-run REFUSED: {exc}")
        try:
            return self._do_dry_run(asset, meta)
        except DraftNotRemoved as exc:
            # The channel HAS changed: a draft is sitting on it. That is a card, always.
            return self.queue(asset, meta, f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 — queues, not silent failures
            return self.queue(asset, meta, f"dry-run: {type(exc).__name__}: {exc}")

    def queue(self, asset: pathlib.Path, meta: dict, detail: str) -> PublishResult:
        """One card per failure, written by session.fail_card so redaction happens once.

        Deliberately not the base class's paste-ready card: what is needed here is a screenshot
        plus the numbered steps to finish the job by hand, and two cards for one failure is how
        a queue stops being read. The mp4 still lands beside the card.
        """
        detail = self.mask(detail)
        asset = pathlib.Path(asset)
        card = session.fail_card(
            self.repo, self._page, subdir=QUEUE_SUBDIR,
            kind=self.platform, slug=base.card_slug(meta, asset), run_name=self.platform,
            title=f"Publish {asset.name} to the {S.CHANNEL_NAME} channel by hand",
            detail=detail,
            steps=manual_steps(asset, meta))
        base.link_or_copy(asset, card.parent / asset.name)
        return PublishResult(platform=self.platform, ok=False, url=None,
                             queued_path=str(card.relative_to(self.repo)), detail=detail)

    # -- live publish -----------------------------------------------------------------

    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        """Open one traced page and drive it, with one retry (spec Chrome rule 7).

        **The Publish click is the point of no return.** Everything that confirms the post
        happens after it, so a generic retry would re-run drive(), find the content list not
        yet updated — YouTube processes an upload asynchronously — and upload the video a
        second time. `self._submitted` is set immediately before the click and nothing is
        retried once it is set. The flag is reset here, not in __init__, because a batch
        reuses one publisher and day 2 must start clean.
        """
        self._submitted = False
        self._video_id = None
        self._uploaded = False
        with session.open_page(self.platform, repo=self.repo) as page:
            self._page = page
            try:
                return self.drive(page, asset, meta)
            except (VerificationFailed, WrongChannel, TitleTooLong, FormFieldError,
                    RowNotPublished, AmbiguousList):
                # VerificationFailed: may already be live, see above. WrongChannel is never
                # worked around. The rest are deterministic — a title YouTube will not take, a
                # form that will not accept its value, a row that is on the list but not public
                # (DraftInTheWay among them, since it is a RowNotPublished) and a truncated list
                # all fail the same way twice, so a retry only doubles the time to the card.
                raise
            except Exception as exc:  # noqa: BLE001 — one retry, then base.publish queues
                if self._submitted:
                    raise VerificationFailed(
                        f"{type(exc).__name__}: {exc} — this happened AFTER Publish was "
                        f"clicked, so YouTube may have taken the video"
                        + (f" ({watch_url(self._video_id)})" if self._video_id else "")
                        + f". NOT retrying: a second attempt would upload "
                          f"{pathlib.Path(asset).name} twice.") from exc
                if self._uploaded:
                    # The file is already with YouTube even though Publish was never clicked —
                    # a timeout in set_public lands here. Re-running drive() from the top would
                    # navigate away, which SILENTLY saves the half-filled upload as a draft,
                    # and then upload the same mp4 a second time; the content read cannot catch
                    # that, because a draft is not a published row. So this is a card, and the
                    # card has to say the draft is there, or nobody will know to delete it.
                    raise DraftNotRemoved(
                        f"{type(exc).__name__}: {exc} — this happened AFTER "
                        f"{pathlib.Path(asset).name} was handed to YouTube but BEFORE Publish "
                        f"was clicked, so a draft titled {title_of(meta)!r} exists on the "
                        f"channel"
                        + (f" (video id {self._video_id})" if self._video_id else "")
                        + f". NOT retrying: a retry would leave that draft behind and upload "
                          f"the file again. Delete the draft at {S.CONTENT_URL} "
                          f"(row menu -> {S.DELETE_MENU_ITEM_TEXT}) before running this day "
                          f"again.") from exc
                print(f"{self.platform}: retrying once after "
                      f"{session.redact_secrets(f'{type(exc).__name__}: {exc}')[:160]}",
                      file=sys.stderr)
                return self.drive(page, asset, meta)

    def drive(self, page, asset: pathlib.Path, meta: dict) -> PublishResult:
        """channel guard → read → skip-if-present → upload → re-read → assert Public."""
        title = title_of(meta)
        check_title(title)
        self.assert_channel(page)

        rows = self.read_content(page)
        refuse_if_ambiguous(rows, title)
        hit = find_video(rows, title)
        if hit is not None:
            self.refuse_unless_public(hit, title)
            return PublishResult(
                platform=self.platform, ok=True,
                url=self.row_url(hit), queued_path=None,
                detail=(f"already published — a video titled {title!r} is on "
                        f"{S.CONTENT_URL} ({hit.get('visibility') or 'visibility unknown'}); "
                        f"nothing uploaded"))

        self.upload(page, asset, meta)
        self.set_public(page)
        self.submit(page)

        # Give the row time to appear before reading the list, exactly as the draft clean-up
        # does. Without it the verification races YouTube's own list refresh: the read lands
        # before the new row is painted, finds nothing, and reports a VerificationFailed over a
        # video that IS live — which is a card telling Stephen to check a channel that is fine,
        # and (worse) the one failure this driver will not retry.
        self.wait_for_row(page, title)
        hit = find_video(self.read_content(page), title)
        if not hit:
            raise VerificationFailed(
                f"published {pathlib.Path(asset).name} but no row titled {title!r} appeared "
                f"on {S.CONTENT_URL}"
                + (f" (the uploader reported {watch_url(self._video_id)})"
                   if self._video_id else "")
                + ". NOT retrying: it may have gone through. Check the content list by hand "
                  "before running this day again.")
        if not is_public(hit):
            raise VerificationFailed(
                f"published {pathlib.Path(asset).name} and the row is on {S.CONTENT_URL}, but "
                f"its visibility reads {hit.get('visibility')!r} rather than "
                f"{S.PUBLIC_VISIBILITY_TEXT!r}. NOT retrying: the video IS on the channel. "
                f"Set it public by hand at {self.row_url(hit)}.")
        return PublishResult(
            platform=self.platform, ok=True, url=self.row_url(hit), queued_path=None,
            detail=(f"published {pathlib.Path(asset).name} to {S.CHANNEL_NAME} as "
                    f"{S.PUBLIC_VISIBILITY_TEXT}: {title}"))

    # -- dry run ----------------------------------------------------------------------

    def _do_dry_run(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        """Everything a live run does except the Publish click, then delete the draft.

        The upload is real, so the clean-up is not optional: the `finally` runs whatever went
        wrong, and a clean-up that itself fails raises DraftNotRemoved so the card names the
        draft rather than reporting a tidy dry run over an untidy channel.
        """
        title = title_of(meta)
        reached: list[str] = []
        self._uploaded = False
        with session.open_page(f"{self.platform}-dry-run", repo=self.repo) as page:
            self._page = page
            self.assert_channel(page)
            reached.append(f"channel confirmed: {S.CHANNEL_NAME}")
            before = self.read_content(page)
            reached.append(f"content list read: {len(before)} row(s)")
            refuse_if_ambiguous(before, title)
            hit = find_video(before, title)
            if hit is not None:
                self.refuse_unless_public(hit, title)
                return PublishResult(
                    platform=self.platform, ok=True, url=self.row_url(hit), queued_path=None,
                    detail=(f"dry-run: already published — a video titled {title!r} is on "
                            f"{S.CONTENT_URL}; a live run would upload nothing"))
            # Not try/finally: a `finally` that raises REPLACES the exception on its way out,
            # so a clean-up failure used to hide the reason the run failed in the first place —
            # and the reason is what a reader of the card needs. The clean-up still always runs.
            primary = None
            try:
                self.upload(page, asset, meta)
                reached.append(f"uploaded {asset.name}, title and description verified, "
                               f"audience set to {S.KIDS_NO_NAME!r}")
                reached.append("walked " + " -> ".join(S.STEP_NAMES))
                self.set_public(page)
                reached.append(f"visibility set to {S.PUBLIC_VISIBILITY_TEXT} "
                               f"(Publish NOT clicked)")
                if self._video_id:
                    reached.append(f"draft video id {self._video_id}")
            except Exception as exc:  # noqa: BLE001 — re-raised below, after the clean-up
                primary = exc
            try:
                reached.append(self.discard_draft(page, title, before))
            except Exception as cleanup:  # noqa: BLE001
                if primary is None:
                    raise
                raise DraftNotRemoved(
                    f"{type(cleanup).__name__}: {cleanup} — AND the run had already failed "
                    f"with {type(primary).__name__}: {primary}, which is the cause to fix "
                    f"first.") from primary
            if primary is not None:
                raise primary
        return PublishResult(
            platform=self.platform, ok=True, url=None, queued_path=None,
            detail="dry-run: " + "; ".join(plan_lines(asset, meta) + reached))

    # -- the driver -------------------------------------------------------------------

    def goto(self, page, url: str) -> None:
        """Navigate, then prove we are still the logged-in studio ON THE RIGHT CHANNEL.

        `assert_channel` runs once at the top of a run, which is not the same as being on
        ParkSheet for the rest of it. Every URL this driver builds carries the channel id
        (`selectors_youtube.channel_url`), so whenever the REQUESTED url names the channel the
        landed one has to name it too. Studio bouncing a request to a different channel — which
        is what it does when the profile's active channel is switched mid-session, in a window
        Stephen also uses by hand — would otherwise put the uploader in front of his personal
        channel with only the first check's word that it was ParkSheet.
        """
        page.goto(url, wait_until="domcontentloaded", timeout=S.NAV_TIMEOUT_MS)
        page.wait_for_load_state("domcontentloaded")
        status = session.classify(SITE, url, page.url)
        if not status.ok:
            raise SessionLost(f"{status.detail} (requested {url}, landed on {status.final_url})")
        if S.CHANNEL_ID in url and S.CHANNEL_ID not in (page.url or ""):
            raise WrongChannel(
                f"requested {url}, which names the {S.CHANNEL_NAME} channel "
                f"{S.CHANNEL_ID}, and landed on {page.url!r}, which does not. Studio has moved "
                f"this session to another channel — refusing to go on, because this profile "
                f"also holds Stephen's personal channel and a Short posted there cannot be "
                f"moved.")

    def assert_channel(self, page) -> str:
        """Refuse to do anything unless Studio is signed in as ParkSheet.

        Two independent tests, because either alone has a way of being wrong: the channel id in
        the URL Studio redirects to (exact, but a deep link could carry a stale one) and the
        header's own channel name (what a person reads, but a substring of another channel's
        name would slip through, so it is compared normalised and whole).

        Stephen's personal channel lives in this same Chrome profile and Studio opens whichever
        was last used. Posting a ParkSheet Short there is not undoable, which is why this is a
        hard refusal rather than a warning.
        """
        self.goto(page, S.STUDIO_URL)
        page.locator(S.CHANNEL_NAME_TEXT).first.wait_for(state="visible",
                                                         timeout=S.ANCHOR_TIMEOUT_MS)
        name = (page.locator(S.CHANNEL_NAME_TEXT).first.text_content() or "").strip()
        if _norm(name) != _norm(S.CHANNEL_NAME):
            raise WrongChannel(
                f"YouTube Studio is signed in as {name!r}, not {S.CHANNEL_NAME!r}. Refusing to "
                f"upload: this Chrome profile also holds Stephen's personal channel, and a "
                f"ParkSheet Short posted there cannot be moved. Switch channels in Studio "
                f"(avatar -> Switch account) and run this again.")
        if S.CHANNEL_ID not in (page.url or ""):
            raise WrongChannel(
                f"the Studio header reads {name!r} but the URL is {page.url!r}, which does not "
                f"carry the ParkSheet channel id {S.CHANNEL_ID}. Refusing to upload against a "
                f"channel the two tests disagree about.")
        return name

    def refuse_unless_public(self, row: dict, title: str) -> None:
        """Let the skip through ONLY for a row that reads Public. Everything else raises.

        The skip is the one place this driver says "do nothing and report success", so it has
        to be a closed door rather than an open one. `is_draft` used to be the only thing that
        could stop it, which meant a Private row, an Unlisted one, a Scheduled one, or a
        visibility cell that read "" because ROW_VISIBILITY had drifted ALL came back as
        "already published" — and the day would be skipped for ever, with nothing on the
        channel and nothing anywhere saying so.

        A draft keeps its own message because it has its own fix (finish it or delete it);
        anything else is a state this driver has never seen and will not guess at.
        """
        if is_public(row):
            return
        if is_draft(row):
            raise DraftInTheWay(
                f"a DRAFT titled {title!r} is already on {S.CONTENT_URL} "
                f"(the row reads {row.get('visibility')!r}). That is not a published video, so "
                f"this is not a skip — and uploading again would put two copies of the same title "
                f"on the channel. Either finish that draft by hand or delete it "
                f"(row menu -> {S.DELETE_MENU_ITEM_TEXT}), then run this again.")
        raise RowNotPublished(
            f"a row titled {title!r} is on {S.CONTENT_URL} but its visibility reads "
            f"{row.get('visibility')!r}, not {S.PUBLIC_VISIBILITY_TEXT!r}. Refusing to treat "
            f"that as 'already published': if it is Private, Unlisted or Scheduled the day is "
            f"not actually up, and if the cell is empty then ROW_VISIBILITY has drifted and "
            f"this read cannot be trusted at all. Look at {self.row_url(row)} and either make "
            f"it {S.PUBLIC_VISIBILITY_TEXT} by hand or delete it, then run this again.")

    def read_content(self, page) -> list:
        """Every video Studio lists for this channel, across both content tabs. Read-only.

        **Both tabs, unioned.** A ParkSheet Short lands on the Shorts tab — live on 2026-09-25
        the Videos tab matched zero rows while the Shorts tab held the two published Shorts and
        the draft — but which tab YouTube files an upload under is its classification decision,
        not ours. Reading one tab and finding nothing is exactly how a video that is already up
        gets posted a second time, so both are read and the rows are merged.

        Each row carries the tab it was read from, because the clean-up has to go back to that
        tab to open the row's menu.
        """
        rows: list = []
        for url in S.CONTENT_TABS:
            self.open_tab(page, url)
            for row in check_rows_sane(page.evaluate(rows_js())):
                # Which tab the row came from. Without it the delete would look for the draft
                # on whichever tab happened to be read LAST — which on 2026-09-25 was the
                # empty Videos tab, so the row was "gone" and the draft stayed on the channel.
                row["tab"] = url
                rows.append(row)
        return rows

    def open_tab(self, page, url: str) -> None:
        """Navigate to one content tab and wait for its list to settle.

        Two waits, in this order: the table header (it renders whether or not the tab has
        videos, so it is the honest "the page arrived" signal), then a row with text or the
        empty-tab copy. The second without the first would read a blank page as an empty tab,
        which uploads a duplicate of a video that is already up.
        """
        self.goto(page, url)
        page.locator(S.CONTENT_PAGE_READY).first.wait_for(state="attached",
                                                          timeout=S.ANCHOR_TIMEOUT_MS)
        page.wait_for_function(rows_ready_js(), timeout=S.LIST_TIMEOUT_MS)

    def row_url(self, row: dict) -> str:
        """A link for a row: its own video URL when it has one, else the content list.

        A DRAFT row carries no link at all (verified 2026-09-25), so this must never assume one.
        """
        vid = video_id_from(row.get("href") or "") or _id_from_edit_href(row.get("href"))
        return watch_url(vid) if vid else S.CONTENT_URL

    def upload(self, page, asset: pathlib.Path, meta: dict) -> None:
        """Hand the file to Studio and fill the Details step, then walk to Visibility."""
        title, desc = title_of(meta), description_of(meta)
        self.goto(page, S.UPLOAD_DIALOG_URL)
        self.open_uploader(page)
        # The file input is hidden (Studio drives it from the "Select files" button), so it is
        # waited on ATTACHED, never visible. set_input_files does not need it shown, and this is
        # what keeps the OS file dialog out of the flow entirely.
        page.locator(S.FILE_INPUT).first.wait_for(state="attached",
                                                  timeout=S.ANCHOR_TIMEOUT_MS)
        page.set_input_files(S.FILE_INPUT, str(pathlib.Path(asset).resolve()))
        self._uploaded = True
        # None of the details form exists before this line, and the wait takes the upload-length
        # timeout rather than the anchor one: it covers YouTube ingesting the mp4, not a render.
        page.locator(S.TITLE_BOX).first.wait_for(state="visible", timeout=S.UPLOAD_TIMEOUT_MS)
        self.fill_box(page, S.TITLE_BOX, title, "title")
        self.fill_box(page, S.DESCRIPTION_BOX, desc, "description")
        self.set_audience(page)
        self.next_to_visibility(page)

    def open_uploader(self, page) -> None:
        """Make sure the upload dialog is on screen.

        The `?d=ud` deep link is the same destination as Create -> Upload videos and normally
        opens it on its own. The menu click is kept as the fallback for the day the deep link
        stops working, rather than as the primary path: a menu is two clicks that can each land
        on the wrong item, and the deep link is one navigation that cannot.
        """
        dialog = page.locator(S.UPLOAD_DIALOG)
        if dialog.count():
            return
        upload = page.get_by_role("button", name=S.UPLOAD_MENU_ITEM_TEXT, exact=True)
        if upload.count():
            upload.first.click()
        else:
            page.get_by_role("button", name=S.CREATE_BUTTON_NAME, exact=True).first.click()
            page.get_by_text(S.UPLOAD_MENU_ITEM_TEXT, exact=True).first.click()
        page.locator(S.UPLOAD_DIALOG).first.wait_for(state="attached",
                                                     timeout=S.ANCHOR_TIMEOUT_MS)

    def fill_box(self, page, selector: str, text: str, what: str) -> None:
        """Clear a Studio contenteditable and insert `text`, then read it back.

        Three decisions, each of which was the difference between working and not:

        * **The click is allowed to fail.** The form re-renders continuously while YouTube
          processes the upload, so Playwright's actionability check can never call the box
          "stable". Keyboard focus needs no stability and the editor takes input the same way
          after either — the same fallback tiktok_web needs for the Draft.js caption box.
        * **insert_text, not type.** `keyboard.type` replays a key event per character, and in a
          contenteditable a newline becomes Enter — which a 681-character description with nine
          line breaks does not survive intact. `insert_text` reproduced it exactly (verified
          2026-09-25 by reading both boxes back).
        * **The read-back is an assertion, not a log line, and it is EXACT.** A description
          that silently lost its attribution lines would breach the Queue-Times and photo-credit
          licences, and the only place that can be caught is here, before Publish. The compare
          is line-for-line after CRLF normalisation — not `_norm`, which collapses runs of
          whitespace and therefore waved through a description whose newlines had all gone.
        """
        box = page.locator(selector).first
        box.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)
        try:
            box.click(timeout=S.BOX_CLICK_TIMEOUT_MS)
        except Exception as exc:  # playwright's TimeoutError is not the builtin one
            if not timed_out(exc):
                raise
            box.focus()
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(text)
        got, want = _lines(box.inner_text()), _lines(text)
        if got != want:
            anchor = "TITLE_BOX" if what == "title" else "DESCRIPTION_BOX"
            # `_norm` is only ever used to describe the difference, never to judge it: it
            # collapses runs of whitespace, so comparing with it passed a description that had
            # LOST every one of its line breaks — which for this field means the attribution
            # block arrives as one paragraph and the credit lines stop being legible credits.
            same_words = _norm(got) == _norm(want)
            raise FormFieldError(
                f"the {what} box would not take its value: it reads {len(got)} characters on "
                f"{len(got.splitlines())} line(s), expected {len(want)} on "
                f"{len(want.splitlines())}"
                + (" — the text is there but the LINE BREAKS were lost, which for the "
                   "description means the licence-required credit lines run together"
                   if same_words else "")
                + f". YouTube's editor markup has changed — fix selectors_youtube.{anchor}.")

    def set_audience(self, page) -> None:
        """Answer "Is this video made for kids?" with No.

        Not optional and not skippable: until it is answered the form shows "You need to answer
        this question" and Next silently does not advance — a 2026-09-25 run clicked Next three
        times and never left the Details step because of exactly this, which is why the driver
        asserts the warning is gone rather than trusting the click.

        ParkSheet is theme-park data commentary for adults planning trips, not children's
        content, so No is the correct answer as well as the one that keeps comments on.
        """
        radio = page.get_by_role("radio", name=S.KIDS_NO_NAME, exact=True)
        if not radio.count():
            raise FormFieldError(
                f"the {S.KIDS_NO_NAME!r} radio is not on the Details step; YouTube's audience "
                f"question has changed — fix selectors_youtube.KIDS_NO_NAME.")
        if not radio.first.is_checked():
            radio.first.click()
        page.locator(f"text={S.KIDS_UNANSWERED_TEXT}").first.wait_for(
            state="hidden", timeout=S.ANCHOR_TIMEOUT_MS)

    def next_to_visibility(self, page) -> None:
        """Details -> Video elements -> Initial check -> Visibility, asserting each arrival.

        The step badge's `aria-selected` is the condition; clicking Next three times and
        assuming is what the unanswered-audience bug hid behind. The Initial-check step also
        gets its own wait for Next to stop being aria-disabled, which is YouTube's copyright
        scan finishing — the one step that can take minutes rather than a render.
        """
        for step in (S.STEP_ELEMENTS, S.STEP_CHECKS, S.STEP_VISIBILITY):
            timeout = S.CHECKS_TIMEOUT_MS if step == S.STEP_VISIBILITY else S.ANCHOR_TIMEOUT_MS
            page.wait_for_function(enabled_js(S.NEXT_BUTTON), timeout=timeout)
            page.locator(S.NEXT_BUTTON).first.click()
            try:
                page.locator(S.step_selected(step)).first.wait_for(
                    state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
            except Exception as exc:  # playwright's TimeoutError is not the builtin one
                if not timed_out(exc):
                    raise
                raise FormFieldError(
                    f"the uploader would not advance to the {S.STEP_NAMES[step]!r} step. If "
                    f"the form is showing a question the driver does not answer, it stops "
                    f"here rather than clicking past it.") from exc

    def set_public(self, page) -> None:
        """Select Public on the Visibility step and answer the one-time notice.

        The radio is resolved by its own `name="PUBLIC"` attribute, never by the word "Public":
        that word also appears in the explanatory sentence beside it and in the Schedule block
        below it.

        The force-click is the fallback rather than the default. YouTube's "Remember that
        anyone can see what you post" notice puts a backdrop over the dialog, and a normal
        click on an element behind it times out — the same notice that swallows a new channel's
        first comment in scripts/browser/youtube_pin_comment.py. A forced click skips the
        actionability check; the radio's own checked state is then read back, so nothing rests
        on the click having been delivered.
        """
        page.locator(S.step_selected(S.STEP_VISIBILITY)).first.wait_for(
            state="attached", timeout=S.CHECKS_TIMEOUT_MS)
        radio = page.locator(S.PUBLIC_RADIO).first
        radio.wait_for(state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
        try:
            radio.click(timeout=S.BOX_CLICK_TIMEOUT_MS)
        except Exception as exc:  # playwright's TimeoutError is not the builtin one
            if not timed_out(exc):
                raise
            radio.click(force=True)
        self.dismiss_notice(page)
        # Capture the id now, not after Publish: the uploader carries "Video link
        # https://youtube.com/shorts/<id>" from the moment the upload lands, and a failure
        # AFTER the click still has to be able to say which video to go and look at.
        self._video_id = video_id_from(page.locator(S.UPLOAD_DIALOG).first.inner_text())

    def dismiss_notice(self, page) -> None:
        """Click "Got it" on YouTube's one-time notice when it appears. Absence is not an error.

        It is shown once per channel, so most runs never see it — which is exactly why it must
        not be waited on as though it were required, and exactly why it cannot be left out: the
        run that does see it would otherwise fail on a backdrop it could have dismissed.
        """
        button = page.get_by_role("button", name=S.GOT_IT_BUTTON_TEXT, exact=True)
        try:
            button.first.wait_for(state="visible", timeout=S.NOTICE_TIMEOUT_MS)
        except Exception as exc:  # playwright's TimeoutError is not the builtin one
            if timed_out(exc):
                return
            raise
        button.first.click()

    def submit(self, page) -> None:
        """Click Publish. Everything after this line is a card, never a retry.

        `self._submitted` is set immediately BEFORE the click, not after: the click itself can
        raise once the request is already on the wire, and a retry from there would upload the
        video a second time.

        The wait afterwards is deliberately forgiving. Studio replaces the uploader with a share
        dialog on success, but that dialog is the one part of this flow that has never been seen
        (a dry run stops before the click), so a timeout here is not treated as failure — the
        content-list re-read in drive() is the confirmation that counts, and it is the one that
        can tell "published" from "published as the wrong visibility".
        """
        button = page.locator(S.DONE_BUTTON).first
        button.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)
        page.wait_for_function(enabled_js(S.DONE_BUTTON), timeout=S.ANCHOR_TIMEOUT_MS)
        self._submitted = True          # point of no return — never re-upload past here
        button.click()
        try:
            page.locator(S.UPLOAD_DIALOG).first.wait_for(state="detached",
                                                         timeout=S.UPLOAD_TIMEOUT_MS)
        except Exception as exc:  # playwright's TimeoutError is not the builtin one
            if not timed_out(exc):
                raise

    # -- the dry run's clean-up -------------------------------------------------------

    def discard_draft(self, page, title: str, before: list) -> str:
        """Close the uploader and delete the draft it leaves, then prove the list is unchanged.

        There is no discard inside the uploader: closing it just says "Your video <title> has
        been saved as draft" (verified 2026-09-25). So the draft is removed the way a person
        removes one — row menu -> Delete forever -> tick the acknowledgement -> "Delete draft
        video" — and two guards keep that from ever touching a published video:

          1. the row must read {DRAFT}, not {PUBLIC}, and
          2. the confirmation button must read "Delete draft video"; YouTube words it
             differently for a published video, and a different word means stop.

        Returns a one-line description for the dry-run report; raises DraftNotRemoved if the
        channel is not back to exactly the rows it started with.
        """
        close = page.locator(S.DIALOG_CLOSE_BUTTON)
        if close.count():
            close.first.click()
        self.wait_for_draft(page, title)
        rows = self.read_content(page)
        row = find_video(rows, title)
        if row is None:
            if self._uploaded:
                raise DraftNotRemoved(
                    f"a file was handed to Studio, so a draft titled {title!r} exists, but no "
                    f"row with that title is on either content tab. It may still be rendering. "
                    f"Check {S.CONTENT_URL} by hand and delete it before running this again.")
            if len(rows) == len(before):
                return ("no draft was left behind (the uploader was closed before YouTube "
                        "created one); content list unchanged")
            raise DraftNotRemoved(
                f"the content list has {len(rows)} row(s) where it had {len(before)} before "
                f"the dry run, but no row is titled {title!r} — something was left on the "
                f"channel that this driver cannot name. Check {S.CONTENT_URL} by hand.")
        if not is_draft(row):
            raise DraftNotRemoved(
                f"the row titled {title!r} reads {row.get('visibility')!r}, which is none of "
                f"{S.DRAFT_VISIBILITY_TEXTS}. REFUSING to delete it: a dry run must never "
                f"remove a published video. Check {S.CONTENT_URL} by hand.")
        self.delete_row(page, title, row.get("tab") or S.CONTENT_URL)
        after = self.read_content(page)
        if find_video(after, title):
            raise DraftNotRemoved(
                f"the draft titled {title!r} is still on {S.CONTENT_URL} after the delete was "
                f"confirmed. Delete it by hand before running anything else for this day.")
        if len(after) != len(before):
            raise DraftNotRemoved(
                f"the draft was deleted but the content list now has {len(after)} row(s) where "
                f"it had {len(before)}. Check {S.CONTENT_URL} by hand.")
        return (f"draft deleted; content list back to {len(after)} row(s), "
                f"unchanged from before the run")

    def wait_for_draft(self, page, title: str) -> None:
        """Give the draft time to appear, before the clean-up reads the list.

        Only when a file was actually handed over: otherwise there is no draft to wait for and
        this would burn the list timeout on every clean run.
        """
        if self._uploaded:
            self.wait_for_row(page, title)

    def wait_for_row(self, page, title: str) -> None:
        """Wait for a row titled `title` on the tab a Short lands on. A timeout is tolerated.

        Tolerated on purpose: the full two-tab read that follows is what decides, and it can
        still find the row on the other tab. This only removes the race — it never supplies the
        answer, so failing it must not fail the run.
        """
        try:
            self.open_tab(page, S.CONTENT_URL)
            page.wait_for_function(row_present_js(title), timeout=S.LIST_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            if not timed_out(exc):
                raise

    def delete_row(self, page, title: str, tab: str) -> None:
        """Row menu -> Delete forever -> acknowledge -> confirm, for the row titled `title`.

        `tab` is where the row was actually seen, and navigating to it first is not optional:
        the list read visits both content tabs, so the page is left standing on the LAST one —
        the empty Videos tab — and looking for the row there reports it as already gone while
        the draft sits on the Shorts tab (seen 2026-09-25, run youtube_web-dry-run-115815).

        The row is located by reading every row's title and matching, rather than by a text
        filter: `filter(has_text=...)` is a substring test, and two ParkSheet days share the
        "Hidden Detail Monday — " prefix, so a filter could open the menu on the wrong row.
        """
        self.open_tab(page, tab)
        page.wait_for_function(row_present_js(title), timeout=S.LIST_TIMEOUT_MS)
        index = self.row_index(page, title)
        row = page.locator(S.VIDEO_ROW).nth(index)
        row.hover()
        row.get_by_role("button", name=S.ROW_OPTIONS_BUTTON_NAME).first.click()
        item = page.locator(S.DELETE_MENU_ITEM).filter(has_text=S.DELETE_MENU_ITEM_TEXT).first
        item.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)
        item.click()
        checkbox = page.locator(S.DELETE_CONFIRM_CHECKBOX).first
        checkbox.wait_for(state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
        # The checkbox is a ytcp-checkbox-lit custom element with no visible box of its own,
        # so the actionability check has nothing to call stable — forced, like the visibility
        # radio. Its effect is then read through the button it unlocks, not assumed.
        checkbox.click(force=True)
        confirm = page.locator(S.DELETE_CONFIRM_BUTTON).first
        confirm.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)
        label = (confirm.inner_text() or "").strip()
        if _norm(label) != _norm(S.DELETE_DRAFT_CONFIRM_TEXT):
            page.locator(S.DELETE_CANCEL_BUTTON).first.click()
            raise DraftNotRemoved(
                f"the delete confirmation reads {label!r}, not "
                f"{S.DELETE_DRAFT_CONFIRM_TEXT!r}. Cancelled without deleting anything: that "
                f"wording is what distinguishes a draft from a published video, and guessing "
                f"is not worth a deleted Short.")
        # **Wait for the checkbox to have unlocked the button, and then click it NORMALLY.**
        # Both halves of that were bugs on 2026-09-25 (run youtube_web-dry-run-120355). The
        # button opens `aria-disabled="true" disabled` and the tick clears it about 200 ms
        # later; a forced click bypasses the actionability check, so clicking straight after
        # the tick did nothing at all — silently, because force is exactly the flag that turns
        # "this button is disabled" from an error into a no-op. The draft stayed on the channel
        # and the run reported a confirmed delete.
        page.wait_for_function(enabled_js(S.DELETE_CONFIRM_BUTTON),
                               timeout=S.ANCHOR_TIMEOUT_MS)
        confirm.click()
        # And wait for the row to actually go, on this page, before anything re-reads the list:
        # the delete is asynchronous, and a re-read that races it reports the draft as still
        # there (which is a card) or, worse on some other path, as gone when it is not.
        page.wait_for_function(row_absent_js(title), timeout=S.LIST_TIMEOUT_MS)

    def row_index(self, page, title: str) -> int:
        """Which `VIDEO_ROW` on the CURRENT page is titled `title`. Raises if none is."""
        rows = check_rows_sane(page.evaluate(rows_js()))
        for i, row in enumerate(rows):
            if title_matches(row, title):
                return i
        raise DraftNotRemoved(
            f"no row titled {title!r} is on {page.url} any more, so its menu cannot be opened. "
            f"Check {S.CONTENT_URL} by hand.")


def _id_from_edit_href(href) -> str | None:
    """The video id out of a content-row href like `/video/<id>/edit`, or None."""
    m = re.search(r"/video/([A-Za-z0-9_-]{11})", str(href or ""))
    return m.group(1) if m else None


# ----------------------------------------------------------------------------- the CLI

def check(page, *, out=None) -> tuple[int, list[str]]:
    """Read-only: is this ParkSheet, and does every anchor still resolve?

    Navigates, waits for each page's own ready anchor, and counts. It never selects a file,
    never types and never clicks anything that changes state: opening the upload dialog creates
    nothing until a file is chosen (verified 2026-09-25 — the content list was unchanged after
    a dialog visit), which is what makes the pre-file anchors honestly checkable.

    Four marks, and only one of them is a failure:
      OK               the anchor is on the page now.
      MISSING          it should be and is not — the selector drifted. Exit 1.
      post-file only   it cannot exist until a video is handed to YouTube.
      post-publish     it cannot exist until something has been published to the channel.
    """
    lines: list[str] = []
    page.goto(S.STUDIO_URL, wait_until="domcontentloaded", timeout=S.NAV_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded")
    status = session.classify(SITE, S.STUDIO_URL, page.url)
    lines.append(f"{'login':<16} {'OK  ' if status.ok else 'FAIL'} {status.detail}")
    if not status.ok:
        return 1, lines
    # The channel guard is a --check result in its own right, and the first one that matters:
    # every other anchor resolving on the wrong channel is worse than none of them resolving.
    try:
        name = (page.locator(S.CHANNEL_NAME_TEXT).first.text_content() or "").strip()
    except Exception as exc:  # noqa: BLE001 — a canary reports, it does not traceback
        lines.append(f"{'channel':<16} FAIL could not read {S.CHANNEL_NAME_TEXT!r} "
                     f"({type(exc).__name__})")
        return 1, lines
    right = _norm(name) == _norm(S.CHANNEL_NAME) and S.CHANNEL_ID in (page.url or "")
    lines.append(f"{'channel':<16} {'OK  ' if right else 'WRONG'} signed in as {name!r} "
                 f"(want {S.CHANNEL_NAME!r}, id {S.CHANNEL_ID} in the URL)")
    if not right:
        return 1, lines

    rc = 0
    current = None
    for url, label, kind, value, stage in check_probes():
        if url != current:
            page.goto(url, wait_until="domcontentloaded", timeout=S.NAV_TIMEOUT_MS)
            page.wait_for_load_state("domcontentloaded")
            current = url
            probe_status = session.classify(SITE, url, page.url)
            if not probe_status.ok:
                lines.append(f"{'navigation':<16} FAIL {probe_status.detail}")
                return 1, lines
            ready = PAGE_READY.get(url)
            if ready:
                try:
                    page.locator(ready).first.wait_for(state="attached",
                                                       timeout=S.ANCHOR_TIMEOUT_MS)
                except Exception as exc:  # noqa: BLE001 — report it, do not traceback
                    lines.append(f"{'page ready':<16} FAIL {ready!r} never appeared on "
                                 f"{url} ({type(exc).__name__})")
                    return 1, lines
        if stage in (POST_FILE, POST_PUBLISH):
            why = ("cannot be resolved without starting an upload" if stage == POST_FILE
                   else "cannot be resolved without publishing a video")
            lines.append(f"{label:<16} n/a  {stage} only — {kind}={value!r} {why}")
            continue
        try:
            found = _probe_count(page, kind, value)
        except Exception as exc:  # noqa: BLE001 — a canary reports, it does not traceback
            found, exc_note = 0, f" ({type(exc).__name__})"
        else:
            exc_note = ""
        if stage == ROWS and not found:
            # No rows on a tab that is showing its empty state is an empty tab, not a drifted
            # selector. No rows and no empty state is the ambiguous read the driver refuses to
            # treat as "nothing is posted", so the canary refuses it too.
            empty = _probe_count(page, "body", S.CONTENT_EMPTY_TEXT)
            if empty:
                lines.append(f"{label:<16} n/a  this tab has no videos — "
                             f"{kind}={value!r} has no row to match")
                continue
            rc |= 1
            lines.append(f"{label:<16} MISSING {kind}={value!r} matched 0 and the tab is not "
                         f"showing its empty state either{exc_note}")
            continue
        mark = "OK  " if found else "MISSING"
        rc |= 0 if found else 1
        lines.append(f"{label:<16} {mark} {kind}={value!r} matched {found}{exc_note}")
    return rc, lines


def main(argv=None, *, repo: pathlib.Path | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Publish a Short to the ParkSheet channel via YouTube Studio in Chrome.")
    ap.add_argument("--check", action="store_true",
                    help="read-only: channel + every anchor resolves; changes nothing")
    ap.add_argument("--dry-run", action="store_true",
                    help="upload for real, fill the form, select Public, then DELETE the "
                         "draft; never clicks Publish")
    ap.add_argument("--go", action="store_true",
                    help="actually publish — the ONLY flag that puts a public video on the "
                         "channel. Without it, a run with --asset/--meta refuses.")
    ap.add_argument("--asset", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    a = ap.parse_args(argv)
    repo = pathlib.Path(repo) if repo is not None else REPO

    if a.check:
        with session.open_page(f"{PLATFORM}-check", repo=repo) as page:
            rc, lines = check(page)
        for line in lines:
            print(session.redact_secrets(line))
        return rc

    if not (a.asset and a.meta):
        ap.error("--asset and --meta are required unless --check is given")
    # tiktok_web's own CLI publishes on a bare invocation, and its `--go` lives one level up in
    # schedule_week.py. There is no such level here, and the consequence is worse: a TikTok
    # mistake is a post scheduled for Saturday that can be deleted before it airs, while this
    # one is a public video on the channel the moment the button lands. So the flag is here.
    if not (a.dry_run or a.go):
        ap.error("refusing to publish without --go. Use --dry-run to rehearse (it uploads for "
                 "real and then deletes the draft), or --go to actually publish.")
    if a.dry_run and a.go:
        ap.error("--dry-run and --go contradict each other; pick one")
    meta = json.loads(a.meta.read_text(encoding="utf-8"))
    meta.setdefault("_meta_path", str(a.meta))
    pub = YouTubeWebPublisher(repo=repo)
    result = pub.publish(a.asset, meta, dry_run=bool(a.dry_run))
    print(session.redact_secrets(
        f"{PLATFORM} {'ok  ' if result.ok else 'QUEUED'} "
        f"{result.url or result.queued_path or '(no url)'}  {result.detail}"))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
