"""`callout.type: hoot` (2026-11-09): Hoot, the Park Detective owl, as a v6 motion-graphic callout.

The pose set is the ParkSheet repo's media/brand/hoot/hoot.json; here a fixture with the same
shape (geometry measured from the real set, rounded) stands in, so this file needs no other repo.
"""
import copy
import json
import pathlib
import struct
import sys
import zlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))

import callouts  # noqa: E402
import illustrate  # noqa: E402
import make_short  # noqa: E402

BODY = [0.17, 0.13, 0.88, 0.85]
SET = {
    "poses": {
        "neutral": {"src": "/h/neutral.png", "body": BODY},
        "point_left": {"src": "/h/pl.png", "body": [0.02, 0.13, 0.95, 0.83], "tip": [0.03, 0.43]},
        "point_right": {"src": "/h/pr.png", "body": [0.05, 0.13, 0.98, 0.85], "tip": [0.97, 0.41]},
        "point_up": {"src": "/h/pu.png", "body": [0.12, 0.03, 0.83, 0.87], "tip": [0.15, 0.04]},
        "point_down": {"src": "/h/pd.png", "body": [0.02, 0.12, 0.98, 0.85], "tip": [0.03, 0.66]},
        "badge": {"src": "/h/badge.png", "body": BODY, "badge": [0.495, 0.569, 0.116]},
        "nope": {"src": "/h/nope.png", "body": BODY, "badge": [0.74, 0.33, 0.15],
                 "badge_color": "#E5202A"},
        "surprised": {"src": "/h/s.png", "body": BODY},
    },
    "bubble": {"src": "/h/bubble.png", "body": [0.08, 0.27, 0.92, 0.71],
               "text_box": [0.18, 0.33, 0.81, 0.56], "tail": [0.22, 0.71]},
}
BAND = (200 / 1080, 0.515, 880 / 1080, 0.625)       # the `style: word` caption band
WORDS = [{"text": t, "start": a, "end": b} for t, a, b in
         (("a", 0.1, 0.2), ("perfect", 0.2, 0.5), ("circle", 0.5, 0.9), ("12", 1.0, 1.3))]
ROWS = illustrate.word_rows(WORDS)


def _resolve(v):
    return illustrate.resolve_time(v, ROWS, "test", "when")


def _hoot(**kw):
    c = {"type": "hoot", "when": {"word": "circle"}, "_hoot": copy.deepcopy(SET)}
    c.update(kw)
    return c


def _compile(*raw, cuts=(2.0,), dur=3.0, avoid=(BAND,)):
    return callouts.compile_callouts(list(raw), _resolve, list(cuts), dur, "t", avoid=list(avoid))


# --- checking ------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"say": "one two three four five six seven eight nine"},     # > 2 lines of 4
    {"say": ""},
    {"bubble": "above"},
    {"badge_text": "TOO LONG TEXT"},
    {"badge_text": "#1", "say": "and words"},
    {"point_to": {"x": 1.5, "y": 0.2}},
    {"in_ms": 500},                                               # slide-in is 230-370 ms
    {"in_ms": 150},
    {"ease": "pop_arrow"},
    {"blur_bg": {"radius": 3}},
    {"pose": "dancing"},
])
def test_hoot_check_refuses_by_name(bad):
    with pytest.raises(ValueError):
        callouts.check([_hoot(**bad)])


def test_hoot_keys_are_refused_on_other_types():
    with pytest.raises(ValueError, match="hoot"):
        callouts.check([{"type": "badge", "text": "#1", "when": 1.0, "say": "hi"}])


def test_say_lines_are_at_most_four_words_and_two_lines_balanced():
    assert callouts.say_lines("A perfect CIRCLE") == ["A perfect CIRCLE"]
    assert callouts.say_lines("that is way too much") == ["that is way", "too much"]
    assert callouts.say_lines("one two three four five six seven eight") == [
        "one two three four", "five six seven eight"]


def test_check_hoot_set_needs_the_poses_the_renderer_picks():
    callouts.check_hoot_set(copy.deepcopy(SET))
    broken = copy.deepcopy(SET)
    del broken["poses"]["point_up"]
    with pytest.raises(ValueError, match="point_up"):
        callouts.check_hoot_set(broken)


