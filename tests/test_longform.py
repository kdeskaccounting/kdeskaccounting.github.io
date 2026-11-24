"""scripts/video/longform.py: the 16:9 long-form keys assemble.py's opt-in `landscape:` path reads
(Park Detective episode 1, 2026-11-23) -- options, beats + in-points, chapter cards, sticker
callouts, Earth Studio zones, the looped music bed, chapters.json.

Stdlib + pytest for the logic; the PNG drawing skips without PIL and the renders skip without
ffmpeg (the render venv has both; run with `--with pillow --with numpy` to include them)."""
import json
import math
import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))
import assemble  # noqa: E402
import longform  # noqa: E402
import make_short  # noqa: E402
import media  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is absent")


def _pil():
    return pytest.importorskip("PIL.Image")


def _xy(expr: str, t: float) -> float:
    """Evaluate one of our ffmpeg overlay expressions in Python (same syntax for these)."""
    return eval(expr, {"__builtins__": {}}, {"t": t, "pow": pow, "min": min, "max": max})


def _overlay_xy(filt: str):
    """(x_expr, y_expr, t0, t1) out of an `overlay=x='..':y='..':...:enable='between(t,a,b)'`."""
    x = filt.split("x='", 1)[1].split("'", 1)[0]
    rest = filt.split(":y=", 1)[1]
    y = rest[1:].split("'", 1)[0] if rest.startswith("'") else rest.split(":", 1)[0]
    a, b = filt.split("between(t,", 1)[1].split(")", 1)[0].split(",")
    return x, y, float(a), float(b)


# --- options ---------------------------------------------------------------------------------

def test_options_are_opt_in_and_default():
    assert longform.options({}) is None
    assert longform.options({"landscape": "yes"}) is None
    o = longform.options({"landscape": {}})
    assert (o.join, o.scene_pad, o.chapter_card_s, o.callout_s, o.max_picture_s,
            o.bed_crossfade, o.bed_loop_in) == ("fade", 0.7, 2.5, 3.0, 12.0, 3.0, 0.0)
    assert o.captions_on and o.caption_position == "lower-third"
    spike = longform.options({"landscape": {"captions": {"style": "sentence",
                                                         "position": "lower-third"},
                                            "join": "cut", "scene_pad": 0.35}})
    assert spike.join == "cut" and spike.scene_pad == 0.35
    assert not longform.options({"landscape": {"captions": {"enabled": False}}}).captions_on


@pytest.mark.parametrize("block, says", [
    ({"chapter_secs": 2}, "unknown landscape key"),
    ({"join": "xfade"}, "landscape.join"),
    ({"captions": {"position": "middle"}}, "position"),
    ({"captions": {"style": "word"}}, "only `sentence`"),
    ({"captions": {"colour": "red"}}, "unknown landscape.captions"),
    ({"scene_pad": 0}, "scene_pad"),
    ({"max_picture_s": 1}, "max_picture_s"),
    ({"bed_crossfade": "3s"}, "bed_crossfade"),
])
def test_options_refuse_what_they_cannot_honour(block, says):
    with pytest.raises(SystemExit, match=says):
        longform.options({"landscape": block})


# --- scenes, beats ---------------------------------------------------------------------------

def test_normalise_gives_a_beats_scene_its_first_beats_src_and_credit():
    spec = {"scenes": [
        {"kind": "media", "beats": [{"src": "a.jpg", "seconds": 2, "credit": "Photo: A"},
                                    {"src": "b.mp4", "seconds": 2}]},
        {"kind": "media", "src": "keep.mp4", "beats": [{"src": "x.mp4", "seconds": 1}]},
        {"kind": "card"}]}
    longform.normalise_spec(spec)
    assert spec["scenes"][0]["src"] == "a.jpg" and spec["scenes"][0]["credit"] == "Photo: A"
    assert spec["scenes"][1]["src"] == "keep.mp4"
    assert "src" not in spec["scenes"][2]


def test_shorts_only_render_keys_are_refused_on_a_landscape_media_scene():
    for key in ("overlay", "scrim", "fx", "elements", "tail_s"):
        with pytest.raises(SystemExit, match=key):
            longform.check_scene_keys({"kind": "media", "src": "a.mp4", key: 1}, "scene 3")
    with pytest.raises(SystemExit, match="chapter"):
        longform.check_scene_keys({"kind": "card", "chapter": {"title": "x"}}, "scene 1")
    longform.check_scene_keys({"kind": "media", "src": "a.mp4", "chapter": {"title": "x"}}, "s")


