#!/usr/bin/env python3
"""Publish a Park Detective LONG-FORM (16:9) video through YouTube Studio's web uploader.

  scripts/video/.venv-tts/bin/python scripts/publishers/youtube_longform_web.py --dry-run \
      --asset <16:9 mp4> --meta ~/parksheet/video/longform/ep01-banned/cut8/meta.json [--wait-checks]
  scripts/video/.venv-tts/bin/python scripts/publishers/youtube_longform_web.py --go \
      --asset <16:9 mp4> --meta <meta.json>
  scripts/video/.venv-tts/bin/python scripts/publishers/publish.py --platform youtube_longform_web \
      --asset <16:9 mp4> --meta <meta.json>

The Shorts driver (`youtube_web.py`) with four things a long-form upload needs and a Short never
has, added as a subclass so a Short's run is untouched:

1. **A/B Testing** (Studio's "Test & compare", renamed in the uploader; mapped live 2026-11-24 on
   a throwaway 16:9 draft, deleted after). Details step -> Thumbnail -> "A/B Testing"
   (`#ab-test-button`) opens a dialog: "Title only | Thumbnail only | Title and thumbnail". The
   "Thumbnail only" test has three slots (two required), one hidden `input[type=file]` each;
   the footer reads "Thumbnails ready" once the required ones hold an image, and "Set test"
   saves it. Slots are filled in `meta.test_and_compare` order, so the package's own pick goes
   in slot 1. Shorts have no such tile, which is why this lives here.
   With one thumbnail and no test, the uploader's own "Upload file" input takes it.
2. **Tags** (advanced settings, "Show more"): one chip per tag, typed and closed with a comma,
   read back from the container. YouTube's limit is 500 characters, counted with commas and
   with quotes around a tag that has a space; `tags_of` refuses a list over it before upload.
3. **Category** (advanced settings; the channel default is Education): `meta.category`.
4. **A longer checks wait.** A 16-minute video's copyright and ad-suitability checks take
   longer than a Short's, so `checks_wait_ms` is LONGFORM_CHECKS_WAIT_MS.

`--dry-run --wait-checks` is the copyright pre-flight: it uploads the real cut as a draft, sets
the test, tags and category, waits for YouTube's checks to finish, reports what they found,
selects Public WITHOUT clicking Publish, and deletes the draft (the parent's discard_draft,
which refuses to delete anything that is not a draft).

**Never promoted.** A long-form episode that uses Storyblocks editorial clips may be posted
(educational context, ParkSheet decision 2026-11-23) but never promoted, boosted or marked
sponsored, so a meta with `promoted` or `sponsored` true is refused before anything is touched.
**SESSION ONLY**, like the Shorts driver: never from a workflow or a cron.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from browser import selectors_youtube as S  # noqa: E402
from browser import session  # noqa: E402
from publishers.base import REPO, PublishResult  # noqa: E402
from publishers import youtube_web as yw  # noqa: E402
from publishers.youtube_web import (  # noqa: E402
    CHECKS_COMPLETE, FormFieldError, YouTubeWebPublisher, checks_probe_js, checks_state_of,
    find_video, plan_lines, refuse_if_ambiguous, timed_out, title_of, video_id_from)

PLATFORM = "youtube_longform_web"

# --- anchors, mapped live 2026-11-24 on a throwaway 16:9 draft (deleted after) -----------------
UPLOADER = "ytcp-uploads-dialog"
AB_TEST_BUTTON = f"{UPLOADER} #ab-test-button"                 # "A/B Testing" tile beside "Upload file"
AB_DIALOG = "ytcp-creator-experiment-create-dialog"             # the A/B dialog's host (2026-11-24 dry run)
AB_DIALOG_TEXT = "Test and compare your thumbnails and titles"
AB_KIND_THUMBNAIL = "Thumbnail only"                           # chip; "Title only", "Title and thumbnail"
AB_ADD_TEXT = "Add thumbnail"                                  # an EMPTY slot reads this
AB_READY_TEXT = "Thumbnails ready"                             # footer once the required slots hold images
AB_SET_TEST = "Set test"
AB_SLOTS = 3                                                   # "Thumbnail 1 (required)", "2 (required)", "3"
THUMB_FILE_INPUT = f"{UPLOADER} ytcp-video-custom-still-editor input#file-loader"   # "Upload file"
ADVANCED_TOGGLE = f"{UPLOADER} {S.ADVANCED_TOGGLE}"            # "Show more" | aria "Show advanced settings"
TAGS_CONTAINER = f"{UPLOADER} #tags-container"
TAGS_INPUT = f"{TAGS_CONTAINER} input"
CATEGORY_SELECT = f"{UPLOADER} ytcp-form-select#category"
THUMBNAIL_EDITOR = f"{UPLOADER} ytcp-thumbnails-experiment-editor"

TAGS_MAX_CHARS = 500           # YouTube's limit (the "0/500" counter under the box)
THUMB_MAX_BYTES = 2 * 1024 * 1024   # YouTube's custom-thumbnail limit
THUMB_SUFFIXES = (".jpg", ".jpeg", ".png")
LONGFORM_CHECKS_WAIT_MS = 45 * 60_000
AB_LOAD_TIMEOUT_MS = 120_000
VIEWPORT = {"width": 1400, "height": 1000}
# Playwright will not stream a file over 50 MB to a browser it attached to over CDP ("Cannot
# transfer files larger than 50Mb to a browser not co-located with the server", 2026-11-24 on the
# 310 MB episode). The debug Chrome IS on this Mac, so a bigger file is handed over by path with
# CDP's own DOM.setFileInputFiles, which lets Chrome read it from disk.
PLAYWRIGHT_FILE_LIMIT = 45 * 1024 * 1024
WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
CATEGORIES = ("Autos & Vehicles", "Comedy", "Education", "Entertainment", "Film & Animation",
              "Gaming", "Howto & Style", "Music", "News & Politics", "Nonprofits & Activism",
              "People & Blogs", "Pets & Animals", "Science & Technology", "Sports",
              "Travel & Events")


class LongformMetaError(ValueError):
    """The meta cannot be published as a long-form video; nothing was touched."""


# --- pure helpers (unit-tested) ---------------------------------------------------------------

def watch_url(video_id) -> str:
    return WATCH_URL.format(video_id=video_id)


def tag_chars(tags) -> int:
    """YouTube's count: each tag, a comma between tags, and quotes around a tag with a space."""
    tags = list(tags)
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def tags_of(meta: dict) -> list[str]:
    """The meta's tags, stripped and de-duplicated (case-insensitive), within YouTube's limit."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in meta.get("tags") or []:
        tag = " ".join(str(raw).replace(",", " ").split())
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    if tag_chars(out) > TAGS_MAX_CHARS:
        raise LongformMetaError(f"tags come to {tag_chars(out)} characters by YouTube's count; "
                                f"the limit is {TAGS_MAX_CHARS}. Drop some before uploading.")
    return out


def resolve_path(rel, meta_path) -> pathlib.Path:
    """`rel` as given, or found from the meta's folder upward (a cut's meta lives one level
    below the episode, and package.yaml paths are episode- or repo-relative)."""
    p = pathlib.Path(str(rel)).expanduser()
    if p.is_absolute():
        if p.exists():
            return p
        raise LongformMetaError(f"file not found: {p}")
    if meta_path:
        for base in [pathlib.Path(meta_path).resolve().parent, *pathlib.Path(meta_path).resolve().parents]:
            if (base / p).exists():
                return base / p
    raise LongformMetaError(f"cannot find {rel!r} from {meta_path or '(no meta path)'} or any "
                            f"folder above it")


def check_thumbnail(path: pathlib.Path) -> pathlib.Path:
    if path.suffix.lower() not in THUMB_SUFFIXES:
        raise LongformMetaError(f"{path.name}: YouTube takes JPG or PNG thumbnails")
    size = path.stat().st_size
    if size > THUMB_MAX_BYTES:
        raise LongformMetaError(f"{path.name} is {size / 1e6:.1f} MB; YouTube's thumbnail "
                                f"limit is 2 MB (use the .jpg export)")
    return path


def thumbnails_of(meta: dict) -> tuple[list[pathlib.Path], str]:
    """(files, mode): the A/B test's thumbnails in slot order (mode "ab"), or the one custom
    thumbnail (mode "single"), or ([], "none")."""
    meta_path = meta.get("_meta_path")
    variants = meta.get("test_and_compare") or []
    if variants:
        files = [check_thumbnail(resolve_path(v["thumbnail"], meta_path)) for v in variants]
        if not 2 <= len(files) <= AB_SLOTS:
            raise LongformMetaError(f"test_and_compare has {len(files)} thumbnails; Studio's "
                                    f"A/B test takes 2 or 3")
        if len({f.resolve() for f in files}) != len(files):
            raise LongformMetaError("test_and_compare names the same thumbnail twice")
        return files, "ab"
    if meta.get("thumbnail"):
        return [check_thumbnail(resolve_path(meta["thumbnail"], meta_path))], "single"
    return [], "none"


def longform_plan(asset, meta: dict) -> list[str]:
    """youtube_web's plan lines, worded for a long-form video (it reads both content tabs)."""
    return [line.replace("a public Short", "a public long-form video")
                .replace(S.CONTENT_SHORTS_URL, "either content tab") for line in plan_lines(asset, meta)]


