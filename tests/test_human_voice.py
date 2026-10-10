"""human_voice.py's pure logic: sentences, normalisation, the take-keeping alignment, the
missing-word report, the gap trimmer, word-time mapping, and the `voice: human` switch.

Standard library only (the module's numpy/soundfile/yaml imports are inside functions).
The audio pipeline itself is exercised end to end by hand on a stand-in recording
(scripts/video/human_voice_standin.py); see the docstring of human_voice.py.
"""
import json

import pytest

import human_voice as H


def norm(text):
    return [w for w, _ in H.normalise(text.split())]


def script_of(*sentences):
    return [norm(s) for s in sentences]


S1 = "The lions came from Oregon."
S2 = "Florida was a shock."
S3 = "So Disney cooled the rock they like to lie on."


# --- text -----------------------------------------------------------------------------

def test_sentences_split_on_terminal_punctuation_and_keep_a_trailing_fragment():
    tokens = "A cold rock in a Florida August? I'd lie on it too. And then".split()
    assert H.sentence_spans(tokens) == [(0, 7), (7, 12), (12, 14)]


def test_numbers_fold_to_digits_on_both_sides():
    assert norm("a hundred and sixty feet") == ["160", "feet"]
    assert norm("climb 160 feet") == ["climb", "160", "feet"]
    assert norm("opened in fifty-five.") == ["opened", "in", "55"]
    assert norm("opened in '55.") == ["opened", "in", "55"]
    assert norm("twenty-seven thousand acres") == ["27000", "acres"]
    assert norm("27,000 acres") == ["27000", "acres"]
    assert norm("forty a week") == ["40", "a", "week"]


def test_a_spelled_number_remembers_every_display_token_it_came_from():
    pairs = H.normalise("You climb a hundred and sixty feet".split())
    assert pairs[2] == ("160", (2, 3, 4, 5))


def test_apostrophes_hyphens_and_case_normalise_away():
    assert norm("I'd air-conditions AC.") == ["id", "air", "conditions", "ac"]


# --- alignment ------------------------------------------------------------------------

def kept_text(heard_text, *sentences, **kw):
    heard = norm(heard_text)
    script = script_of(*sentences)
    takes = H.align_script(heard, script, **kw)
    kept = H.kept_takes(takes, len(script))
    return [None if t is None else " ".join(heard[t.start:t.end]) for t in kept], takes


def test_a_clean_read_keeps_one_take_per_sentence():
    kept, takes = kept_text(f"{S1} {S2} {S3}", S1, S2, S3)
    assert kept == [" ".join(norm(S1)), " ".join(norm(S2)), " ".join(norm(S3))]
    assert len(takes) == 3


def test_a_sentence_read_twice_keeps_the_LAST_take():
    heard = norm(f"{S1} {S2} {S2} {S3}")
    takes = H.align_script(heard, script_of(S1, S2, S3))
    kept = H.kept_takes(takes, 3)
    assert kept[1].start == len(norm(S1)) + len(norm(S2))      # the second reading
    assert [t.sentence for t in takes] == [0, 1, 1, 2]


def test_a_false_start_is_cut_and_the_full_reread_kept():
    heard = norm(f"{S1} So Disney cooled the {S3}")
    takes = H.align_script(heard, script_of(S1, S3))
    kept = H.kept_takes(takes, 2)
    assert kept[1].start == len(norm(S1)) + 4
    false_starts = [t for t in takes if not t.complete]
    assert len(false_starts) == 1 and false_starts[0].sentence == 1


def test_a_flub_with_a_wrong_word_then_a_reread_keeps_the_reread():
    kept, _ = kept_text(f"The lions came from Ohio. {S1} {S2}", S1, S2)
    assert kept[0] == " ".join(norm(S1))


def test_a_reread_of_two_sentences_back_keeps_both_later_takes():
    heard = norm(f"{S1} {S2} {S1} {S2} {S3}")
    takes = H.align_script(heard, script_of(S1, S2, S3))
    kept = H.kept_takes(takes, 3)
    n1, n2 = len(norm(S1)), len(norm(S2))
    assert kept[0].start == n1 + n2 and kept[1].start == 2 * n1 + n2


