#!/usr/bin/env python3
"""HTML cards for the `card` scene kind: a caller's data block straight into a 9:16 frame.

Five templates, all fed by one `data:` block with the same four keys — `heading`,
`subheading`, `items`, `footer` (`wait_curve` adds one optional fifth, `annotation`):

  ranked_list  items: [{rank: int ascending, label: str, value: int|float|""}]   0-8 rows
  countdown    items: [{rank: int descending, label: str, value: int}]           0-8 rows, list order
  changed      items: [{label: str, value: str}]                                 0-5 rows; no rank, and
                                                                                 value is a 60-120
                                                                                 character sentence
                                                                                 that wraps
  calendar_heatmap
               items: [{label: str, value: 1-10, highlight: bool}]               0-42 cells, 7 across
  wait_curve   items: [{label: str, value: int|float}]                           0-16 points, plus
               annotation: {label: str, index: int}                              an optional marked point

The row caps are readability limits, not storage limits: rows shrink as they multiply, and past
8 ranked rows (or 5 sentence rows, 42 heatmap cells, 16 curve points) the type is too small to
read on a phone, so `card_html` raises rather than render something unusable. `changed` note
text never falls below 30px on the 1296x2304 canvas.

The two data-graphic templates (2026-09-16) are our own charts, drawn as plain HTML and inline
SVG — no charting library, because this file is stdlib-only by contract. `calendar_heatmap`
colours each cell by `cards.HEATMAP_RAMP` (clamped, so a missing or out-of-range score still
renders) and rings a `highlight: true` day in the brand accent; `wait_curve` draws a polyline
with a circled annotation whose index is clamped to the series and whose flat case cannot
divide by zero. Both go through the same `box`/`fill`/`transparent` plumbing as every other
template, so they work as a `media` overlay and under captions untouched. Nothing here knows
what a crowd score is — the caller builds the `data:` block.

`ranked_list` renders a rank + label row with no value column when `value` is `""`, and an
empty `items` list renders the heading, subheading and footer over a tasteful empty body
rather than raising — the caller emits an empty list when its source has nothing to report
and a Short still has to render.

Colours come from the spec's optional `brand:` block (`{name, url, accent}` is the usual
three-key form); the defaults are brand-neutral and dark, so the same renderer serves a
second venture without carrying KDesk's palette. Every string from `data`/`brand` is
HTML-escaped, and every brand colour is checked against a hex literal before it lands in the
<style> block, because a brand token is the one value that is interpolated unescaped.

Pure string building — no I/O, stdlib only — so the golden tests run in the plain
`uv run --with pytest` environment.
"""
from __future__ import annotations

import html as _html
import math
import re

TEMPLATES = ("ranked_list", "countdown", "changed", "calendar_heatmap", "wait_curve")

#: A 9:16 card stays legible down to about this many rank rows; past it the caller must split.
MAX_ITEMS = 8

#: `changed` rows carry a whole sentence each, so they run out of room far sooner.
MAX_CHANGED_ITEMS = 5

#: Six weeks of a calendar. Past that a cell is smaller than a fingertip on a phone.
MAX_HEATMAP_ITEMS = 42

#: Hour-by-hour for a park day plus a little slack. Past that the labels collide.
MAX_CURVE_POINTS = 16

#: Cool -> hot, six steps over a 1-10 score. Deliberately not the brand accent: the ramp has
#: to be readable AS a ramp, and a single-hue tint of one brand colour is not.
#:
#: Every step also has to hold DARK TYPE, because a cell prints its day and its score in
#: `brand['bg']`. The coolest step was #2F6F4F, which put the day label at 2.87:1 — below
#: WCAG AA even for large text. It was lightened just far enough to clear the floor
#: tests/test_cards.py asserts (3.5:1), while staying darker than the next step so the cool
#: end still reads as a step rather than a flat pair. Change a value here and that test tells
#: you whether the type survived.
#:
#: 2026-09-26: `brand['bg']` (the same ink) moved from #101418 to #2F3540 to clear gate S1's
#: frame-0 luma floor (see DEFAULT_BRAND above) -- a lighter ink is closer to a mid-value
#: cell, so three steps (both cool steps and the hot end) dropped under 3.5:1 against the
#: new ink and were lightened again to clear it (2.50/2.75:1 and 2.67:1 measured before this
#: change); the two untouched middle-to-hot steps already cleared the floor unchanged.
HEATMAP_RAMP: tuple[str, ...] = (
    "#69A487", "#78A35F", "#93B23A", "#D9B740", "#D98A3C", "#D87E6E",
)

