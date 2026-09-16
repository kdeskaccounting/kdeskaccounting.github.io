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


def test_the_layers_are_full_frame_pngs_so_the_geometry_lives_in_one_place(stub_main):
    """Laid over the footage at 0,0 — nothing in ffmpeg re-decides where a plate sits."""
    M.main()
    for cmd in _media_cmds(stub_main):
        chain = cmd[cmd.index("-filter_complex") + 1]
        for step in chain.split(";"):
            if "overlay=" in step:
                assert "overlay=x=0:y=0" in step


# --- the encode -------------------------------------------------------------------------

def test_media_branch_encodes_each_scene_against_its_narrated_wav(stub_main):
    M.main()
    cmds = _media_cmds(stub_main)
    assert len(cmds) == 2
    for k, idx in enumerate(stub_main.spec["short"]["scenes"]):
        wav = stub_main.build / "audio" / f"scene_{idx:02d}.wav"
        dur = DURATIONS[str(idx)] + 0.6
        assert str(wav) in cmds[k]
        assert cmds[k][cmds[k].index("-t") + 1] == f"{dur:.3f}"
        assert str(stub_main.work / f"scene_{k}.mp4") == cmds[k][-1]


def test_the_encode_flags_match_the_card_and_sheet_scenes_so_concat_still_works(stub_main):
    """Every part of a Short is concatenated with -c:v copy: the streams must match."""
    M.main()
    for cmd in _media_cmds(stub_main):
        for flag, value in (("-c:v", "libx264"), ("-preset", "medium"),
                            ("-r", "30"), ("-c:a", "aac"), ("-b:a", "128k"),
                            ("-crf", "26")):
            assert cmd[cmd.index(flag) + 1] == value
        chain = cmd[cmd.index("-filter_complex") + 1]
        assert f"scale={M.OUT_W}:{M.OUT_H}" in chain
        assert "format=yuv420p" in chain
        assert "fade=t=in:st=0:d=0.3" in chain
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
        dur = DURATIONS[str(k)] + 0.6
        chain = cmds[k][cmds[k].index("-filter_complex") + 1]
        assert media.ffmpeg_video_filter(motion, dur, M.RW, M.RH) in chain


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


def test_a_video_with_motion_kenburns_is_refused(stub_main):
    """It would silently encode a freeze frame, which no one notices until the Short ships."""
    stub_main.spec["scenes"][1]["motion"] = "kenburns"
    with pytest.raises(ValueError) as e:
        M.main()
    assert "kenburns" in str(e.value) and "video" in str(e.value)


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
