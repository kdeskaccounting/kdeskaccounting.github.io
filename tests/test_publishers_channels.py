"""scripts/publishers/channels.py -- the venture's channel identity, renamed 2026-11-09."""
from publishers import channels as C


def test_current_identity_is_park_detective():
    assert C.YOUTUBE_CHANNEL_NAME == "Park Detective"
    assert C.YOUTUBE_HANDLE == "@ParkDetective"
    assert C.TIKTOK_HANDLE == "parkdetective"
    assert C.INSTAGRAM_HANDLE == "park.detective"


def test_legacy_values_are_kept_for_history_and_differ_from_current():
    assert C.LEGACY_YOUTUBE_CHANNEL_NAME == "ParkSheet" != C.YOUTUBE_CHANNEL_NAME
    assert C.LEGACY_INSTAGRAM_HANDLE == "park.sheet" != C.INSTAGRAM_HANDLE
    assert C.LEGACY_TIKTOK_HANDLE == "park.sheet" != C.TIKTOK_HANDLE


def test_profile_urls():
    assert C.tiktok_profile_url() == "https://www.tiktok.com/@parkdetective"
    assert C.instagram_profile_url() == "https://www.instagram.com/park.detective/"


def test_drivers_read_the_name_from_this_module():
    from browser import selectors_youtube as S
    from browser import instagram_web as ig
    assert S.CHANNEL_NAME is C.YOUTUBE_CHANNEL_NAME
    assert ig.HANDLE is C.INSTAGRAM_HANDLE
