"""Studio channel switch-and-restore (scripts/browser/studio_channel.py), 2026-10-10.

Studio was on Court of Inquiry — another channel of the santiagokdesk Google account — and the
publisher refused, because it only knew how to switch away from KDeskAccounting. The rule now:

  * Studio on ParkSheet ............................... stay
  * Studio on ANY other channel of santiagokdesk ...... switch to ParkSheet, switch back after
  * Studio on a channel of another Google account ..... refuse (switching there is a sign-in)

and "switch back after" holds whether the run succeeded or failed, best-effort, never raising.
The switch panel read below is the one seen live on 2026-10-10.
"""
import contextlib
import importlib

import pytest

from browser import selectors_youtube as S
from browser import studio_channel as sc
from publishers import youtube_web as yw

SANTIAGO = {"active": True, "email": "santiagokdesk@gmail.com",
            "channels": ["KDeskAccounting", "ParkSheet", "Court of Inquiry", "KDesk Games"]}
SMICHELS_OTHER = {"active": False, "email": "smichels1@gmail.com",
                  "channels": ["Stephen is Acting", "booshigotyou"]}
# Seen live 2026-10-10 with Studio on Court of Inquiry.
PANEL_ON_SANTIAGO = [SANTIAGO, SMICHELS_OTHER]
# What the same panel reads when the ACTIVE account is smichels1 ("Stephen is Acting").
PANEL_ON_SMICHELS = [dict(SMICHELS_OTHER, active=True), dict(SANTIAGO, active=False)]


# ------------------------------------------------------------------- the decision (pure)

@pytest.mark.parametrize("current", ["Court of Inquiry", "KDeskAccounting", "KDesk Games",
                                     "court of  inquiry"])
def test_another_channel_of_the_same_account_is_switched(current):
    decision, why = sc.plan_switch(current, "ParkSheet", PANEL_ON_SANTIAGO)
    assert decision == sc.SWITCH, why


def test_already_on_the_target_stays_without_reading_the_menu():
    assert sc.plan_switch("ParkSheet", "ParkSheet", None)[0] == sc.STAY


@pytest.mark.parametrize("current", ["Stephen is Acting", "booshigotyou"])
def test_a_different_google_account_is_refused(current):
    decision, why = sc.plan_switch(current, "ParkSheet", PANEL_ON_SMICHELS)
    assert decision == sc.REFUSE
    assert "smichels1@gmail.com" in why and "sign-in" in why


def test_the_target_only_under_other_accounts_is_refused():
    """ParkSheet listed, but not under the active account: clicking it is a Google sign-in."""
    assert sc.plan_switch("Stephen is Acting", "ParkSheet", PANEL_ON_SMICHELS)[0] == sc.REFUSE


@pytest.mark.parametrize("sections", [[], None, [SMICHELS_OTHER],
                                      [SANTIAGO, dict(SMICHELS_OTHER, active=True)]])
def test_a_menu_that_does_not_say_which_account_is_active_is_refused(sections):
    assert sc.plan_switch("Court of Inquiry", "ParkSheet", sections)[0] == sc.REFUSE


def test_a_current_channel_the_active_account_does_not_list_is_refused():
    assert sc.plan_switch("Someone Else", "ParkSheet", PANEL_ON_SANTIAGO)[0] == sc.REFUSE


def test_the_restore_direction_is_the_same_decision():
    assert sc.plan_switch("ParkSheet", "Court of Inquiry", PANEL_ON_SANTIAGO)[0] == sc.SWITCH


# ------------------------------------------------------------------- switch_to (browser half)

class _Page:
    """Just enough page: a header, a switch panel, and a log of what was clicked."""

    def __init__(self, header, panel, *, url=None, switch_works=True):
        self.header, self.panel, self.switch_works = header, panel, switch_works
        self.url = url or f"{S.STUDIO_URL}/channel/UCx"
        self.clicked, self.pressed, self.navigated = [], [], []
        self.context = self

    def goto(self, url, **kw):
        self.navigated.append(url)

    def wait_for_function(self, js, **kw):
        if not self.switch_works:
            raise TimeoutError("header never changed")

    def new_page(self):
        return self

    def close(self):
        pass


@pytest.fixture
def fake_menu(monkeypatch):
    """read_accounts / click_channel / current_channel against a _Page, no DOM."""
    monkeypatch.setattr(sc, "read_accounts", lambda page: page.panel)

    def click(page, name):
        page.clicked.append(name)
        page.header = name
        return True
    monkeypatch.setattr(sc, "click_channel", click)
    monkeypatch.setattr(sc, "current_channel", lambda page: page.header)


