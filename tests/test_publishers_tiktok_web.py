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

import pytest

from publishers import tiktok_web as tw
from browser import selectors_tiktok as S

PT = dt.timezone(dt.timedelta(hours=-7))
WHEN = dt.datetime(2026, 9, 21, 14, 0, tzinfo=PT)
META = {"slug": "parksheet-day-1", "title": "Wait times fell 22% at Epcot",
        "description": "Epcot wait times fell 22% last week.", "tags": ["parks", "data"],
        "schedule_at": "2026-09-21T14:00:00-07:00"}


# --------------------------------------------------------------------------- the fake page

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

    def wait_for(self, **kw):
        self.page.calls.append(f"wait_for:{self.key}")

    def scroll_into_view_if_needed(self):
        self.page.calls.append(f"scroll:{self.key}")

    def click(self, **kw):
        self.page.calls.append(f"click:{self.key}")
        for hook in self.page.on_click.get(self.key, ()):
            hook()

    def fill(self, value):
        self.page.calls.append(f"fill:{self.key}={value}")
        if self.key not in self.page.readonly:
            self.page.values[self.key] = value

    def input_value(self):
        return self.page.values.get(self.key, "")


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
        self.readonly = set()
        self.on_click = {}
        self.shots = []
        self.url = url
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

    def get_by_role(self, role, name=None):
        return _Loc(self, f"role:{role}:{name}")

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


def _row(caption, when=WHEN, url=""):
    return {"caption": caption, "url": url,
            "text": f"{caption} Scheduled {when.strftime('%Y-%m-%d')} {when.strftime('%H:%M')}"}


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


def test_the_scheduler_is_not_toggled_again_when_the_date_field_is_already_showing(pub, asset):
    page = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    pub.drive(page, asset, META)
    assert f"click:text:{S.SCHEDULE_TOGGLE_TEXT}" not in page.calls

    page2 = _Page(rows_reads=[[], [_row(tw.caption_of(META))]])
    page2.counts[S.SCHEDULE_DATE_INPUT] = 0          # scheduler is off
    pub.drive(page2, asset, META)
    assert f"click:text:{S.SCHEDULE_TOGGLE_TEXT}" in page2.calls


def test_a_date_field_that_refuses_the_typed_value_falls_back_to_the_picker_then_raises(
        pub, asset):
    page = _Page(rows_reads=[[]])
    page.readonly.add(S.SCHEDULE_DATE_INPUT)         # a readonly picker input
    with pytest.raises(tw.ScheduleFieldError) as e:
        pub.drive(page, asset, META)
    assert "2026-09-21" in str(e.value)
    assert f"click:text:21" in page.calls, "the day cell is the documented fallback"


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
    cards = list((pub.repo / "marketing" / "publish-queue" / "manual").glob("*.md"))
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
    assert (pub.repo / "marketing" / "publish-queue" / "manual" / "day-1.mp4").exists()


def test_a_logged_out_profile_queues_before_the_browser_is_driven(tmp_path, asset,
                                                                  monkeypatch):
    out = tw.TikTokWebPublisher(repo=tmp_path, check_fn=lambda: tw.session.SiteStatus(
        "tiktok", False, S.STUDIO_URL, "https://www.tiktok.com/login", "not logged in"))
    monkeypatch.setattr(tw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("preflight must stop before any page is opened")))
    result = out.publish(asset, META, dry_run=False)
    assert result.ok is False
    card = next((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
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


def test_dry_run_still_refuses_an_unparseable_schedule(pub, asset):
    with pytest.raises(tw.ScheduleError):
        pub.publish(asset, {**META, "schedule_at": "next tuesday"}, dry_run=True)


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
