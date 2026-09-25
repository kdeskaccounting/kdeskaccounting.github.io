"""scripts/publishers/youtube_web.py — the Chrome-driven YouTube Studio publisher.

Playwright is absent in this suite (CLAUDE.md "Useful commands"), so the driver is exercised
against the same kind of fake page tests/test_publishers_tiktok_web.py uses: every locator,
keyboard press and navigation is recorded, and the assertions are about the *sequence* of
calls and about the pure functions that match and format.

What is being protected, in order of how much it would cost to get wrong:

1. **The channel guard.** The debug Chrome profile holds Stephen's personal channel as well
   as ParkSheet, and a Short posted to the wrong one cannot be moved. Nothing — not a check,
   not a dry run, not a publish — touches the uploader before the channel is confirmed.
2. **Idempotency.** Re-running a day must not double-post. The driver reads the content list
   (BOTH tabs) first and skips a title that is already there.
3. **No double-upload after Publish.** A verification miss is NOT retried — the video may
   already be live. One retry, and only for failures before the click.
4. **A dry run leaves no draft.** It uploads for real, so it must delete what it leaves, and
   it must refuse to delete anything that is not a draft.
5. **The description reaches YouTube verbatim.** It carries licence-required attribution.
6. **Queues, not silent failures**, with no secret in the card.
"""
import json
import pathlib

import pytest

from publishers import youtube_web as yw
from browser import selectors_youtube as S

TITLE = "Horizons let riders vote on how their ride would end"
DESC = ("Horizons let riders vote on how their ride would end.\n\n"
        "Powered by Queue-Times.com https://queue-times.com/\n"
        "Not affiliated with or endorsed by The Walt Disney Company or Universal.")
META = {"slug": "parksheet-2026-W38-day-6", "title": TITLE, "description": DESC,
        "tags": ["themeparks", "disney"]}


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

    def is_enabled(self):
        return self.page.enabled.get(self.key, True)

    def is_checked(self):
        return self.page.checked.get(self.key, False)

    def evaluate(self, js, *a):
        self.page.calls.append(f"evaluate:{self.key}")
        return None

    def get_attribute(self, name):
        return self.page.attrs.get((self.key, name))

    def check(self, **kw):
        self.page.calls.append(f"check:{self.key}")
        self.page.checked[self.key] = True

    def wait_for(self, **kw):
        self.page.calls.append(f"wait_for:{self.key}:{kw.get('state', '')}")
        state = kw.get("state")
        if state in ("hidden", "detached"):
            # A key in `sticky` is an element that refuses to go away.
            if kw.get("timeout") is not None and self.key in self.page.sticky:
                raise _FakeTimeout(f"Timeout waiting for {self.key} to {state}")
            return
        if kw.get("timeout") is not None and self.page.counts.get(self.key, 1) == 0:
            raise _FakeTimeout(f"Timeout waiting for {self.key}")

    def locator(self, sel):
        return _Loc(self.page, f"{self.key}+{sel}")

    def nth(self, i):
        return _Loc(self.page, f"{self.key}#{i}")

    def filter(self, has_text=None):
        tag = has_text.pattern if hasattr(has_text, "pattern") else has_text
        return _Loc(self.page, f"{self.key}|has_text={tag}")

    def get_by_role(self, role, name=None, exact=False):
        return _Loc(self.page, f"{self.key}+role:{role}:{name}" + ("" if exact else "~"))

    def hover(self):
        self.page.calls.append(f"hover:{self.key}")

    def click(self, **kw):
        if self.key in self.page.click_timeouts and not kw.get("force"):
            self.page.calls.append(f"click-timeout:{self.key}")
            raise _FakeTimeout(f"Timeout {kw.get('timeout')}ms exceeded")
        self.page.calls.append(f"click:{self.key}" + (":force" if kw.get("force") else ""))
        for hook in self.page.on_click.get(self.key, ()):
            hook()

    def focus(self):
        self.page.calls.append(f"focus:{self.key}")

    def input_value(self):
        return self.page.values.get(self.key, "")

    def text_content(self):
        return self.page.texts.get(self.key, "")

    def inner_text(self):
        return self.page.texts.get(self.key, "")


class _Keyboard:
    def __init__(self, page):
        self.page = page

    def press(self, key):
        self.page.calls.append(f"press:{key}")

    def type(self, text, **kw):
        self.page.calls.append(f"type:{text[:24]}")

    def insert_text(self, text):
        self.page.calls.append(f"insert_text:{text[:24]}")
        self.page.inserted.append(text)
        # Whatever was inserted becomes what the box reads back, unless a test says otherwise.
        for key in (S.TITLE_BOX, S.DESCRIPTION_BOX):
            if self.page.focus_box == key and key not in self.page.lossy_boxes:
                self.page.texts[key] = text