def _beats(*seconds, **extra):
    return [{"src": f"b{i}.mp4", "seconds": s, **extra} for i, s in enumerate(seconds)]


def test_scene_beats_normalise_and_fall_back_to_the_scenes_fill_and_focus():
    scene = {"fill": "crop", "focus": [0.4, 0.3],
             "beats": [{"src": "a.mp4", "seconds": 4, "in": 2.5},
                       {"src": "b.jpg", "seconds": 5, "fill": "blur", "focus": [0.9, 0.1],
                        "motion": "hold", "crop": {"zoom": 1.5}, "credit": "Photo: B"}]}
    a, b = longform.scene_beats(scene)
    assert (a["in"], a["fill"], a["focus"], a["motion"]) == (2.5, "crop", (0.4, 0.3), "")
    assert (b["in"], b["fill"], b["focus"], b["motion"]) == (0.0, "blur", (0.9, 0.1), "hold")
    assert b["crop"] == {"zoom": 1.5} and b["credit"] == "Photo: B"
    assert longform.scene_beats({}) == []


@pytest.mark.parametrize("beats, says", [
    (_beats(3), "one entry"),
    ("a.mp4", "must be a list"),
    ([{"src": "a.mp4", "seconds": 2, "start": 1}, {"src": "b.mp4", "seconds": 2}], "`in:`"),
    ([{"src": "a.mp4", "seconds": 2, "zoom": 2}, {"src": "b.mp4", "seconds": 2}], "unknown key"),
    (_beats(3, 13), "seconds"),
    (_beats(3, 0), "seconds"),
    (_beats(3, 3, **{"in": -1}), "`in`"),
    (_beats(3, 3, fill="stretch"), "fill"),
    (_beats(3, 3, motion="punch"), "portrait-only"),
    ([{"seconds": 2}, {"src": "b.mp4", "seconds": 2}], "no `src`"),
])
def test_scene_beats_refuse_a_bad_list_by_name(beats, says):
    with pytest.raises(SystemExit, match=says):
        longform.scene_beats({"beats": beats}, "scene 4")


def test_beat_spans_rescale_like_make_short_and_sum_exactly():
    beats = _beats(2.0, 3.0, 1.5)
    for dur in (6.5, 7.123, 5.0):
        spans = longform.beat_spans(beats, dur)
        assert spans == make_short.beat_spans(beats, dur)
        assert round(sum(spans), 3) == round(dur, 3)
    # the long-form backstop is not the Shorts' 6 s: a 9 s picture is fine here
    assert longform.beat_spans(_beats(9, 9), 18.0) == [9.0, 9.0]
    with pytest.raises(SystemExit, match="max_picture_s"):
        longform.beat_spans(_beats(5, 5), 26.0)
    with pytest.raises(SystemExit):
        make_short.beat_spans(_beats(9, 9), 18.0)


def test_cut_times_are_the_beat_boundaries():
    assert longform.cut_times([2.0, 3.5, 1.0]) == [2.0, 5.5]
    assert longform.cut_times([4.0]) == []


# --- Earth Studio zones -------------------------------------------------------------------------

def test_earth_zone_of_a_pillarboxed_portrait_export_sits_inside_the_displayed_picture():
    zones = longform.earth_zones((1080, 1920))
    full, shown = zones
    assert full == media.watermark_box(1920, 1080)
    x0, y0, dw, dh = longform.fit_rect(1080, 1920)
    assert shown[0] == round(x0 + 0.45 * dw) and shown[2] == round(x0 + dw)
    assert longform.earth_zones((1920, 1080)) == [full]
    assert longform.earth_zones(None) == [full]


@pytest.mark.parametrize("size", [(1080, 1920), (1920, 1080), (1440, 1080), (3840, 1634),
                                  (1080, 1080), None])
def test_no_earth_zone_ever_reaches_left_of_045_of_the_frame(size):
    for zone in longform.earth_zones(size):
        assert zone[0] >= round(0.45 * longform.W) - 1