#: Per-template row caps. The three original templates keep exactly the caps they had.
CAPS: dict[str, int] = {
    "changed": MAX_CHANGED_ITEMS,
    "calendar_heatmap": MAX_HEATMAP_ITEMS,
    "wait_curve": MAX_CURVE_POINTS,
}

#: Floor on a `changed` row's font size, in canvas units (height/100). The note is .9em of it,
#: so 1.45 units keeps note text at 30px or more on the 1296x2304 card.
MIN_CHANGED_ROW_UNITS = 1.45

#: `bg`/`bg_alt` were `#101418`/`#1B2430` (YAVG ~36 at every reveal) until 2026-09-26: that
#: ground alone put a card hero's frame 0 and every step below gate S1's frame0 luma >= 60
#: and fed S7's dark-frame count, independent of `reveal` -- a data day with a card hero
#: could never pass either line. Raised so the mean frame lands >= 64 (measured via
#: `signalstats` YAVG on a rendered card PNG; see the final-fix report for the numbers).
DEFAULT_BRAND: dict = {
    "name": "Your Brand",
    "url": "example.com",
    "bg": "#2F3540",
    "bg_alt": "#3A4250",
    "fg": "#FFFFFF",
    "muted": "#AAB6C4",
    "accent": "#F2C14E",
    "accent_fg": "#101418",
    "font": "Carlito, Arial, Helvetica, sans-serif",
}

_COLOUR_TOKENS = ("bg", "bg_alt", "fg", "muted", "accent", "accent_fg")
_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_FONT_STACK = re.compile(r"^[A-Za-z0-9 ,'\-]+$")


# --- brand ----------------------------------------------------------------------------

def _checked_token(key: str, value: object) -> str:
    """Brand tokens are interpolated into CSS unescaped, so validate them as literals."""
    text = str(value)
    if key in _COLOUR_TOKENS and not _HEX.match(text):
        raise ValueError(f"brand token {key!r} must be a hex colour like '#1F3864', got {text!r}")
    if key == "font" and not _FONT_STACK.match(text):
        raise ValueError(f"brand token 'font' must be a plain font stack "
                         f"(letters, digits, spaces, commas, hyphens), got {text!r}")
    return text


def brand_tokens(spec_brand: dict | None) -> dict:
    """`DEFAULT_BRAND` overlaid with the spec's `brand:` block. Unknown keys are an error."""
    tokens = dict(DEFAULT_BRAND)
    for key, value in (spec_brand or {}).items():
        if key not in DEFAULT_BRAND:
            raise KeyError(f"unknown brand token {key!r}; "
                           f"known: {', '.join(sorted(DEFAULT_BRAND))}")
        tokens[key] = _checked_token(key, value)
    return tokens


def is_card(scene: dict) -> bool:
    return scene.get("kind") == "card"


# --- values ---------------------------------------------------------------------------

def _e(value: object) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def reveal_count(total: int, reveal: float) -> int:
    """How many of `total` items are on screen at `reveal`. CEILING, clamped.

    Ceiling, not floor, because an item becomes visible as soon as it STARTS arriving:
    `item_progress` then counts its value up over its own arrival, which is the
    "count-up on the headline number" the motion doc asks for. `reveal_count(n, 0.0)` is
    still 0 and `reveal_count(n, 1.0)` is still n, so the two ends are unchanged.
    """
    total = max(0, int(total))
    if reveal >= 1.0:
        return total
    return max(0, min(total, math.ceil(float(reveal) * total - 1e-9)))


