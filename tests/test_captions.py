"""scripts/video/captions.py — word-timed ("karaoke") burned-in captions.

Three things are worth testing here and nowhere else:

  * **the cue rules**, ported from kdeskgames/word-chain/video/captions.mjs: a cue is a phrase
    of at most 3 words / 20 characters, sentences and commas break it, and a cue stays up
    until the next one starts so the top of the frame never flickers between phrases;
  * **the karaoke windows**: word k is lit from its own start until the next word's start, the
    last word until the cue ends, so the phrase is never on screen with nothing lit;
  * **the geometry**, the same way tests/test_media.py guards the attribution watermark: the
    caption band lives inside the Shorts safe zone, above the card overlay, and nowhere near
    the bottom-right corner Google Earth Studio burns its watermark into.

Pure string and arithmetic work — stdlib only, no Chrome, no ffmpeg.
"""
import json
import math
import pathlib

import pytest

import captions as C
import media


def W(text, start, end):
    return {"text": text, "start": start, "end": end}


def texts(cues):
    return [c.text for c in cues]


# --- cue building: the phrase rules -----------------------------------------------------

def test_three_short_words_make_one_cue():
    cues = C.build_cues([W("Magic", 0.0, 0.3), W("Kingdom", 0.3, 0.7), W("now", 0.7, 0.9)])
    assert texts(cues) == ["Magic Kingdom now"]
    assert cues[0].start == pytest.approx(0.0)


