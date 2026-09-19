"""make_short.py's audio mix: a music bed ducked by the voice, with a whoosh on each beat.

There was no audio path of any kind before this — the only audio filters in the renderer
were apad, afade, aformat and the final loudnorm. Every number here was measured on the real
day-3 parts (docs/research/2026-09-19-production-techniques.md section 5), so the tests
assert the mix's SHAPE, which is what a later refactor can quietly break.
"""
import json
import pathlib
import sys
import types

import pytest

import captions
import make_short as M


BED = {"src": "media/audio/bed.mp3", "lufs": -28.9, "target_lufs": -22}
SFX = {"src": "media/audio/whoosh.wav", "gain_db": -6, "lead": 0.20}


def _mix(**over):
    block = {"bed": dict(BED), "sfx": dict(SFX), **over}
    return {"audio": block}


def test_a_spec_with_no_audio_block_emits_the_plain_loudnorm_chain():
    """Golden guard: this is the exact string the renderer has always written."""
    assert M.audio_settings({}, pathlib.Path("/x/scenes.yaml")) is None
    assert M.plain_audio_steps(M.Master()) == "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]"


def test_the_bed_gain_is_the_difference_between_its_measured_lufs_and_the_target():
    assert M.bed_gain_db(-22.0, -28.9) == pytest.approx(6.9, abs=1e-6)
    assert M.bed_gain_db(-22.0, -14.0) == pytest.approx(-8.0, abs=1e-6)


def _steps(runtime=45.29, cuts=(3.07, 5.8, 9.1, 13.18, 20.0, 30.0)):
    mix = M.AudioMix(bed=M.Bed(src="/a/bed.mp3", lufs=-28.9), duck=M.Duck(),
                     sfx=M.Sfx(src="/a/whoosh.wav"), master=M.Master())
    return M.audio_steps(mix, runtime=runtime, cuts=list(cuts), bed_index=1,
                         sfx_indexes=[2, 3])


def test_the_voice_is_split_into_a_stem_and_a_sidechain_key():
    graph = ";".join(_steps())
    assert "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[vox][key]" \
        in graph


def test_the_sidechain_key_is_the_voice_and_the_main_is_the_bed():
    """sidechaincompress is [main][sidechain]; reversed, it ducks the narration."""
    graph = ";".join(_steps())
    assert ("[bed][key]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300:"
            "detection=rms[bedduck]") in graph


def test_the_bed_is_trimmed_to_the_runtime_so_a_looped_input_cannot_run_past_the_video():
    graph = ";".join(_steps(runtime=45.29))
    assert "atrim=0:45.290" in graph
    assert "volume=6.9dB" in graph
    assert "afade=t=in:d=0.6" in graph
    assert "afade=t=out:st=44.090:d=1.2" in graph


def test_every_amix_in_the_graph_disables_normalisation():
    """normalize=1 divides every input by the input count: adding a whoosh would drop the
    voice by 6 dB without anyone touching the voice."""
    graph = ";".join(_steps())
    assert graph.count("amix=") == 2
    assert graph.count("normalize=0") == 2
    assert "dropout_transition=0" in graph


def test_a_whoosh_is_delayed_to_start_one_lead_before_each_beat_boundary():
    graph = ";".join(_steps(runtime=45.29, cuts=(3.0, 8.0, 15.1, 22.0, 30.2, 40.0)))
    # three beats over 45.29 s puts the divisions at 15.10 and 30.19; the nearest cuts are
    # 15.1 and 30.2, and a whoosh starts 0.20 s before each.
    assert "adelay=14900|14900" in graph
    assert "adelay=30000|30000" in graph


def test_the_whooshes_land_on_beats_not_on_every_cut():
    cuts = [round(0.9 * n, 2) for n in range(1, 40)]
    assert len(M.beat_boundaries(cuts, 36.0, beats=3)) == 2
    assert len(M.beat_boundaries(cuts, 36.0, beats=4)) == 3


def test_a_boundary_before_zero_is_clamped_rather_than_negative():
    graph = ";".join(_steps(runtime=9.0, cuts=(0.1, 3.0, 6.0)))
    assert "adelay=-" not in graph


