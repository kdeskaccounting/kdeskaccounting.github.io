"""make_short.py's `media` branch, with the ffmpeg and Chrome seams stubbed.

Same shape as tests/test_make_short_cards.py: make_short imports yaml/PIL inside the
functions that need them, `run()` is the single seam every ffmpeg invocation goes through,
and `R.screenshot` is the single seam every Chrome invocation goes through — so stubbing
both lets us assert the exact composite ffmpeg is asked to build without waiting on an
encode. No venv, no Chrome, no ffmpeg.

What matters here and nowhere else: the credit plate and the overlay reach ffmpeg as
full-frame transparent PNGs laid over the footage at 0,0, which is what makes
media.credit_box/overlay_box — and therefore the Earth Studio attribution zone they avoid —
the single place that decides where anything lands.
"""
import json
import pathlib
import re
import sys
import types

import pytest

import cards
import make_short as M
import media

BRAND = {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"}
CREDIT = "Imagery: Google Earth, Maxar Technologies"
OVERLAY = {
    "template": "ranked_list",
    "data": {"heading": "Shortest waits", "subheading": "Magic Kingdom",
             "items": [{"rank": 1, "label": "Speedway", "value": 5}],
             "footer": "Powered by Queue-Times.com"},
}
DURATIONS = {"0": 4.0, "1": 6.0}


def _spec():
    return {
        "slug": "media-demo",
        "brand": dict(BRAND),
        "short": {"hook": "Two media scenes", "scenes": [0, 1],
                  "cta": "More → parksheet.com"},
        "scenes": [
            {"kind": "media", "src": "assets/still.png", "motion": "kenburns",
             "credit": CREDIT, "overlay": dict(OVERLAY), "narration": "one"},
            {"kind": "media", "src": "assets/clip.mp4", "motion": "clip",
             "credit": CREDIT, "narration": "two"},
        ],
    }


@pytest.fixture
def stub_main(tmp_path, monkeypatch):
    """Run main() against a media-only spec with every external tool stubbed out."""
    spec = _spec()
    monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(safe_load=lambda fh: spec))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "still.png").write_bytes(b"\0")
    (assets / "clip.mp4").write_bytes(b"\0")
    build = tmp_path / "build" / "media-demo"
    (build / "audio").mkdir(parents=True)
    (build / "audio" / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: 30.0)
    monkeypatch.setattr(M, "subprocess",
                        types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    shots, cmds = [], []
    monkeypatch.setattr(M.R, "screenshot",
                        lambda *a, **k: shots.append((a, k)))
    monkeypatch.setattr(M, "run", cmds.append)
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(spec_path)])
    return types.SimpleNamespace(build=build, shots=shots, cmds=cmds, spec=spec,
                                 spec_path=spec_path, assets=assets,
                                 work=build / "short")


def _media_cmds(stub):
    """The per-scene encodes, i.e. everything before the end card and the concat."""
    return [c for c in stub.cmds
            if "-filter_complex" in c and not any("anullsrc" in tok for tok in c)]


# --- the layers -------------------------------------------------------------------------

def test_media_branch_screenshots_the_overlay_and_the_credit_transparently(stub_main):
    M.main()
    work = stub_main.work
    shot_pngs = [a[1] for a, _k in stub_main.shots]
    assert work / "overlay_0.png" in shot_pngs
    assert work / "credit_0.png" in shot_pngs
    assert work / "credit_1.png" in shot_pngs
    assert work / "overlay_1.png" not in shot_pngs      # scene 1 carries no overlay
    for args, kwargs in stub_main.shots:
        if "overlay_" in str(args[1]) or "credit_" in str(args[1]):
            assert args[2:] == (M.RW, M.RH) == (1296, 2304)
            assert kwargs["transparent"] is True


def test_media_branch_writes_the_html_the_layer_helpers_produced(stub_main):
    M.main()
    work = stub_main.work
    tokens = cards.brand_tokens(BRAND)
    assert (work / "overlay_0.html").read_text(encoding="utf-8") == \
        media.overlay_html(OVERLAY, tokens, M.RW, M.RH)
    assert (work / "credit_0.html").read_text(encoding="utf-8") == \
        media.credit_plate_html(CREDIT, tokens, M.RW, M.RH)


