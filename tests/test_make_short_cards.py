"""make_short.py's card branch, with the ffmpeg seam stubbed - no encode, no Chrome, no venv.

make_short imports yaml/PIL inside the functions that need them, so the module itself imports
with the standard library alone and these tests run in the plain `uv run --with pytest`
environment. `run()` is the single seam every ffmpeg invocation goes through; stubbing it lets
us assert the exact command the card branch builds instead of waiting on an encode.
"""
import json
import math
import pathlib
import sys
import types

import pytest

import make_short as M

SPEC = {
    "slug": "card-demo",
    "brand": {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"},
    "short": {"hook": "Three layouts", "scenes": [0, 1], "cta": "More → parksheet.com"},
    "scenes": [
        {"kind": "card", "template": "ranked_list",
         "data": {"heading": "Shortest waits", "subheading": "Magic Kingdom",
                  "items": [{"rank": 1, "label": "Speedway", "value": 5}],
                  "footer": "Powered by Queue-Times.com"},
         "narration": "one"},
        {"kind": "card", "template": "changed",
         "data": {"heading": "What changed", "subheading": "This week",
                  "items": [{"label": "Test Track", "value": "Reopened on Tuesday after a "
                                                             "long refurbishment this week."}],
                  "footer": "Powered by Queue-Times.com"},
         "narration": "two"},
    ],
}
DURATIONS = {"0": 4.0, "1": 6.0}


def _expected_encode_cmd(png, wav, out, dur, crf=26, join="fade"):
    """The ffmpeg command as make_short built it before encode_scene was extracted.

    Plus `-color_range tv`, added later so the TAG matches the limited-range pixels every
    scene kind already produced — see the colour-range tests below.
    """
    n = math.ceil(dur * 30)
    dz = (1.06 - 1.0) / n
    vf = (f"scale=1296:2304:flags=lanczos,zoompan=z='min(zoom+{dz:.7f},1.06)':"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1920:fps=30,"
          f"{M.fade_steps(dur, join)}format=yuv420p")
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-i", str(wav),
            "-filter_complex",
            f"[0:v]{vf}[v];[1:a]apad=pad_dur=2,afade=t=in:d=0.05,"
            f"aformat=sample_rates=48000:channel_layouts=stereo[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264",
            "-preset", "medium", "-crf", str(crf), "-r", "30", "-color_range", "tv",
            "-bsf:v", "h264_metadata=video_full_range_flag=0",
            "-c:a", "aac", "-b:a", "128k", str(out)]


# --- encode_scene ---------------------------------------------------------------------

def test_encode_scene_writes_its_mp4_beside_the_png_it_was_given(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "run", lambda cmd: None)
    out = M.encode_scene(tmp_path / "scene_0.png", tmp_path / "scene_00.wav", 5.0, 26)
    assert out == tmp_path / "scene_0.mp4"


@pytest.mark.parametrize("dur,crf", [(5.0, 26), (12.9, 20), (0.7, 30)])
def test_encode_scene_builds_the_command_the_inline_block_used_to_build(tmp_path, monkeypatch,
                                                                        dur, crf):
    """Locks the encode byte-for-byte: existing Shorts must come out of the extraction unchanged."""
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    png, wav = tmp_path / "scene_1.png", tmp_path / "scene_03.wav"
    out = M.encode_scene(png, wav, dur, crf)
    assert seen == [_expected_encode_cmd(png, wav, out, dur, crf)]


# --- the card branch of main() ---------------------------------------------------------

@pytest.fixture
def stub_main(tmp_path, monkeypatch):
    """Run main() against a card-only spec with every external tool stubbed out."""
    monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(safe_load=lambda fh: SPEC))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")
    build = tmp_path / "build" / "card-demo"
    (build / "audio").mkdir(parents=True)
    (build / "audio" / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: 30.0)
    monkeypatch.setattr(M, "subprocess",
                        types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    cards_seen, shots, cmds = [], [], []
    monkeypatch.setattr(M.R, "render_card_scene",
                        lambda *a, **k: cards_seen.append((a, k)))
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: shots.append(a))
    monkeypatch.setattr(M, "run", cmds.append)
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(spec_path)])
    return types.SimpleNamespace(build=build, cards=cards_seen, shots=shots, cmds=cmds,
                                 spec_path=spec_path)