class _Page:
    """Records every interaction; returns queued values for the row reads."""

    def __init__(self, rows_reads=(), url=S.STUDIO_URL):
        self.calls = []
        self.counts = {}
        self.values = {}
        self.texts = {}
        self.attrs = {}
        self.checked = {}
        self.enabled = {}
        self.on_click = {}
        self.sticky = set()
        self.click_timeouts = set()
        self.lossy_boxes = set()
        self.inserted = []
        self.focus_box = None
        self.shots = []
        self.url = url
        self.body_text = "No content available"
        # Which channel id a navigation lands on. A test overrides it to stand on someone
        # else's channel without having to fight goto() for the url.
        self.url_channel = S.CHANNEL_ID
        self.keyboard = _Keyboard(self)
        # Signed in as ParkSheet, on the ParkSheet channel URL. Tests that want the wrong
        # channel override one or both.
        self.texts[S.CHANNEL_NAME_TEXT] = S.CHANNEL_NAME
        self.url = f"{S.STUDIO_URL}/channel/{S.CHANNEL_ID}"
        # The uploader's own text carries the video link from the moment the upload lands.
        self.texts[S.UPLOAD_DIALOG] = "Video link https://youtube.com/shorts/Oxo41KgeVoA"
        # The one-time "anyone can see" notice is absent by default; a test opts in.
        self.counts[f"role:button:{S.GOT_IT_BUTTON_TEXT}"] = 0
        # So is the unanswered-audience warning, once the radio has been clicked.
        self.counts[f"text={S.KIDS_UNANSWERED_TEXT}"] = 0
        # The delete confirmation says what a DRAFT delete says, unless a test changes it.
        self.texts[S.DELETE_CONFIRM_BUTTON] = S.DELETE_DRAFT_CONFIRM_TEXT
        self.rows_reads = list(rows_reads)

    # navigation ------------------------------------------------------------
    def goto(self, url, **kw):
        self.calls.append(f"goto:{url}")
        self.url = url if self.url_channel in url else f"{url}?c={self.url_channel}"

    def wait_for_load_state(self, *a, **kw):
        self.calls.append("load_state")

    def wait_for_function(self, js, **kw):
        self.calls.append("wait_for_function")

    def evaluate(self, js, *a):
        self.calls.append("evaluate")
        value = self.rows_reads.pop(0) if self.rows_reads else []
        return value if isinstance(value, dict) else {"count": len(value), "rows": value}

    # locators --------------------------------------------------------------
    def locator(self, sel):
        if sel in (S.TITLE_BOX, S.DESCRIPTION_BOX):
            self.focus_box = sel
        return _Loc(self, sel)

    def get_by_role(self, role, name=None, exact=False):
        return _Loc(self, f"role:{role}:{name}" + ("" if exact else "~"))

    def get_by_text(self, text, exact=False):
        return _Loc(self, f"text:{text}")

    def inner_text(self, sel):
        self.calls.append(f"inner_text:{sel}")
        return self.body_text

    # writes ----------------------------------------------------------------
    def set_input_files(self, sel, path):
        self.calls.append(f"set_input_files:{pathlib.Path(path).name}")

    def screenshot(self, path):
        self.shots.append(path)


def _row(title, visibility=S.PUBLIC_VISIBILITY_TEXT, href="/video/MZUo3q8ENaM/edit"):
    lines = ["0:39", title, "—", visibility, "Sep 25, 2026", "Published", "22", "1"]
    return {"title": title, "visibility": visibility, "href": href,
            "lines": lines, "text": " ".join(lines)}


def _fake_open_page(page):
    import contextlib

    @contextlib.contextmanager
    def _cm(*_a, **_k):
        yield page
    return _cm


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "day-6.mp4"
    p.write_bytes(b"mp4")
    return p


@pytest.fixture
def pub(tmp_path):
    """A publisher whose repo is a tmp dir and whose login preflight passes."""
    return yw.YouTubeWebPublisher(repo=tmp_path, check_fn=lambda: yw.session.SiteStatus(
        "youtube", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))


def _driven(pub, page, asset, meta=None, monkeypatch=None):
    """Run drive() against `page` and return the result."""
    return pub.drive(page, asset, meta or META)


# ------------------------------------------------------------------ pure: title and meta

def test_the_title_is_stephens_copy_verbatim():
    assert yw.title_of(META) == TITLE


def test_the_description_is_verbatim_and_never_gets_hashtags_appended():
    """The tags field exists; the description is NOT where they go.

    Unlike TikTok, YouTube has its own tag field, and the description carries the
    Queue-Times / ThemeParks.wiki / photo-credit lines the licences require. Appending a
    hashtag wall to it would alter copy that a fact-check pass approved.
    """
    got = yw.description_of(META)
    assert got == DESC.rstrip()
    assert "#themeparks" not in got
    assert "Powered by Queue-Times.com" in got


def test_a_title_over_the_youtube_limit_is_refused_not_truncated():
    with pytest.raises(yw.TitleTooLong) as exc:
        yw.check_title("x" * (S.TITLE_MAX + 1))
    assert "Refusing to truncate" in str(exc.value)


def test_a_title_at_the_limit_is_fine():
    yw.check_title("y" * S.TITLE_MAX)


def test_a_stub_of_a_title_is_refused_because_it_could_not_be_skipped_safely():
    with pytest.raises(yw.TitleTooLong):
        yw.check_title("day 6")


# --------------------------------------------------------------- pure: row matching

def test_a_row_with_exactly_this_title_matches():
    assert yw.title_matches(_row(TITLE), TITLE)


def test_two_parksheet_days_sharing_a_prefix_do_not_match_each_other():
    a = "Hidden Detail Monday — Pirates of the Caribbean was a wax museum"
    b = "Hidden Detail Monday — A web of tunnels connects Magic Kingdom"
    assert not yw.title_matches(_row(a), b)
    assert not yw.title_matches(_row(b), a)


def test_a_row_youtube_truncated_with_an_ellipsis_still_matches():
    assert yw.title_matches(_row(TITLE[:30] + "…"), TITLE)


def test_a_short_row_with_no_ellipsis_is_not_treated_as_truncated():
    assert not yw.title_matches(_row(TITLE[:30]), TITLE)


