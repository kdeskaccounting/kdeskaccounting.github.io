"""The 2026-10-08 incident: teardown masked the real error, and the card said "upload by hand".

The Tower of Terror Short was published at 07:42:00; ~26 s later the CDP connection dropped,
`Tracing.stop` in open_page's teardown raised TargetClosedError over the run's own error, and
the card (ledger #158) carried the standard upload steps for a video that was already live.

Protected here:
1. A teardown failure (Tracing.stop, page.close) is logged, never raised over the run's error,
   and never turns a finished run into a failure.
2. A failure after the Publish click files a "PROBABLY LIVE, do not upload again" card and
   ledger detail; a failure before it files the unchanged upload card.
3. A dropped connection is announced; the checks poll runs with tracing paused.
"""
import contextlib
import datetime as dt
import pathlib
import sys
import types

import pytest

from browser import ensure_chrome, session
from browser import selectors_youtube as S
from publishers import youtube_web as yw

TITLE = "Tower of Terror Is 199 Feet on PURPOSE | Disney Secret #4"
META = {"slug": "parksheet-hand-tower-of-terror", "title": TITLE,
        "description": "Tower of Terror.\n\nPowered by Queue-Times.com"}


class TargetClosedError(Exception):
    """Stands in for playwright's TargetClosedError."""


# ------------------------------------------------------------------ a fake playwright

class _Tracing:
    def __init__(self, log, fail_stop=False):
        self.log, self.fail_stop = log, fail_stop

    def start(self, **kw):
        self.log.append(("tracing.start", kw.get("screenshots"), kw.get("snapshots")))

    def stop(self, path=None):
        self.log.append(("tracing.stop", pathlib.Path(path).name if path else None))
        if self.fail_stop:
            raise TargetClosedError(
                "Tracing.stop: Target page, context or browser has been closed")


class _PwPage:
    def __init__(self, log, fail_close=False):
        self.log, self.fail_close = log, fail_close

    def close(self):
        self.log.append(("page.close",))
        if self.fail_close:
            raise TargetClosedError("Page.close: Target page, context or browser has been closed")

    def goto(self, url, **kw):
        self.log.append(("goto", url))


class _Ctx:
    def __init__(self, log, **fail):
        self.log = log
        self.tracing = _Tracing(log, fail.get("fail_stop", False))
        self._fail_close = fail.get("fail_close", False)
        self.pages = [_PwPage(log)]          # the tab Chrome already had open

    def new_page(self):
        page = _PwPage(self.log, self._fail_close)
        self.pages.append(page)
        return page


class _Browser:
    def __init__(self, ctx):
        self.contexts = [ctx]
        self.handlers = {}

    def on(self, event, fn):
        self.handlers.setdefault(event, []).append(fn)

    def emit(self, event):
        for fn in self.handlers.get(event, []):
            fn(self)


