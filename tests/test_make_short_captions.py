"""make_short.py's caption pass, with the ffmpeg and Chrome seams stubbed.

Same shape as tests/test_make_short_media.py: `run()` is the single seam every ffmpeg
invocation goes through and `R.screenshot` the single seam every Chrome invocation goes
through, so stubbing both lets us assert the exact composite ffmpeg is asked to build without
waiting on an encode.

What matters here and nowhere else:

  * **captions are off unless a spec asks.** Every walkthrough Short in marketing/video/
    predates them, and the final pass has to stay the byte-identical `-c:v copy` concat it has
    always been until a spec opts in.
  * **the word windows sit on the CONCATENATED timeline.** Each scene's words are timed
    against its own WAV; the offset is the sum of the parts already encoded, measured from the
    encoded parts themselves rather than from the nominal durations, because `-t 4.633` at
    30 fps lands on a frame boundary and a frame of drift per scene is visible karaoke.
  * **one encode, not two.** The concat pass was a stream copy; captions turn it into the
    single re-encode, with loudnorm in the same filter graph, rather than adding a pass.
  * **the band clears the card**, geometrically, the way tests/test_media.py keeps plates off
    the attribution watermark.
"""
import json
import pathlib
import sys
import types

import pytest

import captions
import cards
import make_short as M
import media

BRAND = {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"}
CREDIT = "Imagery: placeholder"
OVERLAY = {"template": "ranked_list",
           "data": {"heading": "Shortest waits", "subheading": "Magic Kingdom",
                    "items": [{"rank": 1, "label": "Speedway", "value": 5}],
                    "footer": "parksheet.com"}}

#: Three words a scene, plainly timed, so the cue arithmetic in a test is readable by eye.
WORDS = {
    0: [{"text": "Magic", "start": 0.3, "end": 0.8},
        {"text": "Kingdom", "start": 0.9, "end": 1.5},
        {"text": "waits.", "start": 1.6, "end": 2.2}],
    1: [{"text": "Five", "start": 0.3, "end": 0.7},
        {"text": "minutes.", "start": 0.8, "end": 1.4}],
    2: [{"text": "Go", "start": 0.3, "end": 0.6},
        {"text": "now.", "start": 0.7, "end": 1.1}],
}
DURATIONS = {"0": 4.0, "1": 5.0, "2": 6.0}

#: What the stubbed ffprobe reports for each encoded part. Deliberately NOT durations+0.6, so
#: a test can tell whether the offsets came from the encoded part or from the nominal length.
PART_SECONDS = 6.0
END_SECONDS = 1.5


def _spec(captions_block=None):
    spec = {
        "slug": "cap-demo",
        "brand": dict(BRAND),
        "short": {"hook": "Three scenes", "scenes": [0, 1, 2], "cta": "More → parksheet.com"},
        "scenes": [
            {"kind": "media", "src": "assets/still.png", "motion": "kenburns",
             "credit": CREDIT, "overlay": dict(OVERLAY), "narration": "one"},
            {"kind": "media", "src": "assets/clip.mp4", "motion": "clip",
             "credit": CREDIT, "narration": "two"},
            {"kind": "media", "src": "assets/clip.mp4", "motion": "hold",
             "credit": CREDIT, "overlay": dict(OVERLAY), "narration": "three"},
        ],
    }
    if captions_block is not None:
        spec["captions"] = captions_block
    return spec


def _card(heading):
    return {"kind": "card", "template": "countdown",
            "data": {"heading": heading, "items": [], "footer": "x"}, "narration": heading}


def _with_card_scene(captions_block=None):
    """The same Short with a full-frame `kind: card` in the middle."""
    spec = _spec(captions_block)
    spec["scenes"][1] = _card("Two")
    return spec


def _card_only(captions_block=None):
    """A card-only data Short: no imagery at all. The case captions help most."""
    spec = _spec(captions_block)
    spec["scenes"] = [_card("One"), _card("Two"), _card("Three")]
    return spec


def _legacy_scene():
    """The pre-card walkthrough layout: a spreadsheet range under the Short's hook band."""
    return {"sheet": "Lease", "caption": "a legacy walkthrough scene", "narration": "legacy"}


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """Drive main() over a mixed spec with ffmpeg, ffprobe and Chrome all stubbed."""
    holder = types.SimpleNamespace(spec=_spec({"enabled": True, "accent": "#ffe234"}),
                                   words=dict(WORDS))
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
    build = tmp_path / "build" / "cap-demo"
    audio = build / "audio"
    audio.mkdir(parents=True)
    (audio / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of",
                        lambda p: END_SECONDS if pathlib.Path(p).name == "end.mp4"
                        else PART_SECONDS)
    monkeypatch.setattr(M, "subprocess", types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    shots, cmds, drawn = [], [], []
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: shots.append((a, k)))
    monkeypatch.setattr(M.R, "render_card_scene", lambda *a, **k: drawn.append((a, k)))
    monkeypatch.setattr(M, "run", cmds.append)
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(spec_path)])
    holder.build, holder.shots, holder.cmds, holder.cards = build, shots, cmds, drawn
    holder.work = build / "short"
    holder.audio = audio

    def go(*extra):
        for idx, words in holder.words.items():
            captions.write_words(audio / f"scene_{idx:02d}.wav", words)
        monkeypatch.setattr(sys, "argv",
                            ["make_short.py", "--spec", str(spec_path), *extra])
        M.main()

    holder.go = go
    return holder


