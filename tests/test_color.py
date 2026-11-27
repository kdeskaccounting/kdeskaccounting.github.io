"""make_short `color:`: per-scene / per-beat colour correction for footage that does not match its
neighbours (Stephen, 2026-11-27, cruise-yellow-lifeboats: "The vibrance of the first clip is dull. And
the coloring doesn't match the other clips."). Pure functions only: the strings handed to ffmpeg."""
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))
import make_short as ms  # noqa: E402


def test_absent_or_neutral_color_is_no_filter():
    assert ms.parse_color(None, "x") == {}
    assert ms.parse_color({"saturation": 1.0, "warmth": 0}, "x") == {}
    assert ms.color_filter({}) == ""


def test_eq_keys_become_one_eq_filter_in_a_fixed_order():
    got = ms.color_filter(ms.parse_color({"saturation": 1.4, "contrast": 1.05, "gamma": 1.1}, "x"))
    assert got == "eq=contrast=1.050:saturation=1.400:gamma=1.100"


def test_warmth_and_tint_are_colorbalance_shifts():
    got = ms.color_filter(ms.parse_color({"warmth": 0.5, "tint": 0.5}, "x"))
    assert got.startswith("colorbalance=")
    shifts = dict(kv.split("=") for kv in got.removeprefix("colorbalance=").split(":"))
    assert float(shifts["rm"]) > 0 > float(shifts["bm"])       # warmer: red up, blue down
    assert float(shifts["gm"]) < 0                             # +tint takes green out
    assert abs(float(shifts["rm"])) == pytest.approx(0.06)     # 0.5 x the midtone weight 0.12


def test_both_halves_chain_eq_then_colorbalance():
    got = ms.color_filter({"saturation": 1.3, "warmth": 0.2})
    assert got.startswith("eq=saturation=1.300,colorbalance=")


@pytest.mark.parametrize("value, match", [
    ({"saturation": 140}, "outside"),
    ({"vibrance": 1.2}, "not a colour setting"),
    ({"saturation": "1.3"}, "must be a number"),
    ({"saturation": True}, "must be a number"),
    ([1.3], "must be a mapping"),
])
def test_bad_color_refuses_the_render(value, match):
    with pytest.raises(SystemExit, match=match):
        ms.parse_color(value, "scene 0 (kind: media)")


def test_a_beat_carries_its_color_and_only_its_chain_gets_the_filter(tmp_path, monkeypatch):
    scene = {"beats": [{"src": "a.mp4", "seconds": 2.0, "color": {"saturation": 1.5}},
                       {"src": "b.mp4", "seconds": 2.0}]}
    beats = ms.scene_beats(scene)
    assert beats[0]["color"] == {"saturation": 1.5} and beats[1]["color"] == {}
    monkeypatch.setattr(ms, "probe_size", lambda src: (1080, 1920))
    monkeypatch.setattr(ms.media, "media_kind", lambda src: "video")
    for b in beats:
        b["motion"] = "clip"
    steps = ms.beat_steps(beats, 4.0)
    b0 = next(s for s in steps if s.endswith("[b0]"))
    b1 = next(s for s in steps if s.endswith("[b1]"))
    assert "eq=saturation=1.500" in b0
    assert "eq=" not in b1


def test_a_bad_beat_color_is_refused_with_its_index():
    with pytest.raises(SystemExit, match=r"beats\[1\]"):
        ms.scene_beats({"beats": [{"src": "a.mp4", "seconds": 2.0},
                                  {"src": "b.mp4", "seconds": 2.0, "color": {"tint": 3}}]})


def test_media_color_reads_the_scene_key():
    assert ms.media_color({"color": {"warmth": -0.2}}, 3) == {"warmth": -0.2}
    assert ms.media_color({}, 3) == {}