def test_stray_words_between_takes_are_junk_not_takes():
    heard = norm(f"{S1} sorry let me try that again {S2}")
    takes = H.align_script(heard, script_of(S1, S2))
    covered = {j for t in takes for j in range(t.start, t.end)}
    assert [heard[j] for j in range(len(heard)) if j not in covered] == \
        ["sorry", "let", "me", "try", "that", "again"]


def test_a_sentence_never_read_is_none():
    kept, _ = kept_text(f"{S1} {S3}", S1, S2, S3)
    assert kept[1] is None and kept[0] and kept[2]


def test_a_patch_file_aligns_against_any_subset_of_the_script():
    kept, _ = kept_text(S2, S1, S2, S3, skip_cost=0.0)
    assert kept == [None, " ".join(norm(S2)), None]


def test_spoken_numbers_align_with_the_spelled_script():
    kept, _ = kept_text("You climb 160 feet.", "You climb a hundred and sixty feet.")
    assert kept == ["you climb 160 feet"]


# --- the report -----------------------------------------------------------------------

def test_the_report_names_missing_and_extra_words_in_the_scripts_spelling():
    tokens = "So Disney cooled the rock they like to lie on.".split()
    rep = H.take_report(tokens, H.normalise(tokens), norm("So Disney cooled the big rock they lie on"))
    assert rep["missing"] == ["like", "to"]
    assert rep["extra"] == ["big"]


def test_a_near_spelling_is_heard_as_not_missing():
    tokens = "Kilimanjaro Safaris".split()
    rep = H.take_report(tokens, H.normalise(tokens), norm("Kilimanjero Safaris"))
    assert rep["missing"] == [] and rep["heard_as"] == ["Kilimanjaro -> kilimanjero"]


def test_a_wrong_word_is_both_missing_and_extra():
    tokens = "The lions came from Oregon.".split()
    rep = H.take_report(tokens, H.normalise(tokens), norm("The lions came from Texas"))
    assert rep["missing"] == ["Oregon."] and rep["extra"] == ["texas"]


def test_word_error_rate():
    assert H.word_error_rate(["a", "b", "c", "d"], ["a", "b", "x", "d"]) == 0.25
    assert H.word_error_rate(["a", "b"], ["a", "b"]) == 0.0


# --- caption timings ------------------------------------------------------------------

def test_token_times_take_the_heard_words_and_interpolate_a_missing_one():
    tokens = "So Disney cooled the rock.".split()
    script = H.normalise(tokens)
    heard = norm("So Disney cooled rock")
    times = [(0.0, 0.2), (0.2, 0.6), (0.6, 1.0), (1.2, 1.5)]
    ops = H.align_ops(heard, [w for w, _ in script])
    out = H.token_times(len(tokens), script, ops, times)
    assert out[0] == (0.0, 0.2) and out[4] == (1.2, 1.5)
    assert out[3] == (1.0, 1.2)          # "the" was never heard: it fills the hole


def test_token_times_split_a_number_across_its_display_tokens():
    tokens = "a hundred and sixty".split()
    script = H.normalise(tokens)
    ops = H.align_ops(["160"], [w for w, _ in script])
    out = H.token_times(4, script, ops, [(1.0, 2.0)])
    assert out[0][0] == 1.0 and out[-1][1] == 2.0
    assert all(a < b for a, b in out)


# --- the gap trimmer ------------------------------------------------------------------

def test_gap_length_trims_only_long_silences():
    p = H.Pacing()
    assert H.gap_length(0.2, True, p) == 0.2          # natural, kept
    assert H.gap_length(0.35, True, p) == 0.35
    assert H.gap_length(1.6, True, p) == p.sentence_target
    assert H.gap_length(0.42, False, p) == 0.42       # a pause inside a sentence
    assert H.gap_length(0.9, False, p) == p.pause_target