def _final(stub):
    """The last ffmpeg call: the concat that writes the delivered mp4."""
    return [c for c in stub.cmds if "concat" in c][-1]


def _chain(cmd):
    return cmd[cmd.index("-filter_complex") + 1].split(";")


def _windows(cmd):
    """(start, end) of every caption overlay in the final pass, in order."""
    out = []
    for step in _chain(cmd):
        if "enable='between(t," in step:
            body = step.split("enable='between(t,")[1].split(")'")[0]
            a, b = body.split(",")
            out.append((float(a), float(b)))
    return out


def _caption_pngs(stub):
    return [a[1] for a, _k in stub.shots if "cap_" in pathlib.Path(a[1]).name]


# --- off by default -----------------------------------------------------------------------

def test_a_spec_that_says_nothing_renders_the_concat_it_always_did(stub):
    """The goldens and every existing Short depend on this pass staying a stream copy."""
    stub.spec = _spec()
    stub.go()
    cmd = _final(stub)
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-filter_complex" not in cmd
    assert cmd[cmd.index("-af") + 1] == "loudnorm=I=-16:TP=-1.5:LRA=11"


def test_nothing_is_rendered_or_read_for_a_spec_with_captions_off(stub):
    stub.spec = _spec({"enabled": False})
    stub.go()
    assert _caption_pngs(stub) == []


def test_captions_off_never_calls_ffprobe_on_the_parts(stub, monkeypatch):
    """dur_of is ffprobe. Uncaptioned, the only probe is the length check on the finished
    Short, exactly as before; captioned, each part is measured so the offsets cannot drift."""
    probed = []
    monkeypatch.setattr(M, "dur_of", lambda p: probed.append(pathlib.Path(p).name) or 6.0)
    stub.spec = _spec()
    stub.go()
    assert probed == ["cap-demo-short.mp4"]
    probed.clear()
    stub.spec = _spec({"enabled": True})
    stub.go()
    assert probed == ["scene_0.mp4", "scene_1.mp4", "scene_2.mp4", "end.mp4",
                      "cap-demo-short.mp4"]


# --- the caption pass ---------------------------------------------------------------------

