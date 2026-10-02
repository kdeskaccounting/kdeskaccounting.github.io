"""`overlay:`, `scrim:` and `blur:` on a `kind: media` scene — illustration OVER imagery.

Stephen's ruling (2026-10-01): illustration is b-roll and graphics laid over video and
imagery, with the flat graphite ground sprinkled in only where there is no footage. So the
same `elements:` an `illustration` scene draws can ride a media scene as a transparent layer,
over a picture that may be darkened (`scrim:`) and softened (`blur:`) under them.

Same seams as tests/test_make_short_media.py and tests/test_make_short_illustration.py:
`run()` is the one place every ffmpeg invocation goes through, `R.screenshot` the one place
every Chrome invocation goes through, and `illustrate.render_scene_frames` the one place the
frame loop goes through — so the exact composite ffmpeg is asked to build can be asserted with
no browser and no encode.

What matters here and nowhere else:

  * **one encode.** The drawing is composited in the SAME ffmpeg call that encodes the
    footage — after the final scale (the frames are already delivered-size) and before the
    fades (a join dips the whole composite to black, not the footage out from under the art).
  * **the grade is on the FOOTAGE.** scrim and blur land before the credit plate, never after:
    the attribution must stay full-brightness and sharp.
  * **both lists of picture changes survive.** A beat boundary and an element entry are both
    cuts, and `cuts.json` is the only record either leaves.
  * **the inputs cannot collide.** The overlay sequence is the last input of the PART encode;
    the caption PNGs and the bed belong to the final pass, which is a different call.
"""
import json
import pathlib
import struct
import sys
import types
import zlib

import pytest

import captions
import illustrate
import make_short as M
import media


BRAND = {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"}
CREDIT = "Imagery: placeholder, generated locally"
DURATIONS = {"0": 4.0, "1": 3.0}
PART_SECONDS = 5.0

#: Scene 0's narration, as narrate.py writes it beside the WAV.
WORDS = [{"text": "Main", "start": 0.30, "end": 0.52},
         {"text": "Street", "start": 0.52, "end": 0.90},
         {"text": "smells", "start": 0.90, "end": 1.26},
         {"text": "like", "start": 1.26, "end": 1.44},
         {"text": "cookies.", "start": 1.44, "end": 2.10}]

ELEMENTS = [
    {"type": "emoji", "glyph": "\U0001F36A", "at": [0.5, 0.55], "size": 0.2,
     "enter": {"when": {"word": "cookies"}, "how": "pop"}, "sfx": "pop"},
    {"type": "arrow", "from": [0.3, 0.7], "to": [0.5, 0.6],
     "enter": {"when": {"word": "smells"}, "how": "draw"}, "sfx": "whoosh"},
]


def _spec():
    return {
        "slug": "overlay-demo",
        "brand": dict(BRAND),
        "short": {"hook": "Two media scenes", "scenes": [0, 1]},
        "scenes": [
            {"kind": "media", "src": "assets/still.png", "motion": "kenburns",
             "credit": CREDIT, "narration": "Main Street smells like cookies.",
             "scrim": 0.3, "overlay": {"elements": [dict(el) for el in ELEMENTS]}},
            {"kind": "media", "src": "assets/clip.mp4", "motion": "clip",
             "narration": "two"},
        ],
    }


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """main() over a media spec whose first scene carries an illustration overlay."""
    holder = types.SimpleNamespace(spec=_spec(), words=list(WORDS))
    monkeypatch.setitem(sys.modules, "yaml",
                        types.SimpleNamespace(safe_load=lambda fh: holder.spec))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "still.png").write_bytes(b"\0")
    (assets / "clip.mp4").write_bytes(b"\0")
    sounds = tmp_path / "media" / "audio"
    sounds.mkdir(parents=True)
    for name in ("bed.mp3", "pop.wav", "whoosh.wav"):
        (sounds / name).write_bytes(b"\0")
    build = tmp_path / "build" / "overlay-demo"
    audio = build / "audio"
    audio.mkdir(parents=True)
    (audio / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: PART_SECONDS)
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    cmds, shots, rendered = [], [], []
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: shots.append((a, k)))
    monkeypatch.setattr(M.R, "close_driver", lambda: None)
    monkeypatch.setattr(M, "run", cmds.append)

    def render_scene_frames(scene, scene_dir, fps=M.FPS, transparent=False):
        rendered.append((dict(scene), pathlib.Path(scene_dir), transparent))
        pathlib.Path(scene_dir).mkdir(parents=True, exist_ok=True)
        return []

    monkeypatch.setattr(M.illustrate, "render_scene_frames", render_scene_frames)
    holder.cmds, holder.shots, holder.rendered = cmds, shots, rendered
    holder.build, holder.work, holder.audio = build, build / "short", audio

    def go(*extra):
        captions.write_words(audio / "scene_00.wav", holder.words)
        monkeypatch.setattr(sys, "argv",
                            ["make_short.py", "--spec", str(spec_path), *extra])
        M.main()

    holder.go = go
    return holder


