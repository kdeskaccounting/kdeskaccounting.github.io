"""`audio.sfx.opening`: the frame-0 whoosh + hit mixed INSIDE the renderer's graph.

It replaces a per-Short `make_opening.py` WAV that was `amix`ed onto the finished master
afterwards. What is tested: the sting's shape in the graph, that it is recorded in cuts.json
(so the gate can see it), that the render refuses a first word inside its guard, that
element sounds are thinned around it, and that the finished Short is 48 kHz.
"""
import json
import pathlib
import sys
import types

import pytest

import captions
import make_short as M

OPENING = {"impact": 0.40, "layers": [
    {"src": "media/audio/whoosh.wav", "at": 0.0, "start": 0.65, "end": 1.08,
     "fade_in": 0.03, "fade_out": 0.04, "fade_out_at": 0.39, "gain_db": -1},
    {"src": "media/audio/hit.wav", "at": 0.40, "gain_db": 1}]}


def _settings(opening, tmp_path, monkeypatch, **sfx):
    monkeypatch.setattr(M.media, "resolve_src", lambda spec_path, src: f"/abs/{src}")
    spec = {"audio": {"bed": {"src": "b.mp3", "lufs": -11.6, "target_lufs": -24},
                      "sfx": {"opening": opening, **sfx}}}
    return M.audio_settings(spec, tmp_path / "scenes.yaml")


def test_an_opening_alone_is_a_complete_sfx_block(tmp_path, monkeypatch):
    mix = _settings(OPENING, tmp_path, monkeypatch)
    sting = mix.sfx.opening
    assert sting.impact == 0.40 and sting.guard == M.OPENING_GUARD_S == 0.10
    assert [layer.src for layer in sting.layers] == ["/abs/media/audio/whoosh.wav",
                                                     "/abs/media/audio/hit.wav"]
    assert mix.sfx.src == ""          # no whoosh-on-cut was asked for


def test_a_spec_without_an_opening_parses_exactly_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(M.media, "resolve_src", lambda spec_path, src: f"/abs/{src}")
    mix = M.audio_settings({"audio": {"bed": {"src": "b.mp3", "lufs": -11.6},
                                      "sfx": {"on_cut": "w.wav"}}}, tmp_path / "s.yaml")
    assert mix.sfx.opening is None
    assert M.opening_placements(mix) == []


@pytest.mark.parametrize("opening,needle", [
    ({"layers": ["a.wav"]}, "needs `impact:`"),
    ({"impact": 0.9, "layers": ["a.wav"]}, "first 0.6s"),
    ({"impact": 0.4, "guard": 0.05, "layers": ["a.wav"]}, "never shorter"),
    ({"impact": 0.4}, "needs `layers:`"),
    ({"impact": 0.4, "layers": [{"src": "a.wav", "at": 0.5}]}, "starts at 0.5s"),
    ({"impact": 0.4, "layers": [{"src": "a.wav", "start": 1.0, "end": 0.9}]}, "nothing would play"),
    ({"impact": 0.4, "layers": [{"src": "a.wav", "volume": 3}]}, "unknown"),
    ({"impact": 0.4, "layers": ["a.wav"], "when": 0}, "unknown"),
])
def test_a_malformed_opening_is_refused_by_name(tmp_path, monkeypatch, opening, needle):
    with pytest.raises(SystemExit) as excinfo:
        _settings(opening, tmp_path, monkeypatch)
    assert needle in str(excinfo.value)


def test_the_sting_rides_the_music_bus_through_the_one_limiter_and_loudnorm(tmp_path,
                                                                            monkeypatch):
    mix = _settings(OPENING, tmp_path, monkeypatch)
    steps = M.audio_steps(mix, runtime=23.1, cuts=[2.4, 5.0], bed_index=1, sfx_indexes=[],
                          opening_indexes=[7, 8])
    graph = ";".join(steps)
    assert ("[7:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=start=0.650:"
            "end=1.080,asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st=0.390:d=0.04,"
            "volume=-1dB,adelay=0|0,atrim=0:23.100,apad=whole_dur=23.100[o1]") in graph
    assert ("[8:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=start=0.000,"
            "asetpts=PTS-STARTPTS,volume=1dB,adelay=400|400,") in graph
    music = next(step for step in steps if step.endswith("[music]"))
    assert "[o1][o2]amix=inputs=3:normalize=0" in music
    assert steps[-1].startswith("[vox][music]amix=inputs=2:normalize=0,alimiter")
    assert "loudnorm" in steps[-1] and graph.count("loudnorm") == 1


def test_a_layer_before_zero_is_trimmed_by_its_head_not_delayed(tmp_path, monkeypatch):
    mix = _settings({"impact": 0.4, "layers": [{"src": "w.wav", "at": -0.2, "start": 0.5,
                                                "end": 1.2, "fade_out": 0.1}]},
                    tmp_path, monkeypatch)
    (step,) = M.opening_steps(mix.sfx.opening, [5], 20.0)
    assert "atrim=start=0.700:end=1.200" in step
    # fade-out positioned on the layer's own clock (0.7 s long, fade 0.1 -> 0.6), minus the head
    assert "afade=t=out:st=0.400:d=0.1" in step
    assert "adelay=0|0" in step
    assert M.opening_placements(mix) == [{"at": 0.0, "role": "opening", "impact": 0.4}]