# --- placing -------------------------------------------------------------------------------

def test_defaults_lower_left_above_the_caption_band_at_22_percent_width():
    [el] = _compile(_hoot())
    assert el["callout"] == "hoot" and el["pose"] == "neutral" and el["mirror"] is False
    hb = el["hoot_box"]
    assert hb[2] - hb[0] == pytest.approx(0.22, abs=1e-4)          # size: body width
    assert hb[3] <= BAND[1] - 0.01 + 1e-6                           # just above the band
    assert hb[0] >= callouts.HOOT_SAFE_X - 1e-6                     # inside the safe margin
    assert el["ease"] == "slide_in" and el["in_ms"] == 300 and el["enter_from"] == "left"
    assert el["sfx"] == "pop" and el["exit"] == {"t": 2.0}          # pop on arrival, next cut
    assert el["enter"]["t"] == pytest.approx(0.58)                  # word + 80 ms (<= 150)


def test_point_to_picks_the_pose_by_direction_and_mirrors_a_pose_facing_away():
    [right] = _compile(_hoot(anchor={"x": 0.2, "y": 0.4}, point_to={"x": 0.7, "y": 0.35}))
    assert right["pose"] == "point_right" and right["mirror"] is False
    [up] = _compile(_hoot(anchor={"x": 0.3, "y": 0.4}, point_to={"x": 0.35, "y": 0.1}))
    assert up["pose"] == "point_up"
    [flipped] = _compile(_hoot(pose="point_left", anchor={"x": 0.2, "y": 0.4},
                               point_to={"x": 0.7, "y": 0.35}))
    assert flipped["pose"] == "point_left" and flipped["mirror"] is True
    [left] = _compile(_hoot(point_to={"x": 0.3, "y": 0.3}))       # default anchor goes right
    assert left["at"][0] > 0.5 and left["pose"] in ("point_left", "point_up")


def test_hoot_never_covers_the_caption_band():
    with pytest.raises(ValueError, match="caption band"):
        _compile(_hoot(anchor={"x": 0.3, "y": 0.56}))
    with pytest.raises(ValueError, match="caption band"):    # his bubble counts too
        _compile(_hoot(anchor={"x": 0.17, "y": 0.47}, say="A perfect CIRCLE"))


def test_hoot_never_covers_the_point_he_points_to():
    with pytest.raises(ValueError, match="points to"):
        _compile(_hoot(anchor={"x": 0.2, "y": 0.4}, point_to={"x": 0.22, "y": 0.4}))
    with pytest.raises(ValueError, match="points to"):    # nor does the bubble
        _compile(_hoot(anchor={"x": 0.17, "y": 0.43}, say="look at this",
                       point_to={"x": 0.5, "y": 0.4}))


def test_the_bubble_sits_toward_the_centre_and_fits_its_text():
    [el] = _compile(_hoot(anchor={"x": 0.17, "y": 0.32}, say="A perfect CIRCLE"))
    b = el["bubble"]
    assert b["mirror"] is False and b["lines"] == ["A perfect CIRCLE"]
    assert b["text_box"][0] > el["hoot_box"][0]                    # to his right
    assert el["box"][2] <= 1 - callouts.HOOT_SAFE_X + 1e-6
    [mirrored] = _compile(_hoot(anchor={"x": 0.8, "y": 0.32}, say="wow"))
    assert mirrored["bubble"]["mirror"] is True
    assert mirrored["bubble"]["text_box"][2] < mirrored["hoot_box"][2]


def test_badge_text_picks_the_badge_pose_and_pops_with_the_measured_overshoot():
    [el] = _compile(_hoot(badge_text="12 G", anchor={"x": 0.2, "y": 0.35}))
    assert el["pose"] == "badge" and el["ease"] == "pop_badge" and el["in_ms"] == 300
    assert el["size"] == callouts.HOOT_BADGE_SIZE                  # bigger, so the number reads
    assert el["badge"]["text"] == "12 G" and el["badge"]["color"] == "#FFFFFF"
    [nope] = _compile(_hoot(pose="nope", badge_text="X", anchor={"x": 0.2, "y": 0.35}))
    assert nope["badge"]["color"] == "#E5202A"
    with pytest.raises(ValueError, match="nothing to write"):
        _compile(_hoot(pose="surprised", badge_text="X", anchor={"x": 0.2, "y": 0.35}))


