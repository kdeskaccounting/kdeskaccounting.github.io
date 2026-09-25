"""scripts/video/cards.py — 9:16 HTML cards for the `card` scene kind.

The `data:` block a card scene carries is fixed by the caller's contract: every template gets
exactly `heading`, `subheading`, `items`, `footer`. `ranked_list` and `countdown` items are
`{rank, label, value}` (countdown's ranks descend in list order); `changed` items are
`{label, value}` with no rank and a full sentence for the value. Nothing here touches the
filesystem or the network, so it runs in the bare `uv run --with pytest` environment.
"""
import os
import pathlib
import re

import pytest

import cards

GOLDEN = pathlib.Path(__file__).parent / "golden"

RANKED = {
    "heading": "Shortest waits right now",
    "subheading": "Magic Kingdom · minutes · 2026-09-14",
    "items": [
        {"rank": 1, "label": "Tomorrowland Speedway", "value": 5},
        {"rank": 2, "label": "The Barnstormer", "value": 10},
        {"rank": 3, "label": "Dumbo the Flying Elephant", "value": 15},
        {"rank": 4, "label": "Mad Tea Party", "value": 20},
        {"rank": 5, "label": "Prince Charming Regal Carrousel", "value": 25},
    ],
    "footer": "Powered by Queue-Times.com",
}
COUNTDOWN = {
    "heading": "The three longest lines today",
    "subheading": "Magic Kingdom · minutes",
    "items": [
        {"rank": 3, "label": "Space Mountain", "value": 85},
        {"rank": 2, "label": "Seven Dwarfs Mine Train", "value": 105},
        {"rank": 1, "label": "TRON Lightcycle / Run", "value": 130},
    ],
    "footer": "Powered by Queue-Times.com",
}
CHANGED = {
    "heading": "What changed this week",
    "subheading": "Walt Disney World · week of 2026-09-14",
    "items": [
        {"label": "Test Track",
         "value": "Reopened on Tuesday after a long refurbishment, and it is already the "
                  "busiest ride at EPCOT."},
        {"label": "Space Mountain",
         "value": "Goes down for refurbishment on Monday and is scheduled to stay closed "
                  "until early spring."},
        {"label": "Jungle Cruise",
         "value": "Held a steady thirty minute wait all week, the flattest line in the "
                  "Magic Kingdom right now."},
    ],
    "footer": "Powered by Queue-Times.com",
}
CHANGED_FIVE = {
    "heading": "What changed this week",
    "subheading": "Walt Disney World · week of 2026-09-14",
    "items": [
        {"label": "Test Track",
         "value": "Reopened on Tuesday after a long refurbishment, and it is already the "
                  "busiest ride at EPCOT."},
        {"label": "Space Mountain",
         "value": "Goes down for refurbishment on Monday and is scheduled to stay closed "
                  "until early spring."},
        {"label": "Jungle Cruise",
         "value": "Held a steady thirty minute wait all week, the flattest line in the "
                  "Magic Kingdom right now."},
        {"label": "Rise of the Resistance",
         "value": "Posted the longest wait of the week on Saturday, and it has not dropped "
                  "below an hour since."},
        {"label": "Haunted Mansion",
         "value": "Switched to its holiday overlay on Friday, which pushed the evening wait "
                  "up by about twenty minutes."},
    ],
    "footer": "Powered by Queue-Times.com",
}
EMPTY_RANKED = {
    "heading": "No parks reporting yet",
    "subheading": "Nothing was open at capture time",
    "items": [],
    "footer": "Powered by Queue-Times.com",
}
BRAND = {"name": "Demo Brand", "url": "example.com"}

HEATMAP = {
    "heading": "Next 30 days at Magic Kingdom",
    "subheading": "Crowd score 1 to 10",
    "items": [
        {"label": str(day), "value": (day % 10) + 1, "highlight": day == 17}
        for day in range(1, 31)
    ],
    "footer": "Powered by Queue-Times.com",
}
CURVE = {
    "heading": "Seven Dwarfs, hour by hour",
    "subheading": "Average posted wait",
    "items": [
        {"label": "9a", "value": 25}, {"label": "10a", "value": 55},
        {"label": "11a", "value": 95}, {"label": "12p", "value": 80},
        {"label": "1p", "value": 70}, {"label": "2p", "value": 65},
    ],
    "annotation": {"label": "95 min by 11", "index": 2},
    "footer": "Powered by Queue-Times.com",
}

GOLDEN_CASES = [
    ("ranked_list", RANKED, "card_ranked_list"),
    ("countdown", COUNTDOWN, "card_countdown"),
    ("changed", CHANGED, "card_changed"),
    ("changed", CHANGED_FIVE, "card_changed_five"),
    ("ranked_list", EMPTY_RANKED, "card_ranked_list_empty"),
    ("calendar_heatmap", HEATMAP, "card_calendar_heatmap"),
    ("wait_curve", CURVE, "card_wait_curve"),
]


# --- module surface -------------------------------------------------------------------

def test_templates_are_the_five_the_spec_names():
    """The three original text templates, then the two data graphics (2026-09-16)."""
    assert cards.TEMPLATES == ("ranked_list", "countdown", "changed",
                               "calendar_heatmap", "wait_curve")