def total(pieces):
    return round(sum(p.seconds for p in pieces), 6)


def test_a_long_pause_inside_a_sentence_is_cut_from_its_middle():
    cut = H.SentenceCut(src=0, runs=[(10.0, 11.0), (12.5, 13.0)], room_before=1.0, room_after=1.0)
    pieces = H.scene_pieces([cut], lead=0.05, tail=0.15)
    # lead + 1.0 speech + 0.30 pause + 0.5 speech + tail
    assert total(pieces) == round(0.05 + 1.0 + 0.30 + 0.5 + 0.15, 6)
    assert pieces == [H.Piece(0, 9.95, 11.15), H.Piece(0, 12.35, 13.15)]


def test_neighbouring_sentences_keep_a_natural_gap_and_trim_a_long_one():
    a = H.SentenceCut(src=0, runs=[(1.0, 2.0)], room_before=1.0, room_after=0.25)
    b = H.SentenceCut(src=0, runs=[(2.25, 3.0)], room_before=0.25, room_after=2.0, follows=True)
    assert H.scene_pieces([a, b], 0.05, 0.15) == [H.Piece(0, 0.95, 3.15)]   # untouched
    b_far = H.SentenceCut(src=0, runs=[(4.0, 5.0)], room_before=2.0, room_after=1.0, follows=True)
    a_far = H.SentenceCut(src=0, runs=[(1.0, 2.0)], room_before=1.0, room_after=2.0)
    pieces = H.scene_pieces([a_far, b_far], 0.05, 0.15)
    assert pieces == [H.Piece(0, 0.95, 2.15), H.Piece(0, 3.85, 5.15)]


def test_a_gap_where_a_retake_was_cut_is_rebuilt_at_the_target_with_room_tone():
    a = H.SentenceCut(src=0, runs=[(1.0, 2.0)], room_before=1.0, room_after=0.1)
    b = H.SentenceCut(src=0, runs=[(9.0, 10.0)], room_before=0.05, room_after=1.0, follows=False)
    pieces = H.scene_pieces([a, b], 0.05, 0.15)
    assert total(pieces) == round(0.05 + 1.0 + 0.30 + 1.0 + 0.15, 6)
    assert H.Piece(None, fill=round(0.30 - 0.1 - 0.05, 6)) in \
        [H.Piece(None, fill=round(p.fill, 6)) for p in pieces]
    assert all(not (p.src == 0 and p.a < 8.9 and p.b > 2.1001) for p in pieces)   # flub gone


def test_scene_tail_sums_to_the_scene_gap_with_pad_and_lead():
    assert H.scene_tail(0.1, 0.05) == pytest.approx(0.15)
    assert H.scene_tail(0.1, 0.05, last=True) == H.Pacing().last_tail


def test_map_time_follows_the_cuts_and_snaps_a_cut_time_to_a_kept_edge():
    pieces = [H.Piece(None, fill=0.05), H.Piece(0, 1.0, 2.0), H.Piece(0, 5.0, 6.0)]
    assert H.map_time(1.5, 0, pieces) == pytest.approx(0.55)
    assert H.map_time(5.5, 0, pieces) == pytest.approx(1.55)
    assert H.map_time(4.9, 0, pieces) == pytest.approx(1.05)   # in the cut, snaps forward


# --- the switch -----------------------------------------------------------------------

def write_spec(tmp_path, **extra):
    (tmp_path / ".git").mkdir(exist_ok=True)
    wav = tmp_path / "read.wav"
    wav.write_bytes(b"RIFF fake")
    spec = {"slug": "demo", "voice": "human", "human_voice": "read.wav",
            "short": {"scenes": [0]}, "scenes": [{"narration": "Hello there."}], **extra}
    return spec, tmp_path / "scenes.yaml", wav


def test_is_human():
    assert H.is_human({"voice": "human"}) and H.is_human({"voice": " Human "})
    assert not H.is_human({"voice": "am_michael"}) and not H.is_human({})