def test_cuts_json_rows_say_what_the_sting_is_and_where_it_lands(tmp_path, monkeypatch):
    mix = _settings(OPENING, tmp_path, monkeypatch)
    assert M.opening_placements(mix) == [{"at": 0.0, "role": "opening", "impact": 0.4},
                                         {"at": 0.4, "role": "opening", "impact": 0.4}]


@pytest.mark.parametrize("first_word,ok", [(0.52, True), (0.50, True), (0.49, False),
                                           (0.05, False), (None, False)])
def test_the_first_word_must_start_after_the_hit_plus_its_guard(tmp_path, monkeypatch,
                                                                first_word, ok):
    mix = _settings(OPENING, tmp_path, monkeypatch)
    if ok:
        M.check_opening_guard(mix, first_word)
    else:
        with pytest.raises(SystemExit) as excinfo:
            M.check_opening_guard(mix, first_word)
        assert "lead_in_s" in str(excinfo.value) or "word timings" in str(excinfo.value)


def test_element_sounds_are_thinned_around_the_sting_never_the_sting_itself():
    seed = [{"at": 0.0, "role": "opening"}, {"at": 0.4, "role": "opening"}]
    events = [{"at": 1.2, "role": "pop"}, {"at": 3.0, "role": "pop"}, {"at": 4.0, "role": "pop"},
              {"at": 5.0, "role": "pop"}]
    kept, dropped = M.thin_events(events, 0.52, guard=0.5, seed=seed)
    # the 10-second window already holds the two sting layers: two more pops fit, not four
    assert [row["at"] for row in kept] == [1.2, 3.0]
    assert all("10s" in row["why"] for row in dropped)
    # and with no seed the rule is exactly the one it always was
    assert [row["at"] for row in M.thin_events(events, 0.52, guard=0.5)[0]] == \
        [1.2, 3.0, 4.0, 5.0]


# --- through main(), with ffmpeg stubbed --------------------------------------------------

WORDS0 = [{"text": "Why", "start": 0.52, "end": 0.67}]


@pytest.fixture
def stub(tmp_path, monkeypatch):
    spec = {"slug": "open-demo",
            "short": {"hook": "x", "scenes": [0, 1]},
            "scenes": [{"kind": "media", "src": "assets/still.png", "motion": "kenburns",
                        "credit": "Imagery: x", "narration": "Why"},
                       {"kind": "media", "src": "assets/still.png", "motion": "kenburns",
                        "credit": "Imagery: x", "narration": "Because"}],
            "audio": {"bed": {"src": "media/audio/bed.mp3", "lufs": -11.6, "target_lufs": -24},
                      "sfx": {"opening": OPENING}}}
    holder = types.SimpleNamespace(spec=spec)
    monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(safe_load=lambda fh: holder.spec))
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(Image=object(), ImageChops=object()))
    (tmp_path / "scenes.yaml").write_text("#\n")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "still.png").write_bytes(b"\0")
    audio = tmp_path / "media" / "audio"
    audio.mkdir(parents=True)
    for name in ("bed.mp3", "whoosh.wav", "hit.wav"):
        (audio / name).write_bytes(b"\0")
    narration = tmp_path / "build" / "open-demo" / "audio"
    narration.mkdir(parents=True)
    (narration / "durations.json").write_text(json.dumps({"0": 2.3, "1": 2.0}))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: 2.4)
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: None)
    cmds = []
    monkeypatch.setattr(M, "run", cmds.append)
    holder.cmds, holder.work = cmds, tmp_path / "build" / "open-demo"

    def go(words0=WORDS0):
        captions.write_words(narration / "scene_00.wav", words0)
        captions.write_words(narration / "scene_01.wav", [{"text": "Because", "start": 0.05,
                                                           "end": 0.4}])
        monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(tmp_path / "scenes.yaml"),
                                          "--no-end-card"])
        M.main()

    holder.go = go
    return holder


def _final(stub):
    return [c for c in stub.cmds if "concat" in c][-1]


def test_the_rendered_short_mixes_the_sting_and_records_it(stub):
    stub.go()
    cmd = _final(stub)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "[o1][o2]" in graph
    whoosh = next(arg for arg in cmd if arg.endswith("whoosh.wav"))
    assert cmd[cmd.index(whoosh) - 1] == "-i"
    cuts = json.loads(next(stub.work.rglob("cuts.json")).read_text())
    assert {"at": 0.0, "role": "opening", "impact": 0.4} in cuts["sfx"]


def test_the_finished_short_is_48_khz_not_whatever_loudnorm_resampled_to(stub):
    stub.go()
    cmd = _final(stub)
    assert cmd[cmd.index("-ar") + 1] == "48000"
    assert cmd.index("-ar") > cmd.index("-c:a")


def test_a_first_word_inside_the_guard_refuses_before_anything_is_encoded(stub):
    with pytest.raises(SystemExit) as excinfo:
        stub.go(words0=[{"text": "Why", "start": 0.05, "end": 0.2}])
    assert "lead_in_s" in str(excinfo.value)
    assert stub.cmds == []
