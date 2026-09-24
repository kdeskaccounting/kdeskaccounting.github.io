"""scripts/publishers/tiktok_web.py — the Chrome-driven TikTok Studio scheduler.

Playwright is absent in this suite (CLAUDE.md "Useful commands"), so the driver is exercised
against the same kind of fake page tests/test_gumroad_workflows_ui.py uses: every locator,
keyboard press and navigation is recorded, and the assertions are about the *sequence* of
calls and about pure functions that format and match.

What is being protected, in order of how much it would cost to get wrong:

1. **Idempotency.** Re-running the Saturday batch must not double-post. The driver reads the
   Scheduled list first and skips a caption+date that is already there.
2. **No double-upload after a submit.** A verification miss is NOT retried — the video may
   already be scheduled, and a second attempt would put two copies on the account. One
   retry, and only for failures before the submit click.
3. **Queues, not silent failures.** Any failure leaves one card naming the file, the caption
   and the schedule time, with no secret in it.
4. **--dry-run and --check touch nothing.**
"""
import datetime as dt
import json
import pathlib
import re

import pytest

from publishers import tiktok_web as tw
from browser import selectors_tiktok as S

PT = dt.timezone(dt.timedelta(hours=-7))
WHEN = dt.datetime(2026, 9, 21, 14, 0, tzinfo=PT)
META = {"slug": "parksheet-day-1", "title": "Wait times fell 22% at Epcot",
        "description": "Epcot wait times fell 22% last week.", "tags": ["parks", "data"],
        "schedule_at": "2026-09-21T14:00:00-07:00"}


# --------------------------------------------------------------------------- the fake page

class _FakeTimeout(Exception):
    """Stands in for playwright.sync_api.TimeoutError (not the builtin)."""


class _Loc:
    def __init__(self, page, key):
        self.page, self.key = page, key

    @property
    def first(self):
        return self

    def count(self):
        return self.page.counts.get(self.key, 1)

    def is_visible(self):
        return self.count() > 0

    def evaluate(self, js, *a):
        self.page.calls.append(f"evaluate:{self.key}")
        return None

    def get_attribute(self, name):
        return self.page.attrs.get((self.key, name))

    def check(self, **kw):
        self.page.calls.append(f"check:{self.key}")
        self.page.checked[self.key] = True

    def is_checked(self):
        return self.page.checked.get(self.key, False)

    def wait_for(self, **kw):
        self.page.calls.append(f"wait_for:{self.key}")
        # A locator that the fake says is absent (counts == 0) behaves like Playwright: the
        # wait times out. Only when a timeout was asked for, so existing tests that never set
        # a count keep their "everything is there" default.
        if kw.get("timeout") is not None and self.page.counts.get(self.key, 1) == 0:
            raise _FakeTimeout(f"Timeout {kw['timeout']}ms exceeded waiting for {self.key}")

    def locator(self, sel):
        """A chained locator, e.g. the not-inside-a-button guard on a text match."""
        return _Loc(self.page, f"{self.key}+{sel}")

    def nth(self, i):
        """A one-of-several-identical-matches locator (both schedule inputs share a selector)."""
        return _Loc(self.page, f"{self.key}#{i}")

    def filter(self, has_text=None):
        """Scoped-and-anchored text match, e.g. picking one timepicker option by its text."""
        tag = has_text.pattern if hasattr(has_text, "pattern") else has_text
        return _Loc(self.page, f"{self.key}|has_text={tag}")

    def scroll_into_view_if_needed(self):
        self.page.calls.append(f"scroll:{self.key}")

    def click(self, **kw):
        self.page.calls.append(f"click:{self.key}")
        for hook in self.page.on_click.get(self.key, ()):
            hook()

    def focus(self):
        self.page.calls.append(f"focus:{self.key}")

    def fill(self, value):
        self.page.calls.append(f"fill:{self.key}={value}")
        if self.key not in self.page.readonly:
            self.page.values[self.key] = value

    def input_value(self):
        return self.page.values.get(self.key, "")

    def text_content(self):
        return self.page.texts.get(self.key, "")


class _Keyboard:
    def __init__(self, page):
        self.page = page

    def type(self, text):
        self.page.calls.append(f"type:{text}")

    def press(self, key):
        self.page.calls.append(f"press:{key}")


class _Page:
    """Records every interaction; returns queued values for the two JS reads."""

    def __init__(self, rows_reads=(), url=S.STUDIO_URL, post_response_fails=False,
                 redirect_fails=False):
        self.calls = []
        self.counts = {}
        self.values = {}
        self.checked = {}
        self.attrs = {}
        self.texts = {}
        self.readonly = set()
        self.on_click = {}
        self.shots = []
        self.url = url
        # What --check's body probe reads. The live content page says "No posts yet"; the
        # constant is lowercased because that is how the driver tests it.
        self.body_text = "No posts yet Your posted and scheduled videos will appear here."
        # The live content page has zero [role=tab]; --check asserts that stays true, so the
        # fake has to agree or the canary reports a tab that does not exist.
        self.counts["role:tab:None~"] = 0
        # First-run modals ("Turn on automatic content checks?" etc.) are the exception to the
        # default-present convention below: most runs never see one, so dismiss_first_run_
        # dialogs must find nothing unless a test opts in by raising one of these back to 1.
        for _name in S.FIRST_RUN_DIALOG_BUTTONS:
            self.counts[f"role:button:{_name}"] = 0
        # The "too soon" warning is likewise absent by default — a test that wants to see
        # ScheduleFieldError raised for it sets this count back up.
        self.counts[f"text:{S.TOO_SOON_TEXT}"] = 0
        # The two read-only schedule inputs: one CSS selector, two elements, told apart by
        # value shape (see tiktok_web._locate_schedule_inputs). Defaults are pre-fill values
        # that are NOT WHEN's own date/time, so a driver that forgot to click the calendar or
        # the time picker would still fail the read-back assertion. Time-then-date matches the
        # DOM order seen live 2026-09-23.
        self.counts[S.SCHEDULE_DATE_INPUT] = 2
        self.values[f"{S.SCHEDULE_DATE_INPUT}#0"] = "19:10"
        self.values[f"{S.SCHEDULE_DATE_INPUT}#1"] = "2026-09-19"
        # The calendar header defaults to WHEN's own month, so a test that never cares about
        # month navigation does not have to wire it up. Tests that DO care override this.
        self.texts[S.CALENDAR_MONTH_TITLE] = WHEN.strftime("%B %Y")
        # Clicking the day cell / hour / minute for WHEN updates whichever of the two schedule
        # inputs CURRENTLY holds a value of the matching shape — not a fixed index, so the
        # wiring holds regardless of which one is "#0" and which is "#1" in a given test (see
        # test_the_date_and_time_inputs_are_told_apart_by_value_not_dom_order). Wired for WHEN
        # specifically since nearly every schedule test targets it; a test scheduling
        # something else, or wanting the click to have no effect, overrides these directly.
        def _update_matching(pattern, new_value):
            for idx in (0, 1):
                k = f"{S.SCHEDULE_DATE_INPUT}#{idx}"
                if re.match(pattern, self.values.get(k, "")):
                    self.values[k] = new_value
                    return
        self.on_click[f"{S.CALENDAR_DAY}|has_text=^{WHEN.day}$"] = [
            lambda: _update_matching(S.DATE_VALUE_RE, WHEN.strftime(S.DATE_FORMAT))]
        self.on_click[f"{S.TIME_HOUR_OPTION}|has_text=^{WHEN:%H}$"] = [
            lambda: _update_matching(S.TIME_VALUE_RE, WHEN.strftime(S.TIME_FORMAT))]
        self.on_click[f"{S.TIME_MINUTE_OPTION}|has_text=^{(WHEN.minute // 5) * 5:02d}$"] = [
            lambda: _update_matching(S.TIME_VALUE_RE, WHEN.strftime(S.TIME_FORMAT))]
        self.rows_reads = list(rows_reads)
        self.keyboard = _Keyboard(self)
        # Playwright raises these on __exit__ / on the call — i.e. AFTER the button was
        # clicked and TikTok may already have taken the post.
        self.post_response_fails = post_response_fails
        self.redirect_fails = redirect_fails

    # navigation ------------------------------------------------------------
    def goto(self, url, **kw):
        self.calls.append(f"goto:{url}")
        self.url = url

    def wait_for_load_state(self, *a, **kw):
        self.calls.append("load_state")

    def wait_for_url(self, *a, **kw):
        self.calls.append("wait_for_url")
        if self.redirect_fails:
            raise TimeoutError("Timeout 60000ms exceeded waiting for url")

    def wait_for_function(self, js, **kw):
        self.calls.append("wait_for_function")

    def evaluate(self, js, *a):
        self.calls.append("evaluate")
        value = self.rows_reads.pop(0) if self.rows_reads else []
        # The row reader returns {count, rows}: `count` is what the selector matched,
        # `rows` only those with text. A bare list in a test means "all of them had text".
        return value if isinstance(value, dict) else {"count": len(value), "rows": value}

    # locators --------------------------------------------------------------
    def locator(self, sel):
        return _Loc(self, sel)

    def get_by_role(self, role, name=None, exact=False):
        # `exact` is recorded, not ignored: matching an accessible name as a substring is
        # what made "Post" resolve to the sidebar's "Posts" entry.
        return _Loc(self, f"role:{role}:{name}" + ("" if exact else "~"))

    def inner_text(self, sel):
        self.calls.append(f"inner_text:{sel}")
        return self.body_text

    def get_by_text(self, text, exact=False):
        return _Loc(self, f"text:{text}")

    # writes ----------------------------------------------------------------
    def set_input_files(self, sel, path):
        self.calls.append(f"set_input_files:{pathlib.Path(path).name}")

    def expect_response(self, *a, **kw):
        import contextlib

        @contextlib.contextmanager
        def _cm():
            self.calls.append("expect_response")
            yield
            if self.post_response_fails:
                raise TimeoutError("Timeout 300000ms exceeded waiting for response")
        return _cm()

    def screenshot(self, path):
        self.shots.append(path)