def test_make_short_guard_refuses_a_human_spec_without_a_human_build(tmp_path):
    spec, path, _ = write_spec(tmp_path)
    audio = tmp_path / "audio"
    audio.mkdir()
    with pytest.raises(SystemExit, match="not a human build"):
        H.check_audio(spec, path, audio)


def test_make_short_guard_accepts_a_matching_build_and_refuses_a_stale_one(tmp_path):
    spec, path, wav = write_spec(tmp_path)
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / H.MARKER).write_text(json.dumps({"source_sha1": [H.file_digest(wav)],
                                              "script_sha1": H.script_digest(spec)}))
    H.check_audio(spec, path, audio)
    spec["scenes"][0]["narration"] = "Hello again."
    with pytest.raises(SystemExit, match="narration text changed"):
        H.check_audio(spec, path, audio)
    spec["scenes"][0]["narration"] = "Hello there."
    wav.write_bytes(b"RIFF another take")
    with pytest.raises(SystemExit, match="different recording"):
        H.check_audio(spec, path, audio)


def test_a_tts_spec_refuses_audio_a_human_build_left(tmp_path):
    spec, path, _ = write_spec(tmp_path)
    spec.pop("voice")
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / H.MARKER).write_text("{}")
    with pytest.raises(SystemExit, match="HUMAN read"):
        H.check_audio(spec, path, audio)
    (audio / H.MARKER).unlink()
    H.check_audio(spec, path, audio)


def test_human_voice_path_resolves_against_the_spec_repo_and_must_exist(tmp_path):
    spec, path, wav = write_spec(tmp_path)
    assert H.human_sources(spec, path) == [wav.resolve()]
    spec["human_voice"] = ["read.wav", "missing.wav"]
    with pytest.raises(SystemExit, match="does not exist"):
        H.human_sources(spec, path)


def test_narrate_refuses_a_human_spec(tmp_path, capsys, monkeypatch):
    yaml = pytest.importorskip("yaml")
    import narrate
    spec, path, _ = write_spec(tmp_path)
    path.write_text(yaml.safe_dump(spec))
    assert narrate.main(["--spec", str(path), "--out", str(tmp_path / "out")]) == 2
    assert "human_voice.py" in capsys.readouterr().err


# --- which audio belongs to a take ----------------------------------------------------

def test_the_tail_of_a_cut_false_start_does_not_ride_into_the_kept_take():
    # false start 12.0-12.54, pause, kept take 13.44-14.4; Whisper ends the flub at 12.52
    # and stretches the take's first word back to 12.52.
    islands = [(12.0, 12.54), (13.44, 14.40)]
    runs = H.take_runs(islands, lo=12.52, hi=15.0, w0=12.52, w1=14.4,
                       cut_before=True, cut_after=False)
    assert runs == [(13.44, 14.40)]


def test_an_island_shared_with_a_kept_neighbour_is_split_at_the_edge():
    islands = [(9.0, 11.0)]
    runs = H.take_runs(islands, lo=10.63, hi=12.0, w0=10.63, w1=11.0,
                       cut_before=False, cut_after=False)
    assert runs == [(10.63, 11.0)]


def test_a_straddling_island_mostly_inside_the_take_stays_even_beside_a_cut():
    runs = H.take_runs([(12.4, 13.5)], lo=12.5, hi=14.0, w0=12.5, w1=13.5,
                       cut_before=True, cut_after=True)
    assert runs == [(12.5, 13.5)]


def test_word_times_in_silence_snap_onto_the_speech():
    runs = [(21.2, 22.9)]
    spans = [(20.6, 20.84), (21.34, 21.64)]
    out = H.snap_to_speech(spans, runs)
    assert out[0][0] == 21.2 and out[0][1] > out[0][0]
    assert out[1] == (21.34, 21.64)


def test_utterances_split_at_pauses_so_a_reread_is_transcribed_apart_from_its_flub():
    islands = [(12.0, 12.2), (12.3, 12.54), (13.44, 13.9), (14.0, 14.4)]
    assert H.utterances(islands, pause=0.45, pad=0.1) == [(11.9, 12.64), (13.34, 14.5)]


