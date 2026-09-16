#!/usr/bin/env python3
"""Schedule a Short into TikTok Studio through the logged-in debug Chrome.

  python3 scripts/publishers/tiktok_web.py --check                      # read-only anchors
  python3 scripts/publishers/tiktok_web.py --dry-run --asset X.mp4 --meta meta.json
  python3 scripts/publishers/publish.py --platform tiktok_web --asset X.mp4 \
      --meta meta.json --schedule 2026-09-21T14:00:00-07:00

**Why a Chrome driver and not Upload-Post.** Upload-Post reaches TikTok only on its paid
plan, which Stephen declined (2026-09-15). TikTok Studio's own web uploader schedules for
free, and the debug Chrome already is the browser Stephen logs in with. The cost is that
this is a **semi-supervised weekly step, never a scheduled Actions job** — spec Chrome rule
1, and the ToS note in the runbook: automating a logged-in web session is a grey area, so it
runs beside Stephen on a Saturday, a handful of posts at a time, and every failure stops and
asks rather than retrying.

**Shape** (spec Chrome rule 4, the same read → diff → apply → re-read → assert the Gumroad
drivers use):

    read the Posts list ─► this caption + this date already there? ─► skip, ok
                        └► no ─► upload, caption, schedule, submit ─► re-read ─► assert

There is no "Scheduled" tab to open first: as of 2026-09-15 TikTok Studio shows posted and
scheduled videos in one table ("Your posted and scheduled videos will appear here"), so the
read navigates and reads, and clicks nothing at all. See selectors_tiktok for the evidence.

Idempotency is the whole safety story. Re-running Saturday's batch, or resuming after a
crash, must never put the same video on the account twice — so the list read comes first and
a post that submitted but could not be verified is **not** retried.

Playwright is only ever imported inside `session.open_page`, so this module imports with the
standard library alone (CLAUDE.md "Useful commands": the test suite has nothing else).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402  (scripts/ledger.py — one ISO-8601 reader for the whole repo)

from browser import selectors_tiktok as S  # noqa: E402
from browser import session  # noqa: E402
from publishers import base  # noqa: E402
from publishers.base import REPO, Publisher, PublishResult  # noqa: E402

PLATFORM = "tiktok_web"
SITE = "tiktok"
# Both TikTok transports queue into one folder: to Stephen a card is "a TikTok post that
# needs a human", and which publisher wrote it is a detail inside the card.
QUEUE_SUBDIR = "tiktok"
# The first N characters of the caption are the idempotency key. Long enough that two Shorts
# in a week cannot collide, short enough to survive the truncation the list applies.
KEY_LEN = 40
# Below this, a "key" is a stub that would prefix-match half the account. A caption this
# short means the meta is wrong, and skipping every day of the week is the failure mode.
MIN_KEY_LEN = 12
# How TikTok says "this caption is cut off". The only case where a row shorter than the key
# may still be that post.
ELLIPSIS = ("\u2026", "...")
NAV_TIMEOUT_MS = 60_000
ANCHOR_TIMEOUT_MS = 30_000
# An mp4 upload plus TikTok's own processing, not an API ping.
UPLOAD_TIMEOUT_MS = 300_000
LIST_TIMEOUT_MS = 45_000


class ScheduleError(ValueError):
    """The requested schedule cannot be honoured (unparseable, naive, past, too far out)."""


class ScheduleFieldError(RuntimeError):
    """The date or time field would not take the value — the picker markup has drifted."""


class ScrapeError(RuntimeError):
    """The posts list rendered, but no row's caption could be read.

    Distinct from "nothing is scheduled": rows exist, so the markup drifted. Reading that as
    an empty list is what would schedule a second copy of every post in the batch.
    """


class SessionLost(RuntimeError):
    """A navigation landed on the login wall part-way through the flow."""


class VerificationFailed(RuntimeError):
    """The submit went through but the post is not on the posts list.

    Deliberately its own type: this is the one failure that must NOT be retried. The video
    may be scheduled already, and a second pass would upload it again.
    """


# --------------------------------------------------------------------------- pure helpers

def parse_schedule(value) -> dt.datetime | None:
    """ISO 8601 *with an offset* → an aware datetime. Empty/None means "post now".

    The offset is required rather than assumed. "14:00" means one instant in Los Angeles and
    another in London, and the whole point of the weekly helper is that Stephen knows which
    one he asked for.
    """
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        when = value
    else:
        try:
            when = ledger.parse_ts(str(value))
        except ValueError as exc:
            raise ScheduleError(f"schedule_at {value!r} is not an ISO-8601 timestamp: {exc}"
                                ) from exc
    if when.tzinfo is None:
        raise ScheduleError(
            f"schedule_at {value!r} has no UTC offset. TikTok schedules in a real timezone; "
            f"refusing to guess one — pass e.g. 2026-09-21T14:00:00-07:00.")
    return when


def check_within_limit(when: dt.datetime, *, now: dt.datetime | None = None) -> None:
    """Refuse a schedule TikTok Studio would not accept, before anything is typed into it."""
    now = now or dt.datetime.now().astimezone()
    if when <= now:
        raise ScheduleError(f"schedule {when.isoformat(timespec='minutes')} is in the past "
                            f"(now {now.isoformat(timespec='minutes')})")
    ahead = when - now
    if ahead > dt.timedelta(days=S.MAX_SCHEDULE_DAYS):
        raise ScheduleError(
            f"schedule {when.isoformat(timespec='minutes')} is {ahead.days} days out; TikTok "
            f"Studio allows at most {S.MAX_SCHEDULE_DAYS} (UNVERIFIED — confirm with "
            f"`tiktok_web.py --check` against the live form before relying on it)")


def format_date(when: dt.datetime) -> str:
    return when.strftime(S.DATE_FORMAT)


def format_time(when: dt.datetime) -> str:
    return when.strftime(S.TIME_FORMAT)


def date_variants(when: dt.datetime) -> tuple[str, ...]:
    """Every lowercase rendering of `when`'s date a Studio row might show.

    The list is read as text, so which of these TikTok uses is a UI decision we do not get to
    make. Matching any of them is what keeps the idempotency check working after a relayout.
    """
    short = when.strftime("%b").lower()
    long = when.strftime("%B").lower()
    return (when.strftime("%Y-%m-%d"),
            f"{when.month}/{when.day}/{when.year}",
            when.strftime("%m/%d/%Y"),
            f"{short} {when.day}",
            f"{long} {when.day}",
            f"{when.day} {short}")


# A date variant is searched on token boundaries, never as a raw substring: "sep 1" sits
# inside "sep 10" (as "2" does inside "20"-"29", "3" inside "30"-"31"), and "1 sep" inside
# "21 sep". A near miss on its own — but combined with the ellipsis exception in row_matches
# it reads a row genuinely scheduled for the 10th as the post targeted at the 1st, reports
# "already scheduled", and that day is silently never posted. Both days are always in the
# same list inside the 10-day window, and ParkSheet's captions share a templated prefix, so
# this is the ordinary case rather than a contrived one.
def date_pattern(variant: str) -> str:
    """`variant` as a regex that cannot be completed by another digit on either side."""
    return r"(?<![0-9])" + re.escape(variant) + r"(?![0-9])"


def date_in_text(text, when: dt.datetime) -> bool:
    """Is `when`'s date present in `text` as a whole token, in any rendering?"""
    haystack = _norm(text)
    return any(re.search(date_pattern(variant), haystack)
               for variant in date_variants(when))