def set_local_file(page, locator, path) -> str:
    """Put a local file in a file input. Small files go through Playwright as before; a file over
    PLAYWRIGHT_FILE_LIMIT goes by path through CDP. Returns which route was taken."""
    path = pathlib.Path(path).resolve()
    if path.stat().st_size <= PLAYWRIGHT_FILE_LIMIT:
        locator.set_input_files(str(path))
        return "playwright"
    locator.evaluate("e => { window.__lfFileInput = e; }")
    cdp = page.context.new_cdp_session(page)
    try:
        found = cdp.send("Runtime.evaluate", {"expression": "window.__lfFileInput"})
        object_id = ((found or {}).get("result") or {}).get("objectId")
        if not object_id:
            raise FormFieldError("could not resolve the upload input over CDP for a large file")
        cdp.send("DOM.setFileInputFiles", {"files": [str(path)], "objectId": object_id})
    finally:
        try:
            page.evaluate("() => { delete window.__lfFileInput; }")
        except Exception:  # noqa: BLE001 — cosmetic
            pass
        cdp.detach()
    return "cdp"


def check_longform_meta(meta: dict) -> None:
    """Refuse, before anything is touched, what this driver must never publish."""
    if meta.get("format") != "longform":
        raise LongformMetaError(f"meta format is {meta.get('format')!r}, not 'longform': a "
                                f"Short goes through youtube_web")
    for key in ("promoted", "sponsored"):
        if meta.get(key):
            raise LongformMetaError(f"meta {key!r} is true: a long-form episode with Storyblocks "
                                    f"editorial clips is never promoted, boosted or sponsored")
    if meta.get("made_for_kids"):
        raise LongformMetaError("meta made_for_kids is true; this driver only answers No")
    cat = meta.get("category")
    if cat and cat not in CATEGORIES:
        raise LongformMetaError(f"category {cat!r} is not one of Studio's: {', '.join(CATEGORIES)}")
    tags_of(meta)
    thumbnails_of(meta)