def test_the_limiter_sits_before_the_loudnorm():
    graph = ";".join(_steps())
    assert ("[vox][music]amix=inputs=2:normalize=0,alimiter=limit=0.97,"
            "loudnorm=I=-16:TP=-1.5:LRA=11[aout]") in graph


def test_a_bed_with_no_sfx_still_mixes():
    mix = M.AudioMix(bed=M.Bed(src="/a/bed.mp3", lufs=-28.9), duck=M.Duck(), sfx=None,
                     master=M.Master())
    graph = ";".join(M.audio_steps(mix, runtime=20.0, cuts=[5.0], bed_index=1,
                                   sfx_indexes=[]))
    assert "sidechaincompress" in graph
    assert "adelay" not in graph


def test_a_missing_bed_file_refuses_the_render_and_names_the_url(tmp_path):
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("x")
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings(_mix(), spec_path)
    assert "media/audio/bed.mp3" in str(excinfo.value)
    assert "mixkit" in str(excinfo.value).lower()


def test_a_bed_with_no_measured_lufs_is_refused(tmp_path):
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("x")
    (tmp_path / "media" / "audio").mkdir(parents=True)
    (tmp_path / "media" / "audio" / "bed.mp3").write_bytes(b"\0")
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings({"audio": {"bed": {"src": "media/audio/bed.mp3"}}}, spec_path)
    assert "lufs" in str(excinfo.value)


def test_a_whoosh_with_no_bed_is_refused_rather_than_silently_dropped(tmp_path):
    """The SFX ride the music bus; there is no bed-less path through the graph. A spec that
    asked for whooshes and got the plain loudnorm chain looks exactly like one that asked for
    nothing, which is the failure this whole block exists to make audible."""
    spec_path = tmp_path / "scenes.yaml"
    (tmp_path / "media" / "audio").mkdir(parents=True)
    (tmp_path / "media" / "audio" / "whoosh.wav").write_bytes(b"\0")
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings({"audio": {"sfx": dict(SFX)}}, spec_path)
    assert "bed" in str(excinfo.value)