def _layer_overlays(chain):
    """The overlay steps that composite a LAYER PNG — i.e. the ones reading an ffmpeg input.

    The blur fill overlays too, but it overlays one branch of the source onto another, never
    an input stream, so `[2:v]`/`[3:v]` is what tells the two apart.
    """
    return [s for s in chain.split(";") if "overlay=" in s and re.search(r"\[\d+:v\]", s)]


def test_the_layers_are_full_frame_pngs_so_the_geometry_lives_in_one_place(stub_main):
    """Laid over the footage at 0,0 — nothing in ffmpeg re-decides where a plate sits."""
    M.main()
    for cmd in _media_cmds(stub_main):
        chain = cmd[cmd.index("-filter_complex") + 1]
        steps = _layer_overlays(chain)
        assert steps
        for step in steps:
            assert "overlay=x=0:y=0" in step


# --- the encode -------------------------------------------------------------------------

def test_media_branch_encodes_each_scene_against_its_narrated_wav(stub_main):
    M.main()
    cmds = _media_cmds(stub_main)
    assert len(cmds) == 2
    for k, idx in enumerate(stub_main.spec["short"]["scenes"]):
        wav = stub_main.build / "audio" / f"scene_{idx:02d}.wav"
        dur = DURATIONS[str(idx)] + M.SCENE_PAD
        assert str(wav) in cmds[k]
        assert cmds[k][cmds[k].index("-t") + 1] == f"{dur:.3f}"
        assert str(stub_main.work / f"scene_{k}.mp4") == cmds[k][-1]


def test_the_encode_flags_match_the_card_and_sheet_scenes_so_concat_still_works(stub_main):
    """Every part of a Short is concatenated with -c:v copy: the streams must match."""
    M.main()
    for k, cmd in enumerate(_media_cmds(stub_main)):
        for flag, value in (("-c:v", "libx264"), ("-preset", "medium"),
                            ("-r", "30"), ("-c:a", "aac"), ("-b:a", "128k"),
                            ("-crf", "26"), ("-color_range", "tv"),
                            ("-bsf:v", "h264_metadata=video_full_range_flag=0")):
            assert cmd[cmd.index(flag) + 1] == value
        dur = DURATIONS[str(k)] + M.SCENE_PAD
        chain = cmd[cmd.index("-filter_complex") + 1]
        assert f"scale={M.OUT_W}:{M.OUT_H}" in chain
        assert "format=yuv420p" in chain
        assert M.fade_steps(dur, "fade") in chain
        assert "apad=pad_dur=2" in chain
        assert "aformat=sample_rates=48000:channel_layouts=stereo" in chain


def test_the_media_file_is_the_first_input_and_the_wav_the_second(stub_main):
    M.main()
    cmd = _media_cmds(stub_main)[0]
    inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
    assert inputs[0] == str((stub_main.assets / "still.png").resolve())
    assert inputs[1] == str(stub_main.build / "audio" / "scene_00.wav")
    assert inputs[2:] == [str(stub_main.work / "overlay_0.png"),
                          str(stub_main.work / "credit_0.png")]
    chain = cmd[cmd.index("-filter_complex") + 1]
    assert chain.startswith("[0:v]")
    assert "[1:a]" in chain


def test_a_clip_scene_loops_its_source_at_the_input_not_in_the_filter_graph(stub_main):
    M.main()
    clip = _media_cmds(stub_main)[1]
    stream_loop = clip.index("-stream_loop")
    assert clip[stream_loop:stream_loop + 2] == list(media.CLIP_INPUT_ARGS)
    assert stream_loop < clip.index("-i")        # applies to the media input
    assert "-stream_loop" not in _media_cmds(stub_main)[0]


def test_each_scene_uses_the_filter_chain_its_motion_names(stub_main):
    M.main()
    cmds = _media_cmds(stub_main)
    for k, motion in enumerate(("kenburns", "clip")):
        dur = DURATIONS[str(k)] + M.SCENE_PAD
        chain = cmds[k][cmds[k].index("-filter_complex") + 1]
        assert media.ffmpeg_video_filter(motion, dur, M.RW, M.RH) in chain


# --- how the source fills the frame -------------------------------------------------------
#
# A 16:9 source cropped to 9:16 keeps under a third of its width, so whatever the photograph
# was of, the Short shows whatever sat in the middle column. Above media.BLUR_FILL_RATIO the
# whole picture is kept, over a blurred copy of itself.