def chips_missing(container_text: str, tags) -> list[str]:
    """Tags whose text is not in the tags container's text (case-insensitive)."""
    have = " ".join((container_text or "").lower().split())
    return [t for t in tags if t.lower() not in have]


def ab_state(dialog_text: str) -> str:
    """"ready" when every slot holds an image and the footer says so, "loading" otherwise."""
    text = dialog_text or ""
    if AB_READY_TEXT in text and AB_ADD_TEXT not in text:
        return "ready"
    return "loading"


# --- the driver ---------------------------------------------------------------------------------

class YouTubeLongformWebPublisher(YouTubeWebPublisher):
    """youtube_web for a 16:9 episode: A/B thumbnails, tags, category, a longer checks wait."""

    platform = PLATFORM
    checks_wait_ms = LONGFORM_CHECKS_WAIT_MS

    def __init__(self, *, repo: pathlib.Path | None = None, check_fn=None,
                 wait_checks: bool = False) -> None:
        super().__init__(repo=repo, check_fn=check_fn)
        self.wait_checks = wait_checks
        self._notes: list[str] = []

    def publish(self, asset, meta: dict, dry_run: bool) -> PublishResult:
        try:
            check_longform_meta(meta)
        except LongformMetaError as exc:
            return PublishResult(platform=self.platform, ok=False, url=None, queued_path=None,
                                 detail=f"REFUSED before touching Studio: {exc}")
        self._notes = []
        return super().publish(asset, meta, dry_run)

    def row_url(self, row: dict) -> str:
        vid = video_id_from(row.get("href") or "") or yw._id_from_edit_href(row.get("href"))
        return watch_url(vid) if vid else S.CONTENT_VIDEOS_URL

    # -- the Details step ---------------------------------------------------------------------

    def upload(self, page, asset: pathlib.Path, meta: dict) -> None:
        """The parent's upload, plus thumbnails/A-B test, tags and category before Next."""
        title, desc = title_of(meta), yw.description_of(meta)
        # The A/B dialog's footer ("Set test") is fixed to the dialog and falls below a short
        # viewport, where no scroll reaches it (2026-11-24 dry run). The probe that mapped it ran
        # at this size and saw the whole dialog.
        try:
            page.set_viewport_size(VIEWPORT)
        except Exception:  # noqa: BLE001 — the click below has its own fallback
            pass
        self.goto(page, S.UPLOAD_DIALOG_URL)
        self.open_uploader(page)
        page.locator(S.FILE_INPUT).first.wait_for(state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
        route = set_local_file(page, page.locator(S.FILE_INPUT).first, asset)
        self._uploaded = True
        print(f"{self.platform}: file handed over ({route})", file=sys.stderr)
        page.locator(S.TITLE_BOX).first.wait_for(state="visible", timeout=S.UPLOAD_TIMEOUT_MS)
        self._video_id = video_id_from(page.locator(S.UPLOAD_DIALOG).first.inner_text())
        print(f"{self.platform}: file handed to Studio"
              + (f" (video id {self._video_id})" if self._video_id else ""), file=sys.stderr)
        self.fill_box(page, S.TITLE_BOX, title, "title")
        self.fill_box(page, S.DESCRIPTION_BOX, desc, "description")
        files, mode = thumbnails_of(meta)
        if mode == "ab":
            self._notes.append(self.set_ab_test(page, files))
        elif mode == "single":
            self._notes.append(self.set_thumbnail(page, files[0]))
        self.set_audience(page)
        self.open_advanced(page)
        tags = tags_of(meta)
        if tags:
            self._notes.append(self.set_tags(page, tags))
        if meta.get("category"):
            self._notes.append(self.set_category(page, meta["category"]))
        if yw.ai_disclosure_of(meta):
            self.disclose_ai_in_uploader(page)
        self.next_to_visibility(page)

    def set_thumbnail(self, page, path: pathlib.Path) -> str:
        page.locator(THUMB_FILE_INPUT).first.wait_for(state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
        page.set_input_files(THUMB_FILE_INPUT, str(path.resolve()))
        return f"custom thumbnail {path.name}"

    def set_ab_test(self, page, files: list[pathlib.Path]) -> str:
        """Thumbnail-only A/B test: one file per slot, wait for "Thumbnails ready", Set test."""
        tile = page.locator(AB_TEST_BUTTON).first
        tile.wait_for(state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
        tile.scroll_into_view_if_needed()
        tile.click()
        # The host element is a zero-size wrapper (Playwright calls it hidden while the dialog
        # inside it is on screen), so visibility is judged on the dialog's own heading and the
        # host is only the SCOPE for its chips, inputs and buttons (2026-11-24 dry run).
        heading = page.get_by_text(AB_DIALOG_TEXT, exact=True).first
        heading.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)
        dialog = page.locator(AB_DIALOG).filter(has_text=AB_DIALOG_TEXT).first
        dialog.get_by_text(AB_KIND_THUMBNAIL, exact=True).first.click()
        inputs = dialog.locator("input[type=file]")
        try:
            page.wait_for_function(
                "([sel, txt, n]) => [...document.querySelectorAll(sel)].some(d => "
                "(d.innerText||'').includes(txt) && d.querySelectorAll('input[type=file]').length >= n)",
                arg=[AB_DIALOG, AB_DIALOG_TEXT, AB_SLOTS], timeout=S.ANCHOR_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            if not timed_out(exc):
                raise
        if inputs.count() != AB_SLOTS:
            raise FormFieldError(f"the A/B Testing dialog shows {inputs.count()} thumbnail inputs "
                                 f"after {AB_KIND_THUMBNAIL!r}, not {AB_SLOTS}; Studio's dialog "
                                 f"has changed (youtube_longform_web AB_* anchors).")
        for k, path in enumerate(files):
            inputs.nth(k).set_input_files(str(path.resolve()))
            time.sleep(1.5)
        try:
            page.wait_for_function(
                "([sel, txt, ready, add, maxEmpty]) => [...document.querySelectorAll(sel)].some(d => { "
                "const t = d.innerText || ''; return t.includes(txt) && t.includes(ready) && "
                "(t.split(add).length - 1) <= maxEmpty; })",
                arg=[AB_DIALOG, AB_DIALOG_TEXT, AB_READY_TEXT, AB_ADD_TEXT, AB_SLOTS - len(files)],
                timeout=AB_LOAD_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            if not timed_out(exc):
                raise
            raise FormFieldError(
                f"the A/B Testing dialog did not reach {AB_READY_TEXT!r} with {len(files)} "
                f"thumbnails within {AB_LOAD_TIMEOUT_MS // 1000}s; it reads "
                f"{' / '.join(dialog.inner_text().split(chr(10)))[:300]!r}") from exc
        set_test = dialog.get_by_role("button", name=AB_SET_TEST, exact=True).first
        try:
            set_test.click(timeout=S.BOX_CLICK_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001 — "outside of the viewport": dispatch instead
            if not timed_out(exc):
                raise
            set_test.dispatch_event("click")
        heading.wait_for(state="hidden", timeout=S.ANCHOR_TIMEOUT_MS)
        shown = ""
        try:
            shown = " / ".join(page.locator(THUMBNAIL_EDITOR).first.inner_text().split("\n"))[:160]
        except Exception:  # noqa: BLE001 — informational
            pass
        return (f"A/B test set, thumbnail only, slots: {', '.join(p.name for p in files)}"
                + (f" (thumbnail block reads {shown!r})" if shown else ""))

    def close_ab_dialog(self, page) -> None:
        """Close an open A/B Testing dialog without setting it. Its backdrop swallows clicks on
        the uploader underneath, close button included (2026-11-24: a dry run's clean-up could
        not close the uploader while it was up). Absence is fine."""
        heading = page.get_by_text(AB_DIALOG_TEXT, exact=True)
        if not heading.count() or not heading.first.is_visible():
            return
        close = page.locator(AB_DIALOG).filter(has_text=AB_DIALOG_TEXT).first.get_by_role(
            "button", name="Close", exact=True)
        if close.count():
            close.first.click()
        else:
            page.keyboard.press("Escape")
        try:
            heading.first.wait_for(state="hidden", timeout=S.ANCHOR_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            if not timed_out(exc):
                raise
            page.keyboard.press("Escape")

    def open_advanced(self, page) -> None:
        toggle = page.locator(ADVANCED_TOGGLE).first
        toggle.wait_for(state="attached", timeout=S.ANCHOR_TIMEOUT_MS)
        if not page.locator(TAGS_INPUT).first.is_visible():
            toggle.scroll_into_view_if_needed()
            toggle.click()
            page.locator(TAGS_INPUT).first.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)

    def set_tags(self, page, tags: list[str]) -> str:
        box = page.locator(TAGS_INPUT).first
        box.scroll_into_view_if_needed()
        box.click()
        for tag in tags:
            page.keyboard.insert_text(tag)
            page.keyboard.press("Comma")
        page.keyboard.press("Tab")
        missing = chips_missing(page.locator(TAGS_CONTAINER).first.inner_text(), tags)
        if missing:
            raise FormFieldError(f"the tags box did not take {len(missing)} of {len(tags)} tags "
                                 f"({', '.join(missing[:4])}...); fix youtube_longform_web.TAGS_*")
        return f"{len(tags)} tags ({tag_chars(tags)}/{TAGS_MAX_CHARS} chars)"

    def set_category(self, page, category: str) -> str:
        select = page.locator(CATEGORY_SELECT).first
        select.scroll_into_view_if_needed()
        if category in " ".join(select.inner_text().split()):
            return f"category {category} (already)"
        select.click()
        option = page.get_by_role("option", name=category, exact=True)
        if not option.count():
            option = page.locator("tp-yt-paper-item").filter(has_text=category)
        option.first.wait_for(state="visible", timeout=S.ANCHOR_TIMEOUT_MS)
        option.first.click()
        time.sleep(1)
        got = " ".join(select.inner_text().split())
        if category not in got:
            raise FormFieldError(f"chose category {category!r} but the select reads {got!r}")
        return f"category {category}"

    # -- after Publish ------------------------------------------------------------------------

    def verify_details(self, page, meta: dict) -> str:
        """The parent's edit-page check, plus a read of the thumbnail block (the A/B test)."""
        note = super().verify_details(page, meta)
        ab = ""
        try:
            ab = page.evaluate(
                "() => { const t = document.body.innerText; const i = t.indexOf('Thumbnail'); "
                "return i < 0 ? '' : t.slice(i, i + 260); }") or ""
        except Exception:  # noqa: BLE001 — informational
            pass
        ab = " / ".join(x for x in ab.split("\n") if x.strip())[:220]
        extra = "; ".join(self._notes)
        return note + (f"; {extra}" if extra else "") + (f"; edit page thumbnail block: {ab!r}" if ab else "")

    # -- the dry run --------------------------------------------------------------------------

    def _dry_run_on(self, page, asset: pathlib.Path, meta: dict, title: str,
                    reached: list) -> PublishResult:
        """Everything a live run does but Publish (optionally waiting for checks), then delete."""
        self.assert_channel(page)
        reached.append(f"channel confirmed: {S.CHANNEL_NAME}")
        before = self.read_content(page)
        reached.append(f"content list read: {len(before)} row(s)")
        refuse_if_ambiguous(before, title)
        hit = find_video(before, title)
        if hit is not None:
            self.refuse_unless_public(hit, title)
            return PublishResult(platform=self.platform, ok=True, url=self.row_url(hit),
                                 queued_path=None,
                                 detail=f"dry-run: already published — {title!r} is on the channel")
        primary = None
        try:
            self.upload(page, asset, meta)
            reached.append(f"uploaded {asset.name}; title and description verified; audience No")
            reached.extend(self._notes)
            reached.append("walked " + " -> ".join(S.STEP_NAMES))
            if self.wait_checks:
                started = time.monotonic()
                decision = self.await_checks(page)
                reached.append(f"checks: {decision} after {(time.monotonic() - started) / 60:.1f} min, "
                               f"footer {self._checks_last!r}")
            else:
                probe = page.evaluate(checks_probe_js())
                probe = probe if isinstance(probe, dict) else {}
                reached.append(f"checks footer reads {checks_state_of(probe)!r} (not waited; "
                               f"--wait-checks waits for {CHECKS_COMPLETE!r})")
            self.set_public(page)
            reached.append(f"visibility set to {S.PUBLIC_VISIBILITY_TEXT} (Publish NOT clicked)")
            if self._video_id:
                reached.append(f"draft video id {self._video_id}")
        except Exception as exc:  # noqa: BLE001 — re-raised below, after the clean-up
            primary = exc
        try:
            self.close_ab_dialog(page)
        except Exception:  # noqa: BLE001 — discard_draft reports what is left
            pass
        try:
            reached.append(self.discard_draft(page, title, before))
        except Exception as cleanup:  # noqa: BLE001
            if primary is None:
                raise
            raise yw.DraftNotRemoved(
                f"{type(cleanup).__name__}: {cleanup} — AND the run had already failed with "
                f"{type(primary).__name__}: {primary}, which is the cause to fix first.") from primary
        if primary is not None:
            raise primary
        return PublishResult(platform=self.platform, ok=True, url=None, queued_path=None,
                             detail="dry-run: " + "; ".join(longform_plan(asset, meta) + reached))


def main(argv=None, *, repo: pathlib.Path | None = None) -> int:
    ap = argparse.ArgumentParser(description=f"Publish a long-form video to {S.CHANNEL_NAME}.")
    ap.add_argument("--dry-run", action="store_true",
                    help="upload for real as a draft, fill everything, select Public, DELETE the draft")
    ap.add_argument("--wait-checks", action="store_true",
                    help="with --dry-run: wait for YouTube's copyright/suitability checks first")
    ap.add_argument("--go", action="store_true", help="actually publish, Public")
    ap.add_argument("--asset", type=pathlib.Path, required=True)
    ap.add_argument("--meta", type=pathlib.Path, required=True)
    a = ap.parse_args(argv)
    if a.dry_run == a.go:
        ap.error("pick exactly one of --dry-run and --go")
    if a.wait_checks and not a.dry_run:
        ap.error("--wait-checks is for --dry-run (a --go run always waits for checks)")
    meta = json.loads(a.meta.read_text(encoding="utf-8"))
    meta.setdefault("_meta_path", str(a.meta.resolve()))
    pub = YouTubeLongformWebPublisher(repo=pathlib.Path(repo) if repo else REPO,
                                      wait_checks=a.wait_checks)
    result = pub.publish(a.asset, meta, dry_run=bool(a.dry_run))
    print(session.redact_secrets(
        f"{PLATFORM} {'ok  ' if result.ok else 'QUEUED'} "
        f"{result.url or result.queued_path or '(no url)'}  {result.detail}"))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
