"""The edit-grammar layer (scripts/video/grammar.py): blur_bg, per-event SFX, fx.verdict.

Every key is opt-in, so the first thing each group pins is that ABSENT means the graph the
renderer always built. The byte-identical proof on a real scene is in the branch's commit log
(an mp4 sha256 before/after); these tests pin the shape that proof depends on.
"""
import json
import pathlib

import pytest

import crashzoom
import grammar as G
import make_short as M

# The main()-level stub from the audio tests: three media scenes, ffmpeg/Chrome stubbed.
from test_make_short_audio import BED, DURATIONS, PART_SECONDS, WORDS, _final, _graph  # noqa: F401
from test_make_short_audio import stub  # noqa: F401  (pytest fixture)


# --- blur_bg ----------------------------------------------------------------------------

def test_blur_bg_absent_or_false_is_none():
    assert G.parse_blur_bg(None) is None
    assert G.parse_blur_bg(False) is None


def test_blur_bg_true_takes_the_defaults():
    cfg = G.parse_blur_bg(True)
    assert cfg == {"sigma": 10.0, "in_ms": 150.0, "out_ms": 150.0, "hold": None}


@pytest.mark.parametrize("raw,needle", [
    ({"sigma": 0}, "sigma"), ({"sigma": 99}, "sigma"), ({"in_ms": -1}, "in_ms"),
    ({"strength": 3}, "unknown"), ("yes", "true or a mapping"), ({"hold": 0}, "hold")])
def test_blur_bg_refuses_bad_values_by_name(raw, needle):
    with pytest.raises(ValueError) as exc:
        G.parse_blur_bg(raw, "scene 2 overlay")
    assert needle in str(exc.value)


def _overlay(*elements, **block):
    return {"elements": list(elements), **block}


def test_an_overlay_blur_runs_from_the_first_entry_to_the_cut_with_no_out_ramp():
    ov = _overlay({"type": "tag", "text": "A", "enter": {"t": 1.2, "how": "pop"}},
                  {"type": "emoji", "glyph": "x", "enter": {"t": 2.0, "how": "pop"}})
    [w] = G.blur_windows({"blur_bg": True}, ov, dur=3.5, scale=1.2)
    assert (w.kind, w.t0, w.t1, w.ramp_in, w.ramp_out) == ("blur", 1.2, 3.5, 0.15, 0.0)
    assert w.filter == "gblur=sigma=12.0000"      # 10 delivered px at the 1.2x render size


def test_an_element_blur_with_hold_ramps_back_out_before_the_cut():
    ov = _overlay({"type": "tag", "text": "A", "enter": {"t": 1.0, "how": "drop"},
                   "blur_bg": {"sigma": 8, "hold": 1.0, "out_ms": 200}})
    [w] = G.blur_windows({}, ov, dur=4.0)
    assert (w.t0, w.t1, w.ramp_in, w.ramp_out) == (1.0, 2.0, 0.15, 0.2)


def test_a_card_template_overlay_blurs_from_frame_zero():
    [w] = G.blur_windows({"template": "countdown", "blur_bg": True}, None, dur=2.0)
    assert (w.t0, w.t1) == (0.0, 2.0)


def test_overlapping_blur_windows_merge_and_keep_the_strongest_blur():
    ov = _overlay({"type": "tag", "text": "A", "enter": {"t": 1.0, "how": "pop"},
                   "blur_bg": {"sigma": 6, "hold": 1.5}},
                  {"type": "tag", "text": "B", "enter": {"t": 2.0, "how": "pop"},
                   "blur_bg": {"sigma": 12, "hold": 1.0}})
    [w] = G.blur_windows({}, ov, dur=5.0)
    assert (w.t0, w.t1) == (1.0, 3.0)
    assert w.filter == "gblur=sigma=12.0000"


def test_no_blur_key_means_no_window():
    ov = _overlay({"type": "tag", "text": "A", "enter": {"t": 1.0, "how": "pop"}})
    assert G.blur_windows({}, ov, dur=3.0) == []
    assert G.blur_windows(None, None, dur=3.0) == []