def test_the_scene_probes_its_source_so_the_fill_can_branch_on_its_shape(stub_main,
                                                                        monkeypatch):
    probed = []
    monkeypatch.setattr(M, "probe_size", lambda p: probed.append(pathlib.Path(p).name) or None)
    M.main()
    assert probed == ["still.png", "clip.mp4"]


def test_a_landscape_source_is_blur_filled_instead_of_cropped(stub_main, monkeypatch):
    monkeypatch.setattr(M, "probe_size", lambda p: (1920, 1080))
    M.main()
    for k, motion in enumerate(("kenburns", "clip")):
        cmd = _media_cmds(stub_main)[k]
        chain = cmd[cmd.index("-filter_complex") + 1]
        dur = DURATIONS[str(k)] + M.SCENE_PAD
        for step in media.ffmpeg_video_steps(motion, dur, M.RW, M.RH, M.FPS, 1920, 1080):
            assert step in chain


def test_a_portrait_source_is_cropped_exactly_as_it_always_was(stub_main, monkeypatch):
    monkeypatch.setattr(M, "probe_size", lambda p: (1080, 1920))
    M.main()
    chain = _media_cmds(stub_main)[0][_media_cmds(stub_main)[0].index("-filter_complex") + 1]
    assert "boxblur" not in chain
    assert chain.startswith(f"[0:v]{media.cover_chain(M.RW, M.RH)}")


def test_a_source_ffprobe_cannot_measure_keeps_the_crop(stub_main):
    """The stubbed ffprobe answers nothing, which is the "unknown size" case."""
    M.main()
    for cmd in _media_cmds(stub_main):
        assert "boxblur" not in cmd[cmd.index("-filter_complex") + 1]


def test_the_layers_still_land_at_zero_zero_over_a_blur_filled_scene(stub_main, monkeypatch):
    """The card, the credit and the caption band must not move because the fill changed."""
    monkeypatch.setattr(M, "probe_size", lambda p: (1920, 1080))
    M.main()
    for cmd in _media_cmds(stub_main):
        steps = _layer_overlays(cmd[cmd.index("-filter_complex") + 1])
        assert steps
        for step in steps:
            assert "overlay=x=0:y=0" in step


def test_probe_size_reads_the_first_video_streams_dimensions(monkeypatch):
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout="1920x1080\n")))
    assert M.probe_size("/tmp/x.mp4") == (1920, 1080)


@pytest.mark.parametrize("stdout", ["", "\n", "N/Ax1080\n", "0x0\n", "1920\n"])
def test_probe_size_answers_none_rather_than_guessing(monkeypatch, stdout):
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout=stdout)))
    assert M.probe_size("/tmp/x.mp4") is None


# --- the pad at every join ------------------------------------------------------------------

def test_the_scene_pad_and_narrates_lead_in_fit_inside_the_join_budget():
    """The silence a viewer hears at a cut is this scene's pad plus the next one's lead-in."""
    import narrate
    assert M.SCENE_PAD + narrate.LEAD_IN_S <= 0.6
    assert M.SCENE_PAD > 0, "some pad has to survive, or the last word is cut off"


def test_every_scene_kind_reads_the_same_pad_helper(stub_main):
    """Media, card and legacy sheet scenes all take `pad` from scene_pad() — one place."""
    src = pathlib.Path(M.__file__).read_text(encoding="utf-8")
    assert src.count("dur = adur + pad") == 3
    assert "dur = adur + SCENE_PAD" not in src
    assert "dur = adur + 0.6" not in src


def test_a_scene_with_neither_overlay_nor_credit_encodes_the_footage_alone(stub_main,
                                                                          monkeypatch):
    stub_main.spec["scenes"][1].pop("credit")
    M.main()
    clip = _media_cmds(stub_main)[1]
    assert clip.count("-i") == 2                 # footage + wav, no layer PNGs
    chain = clip[clip.index("-filter_complex") + 1]
    assert "overlay=" not in chain


def test_the_motion_defaults_to_kenburns_for_a_still_and_clip_for_footage(stub_main):
    stub_main.spec["scenes"][0].pop("motion")
    stub_main.spec["scenes"][1].pop("motion")
    M.main()
    cmds = _media_cmds(stub_main)
    assert "zoompan" in cmds[0][cmds[0].index("-filter_complex") + 1]
    assert "-stream_loop" in cmds[1]


# --- refusals -----------------------------------------------------------------------------