def item_progress(index: int, total: int, reveal: float) -> float:
    """How far item `index` is into its OWN arrival, 0.0 to 1.0.

    The card's reveal is spread evenly across its items: item k owns the window
    [k/n, (k+1)/n]. Everything before it has landed, everything after it has not started.
    """
    if reveal >= 1.0:
        return 1.0
    return max(0.0, min(1.0, float(reveal) * max(1, int(total)) - int(index)))


def count_up(value, reveal: float = 1.0):
    """A number on its way to `value`, eased out. Anything not a number is itself.

    Cubic ease-out, `1 - (1 - r)**3`: fast at first and settling on the final figure,
    which is what reads as a counter rather than as a linear sweep.

    At `reveal >= 1.0` the value is returned UNCHANGED -- the same object, so the same
    type, so `_value_text` renders the same string it always did. That is what keeps every
    card golden byte-identical (tests/golden/card_*.html).

    A str is left alone even when it looks like a number: a `ranked_list` value may be a
    label, a `changed` value is a whole sentence, and parsing either to count it would be
    guessing at what the caller meant. A bool is left alone because a bool is not a figure.
    """
    if reveal >= 1.0:
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    eased = 1.0 - (1.0 - max(0.0, min(1.0, float(reveal)))) ** 3
    if isinstance(value, int):
        return int(round(value * eased))
    return float(round(value * eased, 1))


def _hidden(index: int, shown: int) -> str:
    """The attribute that keeps an unrevealed element's BOX while hiding its ink.

    `visibility:hidden`, never `display:none` and never leaving the element out: a card
    that reflowed as its rows arrived would read as a bug, not as an animation. Empty at
    `index < shown`, so a fully revealed card emits nothing new (see `count_up`).
    """
    return "" if index < shown else ' style="visibility:hidden"'


def _value_text(value: object) -> str:
    """`5` -> '5', `9.4` -> '9.4', `8.0` -> '8', `""`/None -> '' (no value column)."""
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)


def _rank_text(template: str, item: dict, index: int, count: int) -> str:
    """The caller supplies the rank; countdown reads `#3 … #1`, ranked_list `1 … N`.

    The fallback follows the template's direction, so a countdown that omits `rank` still
    counts down instead of silently counting up.
    """
    default = count - index if template == "countdown" else index + 1
    rank = item.get("rank", default)
    return f"#{rank}" if template == "countdown" else str(rank)


# --- rows -----------------------------------------------------------------------------

def _rows_ranked(template: str, items: list[dict], reveal: float = 1.0) -> str:
    out = []
    shown = reveal_count(len(items), reveal)
    for i, item in enumerate(items):
        value = _value_text(count_up(item.get("value"),
                                     item_progress(i, len(items), reveal)))
        cells = (f'<div class="rank">{_e(_rank_text(template, item, i, len(items)))}</div>'
                 f'<div class="label">{_e(item.get("label"))}</div>')
        if value:
            out.append(f'<li class="row"{_hidden(i, shown)}>{cells}'
                       f'<div class="value">{_e(value)}</div></li>')
        else:
            out.append(f'<li class="row novalue"{_hidden(i, shown)}>{cells}</li>')
    return "\n      ".join(out)


def _rows_changed(items: list[dict], reveal: float = 1.0) -> str:
    out = []
    shown = reveal_count(len(items), reveal)
    for i, item in enumerate(items):
        out.append(f'<li class="row changed"{_hidden(i, shown)}>'
                   f'<div class="label">{_e(item.get("label"))}</div>'
                   f'<div class="note">{_e(item.get("value"))}</div></li>')
    return "\n      ".join(out)