def test_no_windows_add_no_filter_steps():
    assert G.window_steps("g0", []) == ([], "g0")


def test_a_window_is_a_split_copy_faded_in_on_alpha_and_overlaid_inside_its_span():
    w = G.Window("blur", 1.0, 2.0, 0.15, 0.2, "gblur=sigma=12.0000")
    steps, stage = G.window_steps("m0", [w])
    assert steps[0] == "[m0]split=2[wb0][ws0]"
    assert steps[1] == ("[ws0]gblur=sigma=12.0000,format=yuva420p,"
                        "fade=t=in:st=1.0000:d=0.1500:alpha=1,"
                        "fade=t=out:st=1.8000:d=0.2000:alpha=1[wf0]")
    assert steps[2] == ("[wb0][wf0]overlay=x=0:y=0:format=auto:"
                        "enable='between(t,1.0000,2.0000)'[wb1]")
    assert stage == "wb1"


# --- fx.verdict -------------------------------------------------------------------------

WORDS_S5 = [{"text": "Taller", "start": 0.10, "end": 0.40},
            {"text": "than", "start": 0.40, "end": 0.55},
            {"text": "child", "start": 2.10, "end": 2.40}]


def test_fx_absent_is_none_and_a_bad_verdict_is_refused():
    assert G.parse_fx({}) is None
    with pytest.raises(ValueError) as exc:
        G.parse_fx({"fx": {"verdict": "meh"}}, "scene 5")
    assert "good, bad" in str(exc.value)
    with pytest.raises(ValueError):
        G.parse_fx({"fx": {"verdict": "bad", "colour": "red"}})


def test_a_whole_scene_verdict_starts_and_ends_on_the_cuts_with_no_ramps():
    fx = G.parse_fx({"fx": {"verdict": "bad"}})
    w = G.verdict_window(fx, WORDS_S5, dur=3.0)
    assert (w.kind, w.t0, w.t1, w.ramp_in, w.ramp_out) == ("tint", 0.0, 3.0, 0.0, 0.0)
    assert w.filter.startswith("colorchannelmixer=rr=0.9200:rg=0.2200:")


def test_a_sub_span_verdict_resolves_its_words_and_ramps_in():
    fx = G.parse_fx({"fx": {"verdict": "good", "from": {"word": "child"}, "strength": 0.5}})
    w = G.verdict_window(fx, WORDS_S5, dur=3.0)
    assert (w.t0, w.t1, w.ramp_in, w.ramp_out) == (2.1, 3.0, 0.1, 0.0)
    assert "rr=0.8600" in w.filter and "gr=0.0900" in w.filter     # halfway from identity


def test_good_pulls_toward_green_and_bad_toward_red():
    good, bad = G.verdict_filter("good"), G.verdict_filter("bad")
    assert "gr=0.1800" in good and "gg=0.9200" in good and "rr=0.7200" in good
    assert "rg=0.2200" in bad and "gg=0.7200" in bad and "rr=0.9200" in bad


def test_a_verdict_span_shorter_than_a_frame_is_refused():
    fx = G.parse_fx({"fx": {"verdict": "bad", "from": 2.0, "to": 2.01}})
    with pytest.raises(ValueError):
        G.verdict_window(fx, WORDS_S5, dur=3.0)


# --- encode_media_scene: absent keys build the same command -----------------------------

def _encode(monkeypatch, tmp_path, **kw):
    cmds = []
    monkeypatch.setattr(M, "run", cmds.append)
    monkeypatch.setattr(M, "probe_size", lambda p: (2000, 3000))
    M.encode_media_scene(tmp_path / "a.jpg", "push", [], tmp_path / "a.wav", 3.0, 18,
                         tmp_path / "out.mp4", join="cut", **kw)
    return cmds[0]


def test_no_windows_is_the_same_ffmpeg_command_as_before_the_layer(monkeypatch, tmp_path):
    assert _encode(monkeypatch, tmp_path) == _encode(monkeypatch, tmp_path, windows=())