@pytest.mark.parametrize("size", [(1080, 1920), (1920, 1080), (3840, 1634), None])
def test_a_lower_left_chapter_card_at_full_width_clears_every_earth_zone(size):
    place = longform.chapter_placement(earth_under=True, captions_top=True)
    assert place["corner"] == "bottom-left"
    box = (place["x"], place["y_bottom"] - 300, place["x"] + place["max_w"], place["y_bottom"])
    assert not longform.overlaps_any(box, longform.earth_zones(size))


def test_chapter_card_goes_where_the_captions_are_not():
    assert longform.chapter_placement(False, False)["corner"] == "top-left"
    assert longform.chapter_placement(False, True)["corner"] == "bottom-left"
    assert longform.chapter_placement(True, False)["corner"] == "bottom-left"


# --- chapters -----------------------------------------------------------------------------------

def test_chapter_of_reads_number_title_and_kicker():
    assert longform.chapter_of({}) is None
    assert longform.chapter_of({"chapter": {"number": 3, "title": " Balloons "}}) == {
        "number": 3, "title": "Balloons", "kicker": "NUMBER 3"}
    assert longform.chapter_of({"chapter": {"title": "Intro"}})["kicker"] == ""
    assert longform.chapter_of({"chapter": {"number": 9, "title": "Drones",
                                            "kicker": "LAST ONE"}})["kicker"] == "LAST ONE"


@pytest.mark.parametrize("chapter, says", [
    ("Number 3", "mapping"), ({"number": 3}, "title"), ({"title": "x", "number": "3"}, "whole"),
    ({"title": "x", "subtitle": "y"}, "unknown chapter key"), ({"title": "x", "kicker": 3}, "kicker"),
])
def test_chapter_of_refuses_a_bad_block(chapter, says):
    with pytest.raises(SystemExit, match=says):
        longform.chapter_of({"chapter": chapter}, "scene 6")


def test_chapter_overlay_slides_in_from_off_frame_and_back_out():
    x, y, t0, t1 = _overlay_xy(longform.chapter_overlay(96, 86, 700, 0.0, 2.5))
    assert (t0, t1, y) == (0.0, 2.5, "86")
    assert _xy(x, 0.0) == pytest.approx(-700)
    assert _xy(x, longform.CHAPTER_IN_S) == pytest.approx(96)
    assert _xy(x, 1.5) == pytest.approx(96)
    assert _xy(x, 2.5) == pytest.approx(-700)