def test_default_brand_is_neutral_and_complete():
    for key in ("name", "url", "bg", "bg_alt", "fg", "muted", "accent", "accent_fg", "font"):
        assert key in cards.DEFAULT_BRAND
    assert "KDesk" not in cards.DEFAULT_BRAND["name"]


def test_is_card_detects_the_kind():
    assert cards.is_card({"kind": "card", "template": "ranked_list"}) is True
    assert cards.is_card({"kind": "title"}) is False
    assert cards.is_card({"sheet": "Setup", "range": "A1:B2"}) is False


# --- brand tokens ---------------------------------------------------------------------

def test_brand_tokens_overlays_the_spec_block_onto_the_defaults():
    tokens = cards.brand_tokens({"name": "Demo Brand", "accent": "#00FF00"})
    assert tokens["name"] == "Demo Brand"
    assert tokens["accent"] == "#00FF00"
    assert tokens["bg"] == cards.DEFAULT_BRAND["bg"]


def test_brand_tokens_of_none_is_the_default_set():
    assert cards.brand_tokens(None) == cards.DEFAULT_BRAND


def test_brand_tokens_accepts_the_three_key_block_the_caller_emits():
    tokens = cards.brand_tokens({"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"})
    assert (tokens["name"], tokens["url"], tokens["accent"]) == ("Park Sheet", "parksheet.com", "#FFD966")


def test_brand_tokens_rejects_an_unknown_key_instead_of_ignoring_it():
    with pytest.raises(KeyError) as e:
        cards.brand_tokens({"colour": "#fff"})
    assert "colour" in str(e.value)


def test_brand_tokens_rejects_a_colour_that_is_not_a_hex_literal():
    """Colours land in a <style> block unescaped, so a non-hex value is a stylesheet injection."""
    with pytest.raises(ValueError) as e:
        cards.brand_tokens({"accent": "red;}</style><script>alert(1)</script>"})
    assert "accent" in str(e.value)


def test_brand_tokens_rejects_a_font_stack_with_css_punctuation():
    with pytest.raises(ValueError):
        cards.brand_tokens({"font": "Arial}</style><img onerror=x>"})


# --- canvas + escaping ----------------------------------------------------------------

def test_card_html_sizes_the_page_to_the_requested_canvas():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304)
    assert "width:1296px" in html and "height:2304px" in html
    landscape = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 2400, 1350)
    assert "width:2400px" in landscape and "height:1350px" in landscape


def test_card_html_escapes_untrusted_data():
    html = cards.card_html("ranked_list",
                           {"heading": "5 < 10 & \"quoted\"", "subheading": "",
                            "items": [{"rank": 1, "label": "<script>x</script>", "value": 1}],
                            "footer": "Powered by <b>Queue-Times.com</b>"},
                           cards.brand_tokens(BRAND))
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "5 &lt; 10 &amp; &quot;quoted&quot;" in html
    assert "Powered by &lt;b&gt;Queue-Times.com&lt;/b&gt;" in html


def test_card_html_escapes_the_brand_name_and_url():
    html = cards.card_html("ranked_list", RANKED,
                           cards.brand_tokens({"name": "A & B <b>", "url": "x.com?a=1&b=2"}))
    assert "A &amp; B &lt;b&gt;" in html
    assert "x.com?a=1&amp;b=2" in html


def test_card_html_carries_the_brand_name_and_url():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND))
    assert "Demo Brand" in html
    assert "example.com" in html


def test_card_html_renders_the_footer_attribution():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND))
    assert '<div class="foot">Powered by Queue-Times.com</div>' in html


def test_card_html_rejects_an_unknown_template():
    with pytest.raises(ValueError) as e:
        cards.card_html("bar_chart", RANKED, cards.brand_tokens(BRAND))
    assert "ranked_list" in str(e.value)


# --- ranked_list ----------------------------------------------------------------------

def test_ranked_list_numbers_rows_from_the_rank_in_the_data():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND))
    assert re.findall(r'<div class="rank">([^<]+)</div>', html) == ["1", "2", "3", "4", "5"]
    assert "Tomorrowland Speedway" in html
    assert '<div class="value">5</div>' in html


def test_ranked_list_renders_a_float_value_without_a_trailing_zero():
    data = dict(RANKED, items=[{"rank": 1, "label": "Crowd score", "value": 9.4},
                               {"rank": 2, "label": "Whole number", "value": 8.0}])
    html = cards.card_html("ranked_list", data, cards.brand_tokens(BRAND))
    assert '<div class="value">9.4</div>' in html
    assert '<div class="value">8</div>' in html


def test_ranked_list_omits_the_value_column_when_the_value_is_blank():
    data = dict(RANKED, items=[{"rank": 1, "label": "Astro Orbiter", "value": ""},
                               {"rank": 2, "label": "The Barnstormer", "value": 10}])
    html = cards.card_html("ranked_list", data, cards.brand_tokens(BRAND))
    assert '<li class="row novalue"><div class="rank">1</div>' \
           '<div class="label">Astro Orbiter</div></li>' in html
    assert '<div class="value">10</div>' in html
    assert html.count('class="value"') == 1


def test_ranked_list_renders_the_full_eight_item_card():
    data = dict(RANKED, items=[{"rank": i, "label": f"Attraction number {i}", "value": i * 5}
                               for i in range(1, 9)])
    html = cards.card_html("ranked_list", data, cards.brand_tokens(BRAND))
    assert len(re.findall(r'<li class="row', html)) == 8
    assert "Attraction number 8" in html


