"""make_short.py's `kind: illustration` scene kind, with ffmpeg and Chrome stubbed.

Same seams as tests/test_make_short_captions.py: `run()` is the one place every ffmpeg
invocation goes through, `R.screenshot` the one place every Chrome invocation goes through,
and `illustrate.render_scene_frames` the one place the frame loop goes through — so a test
can assert the exact composite ffmpeg is asked to build without a browser or an encode.

What matters here and nowhere else:

  * **the picture is the only thing illustrate.py owns.** Narration, the scene pad, word-timed
    captions, the join, the audio mix and cuts.json all come from make_short, which is the
    whole reason `illustration` is a scene kind rather than a second pipeline.
  * **frames are already the delivered size.** They come off illustrate at 1080x1920, so the
    chain carries no zoompan and no scale — and the input rate must be pinned at 30 fps, or an
    image2 sequence is read at 25 and the scene runs 20% long against its own WAV.
  * **the elements' entry times are the cuts.** An illustration scene is one continuous render
    and several pictures; `cuts.json` is the only record of that (nothing can detect it
    afterwards), so `illustration_spans` is what feeds it.
  * **captions are NOT skipped.** An illustration scene is captioned like a media scene; the
    spec keeps its elements out of the band.
"""
import json
import pathlib
import sys
import types

import pytest

import captions
import illustrate
import make_short as M


BRAND = {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"}

#: The narration of scene 0, as narrate.py writes it beside the WAV.
WORDS = {
    0: [{"text": "Main", "start": 0.30, "end": 0.52},
        {"text": "Street", "start": 0.52, "end": 0.90},
        {"text": "smells", "start": 0.90, "end": 1.26},
        {"text": "like", "start": 1.26, "end": 1.44},
        {"text": "cookies.", "start": 1.44, "end": 2.10}],
    1: [{"text": "The", "start": 0.30, "end": 0.44},
        {"text": "reason", "start": 0.44, "end": 0.92},
        {"text": "has", "start": 0.92, "end": 1.10},
        {"text": "a", "start": 1.10, "end": 1.18},
        {"text": "patent.", "start": 1.18, "end": 1.80}],
}
DURATIONS = {"0": 2.4, "1": 2.0}
PART_SECONDS = 3.0


def _elements():
    return [
        {"type": "label", "text": "MAIN STREET", "at": [0.5, 0.33], "size": 0.05,
         "enter": {"t": 0.0, "how": "slide-left"}},
        {"type": "emoji", "glyph": "\U0001F36A", "at": [0.5, 0.55], "size": 0.2,
         "enter": {"when": {"word": "cookies"}, "how": "pop"}, "sfx": "pop"},
        {"type": "squiggle", "from": [0.5, 0.5], "to": [0.5, 0.36],
         "enter": {"when": {"word": "smells"}, "how": "draw"}, "sfx": "whoosh"},
    ]


def _spec(captions_block=None, scene_over=None):
    scene = {"kind": "illustration", "narration": "Main Street smells like cookies.",
             "bg": "#F7F3EA", "elements": _elements()}
    scene.update(scene_over or {})
    spec = {
        "slug": "illus-demo",
        "brand": BRAND,
        "short": {"hook": "Two scenes", "scenes": [0, 1]},
        "scenes": [
            scene,
            {"kind": "illustration", "narration": "The reason has a patent.", "bg": "#F7F3EA",
             "elements": [
                 {"type": "tag", "text": "PATENT", "at": [0.5, 0.6],
                  "enter": {"when": {"word": "patent"}, "how": "drop"}, "sfx": "hit"}]},
        ],
    }
    if captions_block is not None:
        spec["captions"] = captions_block
    return spec


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """main() over an all-illustration spec with ffmpeg, ffprobe and the frame loop stubbed."""
    holder = types.SimpleNamespace(spec=_spec(), words=dict(WORDS))
    monkeypatch.setitem(sys.modules, "yaml",
                        types.SimpleNamespace(safe_load=lambda fh: holder.spec))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")
    build = tmp_path / "build" / "illus-demo"
    audio = build / "audio"
    audio.mkdir(parents=True)
    (audio / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: PART_SECONDS)
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    cmds, rendered, closed = [], [], []
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: None)
    monkeypatch.setattr(M.R, "render_card_scene", lambda *a, **k: None)
    monkeypatch.setattr(M.R, "close_driver", lambda: closed.append(True))
    monkeypatch.setattr(M, "run", cmds.append)

    def render_scene_frames(scene, scene_dir, fps=M.FPS):
        rendered.append((dict(scene), pathlib.Path(scene_dir)))
        pathlib.Path(scene_dir).mkdir(parents=True, exist_ok=True)
        return []

    monkeypatch.setattr(M.illustrate, "render_scene_frames", render_scene_frames)
    holder.cmds, holder.rendered, holder.closed = cmds, rendered, closed
    holder.build, holder.work, holder.audio = build, build / "short", audio

    def go(*extra):
        for idx, words in holder.words.items():
            captions.write_words(audio / f"scene_{idx:02d}.wav", words)
        monkeypatch.setattr(sys, "argv",
                            ["make_short.py", "--spec", str(spec_path), *extra])
        M.main()

    holder.go = go
    return holder