def test_card_branch_renders_each_card_at_the_short_canvas(stub_main):
    M.main()
    assert len(stub_main.cards) == 2
    (png0, template0, data0, brand0, w0, h0), kw0 = stub_main.cards[0]
    assert template0 == "ranked_list" and data0 == SPEC["scenes"][0]["data"]
    assert brand0 == SPEC["brand"]
    assert (w0, h0) == (M.RW, M.RH) == (1296, 2304)
    assert kw0["html_dir"] == stub_main.build / "short"
    assert png0 == stub_main.build / "short" / "scene_0.png"
    assert stub_main.cards[1][0][1] == "changed"


def test_card_branch_encodes_its_own_png_against_the_narrated_wav(stub_main):
    M.main()
    work = stub_main.build / "short"
    for k, idx in enumerate(SPEC["short"]["scenes"]):
        dur = DURATIONS[str(idx)] + M.SCENE_PAD
        assert stub_main.cmds[k] == _expected_encode_cmd(
            work / f"scene_{k}.png", stub_main.build / "audio" / f"scene_{idx:02d}.wav",
            work / f"scene_{k}.mp4", dur)


def test_card_branch_concatenates_into_the_slugs_final_short(stub_main):
    M.main()
    final = stub_main.build / "card-demo-short.mp4"
    concat = [c for c in stub_main.cmds if "concat" in c]
    assert len(concat) == 1 and str(final) in concat[0]
    listed = (stub_main.build / "short" / "concat.txt").read_text().splitlines()
    assert listed == [f"file '{stub_main.build / 'short' / n}'"
                      for n in ("scene_0.mp4", "scene_1.mp4", "end.mp4")]


def test_a_card_only_short_needs_no_frames_or_focus_json(stub_main):
    M.main()  # build/frames never existed; the card branch must not read it
    assert not (stub_main.build / "frames").exists()


def test_missing_narration_durations_names_narrate_py(stub_main):
    (stub_main.build / "audio" / "durations.json").unlink()
    with pytest.raises(SystemExit) as e:
        M.main()
    assert "narrate.py" in str(e.value)
    assert "durations.json" in str(e.value)


@pytest.mark.parametrize("slug", ["../../etc", "a/b", ".."])
def test_a_traversing_slug_is_rejected_before_it_is_used_to_open_a_spec(stub_main, slug):
    """--slug also builds a path (marketing/video/<slug>/scenes.yaml), so validate it first."""
    sys.argv = ["make_short.py", "--slug", slug]   # restored by the fixture's monkeypatch
    with pytest.raises(SystemExit) as e:
        M.main()
    assert "slug" in str(e.value)


# --- colour range ------------------------------------------------------------------------

def test_every_scene_kind_tags_its_output_limited_range(tmp_path, monkeypatch):
    """The pixels were always limited range; only the TAG was missing, and only on some
    parts. Parts are concatenated with `-c:v copy`, so mixed tagging leaves the finished
    Short's range depending on which scene happened to be encoded first."""
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    M.encode_scene(tmp_path / "scene_0.png", tmp_path / "scene_00.wav", 5.0, 26)
    cmd = seen[0]
    assert cmd[cmd.index("-color_range") + 1] == "tv"
    # libx264 only signals limited range in the VUI when a conversion actually happened, so
    # -color_range alone leaves most parts untagged. The bitstream filter writes the flag
    # unconditionally, and it survives the `-c:v copy` concat.
    assert cmd[cmd.index("-bsf:v") + 1] == "h264_metadata=video_full_range_flag=0"


# --- steps: the card analogue of beats: -------------------------------------------------

STEPS = [{"reveal": 0.25, "seconds": 1.0}, {"reveal": 0.6, "seconds": 1.0},
         {"reveal": 1.0, "seconds": 2.0}]


def test_a_card_scene_with_no_steps_reads_as_no_steps():
    assert M.scene_steps({"kind": "card", "template": "ranked_list"}) == []
    assert M.scene_steps({"kind": "card", "steps": []}) == []
    assert M.scene_steps({}) == []


def test_scene_steps_normalises_what_the_spec_wrote():
    assert M.scene_steps({"steps": STEPS}) == [
        {"reveal": 0.25, "seconds": 1.0},
        {"reveal": 0.6, "seconds": 1.0},
        {"reveal": 1.0, "seconds": 2.0},
    ]