def test_a_fourth_word_starts_a_new_cue():
    words = [W(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(4)]
    assert texts(C.build_cues(words)) == ["w0 w1 w2", "w3"]


def test_a_cue_breaks_on_the_character_cap_before_the_word_cap():
    """Two long words already overrun 20 characters, so the third never joins them."""
    cues = C.build_cues([W("Tomorrowland", 0.0, 0.5), W("Speedway", 0.5, 1.0),
                         W("today", 1.0, 1.4)])
    assert texts(cues) == ["Tomorrowland", "Speedway today"]
    for cue in cues:
        assert len(cue.text) <= C.MAX_CHARS


def test_a_sentence_end_always_breaks_the_cue():
    cues = C.build_cues([W("Stop.", 0.0, 0.4), W("Go", 0.5, 0.8), W("on", 0.8, 1.0)])
    assert texts(cues) == ["Stop.", "Go on"]


@pytest.mark.parametrize("word", ["Stop.", "Stop!", "Stop?", "Stop—"])
def test_every_sentence_ending_mark_breaks(word):
    cues = C.build_cues([W(word, 0.0, 0.4), W("next", 0.5, 0.8)])
    assert texts(cues) == [word, "next"]


def test_a_sentence_end_hidden_behind_a_closing_quote_still_breaks():
    cues = C.build_cues([W('"Stop."', 0.0, 0.4), W("Go", 0.5, 0.8)])
    assert texts(cues) == ['"Stop."', "Go"]


@pytest.mark.parametrize("word", ["scores:", "scores;"])
def test_a_trailing_colon_or_semicolon_always_breaks_the_cue(word):
    """A list lead-in like "scores:" must not glue to the list's first item."""
    cues = C.build_cues([W(word, 0.0, 0.4), W("Sat", 0.5, 0.8)])
    assert texts(cues) == [word, "Sat"]


def test_a_comma_breaks_only_once_the_phrase_has_two_words():
    """Otherwise "so," shows up as a card of its own, which reads as a glitch."""
    one = C.build_cues([W("So,", 0.0, 0.3), W("and", 0.3, 0.5), W("then", 0.5, 0.8)])
    assert texts(one) == ["So, and then"]
    two = C.build_cues([W("Wait", 0.0, 0.3), W("here,", 0.3, 0.6), W("then", 0.6, 0.9)])
    assert texts(two) == ["Wait here,", "then"]


def test_a_cue_full_on_words_absorbs_the_word_that_closes_it():
    """Look-ahead grace: the 4th word joins anyway because it closes the phrase and fits."""
    words = [W("one", 0.0, 0.3), W("two", 0.3, 0.6), W("three", 0.6, 0.9),
             W("four,", 0.9, 1.2)]
    cues = C.build_cues(words)
    assert texts(cues) == ["one two three four,"]
    assert len(cues[0].words) == C.MAX_WORDS + 1


def test_the_look_ahead_grace_is_refused_when_the_result_would_run_too_long():
    """Too long even with the grace budget: the closer starts its own cue (old behaviour)."""
    words = [W("one", 0.0, 0.3), W("two", 0.3, 0.6), W("three", 0.6, 0.9),
             W("superlongclosing,", 0.9, 1.2)]
    cues = C.build_cues(words)
    assert texts(cues) == ["one two three", "superlongclosing,"]


def test_five_plain_words_still_split_three_and_two():
    words = [W(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(5)]
    assert texts(C.build_cues(words)) == ["w0 w1 w2", "w3 w4"]


def test_punctuation_stays_attached_to_its_word():
    """A lone comma never breaks (see above), so both marks survive into the one cue."""
    cues = C.build_cues([W("waits,", 0.0, 0.4), W("today.", 0.5, 0.9)])
    assert texts(cues) == ["waits, today."]


def test_no_words_makes_no_cues():
    assert C.build_cues([]) == []
    assert C.build_cues(None) == []


def test_a_word_with_no_usable_timing_is_dropped_rather_than_placed_at_zero():
    cues = C.build_cues([W("good", 0.0, 0.4), W("bad", None, 0.9), W("ok", 1.0, 1.4)])
    assert [w.text for c in cues for w in c.words] == ["good", "ok"]


def test_blank_word_text_is_dropped():
    cues = C.build_cues([W("  ", 0.0, 0.4), W("real", 0.5, 0.9)])
    assert [w.text for c in cues for w in c.words] == ["real"]


# --- cue building: the timeline ---------------------------------------------------------

def test_the_scene_offset_moves_every_cue_onto_the_final_timeline():
    cues = C.build_cues([W("one.", 0.0, 0.4), W("two", 1.0, 1.4)], 12.5)
    assert cues[0].start == pytest.approx(12.5)
    assert cues[0].words[0].start == pytest.approx(12.5)
    assert cues[1].start == pytest.approx(13.5)


def test_a_cue_stays_up_until_the_next_one_starts():
    """No flicker between phrases: the gap belongs to the cue that is already on screen."""
    words = [W("a.", 0.0, 0.4), W("b", 2.0, 2.4)]
    cues = C.build_cues(words)
    assert cues[0].end == pytest.approx(cues[1].start - C.GAP_S)


def test_the_hold_is_capped_so_a_long_silence_does_not_leave_a_cue_on_screen():
    cues = C.build_cues([W("alone.", 0.0, 0.4), W("later", 30.0, 30.4)])
    assert cues[0].end == pytest.approx(0.4 + C.HOLD_CAP_S)


def test_the_last_cue_holds_past_its_final_word_but_no_further_than_the_cap():
    cues = C.build_cues([W("the", 0.0, 0.3), W("end.", 0.3, 0.8)])
    assert len(cues) == 1
    assert cues[0].end == pytest.approx(0.8 + C.HOLD_PAD_S)


def test_a_very_short_cue_is_held_to_a_readable_minimum():
    cues = C.build_cues([W("hi.", 0.0, 0.1)])
    assert cues[0].end - cues[0].start >= C.MIN_CUE_S - 1e-9


def test_a_cue_that_could_never_be_read_is_dropped():
    """Two words 0.05 s apart: the first can hold for at most 0.03 s before the second."""
    cues = C.build_cues([W("a.", 0.0, 0.02), W("b", 0.04, 0.5)])
    assert texts(cues) == ["b"]


def test_the_limit_clamps_captions_to_the_scene_they_belong_to():
    cues = C.build_cues([W("last.", 0.0, 0.5)], 10.0, limit=10.7)
    assert cues[0].end == pytest.approx(10.7)


def test_a_limit_before_the_cue_could_be_read_drops_it():
    assert C.build_cues([W("last.", 0.0, 0.5)], 10.0, limit=10.05) == []


# --- the karaoke windows ----------------------------------------------------------------

def test_each_word_is_lit_from_its_own_start_until_the_next_word_starts():
    cues = C.build_cues([W("one", 0.0, 0.3), W("two", 0.4, 0.7), W("three", 0.8, 1.1)])
    wins = C.word_windows(cues)
    assert [(w.cue, w.word) for w in wins] == [(0, 0), (0, 1), (0, 2)]
    assert wins[0].start == pytest.approx(cues[0].start)
    assert wins[0].end == pytest.approx(0.4)
    assert wins[1].start == pytest.approx(0.4)
    assert wins[1].end == pytest.approx(0.8)


def test_the_last_word_stays_lit_until_the_cue_ends():
    """Otherwise the phrase sits on screen with nothing lit, which reads as a stuck frame."""
    cues = C.build_cues([W("one", 0.0, 0.3), W("two.", 0.4, 0.7)])
    wins = C.word_windows(cues)
    assert wins[-1].end == pytest.approx(cues[0].end)


def test_the_first_word_is_lit_from_the_cue_start_not_from_its_own():
    cues = C.build_cues([W("a.", 0.0, 0.3), W("b", 2.0, 2.3)])
    wins = C.word_windows(cues)
    second = [w for w in wins if w.cue == 1][0]
    assert second.start == pytest.approx(cues[1].start)


def test_the_windows_of_one_cue_tile_it_with_no_gap_and_no_overlap():
    cues = C.build_cues([W("one", 0.0, 0.3), W("two", 0.4, 0.7), W("three.", 0.8, 1.1)])
    wins = C.word_windows(cues)
    assert wins[0].end == pytest.approx(wins[1].start)
    assert wins[1].end == pytest.approx(wins[2].start)
    assert wins[-1].end == pytest.approx(cues[0].end)


def test_a_window_too_short_to_see_is_dropped():
    cues = [C.Cue(text="a b", start=0.0, end=1.0,
                  words=(C.Word("a", 0.0, 0.005), C.Word("b", 0.005, 1.0)))]
    assert [w.word for w in C.word_windows(cues)] == [1]


def test_no_cues_means_no_windows():
    assert C.word_windows([]) == []


# --- geometry: the band ------------------------------------------------------------------

SIZES = [(1080, 1920), (1296, 2304)]


@pytest.mark.parametrize("w,h", SIZES)
def test_the_band_sits_in_the_top_fifth_of_the_frame(w, h):
    left, top, right, bottom = C.caption_box(w, h)
    centre = (top + bottom) / 2 / h
    assert centre == pytest.approx(C.BAND_CENTER_FRAC, abs=0.005)
    assert top > 0 and bottom < h


@pytest.mark.parametrize("w,h", SIZES)
def test_the_band_stays_inside_the_shorts_safe_zone(w, h):
    """Middle 80% of the width, nothing below 75% of the height — the platform's own rule."""
    left, top, right, bottom = C.caption_box(w, h)
    assert left >= round(w * 0.10)
    assert right <= w - round(w * 0.10)
    assert bottom <= round(h * C.SAFE_BOTTOM_FRAC)


@pytest.mark.parametrize("w,h", SIZES)
def test_the_band_never_reaches_the_attribution_watermark(w, h):
    assert not media.boxes_overlap(C.caption_box(w, h), media.watermark_box(w, h))


@pytest.mark.parametrize("w,h", SIZES)
def test_the_band_never_collides_with_the_card_overlay_of_a_media_scene(w, h):
    card = media.overlay_box(w, h)
    assert not media.boxes_overlap(C.caption_box(w, h, card_top=card[1]), card)
    assert C.caption_box(w, h, card_top=card[1])[3] < card[1]


@pytest.mark.parametrize("w,h", SIZES)
def test_the_band_is_unchanged_by_a_card_that_sits_below_it(w, h):
    """The stock card overlay starts at 40% of the frame; the band ends far above it."""
    assert C.caption_box(w, h, card_top=media.overlay_box(w, h)[1]) == C.caption_box(w, h)


def test_a_card_whose_top_reaches_into_the_band_shrinks_the_band():
    plain = C.caption_box(1080, 1920)
    tight = C.caption_box(1080, 1920, card_top=plain[3] - 40)
    assert tight[3] < plain[3]
    assert tight[1] == plain[1], "the band shrinks from the bottom before it moves"
    assert not media.boxes_overlap(tight, (0, plain[3] - 40, 1080, 1920))


def test_a_card_high_enough_to_squeeze_the_band_moves_it_up_instead():
    plain = C.caption_box(1080, 1920)
    high = C.caption_box(1080, 1920, card_top=round(1920 * 0.18))
    assert high[1] < plain[1], "the band moved up to keep a readable height"
    assert high[3] <= round(1920 * 0.18) - round(1920 * C.CLEARANCE_FRAC)
    assert high[3] - high[1] >= round(1920 * C.MIN_BAND_H_FRAC)


def test_a_card_that_owns_the_whole_top_of_the_frame_is_refused_not_overlapped():
    with pytest.raises(ValueError) as exc:
        C.caption_box(1080, 1920, card_top=round(1920 * 0.05))
    assert "caption" in str(exc.value).lower()


# --- the HTML ----------------------------------------------------------------------------

BRAND = {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"}


def _tokens():
    import cards
    return cards.brand_tokens(BRAND)


def _cue():
    return C.build_cues([W("Magic", 0.0, 0.3), W("Kingdom", 0.4, 0.8)])[0]


def test_the_lit_word_carries_the_accent_and_the_others_do_not():
    doc = C.caption_html(_cue(), 1, "#ffe234", _tokens(), 1080, C.caption_box(1080, 1920))
    assert '<span class="lit">Kingdom</span>' in doc
    assert "<span>Magic</span>" in doc
    assert "#ffe234" in doc


def test_every_word_of_the_cue_is_on_every_frame_so_only_the_colour_moves():
    box = C.caption_box(1080, 1920)
    for lit in (0, 1):
        doc = C.caption_html(_cue(), lit, "#ffe234", _tokens(), 1080, box)
        assert "Magic" in doc and "Kingdom" in doc


def test_the_page_is_the_band_not_the_whole_frame():
    """The PNG is overlaid at the band's own y, so a 1920-tall page would waste 6x the memory."""
    box = C.caption_box(1080, 1920)
    doc = C.caption_html(_cue(), 0, "#ffe234", _tokens(), 1080, box)
    assert f"width:1080px;height:{box[3] - box[1]}px" in doc
    assert "background:transparent" in doc


def test_the_side_padding_is_the_safe_zone_margin():
    box = C.caption_box(1080, 1920)
    doc = C.caption_html(_cue(), 0, "#ffe234", _tokens(), 1080, box)
    assert f"padding:0 {box[0]}px" in doc


def test_word_text_is_html_escaped():
    cue = C.build_cues([W("<b>&", 0.0, 0.4)])[0]
    doc = C.caption_html(cue, 0, "#ffe234", _tokens(), 1080, C.caption_box(1080, 1920))
    assert "<b>&" not in doc.split("<style>")[-1].split("</style>")[-1].replace("&lt;b&gt;&amp;", "")
    assert "&lt;b&gt;&amp;" in doc


def test_a_non_hex_accent_is_refused_because_it_lands_in_css_unescaped():
    with pytest.raises(ValueError):
        C.caption_html(_cue(), 0, "red; } body{display:none", _tokens(), 1080,
                       C.caption_box(1080, 1920))


def test_a_long_cue_is_typeset_smaller_so_it_stays_on_one_line():
    box = C.caption_box(1080, 1920)
    short = C.font_size("Go", box)
    long = C.font_size("Tomorrowland waits", box)
    assert long < short
    assert C.MIN_FONT_PX <= long


# --- the spec surface ---------------------------------------------------------------------

def test_captions_are_off_unless_a_spec_asks_for_them():
    """Every existing KDesk spec renders byte-identically until it opts in."""
    assert C.settings({}).enabled is False
    assert C.settings({"slug": "asc842"}).enabled is False


def test_the_spec_block_turns_them_on_with_its_own_accent():
    cfg = C.settings({"captions": {"enabled": True, "accent": "#FFD966", "position": "top"}})
    assert (cfg.enabled, cfg.accent, cfg.position) == (True, "#FFD966", "top")


def test_the_accent_defaults_to_the_reference_yellow():
    assert C.settings({"captions": {"enabled": True}}).accent == C.DEFAULT_ACCENT == "#ffe234"


@pytest.mark.parametrize("override,expected", [(True, True), (False, False)])
def test_the_command_line_override_wins_over_the_spec(override, expected):
    assert C.settings({"captions": {"enabled": not expected}}, override).enabled is expected
    assert C.settings({}, override).enabled is expected


def test_no_override_leaves_the_spec_alone():
    assert C.settings({"captions": {"enabled": True}}, None).enabled is True


def test_an_unknown_captions_key_is_an_error_rather_than_silently_ignored():
    with pytest.raises(KeyError):
        C.settings({"captions": {"enabled": True, "colour": "#fff"}})


def test_a_non_hex_accent_in_the_spec_is_refused():
    with pytest.raises(ValueError):
        C.settings({"captions": {"enabled": True, "accent": "yellow"}})


def test_an_unknown_position_is_refused_by_name():
    with pytest.raises(ValueError) as exc:
        C.settings({"captions": {"enabled": True, "position": "bottom"}})
    assert "top" in str(exc.value)


def test_a_captions_block_that_is_not_a_mapping_is_refused():
    with pytest.raises(TypeError):
        C.settings({"captions": True})


# --- the words file -----------------------------------------------------------------------

def test_the_words_file_sits_beside_the_scene_wav():
    assert C.words_path(pathlib.Path("/b/audio/scene_03.wav")) == \
        pathlib.Path("/b/audio/scene_03.words.json")


def test_words_round_trip_through_the_file(tmp_path):
    wav = tmp_path / "scene_00.wav"
    words = [{"text": "Magic", "start": 0.12, "end": 0.41}]
    C.write_words(wav, words)
    assert json.loads(C.words_path(wav).read_text()) == words
    assert C.read_words(wav) == words


def test_a_scene_with_no_timings_is_written_as_null_and_reads_back_as_none(tmp_path):
    wav = tmp_path / "scene_00.wav"
    C.write_words(wav, None)
    assert C.words_path(wav).read_text() == "null"
    assert C.read_words(wav) is None


def test_a_missing_or_corrupt_words_file_reads_as_none(tmp_path):
    assert C.read_words(tmp_path / "scene_00.wav") is None
    C.words_path(tmp_path / "scene_01.wav").write_text("{not json")
    assert C.read_words(tmp_path / "scene_01.wav") is None


def test_the_words_file_is_written_atomically(tmp_path):
    """A crash mid-write must not leave half a JSON array in the cache beside a good WAV."""
    wav = tmp_path / "scene_00.wav"
    C.write_words(wav, [{"text": "a", "start": 0.0, "end": 0.1}])
    assert [p.name for p in sorted(tmp_path.iterdir())] == ["scene_00.words.json"]


def test_a_list_lead_in_and_its_items_each_land_on_their_own_card():
    """The real-render regression: "scores:" used to glue to "Sat", and the 3-word cap fired
    before each item's closing comma arrived, scrambling the list into "10, Sat Oct" etc.
    """
    text = ("the highest crowd scores: Sat Oct 10, Sat Oct 3, Sat Sep 26. "
            "Scores come from").split()
    words = [W(w, i * 0.35, i * 0.35 + 0.35) for i, w in enumerate(text)]
    cues = C.build_cues(words)
    assert texts(cues) == [
        "the highest crowd", "scores:", "Sat Oct 10,", "Sat Oct 3,", "Sat Sep 26.",
        "Scores come from",
    ]


# --- end to end over one scene's worth of words -------------------------------------------

def test_a_paragraph_of_words_becomes_readable_cues_that_never_overlap():
    text = ("This scene is a still photograph, not a rendered card. It fills the whole "
            "frame, and the card you can read sits on top of it.").split()
    words = [W(w, i * 0.32, i * 0.32 + 0.28) for i, w in enumerate(text)]
    cues = C.build_cues(words, 3.0)
    assert len(cues) > 5
    for cue in cues:
        assert len(cue.words) <= C.MAX_WORDS
        assert cue.end > cue.start
    for a, b in zip(cues, cues[1:]):
        assert a.end <= b.start, "two cues on screen at once would overprint"
    wins = C.word_windows(cues)
    assert len(wins) >= len(cues)
    for a, b in zip(wins, wins[1:]):
        assert a.end <= b.start + 1e-9
    assert all(not math.isinf(w.end) for w in wins)


def test_a_spelled_out_date_stays_on_one_card_even_when_the_cue_filled_on_characters():
    """"Saturday, October" is only two words but already 17 characters, so the word-count
    grace alone would still orphan "10,". The grace fires on either cap, and a short closing
    numeral joins its date."""
    text = "the highest crowd scores: Saturday, October 10, Saturday, September 26. Scores come from"
    words = [{"text": w, "start": i * 0.35, "end": i * 0.35 + 0.3} for i, w in enumerate(text.split())]
    cues = [c.text for c in C.build_cues(words)]
    assert "Saturday, October 10," in cues
    assert "Saturday, September 26." in cues
    assert not any(c.startswith("10,") or c.startswith("26.") for c in cues)


def test_a_long_closing_word_is_not_rescued_so_prose_keeps_its_rhythm():
    text = "this is not a rendered card. more words here"
    words = [{"text": w, "start": i * 0.35, "end": i * 0.35 + 0.3} for i, w in enumerate(text.split())]
    cues = [c.text for c in C.build_cues(words)]
    assert all(len(c.split()) <= 3 for c in cues)


def test_caption_overlays_render_in_all_caps_without_changing_the_cue_text():
    """Stephen wants the burned-in captions in capitals; the transform is CSS so the karaoke
    windows, words.json and the cue text stay exactly as spoken."""
    doc = C.caption_html(_cue(), 0, "#ffe234", _tokens(), 1080, C.caption_box(1080, 1920))
    assert "text-transform:uppercase" in doc
    assert "<span>Kingdom</span>" in doc  # source text untouched; the capitals are CSS