def test_a_word_in_pure_silence_is_not_audible():
    islands = [(1.0, 2.0)]
    assert H.audible((1.5, 1.7), islands)
    assert not H.audible((2.3, 2.5), islands)
    assert not H.audible((1.99, 2.4), islands)


# --- tempo (human_voice_tempo) ------------------------------------------------------------

def test_spec_tempo_defaults_to_1_and_rejects_a_typo():
    assert H.spec_tempo({}) == 1.0 and H.spec_tempo({"human_voice_tempo": None}) == 1.0
    assert H.spec_tempo({"human_voice_tempo": 1.1}) == 1.1
    assert H.spec_tempo({"human_voice_tempo": "1.1"}) == 1.1
    with pytest.raises(SystemExit, match="outside"):
        H.spec_tempo({"human_voice_tempo": 11})
    with pytest.raises(SystemExit, match="number"):
        H.spec_tempo({"human_voice_tempo": "fast"})


def test_tempo_filter_is_atempo_and_a_no_op_at_1():
    assert H.tempo_filter(1.0) is None
    assert H.tempo_filter(1.1) == "atempo=1.1"


def test_make_short_guard_refuses_a_build_made_at_another_tempo(tmp_path):
    spec, path, wav = write_spec(tmp_path, human_voice_tempo=1.1)
    audio = tmp_path / "audio"
    audio.mkdir()
    marker = {"source_sha1": [H.file_digest(wav)], "script_sha1": H.script_digest(spec)}
    (audio / H.MARKER).write_text(json.dumps(marker))           # built before tempo existed
    with pytest.raises(SystemExit, match="tempo"):
        H.check_audio(spec, path, audio)
    (audio / H.MARKER).write_text(json.dumps({**marker, "tempo": 1.1}))
    H.check_audio(spec, path, audio)
    spec.pop("human_voice_tempo")
    with pytest.raises(SystemExit, match="tempo"):
        H.check_audio(spec, path, audio)


def _zero_crossing_hz(samples, sr):
    flips = sum(1 for x, y in zip(samples, samples[1:]) if (x < 0) != (y < 0))
    return flips / 2 / (len(samples) / sr)