def test_a_still_with_no_credit_is_refused_before_anything_is_encoded(stub_main):
    stub_main.spec["scenes"][0].pop("credit")
    with pytest.raises(ValueError) as e:
        M.main()
    assert "credit" in str(e.value)
    assert not _media_cmds(stub_main)


def test_a_missing_src_names_the_file_it_looked_for(stub_main):
    stub_main.spec["scenes"][0]["src"] = "assets/gone.png"
    with pytest.raises(FileNotFoundError) as e:
        M.main()
    assert "assets/gone.png" in str(e.value)


# --- the rest of the pipeline is untouched ------------------------------------------------

def test_a_media_only_short_needs_no_frames_or_focus_json(stub_main):
    M.main()
    assert not (stub_main.build / "frames").exists()


def test_a_media_only_short_concatenates_into_the_slugs_final_mp4(stub_main):
    M.main()
    final = stub_main.build / "media-demo-short.mp4"
    concat = [c for c in stub_main.cmds if "concat" in c]
    assert len(concat) == 1 and str(final) in concat[0]
    listed = (stub_main.work / "concat.txt").read_text().splitlines()
    assert listed == [f"file '{stub_main.work / n}'"
                      for n in ("scene_0.mp4", "scene_1.mp4", "end.mp4")]


def test_every_media_scene_is_pinned_to_limited_range_like_every_other_scene(stub_main):
    """A JPEG is full-range; a card PNG encodes limited. Parts are concatenated with
    `-c:v copy`, so a media scene that kept its source's range would put a brightness jump
    at the cut — and leave the Short's own range depending on which scene happened to be
    first."""
    M.main()
    for cmd in _media_cmds(stub_main):
        chain = cmd[cmd.index("-filter_complex") + 1]
        assert f"scale={M.OUT_W}:{M.OUT_H}:flags=lanczos:out_range=tv" in chain


# --- motion vs kind, at the pipeline level ------------------------------------------------

def test_an_image_with_motion_clip_is_refused_before_any_ffmpeg_runs(stub_main):
    """It hangs ffmpeg forever — 0 bytes out, still spinning at two minutes — so the only
    safe place to catch it is before the encode starts."""
    stub_main.spec["scenes"][0]["motion"] = "clip"
    with pytest.raises(ValueError) as e:
        M.main()
    assert "clip" in str(e.value) and "image" in str(e.value)
    assert not stub_main.cmds, "no ffmpeg command may be built for a wedging combination"
    assert not stub_main.shots, "no Chrome screenshot either"


def test_a_video_with_motion_kenburns_is_refused_before_any_ffmpeg_runs(stub_main):
    """It would silently encode a freeze frame, which no one notices until the Short ships.

    Scene 1, not scene 0: the preflight has to reject it before scene 0 is rendered, or the
    typo costs a narration, two screenshots and an encode before anyone hears about it.
    """
    stub_main.spec["scenes"][1]["motion"] = "kenburns"
    with pytest.raises(ValueError) as e:
        M.main()
    assert "kenburns" in str(e.value) and "video" in str(e.value)
    assert "scene 1" in str(e.value)
    assert not stub_main.cmds and not stub_main.shots


def test_an_unknown_motion_on_a_later_scene_stops_the_run_before_the_first_one(stub_main):
    """The unknown-motion error used to fire inside encode_media_scene — after Chrome, after
    narration, after every earlier scene had already been encoded."""
    stub_main.spec["scenes"][1]["motion"] = "wiggle"
    with pytest.raises(ValueError) as e:
        M.main()
    assert "wiggle" in str(e.value) and "scene 1" in str(e.value)
    assert not stub_main.cmds, "nothing may be encoded before the spec is known to be valid"
    assert not stub_main.shots, "and nothing may be screenshotted either"


def test_a_missing_src_on_a_later_scene_also_stops_the_run_first(stub_main):
    stub_main.spec["scenes"][1]["src"] = "assets/gone.mp4"
    with pytest.raises(FileNotFoundError) as e:
        M.main()
    assert "scene 1" in str(e.value)
    assert not stub_main.cmds and not stub_main.shots


def test_the_preflight_runs_even_when_the_short_selects_no_media_scene(stub_main):
    """A broken scene the current variant skips is still broken for the next one."""
    stub_main.spec["scenes"][1]["motion"] = "wiggle"
    stub_main.spec["short"]["scenes"] = [0]
    with pytest.raises(ValueError):
        M.main()


