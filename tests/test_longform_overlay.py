"""scripts/video/longform_overlay.py: the v6 Shorts overlay language on the 16:9 path -- Hoot,
badges, stamps, arrows, circles, verdict washes and their sounds (2026-11-23 follow-up).

Logic tests are stdlib + pytest; drawing skips without PIL, renders skip without ffmpeg. Hoot is
tested against a synthetic pose set written to tmp_path (PARKSHEET_HOOT_SET), never ParkSheet's."""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))
import assemble  # noqa: E402
import grammar  # noqa: E402
import longform  # noqa: E402
import longform_overlay as lo  # noqa: E402
import make_short  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is absent")


def _touch(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"")
    return str(p)


# --- sound ------------------------------------------------------------------------------------

def _mix(tmp_path, **sfx):
    bed = _touch(tmp_path, "bed.mp3")
    spec = {"slug": "t", "audio": {"bed": {"src": bed, "lufs": -24.2, "target_lufs": -24},
                                   "sfx": sfx}}
    return longform.audio_mix(spec, tmp_path / "s.yaml")


def test_placements_use_the_events_file_then_on_tag_then_say_why(tmp_path):
    pop, whoosh, buzz = (_touch(tmp_path, n) for n in ("pop.wav", "wh.wav", "bz.wav"))
    mix = _mix(tmp_path, events={"pop": {"src": pop, "gain_db": -13}},
               on_tag={"src": whoosh, "gain_db": -20},
               on_verdict={"bad": {"src": buzz, "gain_db": -15}})
    rows, notes = lo.placements(
        mix, [{"at": 2.0, "role": "pop"}, {"at": 5.0, "role": "ding"}],
        [{"at": 9.0, "role": "verdict_bad"}, {"at": 12.0, "role": "verdict_good"}],
        [{"at": 20.0}], {"src": whoosh, "gain_db": -16.0, "lead": 0.2})
    got = [(r["at"], r["role"], r["src"], r["gain_db"]) for r in rows]
    assert got == [(2.0, "tag", pop, -13.0), (5.0, "tag", whoosh, -20.0),
                   (9.0, "verdict_bad", buzz, -15.0), (19.8, "cut", whoosh, -16.0)]
    assert any("verdict_good" in n and "on_verdict" in n for n in notes)


def test_placements_thin_a_collision_in_favour_of_the_verdict(tmp_path):
    pop, buzz = _touch(tmp_path, "pop.wav"), _touch(tmp_path, "bz.wav")
    mix = _mix(tmp_path, events={"pop": pop}, on_verdict={"bad": {"src": buzz}})
    rows, notes = lo.placements(mix, [{"at": 3.05, "role": "pop"}],
                                [{"at": 3.0, "role": "verdict_bad"}], [], None)
    assert [r["role"] for r in rows] == ["verdict_bad"] and "dropped" in notes[0]


def test_without_an_audio_block_only_the_chapter_sound_plays():
    rows, notes = lo.placements(None, [{"at": 1.0, "role": "pop"}], [], [{"at": 0.1}],
                                {"src": "/s/w.wav", "gain_db": -16.0, "lead": 0.2})
    assert [(r["at"], r["role"]) for r in rows] == [(0.0, "cut")] and len(notes) == 1


def test_chapter_sound_defaults_to_the_whoosh_and_can_be_turned_off():
    resolve = lambda src: f"/r/{src}"                        # noqa: E731
    assert lo.chapter_sound({}, resolve) == {"src": "/r/bundle:whoosh", "gain_db": -16.0,
                                             "lead": 0.2}
    assert lo.chapter_sound({"chapter_sfx": None}, resolve) is None
    assert lo.chapter_sound({"chapter_sfx": "bundle:ding"}, resolve)["src"] == "/r/bundle:ding"
    with pytest.raises(SystemExit, match="unknown landscape.chapter_sfx"):
        lo.chapter_sound({"chapter_sfx": {"src": "x", "volume": 3}}, resolve)
    assert longform.options({"landscape": {"chapter_sfx": None}}) is not None