def test_an_ellipsis_row_still_has_to_be_long_enough_to_identify_anything():
    assert not yw.title_matches(_row("Hori…"), TITLE)


def test_the_title_is_found_even_when_it_is_not_the_title_node():
    """innerText line order is YouTube's decision; equality keeps that from loosening anything."""
    row = {"title": "", "visibility": "Public", "lines": ["0:39", TITLE, "Public"],
           "text": f"0:39 {TITLE} Public"}
    assert yw.title_matches(row, TITLE)


def test_a_row_of_pure_furniture_never_matches():
    row = {"title": "", "visibility": "", "lines": ["0:39", "Public", "22"], "text": "0:39"}
    assert not yw.title_matches(row, TITLE)


def test_visibility_is_read_off_the_row():
    assert yw.is_public(_row(TITLE))
    assert not yw.is_public(_row(TITLE, S.DRAFT_VISIBILITY_TEXT))
    assert yw.is_draft(_row(TITLE, S.DRAFT_VISIBILITY_TEXT))


def test_a_pending_row_counts_as_a_draft_because_that_is_what_it_becomes():
    """Caught live 2026-09-25: a just-closed upload reads "Pending" before it says "Draft".

    Under the old rule the dry run refused to delete its own upload and left it on the
    channel — the one thing a dry run must never do.
    """
    assert yw.is_draft(_row(TITLE, S.DRAFT_PENDING_TEXT))
    assert not yw.is_public(_row(TITLE, S.DRAFT_PENDING_TEXT))


# ------------------------------------------------------------------- pure: the row reader

def test_rows_that_all_read_empty_raise_instead_of_reading_as_an_empty_list():
    with pytest.raises(yw.ScrapeError):
        yw.check_rows_sane({"count": 3, "rows": []})


def test_a_genuinely_empty_list_is_fine():
    assert yw.check_rows_sane({"count": 0, "rows": []}) == []


def test_rows_with_text_pass_through_unchanged():
    rows = [_row(TITLE)]
    assert yw.check_rows_sane({"count": 1, "rows": rows}) == rows


def test_the_row_reader_js_is_syntactically_balanced_and_built_from_the_constants():
    js = yw.rows_js()
    assert js.count("{") == js.count("}")
    assert js.count("(") == js.count(")")
    assert repr(S.VIDEO_ROW) in js and repr(S.ROW_TITLE) in js and repr(S.ROW_VISIBILITY) in js


def test_the_ready_predicate_distinguishes_an_empty_tab_from_an_unrendered_one():
    js = yw.rows_ready_js()
    assert js.count("{") == js.count("}")
    assert repr(S.CONTENT_EMPTY_TEXT) in js
    assert "innerText" in js       # a row must carry TEXT, not merely exist


def test_the_row_present_predicate_is_valid_js_and_quotes_the_title_safely():
    """ParkSheet titles carry em dashes and apostrophes; repr() would not survive them."""
    title = "Hidden Detail Monday — it's a \"quote\" \\ backslash"
    js = yw.row_present_js(title)
    assert js.count("{") == js.count("}")
    assert js.count("(") == js.count(")")
    assert repr(S.VIDEO_ROW) in js and repr(S.ROW_TITLE) in js
    # The literal must survive as the NORMALISED title when JS (or JSON) reads it back.
    literal = js.split("const want = ", 1)[1].split(";", 1)[0]
    assert json.loads(literal) == title.lower()


def test_the_row_present_predicate_compares_normalised_titles():
    literal = yw.row_present_js("  Horizons   Ride  ").split("const want = ", 1)[1].split(";", 1)[0]
    assert json.loads(literal) == "horizons ride"


def test_the_enabled_predicate_asks_about_aria_disabled():
    js = yw.enabled_js(S.NEXT_BUTTON)
    assert repr(S.NEXT_BUTTON) in js and "aria-disabled" in js


# ------------------------------------------------------------------- pure: the video id

def test_the_video_id_is_read_out_of_a_shorts_link():
    assert yw.video_id_from("Video link https://youtube.com/shorts/Oxo41KgeVoA") == "Oxo41KgeVoA"


def test_a_watch_link_and_a_youtu_be_link_work_too():
    assert yw.video_id_from("https://www.youtube.com/watch?v=Oxo41KgeVoA") == "Oxo41KgeVoA"
    assert yw.video_id_from("https://youtu.be/Oxo41KgeVoA") == "Oxo41KgeVoA"


def test_no_link_means_no_id_rather_than_a_wrong_one():
    assert yw.video_id_from("Processing will begin shortly") is None


def test_a_draft_row_with_no_link_falls_back_to_the_content_list(pub):
    row = _row(TITLE, S.DRAFT_VISIBILITY_TEXT, href=None)
    assert pub.row_url(row) == S.CONTENT_URL


def test_a_published_row_yields_its_own_watch_url(pub):
    assert pub.row_url(_row(TITLE)) == S.WATCH_URL.format(video_id="MZUo3q8ENaM")


# --------------------------------------------------------------------- the channel guard

def test_the_wrong_channel_refuses_before_anything_is_opened(pub):
    page = _Page()
    page.texts[S.CHANNEL_NAME_TEXT] = "Stephen Michels"
    with pytest.raises(yw.WrongChannel) as exc:
        pub.assert_channel(page)
    assert S.CHANNEL_NAME in str(exc.value)
    assert not [c for c in page.calls if c.startswith("set_input_files")]