def _row(caption, when=WHEN, url="", lead=()):
    """A row shaped the way scheduled_rows_js returns one: caption, every line, flat text.

    `lead` puts lines AHEAD of the caption — a duration badge or a status word — which is the
    case the caption-candidate scan exists for and a fixed line index would get wrong.
    """
    lines = [*lead, caption, "Scheduled",
             when.strftime("%Y-%m-%d"), when.strftime("%H:%M")]
    return {"caption": lines[0], "lines": lines, "url": url,
            "text": " ".join(lines)}


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "day-1.mp4"
    p.write_bytes(b"mp4")
    return p


@pytest.fixture
def pub(tmp_path):
    """A publisher whose repo is a tmp dir and whose login preflight passes."""
    return tw.TikTokWebPublisher(repo=tmp_path, check_fn=lambda: tw.session.SiteStatus(
        "tiktok", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))


# ------------------------------------------------------------------- pure: schedule parsing

def test_an_iso_stamp_with_an_offset_parses_to_that_instant():
    assert tw.parse_schedule("2026-09-21T14:00:00-07:00") == WHEN


def test_the_ledger_style_colon_free_offset_parses_too():
    """scripts/ledger.py stamps -0700; both readers must agree on one instant."""
    assert tw.parse_schedule("2026-09-21T14:00:00-0700") == WHEN


def test_a_naive_stamp_is_refused_rather_than_guessed():
    with pytest.raises(tw.ScheduleError) as e:
        tw.parse_schedule("2026-09-21T14:00:00")
    assert "offset" in str(e.value).lower()


def test_no_schedule_at_means_post_now_not_an_error():
    assert tw.parse_schedule(None) is None
    assert tw.parse_schedule("") is None


def test_a_schedule_past_the_studio_limit_is_refused_before_anything_is_typed():
    now = dt.datetime(2026, 9, 1, 9, 0, tzinfo=PT)
    far = dt.datetime(2026, 9, 30, 9, 0, tzinfo=PT)
    with pytest.raises(tw.ScheduleError) as e:
        tw.check_within_limit(far, now=now)
    assert str(S.MAX_SCHEDULE_DAYS) in str(e.value)
    assert tw.check_within_limit(dt.datetime(2026, 9, 8, 9, 0, tzinfo=PT), now=now) is None


def test_a_schedule_in_the_past_is_refused():
    now = dt.datetime(2026, 9, 21, 15, 0, tzinfo=PT)
    with pytest.raises(tw.ScheduleError) as e:
        tw.check_within_limit(WHEN, now=now)
    assert "past" in str(e.value).lower()


# ------------------------------------------------------------- pure: date/time formatting

def test_the_date_and_time_are_formatted_from_the_selector_constants():
    assert tw.format_date(WHEN) == "2026-09-21"
    assert tw.format_time(WHEN) == "14:00"
    assert tw.format_date(WHEN) == WHEN.strftime(S.DATE_FORMAT)
    assert tw.format_time(WHEN) == WHEN.strftime(S.TIME_FORMAT)


def test_the_time_is_twenty_four_hour_so_two_pm_never_reads_as_two_am():
    assert tw.format_time(dt.datetime(2026, 9, 21, 2, 5, tzinfo=PT)) == "02:05"
    assert tw.format_time(dt.datetime(2026, 9, 21, 14, 5, tzinfo=PT)) == "14:05"


def test_date_variants_cover_the_renderings_a_studio_row_might_use():
    variants = tw.date_variants(WHEN)
    for expected in ("2026-09-21", "9/21/2026", "sep 21", "september 21"):
        assert expected in variants, expected
    assert all(v == v.lower() for v in variants)


# ------------------------------------------------------------------- pure: the caption key

class _PWTimeout(Exception):
    """Stands in for playwright.sync_api.TimeoutError, which is not the builtin."""


def test_a_caption_editor_that_never_settles_is_focused_by_keyboard_instead():
    """2026-09-23: the editor resolved, was visible, and the click timed out on the
    stability check four runs in a row. The driver must fall back to focus and still type."""
    page = _Page()
    def unstable():
        raise _PWTimeout("Locator.click: Timeout 10000ms exceeded. waiting for element to be visible, enabled and stable")
    page.on_click[S.CAPTION_EDITOR] = [unstable]
    tw.TikTokWebPublisher().fill_caption(page, "hello world")
    assert f"focus:{S.CAPTION_EDITOR}" in page.calls
    assert page.calls.index(f"focus:{S.CAPTION_EDITOR}") < page.calls.index("press:Meta+A")
    assert "type:hello world" in page.calls


def test_a_caption_editor_that_clicks_normally_is_not_focused_twice():
    page = _Page()
    tw.TikTokWebPublisher().fill_caption(page, "hello")
    assert f"click:{S.CAPTION_EDITOR}" in page.calls
    assert f"focus:{S.CAPTION_EDITOR}" not in page.calls


def test_a_non_timeout_click_error_still_raises():
    page = _Page()
    def broken():
        raise RuntimeError("page closed")
    page.on_click[S.CAPTION_EDITOR] = [broken]
    with pytest.raises(RuntimeError):
        tw.TikTokWebPublisher().fill_caption(page, "hello")


def test_the_caption_is_the_description_plus_hashtags():
    caption = tw.caption_of(META)
    assert caption.startswith("Epcot wait times fell 22% last week.")
    assert "#parks" in caption and "#data" in caption


def test_a_multi_word_tag_becomes_one_hashtag():
    assert "#waittimes" in tw.caption_of({"description": "d", "tags": ["wait times"]}).lower()


def test_the_caption_falls_back_to_the_title_when_there_is_no_description():
    assert tw.caption_of({"title": "Only a title"}).startswith("Only a title")


def test_the_caption_is_capped_at_the_studio_limit():
    assert len(tw.caption_of({"description": "x" * 5000})) <= S.CAPTION_MAX


def test_the_key_is_the_first_forty_characters_normalised():
    key = tw.caption_key("  Epcot   wait times fell 22%   last week, and here is why  ")
    assert len(key) == 40
    assert key == key.lower()
    assert "  " not in key


# --------------------------------------------------------------- pure: matching a live row

def test_a_row_with_the_same_caption_and_date_matches():
    key = tw.caption_key(tw.caption_of(META))
    assert tw.find_scheduled([_row(tw.caption_of(META))], key, WHEN)