@pytest.fixture
def fake_pw(monkeypatch):
    """Install a fake playwright.sync_api; returns (log, make) where make() builds the browser."""
    log = []
    state = {}

    def make(**fail):
        state["browser"] = _Browser(_Ctx(log, **fail))
        return state["browser"]

    @contextlib.contextmanager
    def sync_playwright():
        chromium = types.SimpleNamespace(connect_over_cdp=lambda url: state["browser"])
        yield types.SimpleNamespace(chromium=chromium)

    pkg = types.ModuleType("playwright")
    api = types.ModuleType("playwright.sync_api")
    api.sync_playwright = sync_playwright
    pkg.sync_api = api
    monkeypatch.setitem(sys.modules, "playwright", pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    monkeypatch.setattr(ensure_chrome, "ensure", lambda *a, **k: None)
    return log, make


# ------------------------------------------------------------------ 1. teardown never masks

def test_a_teardown_error_does_not_replace_the_primary_error(fake_pw, tmp_path, capsys):
    log, make = fake_pw
    make(fail_stop=True, fail_close=True)
    with pytest.raises(yw.VerificationFailed, match="the real reason"):
        with session.open_page("youtube_web", repo=tmp_path):
            raise yw.VerificationFailed("the real reason")
    err = capsys.readouterr().err
    assert "Tracing.stop failed (TargetClosedError" in err
    assert "page.close failed (TargetClosedError" in err
    assert "VerificationFailed: the real reason) is what is reported" in err
    # Every clean-up step still ran, even though the one before it failed.
    assert ("tracing.stop", "trace.zip") in log and ("page.close",) in log


def test_a_teardown_error_after_a_clean_run_is_logged_not_raised(fake_pw, tmp_path, capsys):
    log, make = fake_pw
    make(fail_stop=True)
    with session.open_page("youtube_web", repo=tmp_path):
        pass                                  # the run finished; the publish stands
    assert "Tracing.stop failed" in capsys.readouterr().err
    assert ("page.close",) in log


def test_a_dropped_connection_is_announced_but_teardown_letting_go_is_not(
        fake_pw, tmp_path, capsys):
    log, make = fake_pw
    browser = make()
    with session.open_page("youtube_web", repo=tmp_path):
        browser.emit("disconnected")
    assert "BROWSER DISCONNECTED" in capsys.readouterr().err
    browser.emit("disconnected")              # after teardown: our own let-go, not news
    assert "BROWSER DISCONNECTED" not in capsys.readouterr().err


def test_the_checks_poll_runs_with_tracing_paused_then_resumes(fake_pw, tmp_path):
    log, make = fake_pw
    make()
    with session.open_page("youtube_web", repo=tmp_path) as page:
        log.append(("before",))
        with session.trace_paused(page, "polling"):
            log.append(("polling",))
        log.append(("publish",))
    i = log.index(("polling",))
    assert log[i - 1] == ("tracing.stop", "trace-part1.zip")
    assert log[i + 1] == ("tracing.start", True, True)
    assert log.count(("tracing.stop", "trace.zip")) == 1


def test_a_pause_that_cannot_stop_never_raises_and_teardown_still_stops(fake_pw, tmp_path):
    log, make = fake_pw
    make(fail_stop=True)
    with pytest.raises(RuntimeError, match="inside"):
        with session.open_page("youtube_web", repo=tmp_path) as page:
            with session.trace_paused(page, "polling"):
                raise RuntimeError("inside")


def test_trace_paused_is_a_no_op_for_a_page_open_page_did_not_open():
    with session.trace_paused(object(), "polling"):
        pass


def test_await_checks_pauses_the_trace(monkeypatch):
    seen = []

    @contextlib.contextmanager
    def paused(page, reason=""):
        seen.append(("pause", reason))
        yield
        seen.append(("resume",))
    monkeypatch.setattr(yw.session, "trace_paused", paused)
    pub = yw.YouTubeWebPublisher(repo=pathlib.Path("."), check_fn=lambda: None)
    monkeypatch.setattr(pub, "_poll_checks", lambda page: seen.append(("poll",)) or "x")
    assert pub.await_checks(object()) == "x"
    assert [s[0] for s in seen] == ["pause", "poll", "resume"]


# ------------------------------------------------------------------ 2. the card after Publish

class _DeadPage:
    def screenshot(self, path):
        raise TargetClosedError("Page.screenshot: Target closed")


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "parksheet-hand-tower-of-terror-short.mp4"
    p.write_bytes(b"mp4")
    return p


@pytest.fixture
def pub(tmp_path):
    return yw.YouTubeWebPublisher(repo=tmp_path, check_fn=lambda: yw.session.SiteStatus(
        "youtube", True, S.STUDIO_URL, S.STUDIO_URL, "logged in"))


def _fake_open_page(page):
    @contextlib.contextmanager
    def _cm(*_a, **_k):
        yield page
    return _cm


CLICKED = dt.datetime(2026, 10, 8, 7, 42, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))


