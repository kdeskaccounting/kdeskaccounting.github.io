"""PoC v5 renderer primitives (2026-11-04): callouts, the easing table, `captions.style: word`,
the frame-0 radial zoom-blur `open:`, and the measured verdict `fx.style: wash`.

Every default asserted here is a number from the grammar study's SPEC (section 6)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))

import callouts  # noqa: E402
import captions  # noqa: E402
import grammar  # noqa: E402
import illustrate  # noqa: E402
import make_short  # noqa: E402


def _words(*pairs):
    """[(text, start, end)] -> words.json-shaped dicts on a scene clock."""
    return [{"text": t, "start": a, "end": b} for t, a, b in pairs]


WORDS = _words(("It", 0.10, 0.20), ("stood", 0.20, 0.45), ("456", 0.50, 1.10),
               ("feet", 1.10, 1.40), ("tall.", 1.40, 1.80))
ROWS = illustrate.word_rows(WORDS)


def _resolve(v):
    return illustrate.resolve_time(v, ROWS, "test", "when")


# --- the easing table ------------------------------------------------------------------------

def test_easing_table_is_the_measured_one():
    e = callouts.EASING
    assert e["pop_badge"] == {"from": 0.60, "peak": 1.15, "peak_ms": 200, "settle_ms": 300}
    assert e["pop_arrow"] == {"from": 0.18, "peak": 1.10, "peak_ms": 133, "settle_ms": 167}
    assert e["pop_caption"] == {"from": 0.94, "peak": 1.05, "peak_ms": 80, "settle_ms": 150}
    assert e["pop_stamp"] == {"from": 0.90, "peak": 1.03, "peak_ms": 67, "settle_ms": 100}
    assert e["slide_in"] == {"curve": "ease_out_cubic", "ms": 300}


def test_scale_keyframes_hide_before_entry_and_peak_at_the_measured_instant():
    css = callouts.scale_keyframes("k", callouts.EASING["pop_badge"])
    assert "0%{opacity:0;transform:scale(0.6)}" in css
    assert "0.01%{opacity:1;transform:scale(0.6)" in css
    assert "66.667%{opacity:1;transform:scale(1.15)" in css      # 200 of 300 ms
    assert css.endswith("100%{opacity:1;transform:scale(1)}}")


def test_ease_aliases():
    assert callouts.ease_of("overshoot", "badge") == "pop_badge"
    assert callouts.ease_of("overshoot", "arrow") == "pop_arrow"
    assert callouts.ease_of("pop", "text") == "pop_stamp"
    assert callouts.ease_of("slide_in", "sticker") == "slide_in"


# --- checking -----------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    [{"type": "balloon", "when": 1.0, "anchor": {"x": 0.5, "y": 0.5}}],
    [{"type": "badge", "when": 1.0}],                                 # no text
    [{"type": "badge", "text": "#1"}],                                 # no when
    [{"type": "arrow", "when": 1.0}],                                  # no anchor
    [{"type": "sticker", "when": 1.0, "anchor": {"x": 0.5, "y": 0.8}}],  # no src
    [{"type": "badge", "text": "#1", "when": 1.0, "hold": "forever"}],
    [{"type": "badge", "text": "#1", "when": 1.0, "ease": "bounce"}],
    [{"type": "badge", "text": "#1", "when": 1.0, "wobble": True}],
    [{"type": "arrow", "when": 1.0, "anchor": {"x": 0.5, "y": 0.5}, "direction": "sideways"}],
    [{"type": "arrow", "when": 1.0, "anchor": {"x": 0.5, "y": 0.5,
                                               "track": [[0.2, 0.5, 0.5], [0.4, 0.4, 0.5]]}}],
    [],
])
def test_check_refuses_by_name(bad):
    with pytest.raises(ValueError):
        callouts.check(bad)


# --- compiling ---------------------------------------------------------------------------------

def test_badge_defaults_are_the_spec_defaults():
    [el] = callouts.compile_callouts([{"type": "badge", "text": "#1", "when": {"word": "456"}}],
                                     _resolve, [1.2], 3.0)
    assert el["type"] == "callout" and el["callout"] == "badge"
    assert el["at"] == [0.185, 0.12]                       # the list-number corner
    assert el["size"] == 0.044
    assert el["ease"] == "pop_badge" and el["in_ms"] == 300
    assert el["enter"]["t"] == pytest.approx(0.58)          # word 0.50 + 80 ms
    assert el["exit"] == {"t": 1.2}                         # hold: next_cut
    assert el["sfx"] == "ding"
    assert el["sticker"] is False                           # no white border on a callout


def test_arrow_holds_1200_ms_and_tracks():
    raw = [{"type": "arrow", "when": 0.5, "offset_ms": 0,
            "anchor": {"x": 0.6, "y": 0.4, "track": [[0, 0.6, 0.4], [0.5, 0.5, 0.42]]}}]
    [el] = callouts.compile_callouts(raw, _resolve, [], 5.0)
    assert el["ease"] == "pop_arrow" and el["in_ms"] == 167
    assert el["exit"]["t"] == pytest.approx(0.5 + 0.167 + 1.2)
    assert el["track"] == [[0, 0.6, 0.4], [0.5, 0.5, 0.42]]


def test_hold_past_the_scene_end_leaves_the_cut_to_end_it():
    [el] = callouts.compile_callouts(
        [{"type": "badge", "text": "x", "when": 1.0, "hold": 5000}], _resolve, [], 2.0)
    assert "exit" not in el
    [el] = callouts.compile_callouts(
        [{"type": "badge", "text": "x", "when": 1.0, "hold": "scene"}], _resolve, [1.5], 2.0)
    assert "exit" not in el


def test_sticker_enters_from_the_nearest_edge_and_whooshes():
    raw = [{"type": "sticker", "src": "/x.png", "when": 0.5, "anchor": {"x": 0.5, "y": 0.75}},
           {"type": "sticker", "src": "/x.png", "when": 0.5, "anchor": {"x": 0.15, "y": 0.5}}]
    a, b = callouts.compile_callouts(raw, _resolve, [], 3.0)
    assert (a["enter_from"], b["enter_from"]) == ("bottom", "left")
    assert a["ease"] == "slide_in" and a["in_ms"] == 300 and a["sfx"] == "whoosh"


def test_sfx_null_is_silent_and_late_entry_is_refused():
    [el] = callouts.compile_callouts(
        [{"type": "text", "text": "GONE", "when": 0.2, "sfx": None,
          "anchor": {"x": 0.5, "y": 0.4}}], _resolve, [], 2.0)
    assert "sfx" not in el and el["ease"] == "pop_stamp"
    with pytest.raises(ValueError):
        callouts.compile_callouts([{"type": "text", "text": "x", "when": 3.0,
                                    "anchor": {"x": 0.5, "y": 0.4}}], _resolve, [], 2.0)


def test_sticker_offset_puts_it_wholly_off_frame():
    el = {"at": [0.5, 0.75], "size": 0.5, "enter_from": "bottom"}
    dx, dy = callouts.sticker_offset(el, aspect=1.0)
    top_after = 0.75 * 1920 - 0.25 * 1080 + dy
    assert dx == 0 and top_after > 1920


# --- HTML ------------------------------------------------------------------------------------

def _compiled(raw, cuts=(), dur=4.0):
    return callouts.compile_callouts(raw, _resolve, list(cuts), dur)


def test_callout_html_is_seekable_and_exits_with_the_cut():
    els = _compiled([{"type": "badge", "text": "456 FT", "when": {"word": "456"},
                      "anchor": {"x": 0.6, "y": 0.2}}], cuts=[1.5])
    page = illustrate.scene_html({"kind": "illustration", "elements": els}, transparent=True)
    assert 'id="el0" data-t1="1.5000"' in page            # the snap at the next cut
    assert 'data-t0="0.5800"' in page
    assert "kf-el0-in" in page and "Nunito Bundled" in page
    assert "var outs = document.querySelectorAll('[data-t1]')" in page


def test_arrow_scales_out_of_its_tip_and_points_down_left():
    [el] = _compiled([{"type": "arrow", "when": 0.5, "anchor": {"x": 0.6, "y": 0.4}}])
    html, css = callouts.callout_html(el, 3)
    assert "transform-origin:0 0" in html
    assert "rotate(135deg)" in html
    assert "#FFC800" in html and "scale(0.18)" in css and "scale(1.1)" in css


def test_sticker_has_no_outline_no_shadow_and_slides():
    [el] = _compiled([{"type": "sticker", "src": "/tmp/s.png", "when": 0.5,
                       "anchor": {"x": 0.5, "y": 0.8}}])
    html, css = callouts.callout_html(el, 0, image_uri=lambda p: "data:image/png;base64,AA",
                                      png_size=lambda p: (100, 200))
    assert "sticker" not in html.split(">")[0].replace("callout-sticker", "")
    assert "drop-shadow" not in html
    assert "translate(0.0px," in css and callouts.EASE_OUT_CUBIC in css


def test_track_keyframes_translate_by_the_subject_offsets():
    css, total = callouts.track_keyframes("t", [[0, 0.5, 0.5], [1.0, 0.4, 0.5]], 0.5, 0.5)
    assert total == 1.0
    assert "100.000%{transform:translate(-108.0px,0.0px)}" in css


def test_slide_out_ends_on_the_exit():
    [el] = _compiled([{"type": "sticker", "src": "/s.png", "when": 0.5, "out": "slide_out",
                       "anchor": {"x": 0.5, "y": 0.8}}], cuts=[2.0])
    html, css = callouts.callout_html(el, 0, image_uri=lambda p: "data:,",
                                      png_size=lambda p: (100, 100))
    assert 'data-t0="1.8000"' in html                       # 200 ms before the 2.0 s cut
    assert "kf-el0-out" in css


def test_compiled_callout_validates_as_an_element():
    els = _compiled([{"type": "circle", "when": 0.5, "anchor": {"x": 0.5, "y": 0.5}}])
    illustrate.validate_spec({"scenes": [{"kind": "illustration", "seconds": 4.0,
                                          "elements": els}]})
    assert illustrate.scene_events({"elements": els}) == [{"t": 0.58, "sfx": "pop"}]


# --- sounds: callouts ride the grammar thinning ------------------------------------------------

def test_callout_events_are_separate_from_element_events():
    els = _compiled([{"type": "badge", "text": "#1", "when": 0.5}])
    scene = {"elements": els + [{"type": "emoji", "glyph": "x", "at": [0.5, 0.5],
                                 "enter": {"t": 1.0, "how": "pop"}, "sfx": "pop"}]}
    rows = [{"scene": 3, "start": 10.0}]
    assert make_short.callout_events([(3, scene)], rows) == [{"at": 10.58, "role": "ding"}]
    assert make_short.illustration_events([(3, scene)], rows) == [{"at": 11.0, "role": "pop"}]


# --- captions.style: word -------------------------------------------------------------------

def _phrase(*pairs, end=None):
    ws = tuple(captions.Word(t, a, b) for t, a, b in pairs)
    return captions.Cue(" ".join(w.text for w in ws), ws[0].start, end or ws[-1].end, ws)


def test_word_style_settings():
    cfg = captions.settings({"captions": {"enabled": True, "style": "word",
                                          "keywords": {"456": "topic", "Kingda": "place"}}})
    assert (cfg.position, cfg.size, cfg.keyword_every) == ("word", "word", 7)
    assert dict(cfg.keywords) == {"456": "#F7E63C", "kingda": "#3BF7FA"}
    with pytest.raises(ValueError):
        captions.settings({"captions": {"enabled": True, "keywords": {"a": "topic"}}})


def test_word_band_is_centred_at_057_inside_the_safe_zone():
    l, t, r, b = captions.caption_box(1080, 1920, None, "word", "word")
    assert (t + b) / 2 / 1920 == pytest.approx(0.57, abs=0.002)
    assert (l + r) / 2 == 540 and 120 <= l and r <= 880 and b <= 1440


def test_split_words_is_one_word_a_cue_with_no_gaps():
    cue = _phrase(("They", 0.10, 0.25), ("blew", 0.25, 0.50), ("up", 0.50, 0.58),
                  ("it.", 0.58, 0.90), end=1.2)
    out = captions.split_words([cue])
    assert [c.text for c in out] == ["They", "blew", "up it."]     # "up" is 80 ms: joined
    assert out[0].start == 0.10 and out[-1].end == 1.2
    for a, b in zip(out, out[1:]):
        assert b.start - a.end == pytest.approx(captions.GAP_S)


def test_keyword_colours_named_and_auto_cadence():
    cues = captions.split_words([_phrase(*[(w, i * 0.3, i * 0.3 + 0.3) for i, w in enumerate(
        "the tallest roller coaster on Earth was 456 feet and it is gone now".split())])])
    named = captions.keyword_colours(cues, (("456", "#F7E63C"),))
    assert [c.text for c, col in zip(cues, named) if col] == ["456"]
    auto = captions.keyword_colours(cues, (), 7)
    assert sum(1 for c in auto if c) == 2 and auto[7] == "#F7E63C"   # "456" wins its block


def test_caption_pop_curve_is_the_measured_one():
    e = callouts.EASING["pop_caption"]
    assert captions.pop_scale(0.0, e) == 0.94
    assert captions.pop_scale(0.080, e) == pytest.approx(1.05)
    assert captions.pop_scale(0.150, e) == 1.0
    assert 1.0 < captions.pop_scale(0.120, e) < 1.05


def test_word_track_plan_frames():
    cues = [captions.Cue("a", 0.0, 0.5, ()), captions.Cue("b", 0.6, 1.0, ())]
    plan = captions.word_track_plan(cues, 1.2, callouts.EASING["pop_caption"], fps=10)
    assert plan[0] == (0, 0.94) and plan[5] == (None, 1.0) and plan[6][0] == 1
    assert plan[-1] == (None, 1.0)


def test_word_caption_page_is_as_spoken_and_rounded():
    cue = _phrase(("Earth.", 0.0, 0.4))
    page = captions.word_caption_html(cue, "#3BF7FA", 1080, (200, 994, 880, 1205), 1920,
                                      callouts.font_face_css(), callouts.ROUNDED_FAMILY)
    assert ">Earth</div>" in page and "uppercase" not in page
    assert "font-weight:900" in page and "#3BF7FA" in page


# --- open: frame-0 radial zoom-blur + ding -----------------------------------------------------

def test_open_defaults_and_strength_decay():
    cfg = callouts.parse_open({"open": {}})
    assert cfg["ms"] == 180 and cfg["sfx"] == "ding"
    k = callouts.open_strengths(cfg, 30)
    assert len(k) == 5 and k[0] == cfg["strength"] and k == sorted(k, reverse=True)
    assert callouts.parse_open({}) is None
    with pytest.raises(ValueError):
        callouts.parse_open({"open": {"frame0": "spin"}})


def test_open_ding_is_an_opening_sting_on_frame_0():
    sting = callouts.open_sting(callouts.parse_open({"open": {"sfx": "ding"}}))
    assert sting["impact"] == 0.0 and sting["layers"][0]["src"] == "bundle:ding"
    assert callouts.open_sting(callouts.parse_open({"open": {"sfx": None}})) is None


def test_zoom_stack_is_identity_at_zero():
    PIL = pytest.importorskip("PIL.Image")
    img = PIL.new("RGB", (8, 8), (10, 20, 30))
    assert make_short.zoom_stack(img, 0.0) is img


# --- fx.style: wash -------------------------------------------------------------------------

def test_wash_bad_is_red_024_with_vignette_and_peaks_on_the_word():
    fx = grammar.parse_fx({"fx": {"verdict": "bad", "style": "wash", "at": {"word": "feet"}}})
    w = grammar.verdict_window(fx, WORDS, 4.0)
    assert w.t0 == pytest.approx(1.10 - 0.08)
    assert w.ramp_in == 0.2 and w.ramp_out == 0.2
    assert w.t1 == pytest.approx(w.t0 + 0.2 + 0.33 + 0.2)
    assert w.filter.startswith("lutrgb=r='val*0.7600+61.20':g='val*0.7600+0.00'")
    assert "vignette" in w.filter


def test_wash_good_is_green_044_held_to_the_cut():
    fx = grammar.parse_fx({"fx": {"verdict": "good", "style": "wash", "at": {"word": "456"}}})
    w = grammar.verdict_window(fx, WORDS, 4.0)
    assert w.t1 == 4.0 and w.ramp_out == 0.0 and w.ramp_in == 0.17
    assert "g='val*0.5600+66.00'" in w.filter and "vignette" not in w.filter


def test_wash_refuses_grade_keys_and_grade_refuses_wash_keys():
    with pytest.raises(ValueError):
        grammar.parse_fx({"fx": {"verdict": "bad", "style": "wash", "at": 1.0, "strength": 0.5}})
    with pytest.raises(ValueError):
        grammar.parse_fx({"fx": {"verdict": "bad", "at": 1.0}})
    with pytest.raises(ValueError):
        grammar.parse_fx({"fx": {"verdict": "bad", "style": "wash"}})


def test_grade_without_style_is_unchanged():
    fx = grammar.parse_fx({"fx": {"verdict": "good"}})
    assert "style" not in fx and grammar.verdict_window(fx, WORDS, 2.0).filter.startswith(
        "colorchannelmixer=")


def test_a_silent_callout_never_gets_the_on_tag_pop():
    els = _compiled([{"type": "badge", "text": "#1", "when": 0.5, "sfx": None}])
    scene = {"elements": els}
    rows = [{"scene": 0, "start": 0.0}]
    assert grammar.tag_events([(0, make_short.callout_free(scene))], rows) == []
    assert grammar.tag_events([(0, scene)], rows) != []      # what the filter prevents


# --- PoC v6 (2026-11-04): sticker labels, a configurable opening sound -------------------------

def test_sticker_labels_are_drawn_on_the_sticker_and_move_with_it():
    [el] = _compiled([{"type": "sticker", "src": "/tmp/s.png", "when": 0.5,
                       "anchor": {"x": 0.5, "y": 0.5}, "size": 0.5, "ease": "overshoot",
                       "labels": [{"text": "456 FT", "x": 0.3, "y": 0.1},
                                  {"text": "382 FT", "x": 0.7, "y": 0.3, "color": "#F7E63C"}]}])
    assert el["labels"][1]["text"] == "382 FT"
    html, css = callouts.callout_html(el, 0, image_uri=lambda p: "data:image/png;base64,AA",
                                      png_size=lambda p: (100, 200))
    # the labels sit inside the sticker's own box (540 x 1080 px), below the entrance node
    assert "width:540.0px;height:1080.0px" in html
    assert html.index("456 FT") > html.index("kf-el0-in") and "382 FT" in html
    assert "left:162.0px;top:108.0px" in html and "#F7E63C" in html
    assert callouts.ROUNDED_FAMILY in css


@pytest.mark.parametrize("bad", [
    {"type": "badge", "text": "x", "when": 0.1, "labels": [{"text": "a", "x": 0, "y": 0}]},
    {"type": "sticker", "src": "a.png", "when": 0.1, "anchor": {"x": 0.5, "y": 0.5},
     "labels": [{"text": "a", "x": 0.5}]},
    {"type": "sticker", "src": "a.png", "when": 0.1, "anchor": {"x": 0.5, "y": 0.5},
     "labels": [{"text": "a", "x": 0.5, "y": 0.5, "font": "x"}]},
])
def test_labels_are_checked(bad):
    with pytest.raises(callouts.CalloutError):
        callouts.check([bad])


def test_open_sfx_mapping_names_any_sound():
    cfg = callouts.parse_open({"open": {"sfx": {"src": "bundle:chime_quick", "gain_db": -12}}})
    sting = callouts.open_sting(cfg)
    assert sting["layers"][0] == {"src": "bundle:chime_quick", "at": 0.0, "gain_db": -12.0}
    trimmed = callouts.open_sting(callouts.parse_open(
        {"open": {"sfx": {"src": "bundle:chime_quick", "end": 0.9}}}))
    assert trimmed["layers"][0]["end"] == 0.9 and trimmed["layers"][0]["fade_out"] == 0.08
    with pytest.raises(callouts.CalloutError):
        callouts.parse_open({"open": {"sfx": {"gain_db": -3}}})