def test_switch_to_clicks_the_target_on_the_same_account(fake_menu):
    page = _Page("Court of Inquiry", PANEL_ON_SANTIAGO)
    assert sc.switch_to(page, "Court of Inquiry", "ParkSheet") == sc.SWITCH
    assert page.clicked == ["ParkSheet"]


def test_switch_to_refuses_another_account_and_clicks_nothing(fake_menu):
    page = _Page("Stephen is Acting", PANEL_ON_SMICHELS)
    page.pressed = []
    page.keyboard = type("K", (), {"press": lambda self, k: page.pressed.append(k)})()
    with pytest.raises(sc.ChannelRefused):
        sc.switch_to(page, "Stephen is Acting", "ParkSheet")
    assert page.clicked == []
    assert page.pressed == ["Escape"]          # the menu is closed again


def test_a_switch_that_lands_on_a_sign_in_page_is_a_refusal(fake_menu):
    """The passkey / sign-in case: nothing is ever typed, the run refuses."""
    page = _Page("Court of Inquiry", PANEL_ON_SANTIAGO, switch_works=False,
                 url="https://accounts.google.com/v3/signin/challenge/pk")
    with pytest.raises(sc.ChannelRefused) as exc:
        sc.switch_to(page, "Court of Inquiry", "ParkSheet")
    assert "no credentials" in str(exc.value)


def test_restore_switches_back_to_the_channel_found(fake_menu):
    page = _Page("ParkSheet", PANEL_ON_SANTIAGO)
    assert sc.restore(page, "Court of Inquiry") is True
    assert page.clicked == ["Court of Inquiry"] and page.navigated == [S.STUDIO_URL]


def test_restore_with_nothing_to_restore_touches_nothing(fake_menu):
    page = _Page("ParkSheet", PANEL_ON_SANTIAGO)
    assert sc.restore(page, None) is True
    assert sc.restore_in_new_tab(page, None) is True
    assert page.navigated == [] and page.clicked == []


def test_restore_never_raises_and_logs_the_failure(fake_menu, capsys):
    page = _Page("ParkSheet", PANEL_ON_SANTIAGO)

    def boom(url, **kw):
        raise RuntimeError("browser went away")
    page.goto = boom
    assert sc.restore(page, "Court of Inquiry", label="youtube_web") is False
    err = capsys.readouterr().err
    assert "COULD NOT switch Studio back to 'Court of Inquiry'" in err
    assert "browser went away" in err


# ------------------------------------------------------------------- the publisher

class _StudioPage(_Page):
    """A page the publisher's assert_channel can read: url carries ParkSheet's id once the
    header reads ParkSheet."""

    @property
    def url(self):
        cid = S.CHANNEL_ID if self.header == S.CHANNEL_NAME else "UCtlnJbF8MzhAeEvn0pVdWVg"
        return f"{S.STUDIO_URL}/channel/{cid}"

    @url.setter
    def url(self, value):
        pass


@pytest.fixture
def pub(monkeypatch, fake_menu):
    p = yw.YouTubeWebPublisher()
    monkeypatch.setattr(p, "goto", lambda page, url: None)
    return p


def test_publisher_on_court_of_inquiry_switches_and_remembers_it(pub):
    page = _StudioPage("Court of Inquiry", PANEL_ON_SANTIAGO)
    assert pub.assert_channel(page) == S.CHANNEL_NAME
    assert page.clicked == [S.CHANNEL_NAME]
    assert pub._restore_channel == "Court of Inquiry"


def test_publisher_on_another_google_account_refuses_and_remembers_nothing(pub):
    page = _StudioPage("Stephen is Acting", PANEL_ON_SMICHELS)
    page.keyboard = type("K", (), {"press": lambda self, k: None})()
    with pytest.raises(yw.WrongChannel) as exc:
        pub.assert_channel(page)
    assert page.clicked == []
    assert pub._restore_channel is None
    assert "smichels1@gmail.com" in str(exc.value)


def test_publisher_already_on_parksheet_has_nothing_to_restore(pub):
    page = _StudioPage(S.CHANNEL_NAME, PANEL_ON_SANTIAGO)
    pub.assert_channel(page)
    assert page.clicked == [] and pub._restore_channel is None


def _open_page(page):
    @contextlib.contextmanager
    def _cm(*_a, **_k):
        yield page
    return _cm


@pytest.fixture
def restores(monkeypatch):
    seen = []
    monkeypatch.setattr(sc, "restore_in_new_tab",
                        lambda ctx, original, **kw: seen.append(original) or True)
    return seen


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "day.mp4"
    p.write_bytes(b"mp4")
    return p