def test_the_right_name_on_the_wrong_channel_id_still_refuses(pub):
    """Two independent tests, because a deep link could carry a stale id under the right name."""
    page = _Page()
    page.url_channel = "UCsomeoneelseschannel"
    with pytest.raises(yw.WrongChannel) as exc:
        pub.assert_channel(page)
    assert S.CHANNEL_ID in str(exc.value)


def test_the_parksheet_channel_passes(pub):
    assert pub.assert_channel(_Page()) == S.CHANNEL_NAME


def test_a_wrong_channel_is_never_retried(pub, asset, monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise yw.WrongChannel("nope")
    monkeypatch.setattr(pub, "drive", boom)
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_Page()))
    result = pub.publish(asset, META, dry_run=False)
    assert calls == [1]
    assert not result.ok


# ----------------------------------------------------------------------- idempotency

def test_a_title_already_on_the_channel_is_skipped_without_uploading(pub, asset):
    page = _Page(rows_reads=[[_row(TITLE)], []])
    result = _driven(pub, page, asset)
    assert result.ok
    assert "already published" in result.detail
    assert not [c for c in page.calls if c.startswith("set_input_files")]


def test_the_skip_reports_the_videos_own_url(pub, asset):
    page = _Page(rows_reads=[[_row(TITLE)], []])
    assert _driven(pub, page, asset).url.endswith("MZUo3q8ENaM")


def test_both_content_tabs_are_read_before_anything_is_uploaded(pub, asset):
    """A Short lands on the Shorts tab; which tab YouTube files it under is its call, not ours."""
    page = _Page(rows_reads=[[], [_row(TITLE)]])
    result = _driven(pub, page, asset)
    assert result.ok and "already published" in result.detail
    gotos = [c for c in page.calls if c.startswith("goto:")]
    assert f"goto:{S.CONTENT_SHORTS_URL}" in gotos
    assert f"goto:{S.CONTENT_VIDEOS_URL}" in gotos


def test_a_leftover_draft_is_refused_not_read_as_already_published(pub, asset):
    """A draft is not a published video, and it is not a skip either.

    Read as "already published" the day silently never goes up; ignored, the upload runs again
    and the channel ends up with two rows of the same title.
    """
    page = _Page(rows_reads=[[_row(TITLE, S.DRAFT_VISIBILITY_TEXT, href=None)], []])
    with pytest.raises(yw.DraftInTheWay) as exc:
        _driven(pub, page, asset)
    assert "not a skip" in str(exc.value)
    assert not [c for c in page.calls if c.startswith("set_input_files")]


def test_a_pending_leftover_is_refused_too(pub, asset):
    page = _Page(rows_reads=[[_row(TITLE, S.DRAFT_PENDING_TEXT, href=None)], []])
    with pytest.raises(yw.DraftInTheWay):
        _driven(pub, page, asset)