def _number(value: object) -> float:
    """A caller's value as a float, or 0.0. Never raises: a card must always render."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _ramp_index(value: object) -> int:
    """A 1-10 score to a HEATMAP_RAMP index. Clamped, so 0, 99 and None all render."""
    step = max(1, min(10, int(round(_number(value)))))
    return min(len(HEATMAP_RAMP) - 1, (step - 1) * len(HEATMAP_RAMP) // 10)


def _heatmap_score_text(value: object) -> str:
    """The score a cell PRINTS: clamped to 1-10, exactly like the colour it is given.

    `_ramp_index` already clamps, so without this a 99 colours as a 10 and prints 99 — the
    ramp and the number are two renderings of one score, and disagreeing is worse than
    either alone. Clamping is not fabrication, though: a value the card cannot read as a
    number at all (missing, "", "n/a") prints nothing and keeps the coolest step, which is
    what an absent score has always drawn. In range, the caller's own formatting stands, so
    a 9.4 crowd score is still a 9.4.
    """
    if value is None or value == "":
        return ""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if number < 1:
        return "1"
    if number > 10:
        return "10"
    return _value_text(value)


def _cells_heatmap(items: list[dict], reveal: float = 1.0) -> str:
    """Cells in the order the caller gave them, which for a calendar is DATE ORDER.

    A month of crowd scores painting itself in two seconds is the single best data-day
    visual this renderer has, and it is free: the caller already emits the cells in date
    order, so revealing them in list order IS revealing them in date order.
    """
    out = []
    shown = reveal_count(len(items), reveal)
    for i, item in enumerate(items):
        colour = HEATMAP_RAMP[_ramp_index(item.get("value"))]
        klass = "cell hot" if item.get("highlight") else "cell"
        style = f"background:{colour}" + ("" if i < shown else ";visibility:hidden")
        out.append(f'<li class="{klass}" style="{style}">'
                   f'<span class="d">{_e(item.get("label"))}</span>'
                   f'<span class="v">{_e(_heatmap_score_text(item.get("value")))}</span></li>')
    return "\n      ".join(out)


#: The curve's own coordinate space. The SVG scales to the card body with viewBox under a
#: UNIFORM scale (`preserveAspectRatio="xMidYMid meet"` against a box carrying this same
#: ratio), so these units are arbitrary but their RATIO is not: it is the shape the plot
#: occupies on the card. 1000x720 is close to the box the old stretched drawing was given,
#: so the curve keeps its proportions while the marker circle is finally round.
CURVE_W = 1000.0
CURVE_H = 720.0
CURVE_PAD = 40.0


def polyline_length(points) -> float:
    """The drawn length of a polyline, in the curve's own coordinate space.

    `stroke-dasharray` wants one number: the length of the whole path. SVG can compute it
    in a browser (`getTotalLength`), but this module is stdlib-only by contract and the
    page is screenshotted, not scripted -- so the length is computed here, in Python, off
    the same points the polyline is built from.
    """
    points = list(points)
    return float(sum(math.hypot(b[0] - a[0], b[1] - a[1])
                     for a, b in zip(points, points[1:])))


def _curve_svg(items: list[dict], annotation: dict, brand: dict, reveal: float = 1.0) -> str:
    """An inline SVG line chart. No library: this file is stdlib-only by contract."""
    values = [_number(item.get("value")) for item in items]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    inner = CURVE_H - 2 * CURVE_PAD
    step = CURVE_W / max(len(values) - 1, 1)
    points = [
        (round(index * step, 1), round(CURVE_H - CURVE_PAD - (value - lo) / span * inner, 1))
        for index, value in enumerate(values)
    ]
    poly = " ".join(f"{x},{y}" for x, y in points)
    area = f"0,{CURVE_H} {poly} {points[-1][0]},{CURVE_H}"

    # The line draws itself: the dash pattern is one dash as long as the whole path, and
    # the offset walks it on from nothing. At full reveal NEITHER attribute is emitted, so
    # the golden is the string it always was.
    dash = ""
    if reveal < 1.0:
        length = polyline_length(points)
        dash = (f' stroke-dasharray="{length:.1f}" '
                f'stroke-dashoffset="{length * (1.0 - float(reveal)):.1f}"')
    # The shaded area under the line, and the annotation dot with its label, belong to a
    # FINISHED curve: an area under half a line is a wedge, and a dot marking a point the
    # line has not reached yet marks nothing. `visibility` keeps their geometry.
    veil = "" if reveal >= 1.0 else ' visibility="hidden"'

    index = max(0, min(len(points) - 1, int(_number(annotation.get("index")))))
    mx, my = points[index]
    label = str(annotation.get("label") or "")
    # Flip the label inside the box near the right edge so it can never be clipped.
    anchor = "end" if mx > CURVE_W * 0.72 else "start"
    dx = -26 if anchor == "end" else 26
    mark = (
        f'<circle cx="{mx}" cy="{my}" r="16" fill="{brand["accent"]}" '
        f'stroke="{brand["bg"]}" stroke-width="7"{veil}/>'
        + (
            f'<text x="{mx + dx}" y="{max(my - 34, 52)}" text-anchor="{anchor}" '
            f'class="ann"{veil}>{_e(label)}</text>'
            if label
            else ""
        )
    )
    # Each tick is placed at its OWN point's x. `space-between` pinned label EDGES to the
    # container's edges instead, so a tick's centre drifted from its data point — worst at
    # the two ends, which are the ones a viewer actually reads off. The end labels anchor by
    # their near edge rather than their centre: `.body` clips its overflow, so a centred
    # label on the first or last point would lose half its text off the side of the card.
    last = len(points) - 1
    labels = "\n        ".join(
        f'<span style="left:{x / CURVE_W * 100:.3f}%;transform:'
        f'{"translateX(0)" if index == 0 else "translateX(-100%)" if index == last else "translateX(-50%)"}'
        f'">{_e(item.get("label"))}</span>'
        for index, ((x, _y), item) in enumerate(zip(points, items))
    )
    return (
        f'<div class="curve">\n'
        f'      <svg viewBox="0 0 {CURVE_W:.0f} {CURVE_H:.0f}" '
        f'preserveAspectRatio="xMidYMid meet" class="plot">\n'
        f'        <polygon points="{area}" class="fill"{veil}/>\n'
        f'        <polyline points="{poly}" class="line"{dash}/>\n'
        f'        {mark}\n'
        f'      </svg>\n'
        f'      <div class="xlabels">\n        {labels}\n      </div>\n'
        f'    </div>'
    )


# --- layout ---------------------------------------------------------------------------

def _heading_size(heading: str, unit: float) -> float:
    """Step the headline down so a long heading wraps instead of overrunning the card."""
    if len(heading) <= 34:
        return 4.4 * unit
    if len(heading) <= 52:
        return 3.8 * unit
    return 3.3 * unit


def _row_size(template: str, count: int, unit: float) -> float:
    """Rows shrink as they multiply, so 3 rows and 8 rows both fit the same canvas."""
    n = max(count, 1)
    if template == "changed":
        return max(min(2.45, 8.4 / n), MIN_CHANGED_ROW_UNITS) * unit
    return min(3.3, 18.0 / n) * unit


def spec_credits(spec: dict) -> str:
    """The "Credits" block a description carries, from the spec's own attribution.

    Sources: the spec's top-level `credits: [str]`, then every `media` scene's `credit:` line
    (deduped, first mention wins) — a credit burned into a frame belongs in the description
    too — then the spec's `disclaimer:`. Returns "" when the spec claims nothing, so a caller
    can append it unconditionally.

    NOT YET WIRED — nothing calls this. The spec keys are parsed and formatted here, but there
    is no end-credits plate and no publisher hook, so a spec's top-level `credits:`/
    `disclaimer:` currently appear nowhere in a rendered video or its description. Only a
    media scene's own `credit:` is burned into the frame. Do not mistake this for behaviour.
    """
    lines: list[str] = []
    for value in (spec.get("credits") or []):
        text = str(value).strip()
        if text and text not in lines:
            lines.append(text)
    for scene in (spec.get("scenes") or []):
        text = str((scene or {}).get("credit") or "").strip()
        if text and text not in lines:
            lines.append(text)
    block = ""
    if lines:
        block = "Credits:\n" + "\n".join(f"- {line}" for line in lines)
    disclaimer = str(spec.get("disclaimer") or "").strip()
    if disclaimer:
        block = f"{block}\n\n{disclaimer}" if block else disclaimer
    return block


def card_html(template: str, data: dict, brand: dict, width: int = 1296,
              height: int = 2304, *, transparent: bool = False,
              box: tuple[int, int, int, int] | None = None, fill: bool = False,
              reveal: float = 1.0) -> str:
    """The 9:16 card. `box`, `fill` and `transparent` are what the other scene kinds add.

    `box` is `(left, top, w, h)`: the card lives inside that rectangle of the page instead
    of over the whole canvas, and sizes its type to the rectangle's height — the same rule
    it always uses, applied to a smaller canvas. It is anchored to the rectangle's BOTTOM
    edge and grows upward only as far as it needs to, because the box's bottom is the edge
    that matters (it is what clears the attribution watermark) while its top is a ceiling:
    a three-row overlay should leave the footage above it alone, not pad itself out with
    dead plate. `transparent` drops the background gradient and turns the card into a
    semi-opaque plate. All three default off, and the default output is unchanged.

    `fill` is for the other kind of boxed card: a card SCENE with captions on, whose box is
    the whole frame below the caption band. There the box is not a ceiling but the canvas —
    hugging the rows would leave a slab of dead background between the captions and the card
    — so the card takes the box's full height and centres its rows in the leftovers, exactly
    as a full-frame card does.

    `reveal` is how much of the card is DRAWN yet, 0.0 to 1.0. It moves the `items` and
    nothing else: the brand line, the heading, the subheading, the rule and the footer are
    always on screen, because a data day's frame 0 IS a card and the stop test wants that
    frame lit (S1) and wants its headline to name the subject (S3). Rows that have not
    arrived keep their boxes under `visibility:hidden`, so the card never reflows; the
    heatmap fills in the caller's order, which for a calendar is date order; the wait
    curve draws itself with a dash offset and shows its shaded area and its annotation
    only once the line is finished. At the default 1.0 this function emits exactly the
    string it emitted before the parameter existed -- that is what keeps every golden in
    tests/golden/card_*.html byte-identical, and tests assert it directly.
    """
    if template not in TEMPLATES:
        raise ValueError(f"unknown card template {template!r}; known: {', '.join(TEMPLATES)}")
    items = data.get("items") or []
    if not isinstance(items, list):
        raise TypeError(f"card data.items must be a list, got {type(items).__name__}")
    cap = CAPS.get(template, MAX_ITEMS)
    if len(items) > cap:
        raise ValueError(f"card template {template!r} holds at most {cap} items, "
                         f"got {len(items)}; split it across two cards")
    if not 0.0 <= float(reveal) <= 1.0:
        raise ValueError(f"card reveal must be between 0.0 and 1.0, got {reveal!r}")

    heading = str(data.get("heading") or "")
    subheading = str(data.get("subheading") or "")
    box_x, box_y, box_w, box_h = box if box is not None else (0, 0, width, height)
    unit = box_h / 100.0
    h1_fs = _heading_size(heading, unit)
    row_fs = _row_size(template, len(items), unit)
    gap = 0.45 * row_fs

    if not items:
        body = '<div class="empty">Nothing to show right now</div>'
    elif template == "calendar_heatmap":
        body = f'<ul class="grid">\n      {_cells_heatmap(items, reveal)}\n    </ul>'
    elif template == "wait_curve":
        body = _curve_svg(items, data.get("annotation") or {}, brand, reveal)
    elif template == "changed":
        body = f'<ul class="rows">\n      {_rows_changed(items, reveal)}\n    </ul>'
    else:
        body = f'<ul class="rows">\n      {_rows_ranked(template, items, reveal)}\n    </ul>'
    sub = f'<p class="sub">{_e(subheading)}</p>' if subheading else ""

    if box is not None and fill:
        # The box IS the canvas: take all of it, top-anchored, rows centred in the leftovers.
        place = f"position:absolute;left:{box_x}px;top:{box_y}px;"
        size = f"width:{box_w}px;height:{box_h}px;"
    elif box is not None:
        # Anchored to the box's bottom edge, growing upward no further than its top.
        place = (f"position:absolute;left:{box_x}px;bottom:{height - box_y - box_h}px;"
                 f"max-height:{box_h}px;")
        size = f"width:{box_w}px;height:auto;"
    else:
        # `position:relative` so a transparent card still anchors its own plate.
        place = "position:relative;" if transparent else ""
        size = f"width:{box_w}px;height:{box_h}px;"
    # An auto-height card has no free space to hand a `flex:1` body, so the body is sized
    # by its rows instead of by the leftovers. A filled box has height, so it keeps flex:1.
    boxed = "" if box is None or fill else "\n.body{flex:0 0 auto}"
    page_bg = ("transparent" if transparent else
               f"radial-gradient(120% 60% at 18% 6%, {brand['bg_alt']} 0%, "
               f"{brand['bg']} 58%, {brand['bg']} 100%)")
    # The plate: a semi-opaque wash behind the card only, drawn as a pseudo-element so the
    # opacity never touches the text sitting on it.
    plate = "" if not transparent else f"""