def test_ranked_list_rejects_more_items_than_the_card_can_hold():
    data = dict(RANKED, items=[{"rank": i, "label": f"Row {i}", "value": i} for i in range(1, 10)])
    with pytest.raises(ValueError) as e:
        cards.card_html("ranked_list", data, cards.brand_tokens(BRAND))
    assert "8" in str(e.value)


def test_ranked_list_with_no_items_renders_an_empty_body_instead_of_raising():
    """The caller emits an empty list when no park is reporting; a Short must still render."""
    html = cards.card_html("ranked_list", EMPTY_RANKED, cards.brand_tokens(BRAND))
    assert "No parks reporting yet" in html
    assert "Nothing was open at capture time" in html
    assert "Powered by Queue-Times.com" in html
    assert 'class="empty"' in html
    assert 'class="rank"' not in html


# --- countdown ------------------------------------------------------------------------

def test_countdown_numbers_rows_downward_from_the_rank_in_the_data():
    html = cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(BRAND))
    assert re.findall(r'<div class="rank">([^<]+)</div>', html) == ["#3", "#2", "#1"]


def test_countdown_keeps_the_items_in_list_order():
    html = cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(BRAND))
    assert html.index("Space Mountain") < html.index("Seven Dwarfs Mine Train") \
        < html.index("TRON Lightcycle / Run")


def test_countdown_without_ranks_counts_down_to_one_instead_of_up_from_one():
    """The rank is the caller's, but a countdown that omits it must still count down."""
    data = dict(COUNTDOWN, items=[{"label": "A", "value": 85}, {"label": "B", "value": 105},
                                  {"label": "C", "value": 130}])
    html = cards.card_html("countdown", data, cards.brand_tokens(BRAND))
    assert re.findall(r'<div class="rank">([^<]+)</div>', html) == ["#3", "#2", "#1"]


def test_ranked_list_without_ranks_counts_up_from_one():
    data = dict(RANKED, items=[{"label": "A", "value": 5}, {"label": "B", "value": 10}])
    html = cards.card_html("ranked_list", data, cards.brand_tokens(BRAND))
    assert re.findall(r'<div class="rank">([^<]+)</div>', html) == ["1", "2"]


# --- changed --------------------------------------------------------------------------

def test_changed_rows_carry_a_label_and_a_sentence_and_no_rank():
    html = cards.card_html("changed", CHANGED, cards.brand_tokens(BRAND))
    assert html.count('<li class="row changed">') == 3
    assert 'class="rank"' not in html
    assert '<div class="label">Test Track</div>' in html
    assert "already the busiest ride at EPCOT." in html


def test_changed_sentences_are_allowed_to_wrap():
    html = cards.card_html("changed", CHANGED, cards.brand_tokens(BRAND))
    assert re.search(r"\.note\{[^}]*white-space:normal", html), "the sentence column must wrap"


@pytest.mark.parametrize("length", [60, 120])
def test_changed_renders_both_ends_of_the_callers_sentence_window(length):
    """The caller's contract is a 60-120 character sentence; both ends must survive intact."""
    sentence = ("Reopened on Tuesday after a long refurbishment, and it is already the busiest "
                "ride in the whole of the park by a very wide margin.")[:length]
    assert len(sentence) == length
    html = cards.card_html("changed", dict(CHANGED, items=[{"label": "Test Track",
                                                            "value": sentence}]),
                           cards.brand_tokens(BRAND))
    assert f'<div class="note">{sentence}</div>' in html
    assert re.search(r"\.note\{[^}]*white-space:normal", html)


def test_changed_renders_the_full_five_row_card():
    html = cards.card_html("changed", CHANGED_FIVE, cards.brand_tokens(BRAND))
    assert html.count('<li class="row changed">') == 5
    assert "Haunted Mansion" in html


def test_changed_rejects_more_rows_than_stay_readable():
    """Six sentences on one 9:16 card shrink the note text past readable - reject, don't render."""
    data = dict(CHANGED, items=[{"label": f"Ride {i}", "value": "A sentence of roughly the "
                                                               "right length for this card."}
                                for i in range(6)])
    with pytest.raises(ValueError) as e:
        cards.card_html("changed", data, cards.brand_tokens(BRAND))
    assert "5" in str(e.value)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_changed_note_text_never_drops_below_30px_on_the_9_16_canvas(n):
    data = dict(CHANGED, items=[{"label": f"Ride {i}", "value": "x" * 120} for i in range(n)])
    html = cards.card_html("changed", data, cards.brand_tokens(BRAND), 1296, 2304)
    row_px = float(re.search(r"\.row\{[^}]*font-size:([\d.]+)px", html).group(1))
    note_em = float(re.search(r"\.note\{[^}]*font-size:([\d.]+)em", html).group(1))
    assert row_px * note_em >= 30, f"{n} rows gives {row_px * note_em:.1f}px note text"


# --- goldens --------------------------------------------------------------------------

@pytest.mark.parametrize("template,data,name", GOLDEN_CASES,
                         ids=[c[2] for c in GOLDEN_CASES])