@pytest.mark.parametrize("steps,needle", [
    ({"reveal": 1.0, "seconds": 1.0}, "must be a list"),
    ([{"reveal": 1.0, "seconds": 1.0}], "one picture IS the scene"),
    ([{"seconds": 1.0}, {"reveal": 1.0, "seconds": 1.0}], "needs a `reveal`"),
    ([{"reveal": 0.5, "seconds": 0}, {"reveal": 1.0, "seconds": 1.0}], "positive length"),
    ([{"reveal": 0.5, "seconds": 7.0}, {"reveal": 1.0, "seconds": 1.0}], "backstop"),
    ([{"reveal": 0.6, "seconds": 1.0}, {"reveal": 0.6, "seconds": 1.0},
      {"reveal": 1.0, "seconds": 1.0}], "increase"),
    ([{"reveal": 0.5, "seconds": 1.0}, {"reveal": 0.9, "seconds": 1.0}], "finish drawn"),
    ([{"reveal": 1.4, "seconds": 1.0}, {"reveal": 1.0, "seconds": 1.0}], "between 0.0 and 1.0"),
])
def test_a_malformed_steps_block_stops_the_render_by_name(steps, needle):
    with pytest.raises(SystemExit) as excinfo:
        M.scene_steps({"steps": steps})
    assert needle in str(excinfo.value)


def test_step_frames_sum_to_the_scenes_whole_frame_count():
    spans = [1.0, 1.0, 2.0]
    counts = M.step_frames(spans, 30)
    assert counts == [30, 30, 60]
    assert sum(counts) == math.ceil(sum(spans) * 30)


def test_step_frames_put_the_rounding_in_the_last_step():
    """0.55 s at 30 fps is 16.5 frames and rounds to 16 (ties-to-even), four times; the
    scene is 66 frames, so the last step absorbs the two the others left behind."""
    spans = [0.55, 0.55, 0.55, 0.55]
    counts = M.step_frames(spans, 30)
    assert sum(counts) == math.ceil(sum(spans) * 30) == 66
    assert counts == [16, 16, 16, 18]


def test_every_step_gets_at_least_one_frame():
    assert all(n >= 1 for n in M.step_frames([0.02, 0.02, 1.0], 30))


def test_encode_card_steps_builds_one_zoompan_per_png_continuing_the_same_push(
        tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    pngs = [tmp_path / f"s{i}.png" for i in range(3)]
    for png in pngs:
        png.write_bytes(b"")
    out = M.encode_card_steps(pngs, [1.0, 1.0, 2.0], tmp_path / "v.wav", 4.0, 26,
                              tmp_path / "scene_0.mp4", join="cut")
    assert out == tmp_path / "scene_0.mp4"
    cmd = seen[0]
    graph = cmd[cmd.index("-filter_complex") + 1]

    # one input per PNG, then the WAV
    assert cmd[4:10] == ["-i", str(pngs[0]), "-i", str(pngs[1]), "-i", str(pngs[2])]
    assert cmd[10:12] == ["-i", str(tmp_path / "v.wav")]
    # one chain per step, each ending at the delivered size, each trimmed and PTS-reset
    n = math.ceil(4.0 * M.FPS)
    dz = (1.06 - 1.0) / n
    for i, (frames_before, frames) in enumerate(((0, 30), (30, 30), (60, 60))):
        assert f"[{i}:v]scale={M.RW}:{M.RH}:flags=lanczos,zoompan=" in graph
        assert f"min({1.0 + frames_before * dz:.7f}+on*{dz:.7f},1.06)" in graph
        assert f":d={frames}:s={M.OUT_W}x{M.OUT_H}:fps={M.FPS}" in graph
        assert f"trim=duration={frames / M.FPS:.3f},setpts=PTS-STARTPTS[c{i}]" in graph
    assert "[c0][c1][c2]concat=n=3:v=1:a=0[m0]" in graph
    # the push is CONTINUOUS: the last step starts where the second one ended
    assert f"min({1.0:.7f}+on*" in graph and f"min({1.0 + 60 * dz:.7f}+on*" in graph


def test_encode_card_steps_normalises_every_step_before_the_concat(tmp_path, monkeypatch):
    """concat demands identical size, pixel format and SAR -- BEAT_TAIL is the one place
    those three are spelled, and a card step goes through the same one a beat does."""
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    pngs = [tmp_path / f"s{i}.png" for i in range(2)]
    for png in pngs:
        png.write_bytes(b"")
    M.encode_card_steps(pngs, [1.0, 1.0], tmp_path / "v.wav", 2.0, 26,
                        tmp_path / "o.mp4")
    graph = seen[0][seen[0].index("-filter_complex") + 1]
    assert graph.count(M.BEAT_TAIL) == 2


def test_encode_card_steps_output_flags_match_encode_scene_exactly(tmp_path, monkeypatch):
    """The parts are concatenated with `-c:v copy`; a card scene that encoded differently
    would break the concat."""
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    png = tmp_path / "s0.png"; png.write_bytes(b"")
    M.encode_card_steps([png, png], [1.0, 1.0], tmp_path / "v.wav", 2.0, 26,
                        tmp_path / "o.mp4")
    cmd = seen[0]
    tail = cmd[cmd.index("-map"):]
    assert tail == ["-map", "[v]", "-map", "[a]", "-t", "2.000", "-c:v", "libx264",
                    "-preset", "medium", "-crf", "26", "-r", "30", "-color_range", "tv",
                    "-bsf:v", M.RANGE_BSF, "-c:a", "aac", "-b:a", "128k",
                    str(tmp_path / "o.mp4")]


def test_a_media_scene_may_not_carry_steps(tmp_path, monkeypatch):
    spec = {"slug": "x", "short": {"scenes": [0]},
            "scenes": [{"kind": "media", "src": "a.jpg", "steps": STEPS}]}
    monkeypatch.setitem(sys.modules, "yaml",
                        types.SimpleNamespace(safe_load=lambda fh: spec))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    monkeypatch.setattr(M.media, "validate_spec", lambda *a, **k: None)
    path = tmp_path / "scenes.yaml"; path.write_text("# stubbed\n")
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(path)])
    with pytest.raises(SystemExit) as excinfo:
        M.main()
    assert "steps:" in str(excinfo.value) and "card" in str(excinfo.value)


