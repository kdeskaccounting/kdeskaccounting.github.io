"""PoC v4 renderer keys (2026-11-04): the strip plate, light captions, tags.clear, end.loop_to_start."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))

import captions  # noqa: E402
import illustrate  # noqa: E402
import make_short  # noqa: E402

BRAND = {"font": "Carlito, Arial, sans-serif", "font_bundle": "carlito"}


def _plate(text, frac=0.04):
    return captions.plate_settings({"plate": {"text": text, "style": "strip", "seconds": 2.6,
                                              "headline_frac": frac}})


# --- strip -------------------------------------------------------------------------------

def test_strip_lines_keep_newlines_and_balance_a_long_line():
    assert captions.strip_lines("NO KID,\nNO RIDE") == ["NO KID,", "NO RIDE"]
    assert captions.strip_lines("ADULTS RIDE ONLY WITH KIDS") == ["ADULTS RIDE", "ONLY WITH KIDS"]


def test_strip_refuses_three_lines_and_five_word_lines():
    with pytest.raises(ValueError):
        captions.strip_lines("A\nB\nC")
    with pytest.raises(ValueError):
        captions.strip_lines("ONE TWO THREE FOUR FIVE\nSIX")
    with pytest.raises(ValueError):
        _plate("A\nB\nC")


def test_strip_box_is_compact_mid_frame_and_inside_the_safe_zone():
    box = captions.strip_box(_plate("NO KID,\nNO RIDE"), BRAND, 1080, 1920)
    left, top, right, bottom = box
    assert 120 <= left and right <= 880
    assert right - left < 760 * 0.8                      # never full-bleed
    assert 0.38 <= (top + bottom) / 2 / 1920 <= 0.45


def test_strip_refuses_a_line_wider_than_the_safe_zone():
    with pytest.raises(ValueError):
        captions.strip_box(_plate("WWWWWW WWWWWW WWWWWW", 0.097), BRAND, 1080, 1920)


def test_strip_html_has_no_icon_and_no_caret():
    html = captions.plate_html(_plate("NO KID,\nNO RIDE"), "#2FBF5B", BRAND, 1080, 1920)
    assert "<svg" not in html and "caret" not in html
    assert "NO KID,<br>NO RIDE" in html


def test_search_plate_is_still_the_default_shape():
    plate = captions.plate_settings({"plate": {"text": "why", "style": "search"}})
    assert "<svg" in captions.plate_html(plate, "#2FBF5B", BRAND, 1080, 1920)


# --- light captions ------------------------------------------------------------------------

WORDS = [{"text": t, "start": a, "end": b} for t, a, b in [
    ("Riders", 0.05, 0.40), ("have", 0.41, 0.55), ("to", 0.56, 0.62), ("be", 0.65, 0.75),
    ("between", 0.76, 1.10), ("thirty-six", 1.12, 1.60), ("and", 1.61, 1.70)]]


def test_split_light_caps_words_and_chars_and_keeps_every_word():
    cues = captions.build_cues(WORDS, 10.0)
    light = captions.split_light(cues)
    assert [w.text for c in light for w in c.words] == [w["text"] for w in WORDS]
    for cue in light:
        assert len(cue.words) <= 2 or cue.end - cue.start <= 0.3
        assert len(cue.text) <= captions.LIGHT_MAX_CHARS or len(cue.words) == 1
    for a, b in zip(light, light[1:]):
        assert a.end <= b.start
    assert light[0].start == cues[0].start


def test_split_light_starts_on_the_words_own_start():
    light = captions.split_light(captions.build_cues(WORDS, 0.0))
    for cue in light[1:]:
        assert cue.start == cue.words[0].start


def test_light_style_overrides_position_and_size():
    cfg = captions.settings({"captions": {"enabled": True, "position": "top", "size": "large",
                                          "style": "light"}})
    assert (cfg.style, cfg.position, cfg.size) == ("light", "lower_middle", "light")
    with pytest.raises(ValueError):
        captions.settings({"captions": {"style": "huge"}})


def test_light_band_sits_lower_middle_inside_the_conservative_zone():
    left, top, right, bottom = captions.caption_box(1080, 1920, None, "lower_middle", "light")
    assert (left, right) == (120, 880)
    assert 0.56 <= (top + bottom) / 2 / 1920 <= 0.62
    assert bottom <= 1248
    big = captions.size_rules("large")
    light = captions.size_rules("light")
    ratio = (light[0] * light[1]) / (big[0] * big[1])
    assert 0.65 <= ratio <= 0.75


def test_symmetric_band_html_is_unchanged():
    cue = captions.build_cues(WORDS[:2], 0.0)[0]
    box = captions.caption_box(1080, 1920, None, "top", "large")
    html = captions.caption_html(cue, 0, "#2FBF5B", BRAND, 1080, box, size="large")
    assert f"padding:0 {box[0]}px}}" in html


# --- tags.clear ------------------------------------------------------------------------------

def test_tag_settings_default_and_refusal():
    assert make_short.tag_settings({})["clear"] == "next_scene"
    assert make_short.tag_settings({"tags": {"clear": "next_cue"}})["clear"] == "next_cue"
    with pytest.raises(SystemExit):
        make_short.tag_settings({"tags": {"clear": "soon"}})


def test_tags_clear_at_the_first_phrase_after_min_s():
    words = [{"text": t, "start": a, "end": b} for t, a, b in [
        ("You", 0.05, 0.2), ("hang", 0.2, 0.4), ("under", 0.4, 0.6), ("ten-foot", 0.64, 1.0),
        ("wings", 1.0, 1.3), ("and", 1.3, 1.45), ("swing", 1.52, 1.8), ("slowly", 1.8, 2.1)]]
    scene = {"elements": [{"type": "tag", "text": "10-FT WINGS", "at": [0.5, 0.4],
                           "enter": {"t": 0.64, "how": "pop"}},
                          {"type": "emoji", "glyph": "x", "at": [0.5, 0.5],
                           "enter": {"t": 0.64, "how": "pop"}}]}
    done = make_short.clear_tags_at_next_cue(scene, words, 3.0)
    assert done == [(0, 0.64, 1.52)]
    assert scene["elements"][0]["exit"] == {"t": 1.52}
    assert "exit" not in scene["elements"][1]


def test_exit_renders_data_t1_and_hide_js_only_when_present():
    el = {"type": "tag", "text": "A", "at": [0.5, 0.4], "enter": {"t": 0.1, "how": "pop"}}
    plain = illustrate.scene_html({"elements": [dict(el)]}, transparent=True)
    assert "data-t1" not in plain
    gone = illustrate.scene_html({"elements": [dict(el, exit={"t": 1.5})]}, transparent=True)
    assert 'data-t1="1.5000"' in gone and "visibility" in gone


# --- end.loop_to_start + the snap ------------------------------------------------------------

def test_end_settings():
    assert make_short.end_settings({}) is None
    assert make_short.end_settings({"end": {"loop_to_start": True, "tail_s": 0.6}}) == {
        "loop_to_start": True, "tail_s": 0.6}
    with pytest.raises(SystemExit):
        make_short.end_settings({"end": {"loop_to_start": True, "tail_s": 9}})


def test_caption_filter_snap_blur_and_plate_spans():
    steps = make_short.caption_filter([], 1000, 2.7, [(0.0, 2.7), (20.2, 21.0)],
                                      (2.55, 2.7, 10.0))
    joined = ";".join(steps)
    assert "gblur=sigma=10.0000" in joined
    assert "between(t,0,2.70)+between(t,20.200,21.000)" in joined
    assert make_short.caption_filter([], 1000, 1.4)[0].endswith("between(t,0,1.40)'[p0]")