def test_blur_bg_rides_the_element_for_the_grammar_layer_holding_as_long_as_hoot():
    [el] = _compile(_hoot(blur_bg=True))
    assert el["blur_bg"] == {"hold": pytest.approx(2.0 - 0.58)}
    import grammar
    [w] = grammar.blur_windows(None, {"elements": [el]}, 3.0)
    assert w.kind == "blur" and w.t0 == pytest.approx(0.58) and w.t1 == pytest.approx(2.0)


def test_hold_ms_and_scene():
    [el] = _compile(_hoot(hold=900))
    assert el["exit"]["t"] == pytest.approx(0.58 + 0.3 + 0.9)
    [el] = _compile(_hoot(hold="scene"))
    assert "exit" not in el


# --- HTML ----------------------------------------------------------------------------------

def test_html_draws_the_pose_the_bubble_text_and_the_badge():
    [el] = _compile(_hoot(anchor={"x": 0.17, "y": 0.32}, say="A perfect CIRCLE"))
    el2 = _compile(_hoot(badge_text="#1", anchor={"x": 0.2, "y": 0.35}))[0]
    html, css = callouts.callout_html(el, 3, image_uri=lambda p: f"uri:{p}")
    assert "uri:/h/neutral.png" in html and "uri:/h/bubble.png" in html
    assert "A perfect CIRCLE" in html and "Nunito" in css
    assert "kf-el3-in" in css and "kf-el3-bub" in css                # slide, then bubble pop
    assert 'id="el3"' in html and "callout-hoot" in html
    html2, _ = callouts.callout_html(el2, 4, image_uri=lambda p: f"uri:{p}")
    assert "#1" in html2 and "uri:/h/badge.png" in html2
    flipped = _compile(_hoot(pose="point_left", anchor={"x": 0.2, "y": 0.4},
                             point_to={"x": 0.7, "y": 0.35}))[0]
    assert "scaleX(-1)" in callouts.callout_html(flipped, 1, image_uri=str)[0]


def test_bbox_is_hoot_plus_bubble():
    [el] = _compile(_hoot(anchor={"x": 0.17, "y": 0.32}, say="A perfect CIRCLE"))
    assert callouts.bbox(el) == tuple(el["box"])
    assert illustrate.element_bbox(el) is not None


def test_illustrate_validates_a_compiled_hoot():
    [el] = _compile(_hoot())
    illustrate._validate_callout(el, "t")


# --- the set loader (make_short) -------------------------------------------------------------

def _png(path):
    raw = b"\x00" + b"\x00\x00\x00\x00"
    data = zlib.compress(raw)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", data) + chunk(b"IEND", b""))


def test_load_hoot_set_resolves_every_src_next_to_the_json(tmp_path, monkeypatch):
    d = tmp_path / "media" / "brand" / "hoot"
    d.mkdir(parents=True)
    data = copy.deepcopy(SET)
    for entry in [*data["poses"].values(), data["bubble"]]:
        name = pathlib.Path(entry["src"]).name
        _png(d / name)
        entry["src"] = name
    (d / "hoot.json").write_text(json.dumps(data))
    (tmp_path / "pyproject.toml").write_text("")
    spec = tmp_path / "video" / "x" / "scenes.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("")
    monkeypatch.delenv("PARKSHEET_HOOT_SET", raising=False)
    make_short._HOOT_CACHE.clear()
    loaded = make_short.load_hoot_set(spec)
    assert pathlib.Path(loaded["poses"]["neutral"]["src"]).is_absolute()
    scene = {"callouts": [{"type": "hoot", "when": 1.0, "say": "hi"}]}
    make_short.callout_preflight(scene, "scene 00", spec)
    assert scene["callouts"][0]["_hoot"] is loaded
    bad = {"callouts": [{"type": "hoot", "when": 1.0, "pose": "moonwalk"}]}
    with pytest.raises(SystemExit, match="moonwalk"):
        make_short.callout_preflight(bad, "scene 00", spec)
