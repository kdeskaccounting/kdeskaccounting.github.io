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

GOLDEN_CASES = [
    ("ranked_list", RANKED, "card_ranked_list"),
    ("countdown", COUNTDOWN, "card_countdown"),
    ("changed", CHANGED, "card_changed"),
    ("changed", CHANGED_FIVE, "card_changed_five"),
    ("ranked_list", EMPTY_RANKED, "card_ranked_list_empty"),
]


# --- module surface -------------------------------------------------------------------

def test_templates_are_the_three_the_spec_names():
    assert cards.TEMPLATES == ("ranked_list", "countdown", "changed")


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