def test_null_shorts_keys_are_dropped_and_live_ones_refused():
    spec = {"audio": {"bed": "rotate", "sfx": {"on_cut": None, "opening": None, "events": {}}}}
    lo.check_sfx_block(spec)
    assert lo.strip_nulls(spec)["audio"]["sfx"] == {"events": {}}
    with pytest.raises(SystemExit, match="whoosh on every cut"):
        lo.check_sfx_block({"audio": {"sfx": {"on_cut": {"src": "bundle:hit"}}}})


def test_bus_steps_split_one_input_per_file_and_delay_each_use():
    rows = [{"at": 1.0, "src": "/a.wav", "gain_db": -13}, {"at": 4.5, "src": "/b.wav",
             "gain_db": -15, "start": 0.1, "end": 0.9}, {"at": 7.25, "src": "/a.wav",
             "gain_db": -13}]
    files, steps = lo.bus_steps(rows, 10.0)
    assert files == ["/a.wav", "/b.wav"]
    assert "asplit=2" in steps[0] and "adelay=1000|1000" in steps[1] and "adelay=7250|7250" in steps[2]
    assert "atrim=start=0.1:end=0.9" in steps[4]
    assert "atrim=0:10.000,apad=whole_dur=10.000[s0_0]" in steps[1]
    assert steps[-1].endswith("amix=inputs=3:normalize=0:dropout_transition=0,"
                              "atrim=0:10.000[bus]")


@needs_ffmpeg
def test_the_bus_renders_exactly_the_runtime(tmp_path):
    tone = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=880:duration=0.3", str(tone)], check=True)
    out = lo.render_bus([{"at": 0.5, "src": str(tone), "gain_db": -6},
                         {"at": 3.0, "src": str(tone), "gain_db": -6}], 6.0, tmp_path / "b.wav")
    assert assemble.dur_of(out) == pytest.approx(6.0, abs=0.03)
    assert lo.render_bus([], 6.0, tmp_path / "none.wav") is None


# --- verdicts ---------------------------------------------------------------------------------

def _words(text, step=0.4):
    return [{"text": w, "start": round(0.2 + i * step, 3), "end": round(0.5 + i * step, 3)}
            for i, w in enumerate(text.split())]


def test_verdict_windows_are_the_shorts_washes():
    words = _words("If you're fourteen or older, you can't wear a costume.")
    (v, w), = lo.verdict_windows({"fx": {"verdict": "bad", "style": "wash",
                                         "at": {"word": "can't"}}}, words, 6.0, "scene 6")
    assert v == "bad" and w.t0 == pytest.approx(2.6 - 0.08) and "lutrgb" in w.filter
    two = {"fx": [{"verdict": "bad", "style": "wash", "at": {"word": "can't"}},
                  {"verdict": "good", "style": "wash", "at": {"word": "wear"}}]}
    with pytest.raises(SystemExit, match="overlap"):
        lo.verdict_windows(two, words, 6.0, "scene 6")          # red holds 330 ms past "wear"
    two["fx"][1]["at"] = {"word": "a"}
    assert [v for v, _w in lo.verdict_windows(two, words, 6.0, "s")] == ["bad", "good"]


# --- drawing ----------------------------------------------------------------------------------

def _pil():
    return pytest.importorskip("PIL.Image")


def test_scale_at_follows_the_measured_overshoot():
    import callouts
    e = callouts.EASING["pop_badge"]
    assert lo.scale_at(e, 0) == pytest.approx(0.60)
    assert lo.scale_at(e, 200) == pytest.approx(1.15)
    assert lo.scale_at(e, 300) == pytest.approx(1.0) and lo.scale_at(e, 900) == 1.0