def _scene_cmds(stub):
    return [c for c in stub.cmds if any("frame_%04d.png" in str(arg) for arg in c)]


def _graph(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


# --- the frames are already the delivered size ---------------------------------------------

def test_illustrate_draws_at_exactly_the_size_the_short_is_delivered_at():
    """The reason the branch carries no scale/zoompan at all. If these ever diverge, the
    illustration part would not concat with the others."""
    assert (illustrate.W, illustrate.H) == (M.OUT_W, M.OUT_H)


def test_the_frames_are_read_at_thirty_fps_and_never_resized(stub):
    stub.go()
    cmd = _scene_cmds(stub)[0]
    at = cmd.index("-i")
    assert cmd[at - 2:at] == ["-r", str(M.FPS)], "an image2 input needs its rate pinned"
    graph = _graph(cmd)
    assert "zoompan" not in graph and "scale=" not in graph


def test_the_audio_chain_is_encode_scenes_own_clause_for_clause(stub):
    stub.go()
    graph = _graph(_scene_cmds(stub)[0])
    assert ("[1:a]apad=pad_dur=2,afade=t=in:d=0.05,"
            "aformat=sample_rates=48000:channel_layouts=stereo[a]") in graph


def test_the_part_is_encoded_the_way_every_other_part_is(stub):
    """`-c:v copy` joins these parts, so the flags have to match encode_scene exactly."""
    stub.go()
    cmd = [str(arg) for arg in _scene_cmds(stub)[0]]
    for flag, value in (("-c:v", "libx264"), ("-preset", "medium"), ("-crf", "26"),
                        ("-r", str(M.FPS)), ("-color_range", "tv"), ("-bsf:v", M.RANGE_BSF),
                        ("-c:a", "aac"), ("-b:a", "128k"), ("-t", "2.650")):
        at = [i for i, arg in enumerate(cmd) if arg == flag]
        assert at, f"{flag} is missing from the illustration encode"
        assert any(cmd[i + 1] == value for i in at), f"{flag} is not {value}"


def test_the_default_join_fades_the_part_at_both_ends(stub):
    stub.go()
    graph = _graph(_scene_cmds(stub)[0])
    assert "fade=t=in:st=0:d=0.3" in graph
    assert "fade=t=out:st=" in graph


def test_join_cut_drops_both_fades(stub):
    stub.spec["transitions"] = {"join": "cut"}
    stub.go()
    graph = _graph(_scene_cmds(stub)[0])
    assert "fade=t=in:st=0" not in graph and "fade=t=out" not in graph
    assert graph.startswith("[0:v]format=yuv420p[v]")


def test_the_scene_is_cut_to_its_narration_plus_the_pad(stub):
    stub.go()
    cmd = _scene_cmds(stub)[0]
    assert cmd[cmd.index("-t") + 1] == f"{DURATIONS['0'] + M.SCENE_PAD:.3f}"


def test_the_frames_go_in_their_own_directory_per_scene(stub):
    stub.go()
    assert [path.name for _scene, path in stub.rendered] == ["scene_0_frames",
                                                             "scene_1_frames"]


def test_the_scene_handed_to_illustrate_carries_the_real_duration(stub):
    stub.go()
    scene, _path = stub.rendered[0]
    assert scene["seconds"] == pytest.approx(DURATIONS["0"] + M.SCENE_PAD)


def test_the_when_times_are_resolved_against_the_scenes_own_words(stub):
    stub.go()
    scene, _path = stub.rendered[0]
    assert scene["elements"][1]["enter"] == {"t": 1.44, "how": "pop"}
    assert scene["elements"][2]["enter"] == {"t": 0.90, "how": "draw"}


def test_the_spec_scene_itself_is_never_mutated_by_the_resolution(stub):
    stub.go()
    assert stub.spec["scenes"][0]["elements"][1]["enter"] == {
        "when": {"word": "cookies"}, "how": "pop"}


def test_chrome_is_released_once_the_pictures_are_drawn(stub):
    stub.go()
    assert stub.closed == [True]


def test_a_word_no_scene_says_refuses_the_render_and_names_it(stub):
    stub.spec["scenes"][0]["elements"][1]["enter"] = {"when": {"word": "smellitzer"},
                                                      "how": "pop"}
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "smellitzer" in str(excinfo.value)
    assert "scene 00" in str(excinfo.value)


# --- the preflight -------------------------------------------------------------------------

def test_a_malformed_element_refuses_the_render_before_anything_is_drawn(stub):
    stub.spec["scenes"][1]["elements"] = [{"type": "emoji", "at": [0.5, 0.5]}]
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "glyph" in str(excinfo.value)
    assert "scene 1" in str(excinfo.value)
    assert stub.rendered == [], "the preflight has to run before the first frame"


def test_an_unknown_element_type_is_refused_at_preflight(stub):
    stub.spec["scenes"][0]["elements"] = [{"type": "sticker", "at": [0.5, 0.5]}]
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "sticker" in str(excinfo.value)


def test_a_bad_word_reference_is_refused_at_preflight_not_at_render(stub):
    stub.spec["scenes"][0]["elements"][1]["enter"] = {"when": {"word": "x", "nth": 0},
                                                      "how": "pop"}
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "nth" in str(excinfo.value)
    assert stub.rendered == []


@pytest.mark.parametrize("key", ["beats", "steps"])
def test_beats_or_steps_on_an_illustration_scene_is_refused(stub, key):
    stub.spec["scenes"][0][key] = [{"src": "a.png", "seconds": 1.0},
                                   {"src": "b.png", "seconds": 1.0}]
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "illustration" in str(excinfo.value)
    assert "Nothing would have read it" in str(excinfo.value)


def test_a_seconds_on_an_illustration_scene_is_announced_not_honoured(stub, capsys):
    stub.spec["scenes"][0]["seconds"] = 9.0
    stub.go()
    assert "ignored" in capsys.readouterr().out
    scene, _path = stub.rendered[0]
    assert scene["seconds"] == pytest.approx(DURATIONS["0"] + M.SCENE_PAD)


def test_the_render_says_what_it_drew(stub, capsys):
    stub.go()
    out = capsys.readouterr().out
    assert "scene 00: illustration 3 elements 2.6s -> scene_0.mp4" in out
    assert "scene 01: illustration 1 elements 2.2s -> scene_1.mp4" in out


# --- where the picture changes -------------------------------------------------------------

class TestIllustrationSpans:
    def test_one_element_on_from_frame_zero_is_one_picture(self):
        scene = {"elements": [{"type": "label", "text": "A", "at": [0.5, 0.5]}]}
        assert M.illustration_spans(scene, 3.0) == [3.0]

    def test_each_distinct_entry_time_ends_a_span(self):
        scene = {"elements": [
            {"type": "label", "text": "A", "at": [0.5, 0.5], "enter": {"t": 0.0, "how": "fade"}},
            {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "enter": {"t": 1.0, "how": "pop"}},
            {"type": "emoji", "glyph": "y", "at": [0.4, 0.5], "enter": {"t": 2.0, "how": "pop"}},
        ]}
        assert M.illustration_spans(scene, 3.0) == [1.0, 1.0, 1.0]

    def test_the_spans_sum_to_the_scenes_own_duration(self):
        scene = {"elements": [
            {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "enter": {"t": 0.37, "how": "pop"}},
            {"type": "emoji", "glyph": "y", "at": [0.4, 0.5], "enter": {"t": 1.93, "how": "pop"}},
        ]}
        spans = M.illustration_spans(scene, 2.65)
        assert sum(spans) == pytest.approx(2.65, abs=1e-9)

    def test_two_elements_on_the_same_frame_are_one_picture_change(self):
        scene = {"elements": [
            {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "enter": {"t": 1.0, "how": "pop"}},
            {"type": "emoji", "glyph": "y", "at": [0.4, 0.5], "enter": {"t": 1.004, "how": "pop"}},
        ]}
        assert M.illustration_spans(scene, 3.0) == [1.0, 2.0]

    def test_a_time_at_or_past_the_end_is_not_a_cut(self):
        scene = {"elements": [
            {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "enter": {"t": 3.0, "how": "pop"}},
            {"type": "emoji", "glyph": "y", "at": [0.4, 0.5], "enter": {"t": 4.0, "how": "pop"}},
        ]}
        assert M.illustration_spans(scene, 3.0) == [3.0]

    def test_a_walking_figure_enters_at_its_t0(self):
        scene = {"elements": [
            {"type": "figure", "pose": "walk", "from": [0.1, 0.8], "to": [0.6, 0.8],
             "t0": 0.5, "t1": 2.0}]}
        assert M.illustration_spans(scene, 3.0) == [0.5, 2.5]

    def test_a_calendar_is_one_picture_per_cell(self):
        scene = {"elements": [
            {"type": "calendar", "at": [0.5, 0.5], "cols": 3, "step": 0.5, "t0": 0.5,
             "cells": [{"label": "Mon", "value": "$1", "tone": "low"},
                       {"label": "Tue", "value": "$2", "tone": "mid"},
                       {"label": "Wed", "value": "$3", "tone": "high"}]}]}
        assert M.illustration_spans(scene, 3.0) == [0.5, 0.5, 0.5, 1.5]

    def test_the_times_are_frame_exact(self):
        """A cut lands on a frame boundary, because a picture cannot change between frames."""
        scene = {"elements": [
            {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "enter": {"t": 0.51, "how": "pop"}}]}
        spans = M.illustration_spans(scene, 2.0)
        assert spans[0] == pytest.approx(round(0.51 * M.FPS) / M.FPS, abs=1e-6)


def test_the_cut_rows_carry_the_spans_the_elements_made(stub):
    stub.go()
    cuts = json.loads((stub.work / "cuts.json").read_text())
    rows = {row["scene"]: row for row in cuts["scenes"]}
    # scene 0: entries at 0.00 (label), 0.90 (squiggle) and 1.44 (cookies), over the 2.65 s
    # this part was ENCODED with (durations.json + the pad) -- the spans sum to that, exactly as
    # `beat_spans` sums to the `dur` a media part was encoded with, not to what it probed to.
    assert rows[0]["beats"] == [0.9, 0.533, 1.217]
    assert sum(rows[0]["beats"]) == pytest.approx(DURATIONS["0"] + M.SCENE_PAD, abs=1e-9)
    # every picture change after frame 0, on the finished timeline: two inside scene 0, the
    # part boundary at 3.0 (what the parts PROBED to), and the tag dropping inside scene 1
    assert cuts["cuts"] == [0.9, 1.433, 3.0, 4.167]


# --- captions ------------------------------------------------------------------------------

def test_an_illustration_scene_is_captioned_like_a_media_scene(stub):
    stub.spec = _spec({"enabled": True, "accent": "#ffe234", "position": "top"})
    stub.go()
    plan = json.loads((stub.work / "captions.json").read_text())
    assert len(plan["windows"]) == sum(len(words) for words in WORDS.values())
    # the UNCONSTRAINED top band: an illustration scene pushes it nowhere, the way a media
    # scene with no card overlay does not (a full-frame card would).
    assert plan["band"] == list(captions.caption_box(M.OUT_W, M.OUT_H))


def test_the_caption_band_is_not_pushed_down_by_an_illustration_scene(stub):
    assert M.scene_card_top({"kind": "illustration", "elements": []}) is None
