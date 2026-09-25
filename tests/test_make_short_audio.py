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
    """One cut at 0.1 s is the nearest to BOTH divisions of a 9 s runtime, so the only
    boundary is 0.1 and the lead of 0.20 puts the whoosh at -0.1 s. adelay refuses a
    negative delay, so the clamp is the difference between a render and an ffmpeg error."""
    graph = ";".join(_steps(runtime=9.0, cuts=(0.1,)))
    assert "adelay=0|0" in graph
    assert "adelay=-" not in graph


def test_each_whoosh_is_made_stereo_before_it_is_delayed():
    """adelay takes one delay PER CHANNEL: `adelay=2747|2747` on a MONO whoosh delays the one
    channel it has and drops the second value, so the SFX lands early against a stereo bed."""
    graph = ";".join(_steps())
    for step in graph.split(";"):
        if "adelay=" in step:
            assert step.index("aformat=sample_rates=48000:channel_layouts=stereo") \
                < step.index("adelay="), step


def test_the_music_bus_cannot_outlast_the_picture():
    """amix ends with its LONGEST input. A 1.33 s whoosh delayed to the last boundary of a
    short runtime would run past the last frame and pad the file with music over nothing."""
    graph = ";".join(_steps(runtime=45.29))
    for step in graph.split(";"):
        if "adelay=" in step:
            assert "atrim=0:45.290" in step, step
            assert "apad=whole_dur=45.290" in step, step


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


def test_a_positive_bed_lufs_is_refused_because_ebur128_reports_negative_lufs(tmp_path):
    """`lufs: 13.2` for a -13.2 LUFS asset is one keystroke, and it is SILENT: the gain
    becomes -35.2 dB, the render returns 0, and the Short ships with an inaudible bed."""
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings(_mix(bed={"src": BED["src"], "lufs": 13.2}), tmp_path / "scenes.yaml")
    assert "13.2" in str(excinfo.value)
    assert "negative" in str(excinfo.value).lower()