def test_card_html_matches_its_golden_file(template, data, name):
    """Regenerate after an intentional design change:
       KDESK_UPDATE_GOLDEN=1 uv run --with pytest pytest tests/test_cards.py -q
    then open the rendered PNG before committing."""
    html = cards.card_html(template, data, cards.brand_tokens(BRAND), 1296, 2304)
    path = GOLDEN / f"{name}.html"
    if os.environ.get("KDESK_UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    assert path.exists(), f"missing golden {path}; regenerate with KDESK_UPDATE_GOLDEN=1"
    assert html == path.read_text(encoding="utf-8")


# --- the transparent / boxed variant (what the `media` overlay renders through) ---------

BOX = (71, 922, 1154, 1170)


def test_the_default_card_is_unchanged_by_the_new_keywords():
    """Belt and braces beside the goldens: the defaults must be the old call exactly."""
    plain = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304)
    explicit = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                               transparent=False, box=None)
    assert plain == explicit


def test_a_transparent_card_drops_the_background_gradient():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                           transparent=True)
    assert "background:transparent" in html
    assert "radial-gradient" not in html


def test_a_transparent_card_wears_its_plate_as_a_pseudo_element():
    """The wash is semi-opaque; the text on it must not be. That is why it is ::before."""
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                           transparent=True, box=BOX)
    assert ".card::before" in html
    assert "opacity:.74" in html
    assert ".card>*{position:relative;z-index:1}" in html


def test_a_boxed_card_is_anchored_to_the_bottom_of_its_box_and_grows_upward():
    """The box's bottom edge is the one that clears the attribution watermark."""
    left, top, w, h = BOX
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                           transparent=True, box=BOX)
    assert f"left:{left}px" in html
    assert f"bottom:{2304 - top - h}px" in html
    assert f"max-height:{h}px" in html
    assert "height:auto" in html
    assert "height:2304px;display:flex" not in html


def test_a_boxed_card_sizes_its_body_by_its_rows_not_by_the_leftover_space():
    """`flex:1` in an auto-height column has no free space to claim, so rows would vanish."""
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                           transparent=True, box=BOX)
    assert ".body{flex:0 0 auto}" in html


def test_a_boxed_card_sizes_its_type_to_the_box_not_to_the_page():
    left, top, w, h = BOX
    boxed = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                            transparent=True, box=BOX)
    same_canvas = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), w, h,
                                  transparent=True)
    boxed_h1 = re.search(r"h1\{font-size:([\d.]+)px", boxed).group(1)
    canvas_h1 = re.search(r"h1\{font-size:([\d.]+)px", same_canvas).group(1)
    assert boxed_h1 == canvas_h1


def test_a_boxed_card_still_enforces_the_row_caps():
    data = dict(RANKED, items=[{"rank": i, "label": f"Ride {i}", "value": i}
                               for i in range(9)])
    with pytest.raises(ValueError):
        cards.card_html("ranked_list", data, cards.brand_tokens(BRAND), 1296, 2304,
                        transparent=True, box=BOX)


# --- spec_credits ----------------------------------------------------------------------

def test_spec_credits_renders_the_top_level_credits_as_a_block():
    spec = {"credits": ["Imagery: Google Earth", "Wait times: Queue-Times.com"]}
    assert cards.spec_credits(spec) == ("Credits:\n"
                                        "- Imagery: Google Earth\n"
                                        "- Wait times: Queue-Times.com")


def test_spec_credits_picks_up_every_media_scenes_own_credit_line():
    """A credit burned into a frame belongs in the description too."""
    spec = {"scenes": [{"kind": "media", "credit": "Imagery: Google Earth"},
                       {"kind": "card"},
                       {"kind": "media", "credit": "Footage: NASA"}]}
    assert cards.spec_credits(spec) == ("Credits:\n"
                                        "- Imagery: Google Earth\n"
                                        "- Footage: NASA")


def test_spec_credits_mentions_a_repeated_credit_once():
    spec = {"credits": ["Imagery: Google Earth"],
            "scenes": [{"kind": "media", "credit": "Imagery: Google Earth"},
                       {"kind": "media", "credit": "  Imagery: Google Earth  "}]}
    assert cards.spec_credits(spec) == "Credits:\n- Imagery: Google Earth"


def test_spec_credits_appends_the_disclaimer_under_the_block():
    spec = {"credits": ["Imagery: Google Earth"],
            "disclaimer": "Wait times are estimates and change minute to minute."}
    assert cards.spec_credits(spec) == ("Credits:\n- Imagery: Google Earth\n\n"
                                        "Wait times are estimates and change minute to minute.")


def test_spec_credits_renders_a_disclaimer_with_no_credits_at_all():
    assert cards.spec_credits({"disclaimer": "Not financial advice."}) == "Not financial advice."


def test_spec_credits_of_a_spec_that_claims_nothing_is_empty():
    assert cards.spec_credits({"slug": "x", "scenes": [{"kind": "card"}]}) == ""
    assert cards.spec_credits({}) == ""


# --- a boxed card that FILLS its box (a card SCENE, not an overlay plate) -----------------

BOXED = (71, 737, 1154, 1567)


def test_fill_is_off_by_default_so_the_media_overlay_plate_is_unchanged():
    """The overlay hugs its rows so a three-row card leaves the footage above it alone."""
    assert cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(None), box=BOXED) == \
        cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(None), box=BOXED, fill=False)