def test_a_row_truncated_with_an_ellipsis_still_matches():
    caption = tw.caption_of(META)
    truncated = caption[:28] + "…"
    assert tw.find_scheduled([_row(truncated)], tw.caption_key(caption), WHEN)


def test_the_same_caption_on_a_different_day_is_not_a_match():
    key = tw.caption_key(tw.caption_of(META))
    other = dt.datetime(2026, 9, 22, 14, 0, tzinfo=PT)
    assert tw.find_scheduled([_row(tw.caption_of(META), when=other)], key, WHEN) is None


def test_a_different_caption_on_the_same_day_is_not_a_match():
    key = tw.caption_key(tw.caption_of(META))
    assert tw.find_scheduled([_row("Something else entirely about Magic Kingdom")],
                             key, WHEN) is None


def test_a_stub_of_a_caption_never_matches_everything():
    """A too-short key would make the driver skip every day of the week."""
    assert tw.find_scheduled([_row("anything at all here")], "epcot", WHEN) is None


def test_rows_that_all_read_empty_raise_instead_of_reading_as_an_empty_list():
    """The Gumroad lesson: 'markup drifted' must never look like 'nothing is scheduled'."""
    with pytest.raises(tw.ScrapeError) as e:
        tw.check_rows_sane([{"caption": "", "text": ""}, {"caption": "  ", "text": " "}])
    assert "duplicate" in str(e.value).lower()


def test_a_genuinely_empty_list_is_fine():
    assert tw.check_rows_sane([]) == []


# ------------------------------------------------------------------------- the injected JS

def _balanced(js, opener, closer):
    depth = 0
    for ch in js:
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def test_the_row_reader_js_is_syntactically_balanced_and_built_from_the_constants():
    js = tw.scheduled_rows_js()
    assert js.count("{") == js.count("}")
    assert _balanced(js, "{", "}") and _balanced(js, "(", ")") and _balanced(js, "[", "]")
    assert S.POST_ROW in js and S.POST_ROW_FALLBACK in js
    assert js.startswith("() =>")


def test_the_row_reader_tries_the_fallback_only_when_the_row_role_finds_nothing():
    js = tw.scheduled_rows_js()
    assert js.index(repr(S.POST_ROW)) < js.index(repr(S.POST_ROW_FALLBACK))
    assert "break" in js


def test_the_ready_predicate_distinguishes_an_empty_list_from_an_unrendered_one():
    js = tw.scheduled_ready_js()
    assert S.SCHEDULED_EMPTY_TEXT in js
    assert S.POST_ROW in js
    assert _balanced(js, "{", "}") and _balanced(js, "(", ")")


# ------------------------------------------------------------------------- capabilities

def test_capabilities_reports_scheduling_and_the_unverified_ten_day_limit(pub):
    caps = pub.capabilities()
    assert caps["platform"] == "tiktok_web"
    assert caps["scheduling"] is True
    assert caps["max_schedule_days"] == 10
    assert "max_schedule_days" in caps["unverified"]
    assert json.dumps(caps, sort_keys=True)          # publish.py --capabilities prints this


def test_capabilities_makes_no_network_or_browser_call(tmp_path):
    """publish.py --capabilities instantiates every publisher; it must stay offline."""
    plain = tw.TikTokWebPublisher(repo=tmp_path, check_fn=lambda: (_ for _ in ()).throw(
        AssertionError("capabilities() must not preflight")))
    assert plain.capabilities()["transport"] == "chrome-debug"


# --------------------------------------------------------------------------- idempotency

def test_a_caption_already_on_the_scheduled_tab_is_skipped_without_uploading(pub, asset):
    page = _Page(rows_reads=[[_row(tw.caption_of(META))]])
    result = pub.drive(page, asset, META)
    assert result.ok is True
    assert "already scheduled" in result.detail
    assert not [c for c in page.calls if c.startswith("set_input_files")]
    assert page.calls.count("evaluate") == 1, "one read, no write, no second read"


def test_the_skip_reports_the_row_url_when_the_list_carries_one(pub, asset):
    page = _Page(rows_reads=[[_row(tw.caption_of(META), url="https://www.tiktok.com/@k/video/7")]])
    assert pub.drive(page, asset, META).url == "https://www.tiktok.com/@k/video/7"


def test_an_empty_scheduled_list_does_not_skip(pub, asset):
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    result = pub.drive(page, asset, META)
    assert result.ok is True
    assert "already scheduled" not in result.detail


# ------------------------------------------------------------------- the happy path

def test_the_full_call_sequence_reads_uploads_schedules_and_re_reads(pub, asset):
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    result = pub.drive(page, asset, META)

    assert result.ok is True
    assert result.url
    calls = page.calls
    order = [c for c in calls if c.startswith(("goto:", "set_input_files", "expect_response",
                                               "evaluate"))]
    assert order == [
        f"goto:{S.CONTENT_URL}",          # 1. read the Scheduled list
        "evaluate",
        f"goto:{S.UPLOAD_URL}",           # 2. upload
        "set_input_files:day-1.mp4",
        "expect_response",                # 3. submit, waiting on the response
        f"goto:{S.CONTENT_URL}",          # 4. re-read and assert
        "evaluate",
    ]
    assert "fill:" + S.SCHEDULE_DATE_INPUT + "=2026-09-21" in calls
    assert "fill:" + S.SCHEDULE_TIME_INPUT + "=14:00" in calls
    assert f"click:role:button:{S.SCHEDULE_BUTTON_TEXT}" in calls
    assert "wait_for_url" in calls


def test_the_caption_box_is_cleared_before_it_is_typed(pub, asset):
    """TikTok pre-fills the caption with the file name; typing over it would keep 'day-1'."""
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    pub.drive(page, asset, META)
    typed = page.calls.index(f"type:{tw.caption_of(META)}")
    assert "press:Meta+A" in page.calls[:typed]
    assert "press:Backspace" in page.calls[:typed]


def test_with_no_schedule_at_it_posts_now_and_never_touches_the_date_fields(pub, asset):
    meta = {k: v for k, v in META.items() if k != "schedule_at"}
    page = _Page(rows_reads=[[], [_row(tw.caption_of(meta))]])
    pub.drive(page, asset, meta)
    assert f"click:role:button:{S.POST_BUTTON_TEXT}" in page.calls
    assert not [c for c in page.calls if c.startswith("fill:" + S.SCHEDULE_DATE_INPUT)]


# 2026-09-23: "When to post" turned out not to be a switch but two <input type=radio>,
# labelled "Now" / "Schedule". A role-scoped radio lookup can never resolve to the <button>
# that submits (unlike the old switch/text guess), so there is no NOT_INSIDE_A_BUTTON-style
# guard to test any more — enable_schedule is just "click it if it isn't checked".

RADIO_KEY = f"role:radio:{S.SCHEDULE_RADIO_NAME}"


def test_the_schedule_radio_is_selected_through_its_label_when_it_is_not_checked():
    """The radio input is hidden behind a custom control; its <label for=…> is the click."""
    page = _Page()
    page.attrs[(RADIO_KEY, "id")] = "radio-x1"
    tw.TikTokWebPublisher().enable_schedule(page)
    assert "click:label[for='radio-x1']" in page.calls
    assert f"click:{RADIO_KEY}" not in page.calls


def test_the_schedule_radio_is_force_checked_when_it_has_no_label():
    page = _Page()
    tw.TikTokWebPublisher().enable_schedule(page)
    assert f"check:{RADIO_KEY}" in page.calls
    assert f"click:{RADIO_KEY}" not in page.calls


def test_the_schedule_radio_is_left_alone_when_already_checked():
    page = _Page()
    page.checked[RADIO_KEY] = True
    tw.TikTokWebPublisher().enable_schedule(page)
    assert f"click:{RADIO_KEY}" not in page.calls
    assert f"check:{RADIO_KEY}" not in page.calls


def test_enable_schedule_waits_for_the_date_input_after_the_radio_click():
    page = _Page()
    tw.TikTokWebPublisher().enable_schedule(page)
    assert (page.calls.index(f"check:{RADIO_KEY}")
            < page.calls.index(f"wait_for:{S.SCHEDULE_DATE_INPUT}"))


CONFIRM_KEY = f"role:button:{S.POST_CONFIRM_TEXT}"