def test_a_failure_after_publish_files_a_probably_live_card(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_DeadPage()))

    def published_then_dropped(*a, **k):
        pub._submitted, pub._submitted_at = True, CLICKED
        pub._video_id = "Oxo41KgeVoA"
        raise TargetClosedError("Page.goto: Target page, context or browser has been closed")
    monkeypatch.setattr(pub, "drive", published_then_dropped)
    result = pub.publish(asset, META, dry_run=False)
    assert not result.ok and result.queued_path
    notice = ("Publish was clicked at 2026-10-08 07:42:00 -0700: the video is PROBABLY LIVE. "
              "Check the Shorts list first; DO NOT upload again.")
    # The ledger row is built from result.detail; it leads with the notice.
    assert result.detail.startswith(notice)
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert notice in card and "PROBABLY LIVE" in card.splitlines()[0]
    assert "TargetClosedError" in card                  # the real error is still there
    assert "by hand" not in card
    assert f"Create -> {S.UPLOAD_MENU_ITEM_TEXT}" not in card
    assert "DO NOT upload" in card and S.CONTENT_URL in card
    assert "Oxo41KgeVoA" in card


def test_a_post_publish_card_without_a_recorded_time_still_says_probably_live(
        pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_DeadPage()))

    def submitted(*a, **k):
        pub._submitted = True
        raise RuntimeError("the dialog went away")
    monkeypatch.setattr(pub, "drive", submitted)
    result = pub.publish(asset, META, dry_run=False)
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert "PROBABLY LIVE" in card and "by hand" not in card


def test_the_submit_records_when_publish_was_clicked(pub, monkeypatch):
    class _Btn:
        first = property(lambda self: self)

        def wait_for(self, **kw):
            pass

        def click(self, **kw):
            assert pub._submitted and pub._submitted_at is not None

    page = types.SimpleNamespace(locator=lambda sel: _Btn(),
                                 wait_for_function=lambda *a, **k: None)
    monkeypatch.setattr(pub, "confirm_publish", lambda page: None)
    pub.submit(page)
    assert pub._submitted_at.tzinfo is not None


def test_a_failure_before_publish_files_the_unchanged_upload_card(pub, asset, monkeypatch):
    monkeypatch.setattr(yw.session, "open_page", _fake_open_page(_DeadPage()))
    monkeypatch.setattr(pub, "drive", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("studio fell over")))
    result = pub.publish(asset, META, dry_run=False)
    card = (pathlib.Path(pub.repo) / result.queued_path).read_text()
    assert card.splitlines()[0] == (f"# youtube_web — Publish {asset.name} to the "
                                    f"{S.CHANNEL_NAME} channel by hand")
    assert "PROBABLY LIVE" not in card and "PROBABLY LIVE" not in result.detail
    assert result.detail.startswith("RuntimeError: studio fell over")
    for i, step in enumerate(yw.manual_steps(asset, META), 1):
        assert f"{i}. {step}" in card


def test_day_one_publish_click_does_not_colour_day_twos_preflight_card(tmp_path, asset):
    pub = yw.YouTubeWebPublisher(repo=tmp_path, check_fn=lambda: yw.session.SiteStatus(
        "youtube", False, S.STUDIO_URL, "https://accounts.google.com/signin",
        "not logged in — redirected to /signin"))
    pub._submitted, pub._submitted_at = True, CLICKED       # left over from day 1
    result = pub.publish(asset, META, dry_run=False)
    assert "PROBABLY LIVE" not in result.detail


def test_teardown_and_card_together_reproduce_2026_10_08_correctly(
        fake_pw, pub, asset, monkeypatch, capsys):
    """End to end over the real open_page: drop after Publish, Tracing.stop raises too."""
    log, make = fake_pw
    make(fail_stop=True, fail_close=True)
    monkeypatch.setattr(yw.session, "trace_dir",
                        lambda repo, name, now=None: pathlib.Path(pub.repo))

    def published_then_dropped(page, asset, meta):
        pub._submitted, pub._submitted_at = True, CLICKED
        raise TargetClosedError("Page.goto: Target page, context or browser has been closed")
    monkeypatch.setattr(pub, "drive", published_then_dropped)
    result = pub.publish(asset, META, dry_run=False)
    assert result.detail.startswith("Publish was clicked at 2026-10-08 07:42:00 -0700")
    assert "VerificationFailed" in result.detail and "Page.goto" in result.detail
    assert "Tracing.stop" not in result.detail
    assert "Tracing.stop failed" in capsys.readouterr().err