.card{{border-radius:{2.2 * unit:.0f}px;overflow:hidden}}
.card::before{{content:'';position:absolute;inset:0;background:{brand['bg']};opacity:.74;
  border:{max(1.0, 0.12 * unit):.1f}px solid {brand['accent']};border-radius:inherit}}
.card>*{{position:relative;z-index:1}}"""
    # Per-template CSS. Empty for every existing template, so no golden can move.
    extra = ""
    if template == "calendar_heatmap":
        # A cell's width is deterministic — the card's content width, less the six gaps,
        # over seven columns — so the type is sized to the cell it actually gets instead of
        # to a guess from the item count (7 across is 7 across whether there are 14 cells or
        # 42; only the row count moves). `minmax(0,1fr)` is what lets a column shrink at all:
        # a bare `1fr` is `minmax(auto,1fr)`, and `aspect-ratio:1` ties a cell's automatic
        # minimum WIDTH to its own content HEIGHT, so tall type floors every column at ~230px
        # and seven of them overflow a 1089px card — the grid clips from day 5 onward, taking
        # the highlighted day with it. MEASURED 2026-09-16 on the first real render.
        gap_px = 0.55 * unit
        cell = (box_w - 9.0 * unit - 6.0 * gap_px) / 7.0
        extra = f"""