def test_a_draft_in_the_way_is_never_retried(pub, asset, monkeypatch):
    page = _Page(rows_reads=[[_row(TITLE, S.DRAFT_VISIBILITY_TEXT, href=None)], []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=False)
    assert not result.ok and result.queued_path
    assert page.calls.count("evaluate") == 2      # one read of each tab, not two rounds


def test_a_dry_run_also_refuses_a_leftover_draft_rather_than_uploading_beside_it(
        pub, asset, monkeypatch):
    page = _Page(rows_reads=[[_row(TITLE, S.DRAFT_VISIBILITY_TEXT, href=None)], []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert not result.ok
    assert "DRAFT" in result.detail
    assert not [c for c in page.calls if c.startswith("set_input_files")]


def test_the_card_tells_a_human_how_to_clear_a_leftover_draft(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    result = pub.publish(asset, META, dry_run=False)
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert S.DELETE_MENU_ITEM_TEXT in card


def test_an_empty_channel_does_not_skip(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    result = _driven(pub, page, asset)
    assert result.ok
    assert "published" in result.detail and "already" not in result.detail
    uploads = [c for c in page.calls if c.startswith("set_input_files")]
    assert uploads == ["set_input_files:day-6.mp4"]


def test_a_skeleton_list_raises_before_anything_is_uploaded(pub, asset):
    page = _Page(rows_reads=[{"count": 4, "rows": []}])
    with pytest.raises(yw.ScrapeError):
        _driven(pub, page, asset)
    assert not [c for c in page.calls if c.startswith("set_input_files")]


# -------------------------------------------------------------------------- the upload

def test_the_full_call_sequence_reads_uploads_fills_and_re_reads(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    result = _driven(pub, page, asset)
    assert result.ok
    calls = page.calls
    assert calls.index(f"goto:{S.CONTENT_SHORTS_URL}") < calls.index("set_input_files:day-6.mp4")
    assert calls.index("set_input_files:day-6.mp4") < calls.index(f"insert_text:{TITLE[:24]}")
    assert calls.index(f"insert_text:{TITLE[:24]}") < calls.index(f"click:{S.DONE_BUTTON}")


def test_the_file_input_is_waited_for_attached_because_it_is_hidden(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert f"wait_for:{S.FILE_INPUT}:attached" in page.calls
    assert f"wait_for:{S.FILE_INPUT}:visible" not in page.calls


def test_the_title_box_is_waited_for_after_the_file_not_before(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert (page.calls.index("set_input_files:day-6.mp4")
            < page.calls.index(f"wait_for:{S.TITLE_BOX}:visible"))


def test_both_boxes_are_cleared_before_they_are_filled(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert page.calls.count("press:Meta+A") == 2
    assert page.calls.count("press:Backspace") == 2


def test_the_description_is_inserted_verbatim_including_its_newlines(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert DESC.rstrip() in page.inserted
    # insert_text, never type: keyboard.type turns a newline into Enter.
    assert not [c for c in page.calls if c.startswith("type:")]


def test_a_box_that_never_settles_is_focused_by_keyboard_instead(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    page.click_timeouts.add(S.TITLE_BOX)
    _driven(pub, page, asset)
    assert f"focus:{S.TITLE_BOX}" in page.calls


def test_a_box_that_loses_its_text_raises_rather_than_publishing_a_broken_description(pub, asset):
    page = _Page(rows_reads=[[], []])
    page.lossy_boxes.add(S.DESCRIPTION_BOX)
    page.texts[S.DESCRIPTION_BOX] = "Horizons let riders"
    with pytest.raises(yw.FormFieldError) as exc:
        _driven(pub, page, asset)
    assert "description" in str(exc.value)


def test_made_for_kids_is_answered_no(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert f"click:role:radio:{S.KIDS_NO_NAME}" in page.calls
    assert f"click:role:radio:{S.KIDS_YES_NAME}" not in page.calls


def test_the_unanswered_warning_must_clear_before_next_is_clicked(pub, asset):
    """Next is enabled but does nothing while the audience question is open (seen 2026-09-25)."""
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert (page.calls.index(f"wait_for:text={S.KIDS_UNANSWERED_TEXT}:hidden")
            < page.calls.index(f"click:{S.NEXT_BUTTON}"))


def test_next_is_clicked_three_times_and_each_step_arrival_is_asserted(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert page.calls.count(f"click:{S.NEXT_BUTTON}") == 3
    for step in (S.STEP_ELEMENTS, S.STEP_CHECKS, S.STEP_VISIBILITY):
        assert f"wait_for:{S.step_selected(step)}:attached" in page.calls


def test_a_step_that_never_arrives_stops_rather_than_clicking_past_it(pub, asset):
    page = _Page(rows_reads=[[], []])
    page.counts[S.step_selected(S.STEP_CHECKS)] = 0
    with pytest.raises(yw.FormFieldError) as exc:
        _driven(pub, page, asset)
    assert S.STEP_NAMES[S.STEP_CHECKS] in str(exc.value)


# -------------------------------------------------------------------------- visibility

def test_public_is_selected_by_the_radios_name_attribute(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert f"click:{S.PUBLIC_RADIO}" in page.calls
    assert f"click:{S.PRIVATE_RADIO}" not in page.calls


def test_a_radio_behind_the_notice_backdrop_gets_a_forced_click(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    page.click_timeouts.add(S.PUBLIC_RADIO)
    _driven(pub, page, asset)
    assert f"click:{S.PUBLIC_RADIO}:force" in page.calls


def test_the_anyone_can_see_notice_is_dismissed_when_it_appears(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    page.counts[f"role:button:{S.GOT_IT_BUTTON_TEXT}"] = 1
    _driven(pub, page, asset)
    assert f"click:role:button:{S.GOT_IT_BUTTON_TEXT}" in page.calls


def test_a_missing_notice_is_not_an_error(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    assert _driven(pub, page, asset).ok
    assert f"click:role:button:{S.GOT_IT_BUTTON_TEXT}" not in page.calls


def test_the_video_id_is_captured_before_publish_is_clicked(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    _driven(pub, page, asset)
    assert pub._video_id == "Oxo41KgeVoA"


# ------------------------------------------------------------------------ verification

def test_a_video_that_never_appears_on_the_list_raises_and_is_not_retried(pub, asset):
    page = _Page(rows_reads=[[], [], [], []])
    with pytest.raises(yw.VerificationFailed) as exc:
        _driven(pub, page, asset)
    assert "NOT retrying" in str(exc.value)
    assert "Oxo41KgeVoA" in str(exc.value)


def test_a_video_that_lands_as_private_is_a_verification_failure_not_a_success(pub, asset):
    page = _Page(rows_reads=[[], [], [_row(TITLE, "Private")], []])
    with pytest.raises(yw.VerificationFailed) as exc:
        _driven(pub, page, asset)
    assert "Private" in str(exc.value) and "NOT retrying" in str(exc.value)


def test_a_failure_after_the_publish_click_is_never_retried(pub, asset, monkeypatch):
    page = _Page(rows_reads=[[], [], [_row(TITLE)], []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    calls = []

    def submitted(*a, **k):
        calls.append(1)
        pub._submitted = True
        raise RuntimeError("the dialog went away")
    monkeypatch.setattr(pub, "drive", submitted)
    result = pub.publish(asset, META, dry_run=False)
    assert calls == [1]
    assert not result.ok and "NOT retrying" in result.detail


def test_a_failure_before_the_click_is_retried_exactly_once(pub, asset, monkeypatch):
    page = _Page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("a flake")
        return yw.PublishResult(platform=yw.PLATFORM, ok=True, url="u", queued_path=None,
                                detail="second time lucky")
    monkeypatch.setattr(pub, "drive", flaky)
    result = pub.publish(asset, META, dry_run=False)
    assert calls == [1, 1] and result.ok


def test_a_second_failure_is_not_retried_a_third_time(pub, asset, monkeypatch):
    page = _Page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    calls = []

    def always(*a, **k):
        calls.append(1)
        raise RuntimeError("still broken")
    monkeypatch.setattr(pub, "drive", always)
    result = pub.publish(asset, META, dry_run=False)
    assert calls == [1, 1] and not result.ok and result.queued_path


# ---------------------------------------------------------------------------- dry run

def _dry_page(rows_before=()):
    """A page whose list reads are: before x2, discard-read x2, row_index, after x2.

    The row_index read is its own entry because delete_row navigates BACK to the tab the draft
    was seen on before it opens the menu — the list read leaves the page on the other tab.
    """
    before = list(rows_before)
    draft = [_row(TITLE, S.DRAFT_VISIBILITY_TEXT, href=None), *before]
    return _Page(rows_reads=[before, [],        # the "is it already there" read (2 tabs)
                             draft, [],         # discard_draft's read (2 tabs)
                             draft,             # row_index, after re-opening the draft's tab
                             before, []])       # the after read (2 tabs)


def test_a_dry_run_uploads_for_real_then_deletes_the_draft(pub, asset, monkeypatch):
    page = _dry_page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert result.ok, result.detail
    assert "set_input_files:day-6.mp4" in page.calls
    assert f"click:{S.DELETE_CONFIRM_BUTTON}" in page.calls
    assert "draft deleted" in result.detail


def test_the_delete_is_confirmed_with_a_plain_click_never_a_forced_one(pub, asset, monkeypatch):
    """A forced click is what made a disabled confirm button a SILENT no-op.

    The button opens `disabled` and the acknowledgement checkbox clears it ~200 ms later
    (measured 2026-09-25). force=True skips exactly the check that would have said so, and the
    run reported a confirmed delete over a draft that was still on the channel.
    """
    page = _dry_page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    pub.publish(asset, META, dry_run=True)
    assert f"click:{S.DELETE_CONFIRM_BUTTON}:force" not in page.calls
    assert f"click:{S.DELETE_CONFIRM_BUTTON}" in page.calls
    # the checkbox, which has no box of its own to be stable, still gets the forced click
    assert f"click:{S.DELETE_CONFIRM_CHECKBOX}:force" in page.calls


def test_the_row_absent_predicate_negates_the_present_one_callably():
    js = yw.row_absent_js(TITLE)
    assert js.startswith("() => !((") and js.endswith(")())")
    assert js.count("(") == js.count(")")


def test_a_dry_run_never_clicks_publish(pub, asset, monkeypatch):
    page = _dry_page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    pub.publish(asset, META, dry_run=True)
    assert f"click:{S.DONE_BUTTON}" not in page.calls
    assert pub._submitted is False


def test_a_dry_run_still_selects_public_so_the_whole_path_is_exercised(pub, asset, monkeypatch):
    page = _dry_page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    pub.publish(asset, META, dry_run=True)
    assert f"click:{S.PUBLIC_RADIO}" in page.calls


def test_the_delete_goes_back_to_the_tab_the_draft_was_seen_on(pub, asset, monkeypatch):
    """The list read leaves the page on the LAST tab; the draft is on the first one.

    Seen live 2026-09-25 (run youtube_web-dry-run-115815): the delete looked for the row on
    the empty Videos tab, reported it already gone, and left the draft on the channel.
    """
    page = _dry_page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    pub.publish(asset, META, dry_run=True)
    gotos = [c for c in page.calls if c.startswith("goto:")]
    last_shorts = len(gotos) - 1 - gotos[::-1].index(f"goto:{S.CONTENT_SHORTS_URL}")
    last_videos = len(gotos) - 1 - gotos[::-1].index(f"goto:{S.CONTENT_VIDEOS_URL}")
    hover = [c for c in page.calls if c.startswith("hover:")]
    assert hover, page.calls
    # the tab holding the draft is re-opened after the videos tab, i.e. right before the menu
    assert last_shorts > 0
    assert page.calls.index(hover[0]) > page.calls.index(f"goto:{S.CONTENT_VIDEOS_URL}")
    assert last_videos < page.calls.index(hover[0]) or last_shorts < page.calls.index(hover[0])


def test_a_dry_run_reports_what_it_reached(pub, asset, monkeypatch):
    page = _dry_page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    detail = pub.publish(asset, META, dry_run=True).detail
    for fragment in ("channel confirmed", "content list read", "uploaded day-6.mp4",
                     "Publish NOT clicked", "draft deleted"):
        assert fragment in detail, detail


def test_a_dry_run_refuses_to_delete_a_row_that_is_not_a_draft(pub, asset, monkeypatch):
    """The whole point of the guard: a dry run must never remove a published video."""
    published = [_row(TITLE)]
    page = _Page(rows_reads=[[], [], published, [], published, [], []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert not result.ok
    assert "REFUSING to delete" in result.detail
    assert f"click:{S.DELETE_CONFIRM_BUTTON}" not in page.calls


def test_a_confirmation_worded_for_a_published_video_is_cancelled_not_confirmed(pub, asset,
                                                                                monkeypatch):
    page = _dry_page()
    page.texts[S.DELETE_CONFIRM_BUTTON] = "Delete forever"
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert not result.ok
    assert f"click:{S.DELETE_CANCEL_BUTTON}" in page.calls
    assert f"click:{S.DELETE_CONFIRM_BUTTON}" not in page.calls


def test_a_draft_that_survives_the_delete_queues_a_card_naming_it(pub, asset, monkeypatch):
    draft = [_row(TITLE, S.DRAFT_VISIBILITY_TEXT, href=None)]
    page = _Page(rows_reads=[[], [], draft, [], draft, draft, []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert not result.ok and result.queued_path
    assert "still on" in result.detail
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert TITLE in card


def test_a_dry_run_on_a_day_already_published_uploads_nothing(pub, asset, monkeypatch):
    page = _Page(rows_reads=[[_row(TITLE)], []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert result.ok and "already published" in result.detail
    assert not [c for c in page.calls if c.startswith("set_input_files")]


def test_a_dry_run_refuses_a_too_long_title_before_opening_a_browser(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a refused dry run must not open a browser")))
    result = pub.publish(asset, {**META, "title": "x" * 200}, dry_run=True)
    assert not result.ok and "REFUSED" in result.detail


def test_a_dry_run_on_the_wrong_channel_uploads_nothing(pub, asset, monkeypatch):
    page = _dry_page()
    page.texts[S.CHANNEL_NAME_TEXT] = "Stephen Michels"
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert not result.ok
    assert not [c for c in page.calls if c.startswith("set_input_files")]


# ------------------------------------------------------------------- failure -> card

def test_a_failure_leaves_one_card_naming_the_file_and_the_title(pub, asset, monkeypatch):
    page = _Page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("studio fell over")))
    result = pub.publish(asset, META, dry_run=False)
    assert not result.ok and result.queued_path
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert asset.name in card and TITLE in card
    assert S.CHANNEL_NAME in card


def test_the_card_warns_against_re_running_the_day(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    result = pub.publish(asset, META, dry_run=False)
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert "would post it twice" in card


def test_the_card_lands_in_the_queue_dir_capabilities_advertises(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    result = pub.publish(asset, META, dry_run=False)
    advertised = pathlib.Path(pub.capabilities()["queue_dir"])
    assert (pathlib.Path(pub.repo) / result.queued_path).parent == advertised


def test_the_mp4_lands_beside_the_card(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    result = pub.publish(asset, META, dry_run=False)
    card = pathlib.Path(pub.repo) / result.queued_path
    assert (card.parent / asset.name).exists()


def test_a_logged_out_profile_queues_before_the_browser_is_driven(tmp_path, asset, monkeypatch):
    pub = yw.YouTubeWebPublisher(repo=tmp_path, check_fn=lambda: yw.session.SiteStatus(
        "youtube", False, S.STUDIO_URL, "https://accounts.google.com/signin",
        "not logged in — redirected to /signin"))
    monkeypatch.setattr(yw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("preflight should have stopped this")))
    result = pub.publish(asset, META, dry_run=False)
    assert not result.ok and result.queued_path


def test_no_secret_reaches_the_card(pub, asset, monkeypatch):
    monkeypatch.setenv("YOUTUBE_SESSION_TOKEN", "yt_live_SUPERSECRET1")
    yw.session.known_secrets.cache_clear()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_Page()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("failed with token yt_live_SUPERSECRET1")))
    result = pub.publish(asset, META, dry_run=False)
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert "yt_live_SUPERSECRET1" not in card and "yt_live_SUPERSECRET1" not in result.detail


# ------------------------------------------------------------------------------ --check

def _check_out(tmp_path, monkeypatch, capsys, page):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(yw.session, "classify", lambda *a, **k: yw.session.SiteStatus(
        "youtube", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))
    rc = yw.main(["--check"], repo=tmp_path)
    return rc, capsys.readouterr().out


def test_check_resolves_the_anchors_read_only(tmp_path, monkeypatch, capsys):
    page = _Page()
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 0, out
    assert "channel" in out and "file input" in out
    forbidden = ("set_input_files", "click:", "insert_text:", "type:", "press:", "hover:")
    assert not [c for c in page.calls if c.startswith(forbidden)], page.calls
    assert not (tmp_path / "marketing").exists()


def test_check_reports_the_channel_first_and_stops_on_the_wrong_one(tmp_path, monkeypatch,
                                                                    capsys):
    page = _Page()
    page.texts[S.CHANNEL_NAME_TEXT] = "Stephen Michels"
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 1
    assert "WRONG" in out
    # It must not go on to report ten green anchors on a channel we refuse to post to.
    assert "file input" not in out


def test_check_says_post_file_only_instead_of_missing_for_the_form(tmp_path, monkeypatch,
                                                                   capsys):
    page = _Page()
    for sel in (S.TITLE_BOX, S.DESCRIPTION_BOX, S.NEXT_BUTTON, S.DONE_BUTTON, S.PUBLIC_RADIO):
        page.counts[sel] = 0
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 0, out
    assert "post-file only" in out
    assert "MISSING" not in out


def test_check_reports_a_missing_live_anchor_and_exits_one(tmp_path, monkeypatch, capsys):
    page = _Page()
    page.counts[S.FILE_INPUT] = 0
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 1 and "MISSING" in out


def test_check_reports_an_empty_tab_rather_than_calling_the_row_anchor_missing(tmp_path,
                                                                               monkeypatch,
                                                                               capsys):
    page = _Page()
    page.counts[S.VIDEO_ROW] = 0
    page.counts[S.ROW_TITLE] = 0
    page.counts[S.ROW_VISIBILITY] = 0
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 0, out
    assert "this tab has no videos" in out


def test_check_calls_the_row_anchor_missing_when_the_tab_is_neither_empty_nor_readable(
        tmp_path, monkeypatch, capsys):
    page = _Page()
    page.counts[S.VIDEO_ROW] = 0
    page.body_text = "Loading"
    rc, out = _check_out(tmp_path, monkeypatch, capsys, page)
    assert rc == 1 and "MISSING" in out


def test_check_visits_the_content_tabs_and_the_uploader(tmp_path, monkeypatch, capsys):
    page = _Page()
    _check_out(tmp_path, monkeypatch, capsys, page)
    gotos = [c for c in page.calls if c.startswith("goto:")]
    for url in (S.STUDIO_URL, S.CONTENT_SHORTS_URL, S.CONTENT_VIDEOS_URL, S.UPLOAD_DIALOG_URL):
        assert f"goto:{url}" in gotos


def test_check_on_a_logged_out_profile_stops_at_the_login(tmp_path, monkeypatch, capsys):
    page = _Page()
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(yw.session, "classify", lambda *a, **k: yw.session.SiteStatus(
        "youtube", False, S.STUDIO_URL, "https://accounts.google.com/signin", "not logged in"))
    assert yw.main(["--check"], repo=tmp_path) == 1
    assert "FAIL" in capsys.readouterr().out


# ------------------------------------------------------------------------ capabilities

def test_capabilities_names_the_channel_and_says_a_dry_run_uploads(pub):
    caps = pub.capabilities()
    assert caps["platform"] == "youtube_web"
    assert caps["channel"] == S.CHANNEL_NAME and caps["channel_id"] == S.CHANNEL_ID
    assert caps["dry_run_uploads"] is True
    assert caps["recurring_job"] is False
    assert caps["scheduling"] is False


def test_capabilities_makes_no_network_or_browser_call(tmp_path, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("capabilities must not open a browser")))
    monkeypatch.setattr(yw.session, "check", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("capabilities must not preflight")))
    yw.YouTubeWebPublisher(repo=tmp_path).capabilities()


# ---------------------------------------------------------------------- the invariants

def test_youtube_web_is_registered_and_upload_post_youtube_is_untouched():
    from publishers import publish
    assert publish.PUBLISHERS["youtube_web"] is yw.YouTubeWebPublisher
    from publishers.youtube import YouTubePublisher
    assert publish.PUBLISHERS["youtube"] is YouTubePublisher


def test_no_youtube_anchor_is_retyped_inside_the_driver():
    src = pathlib.Path(yw.__file__).read_text(encoding="utf-8")
    for literal in ("input[type=file]", "ytcp-video-row", "studio.youtube.com",
                    "#textbox", "tp-yt-paper", "#next-button", "#done-button",
                    "UC7ApR5Ntbc4DRkkZ_FrwyOw"):
        assert literal not in src, f"{literal!r} belongs in selectors_youtube.py"


def test_the_driver_imports_cleanly_without_playwright():
    src = pathlib.Path(yw.__file__).read_text(encoding="utf-8")
    top = src.split("\ndef ")[0]
    assert "import playwright" not in top and "from playwright" not in top


def test_the_clean_up_waits_for_the_draft_it_knows_it_created(pub, asset, monkeypatch):
    """Once a file has been handed over a draft EXISTS; "I cannot see one" is not an answer."""
    page = _Page(rows_reads=[[], [], [], [], [], []])
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(page))
    result = pub.publish(asset, META, dry_run=True)
    assert not result.ok
    assert "a draft titled" in result.detail and "exists" in result.detail


def test_nothing_is_waited_for_when_no_file_was_ever_handed_over(pub):
    page = _Page(rows_reads=[[], []])
    pub._uploaded = False
    assert "no draft was left behind" in pub.discard_draft(page, TITLE, [])


def test_there_are_no_fixed_sleeps_anywhere_in_the_driver():
    """Chrome rule 6: condition waits only."""
    src = pathlib.Path(yw.__file__).read_text(encoding="utf-8")
    for banned in ("wait_for_timeout", "time.sleep"):
        assert banned not in src, banned


def test_the_driver_says_out_loud_that_it_never_runs_from_actions():
    doc = (yw.__doc__ or "")
    assert "SESSION ONLY" in doc and "Actions" in doc


def test_no_workflow_file_runs_this_publisher():
    """Chrome rule 1, enforced rather than promised."""
    root = pathlib.Path(yw.__file__).resolve().parents[2]
    for wf in (root / ".github" / "workflows").glob("*.yml"):
        assert "youtube_web" not in wf.read_text(encoding="utf-8"), wf.name


def test_every_name_in_the_stage_lists_actually_exists():
    """A stage list naming an anchor that is gone makes --check quietly stop checking it."""
    for group in (S.POST_FILE_ONLY, S.POST_PUBLISH_ONLY, S.UNVERIFIED):
        for name in group:
            assert hasattr(S, name), name


def test_the_selectors_module_carries_its_evidence():
    """House rule: an anchor without evidence is a guess, and a guess fails SILENTLY."""
    src = pathlib.Path(S.__file__).read_text(encoding="utf-8")
    assert src.count("verified 2026-09-25") >= 20, src.count("verified 2026-09-25")
    assert "UNVERIFIED" in src


def test_the_session_site_entry_points_at_studio():
    assert yw.session.SITES[yw.SITE].dashboard_url == S.STUDIO_URL


def test_the_meta_files_on_disk_would_be_accepted():
    """The real ParkSheet meta, if it is there: titles must be inside YouTube's limit."""
    week = pathlib.Path.home() / "parksheet" / "build" / "release"
    metas = sorted(week.glob("*/day-*.json")) if week.exists() else []
    if not metas:
        pytest.skip("no ParkSheet release meta on this machine")
    for path in metas:
        meta = json.loads(path.read_text(encoding="utf-8"))
        title = yw.title_of(meta)
        assert len(title) <= S.TITLE_MAX, f"{path.name}: {len(title)} > {S.TITLE_MAX}"
        assert yw.description_of(meta) == str(meta["description"]).rstrip()