def test_a_bed_gain_beyond_thirty_db_is_refused_and_names_both_numbers(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings(_mix(bed={"src": BED["src"], "lufs": -60.0, "target_lufs": -22}),
                         tmp_path / "scenes.yaml")
    message = str(excinfo.value)
    assert "38" in message, "the gain it would have applied"
    assert "30" in message, "the limit it broke"


def test_a_bed_gain_of_exactly_thirty_db_is_allowed(tmp_path):
    """The bound is a sanity check on a typo, not an opinion about quiet assets."""
    (tmp_path / "media" / "audio").mkdir(parents=True)
    (tmp_path / "media" / "audio" / "bed.mp3").write_bytes(b"\0")
    mix = M.audio_settings({"audio": {"bed": {"src": BED["src"], "lufs": -52.0,
                                              "target_lufs": -22}}},
                           tmp_path / "scenes.yaml")
    assert M.bed_gain_db(mix.bed.target_lufs, mix.bed.lufs) == pytest.approx(30.0)


def test_a_duck_or_master_block_with_no_bed_is_refused_by_name(tmp_path):
    """Both only mean something against a bed. Accepted and ignored, they read as applied."""
    for key in ("duck", "master"):
        with pytest.raises(SystemExit) as excinfo:
            M.audio_settings({"audio": {key: {}}}, tmp_path / "scenes.yaml")
        assert key in str(excinfo.value)


def test_fewer_than_two_beats_places_no_whoosh_and_is_refused(tmp_path):
    (tmp_path / "media" / "audio").mkdir(parents=True)
    for name in ("bed.mp3", "whoosh.wav"):
        (tmp_path / "media" / "audio" / name).write_bytes(b"\0")
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings(_mix(sfx={**SFX, "beats": 1}), tmp_path / "scenes.yaml")
    assert "beats" in str(excinfo.value)


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


# --- cues: a riser into the payoff, a hit on it -----------------------------------------

CUES = [{"role": "riser", "src": "media/audio/riser.wav", "on": "payoff",
         "lead": 1.5, "gain_db": -12},
        {"role": "hit", "src": "media/audio/hit.wav", "on": "payoff", "gain_db": -8}]


def test_the_default_sfx_gain_is_minus_nine_not_minus_six():
    """Measured (sound-design section 2.4): the whoosh is -13.0 LUFS and lands near -19 at
    -6 dB, about 2 LU under the voice's -17.1 -- not the 12-18 dB of creator lore. With
    more than one cue on the bus, -9 is the safer floor."""
    assert M.Sfx(src="w.wav").gain_db == -9.0
    assert M.SfxCue(role="riser", src="r.wav").gain_db == -9.0


def test_a_cue_is_parsed_off_the_sfx_block(tmp_path, monkeypatch):
    monkeypatch.setattr(M.media, "resolve_src", lambda spec_path, src: f"/abs/{src}")
    spec = {"audio": {"bed": {"src": "b.mp3", "lufs": -13.2},
                      "sfx": {"on_cut": "w.wav", "cues": CUES}}}
    mix = M.audio_settings(spec, tmp_path / "scenes.yaml")
    assert [c.role for c in mix.sfx.cues] == ["riser", "hit"]
    assert mix.sfx.cues[0].lead == 1.5 and mix.sfx.cues[0].gain_db == -12.0
    assert mix.sfx.cues[1].lead == 0.0 and mix.sfx.cues[1].gain_db == -8.0
    assert mix.sfx.cues[0].src == "/abs/media/audio/riser.wav"


@pytest.mark.parametrize("cues,needle", [
    ({"role": "riser"}, "must be a list"),
    ([{"src": "r.wav"}], "needs a `role`"),
    ([{"role": "boom", "src": "r.wav"}], "riser, hit"),
    ([{"role": "riser"}], "no `src`"),
    ([{"role": "riser", "src": "r.wav", "on": "every_cut"}], "payoff"),
    ([{"role": "riser", "src": "r.wav", "lead": -1}], "lead"),
    ([{"role": "riser", "src": "r.wav"}, {"role": "riser", "src": "r2.wav"}], "twice"),
])
def test_a_malformed_cue_stops_the_render_by_name(tmp_path, monkeypatch, cues, needle):
    monkeypatch.setattr(M.media, "resolve_src", lambda spec_path, src: f"/abs/{src}")
    spec = {"audio": {"bed": {"src": "b.mp3", "lufs": -13.2},
                      "sfx": {"on_cut": "w.wav", "cues": cues}}}
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings(spec, tmp_path / "scenes.yaml")
    assert needle in str(excinfo.value)


def test_an_unknown_key_under_sfx_is_still_refused_by_name(tmp_path):
    """GC7: this is why `cues:` needs no capability probe -- an old engine refuses it."""
    spec = {"audio": {"bed": {"src": "b.mp3", "lufs": -13.2},
                      "sfx": {"on_cut": "w.wav", "cuez": []}}}
    with pytest.raises(SystemExit) as excinfo:
        M.audio_settings(spec, "scenes.yaml")
    assert "cuez" in str(excinfo.value)


def _mix_with_cues(**kw):
    return M.AudioMix(
        bed=M.Bed(src="/abs/b.mp3", lufs=-13.2),
        duck=M.Duck(),
        sfx=M.Sfx(src="/abs/w.wav", cues=(
            M.SfxCue(role="riser", src="/abs/r.wav", lead=1.5, gain_db=-12.0),
            M.SfxCue(role="hit", src="/abs/h.wav", lead=0.0, gain_db=-8.0))),
        master=M.Master(), **kw)


def test_a_cue_is_delayed_to_its_lead_before_the_payoff():
    mix = _mix_with_cues()
    graph = ";".join(M.audio_steps(mix, runtime=38.0, cuts=[5.0, 20.0], bed_index=1,
                                   sfx_indexes=[2, 3], cue_indexes=[4, 5],
                                   payoff_s=30.0))
    assert "[4:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-12dB," \
           "adelay=28500|28500," in graph
    assert "volume=-8dB,adelay=30000|30000," in graph


def test_every_cue_joins_the_music_bus_and_the_amix_counts_them_all():
    # 12.0 and 26.0, not 5.0/20.0: beat_boundaries(runtime=38, beats=3) targets ~12.67 and
    # ~25.33, and 5.0/20.0 are both nearest to 20.0 -- one boundary, not two. These two cuts
    # land the beat math on two distinct boundaries so the whoosh count in the comment below
    # is the whoosh count in the graph.
    mix = _mix_with_cues()
    graph = ";".join(M.audio_steps(mix, runtime=38.0, cuts=[12.0, 26.0], bed_index=1,
                                   sfx_indexes=[2, 3], cue_indexes=[4, 5],
                                   payoff_s=30.0))
    # bedduck + 2 whooshes + 2 cues
    assert "amix=inputs=5:normalize=0:dropout_transition=0[music]" in graph


def test_a_cue_is_trimmed_and_padded_to_the_runtime_like_a_whoosh():
    mix = _mix_with_cues()
    graph = ";".join(M.audio_steps(mix, runtime=38.0, cuts=[5.0], bed_index=1,
                                   sfx_indexes=[2], cue_indexes=[3, 4], payoff_s=30.0))
    assert graph.count("atrim=0:38.000,apad=whole_dur=38.000") == 3


def test_no_payoff_means_no_cue_is_placed():
    """A spec with no scene rows has no payoff frame; a cue with nowhere to land is not
    silently dropped onto second zero."""
    mix = _mix_with_cues()
    graph = ";".join(M.audio_steps(mix, runtime=38.0, cuts=[5.0], bed_index=1,
                                   sfx_indexes=[2], cue_indexes=[], payoff_s=None))
    assert "volume=-12dB" not in graph and "volume=-8dB" not in graph


def test_audio_inputs_queues_one_input_per_whoosh_then_one_per_cue():
    mix = _mix_with_cues()
    args, bed_index, sfx_indexes, cue_indexes = M.audio_inputs(mix, [5.0, 20.0], 1)
    assert args == ["-stream_loop", "-1", "-i", "/abs/b.mp3",
                    "-i", "/abs/w.wav", "-i", "/abs/w.wav",
                    "-i", "/abs/r.wav", "-i", "/abs/h.wav"]
    assert (bed_index, sfx_indexes, cue_indexes) == (1, [2, 3], [4, 5])


def test_sfx_placements_are_the_starts_not_the_events_they_key_off():
    mix = _mix_with_cues()
    assert M.sfx_placements(mix, [9.97, 19.01], 30.0) == [
        {"at": 9.77, "role": "whoosh"},
        {"at": 18.81, "role": "whoosh"},
        {"at": 28.5, "role": "riser"},
        {"at": 30.0, "role": "hit"},
    ]


def test_sfx_placements_of_a_render_with_no_sfx_is_an_empty_list():
    mix = M.AudioMix(bed=M.Bed(src="/abs/b.mp3", lufs=-13.2), duck=M.Duck(), sfx=None,
                     master=M.Master())
    assert M.sfx_placements(mix, [], 30.0) == []
    assert M.sfx_placements(None, [], 30.0) == []


def test_cut_plan_json_always_carries_an_sfx_list():
    rows = [{"scene": 0, "start": 0.0, "seconds": 10.0, "beats": [10.0]}]
    assert M.cut_plan_json(rows, "cut", 10.0)["sfx"] == []
    placed = [{"at": 9.77, "role": "whoosh"}]
    assert M.cut_plan_json(rows, "cut", 10.0, sfx=placed)["sfx"] == placed