def test_a_post_now_confirmation_is_clicked_after_the_post_button():
    page = _Page()
    tw.TikTokWebPublisher().submit(page, None)
    post_i = page.calls.index(f"click:role:button:{S.POST_BUTTON_TEXT}")
    assert f"click:{CONFIRM_KEY}" in page.calls
    assert post_i < page.calls.index(f"click:{CONFIRM_KEY}") < page.calls.index("wait_for_url")


def test_a_missing_post_now_confirmation_is_not_an_error():
    page = _Page()
    page.counts[CONFIRM_KEY] = 0          # the dialog never appears: wait_for times out
    tw.TikTokWebPublisher().submit(page, None)
    assert f"click:{CONFIRM_KEY}" not in page.calls
    assert "wait_for_url" in page.calls


def test_the_submit_button_is_resolved_exactly_not_as_a_substring(pub, asset):
    """`name="Post"` as a substring also matches the sidebar's "Posts" entry, which sorts
    first in the DOM — `.first` would have clicked the navigation instead of submitting."""
    meta = {k: v for k, v in META.items() if k != "schedule_at"}
    page = _Page(rows_reads=[[], [_row(tw.caption_of(meta))]])
    pub.drive(page, asset, meta)
    # the fake appends "~" to the key for a non-exact role lookup
    assert f"click:role:button:{S.POST_BUTTON_TEXT}" in page.calls
    assert f"click:role:button:{S.POST_BUTTON_TEXT}~" not in page.calls


# --------------------------------------------------------- set_schedule: the date/time pickers
#
# 2026-09-23: both fields are READ-ONLY `input.TUXTextInputCore-input` — `fill()` cannot set
# them — sharing one selector with no documented DOM order. set_schedule tells them apart by
# the shape of their current value (DATE_VALUE_RE / TIME_VALUE_RE), drives the calendar for
# the date and the hour/minute picker for the time, then reads both back.

HOUR_KEY = f"{S.TIME_HOUR_OPTION}|has_text=^{WHEN:%H}$"
MINUTE_KEY = f"{S.TIME_MINUTE_OPTION}|has_text=^{(WHEN.minute // 5) * 5:02d}$"
DAY_KEY = f"{S.CALENDAR_DAY}|has_text=^{WHEN.day}$"


def test_the_date_and_time_inputs_are_told_apart_by_value_not_dom_order():
    """The live DOM order was time-then-date; the driver must not depend on it."""
    page = _Page()
    page.values[f"{S.SCHEDULE_DATE_INPUT}#0"] = "2026-09-19"   # date first this time
    page.values[f"{S.SCHEDULE_DATE_INPUT}#1"] = "19:10"        # time second
    tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert page.values[f"{S.SCHEDULE_DATE_INPUT}#0"] == "2026-09-21"
    assert page.values[f"{S.SCHEDULE_DATE_INPUT}#1"] == "14:00"


def test_set_schedule_raises_when_no_input_value_matches_either_pattern():
    page = _Page()
    page.values[f"{S.SCHEDULE_DATE_INPUT}#0"] = "garbage"
    page.values[f"{S.SCHEDULE_DATE_INPUT}#1"] = "also garbage"
    with pytest.raises(tw.ScheduleFieldError) as e:
        tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert "DATE_VALUE_RE" in str(e.value) or "TIME_VALUE_RE" in str(e.value)


def test_the_hour_is_clicked_before_the_minute():
    page = _Page()
    tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert page.calls.index(f"click:{HOUR_KEY}") < page.calls.index(f"click:{MINUTE_KEY}")


def test_the_day_cell_is_clicked_only_once_the_month_title_matches():
    page = _Page()
    page.texts[S.CALENDAR_MONTH_TITLE] = "August 2026"        # one month behind WHEN
    page.on_click[S.CALENDAR_NEXT] = [
        lambda: page.texts.__setitem__(S.CALENDAR_MONTH_TITLE, WHEN.strftime("%B %Y"))]
    tw.TikTokWebPublisher().set_schedule(page, WHEN)
    calls = page.calls
    assert f"click:{S.CALENDAR_NEXT}" in calls
    assert f"click:{S.CALENDAR_PREV}" not in calls
    assert calls.index(f"click:{S.CALENDAR_NEXT}") < calls.index(f"click:{DAY_KEY}")


def test_the_prev_arrow_is_clicked_when_the_calendar_is_ahead_of_the_target_month():
    page = _Page()
    page.texts[S.CALENDAR_MONTH_TITLE] = "October 2026"       # one month ahead of WHEN
    page.on_click[S.CALENDAR_PREV] = [
        lambda: page.texts.__setitem__(S.CALENDAR_MONTH_TITLE, WHEN.strftime("%B %Y"))]
    tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert f"click:{S.CALENDAR_PREV}" in page.calls
    assert f"click:{S.CALENDAR_NEXT}" not in page.calls


def test_schedule_field_error_when_the_date_does_not_read_back():
    page = _Page()
    page.on_click[DAY_KEY] = []          # clicking the day cell has no effect this time
    with pytest.raises(tw.ScheduleFieldError) as e:
        tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert "date" in str(e.value) and "2026-09-21" in str(e.value)


def test_schedule_field_error_when_the_time_does_not_read_back():
    page = _Page()
    page.on_click[HOUR_KEY] = []
    page.on_click[MINUTE_KEY] = []       # neither picker click takes
    with pytest.raises(tw.ScheduleFieldError) as e:
        tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert "time" in str(e.value) and "14:00" in str(e.value)


def test_the_too_soon_warning_raises_once_both_fields_are_set():
    page = _Page()
    page.counts[f"text:{S.TOO_SOON_TEXT}"] = 1
    with pytest.raises(tw.ScheduleFieldError) as e:
        tw.TikTokWebPublisher().set_schedule(page, WHEN)
    assert S.TOO_SOON_TEXT in str(e.value)
    # both fields were still set before the warning was judged
    assert page.values[f"{S.SCHEDULE_DATE_INPUT}#1"] == "2026-09-21"
    assert page.values[f"{S.SCHEDULE_DATE_INPUT}#0"] == "14:00"


# --------------------------------------------------------------- dismiss_first_run_dialogs

def test_dismiss_first_run_dialogs_clicks_the_one_showing():
    page = _Page()
    page.counts["role:button:Allow"] = 1
    tw.dismiss_first_run_dialogs(page)
    assert page.calls == ["click:role:button:Allow"]


def test_dismiss_first_run_dialogs_does_nothing_when_none_are_showing():
    page = _Page()
    tw.dismiss_first_run_dialogs(page)
    assert page.calls == []


def test_dismiss_first_run_dialogs_never_clicks_post_or_discard():
    page = _Page()
    for name in S.FIRST_RUN_DIALOG_BUTTONS:
        page.counts[f"role:button:{name}"] = 1
    page.counts["role:button:Post"] = 1
    page.counts["role:button:Discard"] = 1
    tw.dismiss_first_run_dialogs(page)
    clicked = {c.rsplit(":", 1)[-1] for c in page.calls}
    assert clicked == set(S.FIRST_RUN_DIALOG_BUTTONS)
    assert "Post" not in clicked and "Discard" not in clicked


# ------------------------------------------------------- verification and the single retry

def test_a_post_that_never_appears_on_the_list_raises_and_is_not_retried(pub, asset):
    page = _Page(rows_reads=[[], []])
    with pytest.raises(tw.VerificationFailed):
        pub.drive(page, asset, META)


def test_do_publish_retries_once_and_only_once_before_the_submit(pub, asset, monkeypatch):
    attempts = []

    def flaky(page, a, m):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Timeout 30000ms exceeded")
        return tw.PublishResult(platform=tw.PLATFORM, ok=True, url=S.CONTENT_URL,
                                queued_path=None, detail="scheduled")

    monkeypatch.setattr(pub, "drive", flaky)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    assert pub._do_publish(asset, META).ok is True
    assert len(attempts) == 2


def test_a_second_failure_is_not_retried_a_third_time(pub, asset, monkeypatch):
    attempts = []

    def always(page, a, m):
        attempts.append(1)
        raise RuntimeError("Timeout 30000ms exceeded")

    monkeypatch.setattr(pub, "drive", always)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    with pytest.raises(RuntimeError):
        pub._do_publish(asset, META)
    assert len(attempts) == 2