def test_windows_go_on_the_footage_before_the_scale(monkeypatch, tmp_path):
    w = G.Window("tint", 0.0, 3.0, 0.0, 0.0, G.verdict_filter("bad"))
    graph = _graph(_encode(monkeypatch, tmp_path, windows=[w]))
    assert graph.index("colorchannelmixer") < graph.index("scale=1080:1920")
    assert "[m0]split=2[wb0][ws0]" in graph


# --- the crash-zoom badge ---------------------------------------------------------------

BADGE = {"text": '36"-56"', "at": [540, 1600]}


def test_a_badge_without_blur_bg_parses_exactly_as_before():
    assert "blur_bg" not in crashzoom.parse_badge(dict(BADGE), "scene 0", "crashzoom.badge")


def test_a_badge_blur_bg_is_parsed_and_checked():
    badge = crashzoom.parse_badge({**BADGE, "blur_bg": {"sigma": 9, "hold": 1.0}},
                                  "scene 0", "crashzoom.badge")
    assert badge["blur_bg"]["sigma"] == 9.0
    with pytest.raises(ValueError):
        crashzoom.parse_badge({**BADGE, "blur_bg": {"sigma": -1}}, "s", "crashzoom.badge")


def test_blur_strength_ramps_in_holds_and_ramps_out():
    cfg = G.parse_blur_bg({"in_ms": 100, "out_ms": 100, "hold": 1.0})
    assert G.blur_strength(cfg, -0.1) == 0.0
    assert G.blur_strength(cfg, 0.05) == pytest.approx(0.5)
    assert G.blur_strength(cfg, 0.5) == 1.0
    assert G.blur_strength(cfg, 0.95) == pytest.approx(0.5)
    assert G.blur_strength(cfg, 1.2) == 0.0


def test_blur_behind_returns_the_frame_untouched_when_no_blur_is_up():
    Image = pytest.importorskip("PIL.Image")
    frame = Image.new("RGBA", (8, 8), (10, 20, 30, 255))
    assert crashzoom.blur_behind(frame, [({"start": 0.0}, 3)]) is frame
    badge = crashzoom.parse_badge({**BADGE, "blur_bg": {"hold": 0.5}}, "s", "b")
    assert crashzoom.blur_behind(frame, [(badge, 300)]) is frame      # 10 s later: over
    assert crashzoom.blur_behind(frame, [(badge, 6)]) is not frame    # 0.2 s in: blurred


# --- sounds -----------------------------------------------------------------------------

def _resolve(name, raw):
    return f"/abs/{raw['src']}"


def test_no_grammar_key_means_no_grammar():
    assert G.parse_grammar({}, _resolve) is None
    assert G.parse_grammar({"on_cut": "whoosh.wav", "events": {}}, _resolve) is None


def test_on_cut_as_a_mapping_is_the_grammar_hit_with_its_default_gain():
    g = G.parse_grammar({"on_cut": {"src": "hit.wav"}}, _resolve)
    assert g.cut == G.Sound("cut", "/abs/hit.wav", -10.0)
    assert g.tag is None and g.any()


def test_on_move_and_on_verdict_parse_their_own_keys():
    g = G.parse_grammar({"on_move": {"src": "w.wav", "lead": 0.2, "motions": ["punch"],
                                     "end": 0.7},
                         "on_verdict": {"bad": {"src": "b.wav", "gain_db": -12}},
                         "min_gap": 0.2}, _resolve)
    assert (g.move.end, g.move_lead, g.move_motions, g.min_gap) == (0.7, 0.2, ("punch",), 0.2)
    assert g.bad.gain_db == -12 and g.good is None


@pytest.mark.parametrize("raw", [
    {"on_tag": {"src": "p.wav", "volume": 3}}, {"on_tag": {}},
    {"on_verdict": {"meh": {"src": "x"}}}, {"on_move": {"src": "w", "start": 1, "end": 0.5}}])
def test_bad_grammar_sounds_are_refused(raw):
    with pytest.raises(ValueError):
        G.parse_grammar(raw, _resolve)


ROWS = [{"scene": 0, "start": 0.0}, {"scene": 1, "start": 4.0}, {"scene": 2, "start": 9.0}]