def test_a_boxed_card_can_fill_its_box_instead_of_hugging_its_content():
    """A card SCENE is the frame minus the caption band; dead space under it reads as a bug."""
    doc = cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(None), box=BOXED, fill=True)
    left, top, width, height = BOXED
    assert f"left:{left}px;top:{top}px" in doc
    assert f"width:{width}px;height:{height}px" in doc
    assert ".body{flex:0 0 auto}" not in doc, "a filled card centres its rows in the leftovers"


def test_a_hugging_box_is_still_anchored_to_its_bottom_edge():
    doc = cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(None), box=BOXED)
    assert "bottom:" in doc and "height:auto" in doc
    assert ".body{flex:0 0 auto}" in doc


def test_fill_without_a_box_changes_nothing_because_the_card_already_fills_the_frame():
    assert cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(None), fill=True) == \
        cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(None))


# --- the two data-graphic templates (2026-09-16) -------------------------------------------

def test_the_two_data_graphic_templates_are_declared():
    assert "calendar_heatmap" in cards.TEMPLATES
    assert "wait_curve" in cards.TEMPLATES


def test_a_calendar_heatmap_draws_one_cell_per_day():
    html = cards.card_html("calendar_heatmap", HEATMAP, cards.brand_tokens(None))

    assert html.count('class="cell') == 30
    assert 'class="cell hot"' in html
    assert "Next 30 days at Magic Kingdom" in html


def test_a_heatmap_cell_takes_its_colour_from_the_score():
    cool = cards.card_html("calendar_heatmap",
                           {**HEATMAP, "items": [{"label": "1", "value": 1}]},
                           cards.brand_tokens(None))
    hot = cards.card_html("calendar_heatmap",
                          {**HEATMAP, "items": [{"label": "1", "value": 10}]},
                          cards.brand_tokens(None))

    assert cards.HEATMAP_RAMP[0] in cool
    assert cards.HEATMAP_RAMP[-1] in hot


def test_an_out_of_range_or_missing_score_still_renders():
    html = cards.card_html("calendar_heatmap",
                           {**HEATMAP, "items": [{"label": "1"}, {"label": "2", "value": 99}]},
                           cards.brand_tokens(None))

    assert html.count('class="cell') == 2


def test_a_heatmap_past_its_cap_raises_rather_than_render_unreadable_type():
    items = [{"label": str(n), "value": 5} for n in range(cards.MAX_HEATMAP_ITEMS + 1)]

    with pytest.raises(ValueError) as excinfo:
        cards.card_html("calendar_heatmap", {**HEATMAP, "items": items}, cards.brand_tokens(None))

    assert str(cards.MAX_HEATMAP_ITEMS) in str(excinfo.value)


def test_a_wait_curve_draws_a_polyline_and_its_hour_labels():
    html = cards.card_html("wait_curve", CURVE, cards.brand_tokens(None))

    assert "<svg" in html and "<polyline" in html
    for label in ("9a", "11a", "2p"):
        assert f">{label}<" in html


def test_the_curve_annotation_marks_the_named_point():
    html = cards.card_html("wait_curve", CURVE, cards.brand_tokens(None))

    assert "95 min by 11" in html
    assert "<circle" in html


def test_an_annotation_index_outside_the_series_is_clamped_not_crashed():
    html = cards.card_html("wait_curve",
                           {**CURVE, "annotation": {"label": "late", "index": 99}},
                           cards.brand_tokens(None))

    assert "late" in html


def test_a_flat_series_does_not_divide_by_zero():
    flat = {**CURVE, "items": [{"label": "9a", "value": 30}, {"label": "10a", "value": 30}]}

    assert "<polyline" in cards.card_html("wait_curve", flat, cards.brand_tokens(None))


def test_a_curve_past_its_cap_raises():
    items = [{"label": str(n), "value": n} for n in range(cards.MAX_CURVE_POINTS + 1)]

    with pytest.raises(ValueError):
        cards.card_html("wait_curve", {**CURVE, "items": items}, cards.brand_tokens(None))


def test_the_new_templates_escape_every_caller_string():
    html = cards.card_html("wait_curve",
                           {**CURVE, "heading": '<script>x</script>',
                            "annotation": {"label": "<b>x</b>", "index": 0}},
                           cards.brand_tokens(None))

    assert "<script>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def test_the_new_templates_honour_a_box_like_every_other_card():
    boxed = cards.card_html("calendar_heatmap", HEATMAP, cards.brand_tokens(None),
                            box=(60, 900, 1176, 1100), transparent=True)

    assert "top:900px" in boxed or "bottom:" in boxed
    assert "radial-gradient" not in boxed


def test_the_three_original_templates_are_byte_identical_to_their_goldens():
    """Belt and braces beside the golden test: the new branches must add nothing.

    `brand_tokens(BRAND)`, not `(None)`: the goldens are generated with the Demo Brand block,
    so comparing against the default brand would fail on the brand line rather than on the
    thing this test is guarding.
    """
    for template, data, name in GOLDEN_CASES:
        if name.startswith(("card_calendar", "card_wait")):
            continue
        expected = (GOLDEN / f"{name}.html").read_text()
        assert cards.card_html(template, data, cards.brand_tokens(BRAND)) == expected