def test_a_verification_failure_is_never_retried_because_it_may_already_be_live(
        pub, asset, monkeypatch):
    attempts = []

    def submitted(page, a, m):
        attempts.append(1)
        raise tw.VerificationFailed("submitted but not on the list")

    monkeypatch.setattr(pub, "drive", submitted)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    with pytest.raises(tw.VerificationFailed):
        pub._do_publish(asset, META)
    assert len(attempts) == 1, "a retry here would post the video twice"


def _fake_open_page(page):
    import contextlib

    @contextlib.contextmanager
    def _cm(*_a, **_k):
        yield page
    return _cm


# ----------------------------------------------------------------------- failure -> card

def test_a_failure_leaves_one_card_naming_the_file_the_caption_and_the_time(pub, asset,
                                                                            monkeypatch):
    page = _Page()
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("Timeout 30000ms exceeded waiting for input[type=file]")))

    result = pub.publish(asset, META, dry_run=False)

    assert result.ok is False
    cards = list((pub.repo / "marketing" / "publish-queue" / "tiktok").glob("*.md"))
    assert len(cards) == 1, "exactly one card, not one per layer"
    body = cards[0].read_text(encoding="utf-8")
    assert str(asset) in body
    assert tw.caption_of(META) in body
    assert "2026-09-21" in body and "14:00" in body
    assert "Timeout 30000ms exceeded" in body
    assert page.shots, "a screenshot goes with the card"
    assert result.queued_path and result.queued_path.endswith(".md")


def test_the_queued_card_gets_the_mp4_next_to_it(pub, asset, monkeypatch):
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    pub.publish(asset, META, dry_run=False)
    assert (pub.repo / "marketing" / "publish-queue" / "tiktok" / "day-1.mp4").exists()


def test_a_logged_out_profile_queues_before_the_browser_is_driven(tmp_path, asset,
                                                                  monkeypatch):
    out = tw.TikTokWebPublisher(repo=tmp_path, check_fn=lambda: tw.session.SiteStatus(
        "tiktok", False, S.STUDIO_URL, "https://www.tiktok.com/login", "not logged in"))
    monkeypatch.setattr(tw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("preflight must stop before any page is opened")))
    result = out.publish(asset, META, dry_run=False)
    assert result.ok is False
    card = next((tmp_path / "marketing" / "publish-queue" / "tiktok").glob("*.md"))
    text = card.read_text(encoding="utf-8")
    assert "not logged in" in text
    assert S.LOGIN_QR_TEXT in text, "the QR login is the step Stephen actually performs"


def test_no_secret_reaches_the_card(pub, asset, monkeypatch):
    monkeypatch.setenv("TIKTOK_SESSION_TOKEN", "tt_live_SUPERSECRET1")
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("failed with Authorization: Bearer tt_live_SUPERSECRET1")))
    result = pub.publish(asset, META, dry_run=False)
    card = pub.repo / result.queued_path
    assert "tt_live_SUPERSECRET1" not in card.read_text(encoding="utf-8")
    assert "tt_live_SUPERSECRET1" not in result.detail


# --------------------------------------------------------------------------- --dry-run

def test_dry_run_prints_the_plan_and_writes_nothing(pub, asset, monkeypatch, tmp_path):
    monkeypatch.setattr(tw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("--dry-run must not open a browser")))
    result = pub.publish(asset, META, dry_run=True)
    assert result.ok is True
    assert "dry-run" in result.detail
    assert "2026-09-21 14:00" in result.detail
    assert asset.name in result.detail
    assert not (tmp_path / "marketing").exists()
    assert not (tmp_path / "scripts").exists()


# MINOR 7. A bad schedule_at in meta.json escaped publish() as a ScheduleError, past the
# contract every caller relies on ("a publisher returns a result; it does not raise"). One
# malformed day of a batch would have taken down the whole week with a traceback.

def test_a_dry_run_reports_an_unparseable_schedule_instead_of_raising(pub, asset):
    result = pub.publish(asset, {**META, "schedule_at": "next tuesday"}, dry_run=True)
    assert result.ok is False
    assert "next tuesday" in result.detail
    assert result.queued_path is None, "a dry run writes nothing, not even a card"


def test_a_live_run_with_a_bad_schedule_queues_a_card_instead_of_raising(pub, asset,
                                                                         monkeypatch):
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page(rows_reads=[[]])))
    result = pub.publish(asset, {**META, "schedule_at": "next tuesday"}, dry_run=False)
    assert result.ok is False
    assert result.queued_path, "the day still needs a card a human can act on"


def test_the_cli_dry_run_exits_two_on_a_bad_schedule_without_a_traceback(tmp_path, asset,
                                                                         capsys):
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({**META, "schedule_at": "next tuesday"}), encoding="utf-8")
    rc = tw.main(["--dry-run", "--asset", str(asset), "--meta", str(meta)], repo=tmp_path)
    assert rc == 2
    assert "next tuesday" in capsys.readouterr().err


def test_the_cli_dry_run_opens_no_browser_and_writes_nothing(tmp_path, asset, monkeypatch,
                                                             capsys):
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps(META), encoding="utf-8")
    monkeypatch.setattr(tw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("--dry-run must not open a browser")))
    rc = tw.main(["--dry-run", "--asset", str(asset), "--meta", str(meta)], repo=tmp_path)
    assert rc == 0
    assert "(dry-run)" in capsys.readouterr().out
    assert not (tmp_path / "marketing").exists()


# ----------------------------------------------------------------------------- --check

def test_check_resolves_the_anchors_read_only(tmp_path, monkeypatch, capsys):
    page = _Page()
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(tw.session, "classify", lambda *a, **k: tw.session.SiteStatus(
        "tiktok", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))

    rc = tw.main(["--check"], repo=tmp_path)

    assert rc == 0
    out = capsys.readouterr().out
    assert "file input" in out and "scheduled tab" in out
    # read-only: it navigates and counts, and does nothing else
    forbidden = ("set_input_files", "click:", "fill:", "type:", "press:", "expect_response")
    assert not [c for c in page.calls if c.startswith(forbidden)], page.calls
    assert not (tmp_path / "marketing").exists()


def test_check_visits_both_the_upload_page_and_the_content_page(tmp_path, monkeypatch):
    page = _Page()
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(tw.session, "classify", lambda *a, **k: tw.session.SiteStatus(
        "tiktok", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))
    tw.main(["--check"], repo=tmp_path)
    gotos = [c for c in page.calls if c.startswith("goto:")]
    assert f"goto:{S.UPLOAD_URL}" in gotos
    assert f"goto:{S.CONTENT_URL}" in gotos


def test_check_reports_a_missing_anchor_and_exits_one(tmp_path, monkeypatch, capsys):
    page = _Page()
    page.counts[S.FILE_INPUT] = 0
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(tw.session, "classify", lambda *a, **k: tw.session.SiteStatus(
        "tiktok", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))
    assert tw.main(["--check"], repo=tmp_path) == 1
    assert "MISSING" in capsys.readouterr().out


def _check_out(tmp_path, monkeypatch, capsys, page):
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(tw.session, "classify", lambda *a, **k: tw.session.SiteStatus(
        "tiktok", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))
    rc = tw.main(["--check"], repo=tmp_path)
    return rc, capsys.readouterr().out


def test_check_says_post_file_only_instead_of_missing_for_the_form(tmp_path, monkeypatch,
                                                                   capsys):
    """The caption box and the scheduler cannot exist until a video is handed over.

    Reporting nine MISSING lines every week for anchors that CANNOT be there is how a canary
    stops being read — and seeing them would mean starting a real upload, which --check may
    not do.
    """
    page = _Page()
    for sel in (S.CAPTION_EDITOR, RADIO_KEY, S.SCHEDULE_DATE_INPUT, S.SCHEDULE_TIME_INPUT):
        page.counts[sel] = 0
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 0, "an anchor that cannot be resolved read-only is not a failure"
    for label in ("caption editor", "schedule radio", "schedule date", "schedule time",
                  "post button"):
        line = next(l for l in out.splitlines() if l.startswith(label))
        assert "post-file only" in line and "MISSING" not in line, line