def test_cut_events_are_scene_starts_after_the_first_plus_beat_boundaries():
    rows = G.cut_events(ROWS, {1: [1.5], 2: []})
    assert [r["at"] for r in rows] == [4.0, 5.5, 9.0]
    assert {r["role"] for r in rows} == {"cut"}


def test_tag_events_skip_elements_with_their_own_sound_and_land_drops_on_landing():
    scene = {"elements": [
        {"type": "tag", "enter": {"t": 1.0, "how": "pop"}},
        {"type": "tag", "enter": {"t": 2.0, "how": "drop"}},
        {"type": "emoji", "enter": {"t": 3.0, "how": "pop"}, "sfx": "chime"},
        {"type": "emoji"}]}
    rows = G.tag_events([(1, scene)], ROWS)
    assert [r["at"] for r in rows] == [5.0, 6.6]


def test_move_events_start_one_lead_before_the_move():
    rows = G.move_events(ROWS, {1: [0.0, 1.5]}, lead=0.15)
    assert [r["at"] for r in rows] == [3.85, 5.35]


def test_verdict_events_name_their_verdict():
    assert G.verdict_events(ROWS, {2: ("bad", 0.4)}) == [{"at": 9.4, "role": "verdict_bad"}]


def test_thin_drops_sounds_before_the_first_word_and_keeps_the_higher_priority_one():
    cands = [{"at": 0.2, "role": "cut"}, {"at": 4.0, "role": "cut"},
             {"at": 4.05, "role": "verdict_bad"}, {"at": 5.0, "role": "move"},
             {"at": 5.06, "role": "tag"}, {"at": 8.0, "role": "cut"}]
    kept, dropped = G.thin(cands, first_speech_s=0.3, guard=0.5, min_gap=0.12,
                           seed=[{"at": 7.95, "role": "pop"}])
    assert [(r["at"], r["role"]) for r in kept] == [(4.05, "verdict_bad"), (5.06, "tag")]
    assert {(r["at"], r["role"]) for r in dropped} == {(0.2, "cut"), (4.0, "cut"),
                                                       (5.0, "move"), (8.0, "cut")}


def test_sound_steps_trim_the_file_and_delay_it_onto_the_timeline():
    g = G.Grammar(move=G.Sound("move", "/w.wav", -20.0, start=0.0, end=0.7))
    steps, labels = G.sound_steps(g, [{"at": 2.5, "role": "move"}], [7], runtime=10.0)
    assert labels == ["g1"]
    assert steps[0] == ("[7:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                        "atrim=start=0:end=0.7,asetpts=PTS-STARTPTS,"
                        "afade=t=out:st=0.680:d=0.02,volume=-20dB,adelay=2500|2500,"
                        "atrim=0:10.000,apad=whole_dur=10.000[g1]")


def test_audio_steps_without_grammar_rows_are_unchanged_and_with_them_add_inputs_to_the_bus():
    mix = M.AudioMix(bed=M.Bed(src="/a/bed.mp3", lufs=-28.9), duck=M.Duck(),
                     sfx=M.Sfx(src="", events=(),
                               grammar=G.Grammar(cut=G.Sound("cut", "/h.wav", -10.0))),
                     master=M.Master())
    plain = M.audio_steps(mix, runtime=10.0, cuts=[], bed_index=1, sfx_indexes=[])
    same = M.audio_steps(mix, runtime=10.0, cuts=[], bed_index=1, sfx_indexes=[],
                         grammar_rows=[], grammar_indexes=[])
    assert plain == same
    with_hits = ";".join(M.audio_steps(
        mix, runtime=10.0, cuts=[], bed_index=1, sfx_indexes=[],
        grammar_rows=[{"at": 4.0, "role": "cut"}], grammar_indexes=[2]))
    assert "[2:a]aformat" in with_hits and "[bedduck][g1]amix=inputs=2" in with_hits
    assert with_hits.endswith("alimiter=limit=0.97,loudnorm=I=-16:TP=-1.5:LRA=11[aout]")


# --- the bundle -------------------------------------------------------------------------