def test_a_heatmap_column_can_actually_shrink_to_a_seventh_of_the_card():
    """`1fr` floors at the cell's automatic minimum, which `aspect-ratio:1` ties to its
    content height — seven such columns overflow the card and clip the last two days.
    MEASURED 2026-09-16 on the first real render; `minmax(0,1fr)` is the fix."""
    html = cards.card_html("calendar_heatmap", HEATMAP, cards.brand_tokens(None), 1296, 2304)

    assert "repeat(7,minmax(0,1fr))" in html
    assert re.search(r"\.cell\{[^}]*min-width:0", html)


@pytest.mark.parametrize("n", [7, 14, 30, 42])
def test_heatmap_type_fits_inside_the_cell_it_is_given(n):
    """Day label + score must stack inside one square cell, at every card-filling count."""
    data = {**HEATMAP, "items": [{"label": str(i), "value": 5} for i in range(n)]}
    html = cards.card_html("calendar_heatmap", data, cards.brand_tokens(None), 1296, 2304)

    unit = 2304 / 100.0
    gap = 0.55 * unit
    column = (1296 - 9.0 * unit - 6.0 * gap) / 7.0
    day = float(re.search(r"\.cell \.d\{font-size:([\d.]+)px", html).group(1))
    score = float(re.search(r"\.cell \.v\{font-size:([\d.]+)px", html).group(1))
    # 1.2 is the normal line box each span gets, plus the flex gap between them.
    assert 1.2 * (day + score) + 0.15 * unit <= column, \
        f"{n} cells: {1.2 * (day + score):.0f}px of type in a {column:.0f}px cell"


def test_the_curve_is_drawn_under_a_uniform_scale():
    """preserveAspectRatio="none" stretched the viewBox into the card's box — 1.7x vertically.

    Under that the marker circle renders as an ellipse, the annotation text is stretched, and
    a stroke's apparent width depends on its segment's angle. The fix is a uniform scale: the
    SVG keeps its viewBox's own ratio, so nothing is distorted at any card or box width.
    """
    html = cards.card_html("wait_curve", CURVE, cards.brand_tokens(None), 1296, 2304)

    assert 'preserveAspectRatio="xMidYMid meet"' in html
    assert 'preserveAspectRatio="none"' not in html

    view_box = re.search(r'viewBox="0 0 (\d+) (\d+)"', html)
    assert (int(view_box.group(1)), int(view_box.group(2))) \
        == (int(cards.CURVE_W), int(cards.CURVE_H))

    # "meet" only avoids letterboxing if the box it is given carries the same ratio.
    ratio = re.search(r"\.plot\{[^}]*aspect-ratio:(\d+)\s*/\s*(\d+)", html)
    assert ratio, "the plot box must be tied to the viewBox's ratio"
    assert (int(ratio.group(1)), int(ratio.group(2))) \
        == (int(cards.CURVE_W), int(cards.CURVE_H))

    # A fixed height would put the mismatch straight back.
    assert not re.search(r"\.plot\{[^}]*height:", html), "a fixed plot height re-stretches it"


# --- heatmap legibility (WCAG 2.x relative luminance, computed here, not eyeballed) ---------