def test_check_never_selects_a_file_or_starts_an_upload(tmp_path, monkeypatch, capsys):
    page = _Page()
    _check_out(tmp_path, monkeypatch, capsys, page)
    assert not [c for c in page.calls if c.startswith("set_input_files")]


def test_check_waits_for_each_page_before_counting_anything(tmp_path, monkeypatch, capsys):
    """A probe that races the render reports a slow page as a drifted selector.

    This is not hypothetical: a 2026-09-15 run that waited only on body text found
    FILE_INPUT missing on a page that had it a moment later.
    """
    page = _Page()
    _check_out(tmp_path, monkeypatch, capsys, page)
    calls = page.calls
    assert (calls.index(f"goto:{S.UPLOAD_URL}") < calls.index(f"wait_for:{S.UPLOAD_PAGE_READY}"))
    assert (calls.index(f"goto:{S.CONTENT_URL}") < calls.index(f"wait_for:{S.CONTENT_PAGE_READY}"))


def test_check_reports_an_empty_account_rather_than_calling_the_row_anchor_missing(
        tmp_path, monkeypatch, capsys):
    page = _Page()
    page.counts[S.POST_ROW] = 0                      # no posts on the account
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 0
    line = next(l for l in out.splitlines() if l.startswith("post rows"))
    assert "no posts yet" in line and "MISSING" not in line


def test_check_calls_the_row_anchor_missing_when_the_list_is_neither_empty_nor_readable(
        tmp_path, monkeypatch, capsys):
    """No rows AND no empty state is the ambiguous read the driver refuses to act on."""
    page = _Page()
    page.counts[S.POST_ROW] = 0
    page.body_text = "Posts (Created on) Privacy Views Likes Comments Actions"
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 1
    assert "MISSING" in next(l for l in out.splitlines() if l.startswith("post rows"))


def test_check_flags_a_scheduled_tab_coming_back_rather_than_ignoring_it(tmp_path, monkeypatch,
                                                                         capsys):
    """read_scheduled deliberately clicks nothing. If TikTok restores a tab, that breaks."""
    page = _Page()
    page.counts["role:tab:None~"] = 2                # TikTok put tabs back
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 1
    assert "CHANGED" in next(l for l in out.splitlines() if l.startswith("scheduled tab"))


def test_check_is_green_against_the_studio_as_it_looked_on_the_day_it_was_read(
        tmp_path, monkeypatch, capsys):
    """The fake page is shaped like the live 2026-09-15 studio: empty account, no tabs."""
    page = _Page()
    page.counts[S.POST_ROW] = 0
    for sel in (S.CAPTION_EDITOR, RADIO_KEY, S.SCHEDULE_DATE_INPUT, S.SCHEDULE_TIME_INPUT):
        page.counts[sel] = 0
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 0, out
    assert "MISSING" not in out and "CHANGED" not in out


def test_check_on_a_logged_out_profile_stops_at_the_login_and_queues(tmp_path, monkeypatch,
                                                                     capsys):
    page = _Page()
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(tw.session, "classify", lambda *a, **k: tw.session.SiteStatus(
        "tiktok", False, S.STUDIO_URL, "https://www.tiktok.com/login", "not logged in"))
    assert tw.main(["--check"], repo=tmp_path) == 1
    assert "not logged in" in capsys.readouterr().out
    assert f"goto:{S.UPLOAD_URL}" not in page.calls, "no point probing anchors behind a wall"


# ---------------------------------------------------------------- shape / house rules

def test_no_tiktok_anchor_is_retyped_inside_the_driver():
    src = pathlib.Path(tw.__file__).read_text(encoding="utf-8")
    for literal in ("input[type=file]", "contenteditable", "tiktokstudio/upload",
                    "tiktokstudio/content", "[role='row']"):
        assert literal not in src, f"{literal!r} belongs in selectors_tiktok.py"


def test_the_driver_imports_cleanly_without_playwright():
    src = pathlib.Path(tw.__file__).read_text(encoding="utf-8")
    top = src.split("\ndef ")[0]
    assert "import playwright" not in top and "from playwright" not in top


def test_there_are_no_fixed_sleeps_anywhere_in_the_driver():
    """Chrome rule 6: condition waits only."""
    src = pathlib.Path(tw.__file__).read_text(encoding="utf-8")
    for banned in ("wait_for_timeout", "time.sleep"):
        assert banned not in src, banned


# ======================================================================== fix round 1
#
# CRITICAL 1. Both confirmation waits raise AFTER the button was clicked — expect_response
# on __exit__, wait_for_url on the call — and _do_publish excluded only VerificationFailed,
# so each fell into the generic retry and re-ran drive(). The re-read that "makes the retry
# safe" happens before TikTok has finished processing the schedule, so the retry finds
# nothing and uploads the video a SECOND time. The click is now the point of no return.

def _uploads(page):
    return [c for c in page.calls if c.startswith("set_input_files")]


def _submit_clicks(page):
    return [c for c in page.calls if c.startswith("click:role:button:")]


def test_a_response_timeout_after_the_click_uploads_once_and_queues(pub, asset, monkeypatch):
    page = _Page(rows_reads=[[], [], []], post_response_fails=True)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))

    result = pub.publish(asset, META, dry_run=False)

    assert result.ok is False
    assert len(_uploads(page)) == 1, "the video must not be uploaded twice"
    assert len(_submit_clicks(page)) == 1
    cards = list((pub.repo / "marketing" / "publish-queue").rglob("*.md"))
    assert len(cards) == 1


def test_a_redirect_timeout_after_the_click_uploads_once_and_queues(pub, asset, monkeypatch):
    page = _Page(rows_reads=[[], [], []], redirect_fails=True)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))

    result = pub.publish(asset, META, dry_run=False)

    assert result.ok is False
    assert len(_uploads(page)) == 1
    assert len(_submit_clicks(page)) == 1


def test_the_card_for_a_post_submit_failure_says_it_may_already_be_live(pub, asset,
                                                                        monkeypatch):
    page = _Page(rows_reads=[[], [], []], post_response_fails=True)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=False)
    body = (pub.repo / result.queued_path).read_text(encoding="utf-8")
    assert "DO NOT re-run" in body
    assert "Timeout 300000ms exceeded" in result.detail


def test_a_failure_before_the_click_is_still_retried_once(pub, asset, monkeypatch):
    """The retry is not gone — only its reach past the click is."""
    page = _Page(rows_reads=[[], [], [_row(tw.caption_of(META))]])
    calls = []
    real_upload = pub.upload

    def flaky(page_, a, c, w):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Timeout 30000ms exceeded waiting for input")
        return real_upload(page_, a, c, w)

    monkeypatch.setattr(pub, "upload", flaky)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    assert pub.publish(asset, META, dry_run=False).ok is True
    assert len(calls) == 2


def test_the_submitted_flag_does_not_leak_between_days_of_a_batch(pub, asset, monkeypatch):
    """schedule_week reuses one publisher for the whole week; day 2 must start clean."""
    page1 = _Page(rows_reads=[[], [], []], post_response_fails=True)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page1))
    assert pub.publish(asset, META, dry_run=False).ok is False

    page2 = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page2))
    assert pub.publish(asset, META, dry_run=False).ok is True


# CRITICAL 2. The ambiguity guard was unreachable. The row reader ended `.filter(r => r.text)`,
# so textless rows vanished before check_rows_sane could see them, and the ready predicate
# returned true the moment ANY [role='row'] existed — a header or a skeleton row. The
# sequence header renders → ready → rows [] → no match → upload is a duplicate, arrived at
# through two "safe" checks that both said yes.

def test_a_skeleton_or_header_row_with_no_text_is_refused_not_read_as_empty():
    with pytest.raises(tw.ScrapeError) as e:
        tw.check_rows_sane({"count": 3, "rows": []})
    assert "3" in str(e.value)
    assert "duplicate" in str(e.value).lower()


def test_a_genuinely_empty_list_passes_through():
    assert tw.check_rows_sane({"count": 0, "rows": []}) == []


def test_rows_with_text_pass_through_unchanged():
    rows = [_row("Epcot wait times fell 22% last week. #parks #data")]
    assert tw.check_rows_sane({"count": 1, "rows": rows}) == rows