def test_an_empty_bed_mapping_is_refused_rather_than_read_as_no_bed(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings({"audio": {"bed": {}}}, tmp_path / "scenes.yaml")
    assert "audio.bed" in str(excinfo.value)


def test_an_unknown_audio_key_is_refused_by_name(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings({"audio": {"bedd": {}}}, tmp_path / "scenes.yaml")
    assert "bedd" in str(excinfo.value)


def test_an_unknown_duck_key_is_refused_rather_than_raising_a_typeerror(tmp_path):
    spec_path = tmp_path / "scenes.yaml"
    (tmp_path / "media" / "audio").mkdir(parents=True)
    (tmp_path / "media" / "audio" / "bed.mp3").write_bytes(b"\0")
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings({"audio": {"bed": dict(BED), "duck": {"thresh": 0.03}}}, spec_path)
    assert "thresh" in str(excinfo.value)


# --- wired into the final pass --------------------------------------------------------------
#
# The graph above is only half of it: the bed and every whoosh are extra ffmpeg INPUTS, and
# the caption pass already numbers its own. A bed queued before the caption PNGs would move
# every overlay's index and burn the wrong word onto the wrong frame.

WORDS = {0: [{"text": "Magic", "start": 0.3, "end": 0.8},
             {"text": "Kingdom", "start": 0.9, "end": 1.5}],
         1: [{"text": "Five", "start": 0.3, "end": 0.7}],
         2: [{"text": "Go", "start": 0.3, "end": 0.6}]}
DURATIONS = {"0": 4.0, "1": 5.0, "2": 6.0}
PART_SECONDS = 6.0
END_SECONDS = 1.5
CREDIT = "Imagery: placeholder"


def _spec(audio=None, caps=None):
    spec = {
        "slug": "aud-demo",
        "brand": {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"},
        "short": {"hook": "Three scenes", "scenes": [0, 1, 2], "cta": "More → parksheet.com"},
        "scenes": [
            {"kind": "media", "src": "assets/still.png", "motion": "kenburns",
             "credit": CREDIT, "narration": "one"},
            {"kind": "media", "src": "assets/clip.mp4", "motion": "clip",
             "credit": CREDIT, "narration": "two"},
            {"kind": "media", "src": "assets/clip.mp4", "motion": "hold",
             "credit": CREDIT, "narration": "three"},
        ],
    }
    if audio is not None:
        spec["audio"] = audio
    if caps is not None:
        spec["captions"] = caps
    return spec


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """main() over a mixed spec with ffmpeg, ffprobe and Chrome stubbed (see test_make_short_captions)."""
    holder = types.SimpleNamespace(spec=_spec(_mix()["audio"]))
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
    audio_dir = tmp_path / "media" / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / "bed.mp3").write_bytes(b"\0")
    (audio_dir / "whoosh.wav").write_bytes(b"\0")
    build = tmp_path / "build" / "aud-demo"
    narration = build / "audio"
    narration.mkdir(parents=True)
    (narration / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of",
                        lambda p: END_SECONDS if pathlib.Path(p).name == "end.mp4"
                        else PART_SECONDS)
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    cmds = []
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: None)
    monkeypatch.setattr(M.R, "render_card_scene", lambda *a, **k: None)
    monkeypatch.setattr(M, "run", cmds.append)
    holder.cmds, holder.bed = cmds, str(audio_dir / "bed.mp3")

    def go(*extra):
        for idx, words in WORDS.items():
            captions.write_words(narration / f"scene_{idx:02d}.wav", words)
        monkeypatch.setattr(sys, "argv",
                            ["make_short.py", "--spec", str(spec_path), *extra])
        M.main()

    holder.go = go
    return holder


def _final(stub):
    return [c for c in stub.cmds if "concat" in c][-1]


def _graph(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


def _input_index(cmd, value):
    """Which ffmpeg input `value` is: the number of `-i` flags ahead of its own."""
    at = cmd.index(value)
    return sum(1 for n, arg in enumerate(cmd) if arg == "-i" and n < at) - 1


def test_an_uncaptioned_render_with_a_bed_loops_it_and_keeps_the_video_a_stream_copy(stub):
    stub.go()
    cmd = _final(stub)
    assert cmd[cmd.index(stub.bed) - 3:cmd.index(stub.bed)] == ["-stream_loop", "-1", "-i"]
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-af" not in cmd, "the mix rides the filter graph, not a second -af pass"
    assert cmd[cmd.index("-map") + 1] == "0:v"
    assert "[aout]" in cmd
    assert "sidechaincompress" in _graph(cmd)


def test_the_bed_runs_the_whole_short_including_the_closing_plate(stub):
    """sum(scenes[].seconds) is 18.0 here; the plate makes the Short 19.5. A bed trimmed to
    the row sum would fade out 1.5 s early and leave the plate in silence."""
    stub.go()
    assert "atrim=0:19.500" in _graph(_final(stub))
    assert "afade=t=out:st=18.300:d=1.2" in _graph(_final(stub))


def test_a_captioned_render_queues_the_bed_after_the_caption_pngs(stub):
    """Every caption overlay is an input index. A bed queued first would shift them all."""
    stub.spec = _spec(_mix()["audio"], {"enabled": True})
    stub.go()
    cmd = _final(stub)
    graph = _graph(cmd)
    bed = _input_index(cmd, stub.bed)
    assert bed > 1, "input 0 is the concat and the caption PNGs come before the bed"
    assert f"[{bed}:a]aformat" in graph
    # the last caption overlay still reads the input immediately before the bed
    assert f"[{bed - 1}:v]overlay" in graph
    assert f"[{bed}:v]overlay" not in graph
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "[vout]" in cmd and "[aout]" in cmd


def test_one_whoosh_input_per_beat_boundary_and_no_more(stub):
    stub.go()
    cmd = _final(stub)
    whoosh = [n for n, arg in enumerate(cmd) if arg.endswith("whoosh.wav")]
    assert len(whoosh) == 2, "three beats have two boundaries"
    assert _graph(cmd).count("adelay=") == 2


def test_a_spec_with_no_audio_block_renders_the_pass_it_always_did(stub):
    stub.spec = _spec()
    stub.go()
    cmd = _final(stub)
    assert "-filter_complex" not in cmd
    assert cmd[cmd.index("-af") + 1] == "loudnorm=I=-16:TP=-1.5:LRA=11"
    assert cmd[cmd.index("-c:v") + 1] == "copy"