def test_entrance_draws_a_sequence_that_settles_on_the_image(tmp_path):
    Image = _pil()
    img = Image.new("RGBA", (100, 40), (255, 0, 0, 255))
    mode, path, cw, ch, pc = lo.entrance(img, (50, 20), "pop_badge", 0.3, tmp_path, "c00")
    frames = sorted((tmp_path / "c00").glob("f_*.png"))
    assert mode == "seq" and len(frames) == 10 and cw >= 115
    assert pc == (pytest.approx(58.5), pytest.approx(24.0))
    last = Image.open(frames[-1])
    box = last.getchannel("A").getbbox()                       # scale 1.0, pivot fixed
    assert (box[2] - box[0], box[3] - box[1]) == (100, 40) and abs(box[0] - 8.5) <= 1
    first = Image.open(frames[0]).getchannel("A").getbbox()
    assert first[2] - first[0] == 60                           # scale 0.60
    assert lo.entrance(img, (50, 20), "slide_in", 0.3, tmp_path, "c01")[0] == "png"


def test_badge_text_and_arrow_keep_their_short_pixels_and_pivots():
    _pil()
    badge, pivot = lo.badge_image({"type": "badge", "text": "456 FT"})
    assert 80 < badge.size[1] < 200 and pivot == (badge.size[0] / 2, badge.size[1] / 2)
    stamp, _ = lo.badge_image({"type": "text", "text": "PARDONED"})
    assert stamp.getpixel((stamp.size[0] // 2, stamp.size[1] // 2))[3] > 0
    arrow, tip = lo.arrow_image({"type": "arrow", "direction": "right", "size": 0.2})
    a = arrow.getchannel("A")
    assert abs(tip[0] - a.getbbox()[2]) < 8                    # the tip is the right edge
    ring, centre = lo.circle_image({"type": "circle", "size": 0.3})
    assert ring.getpixel((round(centre[0]), round(centre[1])))[3] == 0   # hollow


def _hoot_set(tmp_path):
    from PIL import Image
    d = tmp_path / "hoot"
    d.mkdir()
    poses = {}
    for name in ("neutral", "badge", "point_left", "point_right", "point_up", "point_down",
                 "nope", "thinking"):
        im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        im.paste((240, 120, 20, 255), (45, 35, 220, 220))
        im.save(d / f"hoot-{name}.png")
        poses[name] = {"src": f"hoot-{name}.png", "body": [0.1758, 0.1348, 0.875, 0.8535]}
    poses["badge"]["badge"] = [0.5, 0.62, 0.1]
    poses["nope"]["badge"] = [0.74, 0.33, 0.15]
    poses["nope"]["badge_color"] = "#E5202A"
    bub = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    bub.paste((255, 255, 255, 255), (20, 65, 235, 180))
    bub.save(d / "bubble.png")
    data = {"poses": poses, "bubble": {"src": "bubble.png", "body": [0.082, 0.2559, 0.918, 0.709],
                                       "text_box": [0.1842, 0.3288, 0.806, 0.5599],
                                       "tail": [0.2168, 0.709]}}
    (d / "hoot.json").write_text(json.dumps(data))
    return d / "hoot.json"


@pytest.fixture
def hoot_env(tmp_path, monkeypatch):
    _pil()
    path = _hoot_set(tmp_path)
    monkeypatch.setenv("PARKSHEET_HOOT_SET", str(path))
    make_short._HOOT_CACHE.clear()
    return path


def _layers(calls, tmp_path, avoid=(), earth=(), dur=6.0, words=None):
    rows = __import__("illustrate").word_rows(words or _words("one two three four five six"))
    checked = lo.check(calls, "scene 1", {}, tmp_path / "s.yaml")
    return lo.build_layers(checked, rows, dur, [], 3.0, tmp_path / "work", "scene 1",
                           lambda a, b: list(avoid), lambda a, b: list(earth))


def test_hoot_takes_the_default_lower_left_and_climbs_over_a_caption_box(hoot_env, tmp_path):
    (L,) = _layers([{"type": "hoot", "when": {"word": "two"}}], tmp_path)
    assert L.callout == "hoot" and L.slide in ("left", "bottom") and L.sfx == "pop"
    assert L.box[0] < 0.2 * lo.W and L.box[3] > 0.8 * lo.H     # lower-left
    band = (0, int(0.75 * lo.H), lo.W, int(0.95 * lo.H))
    (up,) = _layers([{"type": "hoot", "when": {"word": "two"}}], tmp_path, avoid=[band])
    assert up.box[3] <= band[1]
    with pytest.raises(SystemExit, match="caption box"):
        _layers([{"type": "hoot", "when": {"word": "two"}, "anchor": {"x": 0.5, "y": 0.85}}],
                tmp_path, avoid=[band])


def test_hoot_nope_with_an_x_pops_and_a_pointing_hoot_faces_its_point(hoot_env, tmp_path):
    (nope,) = _layers([{"type": "hoot", "when": {"word": "three"}, "pose": "nope",
                        "badge_text": "X", "hold": 650}], tmp_path)
    assert nope.kind == "seq" and nope.slide is None           # overshoot, as in the Shorts
    hs = lo.load_hoot_set({}, tmp_path / "s.yaml")
    img, _c, _b, pose, _s = lo.hoot_image({"type": "hoot", "point_to": {"x": 0.8, "y": 0.3}},
                                          hs, 0.15, 0.7)
    assert pose == "point_right"
    _i, _c, _b, pose, _s = lo.hoot_image({"type": "hoot", "point_to": {"x": 0.15, "y": 0.3}},
                                         hs, 0.15, 0.8)
    assert pose == "point_up"
    with pytest.raises(SystemExit, match="unknown hoot pose"):
        _layers([{"type": "hoot", "when": 1.0, "pose": "moonwalk"}], tmp_path)


def test_hoot_with_a_bubble_grows_his_image(hoot_env, tmp_path):
    hs = lo.load_hoot_set({}, tmp_path / "s.yaml")
    plain = lo.hoot_image({"type": "hoot"}, hs, None, None)[0]
    said = lo.hoot_image({"type": "hoot", "say": "BALLOON DAYCARE"}, hs, None, None)[0]
    assert said.size[0] > plain.size[0] and said.size[1] >= plain.size[1]


def test_no_callout_may_cover_an_earth_zone(hoot_env, tmp_path):
    zone = (int(0.45 * lo.W), int(0.88 * lo.H), lo.W, lo.H)
    with pytest.raises(SystemExit, match="Earth Studio"):
        _layers([{"type": "badge", "text": "X", "when": 1.0, "anchor": {"x": 0.7, "y": 0.93}}],
                tmp_path, earth=[zone])
    (L,) = _layers([{"type": "hoot", "when": 1.0, "point_to": {"x": 0.2, "y": 0.3}}],
                   tmp_path, earth=[zone])                     # pointing left: lower-right...
    assert not lo._hits(L.box, zone)                           # ...climbed clear of the mark


@needs_ffmpeg
def test_a_scene_renders_a_verdict_wash_and_a_hoot(hoot_env, tmp_path):
    Image = _pil()
    still = tmp_path / "still.png"
    Image.new("RGB", (1920, 1080), (128, 128, 128)).save(still)
    wav = tmp_path / "scene_00.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=220:duration=3.6", "-ar", "24000", str(wav)], check=True)
    words = _words("Masks are out at that age too.")
    wav.with_suffix(".words.json").write_text(json.dumps(words))
    scene = {"kind": "media", "src": str(still), "credit": "P", "motion": "hold",
             "fx": {"verdict": "bad", "style": "wash", "at": {"word": "out"}},
             "callouts": [{"type": "hoot", "when": {"word": "masks"}, "pose": "nope",
                           "badge_text": "X", "hold": "scene", "sfx": "pop"}]}
    out = tmp_path / "scene_00.mp4"
    events = assemble.landscape_media_part(scene, str(tmp_path / "s.yaml"), wav, 4.0, out,
                                           {"join": "cut", "captions": {"enabled": False}},
                                           tmp_path, 0, 30, spec_brand={}, spec={})
    assert {e["kind"] for e in events} == {"verdict", "callout"}
    frame = tmp_path / "f.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(out),
                    "-frames:v", "1", str(frame)], check=True)
    im = Image.open(frame).convert("RGB")
    r, g, b = im.getpixel((960, 400))
    assert r > g + 20                                          # the red wash on the grey
    hoot = im.getpixel((round(0.035 * lo.W) + 60, round(0.85 * lo.H)))
    assert hoot[0] > 200 and hoot[2] < 90                      # Hoot's orange, lower-left
