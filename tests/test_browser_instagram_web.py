"""scripts/browser/instagram_web.py -- the pure parsing and verification logic.

The 2026-10-06 false failure: the profile grid renders 12 tiles on load, so once @park.sheet had
13 posts the tile count could not rise and a live reel was reported as exit 2. Verification now
reads the header's "N posts" figure and the newest tile's caption; the tile count is a fallback.
"""
import pytest
from browser import instagram_web as ig

TITLE = "Disney Secret #2: the Tree of Life at Animal Kingdom hides an oil rig."
CAPTION = TITLE + " The Disney World icon is 145 feet tall...\n\n#animalkingdom"


@pytest.mark.parametrize("text, want", [
    ("13 posts", 13),
    ("1,234 posts", 1234),
    ("1 post", 1),
    ("0 posts", 0),
    ("Note...\npark.sheet\nSantiago Kdesk\n13 posts\n0 followers\n0 following\nbio", 13),
    ("0 Followers, 0 Following, 13 Posts - See Instagram photos and videos", 13),
    ("12,345,678 posts", 12345678),
    ("13\nposts", 13),
])
def test_parse_post_count(text, want):
    assert ig.parse_post_count(text) == want


@pytest.mark.parametrize("text", [None, "", "no figure here", "1.2K posts", "3M posts", "13 followers"])
def test_parse_post_count_none(text):
    assert ig.parse_post_count(text) is None


def test_matches_post_on_title_or_caption_prefix():
    assert ig.matches_post(CAPTION.upper(), TITLE)
    assert ig.matches_post("  " + CAPTION.replace(" ", "\n"), "", CAPTION)
    assert not ig.matches_post("Disney Secret #1: something else", TITLE, CAPTION)
    assert not ig.matches_post("", TITLE, CAPTION)
    assert not ig.matches_post(None, TITLE, CAPTION)
    assert not ig.matches_post("anything", "", "")


def _verify(**kw):
    base = dict(before_count=12, after_count=12, before_href="/park.sheet/reel/OLD/",
                after_href="/park.sheet/reel/OLD/", after_alt="Disney Secret #1: older post",
                title=TITLE, caption=CAPTION, before_tiles=12, after_tiles=12)
    base.update(kw)
    return ig.verify(**base)


def test_header_count_rise_confirms_even_with_12_tiles():
    ok, why = _verify(after_count=13)
    assert ok and "12 -> 13" in why


def test_new_matching_newest_tile_confirms_when_header_lags():
    ok, why = _verify(after_href="/park.sheet/reel/NEW/", after_alt=CAPTION)
    assert ok and "NEW" in why


def test_new_tile_with_other_caption_does_not_confirm():
    assert not _verify(after_href="/park.sheet/reel/NEW/", after_alt="something unrelated")[0]


def test_tile_count_is_only_a_fallback():
    # header readable and unchanged: a tile-count rise alone is not trusted
    assert not _verify(before_tiles=5, after_tiles=6)[0]
    # header unreadable: tile-count rise is accepted
    ok, why = _verify(before_count=None, after_count=None, before_tiles=5, after_tiles=6)
    assert ok and "unreadable" in why


def test_unconfirmed_after_shared_toast_says_probably_live_and_no_retry():
    ok, why = _verify()
    assert not ok
    assert "has been shared" in why and "PROBABLY LIVE" in why
    assert "Do NOT re-run with --go" in why
    assert "instagram.com/park.sheet/" in why


# --- Trial Reels (--trial). instagram.com has no trial option (2026-10-09), so --trial only checks and aborts.

# The New reel dialog text as read on 2026-10-09, with Accessibility and Advanced settings expanded.
NEW_REEL_2026_10_09 = """New reel
Share
Tag people
park.sheet
Add a caption...
0/2,200
Add AI label
This label is required for realistic photos and videos made with AI. People will see it on your content. Learn more
Accessibility
Auto-generated captions
Auto-generated captions added to your video help people with hearing impairments. They are only available on the iOS and Android apps and may take a few minutes to appear.
Advanced settings
Hide like and view counts on this post
Only you will see the total number of likes and views on this post. You can change this later by going to the ··· menu at the top of the post. To hide like counts on other people's posts, go to your account settings. Learn more
Turn off commenting
You can change this later by going to the ··· menu at the top of your post.
Your reel will be shared with your followers in their feeds and can be seen on your profile. It may also appear in places like Reels, where anyone can see it."""


def test_web_new_reel_screen_has_no_trial_control():
    assert ig.trial_control_label(NEW_REEL_2026_10_09) is None


@pytest.mark.parametrize("text, want", [
    ("New reel\nTrial\nShare", "Trial"),
    ("Advanced settings\n  Share as trial reel  \nTurn off commenting", "Share as trial reel"),
    ("TRIAL REELS\nOnly shown to non-followers", "TRIAL REELS"),
])
def test_trial_control_label_finds_a_trial_line(text, want):
    assert ig.trial_control_label(text) == want


@pytest.mark.parametrize("text", [None, "", "Industrial Light", "Free trials\n", "Trials and tribulations"])
def test_trial_control_label_needs_the_word_trial(text):
    assert ig.trial_control_label(text) is None


def test_trial_messages_say_nothing_was_shared_and_point_to_the_app():
    for msg in (ig.TRIAL_MISSING, ig.trial_found_message("Trial")):
        assert "Nothing was shared" in msg and "discarded" in msg and "app" in msg


def test_trial_check_never_shares_or_types_a_caption():
    # --trial must never fall back to a normal post: its code path has no Share click and no caption typing
    import inspect
    for fn in (ig.run_trial_check, ig.open_new_reel, ig.discard):
        src = inspect.getsource(fn)
        assert '"Share"' not in src and "'Share'" not in src
        assert "keyboard.type" not in src


def test_trial_is_routed_before_the_profile_read_and_share():
    import inspect
    src = inspect.getsource(ig.main)
    assert src.index("if args.trial") < src.index("HANDLE}/") < src.index('"Share"')