def test_the_reader_reports_what_the_selector_matched_not_only_what_had_text():
    js = tw.scheduled_rows_js()
    assert "count:" in js and "rows:" in js
    assert not js.rstrip().endswith(".filter(r => r.text); }"), \
        "filtering before the count is what made the guard unreachable"
    assert _balanced(js, "{", "}") and _balanced(js, "(", ")") and _balanced(js, "[", "]")


def test_the_ready_predicate_needs_a_row_with_text_not_merely_a_row():
    js = tw.scheduled_ready_js()
    assert "innerText" in js and "trim()" in js
    # The anti-pattern is the bare element count: a header or skeleton row matches the row
    # selector while the real rows are still loading.
    assert "querySelectorAll(s).length) return true" not in js, \
        "a textless row must not count as 'settled'"
    assert S.SCHEDULED_EMPTY_TEXT in js, "the empty-state copy is the other way to settle"


def test_the_ready_predicate_still_accepts_the_empty_state_copy():
    js = tw.scheduled_ready_js()
    assert "includes(" + repr(S.SCHEDULED_EMPTY_TEXT) + ")" in js


def test_a_skeleton_list_raises_before_anything_is_uploaded(pub, asset, monkeypatch):
    page = _Page(rows_reads=[{"count": 4, "rows": []}])
    with pytest.raises(tw.ScrapeError):
        pub.drive(page, asset, META)
    assert not _uploads(page), "an unreadable list must never lead to an upload"


def test_a_skeleton_list_is_not_retried_into_an_upload(pub, asset, monkeypatch):
    page = _Page(rows_reads=[{"count": 4, "rows": []}, {"count": 4, "rows": []}])
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=False)
    assert result.ok is False
    assert not _uploads(page)


# CRITICAL 3, revisited 2026-09-15. read_scheduled used to click a "Scheduled" tab first,
# on the belief that the content page defaulted to published posts. Live, that tab does not
# exist: [role=tab] matches 0 on the content page and TikTok's own empty state reads "Your
# posted and scheduled videos will appear here" — one table for both. The click therefore hit
# nothing, timed out on EVERY read, and queued a card instead of scheduling anything. The read
# is now navigate-and-read, and these tests hold it to that.

def test_the_list_read_clicks_nothing_at_all(pub, asset):
    """There is no tab to open, so a click here can only land on something unintended."""
    page = _Page(rows_reads=[[]])
    pub.read_scheduled(page)
    assert not [c for c in page.calls if c.startswith("click:")], page.calls


def test_the_posts_table_is_waited_for_before_the_list_is_read(pub, asset):
    """The table renders whether or not the account has posts, so it is the arrival signal.

    Without it a blank page settles straight to "no rows", which reads as "nothing is
    scheduled" and schedules a duplicate of every post in the batch.
    """
    page = _Page(rows_reads=[[]])
    pub.read_scheduled(page)
    calls = page.calls
    assert (calls.index(f"goto:{S.CONTENT_URL}")
            < calls.index(f"wait_for:{S.POSTS_TABLE}")
            < calls.index("wait_for_function")
            < calls.index("evaluate"))


def test_both_list_reads_in_a_full_run_wait_for_the_table(pub, asset):
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    pub.drive(page, asset, META)
    assert len([c for c in page.calls if c == f"wait_for:{S.POSTS_TABLE}"]) == 2


def test_the_caption_editor_is_waited_for_after_the_file_not_before(pub, asset):
    """The whole form is post-file: the bare upload page has no editor to wait on.

    Waiting first is not a slow no-op, it is a guaranteed timeout — which is why the wait
    moved after set_input_files and took the upload-length budget with it.
    """
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    pub.drive(page, asset, META)
    calls = page.calls
    assert (calls.index("set_input_files:day-1.mp4")
            < calls.index(f"wait_for:{S.CAPTION_EDITOR}")
            < calls.index(f"type:{tw.caption_of(META)}"))


def test_the_file_input_is_waited_for_attached_because_it_is_hidden(pub, asset):
    """TikTok's input[type=file] is display:none and driven by the Select video button."""
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    pub.drive(page, asset, META)
    calls = page.calls
    assert (calls.index(f"wait_for:{S.FILE_INPUT}")
            < calls.index("set_input_files:day-1.mp4"))


# IMPORTANT 5. POST_ROW_FALLBACK was "main li", which matches nav and menu items, and the
# match was two-way ("the shorter of the two is a prefix of the longer"). Together those let
# a menu entry stand in for a scheduled post and produce a false SKIP — the day silently
# never gets posted. The direction is now fixed: the key must be a prefix of the row, and the
# only exception is a row TikTok itself marked as truncated with an ellipsis.

NAV_ROW = {"caption": "Upload video", "text": "Upload video", "url": ""}
LONG_CAPTION = "Upload video: how we cut Epcot waits in half this week"


def test_a_nav_item_does_not_match_a_longer_caption_key():
    key = tw.caption_key(LONG_CAPTION)
    assert tw.row_matches(NAV_ROW, key, None) is False
    assert tw.find_scheduled([NAV_ROW], key, None) is None


def test_a_nav_row_cannot_stand_in_for_a_post_in_the_other_direction_either():
    """The reverse pairing is caught by the date, not by the prefix rule.

    A short key that is a prefix of a longer row is the *designed* match — the key is the
    first 40 characters of the caption, and the row carries the whole thing. So what rules a
    menu entry out when the roles are swapped is the second half of row_matches: a scheduled
    post's row carries its date, and 'Upload video' never does.
    """
    assert tw.row_matches(NAV_ROW, tw.caption_key(LONG_CAPTION), WHEN) is False
    assert tw.row_matches(NAV_ROW, tw.caption_key("Upload video"), WHEN) is False
    # ...and without a date to check, the floor on key length is the only guard left, which
    # is why drive() refuses to run at all with a caption this short.
    assert len(tw.caption_key("Epcot")) < tw.MIN_KEY_LEN


def test_a_full_row_whose_caption_starts_with_the_key_still_matches():
    caption = tw.caption_of(META)
    assert tw.find_scheduled([_row(caption)], tw.caption_key(caption), WHEN)


def test_a_row_tiktok_truncated_with_an_ellipsis_still_matches():
    """The one two-way case, and it is explicit: TikTok says the text is cut off."""
    caption = tw.caption_of(META)
    for marker in ("…", "..."):
        assert tw.find_scheduled([_row(caption[:28] + marker)],
                                 tw.caption_key(caption), WHEN), marker


def test_a_short_row_with_no_ellipsis_is_not_treated_as_truncated():
    caption = tw.caption_of(META)
    short = {"caption": caption[:20], "text": f"{caption[:20]} Scheduled 2026-09-21 14:00"}
    assert tw.find_scheduled([short], tw.caption_key(caption), WHEN) is None


def test_an_ellipsis_row_still_has_to_be_long_enough_to_identify_anything():
    caption = tw.caption_of(META)
    stub = {"caption": "Ep…", "text": "Ep… Scheduled 2026-09-21 14:00"}
    assert tw.find_scheduled([stub], tw.caption_key(caption), WHEN) is None


def test_the_caption_is_found_even_when_it_is_not_the_first_line_of_the_row():
    """A duration badge or a status word ahead of the caption must not defeat the match.

    No real Studio row has ever been read, so betting on line 0 is a bet that, if lost,
    re-uploads a video that is already scheduled.
    """
    caption = tw.caption_of(META)
    row = _row(caption, lead=("0:32", "Public"))
    assert row["caption"] == "0:32", "precondition: the caption is not line 0 here"
    assert tw.find_scheduled([row], tw.caption_key(caption), WHEN) is row


def test_a_row_whose_lines_are_all_furniture_still_does_not_match():
    row = {"caption": "0:32", "lines": ["0:32", "Public", "Scheduled"],
           "text": "0:32 Public Scheduled 2026-09-21 14:00"}
    assert tw.find_scheduled([row], tw.caption_key(tw.caption_of(META)), WHEN) is None


def test_the_candidate_scan_still_requires_the_date_when_one_was_asked_for():
    caption = tw.caption_of(META)
    other = dt.datetime(2026, 9, 28, 14, 0, tzinfo=PT)
    assert tw.find_scheduled([_row(caption, lead=("0:32",))],
                             tw.caption_key(caption), other) is None