def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _rgb(hex_colour: str) -> tuple[float, float, float]:
    raw = hex_colour.lstrip("#")
    return tuple(int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(hex_colour: str) -> float:
    r, g, b = (_linear(c) for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    lo, hi = sorted((la, lb))
    return (hi + 0.05) / (lo + 0.05)


def _over(ink: str, plate: str, alpha: float) -> str:
    """`ink` at `alpha` composited on `plate` — what CSS `opacity` actually paints."""
    mixed = (alpha * i + (1 - alpha) * p for i, p in zip(_rgb(ink), _rgb(plate)))
    return "#" + "".join(f"{round(c * 255):02X}" for c in mixed)


#: Both cell strings are large bold type (the day >= 35px, the score >= 55px on the 9:16
#: canvas), so WCAG AA asks 3:1. 3.5 keeps a little headroom for the ramp being tuned by eye.
MIN_CELL_CONTRAST = 3.5


def test_a_heatmap_day_label_is_legible_on_every_step_of_the_ramp():
    """The day sits at reduced opacity on its own cell — the one place the ramp can hide it."""
    html = cards.card_html("calendar_heatmap", HEATMAP, cards.brand_tokens(None))
    opacity = float(re.search(r"\.cell \.d\{[^}]*opacity:([\d.]+)", html).group(1))
    ink = cards.DEFAULT_BRAND["bg"]

    assert opacity >= 0.9, f"the day label is washed out at opacity {opacity}"
    for step in cards.HEATMAP_RAMP:
        ratio = _contrast(_over(ink, step, opacity), step)
        assert ratio >= MIN_CELL_CONTRAST, \
            f"day label on {step} is {ratio:.2f}:1 at opacity {opacity}"


def test_a_heatmap_score_is_legible_on_every_step_of_the_ramp():
    ink = cards.DEFAULT_BRAND["bg"]
    for step in cards.HEATMAP_RAMP:
        ratio = _contrast(ink, step)
        assert ratio >= MIN_CELL_CONTRAST, f"score on {step} is {ratio:.2f}:1"


def _cell_of(value):
    """The single rendered cell for one caller value: (printed text, background colour)."""
    html = cards.card_html("calendar_heatmap",
                           {**HEATMAP, "items": [{"label": "1", "value": value}]},
                           cards.brand_tokens(None))
    cell = re.search(r'<li class="cell[^"]*" style="background:(#[0-9A-Fa-f]{6})">'
                     r'<span class="d">[^<]*</span><span class="v">([^<]*)</span></li>', html)
    assert cell, "one item must render exactly one cell"
    return cell.group(2), cell.group(1)


@pytest.mark.parametrize("value,printed", [
    (99, "10"), (11, "10"), (10, "10"),          # above the scale clamps to its top
    (0, "1"), (-4, "1"), (1, "1"),               # below it clamps to its bottom
    (9.4, "9.4"), (8.0, "8"), (7, "7"),          # in range, the caller's own formatting stands
])
def test_a_heatmap_prints_the_same_score_it_colours(value, printed):
    """A cell that colours as a 10 must not print 99: the ramp and the number are two
    renderings of ONE score, and disagreeing is worse than either alone."""
    text, colour = _cell_of(value)

    assert text == printed
    assert colour == cards.HEATMAP_RAMP[cards._ramp_index(value)]


@pytest.mark.parametrize("value", [None, "", "n/a"])
def test_a_heatmap_cell_with_no_readable_score_prints_nothing_rather_than_inventing_one(value):
    """Clamping must not become fabrication — an absent score has no number to show."""
    text, colour = _cell_of(value)

    assert text == ""
    assert colour == cards.HEATMAP_RAMP[0]


def _curve_points(html: str) -> list[float]:
    raw = re.search(r'<polyline points="([^"]+)"', html).group(1)
    return [float(pair.split(",")[0]) for pair in raw.split()]


def _curve_label_positions(html: str) -> list[float]:
    return [float(x) for x in re.findall(r'<span style="left:([\d.]+)%', html)]


def test_every_curve_x_label_sits_at_the_point_it_names():
    """`justify-content:space-between` pins label EDGES to the container's edges, so a tick's
    centre drifts from its data point — worst at the two ends, which are the ones a viewer
    reads off. Each label is positioned at its own point's x instead."""
    html = cards.card_html("wait_curve", CURVE, cards.brand_tokens(None))
    xs = _curve_points(html)
    lefts = _curve_label_positions(html)

    assert len(lefts) == len(xs) == len(CURVE["items"])
    for x, left in zip(xs, lefts):
        assert abs(left - x / cards.CURVE_W * 100) < 0.01
    assert lefts[0] == 0.0 and lefts[-1] == 100.0
    assert not re.search(r"\.xlabels\{[^}]*space-between", html), "space-between drifts"
    assert re.search(r"\.xlabels\{[^}]*position:relative", html)


def test_the_end_labels_are_anchored_on_their_point_without_hanging_off_the_card():
    """The body clips its overflow, so a centred end label would lose half its text."""
    html = cards.card_html("wait_curve", CURVE, cards.brand_tokens(None))
    spans = re.findall(r'<span style="left:[\d.]+%;transform:([^"]+)"', html)

    assert len(spans) == len(CURVE["items"])
    assert spans[0] == "translateX(0)"
    assert spans[-1] == "translateX(-100%)"
    assert set(spans[1:-1]) == {"translateX(-50%)"}


@pytest.mark.parametrize("count", [2, 3, 6, 16])
def test_curve_labels_and_points_stay_in_step_at_every_series_length(count):
    data = {**CURVE, "items": [{"label": f"h{n}", "value": n * 3} for n in range(count)]}
    html = cards.card_html("wait_curve", data, cards.brand_tokens(None))

    assert len(_curve_label_positions(html)) == len(_curve_points(html)) == count


def test_a_single_point_curve_renders_instead_of_dividing_by_zero():
    """The contract says a one-point series is legal; `step` divides by len-1, so say so here.

    A one-hour series is what a park that has only just opened reports, and it must draw
    something rather than raise — the rest of the Short still has to render.
    """
    one = {**CURVE, "items": [{"label": "9a", "value": 25}],
           "annotation": {"label": "just opened", "index": 0}}

    html = cards.card_html("wait_curve", one, cards.brand_tokens(None))

    assert "<polyline" in html and "<circle" in html
    assert "just opened" in html
    assert _curve_points(html) == [0.0]
    assert _curve_label_positions(html) == [0.0]
    assert ">9a<" in html


def test_a_single_point_curve_is_fine_without_an_annotation_too():
    one = {k: v for k, v in CURVE.items() if k != "annotation"}
    one["items"] = [{"label": "9a", "value": 25}]

    html = cards.card_html("wait_curve", one, cards.brand_tokens(None))

    assert "<polyline" in html
    assert "<text" not in html, "no annotation label means no annotation text"


# --- reveal ----------------------------------------------------------------------------

def test_reveal_counts_items_by_ceiling_so_an_arriving_row_is_on_screen():
    assert cards.reveal_count(5, 0.0) == 0
    assert cards.reveal_count(5, 0.01) == 1
    assert cards.reveal_count(5, 0.2) == 1
    assert cards.reveal_count(5, 0.21) == 2
    assert cards.reveal_count(5, 1.0) == 5
    assert cards.reveal_count(0, 0.5) == 0


def test_item_progress_is_that_items_own_arrival_clamped_to_zero_and_one():
    assert cards.item_progress(0, 4, 0.125) == pytest.approx(0.5)
    assert cards.item_progress(0, 4, 0.25) == pytest.approx(1.0)
    assert cards.item_progress(1, 4, 0.25) == pytest.approx(0.0)
    assert cards.item_progress(3, 4, 0.5) == pytest.approx(0.0)
    assert cards.item_progress(3, 4, 1.0) == pytest.approx(1.0)


def test_count_up_returns_the_value_itself_at_full_reveal():
    """Same type, same object -- this is what keeps the goldens byte-identical."""
    for value in (5, 9.4, 8.0, "", None, "Reopened on Tuesday."):
        assert cards.count_up(value, 1.0) is value


def test_count_up_eases_out_toward_the_final_number():
    assert cards.count_up(100, 0.0) == 0
    assert cards.count_up(100, 0.5) == 88          # 1 - 0.5**3 = 0.875
    assert cards.count_up(100, 0.9) == 100         # 1 - 0.1**3 = 0.999
    assert cards.count_up(100, 0.5) < 100


def test_count_up_keeps_an_int_an_int_and_a_float_a_float():
    assert isinstance(cards.count_up(80, 0.5), int)
    assert isinstance(cards.count_up(9.4, 0.5), float)


def test_count_up_leaves_anything_that_is_not_a_number_alone():
    assert cards.count_up("Reopened on Tuesday.", 0.3) == "Reopened on Tuesday."
    assert cards.count_up("", 0.3) == ""
    assert cards.count_up(None, 0.3) is None
    assert cards.count_up(True, 0.3) is True       # a bool is not a figure to count


def test_a_hidden_row_keeps_its_box_so_the_card_never_reflows():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                           reveal=0.4)
    assert html.count("visibility:hidden") == 3    # 5 rows, ceil(0.4*5)=2 drawn
    assert html.count('class="row"') + html.count('class="row novalue"') == 5


def test_the_heading_and_the_footer_are_drawn_at_every_reveal():
    """`reveal` reveals the ITEMS. Frame 0 of a data day is a card, and S1 wants it lit
    and S3 wants its headline to be the frame-0 text."""
    for reveal in (0.0, 0.25, 1.0):
        html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND),
                               1296, 2304, reveal=reveal)
        assert RANKED["heading"] in html
        assert RANKED["footer"] in html
        assert "Demo Brand" in html          # BRAND["name"], the brand line at the top


