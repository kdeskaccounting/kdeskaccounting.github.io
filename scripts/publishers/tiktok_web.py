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

    read the Scheduled tab ─► this caption + this date already there? ─► skip, ok
                           └► no ─► upload, caption, schedule, submit ─► re-read ─► assert

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
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402  (scripts/ledger.py — one ISO-8601 reader for the whole repo)

from browser import selectors_tiktok as S  # noqa: E402
from browser import session  # noqa: E402
from publishers import base  # noqa: E402
from publishers.base import REPO, Publisher, PublishResult  # noqa: E402

PLATFORM = "tiktok_web"
SITE = "tiktok"
# The first N characters of the caption are the idempotency key. Long enough that two Shorts
# in a week cannot collide, short enough to survive the truncation the list applies.
KEY_LEN = 40
# Below this, a "key" is a stub that would prefix-match half the account. A caption this
# short means the meta is wrong, and skipping every day of the week is the failure mode.
MIN_KEY_LEN = 12
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
    """The Scheduled list rendered, but no row's caption could be read.

    Distinct from "nothing is scheduled": rows exist, so the markup drifted. Reading that as
    an empty list is what would schedule a second copy of every post in the batch.
    """


class SessionLost(RuntimeError):
    """A navigation landed on the login wall part-way through the flow."""