def test_caption_candidates_dedupes_and_drops_blanks():
    row = {"caption": "Same", "lines": ["Same", "", "  ", "Other"], "text": "Same Other"}
    assert tw.caption_candidates(row) == ("same", "other")


def test_caption_candidates_falls_back_to_the_flat_text_when_there_are_no_lines():
    row = {"caption": "", "lines": [], "text": "Epcot wait times fell 22% last week."}
    assert tw.caption_candidates(row) == ("epcot wait times fell 22% last week.",)


def test_the_row_reader_asks_for_the_lines_the_candidate_scan_needs():
    js = tw.scheduled_rows_js()
    assert "lines:" in js and "POST_ROW_MAX_LINES" not in js
    assert repr(S.POST_ROW_MAX_LINES) in js


def test_the_row_reader_survives_a_selector_the_browser_will_not_parse():
    """POST_ROW uses :not(:has(...)). One unsupported selector must fall through, not throw."""
    js = tw.scheduled_rows_js()
    assert "try {" in js and "catch" in js
    assert tw.scheduled_ready_js().count("try {") >= 1


def test_the_row_fallback_selector_excludes_navigation():
    """The old fallback was "main li", which matched the studio menu entries.

    Live on 2026-09-15 the studio has no list items and no ARIA rows at all, and its sidebar
    is built from buttons — so a row-role fallback cannot reach the menu the way "main li"
    could. What must never come back is a fallback that matches ordinary page furniture.
    """
    assert S.POST_ROW_FALLBACK != "main li"
    assert " li" not in S.POST_ROW_FALLBACK
    assert "row" in S.POST_ROW_FALLBACK


# IMPORTANT 6. capabilities() advertised publish-queue/tiktok/ while session.fail_card wrote
# every card into publish-queue/manual/. A queue nobody looks in is the same as no queue.

def test_the_card_lands_in_the_queue_dir_capabilities_advertises(pub, asset, monkeypatch):
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    result = pub.publish(asset, META, dry_run=False)
    advertised = pathlib.Path(pub.capabilities()["queue_dir"])
    assert (pub.repo / result.queued_path).parent == advertised
    assert advertised.name == "tiktok"


def test_the_mp4_lands_beside_the_card_in_that_same_dir(pub, asset, monkeypatch):
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    pub.publish(asset, META, dry_run=False)
    assert (pathlib.Path(pub.capabilities()["queue_dir"]) / "day-1.mp4").exists()


# MINOR 8. A deterministic failure produces the same failure twice. Retrying a bad schedule
# or a picker that will not take its value just doubles the time to the card, and doubles the
# time a browser sits on the page during a supervised Saturday run.

@pytest.mark.parametrize("exc", [
    tw.ScheduleError("schedule_at 'next tuesday' is not an ISO-8601 timestamp"),
    tw.ScheduleFieldError("the date field would not take '2026-09-21'"),
])
def test_a_deterministic_failure_is_attempted_once(pub, asset, monkeypatch, exc):
    attempts = []

    def boom(*_a, **_k):
        attempts.append(1)
        raise exc

    monkeypatch.setattr(pub, "drive", boom)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    assert pub.publish(asset, META, dry_run=False).ok is False
    assert len(attempts) == 1


def test_a_racy_read_of_the_list_is_still_retried(pub, asset, monkeypatch):
    """ScrapeError can be a raced render, and retrying it uploads nothing."""
    attempts = []

    def flaky(page, a, m):
        attempts.append(1)
        if len(attempts) == 1:
            raise tw.ScrapeError("matched 4 rows, none with text")
        return tw.PublishResult(platform=tw.PLATFORM, ok=True, url=S.CONTENT_URL,
                                queued_path=None, detail="scheduled")

    monkeypatch.setattr(pub, "drive", flaky)
    monkeypatch.setattr(tw.session, "open_page", _fake_open_page(_Page()))
    assert pub.publish(asset, META, dry_run=False).ok is True
    assert len(attempts) == 2


# ======================================================================== fix round 2
#
# date_variants matched by raw substring, and "sep 1" is inside "sep 10" (as 2 is inside 20-29
# and 3 inside 30-31, and "1 sep" inside "21 sep"). On its own that is a near miss; combined
# with the ellipsis exception it is a silent lost post. ParkSheet's captions share a long
# templated prefix, so a row genuinely scheduled Sep 10 — truncated mid-prefix by TikTok —
# satisfies the caption half of row_matches for a video targeted at Sep 1, and then the date
# half agrees too. The day is reported as "already scheduled" and never posted. Entirely
# reachable inside the 10-day window, where both days are always in the same list.

TEMPLATE = "ParkSheet daily: wait times, crowd levels and ride downtime across the Orlando parks"


def _dated_row(caption, when, *, truncate=None):
    """A row rendered the way a Studio list shows a month name, not an ISO stamp."""
    shown = f"{caption[:truncate]}…" if truncate else caption
    return {"caption": shown, "url": "",
            "text": f"{shown} Scheduled {when.strftime('%b %-d')} {when.strftime('%Y')} 14:00"}


def _pt(day):
    # October, because it has 31 days: the 3-vs-31 pair has to be a real date.
    return dt.datetime(2026, 10, day, 14, 0, tzinfo=PT)


@pytest.mark.parametrize("early,late", [(1, 10), (1, 19), (2, 20), (2, 29), (3, 30), (3, 31)])
def test_a_single_digit_day_does_not_match_a_two_digit_one(early, late):
    """The core of it: 'sep 1' must not be found inside 'sep 10'."""
    key = tw.caption_key(f"{TEMPLATE} — video for the {early}st")
    row = _dated_row(f"{TEMPLATE} — video for the {late}th", _pt(late))
    assert tw.row_matches(row, key, _pt(early)) is False


@pytest.mark.parametrize("early,late", [(1, 10), (2, 20), (3, 30)])
def test_the_ellipsis_exception_does_not_reopen_the_substring_hole(early, late):
    """The reported reproduction: shared 40-char prefix + a row TikTok truncated mid-prefix."""
    key_b = tw.caption_key(f"{TEMPLATE} — B")
    row_a = _dated_row(f"{TEMPLATE} — A", _pt(late), truncate=38)
    assert tw.row_matches(row_a, key_b, _pt(early)) is False
    assert tw.find_scheduled([row_a], key_b, _pt(early)) is None


@pytest.mark.parametrize("day", [1, 2, 3, 10, 20, 30])
def test_the_row_for_the_day_actually_targeted_still_matches(day):
    key = tw.caption_key(f"{TEMPLATE} — B")
    row = _dated_row(f"{TEMPLATE} — B", _pt(day), truncate=38)
    assert tw.row_matches(row, key, _pt(day)) is True


def test_a_two_digit_day_still_matches_its_own_row():
    key = tw.caption_key(f"{TEMPLATE} — B")
    assert tw.row_matches(_dated_row(f"{TEMPLATE} — B", _pt(10)), key, _pt(10)) is True


def test_a_leading_digit_cannot_borrow_a_day_either():
    """'1 oct' sits inside '21 oct', so the guard has to hold on both sides."""
    key = tw.caption_key(f"{TEMPLATE} — B")
    row = {"caption": f"{TEMPLATE} — B", "url": "",
           "text": f"{TEMPLATE} — B Scheduled 21 Oct 2026 14:00"}
    assert tw.row_matches(row, key, _pt(1)) is False
    assert tw.row_matches(row, key, _pt(21)) is True


def test_every_variant_is_searched_on_a_token_boundary():
    """Not one guarded variant and five raw ones: the rule applies to the whole set."""
    for variant in tw.date_variants(_pt(1)):
        assert tw.date_in_text(f"scheduled {variant} 14:00", _pt(1)) is True
        assert tw.date_in_text(f"scheduled {variant}0 14:00", _pt(1)) is False
        assert tw.date_in_text(f"scheduled 9{variant} 14:00", _pt(1)) is False


def test_the_iso_and_slash_renderings_still_match():
    for text in ("scheduled 2026-10-01 14:00", "scheduled 10/1/2026 14:00",
                 "scheduled 10/01/2026 14:00", "scheduled october 1 14:00"):
        assert tw.date_in_text(text, _pt(1)) is True