def test_the_heatmap_fills_in_date_order():
    n = len(HEATMAP["items"])
    for reveal, drawn in ((0.0, 0), (0.5, -(-n // 2)), (1.0, n)):
        html = cards.card_html("calendar_heatmap", HEATMAP, cards.brand_tokens(BRAND),
                               1296, 2304, reveal=reveal)
        assert html.count("visibility:hidden") == n - drawn, reveal
    half = cards.card_html("calendar_heatmap", HEATMAP, cards.brand_tokens(BRAND),
                           1296, 2304, reveal=0.5)
    cells = re.findall(r'<li class="cell[^"]*"([^>]*)>', half)
    hidden = [bool("visibility:hidden" in attrs) for attrs in cells]
    assert hidden == sorted(hidden), "cells must fill in order, never out of it"


def test_the_wait_curve_draws_itself_with_a_dash_offset():
    half = cards.card_html("wait_curve", CURVE, cards.brand_tokens(BRAND), 1296, 2304,
                           reveal=0.5)
    m = re.search(r'stroke-dasharray="([0-9.]+)" stroke-dashoffset="([0-9.]+)"', half)
    assert m, half
    length, offset = float(m.group(1)), float(m.group(2))
    assert length > 0
    assert offset == pytest.approx(length * 0.5, abs=0.2)


def test_the_curve_fill_and_its_annotation_only_appear_when_the_line_is_finished():
    partial = cards.card_html("wait_curve", CURVE, cards.brand_tokens(BRAND), 1296, 2304,
                              reveal=0.75)
    assert 'class="fill" visibility="hidden"' in partial
    assert '<circle' in partial and 'visibility="hidden"' in partial
    whole = cards.card_html("wait_curve", CURVE, cards.brand_tokens(BRAND), 1296, 2304)
    assert "visibility" not in whole


def test_polyline_length_is_the_sum_of_its_segments():
    assert cards.polyline_length([(0.0, 0.0), (3.0, 4.0)]) == pytest.approx(5.0)
    assert cards.polyline_length([(0.0, 0.0), (3.0, 4.0), (3.0, 14.0)]) == pytest.approx(15.0)
    assert cards.polyline_length([(1.0, 1.0)]) == pytest.approx(0.0)
    assert cards.polyline_length([]) == pytest.approx(0.0)


def test_a_reveal_outside_zero_to_one_is_refused():
    for bad in (-0.1, 1.5):
        with pytest.raises(ValueError) as excinfo:
            cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304,
                            reveal=bad)
        assert "reveal" in str(excinfo.value)


@pytest.mark.parametrize("template,data,name", GOLDEN_CASES,
                         ids=[c[2] for c in GOLDEN_CASES])
def test_full_reveal_is_byte_identical_to_the_card_with_no_reveal_at_all(template, data, name):
    """GC3: no golden moves. `reveal=1.0` must emit exactly the old string -- no
    visibility attribute, no dash attributes, no re-formatted number."""
    plain = cards.card_html(template, data, cards.brand_tokens(BRAND), 1296, 2304)
    explicit = cards.card_html(template, data, cards.brand_tokens(BRAND), 1296, 2304,
                               reveal=1.0)
    assert plain == explicit
    assert plain == (GOLDEN / f"{name}.html").read_text(encoding="utf-8")