def test_the_final_pass_burns_one_overlay_per_spoken_word(stub):
    stub.go()
    cmd = _final(stub)
    spoken = sum(len(w) for w in WORDS.values())
    assert len(_windows(cmd)) == spoken
    assert len(_caption_pngs(stub)) == spoken


def test_every_caption_png_is_an_input_to_the_final_pass_in_order(stub):
    stub.go()
    cmd = _final(stub)
    inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
    assert [str(p) for p in _caption_pngs(stub)] == [str(p) for p in inputs[1:]]


def test_each_overlay_is_gated_to_its_own_word_window(stub):
    stub.go()
    wins = _windows(_final(stub))
    for start, end in wins:
        assert end > start
    for (_a, a_end), (b_start, _b) in zip(wins, wins[1:]):
        assert a_end <= b_start + 1e-6, "two caption frames on screen at once would overprint"


def test_the_word_windows_sit_on_the_concatenated_timeline_not_the_scenes_own(stub):
    """Scene 1's first word is 0.3 s into its WAV and 6.3 s into the Short."""
    stub.go()
    wins = _windows(_final(stub))
    assert wins[0][0] == pytest.approx(0.3, abs=0.01)
    scene_one = [w for w in wins if PART_SECONDS <= w[0] < 2 * PART_SECONDS]
    assert scene_one and scene_one[0][0] == pytest.approx(PART_SECONDS + 0.3, abs=0.01)
    scene_two = [w for w in wins if 2 * PART_SECONDS <= w[0]]
    assert scene_two and scene_two[0][0] == pytest.approx(2 * PART_SECONDS + 0.3, abs=0.01)