def test_tempo_filter_shortens_the_read_without_moving_its_pitch(tmp_path):
    """The real filter through the real ffmpeg: 1.1x is 1/1.1 the length at the same pitch."""
    import array
    import math
    import os
    import subprocess
    if not os.path.exists(H.FFMPEG) and not __import__("shutil").which(H.FFMPEG):
        pytest.skip("no ffmpeg")
    sr, seconds, hz = 48000, 2.0, 220.0
    tone = array.array("f", (0.5 * math.sin(2 * math.pi * hz * k / sr)
                             for k in range(int(sr * seconds))))
    src = tmp_path / "tone.f32"
    src.write_bytes(tone.tobytes())
    out = subprocess.run([H.FFMPEG, "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1",
                          "-i", str(src), "-af", H.tempo_filter(1.1), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    fast = array.array("f")
    fast.frombytes(out)
    assert len(fast) / sr == pytest.approx(seconds / 1.1, abs=0.03)
    middle = fast[int(0.2 * sr):int(-0.2 * sr)]
    assert _zero_crossing_hz(middle, sr) == pytest.approx(hz, rel=0.01)   # no chipmunk


# --- breaths, shared boundaries, pacing ---------------------------------------------------

LOUD, FLOOR = -20.0, -74.0


def frames(*runs):
    """[(seconds, dB, voiced), ...] -> per-10 ms dB and voicing lists."""
    db, voiced = [], []
    for seconds, level, v in runs:
        n = int(round(seconds / 0.01))
        db += [level] * n
        voiced += [v] * n
    return db, voiced


def test_an_unvoiced_inhale_between_words_becomes_a_breath_span():
    db, voiced = frames((0.5, -20, True), (0.3, -48, False), (0.5, -20, True))
    spans = H.breath_spans(db, voiced, LOUD, FLOOR)
    assert spans == [(0.54, 0.76)]          # 0.5-0.8 less the 40 ms guards


def test_a_short_fricative_and_a_loud_sibilant_are_not_breaths():
    db, voiced = frames((0.5, -20, True), (0.08, -45, False), (0.5, -20, True),
                        (0.25, -26, False), (0.5, -20, True))
    assert H.breath_spans(db, voiced, LOUD, FLOOR) == []


def test_plain_silence_is_left_to_the_gap_trimmer():
    db, voiced = frames((0.5, -20, True), (0.5, -80, False), (0.5, -20, True))
    assert H.breath_spans(db, voiced, LOUD, FLOOR) == []


def test_outside_words_a_louder_or_voiced_inhale_is_a_breath_inside_a_word_it_is_not():
    # -38 dB is above the in-word bar (loud - 22) but under the outside bar (loud - 15)
    db, voiced = frames((0.5, -20, True), (0.4, -38, True), (0.5, -20, True))
    assert H.breath_spans(db, voiced, LOUD, FLOOR) == []
    outside = [False] * len(db)
    assert H.breath_spans(db, voiced, LOUD, FLOOR, in_word=outside) == [(0.54, 0.86)]
    covered = [True] * len(db)
    assert H.breath_spans(db, voiced, LOUD, FLOOR, in_word=covered) == []


def test_word_mask_covers_each_word_shrunk_at_both_ends():
    mask = H.word_mask([{"start": 0.10, "end": 0.30}], 40)
    assert [k for k, m in enumerate(mask) if m] == list(range(14, 27))


def test_back_to_back_takes_split_at_one_quiet_point():
    db = [-20.0] * 100
    db[57] = -70.0                           # the gap between the two words
    point = H.shared_boundary(db, 0.50, 0.62)
    assert point == 0.57
    assert H.shared_boundary(db, 0.62, 0.50) == point      # order does not matter
    # a straddling island split at that point lands in exactly one take
    islands = [(0.2, 0.9)]
    first = H.take_runs(islands, 0.0, point, 0.2, 0.50, cut_before=True, cut_after=False)
    second = H.take_runs(islands, point, 2.0, 0.62, 0.9, cut_before=False, cut_after=True)
    assert first[-1][1] == second[0][0] == point


def test_spec_pacing_sets_targets_and_limits_together():
    p = H.spec_pacing({"human_voice_pacing": {"sentence_gap": 0.2, "pause": 0.15}})
    assert (p.sentence_target, p.scene_gap, p.sentence_limit) == (0.2, 0.2, 0.25)
    assert (p.pause_target, p.pause_limit) == (0.15, 0.30)
    assert H.spec_pacing({}) == H.Pacing()
    with pytest.raises(SystemExit, match="unknown"):
        H.spec_pacing({"human_voice_pacing": {"gap": 0.2}})
    with pytest.raises(SystemExit, match="outside"):
        H.spec_pacing({"human_voice_pacing": {"sentence_gap": 2}})


def test_whisper_thousands_split_in_two_words_is_merged_and_meets_the_script():
    words = [{"text": " More", "start": 0.0, "end": 0.2}, {"text": " 27", "start": 0.6, "end": 1.0},
             {"text": ",000", "start": 1.2, "end": 2.0}, {"text": " acres.", "start": 2.0, "end": 2.4}]
    merged = H.merge_digit_groups(words)
    assert [w["text"].strip() for w in merged] == ["More", "27,000", "acres."]
    assert (merged[1]["start"], merged[1]["end"]) == (0.6, 2.0)
    heard = [w for x in merged for w, _ in H.normalise([x["text"]])]
    assert heard == norm("More than twenty-seven thousand acres.")[:1] + ["27000", "acres"]
    assert H.merge_digit_groups([{"text": ",000", "start": 0, "end": 1}])[0]["text"] == ",000"
