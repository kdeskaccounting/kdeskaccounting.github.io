"""scripts/browser/selectors_tiktok.py — the one file that changes when TikTok Studio moves.

Spec Chrome rule 6: site-specific anchors live in one selectors_<site>.py, and role/label/
text locators come before CSS chains. Since 2026-09-15 the debug profile IS signed in, and
every anchor reachable without committing anything has been resolved live — so the honesty
requirement now cuts both ways: an anchor that has been seen must not still claim to be a
guess, and one that cannot be seen read-only (the post-file form) must still say so, in
UNVERIFIED and in an `# UNVERIFIED` comment next to its definition.
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
    for attr in ("FILE_INPUT", "CAPTION_EDITOR", "SCHEDULE_RADIO_NAME",
                 "SCHEDULE_DATE_INPUT", "SCHEDULE_TIME_INPUT", "DATE_VALUE_RE",
                 "TIME_VALUE_RE", "TIME_HOUR_OPTION", "TIME_MINUTE_OPTION",
                 "CALENDAR_MONTH_TITLE", "CALENDAR_DAY", "CALENDAR_NEXT", "CALENDAR_PREV",
                 "TOO_SOON_TEXT", "FIRST_RUN_DIALOG_BUTTONS", "POST_BUTTON_TEXT",
                 "SCHEDULE_BUTTON_TEXT", "POST_ROW", "POST_ROW_FALLBACK", "LOGIN_MARKER",
                 "POST_RESPONSE", "SCHEDULED_EMPTY_TEXT", "UPLOAD_READY_TEXT",
                 "POSTS_TABLE", "UPLOAD_PAGE_READY", "CONTENT_PAGE_READY",
                 "SELECT_VIDEO_BUTTON"):
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
    for name in ("SCHEDULE_RADIO_NAME", "POST_BUTTON_TEXT", "SCHEDULE_BUTTON_TEXT",
                 "POST_NOW_RADIO_NAME", "UPLOAD_READY_TEXT", "TOO_SOON_TEXT"):
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


# --- 2026-09-15: the live read-only pass against @park.sheet. Each of these encodes
# something that was observed, so a future edit that quietly re-guesses it fails here.

def test_the_anchors_seen_live_are_no_longer_claimed_to_be_guesses():
    """FILE_INPUT, the posts table and the empty-state copy were counted on the live pages."""
    for name in ("FILE_INPUT", "POSTS_TABLE", "SELECT_VIDEO_BUTTON", "SELECT_VIDEO_CONTAINER",
                 "SCHEDULED_EMPTY_TEXT", "UPLOAD_PAGE_READY", "CONTENT_PAGE_READY"):
        assert name not in S.UNVERIFIED, f"{name} was verified live; drop it from UNVERIFIED"


def test_every_verified_anchor_says_when_it_was_verified():
    """A bare value with no date is indistinguishable from a guess someone forgot to flag."""
    for name in ("FILE_INPUT", "POSTS_TABLE", "SELECT_VIDEO_BUTTON", "SCHEDULED_EMPTY_TEXT"):
        line = next((l for l in SRC.splitlines() if re.match(rf"{name}\s*[:=]", l)), None)
        assert line and "verified 2026-09-15" in line, f"{name} does not say how it is known"


def test_the_post_file_anchors_all_exist():
    """POST_FILE_ONLY is about *when* an anchor can be checked (never by `--check`, which may
    not select a file), not about whether it is still a guess — 2026-09-23 verified most of
    this section by actually driving a real upload through the scheduler. The two exceptions
    are the calendar arrows, which stay in both POST_FILE_ONLY and UNVERIFIED because no month
    change was ever driven end to end.
    """
    for name in S.POST_FILE_ONLY:
        assert hasattr(S, name), f"POST_FILE_ONLY names {name!r}, which is not a selector here"
    for name in ("CALENDAR_NEXT", "CALENDAR_PREV"):
        assert name in S.POST_FILE_ONLY and name in S.UNVERIFIED
    for name in ("SCHEDULE_RADIO_NAME", "SCHEDULE_DATE_INPUT", "SCHEDULE_TIME_INPUT",
                 "TIME_HOUR_OPTION", "TIME_MINUTE_OPTION", "CALENDAR_MONTH_TITLE",
                 "CALENDAR_DAY", "TOO_SOON_TEXT", "POST_BUTTON_TEXT", "SCHEDULE_BUTTON_TEXT"):
        assert name in S.POST_FILE_ONLY
        assert name not in S.UNVERIFIED, f"{name} was verified live 2026-09-23; drop it from UNVERIFIED"


def test_the_empty_state_copy_is_lowercase_because_that_is_how_it_is_matched():
    """scheduled_ready_js lowercases body innerText before testing it."""
    assert S.SCHEDULED_EMPTY_TEXT == S.SCHEDULED_EMPTY_TEXT.lower()
    assert S.SCHEDULED_EMPTY_TEXT == "no posts yet"


def test_there_is_no_scheduled_tab_and_the_file_says_so():
    """The content page had zero [role=tab] live; posted and scheduled share one table."""
    assert S.CONTENT_HAS_SCHEDULED_TAB is False
    assert not hasattr(S, "SCHEDULED_TAB_TEXT"), \
        "a tab anchor implies a tab to click, and there is none"


def test_the_row_anchor_excludes_the_column_header():
    """The header is built from the same RowLayout component and carries text.

    Without the exclusion the header reads as a settled row, `scheduled_ready_js` returns
    true before any real row has arrived, the list reads empty, and the batch double-posts.
    """
    assert "components_PostTableHeader" in S.POST_ROW
    assert ":not(" in S.POST_ROW and ":has(" in S.POST_ROW


def test_the_two_row_anchors_are_different_in_kind_not_near_copies():
    """A fallback that is a near-copy of the primary fails the same way the primary does."""
    assert S.POST_ROW != S.POST_ROW_FALLBACK
    assert "data-tt" in S.POST_ROW and "data-tt" not in S.POST_ROW_FALLBACK


def test_the_radio_and_the_submit_button_share_a_word_but_not_a_role():
    """SCHEDULE_RADIO_NAME == SCHEDULE_BUTTON_TEXT ("Schedule"), the same collision risk the
    old SCHEDULE_TOGGLE_TEXT/NOT_INSIDE_A_BUTTON guard existed for. That guard is gone because
    it is no longer needed: get_by_role("radio", ...) is scoped by role and can never resolve
    to the <button> that submits, unlike the old switch-or-text lookup it replaced.
    """
    assert S.SCHEDULE_RADIO_NAME == S.SCHEDULE_BUTTON_TEXT, \
        "if these ever differ, say so here — the point is that they are the same word"
    assert not hasattr(S, "NOT_INSIDE_A_BUTTON"), \
        "a role-scoped radio lookup does not need a not-inside-a-button guard"


def test_the_page_ready_anchors_are_ones_that_exist_before_anything_is_chosen():
    """Both are real, observed anchors, not the elements whose presence is being probed."""
    assert S.UPLOAD_PAGE_READY == S.SELECT_VIDEO_CONTAINER
    assert S.CONTENT_PAGE_READY == S.POSTS_TABLE