STEPPED_SPEC = {
    **SPEC,
    "short": {"hook": "Three layouts", "scenes": [0, 1], "cta": "More → parksheet.com"},
    "scenes": [
        {**SPEC["scenes"][0], "steps": [{"reveal": 0.4, "seconds": 2.0},
                                        {"reveal": 1.0, "seconds": 2.0}]},
        SPEC["scenes"][1],
    ],
}


@pytest.fixture
def stub_main_stepped(tmp_path, monkeypatch):
    """stub_main, against a spec whose first card scene carries `steps:`."""
    monkeypatch.setitem(sys.modules, "yaml",
                        types.SimpleNamespace(safe_load=lambda fh: STEPPED_SPEC))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")
    build = tmp_path / "build" / "card-demo"
    (build / "audio").mkdir(parents=True)
    (build / "audio" / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: 30.0)
    monkeypatch.setattr(M, "subprocess",
                        types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    cards_seen, shots, cmds = [], [], []
    monkeypatch.setattr(M.R, "render_card_scene",
                        lambda *a, **k: cards_seen.append((a, k)))
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: shots.append(a))
    monkeypatch.setattr(M, "run", cmds.append)
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(spec_path)])
    return types.SimpleNamespace(build=build, cards=cards_seen, shots=shots, cmds=cmds)


def test_a_stepped_card_scene_screenshots_one_png_per_step(stub_main_stepped):
    M.main()
    stepped = [c for c in stub_main_stepped.cards if "reveal" in c[1]]
    assert [c[1]["reveal"] for c in stepped] == [0.4, 1.0]
    assert [c[0][0].name for c in stepped] == ["scene_0_step0.png", "scene_0_step1.png"]
    # scene 1 has no steps, so it is rendered exactly as it always was: no reveal kwarg.
    plain = [c for c in stub_main_stepped.cards if "reveal" not in c[1]]
    assert [c[0][0].name for c in plain] == ["scene_1.png"]


def test_a_stepped_card_scene_records_its_spans_so_cuts_json_counts_them(stub_main_stepped):
    M.main()
    cuts = json.loads((stub_main_stepped.build / "short" / "cuts.json").read_text())
    scene0 = next(row for row in cuts["scenes"] if row["scene"] == 0)
    assert len(scene0["beats"]) == 2
    # The spans sum to the ENCODE's clock (DURATIONS["0"] + SCENE_PAD), not ffprobe's --
    # `dur_of` is stubbed flat at 30.0 for every part in this fixture (see stub_main_stepped
    # / test_the_part_boundaries_are_measured_and_the_closing_plate_is_one_of_them for the
    # same decoupling on a media scene), so `scene0["seconds"]` is 30.0 regardless of what
    # the scene actually encoded to.
    assert sum(scene0["beats"]) == pytest.approx(DURATIONS["0"] + M.SCENE_PAD, abs=0.002)
    # the step boundary inside scene 0 is a picture change in its own right
    assert round(scene0["start"] + scene0["beats"][0], 3) in cuts["cuts"]