class VerificationFailed(RuntimeError):
    """The submit went through but the post is not on the Scheduled list.

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


def row_matches(row: dict, key: str, when: dt.datetime | None) -> bool:
    """Is this Scheduled-list row the post `key` + `when` describes?

    The row's caption is usually truncated with an ellipsis, so the test is "the shorter of
    the two is a prefix of the longer", floored at MIN_KEY_LEN characters so a stub can never
    match everything. When a schedule was asked for, the row's text must also carry that date
    — the same caption on two days is two different posts.
    """
    if len(_norm(key)) < MIN_KEY_LEN:
        return False
    key = _norm(key)
    caption = _norm(row.get("caption") or row.get("text") or "").rstrip("….")
    if len(caption) < MIN_KEY_LEN:
        return False
    shorter, longer = sorted((caption, key), key=len)
    if not longer.startswith(shorter):
        return False
    if when is None:
        return True
    text = _norm(row.get("text") or row.get("caption") or "")
    return any(variant in text for variant in date_variants(when))


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

    Built by concatenating repr()d constants rather than an f-string — the 2026-09-14 Gumroad
    outage was an f-string segment spliced onto a plain one, where `}}` stayed two literal
    braces. The two row selectors are tried in order and the first that matches anything
    wins; joining them with a comma would silently mix a table with a card grid.
    """
    sels = "[" + repr(S.POST_ROW) + "," + repr(S.POST_ROW_FALLBACK) + "]"
    return ("() => { let els = []; for (const s of " + sels + ") {"
            " els = [...document.querySelectorAll(s)]; if (els.length) break; }"
            " const rows = els.map(r => { const t = (r.innerText || '');"
            " const a = r.querySelector('a[href]');"
            " return {caption: (t.split('\\n').map(x => x.trim()).filter(Boolean)[0] || ''),"
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
    """
    sels = "[" + repr(S.POST_ROW) + "," + repr(S.POST_ROW_FALLBACK) + "]"
    return ("() => { for (const s of " + sels + ")"
            " for (const r of document.querySelectorAll(s))"
            " if (((r.innerText || '').trim()).length) return true;"
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
        f"Paste this caption: {caption}",
        f"Then {timing}",
        f"Confirm it appears under the '{S.SCHEDULED_TAB_TEXT}' tab at {S.CONTENT_URL}",
        "DO NOT re-run the scheduler for this day until you have looked at that tab — the "
        "post may have gone through after the failure, and a second run would upload it twice",
    ]


# ------------------------------------------------------------------------- the --check probes

def check_probes() -> tuple[tuple[str, str, str, str], ...]:
    """(page url, label, kind, value) for every anchor `--check` resolves, read-only.

    A table rather than code so the canary and the driver cannot disagree about what "the
    anchors resolve" means, and so a new anchor is one row.
    """
    return (
        (S.UPLOAD_URL, "file input", "css", S.FILE_INPUT),
        (S.UPLOAD_URL, "caption editor", "css", S.CAPTION_EDITOR),
        (S.UPLOAD_URL, "schedule toggle", "text", S.SCHEDULE_TOGGLE_TEXT),
        (S.UPLOAD_URL, "post button", "role", S.POST_BUTTON_TEXT),
        (S.CONTENT_URL, "scheduled tab", "text", S.SCHEDULED_TAB_TEXT),
        (S.CONTENT_URL, "post rows", "css", S.POST_ROW),
    )


def _resolve(page, kind: str, value: str):
    if kind == "css":
        return page.locator(value)
    if kind == "role":
        return page.get_by_role("button", name=value)
    return page.get_by_text(value, exact=True)


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
                "queue_dir": str(self.repo / "marketing" / "publish-queue" / "manual")}

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
        return dataclasses.replace(
            result, detail="dry-run: " + "; ".join(plan_lines(pathlib.Path(asset), meta)))

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
            self.repo, self._page,
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
            except VerificationFailed:
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
                        + " is on the Scheduled tab; nothing uploaded"))

        self.upload(page, asset, caption, when)

        hit = find_scheduled(self.read_scheduled(page), key, when)
        if not hit:
            raise VerificationFailed(
                f"submitted {pathlib.Path(asset).name} but no row matching {key!r}"
                + (f" on {format_date(when)}" if when else "")
                + f" appeared on {S.CONTENT_URL}. NOT retrying: it may have gone through. "
                  f"Check the Scheduled tab by hand before running this day again.")
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
        """The live Scheduled list. Read-only, and the only thing idempotency rests on.

        The tab click is load-bearing, not cosmetic: the content page opens on published
        posts, so reading whatever tab happens to be showing means a scheduled post is
        invisible to this check and every re-run uploads it again. Clicking an already-open
        tab is harmless; not clicking it is a duplicate.

        The settle-wait comes AFTER the click, because the click replaces the rows — waiting
        first would settle on the previous tab's list and then read the new one mid-swap.
        """
        self.goto(page, S.CONTENT_URL)
        tab = page.get_by_text(S.SCHEDULED_TAB_TEXT, exact=True).first
        tab.wait_for(state="visible", timeout=ANCHOR_TIMEOUT_MS)
        tab.click()
        page.wait_for_function(scheduled_ready_js(), timeout=LIST_TIMEOUT_MS)
        return check_rows_sane(page.evaluate(scheduled_rows_js()))

    def upload(self, page, asset: pathlib.Path, caption: str, when) -> None:
        if when is not None:
            check_within_limit(when)
        self.goto(page, S.UPLOAD_URL)
        page.set_input_files(S.FILE_INPUT, str(pathlib.Path(asset).resolve()))
        # The form only exists once TikTok has taken the file; this is the condition wait that
        # replaces "sleep until the upload finishes".
        page.get_by_text(S.UPLOAD_READY_TEXT, exact=False).first.wait_for(
            state="visible", timeout=UPLOAD_TIMEOUT_MS)
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
        """Turn the scheduler on only if it is off — read the state, then apply the diff."""
        if page.locator(S.SCHEDULE_DATE_INPUT).count() == 0:
            page.get_by_text(S.SCHEDULE_TOGGLE_TEXT, exact=True).first.click()
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
        Stephen to look at the Scheduled tab; none of them is a retry.
        """
        label = S.SCHEDULE_BUTTON_TEXT if when is not None else S.POST_BUTTON_TEXT
        button = page.get_by_role("button", name=label).first
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

    Navigates and counts. It never clicks, types or uploads — the Scheduled tab is *resolved*
    rather than opened, because a canary that changes the view is a canary nobody trusts to
    run while something else is in flight.
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
    for url, label, kind, value in check_probes():
        if url != current:
            page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            page.wait_for_load_state("domcontentloaded")
            current = url
            probe_status = session.classify(SITE, url, page.url)
            if not probe_status.ok:
                lines.append(f"{'navigation':<16} FAIL {probe_status.detail}")
                return 1, lines
        try:
            found = _resolve(page, kind, value).count()
        except Exception as exc:  # noqa: BLE001 — a canary reports, it does not traceback
            found, exc_note = 0, f" ({type(exc).__name__})"
        else:
            exc_note = ""
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
        for line in plan_lines(a.asset, meta):
            print(f"(dry-run) {line}")
        return 0
    result = pub.publish(a.asset, meta, dry_run=False)
    print(session.redact_secrets(
        f"{PLATFORM} {'ok  ' if result.ok else 'QUEUED'} "
        f"{result.url or result.queued_path}  {result.detail}"))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