def test_no_caption_outlives_the_scene_it_belongs_to(stub):
    """A held phrase must not bleed over a cut onto the next scene's footage."""
    stub.go()
    for start, end in _windows(_final(stub)):
        assert end <= (int(start // PART_SECONDS) + 1) * PART_SECONDS + 1e-6


def test_captions_never_run_past_the_end_card(stub):
    stub.go()
    total = 3 * PART_SECONDS + END_SECONDS
    assert max(end for _s, end in _windows(_final(stub))) <= total


# --- one encode, not two -------------------------------------------------------------------

def test_the_captioned_final_pass_re_encodes_once_with_loudnorm_in_the_same_graph(stub):
    stub.go()
    cmd = _final(stub)
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-af" not in cmd, "loudnorm belongs in the one filter graph, not a second pass"
    assert any("loudnorm=I=-16:TP=-1.5:LRA=11" in step for step in _chain(cmd))
    assert cmd[cmd.index("-map") + 1] == "[vout]"
    assert "[aout]" in cmd


def test_the_captioned_output_keeps_the_limited_range_tagging_of_every_part(stub):
    stub.go()
    cmd = _final(stub)
    assert cmd[cmd.index("-color_range") + 1] == "tv"
    assert cmd[cmd.index("-bsf:v") + 1] == M.RANGE_BSF
    assert cmd[cmd.index("-r") + 1] == str(M.FPS)


def test_there_is_still_exactly_one_pass_that_writes_the_delivered_file(stub):
    stub.go()
    final = str(M.short_paths(stub.build, "cap-demo", None).final)
    written = [c for c in stub.cmds if str(c[-1]) == final]
    assert len(written) == 1, "captions must not add a second full re-encode"


# --- geometry ------------------------------------------------------------------------------

def test_the_overlays_land_on_the_caption_band_and_nowhere_else(stub):
    stub.go()
    box = captions.caption_box(M.OUT_W, M.OUT_H, media.overlay_box(M.OUT_W, M.OUT_H)[1])
    for step in _chain(_final(stub)):
        if "overlay=" in step:
            assert f"overlay=x=0:y={box[1]}:" in step


def test_the_band_clears_the_card_overlay_of_a_media_scene(stub):
    stub.go()
    box, skipped = M.caption_plan(stub.spec, stub.spec["short"])
    card = media.overlay_box(M.OUT_W, M.OUT_H)
    assert skipped == set()
    assert not media.boxes_overlap(box, card)
    assert not media.boxes_overlap(box, media.watermark_box(M.OUT_W, M.OUT_H))
    assert box[3] <= round(M.OUT_H * captions.SAFE_BOTTOM_FRAC)


def test_a_spec_with_no_card_overlay_still_gets_the_same_band(stub):
    """The stock card starts at 40% of the frame, far below a band centred on 22%."""
    plain = dict(stub.spec)
    plain["scenes"] = [dict(s) for s in stub.spec["scenes"]]
    for scene in plain["scenes"]:
        scene.pop("overlay", None)
    assert M.caption_plan(plain, plain["short"])[0] == \
        captions.caption_box(M.OUT_W, M.OUT_H)


# --- a scene whose own layout owns the top of the frame ---------------------------------------

def test_a_media_scenes_card_is_the_only_thing_that_constrains_the_band():
    scene = {"kind": "media", "src": "x.mp4", "overlay": dict(OVERLAY)}
    assert M.scene_card_top(scene) == media.overlay_box(M.OUT_W, M.OUT_H)[1]
    assert M.scene_card_top({"kind": "media", "src": "x.mp4"}) is None


def test_a_legacy_sheet_scene_still_owns_the_top_of_the_frame():
    """Its hook band starts at y=0 and there is nowhere else for it to go."""
    assert M.scene_card_top(_legacy_scene()) == 0


def test_a_card_scene_reports_the_box_it_will_be_moved_into():
    """A card scene is not skipped: the CARD moves below the band, so it constrains nothing."""
    card_top = M.scene_card_top(_card("One"))
    assert card_top == M.card_box_under_captions(M.OUT_W, M.OUT_H)[1]
    assert card_top > captions.caption_box(M.OUT_W, M.OUT_H)[3]


def test_the_card_box_starts_below_the_caption_band_with_clearance():
    for width, height in ((M.OUT_W, M.OUT_H), (M.RW, M.RH)):
        band = captions.caption_box(width, height)
        left, top, box_w, box_h = M.card_box_under_captions(width, height)
        assert top >= band[3] + round(height * captions.CLEARANCE_FRAC)
        assert not media.boxes_overlap(band, (left, top, left + box_w, top + box_h))
        assert top + box_h == height, "the card still runs to the bottom of the frame"
        assert left == round(width * media.SAFE_X_FRAC) and left + box_w == width - left


def test_a_card_scene_no_longer_constrains_the_band(stub):
    stub.spec = _with_card_scene({"enabled": True})
    box, skipped = M.caption_plan(stub.spec, stub.spec["short"])
    assert skipped == set()
    assert box == captions.caption_box(M.OUT_W, M.OUT_H,
                                       media.overlay_box(M.OUT_W, M.OUT_H)[1])


def test_a_card_scene_is_drawn_into_that_box_when_captions_are_on(stub):
    stub.spec = _with_card_scene({"enabled": True})
    stub.go()
    assert len(stub.cards) == 1
    _args, kwargs = stub.cards[0]
    assert kwargs["box"] == M.card_box_under_captions(M.RW, M.RH)


def test_a_card_scene_is_drawn_full_frame_when_captions_are_off(stub):
    """The captions-off path has to stay byte-identical: the goldens depend on it."""
    stub.spec = _with_card_scene()
    stub.go()
    assert stub.cards[0][1].get("box") is None


def test_every_scene_of_a_card_only_short_is_captioned(stub):
    """A card-only data Short is the case captions help most; none of it may be skipped."""
    stub.spec = _card_only({"enabled": True})
    assert M.caption_plan(stub.spec, stub.spec["short"])[1] == set()
    stub.go()
    assert len(_caption_pngs(stub)) == sum(len(w) for w in WORDS.values())
    assert all(k["box"] == M.card_box_under_captions(M.RW, M.RH) for _a, k in stub.cards)


def test_a_card_scene_is_captioned_alongside_the_media_scenes(stub):
    stub.spec = _with_card_scene({"enabled": True})
    stub.go()
    wins = _windows(_final(stub))
    assert len(wins) == sum(len(w) for w in WORDS.values())
    assert any(PART_SECONDS <= start < 2 * PART_SECONDS for start, _e in wins)


# --- the plan that was actually burned in --------------------------------------------------------

def test_the_burned_in_caption_plan_is_written_beside_the_parts(stub):
    """So a pixel test over a finished Short reads what was rendered, not a re-derivation.

    Re-deriving the windows from the spec would let a broken render agree with a broken
    derivation, and it would need a YAML parser the bare pytest environment does not have.
    """
    stub.go()
    plan = json.loads((stub.work / "captions.json").read_text(encoding="utf-8"))
    assert plan["band"] == list(M.caption_plan(stub.spec, stub.spec["short"])[0])
    assert plan["accent"] == "#ffe234"
    assert len(plan["windows"]) == sum(len(w) for w in WORDS.values())
    first = plan["windows"][0]
    assert first["lit"] == "Magic" and first["text"].startswith("Magic")
    assert first["png"] == "cap_0000.png"
    assert (first["start"], first["end"]) == _windows(_final(stub))[0]


def test_every_plan_row_names_the_png_that_ffmpeg_was_given(stub):
    stub.go()
    plan = json.loads((stub.work / "captions.json").read_text(encoding="utf-8"))
    assert [row["png"] for row in plan["windows"]] == \
        [p.name for p in _caption_pngs(stub)]
    assert [(row["start"], row["end"]) for row in plan["windows"]] == _windows(_final(stub))


def test_no_plan_is_written_when_nothing_was_burned_in(stub):
    stub.spec = _spec()
    stub.go()
    assert not (stub.work / "captions.json").exists()


# --- render_sheets passes the box through -------------------------------------------------------

def test_render_card_scene_hands_its_box_to_the_card_renderer(tmp_path, monkeypatch):
    """cards.card_html has taken a `box` since the media overlay landed; nothing passed one."""
    import render_sheets as R
    monkeypatch.setattr(R, "screenshot", lambda *a, **k: None)
    box = M.card_box_under_captions(M.RW, M.RH)
    data = {"heading": "Two", "items": [], "footer": "x"}
    R.render_card_scene(tmp_path / "scene_0.png", "countdown", data, BRAND,
                        M.RW, M.RH, html_dir=tmp_path, box=box)
    # A card scene FILLS its box; only the media overlay plate hugs its rows.
    assert (tmp_path / "scene_0.html").read_text(encoding="utf-8") == \
        cards.card_html("countdown", data, cards.brand_tokens(BRAND), M.RW, M.RH,
                        box=box, fill=True)


def test_render_card_scene_without_a_box_is_the_full_frame_card_it_always_was(tmp_path,
                                                                              monkeypatch):
    """The captions-off path, byte for byte — every existing card Short depends on it."""
    import render_sheets as R
    monkeypatch.setattr(R, "screenshot", lambda *a, **k: None)
    data = {"heading": "Two", "items": [], "footer": "x"}
    R.render_card_scene(tmp_path / "scene_0.png", "countdown", data, BRAND,
                        M.RW, M.RH, html_dir=tmp_path)
    assert (tmp_path / "scene_0.html").read_text(encoding="utf-8") == \
        cards.card_html("countdown", data, cards.brand_tokens(BRAND), M.RW, M.RH)


# --- the scenes that genuinely cannot be captioned ----------------------------------------------

def test_caption_plan_skips_a_scene_whose_own_layout_owns_the_top_of_the_frame():
    spec = _spec({"enabled": True})
    spec["scenes"][1] = _legacy_scene()
    box, skipped = M.caption_plan(spec, spec["short"])
    assert skipped == {1}
    assert box == captions.caption_box(M.OUT_W, M.OUT_H,
                                       media.overlay_box(M.OUT_W, M.OUT_H)[1])


def test_caption_cues_says_out_loud_which_scenes_it_skipped(tmp_path, capsys):
    captions.write_words(tmp_path / "scene_00.wav", WORDS[0])
    captions.write_words(tmp_path / "scene_01.wav", WORDS[1])
    cues = M.caption_cues([(0, 0.0, 6.0), (1, 6.0, 12.0)], tmp_path, skipped={1})
    out = capsys.readouterr().out
    assert "scene 01" in out and "captions skipped" in out
    assert cues and all(c.start < 6.0 for c in cues)


def test_the_caption_pngs_are_the_band_not_the_whole_frame(stub):
    """A full-frame RGBA PNG per spoken word is six times the memory for nothing."""
    stub.go()
    box = M.caption_plan(stub.spec, stub.spec["short"])[0]
    for args, kwargs in stub.shots:
        if "cap_" in pathlib.Path(args[1]).name:
            assert args[2:] == (M.OUT_W, box[3] - box[1])
            assert kwargs["transparent"] is True


def test_the_caption_html_is_written_beside_its_png(stub):
    stub.go()
    doc = (stub.work / "cap_0000.html").read_text(encoding="utf-8")
    assert "Magic" in doc and "#ffe234" in doc
    assert cards.brand_tokens(BRAND)["font"] in doc


# --- missing timings -------------------------------------------------------------------------

def test_a_scene_with_no_word_timings_is_skipped_with_a_line(stub, capsys):
    stub.words = {0: WORDS[0], 1: None, 2: WORDS[2]}
    stub.go()
    out = capsys.readouterr().out
    assert "scene 01" in out and "captions" in out
    wins = _windows(_final(stub))
    assert not any(PART_SECONDS <= start < 2 * PART_SECONDS for start, _e in wins)
    assert len(wins) == len(WORDS[0]) + len(WORDS[2])


def test_a_short_with_no_timings_at_all_falls_back_to_the_plain_concat(stub, capsys):
    stub.words = {0: None, 1: None, 2: None}
    stub.go()
    cmd = _final(stub)
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert _caption_pngs(stub) == []


def test_asking_for_captions_and_getting_none_says_so_instead_of_going_quiet(stub, capsys):
    """Silently shipping an uncaptioned Short is how a broken narrate.py run goes unnoticed."""
    stub.words = {0: None, 1: None, 2: None}
    stub.go()
    out = capsys.readouterr().out
    assert "captions: enabled, but no scene produced a window" in out


def test_a_short_that_did_produce_windows_does_not_print_the_empty_summary(stub, capsys):
    stub.go()
    out = capsys.readouterr().out
    assert "no scene produced a window" not in out
    assert "word windows burned in" in out


def test_captions_off_prints_neither_summary(stub, capsys):
    stub.spec = _spec()
    stub.go()
    out = capsys.readouterr().out
    assert "captions:" not in out


# --- the command line -------------------------------------------------------------------------

def test_the_captions_flag_turns_them_on_for_a_spec_that_does_not_ask(stub):
    stub.spec = _spec()
    stub.go("--captions")
    assert _caption_pngs(stub)
    assert _final(stub)[_final(stub).index("-c:v") + 1] == "libx264"


def test_no_captions_wins_over_a_spec_that_asks_for_them(stub):
    stub.go("--no-captions")
    assert _caption_pngs(stub) == []
    assert _final(stub)[_final(stub).index("-c:v") + 1] == "copy"


def test_the_spec_accent_reaches_the_rendered_html(stub):
    stub.spec = _spec({"enabled": True, "accent": "#FFD966"})
    stub.go()
    assert "#FFD966" in (stub.work / "cap_0000.html").read_text(encoding="utf-8")