def test_chapter_png_fits_its_max_width_and_shrinks_or_refuses_a_long_title(tmp_path):
    Image = _pil()
    brand = {"accent": "#1F6F3D", "bg": "#343A46", "fg": "#FFFFFF"}
    ch = {"number": 3, "title": "Balloons", "kicker": "NUMBER 3"}
    out, w, h = longform.chapter_png(ch, brand, tmp_path / "c.png", 745)
    im = Image.open(out)
    assert im.size == (w, h) and im.mode == "RGBA" and w <= 745
    assert im.getpixel((0, 0))[3] == 0                     # transparent outside the panel
    sh = longform.CHAPTER_SHADOW
    r, g, b, a = im.getpixel((sh + 4, h // 2))              # the accent bar
    assert (r, g, b) == (0x1F, 0x6F, 0x3D) and a == 255
    long = {"number": 7, "title": "The rule about selfie sticks and the rule about drones",
            "kicker": "NUMBER 7"}
    _, w2, h2 = longform.chapter_png(long, brand, tmp_path / "l.png", 745)
    assert w2 <= 745 and h2 > h                            # wrapped to two lines
    with pytest.raises(SystemExit, match="does not fit"):
        longform.chapter_png({"title": "x" * 200, "kicker": ""}, brand, tmp_path / "x.png", 745)


# --- callouts -----------------------------------------------------------------------------------

def _callout(**kw):
    base = {"type": "sticker", "src": "media/photos/ai-x.png", "when": {"word": "mask"},
            "anchor": {"x": 0.8, "y": 0.35}}
    base.update(kw)
    return base


def test_check_callouts_normalises_a_sticker():
    (c,) = longform.check_callouts({"callouts": [_callout(label="1971")]})
    assert c["size"] == longform.STICKER_SIZE and c["seconds"] is None
    assert c["enter_from"] == "right"                       # nearest edge of (0.8, 0.35)
    assert c["labels"] == [{"text": "1971", "x": 0.5, "y": 0.8, "size": 0.14, "rotate": 0.0,
                            "color": "#FFFFFF", "ink": "#111111"}]
    timed = {k: v for k, v in _callout(at=4.0, seconds=2, enter_from="top", sfx="pop").items()
             if k != "when"}
    (d,) = longform.check_callouts({"callouts": [timed]})
    assert (d["when"], d["seconds"], d["enter_from"], d["sfx"]) == (4.0, 2.0, "top", "pop")


@pytest.mark.parametrize("callout, says", [
    (_callout(type="badge", text="456 FT"), "Shorts-only"),
    (_callout(type="hoot"), "Shorts-only"),
    (_callout(type="gif"), "must be sticker"),
    (_callout(at=3.0), "exactly one"),
    ({k: v for k, v in _callout().items() if k != "when"}, "exactly one"),
    (_callout(anchor={"x": 1.4, "y": 0.2}), "anchor.x"),
    (_callout(anchor=[0.5, 0.5]), "anchor"),
    (_callout(size=2), "size"),
    (_callout(hold="next_cut"), "unknown key"),
    (_callout(sfx="boing"), "sfx"),
    (_callout(enter_from="corner"), "enter_from"),
    (_callout(src=""), "src"),
    (_callout(label={"text": "x", "font": "y"}), "unknown label key"),
])
def test_check_callouts_refuses_by_name(callout, says):
    with pytest.raises(SystemExit, match=says):
        longform.check_callouts({"callouts": [callout]}, "scene 8")


def _rows(text, step=0.4):
    import illustrate
    return illustrate.word_rows([{"text": w, "start": round(i * step, 3),
                                  "end": round(i * step + 0.3, 3)}
                                 for i, w in enumerate(text.split())])


def test_callout_window_lands_on_its_word_and_leaves_at_the_next_cut_or_its_seconds():
    rows = _rows("And even a little kid's mask has to leave the eyes fully visible.")
    (c,) = longform.check_callouts({"callouts": [_callout()]})
    assert longform.callout_window(c, rows, 8.0, [], 3.0, "t") == (2.08, 5.08)   # 2.0 + 80 ms
    # the next picture cut 1 s or more after landing cuts the default hold short
    assert longform.callout_window(c, rows, 8.0, [2.5, 4.0], 3.0, "t") == (2.08, 4.0)
    # an explicit `seconds` wins, and nothing outlives the scene
    (s,) = longform.check_callouts({"callouts": [_callout(seconds=5)]})
    assert longform.callout_window(s, rows, 6.0, [4.0], 3.0, "t") == (2.08, 6.0)
    (n,) = longform.check_callouts({"callouts": [{k: v for k, v in _callout(at=1.25).items()
                                                  if k != "when"}]})
    assert longform.callout_window(n, rows, 8.0, [], 3.0, "t")[0] == 1.25      # no offset
    (late,) = longform.check_callouts({"callouts": [_callout(when=7.95)]})
    with pytest.raises(SystemExit, match="after its scene ends"):
        longform.callout_window(late, rows, 8.0, [], 3.0, "t")
    (missing,) = longform.check_callouts({"callouts": [_callout(when={"word": "balloon"})]})
    with pytest.raises(SystemExit, match="balloon"):
        longform.callout_window(missing, rows, 8.0, [], 3.0, "t")


@pytest.mark.parametrize("edge", ["bottom", "left", "right", "top"])
def test_sticker_overlay_starts_off_frame_and_lands_on_its_box(edge):
    box = (1300, 200, 1700, 600)
    x, y, t0, t1 = _overlay_xy(longform.sticker_overlay(box, edge, 2.0, 5.0))
    assert (t0, t1) == (2.0, 5.0)
    sx, sy = _xy(x, 2.0), _xy(y, 2.0)
    off = {"bottom": sy >= longform.H, "top": sy <= -400, "left": sx <= -400,
           "right": sx >= longform.W}
    assert off[edge]
    assert (_xy(x, 2.0 + longform.SLIDE_S), _xy(y, 2.0 + longform.SLIDE_S)) == (1300, 200)


def test_sticker_png_is_trimmed_and_sized_by_its_longer_side(tmp_path):
    Image = _pil()
    src = tmp_path / "s.png"
    im = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    im.paste((200, 40, 40, 255), (300, 100, 700, 900))      # 400 x 800 visible
    im.save(src)
    c = {"src": str(src), "size": 0.40, "labels": []}
    out, w, h = longform.sticker_png(c, tmp_path / "o.png")
    assert (w, h) == (216, 432) == longform.sticker_dims(src, 0.40)   # 0.40 * 1080 = 432
    plain = Image.open(out).copy()
    c["labels"] = [longform._label("EYES", "t")]
    out2, _, _ = longform.sticker_png(c, tmp_path / "o2.png")
    assert Image.open(out2).tobytes() != plain.tobytes()


# --- sound ------------------------------------------------------------------------------------

def test_bed_copies_cover_the_runtime_with_crossfades():
    assert longform.bed_copies(70, 50, 3) == 1
    n = longform.bed_copies(70, 900, 3)
    assert n == 14 and n * 70 - (n - 1) * 3 >= 900 > (n - 1) * 70 - (n - 2) * 3
    assert longform.bed_copies(60.9, 1000, 0) == math.ceil(1000 / 60.9)
    # repeats that skip a 17 s intro are 53 s long: 70 + 12 * 50 >= 660
    assert longform.bed_copies(70, 660, 3, loop_s=53) == 13
    with pytest.raises(SystemExit, match="too short"):
        longform.bed_copies(5, 900, 3)


def test_bed_loop_steps_crossfade_every_seam_and_trim_to_the_runtime():
    steps = longform.bed_loop_steps(3, 150.0, 3.0)
    assert sum("acrossfade=d=3:c1=qsin:c2=qsin" in s for s in steps) == 2
    assert steps[-1] == "[x2]atrim=0:150.000,asetpts=PTS-STARTPTS[bed]"
    assert any("concat=n=3:v=0:a=1" in s for s in longform.bed_loop_steps(3, 150.0, 0))
    one = longform.bed_loop_steps(1, 20.0, 3.0)
    assert not any("acrossfade" in s for s in one) and one[-1].startswith("[a0]atrim=0:20.000")


def test_every_copy_is_trimmed_to_the_audible_span_and_repeats_skip_the_intro():
    steps = longform.bed_loop_steps(3, 150.0, 3.0, span=(2.0, 67.5), loop_in=17.0)
    assert steps[0].startswith("[0:a]atrim=2.000:67.500,asetpts=PTS-STARTPTS,aformat")
    assert steps[1].startswith("[1:a]atrim=17.000:67.500,") and steps[2].startswith("[2:a]atrim=17.000:")
    assert longform.bed_loop_steps(2, 90.0, 3.0, span=(0.5, 70.0))[1].startswith(
        "[1:a]atrim=0.500:70.000,")


def test_audible_span_finds_the_first_and_last_sound():
    rate = 1000
    quiet, loud = [3] * 2000, [8000, -8000] * 1500            # 2 s at -80 dBFS, 3 s loud
    start, end = longform.audible_span(quiet + loud + quiet[:1500], rate)
    assert start == pytest.approx(2.0, abs=0.02) and end == pytest.approx(5.0, abs=0.02)
    assert longform.audible_span([0] * 3000, rate) == (0.0, 3.0)


def _bed_spec(tmp_path, **audio):
    bed = tmp_path / "bed.mp3"
    bed.write_bytes(b"")
    return {"slug": "t", "audio": {"bed": "pool:b1", **audio},
            "bed_pool": [{"id": "b1", "src": str(bed), "lufs": -24.2, "target_lufs": -24,
                          "fade_in": 0.3, "fade_out": 1.2}]}


def test_audio_mix_is_make_shorts_settings_with_a_pool_bed(tmp_path):
    spec = _bed_spec(tmp_path, master={"lufs": -16, "tp": -1.5, "lra": 11})
    mix = longform.audio_mix(spec, tmp_path / "scenes.yaml")
    assert mix.bed.lufs == -24.2 and mix.bed.target_lufs == -24
    assert (mix.master.lufs, mix.master.tp, mix.master.lra) == (-16, -1.5, 11)
    assert longform.audio_mix({"slug": "t"}, tmp_path / "scenes.yaml") is None
    steps = make_short.audio_steps(mix, runtime=900.0, cuts=[], bed_index=1, sfx_indexes=[])
    joined = ";".join(steps)
    assert "volume=0.2dB" in joined and "sidechaincompress" in joined
    assert "afade=t=out:st=898.800:d=1.2" in joined
    assert joined.endswith("loudnorm=I=-16:TP=-1.5:LRA=11[aout]")


def test_audio_mix_refuses_shorts_only_sfx_and_an_unmeasured_bed(tmp_path):
    with pytest.raises(SystemExit, match="Shorts-only"):
        longform.audio_mix(_bed_spec(tmp_path, sfx={"on_cut": "w.wav"}), tmp_path / "s.yaml")
    spec = _bed_spec(tmp_path)
    del spec["bed_pool"][0]["lufs"]
    with pytest.raises(SystemExit, match="lufs"):
        longform.audio_mix(spec, tmp_path / "s.yaml")


def test_kept_events_keeps_the_roles_it_has_a_file_for(tmp_path):
    pop = tmp_path / "pop.wav"
    pop.write_bytes(b"")
    spec = _bed_spec(tmp_path, sfx={"events": {"pop": str(pop)}})
    mix = longform.audio_mix(spec, tmp_path / "s.yaml")
    kept, missing = assemble.kept_events(mix, [{"at": 3.0, "role": "pop"},
                                               {"at": 9.0, "role": "whoosh"}])
    assert kept == [{"at": 3.0, "role": "pop"}] and missing == ["whoosh"]
    assert assemble.kept_events(None, [{"at": 1.0, "role": "pop"}]) == ([], ["pop"])


# --- chapters.json ------------------------------------------------------------------------------

def test_write_chapters_records_each_start_with_a_youtube_timestamp(tmp_path):
    marks = [{"scene": 2, "start": 16.53, "number": None, "title": "Rules", "kicker": ""},
             {"scene": 6, "start": 3725.2, "number": 1, "title": "Costumes", "kicker": "NUMBER 1"}]
    rows = json.loads(longform.write_chapters(tmp_path / "chapters.json", marks).read_text())
    assert [r["timestamp"] for r in rows] == ["0:16", "1:02:05"]
    assert rows[1]["title"] == "Costumes" and rows[0]["start"] == 16.53


# --- preflight ----------------------------------------------------------------------------------

def _touch(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"")
    return str(p)


def test_preflight_refuses_an_in_point_on_a_still_and_on_a_beats_scene(tmp_path):
    still, clip = _touch(tmp_path, "a.jpg"), _touch(tmp_path, "b.mp4")
    spec = {"landscape": {}, "scenes": [{"kind": "media", "src": still, "credit": "P", "in": 2}]}
    with pytest.raises(SystemExit, match="a still has none"):
        longform.preflight(spec, tmp_path / "s.yaml")
    spec["scenes"] = [{"kind": "media", "src": clip, "in": 1,
                       "beats": [{"src": clip, "seconds": 2}, {"src": clip, "seconds": 2}]}]
    with pytest.raises(SystemExit, match="put it on the beat"):
        longform.preflight(spec, tmp_path / "s.yaml")
    spec["scenes"] = [{"kind": "media", "src": clip,
                       "beats": [{"src": clip, "seconds": 2, "in": 4},
                                 {"src": still, "seconds": 2, "credit": "P"}]}]
    assert longform.preflight(spec, tmp_path / "s.yaml") is not None
    spec["scenes"][0]["beats"][1]["in"] = 1
    with pytest.raises(SystemExit, match=r"beats\[1\]"):
        longform.preflight(spec, tmp_path / "s.yaml")
    assert longform.preflight({"scenes": spec["scenes"]}, tmp_path / "s.yaml") is None


def test_preflight_refuses_a_sticker_over_the_earth_studio_zone(tmp_path):
    Image = _pil()
    earth = tmp_path / "earth"
    earth.mkdir()
    clip = _touch(earth, "mk.mp4")
    png = tmp_path / "s.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(png)
    scene = {"kind": "media", "src": clip, "callouts": [
        {"type": "sticker", "src": str(png), "at": 1.0, "anchor": {"x": 0.7, "y": 0.9},
         "size": 0.2}]}
    with pytest.raises(SystemExit, match="Earth Studio"):
        longform.preflight({"landscape": {}, "scenes": [scene]}, tmp_path / "s.yaml")
    scene["callouts"][0]["anchor"] = {"x": 0.7, "y": 0.3}
    longform.preflight({"landscape": {}, "scenes": [scene]}, tmp_path / "s.yaml")


# --- real renders (ffmpeg) ---------------------------------------------------------------------

def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, capture_output=True)


def _dur(p):
    return assemble.dur_of(p)


@needs_ffmpeg
def test_bed_loop_renders_exactly_the_runtime_with_no_silent_seam(tmp_path):
    bed = tmp_path / "bed.wav"
    # 1 s of silence, 4 s of tone, 1 s of silence: looped as is, every seam would be a 2 s hole
    _ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=1", "-f", "lavfi", "-i",
        "sine=frequency=330:duration=4:sample_rate=48000", "-f", "lavfi", "-i",
        "anullsrc=r=48000:cl=stereo:d=1", "-filter_complex",
        "[1:a]aformat=channel_layouts=stereo[s];[0:a][s][2:a]concat=n=3:v=0:a=1[o]",
        "-map", "[o]", str(bed))
    assert longform.bed_span(bed) == (pytest.approx(1.0, abs=0.03), pytest.approx(5.0, abs=0.03))
    out = longform.render_bed_loop(bed, 10.0, 1.0, tmp_path / "loop.wav")
    assert _dur(out) == pytest.approx(10.0, abs=0.03)
    q = tmp_path / "quiet.txt"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out), "-af",
                        "silencedetect=n=-50dB:d=0.2", "-f", "null", "-"],
                       capture_output=True, text=True)
    q.write_text(r.stderr)
    assert "silence_start" not in r.stderr