def _media_cmds(stub):
    """The per-scene encodes, i.e. everything before the end card and the concat."""
    return [c for c in stub.cmds
            if "-filter_complex" in c and not any("anullsrc" in str(t) for t in c)]


def _graph(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


def _inputs(cmd):
    cmd = [str(arg) for arg in cmd]
    return [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-i"]


# --- the grade on the footage ---------------------------------------------------------------

class TestFootageGrade:
    def test_no_scrim_and_no_blur_is_no_filter_at_all(self):
        """Which is every spec that predates this: the graph must not grow a no-op."""
        assert M.footage_grade() == ""
        assert M.footage_grade(0, 0) == ""

    def test_the_scrim_multiplies_every_rgb_channel_by_the_same_gain(self):
        """Which is what keeps the hue: see footage_grade's docstring for the measurement that
        ruled out drawbox, lutyuv and eq=brightness, all three of which move luma and leave
        chroma where it was."""
        assert M.footage_grade(scrim=0.3) == \
            "colorchannelmixer=rr=0.7000:gg=0.7000:bb=0.7000"
        for name in ("drawbox", "eq=", "lutyuv"):
            assert name not in M.footage_grade(scrim=0.3)

    @pytest.mark.parametrize("scrim", [0.1, 0.25, 0.5, M.SCRIM_MAX])
    def test_the_gain_is_one_minus_the_scrim_all_the_way_up(self, scrim):
        gain = f"{1 - scrim:.4f}"
        assert M.footage_grade(scrim=scrim) == \
            f"colorchannelmixer=rr={gain}:gg={gain}:bb={gain}"

    def test_the_blur_sigma_is_scaled_to_the_render_size(self):
        """The clause runs on the 1.2x footage, and the author writes delivered pixels."""
        assert M.footage_grade(blur=8) == f"gblur=sigma={8 * M.RW / M.OUT_W:.4f}"
        assert M.footage_grade(blur=8) == "gblur=sigma=9.6000"

    def test_both_are_one_comma_joined_clause(self):
        clause = M.footage_grade(scrim=0.25, blur=4)
        assert clause.startswith("colorchannelmixer=")
        assert clause.count(",") == 1
        assert ",gblur=sigma=" in clause


class TestMediaGrade:
    def test_a_scene_with_neither_key_grades_nothing(self):
        assert M.media_grade({"kind": "media"}) == (0.0, 0.0)

    def test_the_values_come_back_as_floats(self):
        assert M.media_grade({"scrim": 0.3, "blur": 6}) == (0.3, 6.0)

    @pytest.mark.parametrize("scene,word", [
        ({"scrim": 0.9}, "scrim"),
        ({"scrim": -0.1}, "scrim"),
        ({"scrim": 25}, "scrim"),
        ({"blur": 13}, "blur"),
        ({"blur": -1}, "blur"),
    ])
    def test_out_of_range_refuses_rather_than_clamping(self, scene, word):
        with pytest.raises(SystemExit) as excinfo:
            M.media_grade(scene, 2)
        assert word in str(excinfo.value)
        assert "scene 2" in str(excinfo.value)

    def test_a_non_number_is_refused_by_name(self):
        with pytest.raises(SystemExit, match="scrim"):
            M.media_grade({"scrim": "0.3"}, 0)

    def test_the_ceilings_are_the_ones_the_brief_set(self):
        assert (M.SCRIM_MAX, M.BLUR_MAX) == (0.8, 12.0)
        assert M.media_grade({"scrim": M.SCRIM_MAX, "blur": M.BLUR_MAX}) == (0.8, 12.0)


# --- the input numbering ---------------------------------------------------------------------

class TestMediaInputs:
    def test_one_source_no_layers_no_overlay(self):
        got = M.media_inputs((), ())
        assert (got.sources, got.audio, got.layers, got.overlay) == (1, 1, (), None)

    def test_the_layers_follow_the_wav(self):
        got = M.media_inputs((), ["a.png", "b.png"])
        assert got.audio == 1 and got.layers == (2, 3) and got.overlay is None

    def test_the_overlay_is_the_last_input_of_the_part(self):
        got = M.media_inputs((), ["a.png", "b.png"], overlay=True)
        assert got.overlay == 4
        assert got.overlay not in got.layers and got.overlay != got.audio

    def test_beats_push_everything_along(self):
        got = M.media_inputs([{"src": "a"}, {"src": "b"}, {"src": "c"}], ["p.png"],
                             overlay=True)
        assert (got.sources, got.audio, got.layers, got.overlay) == (3, 3, (4,), 5)

    def test_nothing_is_ever_numbered_twice(self):
        got = M.media_inputs([{"src": "a"}, {"src": "b"}], ["p.png", "q.png"], overlay=True)
        used = list(range(got.sources)) + [got.audio] + list(got.layers) + [got.overlay]
        assert sorted(used) == list(range(len(used)))


# --- the filter graph ------------------------------------------------------------------------

def test_the_graph_without_an_overlay_is_the_one_it_has_always_been(stub):
    """Scene 1 carries no overlay, no scrim and no blur: one scale/fade/format step, no [s0],
    no [o0], no drawbox and no gblur. Every spec that predates this renders that graph."""
    stub.go()
    graph = _graph(_media_cmds(stub)[1])
    assert "[s0]" not in graph and "[o0]" not in graph
    assert "colorchannelmixer" not in graph and "gblur" not in graph
    assert f"scale={M.OUT_W}:{M.OUT_H}:flags=lanczos:out_range=tv," in graph


def test_the_drawing_is_composited_after_the_scale_and_before_the_fades(stub):
    stub.go()
    steps = _graph(_media_cmds(stub)[0]).split(";")
    scaled = [s for s in steps if s.endswith("[s0]")]
    drawn = [s for s in steps if s.startswith("[s0]")]
    faded = [s for s in steps if s.endswith("[v]")]
    assert scaled == [f"[g0]scale={M.OUT_W}:{M.OUT_H}:flags=lanczos:out_range=tv[s0]"]
    assert drawn == ["[s0][3:v]overlay=x=0:y=0:format=auto:eof_action=repeat[o0]"]
    assert faded and faded[0].startswith("[m1]fade=t=in:st=0:d=0.3")
    assert faded[0].endswith("format=yuv420p[v]")


def test_the_drawings_eof_action_is_spelled_out(stub):
    """The sequence is round(dur * FPS) frames against a part cut at `-t dur`, so it can run
    out up to half a frame early. Without this the drawing would drop on the last frame."""
    stub.go()
    drawn = [s for s in _graph(_media_cmds(stub)[0]).split(";") if s.startswith("[s0]")]
    assert drawn and "eof_action=repeat" in drawn[0]


def test_the_plates_are_composited_ON_TOP_OF_the_drawing(stub):
    """A credit plate is an attribution: nothing may cover it, a sticker included. Our own
    plates are the half of that this can fix by ordering — the other half is Earth Studio,
    whose mark is in the footage, and that is what the preflight below is for."""
    stub.go()
    steps = _graph(_media_cmds(stub)[0]).split(";")
    drawn = [i for i, s in enumerate(steps) if "eof_action=repeat" in s]
    plated = [i for i, s in enumerate(steps) if "[2:v]overlay=" in s]
    assert drawn and plated and drawn[0] < plated[0]
    assert steps[plated[0]].startswith("[o0]"), "the plate has to read the DRAWN stage"


def test_a_scene_with_a_drawing_renders_its_plates_at_the_delivered_size(stub):
    """They are composited after the final scale now, so there is nothing left to scale them.
    Every box in media.py is a fraction of the frame, so the layout does not move."""
    stub.spec["scenes"][1]["credit"] = CREDIT      # so scene 1 has a plate to compare against
    stub.go()
    sizes = {pathlib.Path(a[1]).name: a[2:4] for a, _k in stub.shots}
    assert sizes["credit_0.png"] == (M.OUT_W, M.OUT_H)      # scene 0 carries the drawing
    assert sizes["credit_1.png"] == (M.RW, M.RH)            # scene 1 does not, and does not move


def test_the_scrim_lands_on_the_footage_before_the_credit_plate(stub):
    """The attribution must stay full-brightness: media.py's first rule. A scrim applied after
    the plates would be darkening the one thing the licence says has to stay readable."""
    stub.go()
    steps = _graph(_media_cmds(stub)[0]).split(";")
    graded = [i for i, s in enumerate(steps) if "colorchannelmixer=" in s]
    plated = [i for i, s in enumerate(steps) if "[2:v]overlay=" in s]
    assert graded and plated and graded[0] < plated[0]
    assert steps[graded[0]].startswith("[m0]") and steps[graded[0]].endswith("[g0]")


def test_the_overlay_sequence_is_the_last_input_and_is_read_at_thirty_fps(stub):
    stub.go()
    cmd = _media_cmds(stub)[0]
    inputs = _inputs(cmd)
    assert len(inputs) == 4                       # still, wav, credit plate, overlay frames
    assert inputs[-1].endswith(M.ILLUSTRATION_FRAME_GLOB)
    assert "scene_0_overlay" in inputs[-1]
    cmd = [str(arg) for arg in cmd]
    at = cmd.index(inputs[-1]) - 1                # the `-i` in front of it
    assert cmd[at - 2:at] == ["-r", str(M.FPS)], "an image2 sequence needs its rate pinned"


def test_the_part_is_still_one_encode(stub):
    """One ffmpeg call for the scene: the composite rides the encode that was happening."""
    stub.go()
    assert len(_media_cmds(stub)) == 2            # one per scene, and nothing extra


# --- the frames ------------------------------------------------------------------------------

def test_the_overlay_frames_are_drawn_transparent_in_their_own_directory(stub):
    stub.go()
    assert len(stub.rendered) == 1
    scene, path, transparent = stub.rendered[0]
    assert path.name == "scene_0_overlay"
    assert transparent is True, "an opaque layer would hide the footage completely"
    assert scene["kind"] == "illustration"


def test_the_overlay_is_as_long_as_the_part_it_rides(stub):
    stub.go()
    scene, _path, _t = stub.rendered[0]
    assert scene["seconds"] == pytest.approx(DURATIONS["0"] + M.SCENE_PAD)


def test_the_when_times_resolve_against_the_scenes_own_words(stub):
    """The overlay's clock is the scene's WAV, the same one the elements of an illustration
    scene are timed against — frame 0 of the layer is t=0 of the WAV, so nothing is offset."""
    stub.go()
    scene, _path, _t = stub.rendered[0]
    assert scene["elements"][0]["enter"] == {"t": 1.44, "how": "pop"}
    assert scene["elements"][1]["enter"] == {"t": 0.90, "how": "draw"}


def test_the_spec_scene_is_never_mutated_by_the_resolution(stub):
    stub.go()
    assert stub.spec["scenes"][0]["overlay"]["elements"][0]["enter"] == {
        "when": {"word": "cookies"}, "how": "pop"}


def test_a_word_the_scene_never_says_refuses_the_render_and_names_it(stub):
    stub.spec["scenes"][0]["overlay"]["elements"][0]["enter"] = {
        "when": {"word": "smellitzer"}, "how": "pop"}
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "smellitzer" in str(excinfo.value)
    assert "scene 00" in str(excinfo.value)


def test_a_scene_with_no_overlay_draws_no_frames_at_all(stub):
    del stub.spec["scenes"][0]["overlay"]
    stub.go()
    assert stub.rendered == []


# --- where the picture changes ---------------------------------------------------------------

class TestMergeSpans:
    def test_two_lists_with_no_cuts_stay_one_picture(self):
        assert M.merge_spans([3.0], [3.0], 3.0) == [3.0]

    def test_the_union_of_both_lists_of_cuts(self):
        assert M.merge_spans([1.0, 2.0], [1.5, 1.5], 3.0) == [1.0, 0.5, 1.5]

    def test_cuts_inside_one_frame_of_each_other_are_one_picture_change(self):
        """8 ms apart at 30 fps is the same frame, and a span shorter than a frame is a cut
        nobody can see."""
        assert M.merge_spans([1.0, 2.0], [1.004, 1.996], 3.0) == [1.0, 2.0]

    def test_the_spans_sum_to_the_part(self):
        spans = M.merge_spans([1.37, 1.28], [0.53, 2.12], 2.65)
        assert sum(spans) == pytest.approx(2.65, abs=1e-9)

    def test_a_cut_at_or_past_the_end_is_not_a_cut(self):
        assert M.merge_spans([3.0], [3.0, 0.0], 3.0) == [3.0]


def test_the_cut_row_carries_the_beats_and_the_elements_together(stub):
    """Three beats under a drawing that enters twice. The beats divide the 4.25 s part in
    thirds (cuts at 1.417 s and 2.833 s) and the elements enter at 0.90 s and 1.44 s, so the
    union is four picture changes, not three — and NOT five: the second beat boundary and the
    cookie's pop both land on frame 43, and one frame is one picture."""
    stub.spec["scenes"][0]["beats"] = [
        {"src": "assets/still.png", "seconds": 1.0, "credit": CREDIT},
        {"src": "assets/still.png", "seconds": 1.0, "credit": CREDIT},
        {"src": "assets/still.png", "seconds": 1.0, "credit": CREDIT},
    ]
    stub.go()
    cuts = json.loads((stub.work / "cuts.json").read_text())
    row = {r["scene"]: r for r in cuts["scenes"]}[0]
    dur = DURATIONS["0"] + M.SCENE_PAD
    assert sum(row["beats"]) == pytest.approx(dur, abs=5e-4)
    at, inside = 0.0, []
    for span in row["beats"][:-1]:
        at += span
        inside.append(round(at, 3))
    assert inside == [0.9, 1.433, 2.833]
    assert round(1.44 * M.FPS) == round(1.4167 * M.FPS) == 43


def test_a_scene_with_no_beats_still_gets_the_elements_cuts(stub):
    stub.go()
    cuts = json.loads((stub.work / "cuts.json").read_text())
    row = {r["scene"]: r for r in cuts["scenes"]}[0]
    assert row["beats"][:2] == [0.9, 0.533]
    assert sum(row["beats"]) == pytest.approx(DURATIONS["0"] + M.SCENE_PAD, abs=5e-4)


def test_a_media_scene_with_no_overlay_records_no_beats_as_it_always_did(stub):
    del stub.spec["scenes"][0]["overlay"]
    stub.go()
    cuts = json.loads((stub.work / "cuts.json").read_text())
    assert [row["beats"] for row in cuts["scenes"]] == [[], []]


# --- the element sounds ------------------------------------------------------------------

AUDIO = {"bed": {"src": "media/audio/bed.mp3", "lufs": -28.9},
         "sfx": {"events": {"pop": "media/audio/pop.wav",
                            "whoosh": "media/audio/whoosh.wav"}}}


def test_an_overlays_sfx_reach_the_mix_like_an_illustration_scenes(stub):
    stub.spec["audio"] = AUDIO
    stub.go()
    cuts = json.loads((stub.work / "cuts.json").read_text())
    # the arrow's whoosh lands where the line finishes DRAWING (0.90 + 0.50) and the cookie's
    # pop 0.04 s later, which the thinning takes
    assert {row["role"] for row in cuts["sfx"]} == {"whoosh"}
    assert cuts["sfx"][0]["at"] == pytest.approx(1.4)


def test_without_an_overlay_the_short_places_no_element_sounds(stub):
    del stub.spec["scenes"][0]["overlay"]
    stub.spec["audio"] = AUDIO
    stub.go()
    cuts = json.loads((stub.work / "cuts.json").read_text())
    assert cuts["sfx"] == []


# --- the preflight ---------------------------------------------------------------------------

def test_a_malformed_element_refuses_the_render_before_a_frame_is_drawn(stub):
    stub.spec["scenes"][0]["overlay"]["elements"] = [{"type": "emoji", "at": [0.5, 0.5]}]
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "glyph" in str(excinfo.value)
    assert "scene 0 (kind: media) overlay" in str(excinfo.value)
    assert stub.rendered == [], "the preflight has to run before the first frame"


def test_an_overlay_that_draws_nothing_is_refused(stub):
    stub.spec["scenes"][0]["overlay"] = {"data": {"heading": "oops"}}
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "template" in str(excinfo.value) and "elements" in str(excinfo.value)


def test_an_overlay_may_not_name_a_ground_or_a_length(stub):
    stub.spec["scenes"][0]["overlay"]["bg"] = "#F7F3EA"
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "overlay.bg" in str(excinfo.value)


def test_the_card_plate_overlay_still_renders_and_is_still_a_card(stub):
    """`overlay: {template, data}` predates this and must be untouched — and a mapping may
    carry both halves, because they are different layers at different points of the graph."""
    stub.spec["scenes"][0]["overlay"]["template"] = "ranked_list"
    stub.spec["scenes"][0]["overlay"]["data"] = {
        "heading": "H", "subheading": "S",
        "items": [{"rank": 1, "label": "L", "value": 1}], "footer": "F"}
    stub.go()
    shot = [a[1] for a, _k in stub.shots]
    assert stub.work / "overlay_0.png" in shot
    assert len(stub.rendered) == 1


# --- the Earth Studio attribution --------------------------------------------------------

#: An element parked in the bottom-right corner, i.e. inside media.watermark_box.
IN_THE_ZONE = {"type": "emoji", "glyph": "\U0001F36A", "at": [0.80, 0.94], "size": 0.2}
EARTH_CREDIT = "Imagery: Google Earth, Maxar Technologies"


def test_the_watermark_zone_is_where_media_says_it_is():
    """One source of truth: the guard asks media.watermark_box, which is derived from
    WATERMARK_W_FRAC/H_FRAC — the only numbers to edit if the mark ever moves."""
    assert media.watermark_box(M.OUT_W, M.OUT_H) == (486, 1690, 1080, 1920)


class TestWatermarkOffenders:
    def test_an_element_clear_of_the_corner_is_not_one(self):
        assert M.watermark_offenders({"elements": ELEMENTS}) == []

    def test_an_element_in_the_corner_is_named_by_index(self):
        found = M.watermark_offenders({"elements": [dict(ELEMENTS[0]), IN_THE_ZONE]})
        assert [index for index, _el, _box in found] == [1]

    def test_the_box_it_reports_is_the_elements_painted_extent(self):
        (_i, _el, box), = M.watermark_offenders({"elements": [IN_THE_ZONE]})
        left, top, right, bottom = illustrate.element_bbox(IN_THE_ZONE)
        assert box == (round(left * M.OUT_W), round(top * M.OUT_H),
                       round(right * M.OUT_W), round(bottom * M.OUT_H))

    def test_an_arrow_that_merely_POINTS_into_the_zone_is_one(self):
        """Its `to` is inside, so the line and its head are drawn there."""
        found = M.watermark_offenders({"elements": [
            {"type": "arrow", "from": [0.2, 0.3], "to": [0.9, 0.95]}]})
        assert [index for index, _el, _box in found] == [0]

    def test_a_walking_figure_is_bounded_by_its_whole_walk(self):
        found = M.watermark_offenders({"elements": [
            {"type": "figure", "pose": "walk", "from": [0.1, 0.94], "to": [0.9, 0.94],
             "t0": 0.0, "t1": 1.0}]})
        assert [index for index, _el, _box in found] == [0]


class TestIsEarthStudio:
    @pytest.mark.parametrize("scene", [
        {"credit": EARTH_CREDIT},
        {"credit": "imagery: google earth"},
        {"src": "media/earth/magic-kingdom.mp4"},
        {"beats": [{"src": "a.jpg"}, {"credit": "Google Earth, Maxar"}]},
        {"beats": [{"src": "media/earth/b.mp4"}]},
    ])
    def test_either_signal_is_enough(self, scene):
        assert media.is_earth_studio(scene) is True

    @pytest.mark.parametrize("scene", [
        {},
        {"credit": "Photo: Pexels"},
        {"src": "media/photos/earthenware-mug.jpg"},   # a substring, not a path segment
        {"beats": [{"src": "media/photos/a.jpg", "credit": "Photo: Pexels"}]},
    ])
    def test_anything_else_is_not(self, scene):
        assert media.is_earth_studio(scene) is False


def test_an_element_over_the_earth_studio_watermark_refuses_the_render(stub):
    """Earth Studio BURNS its attribution into the exported frames, so there is no layer to
    reorder — keeping the drawing out of the rectangle is the whole mechanism."""
    stub.spec["scenes"][0]["credit"] = EARTH_CREDIT
    stub.spec["scenes"][0]["overlay"]["elements"].append(dict(IN_THE_ZONE))
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    message = str(excinfo.value)
    assert "element 2 (emoji)" in message
    assert "Earth Studio" in message and "watermark zone" in message
    assert stub.rendered == [], "it has to refuse before a frame is drawn"


def test_the_same_element_is_allowed_over_a_source_that_is_not_earth_studio(stub):
    """The zone only means something where the mark is. A Pexels still has no burned-in
    attribution, and refusing a corner sticker there would be a rule nobody asked for."""
    stub.spec["scenes"][0]["overlay"]["elements"].append(dict(IN_THE_ZONE))
    stub.go()
    scene, _path, _t = stub.rendered[0]
    assert len(scene["elements"]) == 3


def test_an_earth_studio_scene_with_the_drawing_clear_of_the_corner_renders(stub):
    stub.spec["scenes"][0]["credit"] = EARTH_CREDIT
    stub.spec["scenes"][0]["src"] = "assets/still.png"
    stub.go()
    assert len(stub.rendered) == 1


def test_an_earth_studio_BEAT_arms_the_guard_for_the_whole_scene(stub):
    """Under `beats:` the scene's own src is never rendered — the beats are what reach the
    screen, so one Earth Studio beat is an Earth Studio scene."""
    stub.spec["scenes"][0]["beats"] = [
        {"src": "assets/still.png", "seconds": 1.0, "credit": CREDIT},
        {"src": "assets/still.png", "seconds": 1.0, "credit": EARTH_CREDIT},
    ]
    stub.spec["scenes"][0]["overlay"]["elements"].append(dict(IN_THE_ZONE))
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "Earth Studio" in str(excinfo.value)


def test_an_illustration_only_overlay_renders_no_card_plate(stub):
    stub.go()
    shot = [str(a[1]) for a, _k in stub.shots]
    assert not any("overlay_0.png" in name for name in shot)
    assert any("credit_0.png" in name for name in shot)


def test_an_illustration_overlay_does_not_push_the_caption_band_down(stub):
    """A card plate owns the top of the frame; drawn elements do not — keeping them out of the
    band is the author's job, exactly as it is on an illustration scene."""
    assert M.scene_card_top({"kind": "media", "overlay": {"elements": ELEMENTS}}) is None
    assert M.scene_card_top({"kind": "media", "overlay": {"template": "ranked_list"}}) is not None


@pytest.mark.parametrize("key,value", [("overlay", {"elements": ELEMENTS}),
                                       ("scrim", 0.3), ("blur", 4)])
def test_a_card_scene_may_not_carry_any_of_them(stub, key, value):
    stub.spec["scenes"].append({"kind": "card", "template": "countdown",
                                "data": {"heading": "H"}, "narration": "three", key: value})
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert key in str(excinfo.value)
    assert "Nothing would have read it" in str(excinfo.value)


def test_a_scrim_out_of_range_refuses_before_anything_renders(stub):
    stub.spec["scenes"][0]["scrim"] = 1.5
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    assert "scrim" in str(excinfo.value)
    assert stub.rendered == []


# --- what the render says --------------------------------------------------------------------

def test_the_render_says_what_it_drew_and_how_it_graded(stub, capsys):
    stub.go()
    out = capsys.readouterr().out
    assert "overlay 2 elements" in out
    assert "scrim 0.3" in out


# --- `image` elements in an overlay: resolved before the watermark guard measures them ------

def write_png(path, width=8, height=8):
    """A real RGBA PNG at `path`, written with the standard library.

    PIL is not installed in the bare `uv run --with pytest` environment this suite runs in, and
    a PNG is a signature plus three CRC'd chunks. A REAL header matters here and not only for
    the file's existence: `illustrate.element_bbox` measures a PNG sticker by this header's
    aspect ratio, and the watermark guard is the caller.
    """
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    rows = b"".join(b"\x00" + b"\xe6\x5a\x3c\xff" * width for _ in range(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return path


def test_an_overlay_images_src_reaches_the_renderer_absolute(stub, tmp_path):
    png = write_png(tmp_path / "assets" / "ai-machine.png")
    stub.spec["scenes"][0]["overlay"]["elements"].append(
        {"type": "image", "src": "assets/ai-machine.png", "at": [0.5, 0.45], "size": 0.3,
         "enter": {"when": {"word": "cookies"}, "how": "pop"}, "sfx": "pop"})
    stub.go()
    scene, _dir, _transparent = stub.rendered[0]
    el, = [e for e in scene["elements"] if e["type"] == "image"]
    assert pathlib.Path(el["src"]).is_absolute()
    assert pathlib.Path(el["src"]) == png.resolve()


def test_a_missing_overlay_image_refuses_the_render_naming_the_scene_and_element(stub):
    stub.spec["scenes"][0]["overlay"]["elements"].append(
        {"type": "image", "src": "assets/absent.png", "at": [0.5, 0.45]})
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    message = str(excinfo.value)
    assert "scene 0 (kind: media) overlay element 2 (type: image)" in message
    assert "absent.png" in message
    assert stub.rendered == [], "the preflight has to run before the first frame"


def test_a_tall_sticker_over_the_earth_studio_mark_is_caught_by_its_real_aspect(stub,
                                                                                tmp_path):
    """The guard measures a PNG by the FILE's aspect ratio, which is why the resolution has to
    happen before it runs: this sticker is twice as tall as it is wide, and only its real
    height reaches the watermark rectangle. Measured as a square it would have passed.
    """
    write_png(tmp_path / "assets" / "tall.png", width=40, height=80)
    tall = {"type": "image", "src": "assets/tall.png", "at": [0.80, 0.80], "size": 0.2}
    assert M.watermark_offenders({"elements": [dict(tall, src=str(
        (tmp_path / "assets" / "tall.png")))]}), "the resolved, tall box reaches the zone"
    assert M.watermark_offenders({"elements": [tall]}) == [], (
        "unresolved, the same element measures as a square and misses it")
    stub.spec["scenes"][0]["credit"] = EARTH_CREDIT
    stub.spec["scenes"][0]["overlay"]["elements"].append(tall)
    with pytest.raises(SystemExit) as excinfo:
        stub.go()
    message = str(excinfo.value)
    assert "element 2 (image)" in message
    assert "Earth Studio" in message and "watermark zone" in message
    assert stub.rendered == []