def _norm(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def caption_of(meta: dict) -> str:
    """The caption TikTok gets: Stephen's copy plus his tags as hashtags, capped."""
    body = str(meta.get("description") or meta.get("title") or "").strip()
    tags = " ".join(f"#{str(t).replace(' ', '')}" for t in meta.get("tags", []) if str(t).strip())
    caption = f"{body} {tags}".strip() if tags else body
    return caption[:S.CAPTION_MAX]


def caption_key(caption: str) -> str:
    """The idempotency key: the first KEY_LEN characters, whitespace- and case-normalised."""
    return _norm(caption)[:KEY_LEN]


def caption_candidates(row: dict) -> tuple[str, ...]:
    """Every string in a row that could be its caption, normalised, best guess first.

    A Studio row is a thumbnail, a caption, a date, a privacy badge and four counters, and
    which line innerText puts first is TikTok's decision rather than ours — a duration badge
    or a status word ahead of the caption would make a fixed line index read the wrong
    string, fail the prefix test, and re-upload a video that is already scheduled. So every
    line is a candidate and one match is enough.

    That is not a loosening worth worrying about: a candidate still has to carry MIN_KEY_LEN
    characters of the exact caption prefix, and row_matches still requires the target date in
    the row. No real row has ever been read — @park.sheet has no posts — which is precisely
    why this does not bet on a line number it cannot check.
    """
    out = [row.get("caption") or ""]
    out += [str(x) for x in (row.get("lines") or [])]
    if not any(_norm(x) for x in out):
        out.append(row.get("text") or "")
    seen, ordered = set(), []
    for candidate in (_norm(x) for x in out):
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return tuple(ordered)


def _candidate_matches(candidate: str, key: str) -> bool:
    """The prefix rule, applied to one candidate string from a row.

    **One direction, with one explicit exception.** The key must be a prefix of the row's
    caption. The old rule — "the shorter of the two is a prefix of the longer" — let a short
    row stand in for a long caption, which with a row selector that matches menu items ("Upload
    video") produces a false SKIP: the day is never posted and nothing says so.

    The exception is a row TikTok itself marked as cut off with an ellipsis. Then the row is a
    prefix of the real caption and the comparison has to run the other way — refusing that case
    would turn every truncated row into a re-upload, which is the worse failure. It stays narrow:
    the ellipsis must be there, and what remains must still be MIN_KEY_LEN characters.
    """
    truncated = candidate.endswith(ELLIPSIS)
    caption = candidate.rstrip("….") if truncated else candidate
    if len(caption) < MIN_KEY_LEN:
        return False
    return key.startswith(caption) if truncated else caption.startswith(key)


def row_matches(row: dict, key: str, when: dt.datetime | None) -> bool:
    """Is this Posts-list row the post `key` + `when` describes?

    When a schedule was asked for, the row's text must also carry that date — the same caption
    on two days is two different posts, and a menu item carries no date at all. That search is
    `date_in_text`, on token boundaries: a raw substring test makes the 1st match the 10th.
    """
    key = _norm(key)
    if len(key) < MIN_KEY_LEN:
        return False
    if not any(_candidate_matches(c, key) for c in caption_candidates(row)):
        return False
    if when is None:
        return True
    return date_in_text(row.get("text") or row.get("caption") or "", when)


def find_scheduled(rows, key: str, when: dt.datetime | None):
    return next((r for r in rows if row_matches(r, key, when)), None)


def check_rows_sane(payload):
    """Unwrap {count, rows}, or refuse when the selector matched rows that carry no text.

    `count` is what the row selector matched; `rows` is the subset that had text. The two are
    reported separately for one reason: the reader used to end `.filter(r => r.text)`, so
    textless rows were gone before this guard could see them and a page of skeletons read as
    "nothing is scheduled" — which schedules a duplicate of every post in the batch.

    count > 0 with rows empty is therefore the ambiguous case, and it fails closed.
    """
    if isinstance(payload, dict):
        count, rows = int(payload.get("count") or 0), list(payload.get("rows") or [])
    else:                       # a bare list: every element carried text by construction
        rows = list(payload or [])
        count = len(rows)
    rows = [r for r in rows if _norm(r.get("caption") or r.get("text"))]
    if count and not rows:
        raise ScrapeError(
            f"the TikTok Studio content list matched {count} row(s) but not one of them "
            f"carried any text, so no scheduled post can be recognised. Either the list "
            f"markup has changed (fix selectors_tiktok.POST_ROW) or the read raced the "
            f"render. Refusing to continue, because treating this as 'nothing is scheduled' "
            f"would schedule a duplicate of every post in the batch.")
    return rows


def scheduled_rows_js() -> str:
    """JS: {count, rows} — what the row selector matched, and the ones carrying text.

    Both numbers, never just the survivors: `check_rows_sane` needs to know that rows existed
    but read empty, which is the difference between "nothing is scheduled" and "the markup
    moved". Filtering first made that guard unreachable.

    Each row also carries `lines`, its innerText split and trimmed. The caption is not
    reliably line 0 of a Studio row and no real row has ever been read, so `row_matches`
    tries every line rather than betting on an index (see caption_candidates).

    Built by concatenating repr()d constants rather than an f-string — the 2026-09-14 Gumroad
    outage was an f-string segment spliced onto a plain one, where `}}` stayed two literal
    braces. The two row selectors are tried in order and the first that matches anything
    wins; joining them with a comma would silently mix a table with a card grid. Each is
    resolved inside a try: POST_ROW carries a `:not(:has(...))` to drop the column header,
    and one unsupported selector must fall through to the fallback rather than throw the
    whole read away — an exception here reads to the caller as "the list would not load".
    """
    sels = "[" + repr(S.POST_ROW) + "," + repr(S.POST_ROW_FALLBACK) + "]"
    return ("() => { let els = []; for (const s of " + sels + ") {"
            " try { els = [...document.querySelectorAll(s)]; } catch (e) { els = []; }"
            " if (els.length) break; }"
            " const rows = els.map(r => { const t = (r.innerText || '');"
            " const lines = t.split('\\n').map(x => x.trim()).filter(Boolean)"
            ".slice(0, " + repr(S.POST_ROW_MAX_LINES) + ");"
            " const a = r.querySelector('a[href]');"
            " return {caption: (lines[0] || ''), lines: lines,"
            " text: t.replace(/\\s+/g, ' ').trim().slice(0, 400),"
            " url: (a ? a.href : '')}; }).filter(r => r.text);"
            " return {count: els.length, rows: rows}; }")


def scheduled_ready_js() -> str:
    """JS predicate: has the list settled — a row WITH TEXT, or the empty-state copy?

    This is the distinction that decides whether a skip is safe. "No rows yet" during
    hydration and "no scheduled posts" look identical in a single read, and only one of them
    means it is safe to upload. A bare element count is not the test: a header row and a
    skeleton row both match the row selector while the real rows are still loading, so
    `if (querySelectorAll(s).length) return true` declared the page settled a beat before it
    was. When neither condition appears the wait times out, which queues a card.

    On an account with no posts the empty-state branch is the one that fires: POST_ROW
    excludes the column header on purpose, so an empty list matches zero rows and the copy
    "no posts yet" is the only thing that says the table finished rendering.
    """
    sels = "[" + repr(S.POST_ROW) + "," + repr(S.POST_ROW_FALLBACK) + "]"
    return ("() => { for (const s of " + sels + ") {"
            " let els = []; try { els = [...document.querySelectorAll(s)]; } catch (e) {}"
            " for (const r of els)"
            " if (((r.innerText || '').trim()).length) return true; }"
            " const t = ((document.body && document.body.innerText) || '').toLowerCase();"
            " return t.includes(" + repr(S.SCHEDULED_EMPTY_TEXT) + "); }")


def plan_lines(asset: pathlib.Path, meta: dict) -> list[str]:
    """What --dry-run prints. Pure: it reads the meta, never the browser."""
    when = parse_schedule(meta.get("schedule_at"))
    caption = caption_of(meta)
    return [f"would schedule {pathlib.Path(asset).name} on TikTok Studio",
            (f"at {format_date(when)} {format_time(when)} (UTC{when.strftime('%z')})"
             if when else "posting immediately (no schedule_at)"),
            f"caption: {caption[:80]}{'…' if len(caption) > 80 else ''}",
            f"skip-if-present key: {caption_key(caption)!r}"]


def manual_steps(asset: pathlib.Path, meta: dict, when: dt.datetime | None) -> list[str]:
    """The exact remaining manual step, for the queue card (spec Chrome rule 7)."""
    caption = caption_of(meta)
    timing = (f"turn on {S.SCHEDULE_TOGGLE_TEXT} and set {format_date(when)} "
              f"{format_time(when)} (UTC{when.strftime('%z')}), then click "
              f"{S.SCHEDULE_BUTTON_TEXT}"
              if when else f"leave the scheduler off and click {S.POST_BUTTON_TEXT}")
    return [
        "Run: python3 scripts/browser/ensure_chrome.py",
        f"Open {S.UPLOAD_URL} — if it bounces to a login, sign in with "
        f"'{S.LOGIN_QR_TEXT}' and scan it with the phone app (the profile keeps the "
        f"session afterwards)",
        f"Upload this file: {pathlib.Path(asset).resolve()}",
        f"Wait for the form to appear (the '{S.UPLOAD_READY_TEXT}' box) — it does not exist "
        f"until TikTok has taken the file",
        f"Paste this caption: {caption}",
        f"Then {timing}",
        f"Confirm it appears in the posts list at {S.CONTENT_URL} — posted and scheduled "
        f"videos share one table, there is no separate tab to open",
        "DO NOT re-run the scheduler for this day until you have looked at that list — the "
        "post may have gone through after the failure, and a second run would upload it twice",
    ]


# ------------------------------------------------------------------------- the --check probes

# What a probe row means. A canary that reports MISSING for something that cannot exist yet
# is a canary Stephen learns to ignore, so the two cases are named apart:
#   LIVE      — must be on the page right now; absent means the anchor drifted, exit 1.
#   POST_FILE — only exists once TikTok has taken a video, and selecting a file starts a real
#               upload. Reported as "post-file only", never as a failure.
#   ROWS      — checkable only once the account HAS a post. While the posts list shows its
#               empty state there is no row to match, and saying MISSING would be a lie; the
#               moment ParkSheet has posted anything this probe starts being a real check,
#               which matters because POST_ROW is the selector idempotency rests on.
#   ABSENT    — asserted NOT to be there (the Scheduled tab that no longer exists). Finding
#               one means TikTok changed back and the driver needs its tab click again.
LIVE, POST_FILE, ROWS, ABSENT = "live", "post-file", "rows", "absent"


def check_probes() -> tuple[tuple[str, str, str, str, str], ...]:
    """(page url, label, kind, value, stage) for every anchor `--check` resolves, read-only.

    A table rather than code so the canary and the driver cannot disagree about what "the
    anchors resolve" means, and so a new anchor is one row.
    """
    return (
        (S.UPLOAD_URL, "file input", "css", S.FILE_INPUT, LIVE),
        (S.UPLOAD_URL, "select video", "css", S.SELECT_VIDEO_BUTTON, LIVE),
        (S.UPLOAD_URL, "caption editor", "css", S.CAPTION_EDITOR, POST_FILE),
        (S.UPLOAD_URL, "schedule toggle", "css", S.SCHEDULE_TOGGLE, POST_FILE),
        (S.UPLOAD_URL, "schedule date", "css", S.SCHEDULE_DATE_INPUT, POST_FILE),
        (S.UPLOAD_URL, "schedule time", "css", S.SCHEDULE_TIME_INPUT, POST_FILE),
        (S.UPLOAD_URL, "post button", "role", S.POST_BUTTON_TEXT, POST_FILE),
        (S.CONTENT_URL, "posts table", "css", S.POSTS_TABLE, LIVE),
        (S.CONTENT_URL, "empty state", "body", S.SCHEDULED_EMPTY_TEXT, LIVE),
        (S.CONTENT_URL, "post rows", "css", S.POST_ROW, ROWS),
        (S.CONTENT_URL, "scheduled tab", "role-tab", "", ABSENT),
    )


# The anchor each page is waited on before anything is counted. Without it the probe races
# the render: a 2026-09-15 run that waited only on body text reported FILE_INPUT missing, and
# the same page had it once the uploader stage had appeared. A canary that reports a race as
# drift is worse than no canary.
PAGE_READY = {S.UPLOAD_URL: S.UPLOAD_PAGE_READY, S.CONTENT_URL: S.CONTENT_PAGE_READY}


def _resolve(page, kind: str, value: str):
    """A locator for one probe row. Resolving only — nothing here clicks or types."""
    if kind == "css":
        return page.locator(value)
    if kind == "role":
        # exact=True is load-bearing. Playwright matches an accessible name as a
        # case-insensitive SUBSTRING by default, and the studio sidebar has a "Posts" entry
        # that sorts before the form — which is why --check used to report the Post button
        # present on a page that has no Post button at all.
        return page.get_by_role("button", name=value, exact=True)
    if kind == "role-tab":
        return page.get_by_role("tab")
    return page.get_by_text(value, exact=True)


def _probe_count(page, kind: str, value: str) -> int:
    """How many times one probe row resolves. Read-only by construction."""
    if kind == "body":
        # The empty-state copy is stored lowercased because that is how scheduled_ready_js
        # tests it, and get_by_text(exact=True) is case-SENSITIVE — probing it as a locator
        # would report the live "No posts yet" as missing. Same test as the driver makes.
        return ((page.inner_text("body") or "").lower()).count(value)
    return _resolve(page, kind, value).count()


# --------------------------------------------------------------------------- the publisher

class TikTokWebPublisher(Publisher):
    """TikTok Studio's web uploader, driven in the logged-in debug Chrome."""

    platform = PLATFORM

    def __init__(self, *, repo: pathlib.Path | None = None, check_fn=None) -> None:
        super().__init__(repo=repo if repo is not None else REPO)
        self._check_fn = check_fn or (lambda: session.check(SITE))
        self._status = None
        # The page currently being driven, so queue() can put a screenshot on the card.
        self._page = None
        # True once the submit button has been clicked for the attempt in flight. Reset per
        # _do_publish call; while set, nothing is retried (see _do_publish).
        self._submitted = False

    # -- contract ---------------------------------------------------------------------

    def capabilities(self) -> dict:
        return {"platform": self.platform,
                "transport": "chrome-debug",
                "cdp_url": session.CDP_URL,
                "scheduling": True,
                "max_schedule_days": S.MAX_SCHEDULE_DAYS,
                "caption_max": S.CAPTION_MAX,
                "upload_url": S.UPLOAD_URL,
                "content_url": S.CONTENT_URL,
                "recurring_job": False,       # rule 1: Chrome is never on the recurring path
                "unverified": list(S.UNVERIFIED),
                "queue_dir": str(self.queue_dir())}

    def queue_dir(self) -> pathlib.Path:
        """Where this publisher's failure cards and their mp4s land."""
        return self.repo / "marketing" / "publish-queue" / QUEUE_SUBDIR

    def status(self):
        """The login preflight, once per publisher instance.

        Cached because a weekly batch makes one instance and schedules five to seven videos,
        and each check is a page open. It is not a hole: every navigation inside the driver
        re-classifies the URL it landed on, so a session that dies mid-batch still fails
        closed on the next goto rather than typing into a login wall.
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
            detail=(f"TikTok preflight failed: {status.detail} (requested "
                    f"{status.requested_url}, landed on {status.final_url}). Nothing was "
                    f"uploaded."))

    def publish(self, asset, meta: dict, dry_run: bool) -> PublishResult:
        result = super().publish(asset, meta, dry_run)
        if not dry_run:
            return result
        # Replace the base's generic dry-run sentence with the real plan: the schedule is the
        # part a reviewer needs to see before Saturday's batch goes live.
        #
        # A malformed schedule_at in meta.json surfaces as a not-ok result rather than an
        # exception: publish() is contractually a function that returns a result, and one bad
        # day of a batch must not take the week down with a traceback. Nothing is written —
        # a dry run that refuses has nothing to queue.
        try:
            plan = "; ".join(plan_lines(pathlib.Path(asset), meta))
        except ScheduleError as exc:
            return dataclasses.replace(result, ok=False, detail=f"dry-run REFUSED: {exc}")
        return dataclasses.replace(result, detail="dry-run: " + plan)

    def queue(self, asset: pathlib.Path, meta: dict, detail: str) -> PublishResult:
        """One card per failure, written by session.fail_card so redaction happens once.

        Deliberately not the base class's paste-ready card: what is needed here is a
        screenshot plus the numbered steps to finish the job by hand, and two cards for one
        failure is how a queue stops being read. The mp4 still lands beside the card.
        """
        detail = self.mask(detail)
        try:
            when = parse_schedule(meta.get("schedule_at"))
        except ScheduleError:
            when = None     # a card about a bad schedule must still be written
        asset = pathlib.Path(asset)
        card = session.fail_card(
            self.repo, self._page, subdir=QUEUE_SUBDIR,
            kind=self.platform, slug=base.card_slug(meta, asset), run_name=self.platform,
            title=f"Schedule {asset.name} on TikTok Studio by hand",
            detail=detail,
            steps=manual_steps(asset, meta, when))
        base.link_or_copy(asset, card.parent / asset.name)
        return PublishResult(platform=self.platform, ok=False, url=None,
                             queued_path=str(card.relative_to(self.repo)), detail=detail)

    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        """Open one traced page and drive it, with one retry (spec Chrome rule 7).

        **The submit click is the point of no return.** Both confirmation waits raise after
        the click — `expect_response` on `__exit__`, `wait_for_url` on the call — so "the
        retry is safe because drive() re-reads the list first" was wrong in the one direction
        that matters: TikTok processes a scheduled post asynchronously, the re-read can easily
        happen before the row exists, and the retry would then upload the video a second time.

        So `self._submitted` is set immediately before the click and nothing is retried once
        it is set. The flag is reset here, not in __init__, because schedule_week reuses one
        publisher for the whole week and day 2 must start clean.
        """
        self._submitted = False
        with session.open_page(self.platform, repo=self.repo) as page:
            self._page = page
            try:
                return self.drive(page, asset, meta)
            except (VerificationFailed, ScheduleError, ScheduleFieldError):
                # VerificationFailed: may already be live, see above. The other two are
                # deterministic — a malformed schedule and a picker that will not take its
                # value both fail the same way twice, so a retry only doubles the time to
                # the card, and the time a browser sits on the page mid-Saturday.
                raise
            except Exception as exc:  # noqa: BLE001 — one retry, then base.publish queues
                if self._submitted:
                    raise VerificationFailed(
                        f"{type(exc).__name__}: {exc} — this happened AFTER the "
                        f"{S.SCHEDULE_BUTTON_TEXT}/{S.POST_BUTTON_TEXT} button was clicked, "
                        f"so TikTok may have taken the post. NOT retrying: a second attempt "
                        f"would upload {pathlib.Path(asset).name} twice.") from exc
                print(f"{self.platform}: retrying once after "
                      f"{session.redact_secrets(f'{type(exc).__name__}: {exc}')[:160]}",
                      file=sys.stderr)
                return self.drive(page, asset, meta)

    # -- the driver -------------------------------------------------------------------

    def drive(self, page, asset: pathlib.Path, meta: dict) -> PublishResult:
        """read → skip-if-present → upload → re-read → assert."""
        when = parse_schedule(meta.get("schedule_at"))
        caption = caption_of(meta)
        key = caption_key(caption)
        if len(key) < MIN_KEY_LEN:
            raise ScheduleError(
                f"caption {caption!r} is too short to identify a post ({len(key)} < "
                f"{MIN_KEY_LEN} characters); it cannot be skipped safely on a re-run")

        hit = find_scheduled(self.read_scheduled(page), key, when)
        if hit:
            return PublishResult(
                platform=self.platform, ok=True, url=hit.get("url") or S.CONTENT_URL,
                queued_path=None,
                detail=(f"already scheduled — a post matching {key!r}"
                        + (f" on {format_date(when)}" if when else "")
                        + " is on the posts list; nothing uploaded"))

        self.upload(page, asset, caption, when)

        hit = find_scheduled(self.read_scheduled(page), key, when)
        if not hit:
            raise VerificationFailed(
                f"submitted {pathlib.Path(asset).name} but no row matching {key!r}"
                + (f" on {format_date(when)}" if when else "")
                + f" appeared on {S.CONTENT_URL}. NOT retrying: it may have gone through. "
                  f"Check the posts list by hand before running this day again.")
        return PublishResult(
            platform=self.platform, ok=True, url=hit.get("url") or S.CONTENT_URL,
            queued_path=None,
            detail=(f"scheduled {pathlib.Path(asset).name} for "
                    f"{format_date(when)} {format_time(when)}" if when else
                    f"posted {pathlib.Path(asset).name}"))

    def goto(self, page, url: str) -> None:
        """Navigate, then prove we are still the logged-in studio before touching anything."""
        page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        page.wait_for_load_state("domcontentloaded")
        status = session.classify(SITE, url, page.url)
        if not status.ok:
            raise SessionLost(f"{status.detail} (requested {url}, landed on {status.final_url})")

    def read_scheduled(self, page) -> list:
        """The live posts list. Read-only, and the only thing idempotency rests on.

        **Nothing is clicked here, on purpose.** An earlier version opened a "Scheduled" tab
        first, because the content page was believed to default to published posts. Live on
        2026-09-15 there is no such tab — `[role=tab]` matches 0 and the page's own empty
        state reads "Your posted and scheduled videos will appear here", one table for both.
        So the click had nothing to hit: it timed out on every read and queued a card instead
        of scheduling anything. `--check` now asserts the tab stays absent, and
        selectors_tiktok.CONTENT_HAS_SCHEDULED_TAB is the flag to flip if it returns.

        Two waits, in this order: the table itself (it renders whether or not the account has
        posts, so it is the honest "the page arrived" signal), then the list settling into
        either a row with text or the empty-state copy. The second without the first would
        read a blank page as an empty list, which schedules a duplicate of the whole batch.
        """
        self.goto(page, S.CONTENT_URL)
        page.locator(S.POSTS_TABLE).first.wait_for(state="attached",
                                                   timeout=ANCHOR_TIMEOUT_MS)
        page.wait_for_function(scheduled_ready_js(), timeout=LIST_TIMEOUT_MS)
        return check_rows_sane(page.evaluate(scheduled_rows_js()))

    def upload(self, page, asset: pathlib.Path, caption: str, when) -> None:
        if when is not None:
            check_within_limit(when)
        self.goto(page, S.UPLOAD_URL)
        # The file input is display:none (TikTok drives it from the "Select video" button),
        # so it is waited on ATTACHED, never visible. set_input_files does not need it shown.
        page.locator(S.FILE_INPUT).first.wait_for(state="attached",
                                                  timeout=ANCHOR_TIMEOUT_MS)
        page.set_input_files(S.FILE_INPUT, str(pathlib.Path(asset).resolve()))
        # None of the form exists before this line. Verified read-only on 2026-09-15: the bare
        # upload page carries one hidden file input and two data-e2e nodes, and zero rich-text
        # editors, switches or text inputs. So the wait for the caption box belongs AFTER the
        # file is handed over, and it takes the upload-length timeout rather than the anchor
        # one — it covers TikTok ingesting and processing the mp4, not just a render.
        #
        # The wait is on the editor the driver actually types into, not on a label beside it:
        # a reworded "Caption" heading would otherwise block a run whose form was fine.
        page.locator(S.CAPTION_EDITOR).first.wait_for(state="visible",
                                                      timeout=UPLOAD_TIMEOUT_MS)
        self.fill_caption(page, caption)
        if when is not None:
            self.enable_schedule(page)
            self.set_schedule(page, when)
        self.submit(page, when)

    def fill_caption(self, page, caption: str) -> None:
        """Clear TikTok's pre-filled caption (it seeds it from the file name), then type."""
        editor = page.locator(S.CAPTION_EDITOR).first
        editor.wait_for(state="visible", timeout=ANCHOR_TIMEOUT_MS)
        editor.click()
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(caption)

    def enable_schedule(self, page) -> None:
        """Turn the scheduler on only if it is off — read the state, then apply the diff.

        **The text path is guarded, and that guard is the point.** SCHEDULE_TOGGLE_TEXT and
        SCHEDULE_BUTTON_TEXT are the same word, "Schedule": if TikTok ever renders the
        scheduler's label inside a <button>, or sorts the submit button ahead of it, then
        "click the text Schedule" is "click the submit button". That would post the video
        immediately — and because this runs BEFORE `self._submitted` is set, the resulting
        failure is retried and the video goes up a second time. So the switch role is tried
        first, and the text match can only ever land on something that is not inside a button.
        """
        if page.locator(S.SCHEDULE_DATE_INPUT).count():
            return
        switch = page.locator(S.SCHEDULE_TOGGLE)
        target = (switch.first if switch.count()
                  else page.get_by_text(S.SCHEDULE_TOGGLE_TEXT, exact=True)
                           .locator(S.NOT_INSIDE_A_BUTTON).first)
        target.click()
        page.locator(S.SCHEDULE_DATE_INPUT).first.wait_for(
            state="visible", timeout=ANCHOR_TIMEOUT_MS)

    def set_schedule(self, page, when: dt.datetime) -> None:
        self.set_field(page, S.SCHEDULE_DATE_INPUT, format_date(when), str(when.day), "date")
        self.set_field(page, S.SCHEDULE_TIME_INPUT, format_time(when), format_time(when), "time")

    def set_field(self, page, selector: str, value: str, cell_text: str, what: str) -> None:
        """Type the value; if the input is a read-only picker, click the cell; else fail loud.

        Both branches end with the field's own value being read back, so "the click landed on
        something else" cannot pass as success — which for a scheduler means posting at the
        wrong hour, on a day nobody checks.
        """
        field = page.locator(selector).first
        field.wait_for(state="visible", timeout=ANCHOR_TIMEOUT_MS)
        field.click()
        field.fill(value)
        if (field.input_value() or "").strip() != value:
            page.get_by_text(cell_text, exact=True).first.click()
        if (field.input_value() or "").strip() != value:
            raise ScheduleFieldError(
                f"the {what} field would not take {value!r} (it reads "
                f"{(field.input_value() or '').strip()!r}). TikTok's picker markup has "
                f"changed: fix selectors_tiktok.{'SCHEDULE_DATE_INPUT' if what == 'date' else 'SCHEDULE_TIME_INPUT'}.")

    def submit(self, page, when) -> None:
        """Click Schedule/Post and wait on the response, then on the redirect.

        Two independent confirmations on purpose: POST_RESPONSE is UNVERIFIED, so if the
        fragment is wrong this times out — and BOTH waits raise after the click, which is why
        `self._submitted` is set first. From that line on, every failure is a card telling
        Stephen to look at the posts list; none of them is a retry.
        """
        label = S.SCHEDULE_BUTTON_TEXT if when is not None else S.POST_BUTTON_TEXT
        # exact=True, and it is not cosmetic. Playwright matches an accessible name as a
        # case-insensitive SUBSTRING by default, so name="Post" also matches the studio
        # sidebar's "Posts" nav entry — which sorts FIRST in the DOM, so `.first` would have
        # clicked the navigation instead of submitting, every single time a post-now run ran.
        button = page.get_by_role("button", name=label, exact=True).first
        button.wait_for(state="visible", timeout=ANCHOR_TIMEOUT_MS)
        with page.expect_response(
                lambda r: S.POST_RESPONSE in r.url and r.request.method == "POST",
                timeout=UPLOAD_TIMEOUT_MS):
            self._submitted = True      # point of no return — never re-upload past here
            button.click()
        page.wait_for_url(lambda url: S.CONTENT_URL in url, timeout=NAV_TIMEOUT_MS)


# ----------------------------------------------------------------------------- the CLI

def check(page, *, out=None) -> tuple[int, list[str]]:
    """Read-only: is the profile logged in, and does every anchor still resolve?

    Navigates, waits for each page's own ready anchor, and counts. It never clicks, types,
    selects a file or uploads: a canary that changes the view — or worse, starts an upload to
    see the post-file form — is a canary nobody trusts to run while something else is in
    flight. That is the whole reason the POST_FILE rows are reported rather than resolved.

    Three marks, and only one of them is a failure:
      OK              the anchor is on the page now.
      MISSING         it should be and is not — the selector drifted. Exit 1.
      post-file only  it cannot exist until a video is handed to TikTok, so nothing is
                      claimed either way. Never exit 1: this is the honest answer, and
                      printing MISSING for nine anchors every week trains Stephen to skim.
    An ABSENT row inverts the test: finding one is the failure, because it means TikTok
    brought back a UI the driver has been rewritten to do without.
    """
    lines: list[str] = []
    page.goto(S.STUDIO_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded")
    status = session.classify(SITE, S.STUDIO_URL, page.url)
    lines.append(f"{'login':<16} {'OK  ' if status.ok else 'FAIL'} {status.detail}")
    if not status.ok:
        return 1, lines
    rc = 0
    current = None
    for url, label, kind, value, stage in check_probes():
        if url != current:
            page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            page.wait_for_load_state("domcontentloaded")
            current = url
            probe_status = session.classify(SITE, url, page.url)
            if not probe_status.ok:
                lines.append(f"{'navigation':<16} FAIL {probe_status.detail}")
                return 1, lines
            # Settle on the page's own anchor before counting anything, or the probe races
            # the render and reports a slow page as a drifted selector.
            ready = PAGE_READY.get(url)
            if ready:
                try:
                    page.locator(ready).first.wait_for(state="attached",
                                                       timeout=ANCHOR_TIMEOUT_MS)
                except Exception as exc:  # noqa: BLE001 — report it, do not traceback
                    lines.append(f"{'page ready':<16} FAIL {ready!r} never appeared on "
                                 f"{url} ({type(exc).__name__})")
                    return 1, lines
        if stage == POST_FILE:
            lines.append(f"{label:<16} n/a  post-file only — {kind}={value!r} cannot be "
                         f"resolved without starting an upload")
            continue
        try:
            found = _probe_count(page, kind, value)
        except Exception as exc:  # noqa: BLE001 — a canary reports, it does not traceback
            found, exc_note = 0, f" ({type(exc).__name__})"
        else:
            exc_note = ""
        if stage == ABSENT:
            mark = "OK  " if not found else "CHANGED"
            rc |= 1 if found else 0
            lines.append(f"{label:<16} {mark} {kind} matched {found} (expected none — the "
                         f"posts list has no tabs){exc_note}")
            continue
        if stage == ROWS and not found:
            # No rows and the empty state showing is an empty account, not a drifted
            # selector. No rows and no empty state is the ambiguous read the driver refuses
            # to treat as "nothing is scheduled", so the canary refuses it too.
            empty = _probe_count(page, "body", S.SCHEDULED_EMPTY_TEXT)
            if empty:
                lines.append(f"{label:<16} n/a  account has no posts yet — "
                             f"{kind}={value!r} has no row to match")
                continue
            rc |= 1
            lines.append(f"{label:<16} MISSING {kind}={value!r} matched 0 and the list is "
                         f"not showing its empty state either{exc_note}")
            continue
        mark = "OK  " if found else "MISSING"
        rc |= 0 if found else 1
        lines.append(f"{label:<16} {mark} {kind}={value!r} matched {found}{exc_note}")
    return rc, lines


def main(argv=None, *, repo: pathlib.Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="Schedule a Short on TikTok Studio via Chrome.")
    ap.add_argument("--check", action="store_true",
                    help="read-only: login + every anchor resolves; changes nothing")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan; open no browser, write nothing")
    ap.add_argument("--asset", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    ap.add_argument("--schedule", help="ISO 8601 with offset, e.g. 2026-09-21T14:00:00-07:00")
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
    meta = json.loads(a.meta.read_text(encoding="utf-8"))
    if a.schedule:
        meta["schedule_at"] = a.schedule
    pub = TikTokWebPublisher(repo=repo)
    if a.dry_run:
        try:
            lines = plan_lines(a.asset, meta)
        except ScheduleError as exc:
            # The caller's own mistake, named: exit 2, never a traceback (publish.py does the
            # same for --schedule).
            print(f"REFUSING: {session.redact_secrets(exc)}", file=sys.stderr)
            return 2
        for line in lines:
            print(f"(dry-run) {line}")
        return 0
    result = pub.publish(a.asset, meta, dry_run=False)
    print(session.redact_secrets(
        f"{PLATFORM} {'ok  ' if result.ok else 'QUEUED'} "
        f"{result.url or result.queued_path}  {result.detail}"))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