def _bundle(tmp_path, data=b"RIFFfake"):
    (tmp_path / "hit.wav").write_bytes(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sounds": {"hit": {
        "file": "hit.wav", "sha256": G.sha256(tmp_path / "hit.wav")}}}))
    return manifest


def test_a_bundle_src_resolves_to_its_checked_file(tmp_path):
    manifest = _bundle(tmp_path)
    assert G.resolve_bundle("bundle:hit", manifest) == str(tmp_path / "hit.wav")


def test_a_bundle_src_refuses_a_missing_name_a_missing_file_and_a_changed_file(tmp_path):
    manifest = _bundle(tmp_path)
    with pytest.raises(ValueError):
        G.resolve_bundle("bundle:boing", manifest)
    (tmp_path / "hit.wav").write_bytes(b"changed")
    with pytest.raises(ValueError) as exc:
        G.resolve_bundle("bundle:hit", manifest)
    assert "sha256" in str(exc.value)
    (tmp_path / "hit.wav").unlink()
    with pytest.raises(FileNotFoundError) as exc:
        G.resolve_bundle("bundle:hit", manifest)
    assert "fetch.py" in str(exc.value)


def test_the_shipped_manifest_records_a_licence_url_and_sha_for_every_sound():
    data = G.load_bundle()
    assert set(data["sounds"]) == {"hit", "pop", "whoosh", "ding", "buzzer"}
    for name, row in data["sounds"].items():
        assert row["provider"] == "mixkit", name
        assert row["licence_url"].startswith("https://mixkit.co/license"), name
        assert row["download_url"].startswith("https://assets.mixkit.co/"), name
        assert len(row["sha256"]) == 64, name


def test_the_bundled_wavs_are_gitignored():
    gitignore = (pathlib.Path(__file__).resolve().parents[1] / ".gitignore").read_text()
    assert "scripts/video/sfx/*.wav" in gitignore


# --- audio_settings ---------------------------------------------------------------------

def _audio_root(tmp_path, *names):
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("x")
    (tmp_path / "media" / "audio").mkdir(parents=True, exist_ok=True)
    for name in ("bed.mp3", *names):
        (tmp_path / "media" / "audio" / name).write_bytes(b"\0")
    return spec_path


def test_legacy_string_on_cut_is_still_the_beat_whoosh(tmp_path):
    spec_path = _audio_root(tmp_path, "whoosh.wav")
    mix = M.audio_settings({"audio": {"bed": dict(BED),
                                      "sfx": {"on_cut": "media/audio/whoosh.wav"}}}, spec_path)
    assert mix.sfx.src.endswith("whoosh.wav") and mix.sfx.grammar is None


def test_mapping_on_cut_is_the_grammar_and_queues_no_whoosh(tmp_path):
    spec_path = _audio_root(tmp_path, "hit.wav")
    mix = M.audio_settings({"audio": {"bed": dict(BED), "sfx": {
        "on_cut": {"src": "media/audio/hit.wav", "gain_db": -9}}}}, spec_path)
    assert mix.sfx.src == ""
    assert mix.sfx.grammar.cut.gain_db == -9 and mix.sfx.grammar.cut.src.endswith("hit.wav")


def test_a_missing_grammar_file_refuses_the_render(tmp_path):
    spec_path = _audio_root(tmp_path)
    with pytest.raises(SystemExit) as exc:
        M.audio_settings({"audio": {"bed": dict(BED), "sfx": {
            "on_tag": {"src": "media/audio/nope.wav"}}}}, spec_path)
    assert "nope.wav" in str(exc.value)


# --- credit plates: off by default (Stephen, 2026-11-04) ---------------------------------

def test_credit_plate_is_off_by_default(tmp_path):
    import cards
    assert M.media_layers({"credit": "Photo: someone / CC BY 2.0"}, cards.brand_tokens(None),
                          tmp_path, 0) == []


def test_credit_plate_token_is_checked():
    import cards
    assert cards.brand_tokens({"credit_plate": "on"})["credit_plate"] == "on"
    with pytest.raises(ValueError):
        cards.brand_tokens({"credit_plate": "yes"})


# --- main(): the layer wired end to end (ffmpeg/Chrome stubbed) -------------------------