.grid{{list-style:none;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));
  gap:{gap_px:.0f}px}}
.cell{{aspect-ratio:1;min-width:0;border-radius:{0.55 * unit:.0f}px;display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:{0.15 * unit:.0f}px;
  color:{brand['bg']};font-weight:700}}
.cell .d{{font-size:{0.26 * cell:.1f}px;opacity:.9}}
.cell .v{{font-size:{0.42 * cell:.1f}px;font-variant-numeric:tabular-nums}}
.cell.hot{{outline:{max(2.0, 0.28 * unit):.1f}px solid {brand['accent']};
  outline-offset:{0.22 * unit:.1f}px}}"""
    elif template == "wait_curve":
        extra = f"""
.curve{{display:flex;flex-direction:column;gap:{1.2 * unit:.0f}px}}
.plot{{width:100%;aspect-ratio:{CURVE_W:.0f}/{CURVE_H:.0f};overflow:visible}}
.plot .line{{fill:none;stroke:{brand['accent']};stroke-width:12;stroke-linejoin:round;
  stroke-linecap:round}}
.plot .fill{{fill:{brand['accent']};opacity:.16}}
.plot .ann{{fill:{brand['fg']};font-family:{brand['font']};font-weight:700;font-size:52px}}
.xlabels{{position:relative;height:{2.2 * unit:.0f}px;color:{brand['muted']};
  font-size:{1.7 * unit:.1f}px;font-variant-numeric:tabular-nums}}