META = {"slug": "parksheet-test", "title": "Horizons let riders vote on how their ride would end",
        "description": "d"}


def test_publish_switches_back_after_success(pub, asset, monkeypatch, restores):
    page = _StudioPage("Court of Inquiry", PANEL_ON_SANTIAGO)
    monkeypatch.setattr(yw.session, "open_page", _open_page(page))

    def drive(pg, a, m):
        pub.assert_channel(pg)
        return yw.PublishResult(platform=pub.platform, ok=True, url="u", queued_path=None,
                                detail="ok")
    monkeypatch.setattr(pub, "drive", drive)
    assert pub._do_publish(asset, META).ok
    assert restores == ["Court of Inquiry"]
    assert pub._restore_channel is None


def test_publish_switches_back_after_failure(pub, asset, monkeypatch, restores):
    page = _StudioPage("Court of Inquiry", PANEL_ON_SANTIAGO)
    monkeypatch.setattr(yw.session, "open_page", _open_page(page))

    def drive(pg, a, m):
        pub.assert_channel(pg)
        raise yw.VerificationFailed("no row")
    monkeypatch.setattr(pub, "drive", drive)
    with pytest.raises(yw.VerificationFailed):
        pub._do_publish(asset, META)
    assert restores == ["Court of Inquiry"]


def test_publish_after_a_retry_switches_back_once(pub, asset, monkeypatch, restores):
    page = _StudioPage("Court of Inquiry", PANEL_ON_SANTIAGO)
    monkeypatch.setattr(yw.session, "open_page", _open_page(page))
    tries = []

    def drive(pg, a, m):
        pub.assert_channel(pg)
        tries.append(1)
        if len(tries) == 1:
            raise RuntimeError("flaky")
        return yw.PublishResult(platform=pub.platform, ok=True, url="u", queued_path=None,
                                detail="ok")
    monkeypatch.setattr(pub, "drive", drive)
    assert pub._do_publish(asset, META).ok
    assert tries == [1, 1] and restores == ["Court of Inquiry"]


def test_publish_on_another_account_refuses_and_switches_nothing_back(pub, asset, monkeypatch,
                                                                      restores):
    page = _StudioPage("Stephen is Acting", PANEL_ON_SMICHELS)
    page.keyboard = type("K", (), {"press": lambda self, k: None})()
    monkeypatch.setattr(yw.session, "open_page", _open_page(page))
    monkeypatch.setattr(pub, "drive", lambda pg, a, m: pub.assert_channel(pg))
    with pytest.raises(yw.WrongChannel):
        pub._do_publish(asset, META)
    assert restores == []                     # nothing was switched, so nothing to put back
    assert page.clicked == []


def test_dry_run_switches_back_too(pub, asset, monkeypatch, restores):
    page = _StudioPage("Court of Inquiry", PANEL_ON_SANTIAGO)
    monkeypatch.setattr(yw.session, "open_page", _open_page(page))

    def body(pg, a, m, title, reached):
        pub.assert_channel(pg)
        raise RuntimeError("upload broke")
    monkeypatch.setattr(pub, "_dry_run_on", body)
    with pytest.raises(RuntimeError):
        pub._do_dry_run(asset, META)
    assert restores == ["Court of Inquiry"]


# ------------------------------------------------------------------- the pin-comment script

@pytest.fixture
def pin():
    return importlib.import_module("browser.youtube_pin_comment")


def test_pin_script_switches_to_parksheet_and_remembers_the_channel(pin, fake_menu):
    page = _Page("Court of Inquiry", PANEL_ON_SANTIAGO)
    found = {}
    pin.ensure_parksheet(page, found)
    assert page.clicked == ["ParkSheet"] and found == {"original": "Court of Inquiry"}


def test_pin_script_refuses_another_account_and_posts_nothing(pin, fake_menu):
    page = _Page("Stephen is Acting", PANEL_ON_SMICHELS)
    page.keyboard = type("K", (), {"press": lambda self, k: None})()
    found = {}
    with pytest.raises(sc.ChannelRefused):
        pin.ensure_parksheet(page, found)
    assert page.clicked == [] and found == {}


def test_pin_script_refuses_a_sign_in_page(pin, fake_menu):
    page = _Page("x", PANEL_ON_SANTIAGO, url="https://accounts.google.com/signin")
    with pytest.raises(sc.ChannelRefused):
        pin.ensure_parksheet(page, {})


def test_pin_script_on_parksheet_has_nothing_to_restore(pin, fake_menu):
    page = _Page("ParkSheet", PANEL_ON_SANTIAGO)
    found = {}
    pin.ensure_parksheet(page, found)
    assert page.clicked == [] and found == {}