def _grammar_render(stub, tmp_path, sfx_extra, scene_extra=None):
    audio = tmp_path / "media" / "audio"
    for name in ("hit.wav", "pop.wav", "buzz.wav", "w.wav"):
        (audio / name).write_bytes(b"\0")
    stub.spec["audio"] = {"bed": dict(BED), "sfx": sfx_extra}
    for idx, extra in (scene_extra or {}).items():
        stub.spec["scenes"][idx].update(extra)
    stub.go("--no-end-card")
    cuts = json.loads((tmp_path / "build" / "aud-demo" / "short" / "cuts.json").read_text())
    return cuts, _final(stub)


def test_a_hit_lands_on_every_cut_and_is_recorded_in_cuts_json(stub, tmp_path):
    cuts, cmd = _grammar_render(stub, tmp_path,
                                {"on_cut": {"src": "media/audio/hit.wav"}})
    assert [r for r in cuts["sfx"] if r["role"] == "cut"] == [
        {"at": PART_SECONDS, "role": "cut"}, {"at": 2 * PART_SECONDS, "role": "cut"}]
    assert cmd.count(str(tmp_path / "media" / "audio" / "hit.wav")) == 2
    assert "adelay=6000|6000" in _graph(cmd)


def test_a_verdict_tints_its_scene_and_its_buzzer_beats_the_cut_hit(stub, tmp_path):
    cuts, cmd = _grammar_render(
        stub, tmp_path,
        {"on_cut": {"src": "media/audio/hit.wav"},
         "on_verdict": {"bad": {"src": "media/audio/buzz.wav"}}},
        {1: {"fx": {"verdict": "bad"}}})
    roles = [(r["at"], r["role"]) for r in cuts["sfx"]]
    assert (PART_SECONDS, "verdict_bad") in roles
    assert (PART_SECONDS, "cut") not in roles               # same instant: the verdict wins
    scene1 = [c for c in stub.cmds if str(c[-1]).endswith("scene_1.mp4")][0]
    assert "colorchannelmixer=rr=0.9200" in _graph(scene1)
    scene0 = [c for c in stub.cmds if str(c[-1]).endswith("scene_0.mp4")][0]
    assert "colorchannelmixer=rr=0.9200" not in _graph(scene0)


def test_fx_on_a_card_scene_is_refused(stub, tmp_path):
    stub.spec["scenes"][0] = {"kind": "card", "template": "countdown", "data": {},
                              "narration": "one", "fx": {"verdict": "good"}}
    with pytest.raises(SystemExit) as exc:
        stub.go()
    assert "fx" in str(exc.value)


def test_fx_list_splits_a_line_into_spans():
    spans = G.parse_fx_list({"fx": [{"verdict": "bad", "to": {"word": "that"}},
                                    {"verdict": "good", "from": {"word": "with"}}]}, "scene 5")
    assert [s["verdict"] for s in spans] == ["bad", "good"]
    assert G.parse_fx_list({}) == []
    assert G.parse_fx_list({"fx": {"verdict": "bad"}})[0]["verdict"] == "bad"
    with pytest.raises(ValueError, match="empty list"):
        G.parse_fx_list({"fx": []})
    with pytest.raises(ValueError, match=r"fx\[1\]"):
        G.parse_fx_list({"fx": [{"verdict": "bad"}, {"verdict": "meh"}]}, "scene 5")
    with pytest.raises(ValueError, match="at most"):
        G.parse_fx_list({"fx": [{"verdict": "bad"}] * 5})


def test_fx_list_spans_may_not_overlap():
    G.check_no_overlap([(0.0, 1.0), (1.0, 2.0)])
    with pytest.raises(ValueError, match="overlap"):
        G.check_no_overlap([(0.0, 1.5), (1.0, 2.0)], "scene 5")


def test_verdict_events_take_a_list_per_scene():
    assert G.verdict_events(ROWS, {2: [("bad", 0.0), ("good", 1.5)]}) == [
        {"at": 9.0, "role": "verdict_bad"}, {"at": 10.5, "role": "verdict_good"}]