@needs_ffmpeg
def test_a_landscape_scene_renders_beats_chapter_sticker_and_captions(tmp_path):
    Image = _pil()
    clip = tmp_path / "clip.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=3", "-pix_fmt", "yuv420p",
        str(clip))
    still = tmp_path / "still.png"
    Image.new("RGB", (1600, 900), (30, 90, 200)).save(still)
    sticker = tmp_path / "sticker.png"
    Image.new("RGBA", (400, 400), (250, 200, 0, 255)).save(sticker)
    wav = tmp_path / "scene_00.wav"
    _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=3.6", "-ar", "24000", str(wav))
    words = [{"text": t, "start": round(0.3 + 0.4 * i, 3), "end": round(0.6 + 0.4 * i, 3)}
             for i, t in enumerate("Number one. Masks are out at that age too.".split())]
    wav.with_suffix(".words.json").write_text(json.dumps(words))
    scene = {"kind": "media", "chapter": {"number": 1, "title": "Costumes"},
             "beats": [{"src": str(clip), "seconds": 2, "in": 1.0},
                       {"src": str(still), "seconds": 2, "credit": "P"}],
             "callouts": [{"type": "sticker", "src": str(sticker), "when": {"word": "masks"},
                           "anchor": {"x": 0.8, "y": 0.4}, "size": 0.3, "seconds": 1.5,
                           "sfx": "pop"}]}
    out = tmp_path / "scene_00.mp4"
    opts = {"join": "cut", "captions": {"style": "sentence"}}
    events = assemble.landscape_media_part(scene, str(tmp_path / "s.yaml"), wav, 4.0, out, opts,
                                           tmp_path, 0, 30, spec_brand={"bg": "#343A46",
                                                                        "accent": "#1F6F3D"})
    assert events == [{"at": 1.18, "role": "pop"}]           # "Masks" at 1.1 s + 80 ms
    assert _dur(out) == pytest.approx(4.0, abs=0.07)
    frame = tmp_path / "f.png"

    def pixel(t, xy):
        _ff("-ss", f"{t}", "-i", str(out), "-frames:v", "1", str(frame))
        return Image.open(frame).convert("RGB").getpixel(xy)

    # 1.0 s: beat 0 (testsrc) under the chapter card, top-left (captions are lower-third)
    card = pixel(1.0, (140, 160))
    assert abs(card[0] - 0x34) < 24 and abs(card[2] - 0x46) < 24
    # 2.0 s: the sticker has landed at (0.8, 0.4); 3.2 s: beat 1 (the blue still), sticker gone
    sx, sy = round(0.8 * 1920), round(0.4 * 1080)
    yellow = pixel(2.0, (sx, sy))
    assert yellow[0] > 200 and yellow[1] > 160 and yellow[2] < 80
    blue = pixel(3.2, (sx, sy))
    assert blue[2] > 150 and blue[0] < 80