def test_run_bounds_every_ffmpeg_call_with_a_timeout(monkeypatch):
    """A wedged ffmpeg must become an error, not a job that never returns."""
    seen = {}

    def fake(cmd, **kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(M.subprocess, "run", fake)
    M.run(["ffmpeg", "-version"])
    assert seen.get("timeout") == M.RUN_TIMEOUT
    assert M.RUN_TIMEOUT >= 600


def test_a_wedged_ffmpeg_is_reported_as_a_failure_not_a_hang(monkeypatch):
    import subprocess as sp

    def fake(cmd, **kwargs):
        raise sp.TimeoutExpired(cmd, kwargs.get("timeout", 0))

    monkeypatch.setattr(M.subprocess, "run", fake)
    with pytest.raises(SystemExit) as e:
        M.run(["ffmpeg", "-i", "x"])
    assert "timed out" in str(e.value)


# --- transitions -------------------------------------------------------------------------

def test_the_default_join_still_emits_the_two_point_three_second_fades(stub_main):
    """Golden guard: a spec with no `transitions:` block renders exactly what it rendered."""
    M.main()
    for cmd in _media_cmds(stub_main):
        chain = cmd[cmd.index("-filter_complex") + 1]
        assert "fade=t=in:st=0:d=0.3" in chain
        assert "fade=t=out:" in chain


def test_join_cut_leaves_no_fade_filter_in_any_scene_chain(stub_main):
    stub_main.spec["transitions"] = {"join": "cut"}
    M.main()
    cmds = _media_cmds(stub_main)
    assert cmds
    for cmd in cmds:
        chain = cmd[cmd.index("-filter_complex") + 1]
        # The AUDIO ramp is `afade=`, which CONTAINS `fade=` — strip it first, so this is a
        # statement about the video fades and cannot be satisfied by dropping the audio one.
        assert "fade=t=" not in chain.replace("afade=t=", "")
        assert "format=yuv420p" in chain
        assert "afade=t=in:d=0.05" in chain    # the audio ramp is not a video fade


def test_fade_steps_is_the_only_place_the_fade_string_is_built():
    assert M.fade_steps(4.0, "cut") == ""
    assert M.fade_steps(4.0, "fade") == "fade=t=in:st=0:d=0.3,fade=t=out:st=3.700:d=0.3,"
    assert M.fade_steps(0.2, "fade") == "fade=t=in:st=0:d=0.3,fade=t=out:st=0.000:d=0.3,"


def test_an_unknown_join_is_refused_by_name():
    with pytest.raises(SystemExit) as excinfo:
        M.transitions({"transitions": {"join": "dissolve"}})
    assert "dissolve" in str(excinfo.value)
    assert "cut" in str(excinfo.value)


def test_xfade_is_a_known_value_that_refuses_until_the_single_pass_join_lands():
    """`xfade` cannot run over a concat demuxer, and that rewrite is not in this change."""
    with pytest.raises(SystemExit) as excinfo:
        M.transitions({"transitions": {"join": "xfade"}})
    assert "xfade" in str(excinfo.value)


def test_xfade_offsets_leave_the_final_part_whole():
    """L_k = sum(d_0..d_k) - k*T; the k-th join's offset is L_{k-1} - T."""
    offsets = M.xfade_offsets([3.067, 2.733, 3.300, 4.079], 0.12)
    assert offsets == pytest.approx([2.9470, 5.5600, 8.7400], abs=1e-3)


def test_the_scene_pad_is_spec_settable_and_defaults_to_the_constant():
    assert M.scene_pad({}) == M.SCENE_PAD
    assert M.scene_pad({"scene_pad": 0.10}) == pytest.approx(0.10)


def test_a_nonsense_scene_pad_is_refused_rather_than_clipping_the_last_word():
    with pytest.raises(SystemExit):
        M.scene_pad({"scene_pad": 0.0})
    with pytest.raises(SystemExit):
        M.scene_pad({"scene_pad": 3.0})


def test_the_spec_scene_pad_reaches_every_scenes_encode(stub_main):
    stub_main.spec["short"]["scene_pad"] = 0.10
    M.main()
    cmds = _media_cmds(stub_main)
    for k, idx in enumerate(stub_main.spec["short"]["scenes"]):
        dur = DURATIONS[str(idx)] + 0.10
        assert cmds[k][cmds[k].index("-t") + 1] == f"{dur:.3f}"


def test_a_bad_transitions_or_pad_is_refused_before_a_single_frame_is_rendered(stub_main):
    """Same rule as the media preflight: a typo costs nothing, not six encoded scenes."""
    stub_main.spec["transitions"] = {"join": "dissolve"}
    with pytest.raises(SystemExit):
        M.main()
    assert not stub_main.cmds and not stub_main.shots
    stub_main.spec.pop("transitions")
    stub_main.spec["short"]["scene_pad"] = 0.0
    with pytest.raises(SystemExit):
        M.main()
    assert not stub_main.cmds and not stub_main.shots


def test_the_scenes_fill_and_focus_reach_its_encode(stub_main, monkeypatch):
    """A 16:9 source, which the ratio alone would blur-fill — so `boxblur not in chain` is a
    statement about `fill: crop` arriving, not about ffprobe having answered nothing."""
    monkeypatch.setattr(M, "probe_size", lambda p: (1920, 1080))
    stub_main.spec["scenes"][0]["fill"] = "crop"
    stub_main.spec["scenes"][0]["focus"] = [0.50, 0.42]
    M.main()
    chain = _media_cmds(stub_main)[0][
        _media_cmds(stub_main)[0].index("-filter_complex") + 1]
    assert "crop=1296:2304:x=(iw-1296)*0.500:y=(ih-2304)*0.420" in chain
    assert "boxblur" not in chain


# --- beats -------------------------------------------------------------------------------

BEATS = [
    {"src": "assets/still.png", "seconds": 1.5, "motion": "punch",
     "crop": {"zoom": 1.00, "fx": 0.50, "fy": 0.50}},
    {"src": "assets/still.png", "seconds": 1.5, "motion": "push",
     "crop": {"zoom": 1.30, "fx": 0.28, "fy": 0.32}},
    {"src": "assets/still.png", "seconds": 1.0, "motion": "pan_right",
     "crop": {"zoom": 1.45, "fx": 0.62, "fy": 0.70}},
]

#: What scene 0's beats are actually rescaled to: its narration plus the scene pad.
BEAT_DUR = DURATIONS["0"] + M.SCENE_PAD


def _beaten(stub_main):
    stub_main.spec["scenes"][0]["beats"] = [dict(beat) for beat in BEATS]
    M.main()
    return _media_cmds(stub_main)[0]


def test_a_scene_with_beats_concatenates_them_against_one_wav(stub_main):
    cmd = _beaten(stub_main)
    chain = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=3:v=1:a=0[m0]" in chain
    assert "[b0][b1][b2]concat=" in chain
    inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
    assert inputs[:3] == [str((stub_main.assets / "still.png").resolve())] * 3
    assert inputs[3] == str(stub_main.build / "audio" / "scene_00.wav")
    assert chain.count("[3:a]") == 1, "one WAV, mapped exactly as a scene without beats"


def test_each_beat_trims_and_resets_pts_so_concat_does_not_overrun(stub_main):
    """Without this, concat inherits zoompan's d= frame count and the beats overrun."""
    cmd = _beaten(stub_main)
    chain = cmd[cmd.index("-filter_complex") + 1]
    for index, span in enumerate(M.beat_spans(BEATS, BEAT_DUR)):
        assert f"trim=duration={span:.3f},setpts=PTS-STARTPTS[b{index}]" in chain


def test_every_beat_chain_ends_at_the_render_size_so_concat_accepts_them(stub_main):
    chain = _beaten(stub_main)[_beaten(stub_main).index("-filter_complex") + 1]
    for step in chain.split(";"):
        if step.endswith(("[b0]", "[b1]", "[b2]")):
            assert f"scale={M.RW}:{M.RH}" in step or f"crop={M.RW}:{M.RH}" in step


def test_the_layers_sit_after_the_beats_and_the_wav_in_the_input_list(stub_main):
    cmd = _beaten(stub_main)
    inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
    assert inputs[4:] == [str(stub_main.work / "overlay_0.png"),
                          str(stub_main.work / "credit_0.png")]
    chain = cmd[cmd.index("-filter_complex") + 1]
    assert "[m0][4:v]overlay=x=0:y=0" in chain


def test_the_beats_are_rescaled_to_the_scenes_real_duration(stub_main):
    """ParkSheet estimates the seconds from the word count before narrate.py has run, so
    the renderer -- which knows the encoded length -- is what makes them add up."""
    assert M.beat_spans(BEATS, 8.0) == pytest.approx([3.0, 3.0, 2.0], abs=1e-3)
    assert sum(M.beat_spans(BEATS, 8.0)) == pytest.approx(8.0, abs=1e-3)
    assert sum(M.beat_spans(BEATS, 4.25)) == pytest.approx(4.25, abs=1e-3)


def test_a_scene_with_no_beats_builds_the_graph_it_always_built(stub_main):
    """Golden guard: one input, one motion chain, layers at 2 and 3."""
    M.main()
    cmd = _media_cmds(stub_main)[0]
    chain = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=" not in chain
    assert chain.startswith("[0:v]")
    assert "[1:a]" in chain


def test_a_single_beat_is_refused_because_it_is_just_the_scene(stub_main):
    stub_main.spec["scenes"][0]["beats"] = [dict(BEATS[0])]
    with pytest.raises(SystemExit) as excinfo:
        M.main()
    assert "beats" in str(excinfo.value)


def test_a_beat_with_no_source_is_refused_by_name(stub_main):
    stub_main.spec["scenes"][0]["beats"] = [{"seconds": 1.0, "motion": "punch"},
                                            dict(BEATS[1])]
    with pytest.raises(SystemExit) as excinfo:
        M.main()
    assert "src" in str(excinfo.value)


def test_more_beats_than_the_backstop_allows_is_refused(stub_main):
    stub_main.spec["scenes"][0]["beats"] = [
        {**BEATS[0], "seconds": M.MAX_PICTURE_S + 1.0}, dict(BEATS[1])]
    with pytest.raises(SystemExit) as excinfo:
        M.main()
    assert str(M.MAX_PICTURE_S) in str(excinfo.value)


def _beat_chain(chain, index):
    """The one step of `chain` that ends at `[b<index>]` — that beat's whole sub-shot."""
    return next(s for s in chain.split(";") if s.endswith(f"[b{index}]"))


def test_a_beats_motion_is_preflighted_against_its_own_source_kind(stub_main):
    """A beat carries its own src, so `punch` on an .mp4 freezes THAT beat, not the scene."""
    stub_main.spec["scenes"][0]["beats"] = [
        {"src": "assets/clip.mp4", "seconds": 1.5, "motion": "punch"}, dict(BEATS[1])]
    with pytest.raises(ValueError) as excinfo:
        M.main()
    assert "punch" in str(excinfo.value) and "video" in str(excinfo.value)
    assert "scene 0" in str(excinfo.value) and "beats[0]" in str(excinfo.value)
    assert not stub_main.cmds and not stub_main.shots


def test_a_beats_missing_source_is_named_at_preflight(stub_main):
    stub_main.spec["scenes"][0]["beats"] = [{**BEATS[0], "src": "assets/gone.png"},
                                            dict(BEATS[1])]
    with pytest.raises(FileNotFoundError) as excinfo:
        M.main()
    assert "assets/gone.png" in str(excinfo.value) and "scene 0" in str(excinfo.value)
    assert not stub_main.cmds and not stub_main.shots


@pytest.mark.parametrize("crop, word", [({"zoom": 0.8}, "zoom"),
                                        ({"zoom": 1.2, "fx": 1.4}, "fx")])
def test_a_beat_crop_outside_the_picture_is_refused_by_name(stub_main, crop, word):
    """crop_chain refuses these; the preflight is where a spec hears about it."""
    stub_main.spec["scenes"][0]["beats"] = [{**BEATS[0], "crop": crop}, dict(BEATS[1])]
    with pytest.raises(ValueError) as excinfo:
        M.main()
    assert word in str(excinfo.value) and "beats[0]" in str(excinfo.value)
    assert not stub_main.cmds and not stub_main.shots


def test_beats_on_a_scene_the_render_has_not_reached_yet_stop_it_first(stub_main):
    """Same rule as every other media key: a typo costs nothing, not an encoded scene 0."""
    stub_main.spec["scenes"][1]["beats"] = [dict(BEATS[0])]
    with pytest.raises(SystemExit):
        M.main()
    assert not stub_main.cmds and not stub_main.shots


def test_a_beat_with_no_motion_takes_its_own_sources_default(stub_main):
    """`punch` is not a safe blanket default: it freezes footage. default_motion() knows."""
    stub_main.spec["scenes"][0]["beats"] = [
        {"src": "assets/still.png", "seconds": 1.5},
        {"src": "assets/clip.mp4", "seconds": 1.5}]
    M.main()
    cmd = _media_cmds(stub_main)[0]
    chain = cmd[cmd.index("-filter_complex") + 1]
    assert "zoompan" in _beat_chain(chain, 0)                    # kenburns, the still default
    assert "zoompan" not in _beat_chain(chain, 1)                # clip, the footage default
    assert "-stream_loop" in cmd                                 # which only `clip` asks for


def test_only_a_clip_beat_loops_its_source_at_the_input(stub_main):
    """Exactly the rule a scene without beats follows: `hold` on footage plays it through
    and then freezes the last frame, which -stream_loop would turn into a replay."""
    stub_main.spec["scenes"][0]["beats"] = [
        {"src": "assets/clip.mp4", "seconds": 1.5, "motion": "hold"},
        {"src": "assets/clip.mp4", "seconds": 1.5, "motion": "clip"}]
    M.main()
    cmd = _media_cmds(stub_main)[0]
    assert cmd.count("-stream_loop") == 1
    assert cmd[cmd.index("-stream_loop") + 2:cmd.index("-stream_loop") + 4] == \
        ["-i", str((stub_main.assets / "clip.mp4").resolve())]
    assert cmd.index("-stream_loop") > cmd.index("-i")           # the SECOND beat's input


def test_a_hold_beat_on_footage_is_not_reframed(stub_main):
    """`hold` is the one motion both kinds share, and footage is never re-framed: a clip
    beat is the shot the clip already is. Only the still's crop survives."""
    stub_main.spec["scenes"][0]["beats"] = [
        {"src": "assets/clip.mp4", "seconds": 1.5, "motion": "hold",
         "crop": {"zoom": 1.30, "fx": 0.28, "fy": 0.32}},
        dict(BEATS[1])]
    M.main()
    cmd = _media_cmds(stub_main)[0]
    chain = cmd[cmd.index("-filter_complex") + 1]
    assert "crop=iw/" not in _beat_chain(chain, 0)
    assert "crop=iw/1.300" in _beat_chain(chain, 1)


def test_the_beats_reach_ffmpeg_through_the_one_chain_builder(stub_main):
    """Every beat is media.ffmpeg_video_steps' output, so the crop, the 2x pre-scale and the
    blur fill behave for a beat exactly as they do for a whole scene."""
    cmd = _beaten(stub_main)
    chain = cmd[cmd.index("-filter_complex") + 1]
    spans = M.beat_spans(BEATS, BEAT_DUR)
    for index, (beat, span) in enumerate(zip(BEATS, spans)):
        built = media.ffmpeg_video_steps(beat["motion"], span, M.RW, M.RH, M.FPS,
                                         src_label=f"{index}:v", out_label=f"b{index}",
                                         crop=beat["crop"])
        assert built[-1].removesuffix(f"[b{index}]") in _beat_chain(chain, index)


def test_beat_spans_of_nothing_is_nothing(stub_main):
    """Task 11's cut list calls this for every scene, beats or not."""
    assert M.beat_spans([], 4.0) == []
    assert M.scene_beats({}) == [] and M.scene_beats({"kind": "media"}) == []


def test_every_beat_is_normalised_so_concat_can_join_unlike_sources(stub_main):
    """Measured, not defensive: the demo JPEG decodes yuvj444p and the demo clip yuv420p,
    and concat of those two is `Error reinitializing filters!`, exit 234, no output file.
    concat wants identical size, PIXEL FORMAT and SAR, and a beats scene is the first thing
    this renderer builds that puts two different sources into one graph."""
    stub_main.spec["scenes"][0]["beats"] = [dict(BEATS[0]),
                                            {"src": "assets/clip.mp4", "seconds": 1.5,
                                             "motion": "clip"}]
    M.main()
    cmd = _media_cmds(stub_main)[0]
    chain = cmd[cmd.index("-filter_complex") + 1]
    for index in range(2):
        span = M.beat_spans(stub_main.spec["scenes"][0]["beats"], BEAT_DUR)[index]
        assert _beat_chain(chain, index).endswith(
            f"format=yuv420p,setsar=1,trim=duration={span:.3f},setpts=PTS-STARTPTS[b{index}]")
        assert _beat_chain(chain, index).count("trim=duration=") == 1