.xlabels span{{position:absolute;top:0;white-space:nowrap}}"""

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{width}px;height:{height}px;overflow:hidden;
  background:{page_bg};
  color:{brand['fg']};font-family:{brand['font']};-webkit-font-smoothing:antialiased}}
.card{{{place}{size}display:flex;flex-direction:column;
  padding:{4.6 * unit:.0f}px {4.5 * unit:.0f}px}}
.brand{{display:flex;align-items:baseline;justify-content:space-between;gap:{2 * unit:.0f}px;
  font-size:{1.55 * unit:.1f}px;letter-spacing:.07em;text-transform:uppercase;
  margin-bottom:{2.2 * unit:.0f}px}}
.bname{{font-weight:700;color:{brand['fg']}}} .burl{{color:{brand['muted']}}}
h1{{font-size:{h1_fs:.1f}px;line-height:1.06;font-weight:700;letter-spacing:-.01em;
  margin-bottom:{1.0 * unit:.0f}px;display:-webkit-box;-webkit-line-clamp:3;
  -webkit-box-orient:vertical;overflow:hidden}}
.sub{{font-size:{2.05 * unit:.1f}px;line-height:1.25;color:{brand['muted']};
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.rule{{width:{8 * unit:.0f}px;height:{0.45 * unit:.1f}px;border-radius:999px;
  background:{brand['accent']};margin:{2.2 * unit:.0f}px 0}}
.body{{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;
  overflow:hidden}}
.rows{{list-style:none;display:flex;flex-direction:column;gap:{gap:.0f}px}}
.row{{display:flex;align-items:center;gap:{1.1 * gap:.0f}px;font-size:{row_fs:.1f}px;
  background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10);
  border-radius:{0.5 * row_fs:.0f}px;padding:{0.55 * row_fs:.0f}px {0.8 * row_fs:.0f}px}}
.rank{{min-width:2.1em;font-size:1em;font-weight:700;color:{brand['accent']};
  font-variant-numeric:tabular-nums}}
.label{{flex:1;font-size:.84em;line-height:1.15;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}}
.value{{font-size:1em;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}}
.row.changed{{flex-direction:column;align-items:stretch;gap:{0.35 * row_fs:.0f}px;
  padding:{0.7 * row_fs:.0f}px {0.8 * row_fs:.0f}px}}
.row.changed .label{{flex:none;font-size:1em;font-weight:700;color:{brand['accent']};
  -webkit-line-clamp:1}}
.note{{font-size:.9em;line-height:1.32;color:{brand['muted']};white-space:normal}}
.empty{{border:{0.25 * unit:.0f}px dashed rgba(255,255,255,.22);border-radius:{1.6 * unit:.0f}px;
  padding:{5 * unit:.0f}px {3 * unit:.0f}px;text-align:center;font-size:{2.4 * unit:.1f}px;
  color:{brand['muted']}}}
.foot{{padding-top:{1.8 * unit:.0f}px;font-size:{1.7 * unit:.1f}px;font-weight:700;
  color:{brand['accent']}}}{boxed}{plate}{extra}
</style></head><body>
<div class="card">
  <div class="brand"><span class="bname">{_e(brand['name'])}</span><span class="burl">{_e(brand['url'])}</span></div>
  <h1>{_e(heading)}</h1>
  {sub}
  <div class="rule"></div>
  <div class="body">
    {body}
  </div>
  <div class="foot">{_e(data.get('footer'))}</div>
</div>
</body></html>"""
