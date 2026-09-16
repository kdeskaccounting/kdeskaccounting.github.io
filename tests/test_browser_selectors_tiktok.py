"""scripts/browser/selectors_tiktok.py — the one file that changes when TikTok Studio moves.

Spec Chrome rule 6: site-specific anchors live in one selectors_<site>.py, and role/label/
text locators come before CSS chains. Nothing here was confirmed against a logged-in TikTok
Studio (the debug profile holds no TikTok session), so the second half of this file enforces
the honesty requirement: every anchor that has not been seen live is listed in UNVERIFIED and
carries an `# UNVERIFIED` comment next to its definition.
"""
import pathlib
import re

from browser import selectors_tiktok as S
from browser import session

SRC = pathlib.Path(S.__file__).read_text(encoding="utf-8")


def test_the_upload_and_content_urls_are_the_studio_urls_the_task_names():
    assert S.UPLOAD_URL == "https://www.tiktok.com/tiktokstudio/upload"
    assert S.CONTENT_URL == "https://www.tiktok.com/tiktokstudio/content"
    assert S.STUDIO_URL == "https://www.tiktok.com/tiktokstudio"


def test_every_anchor_the_driver_needs_exists():
    for attr in ("FILE_INPUT", "CAPTION_EDITOR", "SCHEDULE_TOGGLE_TEXT", "SCHEDULE_DATE_INPUT",
                 "SCHEDULE_TIME_INPUT", "POST_BUTTON_TEXT", "SCHEDULE_BUTTON_TEXT",
                 "SCHEDULED_TAB_TEXT", "POST_ROW", "POST_ROW_FALLBACK", "LOGIN_MARKER",
                 "POST_RESPONSE", "SCHEDULED_EMPTY_TEXT", "UPLOAD_READY_TEXT"):
        assert getattr(S, attr), attr


def test_the_login_marker_is_a_path_fragment_not_a_whole_url():
    # session.classify tests it with `in got.path`, so a full URL would never match.
    assert S.LOGIN_MARKER.startswith("/")
    assert "://" not in S.LOGIN_MARKER


def test_unverified_lists_every_anchor_that_has_not_been_seen_live():
    assert "max_schedule_days" in S.UNVERIFIED
    for name in S.UNVERIFIED:
        if name == "max_schedule_days":
            continue
        assert hasattr(S, name), f"UNVERIFIED names {name!r}, which is not a selector here"


def test_each_unverified_selector_is_commented_as_unverified_in_the_source():
    """A reader skimming the file must see the warning next to the value, not only in a list."""
    for name in S.UNVERIFIED:
        if name == "max_schedule_days":
            continue
        line = next((l for l in SRC.splitlines() if re.match(rf"{name}\s*[:=]", l)), None)
        assert line, f"{name} has no assignment line"
        assert "UNVERIFIED" in line, f"{name} is unverified but its line does not say so"


def test_max_schedule_days_is_ten_and_marked_unverified():
    assert S.MAX_SCHEDULE_DAYS == 10
    assert "max_schedule_days" in S.UNVERIFIED


def test_role_and_text_anchors_are_preferred_over_css_chains():
    """Rule 6: get_by_role / get_by_text first. A long descendant chain is the smell."""
    for name in ("SCHEDULE_TOGGLE_TEXT", "POST_BUTTON_TEXT", "SCHEDULE_BUTTON_TEXT",
                 "SCHEDULED_TAB_TEXT"):
        value = getattr(S, name)
        assert ">" not in value and "." not in value, f"{name} looks like a CSS chain"


def test_selectors_module_is_stdlib_only_so_the_test_suite_can_import_it():
    assert "import playwright" not in SRC
    assert "import requests" not in SRC


# --- session.SITES["tiktok"] is the preflight half: the same fail-closed login check the
# Gumroad drivers get, so a logged-out profile writes a card instead of driving a login wall.

def test_tiktok_is_a_known_site_with_the_studio_dashboard():
    assert "tiktok" in session.SITES
    site = session.SITES["tiktok"]
    assert site.dashboard_url == S.STUDIO_URL
    assert site.login_marker == S.LOGIN_MARKER
    assert site.anchor_description


def test_the_apex_host_is_an_allowed_redirect_target_and_lookalikes_are_not():
    site = session.SITES["tiktok"]
    assert "tiktok.com" in site.alt_hosts
    assert not any("eviltiktok" in h for h in site.alt_hosts)


def test_classify_accepts_the_logged_in_studio():
    s = session.classify("tiktok", S.STUDIO_URL, S.CONTENT_URL)
    assert s.ok is True
    assert "logged in" in s.detail


def test_classify_detects_the_redirect_to_the_login_wall():
    s = session.classify("tiktok", S.STUDIO_URL,
                         "https://www.tiktok.com/login?redirect_url=%2Ftiktokstudio")
    assert s.ok is False
    assert "not logged in" in s.detail


def test_classify_refuses_a_lookalike_host():
    s = session.classify("tiktok", S.STUDIO_URL, "https://www.tiktok.com.evil.example/tiktokstudio")
    assert s.ok is False
    assert "unexpected host" in s.detail
