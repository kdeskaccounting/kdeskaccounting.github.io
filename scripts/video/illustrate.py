#!/usr/bin/env python3
"""
Illustrated, animated 9:16 scenes -- a prototype path OUTSIDE the normal make_short.py /
build_video.py pipeline. Stephen ruled out licensed-photo stills ALONE for the Shorts in
`marketing/video/illustration-demo/` territory; he wants stick figures, emoji that pop on the
word being said, arrows that draw themselves, numbers that fly in -- the FirstParkVisit /
Zack D. Films look. This module renders exactly that from a small YAML scene spec,
deterministically, to a PNG sequence and an mp4. No narration, no captions, no audio mix:
those stay in make_short.py's territory (see the module's own docstring for
`audio_steps`/`cut_plan_json`). This writes `events.json` -- `[{t, sfx}]`, one entry per sound
cue, absolute scene time -- and stops there; wiring it into an audio mix is future work.

WHAT THE DRAWING SITS ON (2026-10-01). The ruling since this module was first written is that
illustration is an OVERLAY: it goes over video and over imagery, and the flat ground is
sprinkled in on the beats with no footage to carry. So two things follow, and both are here.
Every element wears a white border and a drop shadow (see STICKERS below) so it reads on a
photograph as well as on a flat ground; and when a scene names no ground at all it gets
GRAPHITE, the brand's one dark, rather than paper.

MECHANISM -- why a frame loop can be frame-exact
--------------------------------------------------
Every animation here is authored as a CSS `@keyframes` rule, applied `paused`, with
`animation-fill-mode: both` (so the 0% keyframe holds before the delay elapses and the 100%
keyframe holds once the animation is "done" -- there is never an undefined state). Each
animated node's natural start time, in scene-local seconds, is baked into BOTH its initial
`animation-delay` (so a freshly-loaded page already matches frame 0 with no JS run at all)
and a `data-t0` attribute. The page defines one function:

    window.seek(t) {
      for every node with a data-t0 attribute:
        node.style.animationDelay = (data-t0 - t) + "s"
    }

That is the entire seek mechanism (`seek_delay()` below is this arithmetic as a pure,
tested function). Negative delay is a standard CSS trick: it is exactly as if the
animation had been RUNNING since `t0` and were now paused at local time `t - t0`. Because
`animation-play-state` is always `paused`, no real wall-clock time ever elapses on the
document timeline -- confirmed empirically (a 1.5 s real sleep between `seek()` and reading
`getComputedStyle` changes nothing) -- so a frame loop that calls `seek(t)` then screenshots,
however long that takes in wall-clock Python/Chrome time, always captures exactly frame t.

Rendering: one self-contained HTML page per SCENE (`scene_html()`), screenshotted once per
frame via `render_sheets.screenshot(html_path, out_png, W, H, before_capture_js=f"window.seek({t})")`.
`render_sheets.screenshot()` could not run JS between captures -- its only mechanism was a
one-shot `chrome --headless --screenshot=` CLI call -- so it gained exactly one minimal
extension, a `before_capture_js` parameter (see render_sheets.py), rather than being forked:
when that parameter is given, the page is driven over Playwright instead of the CLI, and the
SAME page is kept open and reused across every call this module makes against it, so a
180-frame scene pays Chrome's page-navigation cost once. Call `render_sheets.close_driver()`
(done automatically at the end of `render_spec()`) to release it.

HARD RULE -- animate `transform`/`opacity`, never `left`/`top`: every position change in this
module (including a walking figure's translate) is a `transform: translate()` keyframe, never
a `left`/`top` keyframe, even though both compute correctly under `getComputedStyle`. Measured
directly while building this (two screenshots at identical `seek()` states, compared
pixel-for-pixel): a `left`/`top` animation driven purely by mutating `animation-delay` can
recompute its LAYOUT correctly while the PAINTED frame a headless screenshot captures still
shows the pre-seek position -- i.e. `getComputedStyle` agreeing with the math proves nothing
about what the screenshot will show. `transform`/`opacity` (what every other animation here
already used) do not have this problem. If a future element type needs to move, move it with
`transform`.

DETERMINISM: no randomness, no dates, no real-timer-driven motion anywhere in this module or
the pages it writes -- `seek(t)` is a pure function of the `t` the frame loop passes it, and
every pixel the page draws is a pure function of that same `t`. Rendering a spec twice
produces byte-identical PNGs (verified with md5sum while building this; not re-asserted on
every test run because a full render needs the render venv + a headless Chrome).

SPEC SCHEMA
-----------
A spec is a YAML mapping with one key, `scenes`, a non-empty list. Every scene:

    - kind: illustration        # required, literal
      seconds: 4.0               # required, > 0 (seconds * 30 fps need not be exact; frame
                                  #   count is round(seconds * fps))
      bg: "#343A46"               # optional, a #rgb or #rrggbb hex colour; default GRAPHITE
      sticker: true               # optional, default true -- see STICKERS below
      elements: [ ... ]           # required, non-empty list, see below

Positions (`at`, `from`, `to`) are always `[x, y]` fractions of the 1080x1920 frame, where
(0, 0) is the top-left corner; off-canvas staging is allowed up to [-0.2, 1.2]. An `enter`
block, where a type accepts one, is `{t: <seconds, scene-local>, how: <style>}`; omitting
`enter` renders the element always-on, unanimated. `sfx`, where a type accepts it, is one of
pop | chime | hit | whoosh and becomes one row of `events.json`. Every element also takes
`sticker: false` to opt out of the white border. Every time in a scene may also be written as
a WORD -- see TIMES AS WORDS below.

  emoji   {glyph, at, size: 0-1 fraction of frame width (default 0.16),
           enter?: {t, how: pop|fade}, sfx?}
          `size` sets font-size; pop is scale 0 -> 1.15 -> 1 over 0.35 s (POP_DUR), per spec.

  label   {text, at, size: 0-1 fraction of frame height (default 0.05),
           enter?: {t, how: pop|fade|slide-left|slide-right}, sfx?}
          slide-left enters FROM the right, sliding left into its resting place (and
          slide-right is the mirror of that) -- i.e. the `how` names the DIRECTION of travel,
          not which edge it starts from.

  tag     {text, at, enter?: {t, how: pop|fade|drop}, sfx?}
          A price-tag-shaped pill (notched + a punch-hole, via clip-path). drop is a fall
          from above the frame with a small bounce-settle, over 0.6 s (DROP_DUR).

  arrow   {from, to, enter?: {t, how: draw|fade}, sfx?}
          An SVG path with an arrowhead marker. draw is a stroke-dash reveal from `from` to
          `to` over 0.5 s (DRAW_DUR), using the SVG `pathLength="1"` normalisation so the
          dash math never depends on the path's actual on-screen length.

  squiggle {from, to, amplitude?: 0-0.1 fraction of frame WIDTH (default 0.02),
            waves?: positive int (default 3), enter?: {t, how: draw|fade}, sfx?}
          The scent line: a sine wave of `waves` full cycles around the from->to chord,
          revealed by the same `pathLength="1"` stroke-dash mechanism as `arrow` and with no
          arrowhead. An integer number of waves is what puts both ends of the path exactly on
          `from` and `to` (sin 0 = sin 2(pi)n = 0), which is why `waves` is not a float.

  figure  {pose: stand|point|walk, ...}
          stand/point: {at, enter?: {t, how: pop|fade}, sfx?} -- a static stick figure (SVG
            lines: head, torso, arms, legs; `point` angles one arm forward).
          walk: {from, to, t0, t1, sfx?} -- the whole figure translates from -> to, linearly,
            over [t0, t1]; independently, its two leg poses alternate every 0.25 s
            (LEG_STEP) for that same window, via a second, per-instance stepped keyframes
            animation (`steps(1)` per stop, so legs SNAP rather than tween). Both animations
            share `t0` as their `data-t0`, so they can never drift out of sync with each
            other, only ever with the frame clock, which `seek()` corrects every frame.

  box     {at, w, h: 0-1.2 fractions of frame width/height, label?,
           enter?: {t, how: pop|fade|box}, sfx?}
          A rounded rect, optionally captioned; `box` is its own gentler scale-in (0.55 ->
          1.05 -> 1, BOX_DUR) so a box behind a label does not fight the label's own pop.

  calendar {at, cols, cells: [{label, value, tone: low|mid|high, sfx?}, ...], step, t0?}
          A cols-wide grid (rows = ceil(len(cells)/cols)); cell i pops in at t0 + i*step
          (`calendar_cell_times()`), coloured by tone (low/mid/high -> green/amber/red).
          `sfx` on the calendar element is the default for every cell; a cell's own `sfx`
          overrides it. (The spec's worked example elides the trailing cells with `…` --
          this module requires a literal, fully-specified `cells` list.)

Everything above also accepts any JSON/YAML-safe extra keys; they are ignored.

STICKERS -- the white border and the drop shadow
------------------------------------------------
Every drawn element wears a bubbly white border and one soft dark shadow, so it reads as a
3D sticker laid ON the ground rather than as ink printed into it (Stephen's ruling, 2026-10-01:
illustration is b-roll laid over video and imagery, and a drawn element has to survive landing
on a photograph as well as on the graphite ground). That is the `.sticker` rule in SHARED_CSS:
four stacked white `drop-shadow`s, which is how a CSS filter spells an outline that follows an
arbitrary shape -- an emoji's silhouette, a stroked path, a run of bold type -- plus one
`drop-shadow(0 10px 14px rgba(0,0,0,.45))` for the lift.

Default ON for every scene and every element. A scene turns it off for all of its elements
with `sticker: false`, and any single element overrides the scene either way with its own
`sticker:` key. The class lands on the element's ROOT node, which is a measured choice rather
than a stylistic one -- see `_sticker_cls()` for what was measured and why.

Labels keep their `#1A1A1A` ink: black type inside a white border is what reads on graphite
AND on a photograph, which is the whole reason the border exists.

TIMES AS WORDS
--------------
Anywhere a scene takes a time in seconds -- `enter.t`, a figure walk's `t0`/`t1`, a calendar's
`t0` -- it may instead take a WORD REFERENCE, so an element lands on the word the narration is
saying rather than on a hand-counted second:

    enter: {when: {word: "cookies", nth: 1, offset: -0.05, edge: start}, how: pop}
    t0: {word: "patent"}        # a bare mapping carrying `word` is the same thing

`word` is matched against the narration's words case-insensitively with surrounding
punctuation stripped ("Smellitzer." matches `smellitzer`), `nth` picks which occurrence
(default 1), `edge` is the word's `start` (default) or `end`, and `offset` shifts it by
seconds (default 0). `resolve_times(scene, words)` turns every one of them into a float
against the word timings narrate.py writes beside the scene's WAV (`captions.read_words`);
`validate_spec` accepts either spelling, and the HTML builders below only ever see numbers.

STILL MISSING to carry a full ~28 s Short (see the report this module was built for):
captions overlaid on top of a rendered scene, and turning `events.json` into an actual audio
mix (`make_short.audio_steps` is the pattern to borrow, not reuse directly: this module's
events are per-element cues, not sfx_placements rows). Aligning the picture to the narration
is no longer missing: that is what `resolve_times()` above is.
"""
from __future__ import annotations

import copy
import html as _html
import json
import math
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_sheets as R  # stdlib-only to import; playwright stays inside R's lazy path

FPS = 30
W, H = 1080, 1920

HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")

#: The ground an illustration scene draws on when it names none. Stephen's ruling
#: (2026-10-01): the illustration IS the overlay now -- it goes over video and imagery, and the
#: flat ground is what gets "sprinkled in" on the beats that have no footage to carry. So the
#: default is the brand's one dark, #343A46, which is the ground the data cards already use in
#: the sibling ParkSheet repo: a Short that cuts between a photo beat and a drawn beat lands on
#: the same dark either way instead of flashing to paper. Paper is still allowed -- a scene
#: that wants it says `bg: "#F7F3EA"` -- it is simply no longer what you get by saying nothing.
GRAPHITE = "#343A46"
PAPER = "#F7F3EA"

ELEMENT_TYPES = {"emoji", "label", "tag", "arrow", "squiggle", "figure", "box", "calendar"}
SFX_KINDS = {"pop", "chime", "hit", "whoosh"}

#: A word reference -- the mapping form of a time (see TIMES AS WORDS in the module docstring).
WORDREF_KEYS = ("word", "nth", "offset", "edge")
WORD_EDGES = ("start", "end")
#: Stripped off both ends of a word before it is matched, so `word: "cookies"` finds
#: "cookies," and `word: "Smellitzer"` finds "Smellitzer.". Only the ENDS: an apostrophe
#: inside "don't" is part of the word.
WORD_TRIM = " \t\n\"'`.,!?;:()[]{}<>-—–‘’“”…"

#: Animation durations, in seconds. Named so a number only ever has one spelling in this file.
POP_DUR = 0.35
FADE_DUR = 0.30
SLIDE_DUR = 0.40
DROP_DUR = 0.60
BOX_DUR = 0.30
DRAW_DUR = 0.50
CELL_DUR = 0.20
#: How often a walking figure's legs swap, per the spec.
LEG_STEP = 0.25

#: how -> (css @keyframes name, duration). Every simple (non-figure, non-calendar-cell)
#: enter animation goes through this table.
HOW_ANIM = {
    "pop": ("kf-pop", POP_DUR),
    "fade": ("kf-fade", FADE_DUR),
    "slide-left": ("kf-slide-left", SLIDE_DUR),
    "slide-right": ("kf-slide-right", SLIDE_DUR),
    "drop": ("kf-drop", DROP_DUR),
    "box": ("kf-box", BOX_DUR),
    "draw": ("kf-draw", DRAW_DUR),
}

#: how -> seconds after enter.t that its SOUND fires (see `scene_events()`). A pop/fade/slide
#: sound lands on the moment the element starts appearing; a drop's "hit" is its landing, and
#: a draw's "hit" is the arrowhead reaching its target -- both are COMPLETION events, so they
#: are offset by the animation's own duration.
EVENT_OFFSET = {
    "pop": 0.0, "fade": 0.0, "slide-left": 0.0, "slide-right": 0.0, "box": 0.0,
    "drop": DROP_DUR, "draw": DRAW_DUR,
}

ENTER_HOW_BY_TYPE = {
    "emoji": {"pop", "fade"},
    "label": {"pop", "fade", "slide-left", "slide-right"},
    "tag": {"pop", "fade", "drop"},
    "arrow": {"draw", "fade"},
    "squiggle": {"draw", "fade"},
    "box": {"pop", "fade", "box"},
    "figure": {"pop", "fade"},  # stand/point only; walk does not use `enter`
}

TONE_COLORS = {"low": "#2E7D46", "mid": "#D98F1E", "high": "#C1443C"}

FIG_W, FIG_H = 120, 170

#: The scent line. `amplitude` is a fraction of the frame WIDTH (the same unit every other
#: size in this module uses for a horizontal measure) and is capped well below a quarter of
#: the frame: past that the "squiggle" is a loop, not a wisp of smell.
SQUIGGLE_AMPLITUDE = 0.02
SQUIGGLE_AMPLITUDE_MAX = 0.1
SQUIGGLE_WAVES = 3
#: Line segments per squiggle. 60 puts a vertex every ~6 px on a frame-tall line, which is
#: smaller than the 10 px stroke -- i.e. the polyline reads as a curve. Fixed, so the path a
#: spec renders twice is the same path twice.
SQUIGGLE_SAMPLES = 60


# --------------------------------------------------------------------------------------------
# Spec validation -- pure, no I/O, runs in the bare `uv run --with pytest` environment.
# --------------------------------------------------------------------------------------------

def is_illustration(scene) -> bool:
    """Is this scene one of ours? The one place that string is compared, as `media.is_media`
    and `cards.is_card` are for their kinds -- make_short.py asks it per scene."""
    return (scene or {}).get("kind") == "illustration"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _point(el, key, tag):
    v = el.get(key)
    if (not isinstance(v, (list, tuple)) or len(v) != 2 or not all(_num(c) for c in v)):
        raise ValueError(f"{tag}: '{key}' must be an [x, y] pair of numbers")
    x, y = v
    if not (-0.2 <= x <= 1.2 and -0.2 <= y <= 1.2):
        raise ValueError(f"{tag}: '{key}' {v!r} is outside the [-0.2, 1.2] fractional range")
    return (float(x), float(y))


def is_wordref(value):
    """Is this value a time written as a WORD rather than as a number?

    One rule, used by the validators and by `resolve_times` alike, so "a bare mapping
    carrying `word`" means exactly the same thing in both: a mapping with a `word` key.
    """
    return isinstance(value, dict) and "word" in value


def _check_wordref(ref, tag, key):
    """Raise unless `ref` is a usable word reference. Returns nothing; see `resolve_times`.

    Unknown keys are refused by name rather than ignored (the only place in this module that
    does): `offest: -0.05` would otherwise shift an element by nothing at all, and a word-timed
    pop that is 50 ms late is exactly the defect these mappings exist to remove.
    """
    unknown = set(ref) - set(WORDREF_KEYS)
    if unknown:
        raise ValueError(f"{tag}: unknown {key} key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(WORDREF_KEYS)}")
    if not isinstance(ref.get("word"), str) or not ref["word"].strip():
        raise ValueError(f"{tag}: {key}.word must be a non-empty string")
    nth = ref.get("nth", 1)
    if not isinstance(nth, int) or isinstance(nth, bool) or nth < 1:
        raise ValueError(f"{tag}: {key}.nth must be a positive integer (1 is the first time "
                         f"the narration says the word), got {nth!r}")
    edge = ref.get("edge", "start")
    if edge not in WORD_EDGES:
        raise ValueError(f"{tag}: {key}.edge must be one of {', '.join(WORD_EDGES)}, "
                         f"got {edge!r}")
    if not _num(ref.get("offset", 0.0)):
        raise ValueError(f"{tag}: {key}.offset must be a number of seconds")


def _check_time(value, tag, key):
    """Raise unless `value` is a non-negative number OR a word reference.

    Every time in a scene goes through this, so the two spellings cannot drift apart: a type
    that accepts `t0: 0.4` accepts `t0: {word: "patent"}`, and nothing but this function
    decides that.
    """
    if is_wordref(value):
        _check_wordref(value, tag, key)
        return
    if not _num(value) or value < 0:
        raise ValueError(f"{tag}: {key} must be a non-negative number of seconds, or a word "
                         f"reference like {{word: \"cookies\"}}, got {value!r}")


def _enter(el, tag, allowed_how):
    enter = el.get("enter")
    if enter is None:
        return None
    if not isinstance(enter, dict):
        raise ValueError(f"{tag}: 'enter' must be a mapping with 't' and 'how'")
    how = enter.get("how")
    if how not in allowed_how:
        raise ValueError(f"{tag}: enter.how must be one of {sorted(allowed_how)}, got {how!r}")
    # `when:` is the word-reference spelling of `t:` -- nothing but the key name differs, and
    # `resolve_times` folds it back onto `t` before anything renders. Both are accepted here
    # (and a word reference under `t:` too) so the schema has one answer to "may this be a
    # word?": yes, everywhere.
    if "when" in enter:
        if "t" in enter:
            raise ValueError(f"{tag}: enter carries both 't' and 'when', which are two "
                             f"spellings of the same time. Keep one.")
        _check_time(enter["when"], tag, "enter.when")
        return {"t": enter["when"], "how": how}
    _check_time(enter.get("t"), tag, "enter.t")
    return {"t": enter["t"], "how": how}


def _sfx(el, tag):
    if "sfx" in el and el["sfx"] not in SFX_KINDS:
        raise ValueError(f"{tag}: sfx must be one of {sorted(SFX_KINDS)}, got {el['sfx']!r}")


def _sticker(block, tag):
    """`sticker:` is a boolean on a scene and on an element alike, and nothing else.

    A STRING here is the trap worth refusing by hand: YAML's `sticker: "false"` is a non-empty
    string, which is truthy, so a spec that meant to turn the border off would render with it
    on and look identical to one that never asked. Both spellings go through this one check so
    the scene default and the element override cannot disagree about what counts as off.
    """
    if "sticker" in block and not isinstance(block["sticker"], bool):
        raise ValueError(f"{tag}: 'sticker' must be true or false, got {block['sticker']!r}")


def _validate_emoji(el, tag):
    if not isinstance(el.get("glyph"), str) or not el["glyph"]:
        raise ValueError(f"{tag}: emoji requires a non-empty 'glyph'")
    _point(el, "at", tag)
    size = el.get("size", 0.16)
    if not _num(size) or not (0 < size <= 1):
        raise ValueError(f"{tag}: emoji 'size' must be a number in (0, 1]")
    _enter(el, tag, ENTER_HOW_BY_TYPE["emoji"])


def _validate_label(el, tag):
    if not isinstance(el.get("text"), str) or not el["text"]:
        raise ValueError(f"{tag}: label requires non-empty 'text'")
    _point(el, "at", tag)
    size = el.get("size", 0.05)
    if not _num(size) or not (0 < size <= 1):
        raise ValueError(f"{tag}: label 'size' must be a number in (0, 1]")
    _enter(el, tag, ENTER_HOW_BY_TYPE["label"])


def _validate_tag(el, tag):
    if not isinstance(el.get("text"), str) or not el["text"]:
        raise ValueError(f"{tag}: tag requires non-empty 'text'")
    _point(el, "at", tag)
    _enter(el, tag, ENTER_HOW_BY_TYPE["tag"])


def _validate_arrow(el, tag):
    _point(el, "from", tag)
    _point(el, "to", tag)
    _enter(el, tag, ENTER_HOW_BY_TYPE["arrow"])


def _validate_box(el, tag):
    _point(el, "at", tag)
    for k in ("w", "h"):
        v = el.get(k)
        if not _num(v) or not (0 < v <= 1.2):
            raise ValueError(f"{tag}: box '{k}' must be a number in (0, 1.2]")
    if "label" in el and not isinstance(el["label"], str):
        raise ValueError(f"{tag}: box 'label' must be a string")
    _enter(el, tag, ENTER_HOW_BY_TYPE["box"])


def _validate_squiggle(el, tag):
    _point(el, "from", tag)
    _point(el, "to", tag)
    amplitude = el.get("amplitude", SQUIGGLE_AMPLITUDE)
    if not _num(amplitude) or not (0 <= amplitude <= SQUIGGLE_AMPLITUDE_MAX):
        raise ValueError(f"{tag}: squiggle 'amplitude' must be a number in "
                         f"[0, {SQUIGGLE_AMPLITUDE_MAX}] (a fraction of the frame width), "
                         f"got {amplitude!r}")
    waves = el.get("waves", SQUIGGLE_WAVES)
    if not isinstance(waves, int) or isinstance(waves, bool) or waves < 1:
        raise ValueError(f"{tag}: squiggle 'waves' must be a positive integer -- a whole "
                         f"number of waves is what lands both ends of the path on 'from' and "
                         f"'to' -- got {waves!r}")
    _enter(el, tag, ENTER_HOW_BY_TYPE["squiggle"])


def _validate_figure(el, tag):
    pose = el.get("pose")
    if pose not in ("stand", "point", "walk"):
        raise ValueError(f"{tag}: figure 'pose' must be one of stand, point, walk, got {pose!r}")
    if pose == "walk":
        _point(el, "from", tag)
        _point(el, "to", tag)
        t0, t1 = el.get("t0"), el.get("t1")
        _check_time(t0, tag, "figure walk 't0'")
        _check_time(t1, tag, "figure walk 't1'")
        # Only when BOTH are numbers: a word-referenced pair cannot be ordered until
        # `resolve_times` has the narration, and it re-checks this once they are floats.
        if _num(t0) and _num(t1) and t1 <= t0:
            raise ValueError(f"{tag}: figure walk 't1' must be a number greater than t0")
    else:
        _point(el, "at", tag)
        _enter(el, tag, ENTER_HOW_BY_TYPE["figure"])


def _validate_calendar(el, tag):
    _point(el, "at", tag)
    cols = el.get("cols")
    if not isinstance(cols, int) or isinstance(cols, bool) or cols < 1:
        raise ValueError(f"{tag}: calendar 'cols' must be a positive integer")
    cells = el.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError(f"{tag}: calendar 'cells' must be a non-empty list")
    for ci, cell in enumerate(cells):
        ctag = f"{tag} cell {ci}"
        if not isinstance(cell, dict):
            raise ValueError(f"{ctag}: must be a mapping")
        if not isinstance(cell.get("label"), str) or not cell["label"]:
            raise ValueError(f"{ctag}: requires a non-empty 'label'")
        if "value" not in cell or cell.get("value") in (None, ""):
            raise ValueError(f"{ctag}: requires a 'value'")
        if cell.get("tone") not in ("low", "mid", "high"):
            raise ValueError(f"{ctag}: 'tone' must be one of low, mid, high, got {cell.get('tone')!r}")
        if "sfx" in cell and cell["sfx"] not in SFX_KINDS:
            raise ValueError(f"{ctag}: sfx must be one of {sorted(SFX_KINDS)}")
    step = el.get("step")
    if not _num(step) or step <= 0:
        raise ValueError(f"{tag}: calendar 'step' must be a positive number")
    _check_time(el.get("t0", 0.0), tag, "calendar 't0'")


_VALIDATORS = {
    "emoji": _validate_emoji, "label": _validate_label, "tag": _validate_tag,
    "arrow": _validate_arrow, "squiggle": _validate_squiggle, "box": _validate_box,
    "figure": _validate_figure, "calendar": _validate_calendar,
}


def validate_spec(spec):
    """Raise ValueError with a specific, scene/element-addressed message on any problem.

    Pure: takes an already-parsed dict (from `yaml.safe_load` or a test literal), does no
    I/O, so it -- and everything that calls only this -- runs in the bare pytest environment
    with no render venv.
    """
    if not isinstance(spec, dict):
        raise ValueError("spec must be a mapping with a top-level 'scenes' list")
    scenes = spec.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("spec.scenes must be a non-empty list")
    for si, scene in enumerate(scenes):
        tag = f"scene {si}"
        if not isinstance(scene, dict):
            raise ValueError(f"{tag}: must be a mapping")
        if not is_illustration(scene):
            raise ValueError(f"{tag}: kind must be 'illustration', got {scene.get('kind')!r}")
        seconds = scene.get("seconds")
        if not _num(seconds) or seconds <= 0:
            raise ValueError(f"{tag}: seconds must be a positive number")
        # OPTIONAL, and absent means GRAPHITE -- not "unset". A scene that names a ground is
        # still held to a hex, because the value is interpolated into CSS unescaped.
        bg = scene.get("bg", GRAPHITE)
        if not isinstance(bg, str) or not HEX_RE.match(bg):
            raise ValueError(f"{tag}: bg must be a hex colour like '{PAPER}' "
                             f"(omit it for the {GRAPHITE} default), got {scene.get('bg')!r}")
        _sticker(scene, tag)
        elements = scene.get("elements")
        if not isinstance(elements, list) or not elements:
            raise ValueError(f"{tag}: elements must be a non-empty list")
        for ei, el in enumerate(elements):
            etag = f"{tag} element {ei}"
            if not isinstance(el, dict):
                raise ValueError(f"{etag}: must be a mapping")
            t = el.get("type")
            if t not in ELEMENT_TYPES:
                raise ValueError(f"{etag}: type must be one of {sorted(ELEMENT_TYPES)}, got {t!r}")
            _sfx(el, etag)
            _sticker(el, etag)
            _VALIDATORS[t](el, etag)


# --------------------------------------------------------------------------------------------
# Frame-time <-> animation-delay math, and the per-scene event list. Pure.
# --------------------------------------------------------------------------------------------

def frame_times(seconds, fps=FPS):
    """Scene-local seconds for each of `round(seconds * fps)` frames, at i / fps.

    round(), not ceil() or int(): a spec's `seconds` is meant to land on an exact frame
    count (4.0 s at 30 fps is 120 frames), and round() is the one of the three that survives
    `seconds` arriving as a float with the ordinary binary-fraction wobble (4.0 * 30 can come
    out 119.99999999999999 depending on how `seconds` was computed upstream).
    """
    n = round(float(seconds) * fps)
    if n < 1:
        raise ValueError("seconds too short to produce any frames at this fps")
    return [i / fps for i in range(n)]


def seek_delay(t_event, frame_t):
    """The `animation-delay` (seconds) that shows, at global clock `frame_t`, the state of
    an animation whose natural start is `t_event`.

    This is the whole mechanism: `paused` plus this one subtraction. Before the element's
    start (frame_t < t_event) the result is positive -- the animation is still in its
    "before" phase, showing the 0% keyframe because every animation here is `both`-filled --
    and from t_event on, the result is negative, i.e. the local clock reads exactly
    `frame_t - t_event` seconds into the timeline, which is the frame this exists to produce.
    """
    return round(float(t_event) - float(frame_t), 6)


def normalise_word(text):
    """A spoken word as `resolve_times` matches it: lower-cased, end punctuation stripped.

    "Smellitzer." -> `smellitzer`, "cookies," -> `cookies`, "don't" -> `don't`. The same
    function normalises BOTH sides of the comparison, so a spec may write the word with its
    punctuation attached and still match.
    """
    return str(text or "").strip().strip(WORD_TRIM).lower()


def word_rows(words):
    """`captions.read_words()` output -> [(normalised text, start, end)] for usable entries.

    `None` (no words.json, or a provider that returned no alignment) and a list with
    unusable rows in it both come back as the rows that ARE usable, so the caller's error
    message can show what the narration actually gave it.
    """
    rows = []
    for raw in words or ():
        if isinstance(raw, dict):
            text, start, end = raw.get("text"), raw.get("start"), raw.get("end")
        else:
            text = getattr(raw, "text", None)
            start, end = getattr(raw, "start", None), getattr(raw, "end", None)
        word = normalise_word(text)
        if not word:
            continue
        try:
            start, end = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            continue
        rows.append((word, start, max(start, end)))
    return rows


def resolve_time(value, rows, tag, key):
    """One time -- a number or a word reference -- as a float of scene-local seconds.

    A number passes through untouched (`float()` and nothing else), which is what keeps every
    spec written before word references rendering the same frames. A word reference is looked
    up in `rows` (`word_rows()` of the scene's own words.json): `nth` occurrence, `edge` end,
    plus `offset`, clamped at 0 because a scene has no frames before its first one.

    An unresolvable word raises ValueError naming the word, the nth it asked for, and every
    word the scene actually says -- the three things needed to fix the spec, since the usual
    cause is a word the narration spells differently (or a nth past how often it is said).
    """
    if not is_wordref(value):
        return float(value)
    want = normalise_word(value["word"])
    nth = int(value.get("nth", 1))
    edge = value.get("edge", "start")
    hits = [row for row in rows if row[0] == want]
    if len(hits) < nth:
        spoken = " ".join(row[0] for row in rows)
        raise ValueError(
            f"{tag}: {key} asks for occurrence {nth} of the word {value['word']!r} and this "
            f"scene's narration says it {len(hits)} time(s). The scene's words are: "
            + (spoken if spoken else "(none -- this scene has no word timings; narrate.py "
                                     "writes scene_NN.words.json beside the WAV)"))
    _word, start, end = hits[nth - 1]
    at = (end if edge == "end" else start) + float(value.get("offset", 0.0))
    return round(max(0.0, at), 4)


def resolve_times(scene, words):
    """A deep copy of `scene` with every word-referenced time replaced by a float.

    This is the join between the picture and the voice: `words` is what
    `captions.read_words(wav)` returns for THIS scene, whose times are already against the
    finished WAV, and frame 0 of the scene is t=0 of that WAV -- so a resolved time is
    directly a scene-local second, with no offset arithmetic anywhere.

    Deep-copied rather than edited in place: the scene dict belongs to the caller's parsed
    spec, and make_short.py validates the spec's own (unresolved) scenes at preflight, which
    a mutated scene would have made a different question the second time it was asked.

    Every time the schema has goes through it -- `enter.t` / `enter.when`, a figure walk's
    `t0`/`t1`, a calendar's `t0` -- and `enter.when` is folded onto `enter.t`, so the HTML
    builders below never learn that word references exist.
    """
    out = copy.deepcopy(scene)
    rows = word_rows(words)
    for index, el in enumerate(out.get("elements") or []):
        etag = f"element {index} ({el.get('type')})" if isinstance(el, dict) else f"element {index}"
        if not isinstance(el, dict):
            continue
        enter = el.get("enter")
        if isinstance(enter, dict):
            if "when" in enter:
                enter["t"] = resolve_time(enter.pop("when"), rows, etag, "enter.when")
            elif "t" in enter:
                enter["t"] = resolve_time(enter["t"], rows, etag, "enter.t")
        for key in ("t0", "t1"):
            if key in el:
                el[key] = resolve_time(el[key], rows, etag, key)
        # Re-checked here and not only in `_validate_figure`: a word-referenced pair cannot be
        # ordered before the narration is known, and a walk whose t1 landed on or before its
        # t0 is a negative CSS animation duration -- which renders as no walk at all.
        if el.get("type") == "figure" and el.get("pose") == "walk" and el["t1"] <= el["t0"]:
            raise ValueError(
                f"{etag}: the walk resolves to t0={el['t0']:.4f}s and t1={el['t1']:.4f}s, "
                f"so it would have no duration. The words these came from are said in the "
                f"other order, or are the same word.")
    return out


def calendar_cell_times(t0, step, n):
    """Absolute scene time each of `n` calendar cells starts popping in: one every `step`
    seconds from `t0`. Pure arithmetic; both the CSS delay and events.json read this."""
    return [round(float(t0) + i * float(step), 6) for i in range(int(n))]


def scene_events(scene):
    """[{t, sfx}] for one scene, absolute (scene-local) time, sorted by t.

    Takes a RESOLVED scene (see `resolve_times`): every time it reads is a number, because a
    word reference has no absolute seconds to put in an event row.

    One row per element that carries an `sfx` (or, for `calendar`, one row per CELL that
    resolves an `sfx` -- its own, or the calendar element's as a default). See
    `EVENT_OFFSET` for why a drop/draw's sound lands at completion, not at `enter.t`. Ties
    are broken by element order: `list.sort` is stable and this never reorders before
    sorting, so two events at the same `t` keep the order they were authored in.
    """
    events = []
    for el in scene["elements"]:
        kind = el["type"]
        if kind == "figure" and el.get("pose") == "walk":
            if "sfx" in el:
                events.append({"t": round(float(el["t0"]), 4), "sfx": el["sfx"]})
            continue
        if kind == "calendar":
            t0, step = float(el.get("t0", 0.0)), float(el["step"])
            default_sfx = el.get("sfx")
            for i, cell in enumerate(el["cells"]):
                sfx = cell.get("sfx", default_sfx)
                if sfx:
                    events.append({"t": round(t0 + i * step, 4), "sfx": sfx})
            continue
        sfx = el.get("sfx")
        if not sfx:
            continue
        enter = el.get("enter")
        t_start = float(enter["t"]) if enter else 0.0
        how = enter["how"] if enter else "fade"
        events.append({"t": round(t_start + EVENT_OFFSET.get(how, 0.0), 4), "sfx": sfx})
    events.sort(key=lambda e: e["t"])
    return events


# --------------------------------------------------------------------------------------------
# Pure HTML/CSS generation, one function per element type. Each returns (html, css) strings;
# `css` is "" for every type except `figure` (walk poses need per-instance @keyframes, since
# the from/to/t0/t1 differ per instance).
# --------------------------------------------------------------------------------------------

SHARED_CSS = f"""
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;width:{W}px;height:{H}px;overflow:hidden;
  font-family:-apple-system,'Helvetica Neue',Arial,sans-serif}}
.el{{position:absolute;transform:translate(-50%,-50%)}}
.anim{{animation-play-state:paused}}
.sticker{{filter:
  drop-shadow(0 0 2.5px #fff) drop-shadow(0 0 2.5px #fff) drop-shadow(0 0 2.5px #fff)
  drop-shadow(0 0 2px #fff) drop-shadow(0 10px 14px rgba(0,0,0,.45));}}
.emoji-glyph{{font-family:'Apple Color Emoji','Segoe UI Emoji',sans-serif;line-height:1;display:block}}
.label-text{{font-weight:800;letter-spacing:.01em;white-space:nowrap;color:#1A1A1A;display:block}}
.tag{{position:relative;display:inline-flex;align-items:center;justify-content:center;
  background:#E2574C;color:#fff;font-weight:800;border-radius:10px;padding:.3em .7em;
  clip-path:polygon(14% 0,100% 0,100% 100%,14% 100%,0 50%)}}
.tag:after{{content:"";position:absolute;left:20%;top:50%;width:.16em;height:.16em;
  margin-top:-.08em;background:#fff;border-radius:50%}}
.box-rect{{border-radius:28px;background:#1F3864}}
.figure line{{stroke:#1A1A1A;stroke-width:9;stroke-linecap:round}}
.figure circle{{fill:#1A1A1A}}
.cal-grid{{position:absolute;display:grid}}
.cal-cell{{display:flex;flex-direction:column;align-items:center;justify-content:center;
  border-radius:16px;color:#fff;font-weight:700}}
.cal-cell .cal-label{{font-size:.34em;opacity:.85;text-transform:uppercase;letter-spacing:.05em}}
.cal-cell .cal-value{{font-size:.6em}}
.arrow-svg{{position:absolute;left:0;top:0}}
@keyframes kf-pop{{0%{{opacity:0;transform:scale(0)}}60%{{opacity:1;transform:scale(1.15)}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes kf-fade{{0%{{opacity:0}}100%{{opacity:1}}}}
@keyframes kf-slide-left{{0%{{opacity:0;transform:translateX(160px)}}100%{{opacity:1;transform:translateX(0)}}}}
@keyframes kf-slide-right{{0%{{opacity:0;transform:translateX(-160px)}}100%{{opacity:1;transform:translateX(0)}}}}
@keyframes kf-drop{{0%{{opacity:0;transform:translateY(-560px)}}55%{{opacity:1;transform:translateY(26px)}}75%{{transform:translateY(-12px)}}90%{{transform:translateY(6px)}}100%{{opacity:1;transform:translateY(0)}}}}
@keyframes kf-box{{0%{{opacity:0;transform:scale(.55)}}70%{{opacity:1;transform:scale(1.05)}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes kf-draw{{0%{{stroke-dashoffset:1}}100%{{stroke-dashoffset:0}}}}
"""


def _el_id(idx):
    return f"el{idx}"


def _sticker_cls(el, default=True):
    """` sticker`, or `` for an element that opts out. See STICKER in the module docstring.

    The class goes on the element's ROOT node -- `.el`, the `arrow`/`squiggle` svg, the
    calendar grid -- not on the inner node that carries the animation, and that placement was
    measured rather than assumed. A CSS `filter` on the PARENT of an animated child is the
    classic way to rasterise that child into a single painted layer, which would freeze the
    pops and draws; a two-frame diff of every enter animation under this exact CSS (pop on an
    emoji, slide-left on a label, draw on an arrow, with the filter on the parent and, as a
    control, on the animated node itself) shows both placements animating identically, because
    nothing here is a compositor animation in the first place: every animation is `paused` and
    the frame loop repaints the whole page per `seek()`.

    What the two placements DO differ in is the border's width while an element is mid-pop.
    On the root the filter is applied before the child's `transform: scale()`, so the white
    edge stays 2.5 px of FRAME whatever the pop is doing; on the animated node it scales with
    it and all but vanishes at scale 0. A sticker's edge does not shrink when the sticker is
    thrown at the camera, so the root is also the right answer for the look.
    """
    return " sticker" if el.get("sticker", default) else ""


def _enter_parts(enter):
    """-> (style_fragment, data_attr_fragment, class_fragment) for a simple enter-animated
    element; all three are "" when `enter` is None, i.e. the element is always on-screen,
    unanimated, with nothing for `seek()` to touch."""
    if not enter:
        return "", "", ""
    t0, how = float(enter["t"]), enter["how"]
    name, dur = HOW_ANIM[how]
    style = f"animation:{name} {dur}s linear both paused;animation-delay:{t0:.4f}s;"
    return style, f' data-t0="{t0:.4f}"', " anim"


def _emoji_html(el, idx, sticker=True):
    x, y = el["at"]
    size_px = el.get("size", 0.16) * W
    glyph = _html.escape(el["glyph"])
    style, data, cls = _enter_parts(el.get("enter"))
    frag = (f'<div class="el{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
            f'style="left:{x*100:.4f}%;top:{y*100:.4f}%;">'
            f'<span class="emoji-glyph{cls}" style="font-size:{size_px:.1f}px;{style}"{data}>'
            f'{glyph}</span></div>')
    return frag, ""


def _label_html(el, idx, sticker=True):
    x, y = el["at"]
    size_px = fit_label_px(el["text"], el.get("size", 0.05) * H)
    text = _html.escape(el["text"])
    style, data, cls = _enter_parts(el.get("enter"))
    frag = (f'<div class="el{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
            f'style="left:{x*100:.4f}%;top:{y*100:.4f}%;'
            f'max-width:{SAFE_W*100:.1f}%;text-align:center;">'
            f'<span class="label-text{cls}" style="font-size:{size_px:.1f}px;{style}"{data}>'
            f'{text}</span></div>')
    return frag, ""


def _tag_html(el, idx, sticker=True):
    x, y = el["at"]
    text = _html.escape(el["text"])
    style, data, cls = _enter_parts(el.get("enter"))
    frag = (f'<div class="el{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
            f'style="left:{x*100:.4f}%;top:{y*100:.4f}%;">'
            f'<div class="tag{cls}" style="font-size:{0.045*H:.1f}px;{style}"{data}>{text}</div>'
            f'</div>')
    return frag, ""


def _box_html(el, idx, sticker=True):
    x, y = el["at"]
    w_px, h_px = el["w"] * W, el["h"] * H
    label = el.get("label")
    style, data, cls = _enter_parts(el.get("enter"))
    inner = (f'<span class="label-text" style="font-size:{0.045*H:.1f}px;color:#fff;">'
             f'{_html.escape(label)}</span>') if label else ""
    frag = (f'<div class="el{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
            f'style="left:{x*100:.4f}%;top:{y*100:.4f}%;">'
            f'<div class="box-rect{cls}" style="width:{w_px:.1f}px;height:{h_px:.1f}px;'
            f'display:flex;align-items:center;justify-content:center;{style}"'
            f'{data}>{inner}</div></div>')
    return frag, ""


#: How long before a `draw` arrow's own completion the arrowhead pops in. SVG markers do
#: NOT respect their path's `stroke-dasharray`/`stroke-dashoffset` -- they are drawn in full
#: at the path's endpoint regardless of how much of the stroke is "drawn on" -- so an
#: undecorated marker is fully visible from frame 0, long before the line reaches it (caught
#: by looking at the actual frames, exactly the QA step this module's spec called for). The
#: fix is to animate the marker's own content on its own short pop, timed to land exactly
#: when the line finishes.
ARROWHEAD_POP_DUR = 0.15


def _arrow_html(el, idx, sticker=True):
    x1, y1 = el["from"]
    x2, y2 = el["to"]
    px1, py1, px2, py2 = x1 * W, y1 * H, x2 * W, y2 * H
    enter = el.get("enter")
    style, data, cls = _enter_parts(enter)
    marker_id = f"arrowhead{idx}"
    if enter:
        t0, how = float(enter["t"]), enter["how"]
        _, line_dur = HOW_ANIM[how]
        if how == "draw":
            head_t0, head_dur, head_name = t0 + line_dur - ARROWHEAD_POP_DUR, ARROWHEAD_POP_DUR, "kf-pop"
        else:
            head_t0, head_dur, head_name = t0, line_dur, "kf-fade"
        head_style = (f"opacity:0;transform-origin:5px 4.5px;"
                      f"animation:{head_name} {head_dur}s linear both paused;"
                      f"animation-delay:{head_t0:.4f}s;")
        head_data = f' data-t0="{head_t0:.4f}"'
    else:
        head_style, head_data = "", ""
    frag = (
        f'<svg class="arrow-svg{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        f'<defs><marker id="{marker_id}" markerWidth="9" markerHeight="9" refX="5" refY="4.5" '
        f'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#1A1A1A" class="anim" '
        f'style="{head_style}"{head_data}/></marker></defs>'
        f'<path class="{cls.strip()}" pathLength="1" d="M{px1:.1f},{py1:.1f} L{px2:.1f},{py2:.1f}" '
        f'stroke="#1A1A1A" stroke-width="10" fill="none" stroke-linecap="round" '
        f'marker-end="url(#{marker_id})" style="stroke-dasharray:1;{style}"{data}/></svg>')
    return frag, ""


def squiggle_points(p_from, p_to, amplitude=SQUIGGLE_AMPLITUDE, waves=SQUIGGLE_WAVES,
                    samples=SQUIGGLE_SAMPLES, width=W, height=H):
    """The on-frame pixel points of a wavy path from `p_from` to `p_to`. Pure.

    A sine of `waves` whole cycles, `amplitude * width` px at the peak, measured along the
    NORMAL to the from->to chord rather than along y -- so a vertical scent line waves
    sideways and a diagonal one waves across itself, both the same way. An integer `waves`
    puts the first and last sample exactly on the two endpoints (sin 0 = sin 2(pi)n = 0),
    which is what `_validate_squiggle` is enforcing when it refuses a float.
    """
    x0, y0 = float(p_from[0]) * width, float(p_from[1]) * height
    x1, y1 = float(p_to[0]) * width, float(p_to[1]) * height
    dx, dy = x1 - x0, y1 - y0
    span = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / span, dx / span
    amp = float(amplitude) * width
    points = []
    for i in range(int(samples) + 1):
        s = i / float(samples)
        off = amp * math.sin(2 * math.pi * int(waves) * s)
        points.append((round(x0 + dx * s + nx * off, 2), round(y0 + dy * s + ny * off, 2)))
    return points


def _squiggle_html(el, idx, sticker=True):
    points = squiggle_points(el["from"], el["to"],
                             el.get("amplitude", SQUIGGLE_AMPLITUDE),
                             el.get("waves", SQUIGGLE_WAVES))
    head, *rest = points
    d = f"M{head[0]:.2f},{head[1]:.2f} " + " ".join(f"L{x:.2f},{y:.2f}" for x, y in rest)
    style, data, cls = _enter_parts(el.get("enter"))
    # `pathLength="1"` + `stroke-dasharray:1` is `arrow`'s mechanism verbatim: the dash maths
    # is normalised to the path's own length, so a 60-segment sine reveals end to end at a
    # constant rate without anything here knowing how long the curve actually is. No marker:
    # a scent line has no arrowhead (and the arrowhead was the one thing on `arrow` that
    # needed its own animation to stay hidden).
    frag = (f'<svg class="arrow-svg{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
            f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<path class="{cls.strip()}" pathLength="1" d="{d}" stroke="#1A1A1A" '
            f'stroke-width="10" fill="none" stroke-linecap="round" stroke-linejoin="round" '
            f'style="stroke-dasharray:1;{style}"{data}/></svg>')
    return frag, ""


def _figure_pose_svg(pose):
    head = '<circle cx="60" cy="22" r="20"/>'
    torso = '<line x1="60" y1="42" x2="60" y2="115"/>'
    if pose == "point":
        arms = '<line x1="60" y1="55" x2="20" y2="68"/><line x1="60" y1="55" x2="92" y2="96"/>'
    else:
        arms = '<line x1="60" y1="55" x2="30" y2="96"/><line x1="60" y1="55" x2="90" y2="96"/>'
    return head, torso, arms


LEGS_IDLE = '<line x1="60" y1="115" x2="40" y2="165"/><line x1="60" y1="115" x2="80" y2="165"/>'
LEGS_A = '<line x1="60" y1="115" x2="32" y2="165"/><line x1="60" y1="115" x2="92" y2="158"/>'
LEGS_B = '<line x1="60" y1="115" x2="92" y2="165"/><line x1="60" y1="115" x2="32" y2="158"/>'


def _walk_leg_keyframes(idx, duration):
    """Per-instance `@keyframes` for a walking figure's two leg poses, alternating every
    LEG_STEP seconds across the whole walk. Two mirror-image rules, one per leg group
    (`legsA{idx}` / `legsB{idx}`); each step's `animation-timing-function: steps(1)` makes the
    opacity SNAP rather than cross-fade, so exactly one leg pose is visible at a time."""
    n = max(2, round(duration / LEG_STEP))
    stops_a, stops_b = [], []
    for i in range(n + 1):
        pct = i * 100.0 / n
        a_visible = (i % 2 == 0)
        stops_a.append(
            f"{pct:.4f}%{{opacity:{1 if a_visible else 0};animation-timing-function:steps(1)}}")
        stops_b.append(
            f"{pct:.4f}%{{opacity:{0 if a_visible else 1};animation-timing-function:steps(1)}}")
    css = (f"@keyframes legsA{idx}{{{''.join(stops_a)}}}"
           f"@keyframes legsB{idx}{{{''.join(stops_b)}}}")
    return css


def _figure_html(el, idx, sticker=True):
    pose = el["pose"]
    eid = _el_id(idx)
    head, torso, arms = _figure_pose_svg(pose)
    if pose == "walk":
        x0, y0 = el["from"]
        x1, y1 = el["to"]
        t0, t1 = float(el["t0"]), float(el["t1"])
        dur = t1 - t0
        # Position is driven by an animated `transform: translate()` on an INNER element, not
        # by animating `left`/`top` on the (statically-positioned) outer `.el` wrapper. This
        # is not a style preference: measured directly (screenshots at identical `seek()`
        # states, compared pixel-for-pixel), a `left`/`top` keyframe driven purely by mutating
        # `animation-delay` recomputes correctly under `getComputedStyle` but does NOT
        # reliably reach a headless screenshot -- the painted frame can still show the
        # pre-seek position. `transform` (a compositor property, like every other animation
        # in this module -- pop/fade/slide/drop/box all animate transform/opacity) does not
        # have that problem. Every position animation in this file must stay on `transform`.
        dx, dy = (x1 - x0) * W, (y1 - y0) * H
        pos_name = f"walkpos{idx}"
        pos_kf = (f"@keyframes {pos_name}{{0%{{transform:translate(0px,0px)}}"
                  f"100%{{transform:translate({dx:.2f}px,{dy:.2f}px)}}}}")
        legs_kf = _walk_leg_keyframes(idx, dur)
        move_style = (f"animation:{pos_name} {dur:.4f}s linear both paused;"
                     f"animation-delay:{t0:.4f}s;")
        legs_a_style = (f"animation:legsA{idx} {dur:.4f}s steps(1) both paused;"
                        f"animation-delay:{t0:.4f}s;")
        legs_b_style = (f"animation:legsB{idx} {dur:.4f}s steps(1) both paused;"
                        f"animation-delay:{t0:.4f}s;")
        legs_svg = (f'<g class="anim" style="{legs_a_style}" data-t0="{t0:.4f}">{LEGS_A}</g>'
                    f'<g class="anim" style="{legs_b_style}" data-t0="{t0:.4f}">{LEGS_B}</g>')
        frag = (f'<div class="el{_sticker_cls(el, sticker)}" id="{eid}" '
                f'style="left:{x0*100:.4f}%;top:{y0*100:.4f}%;">'
                f'<div class="anim" style="{move_style}" data-t0="{t0:.4f}">'
                f'<svg width="{FIG_W}" height="{FIG_H}" viewBox="0 0 {FIG_W} {FIG_H}" '
                f'class="figure">{head}{torso}{arms}{legs_svg}</svg></div></div>')
        return frag, pos_kf + legs_kf
    x, y = el["at"]
    style, data, cls = _enter_parts(el.get("enter"))
    frag = (f'<div class="el{_sticker_cls(el, sticker)}{cls}" id="{eid}" '
            f'style="left:{x*100:.4f}%;top:{y*100:.4f}%;{style}"'
            f'{data}><svg width="{FIG_W}" height="{FIG_H}" viewBox="0 0 {FIG_W} {FIG_H}" '
            f'class="figure">{head}{torso}{arms}{LEGS_IDLE}</svg></div>')
    return frag, ""


#: Cell geometry as fractions of the frame width -- fixed, since the spec gives no per-element
#: size knob for a calendar (only `cols`, which drives the grid's own width).
#: Widest anything may be, as a fraction of W: the 80 % title-safe zone the card renderer
#: and the caption band already honour, plus a little, because an illustration label is
#: centred and has nothing beside it.
SAFE_W = 0.86
#: Average advance of a bold Helvetica/Arial capital, em per glyph. The caption band keeps a
#: per-glyph table (captions.py); a label is one line of a few words, so the mean is enough
#: here and it errs wide (M and W are the only glyphs that beat it).
LABEL_EM_PER_CHAR = 0.68


def fit_label_px(text, size_px, width=W, safe=SAFE_W, em=LABEL_EM_PER_CHAR):
    """The font size that keeps `text` on one line inside the safe width.

    The spec's `size` is a ceiling, not a promise: "ONE WEEK, SEVEN PRICES" at 0.042 H is
    1,150 px of bold caps on a 1,080 px frame and clipped both edges in the first demo
    render. Pure, so the test suite can pin the arithmetic without a browser.
    """
    max_px = (width * safe) / (max(len(text), 1) * em)
    return min(float(size_px), max_px)


CAL_CELL_W = 0.12
CAL_GAP = 0.016


def calendar_geometry(cols, width=W, safe=SAFE_W):
    """(cell_px, gap_px): CAL_CELL_W cells unless `cols` of them would leave the safe width.

    Seven 0.12 W cells plus gaps are 0.936 W -- inside the frame, outside the safe zone,
    and the first demo render showed the row flush against the left edge. Pure.
    """
    gap = CAL_GAP * width
    cell = min(CAL_CELL_W * width, (width * safe - (cols - 1) * gap) / cols)
    return cell, gap


def _calendar_html(el, idx, sticker=True):
    x, y = el["at"]
    cols = int(el["cols"])
    cells = el["cells"]
    step, t0 = float(el["step"]), float(el.get("t0", 0.0))
    n = len(cells)
    rows = math.ceil(n / cols)
    cell_w, gap = calendar_geometry(cols)
    cell_h = cell_w
    grid_w = cols * cell_w + (cols - 1) * gap
    grid_h = rows * cell_h + (rows - 1) * gap
    times = calendar_cell_times(t0, step, n)
    cell_html = []
    for i, (cell, t_i) in enumerate(zip(cells, times)):
        color = TONE_COLORS[cell["tone"]]
        label = _html.escape(str(cell["label"]))
        value = _html.escape(str(cell["value"]))
        style = (f"animation:kf-pop {CELL_DUR}s linear both paused;"
                 f"animation-delay:{t_i:.4f}s;background:{color};")
        cell_html.append(
            f'<div class="cal-cell anim" id="{_el_id(idx)}c{i}" data-t0="{t_i:.4f}" '
            f'style="{style}"><span class="cal-label">{label}</span>'
            f'<span class="cal-value">{value}</span></div>')
    grid_style = (f"left:{x*100:.4f}%;top:{y*100:.4f}%;transform:translate(-50%,-50%);"
                  f"width:{grid_w:.1f}px;height:{grid_h:.1f}px;"
                  f"grid-template-columns:repeat({cols},{cell_w:.1f}px);"
                  f"grid-auto-rows:{cell_h:.1f}px;gap:{gap:.1f}px;font-size:{cell_w*0.42:.1f}px;")
    frag = (f'<div class="cal-grid{_sticker_cls(el, sticker)}" id="{_el_id(idx)}" '
            f'style="{grid_style}">{"".join(cell_html)}</div>')
    return frag, ""


_BUILDERS = {
    "emoji": _emoji_html, "label": _label_html, "tag": _tag_html, "arrow": _arrow_html,
    "squiggle": _squiggle_html, "figure": _figure_html, "box": _box_html,
    "calendar": _calendar_html,
}


def render_element(el, idx, sticker=True):
    """-> (html, css) for one element dict. The thin, testable entry point `scene_html()`
    uses for every element; kept separate so "pure HTML generation per element type" can be
    asserted type by type without building a whole scene.

    `sticker` is the SCENE's default (see `scene_html`); the element's own `sticker:` key, when
    it has one, wins. Defaulted here as well as there so a caller testing one element type gets
    the treatment every element really renders with.
    """
    return _BUILDERS[el["type"]](el, idx, sticker)


def scene_html(scene):
    """The full, self-contained, frame-exact HTML page for one `kind: illustration` scene."""
    sticker = scene.get("sticker", True)
    html_parts, css_parts = [], []
    for idx, el in enumerate(scene["elements"]):
        h, c = render_element(el, idx, sticker)
        html_parts.append(h)
        if c:
            css_parts.append(c)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{SHARED_CSS}
{''.join(css_parts)}
html,body{{background:{scene.get("bg") or GRAPHITE}}}
</style></head><body>
{''.join(html_parts)}
<script>
window.seek = function(t) {{
  document.body.setAttribute('data-t', t.toFixed(4));
  document.body.setAttribute('data-frame', String(Math.round(t * {FPS})));
  var nodes = document.querySelectorAll('[data-t0]');
  for (var i = 0; i < nodes.length; i++) {{
    var node = nodes[i];
    var t0 = parseFloat(node.getAttribute('data-t0'));
    node.style.animationDelay = (t0 - t) + 's';
  }}
}};
window.seek(0);
</script>
</body></html>"""


# --------------------------------------------------------------------------------------------
# Rendering: needs the render venv (playwright) and ffmpeg. Everything above this line runs
# with the standard library alone.
# --------------------------------------------------------------------------------------------

def render_scene_frames(scene, scene_dir, fps=FPS):
    """One scene -> `scene_dir/scene.html`, `scene_dir/frame_NNNN.png` (one per frame, at
    `fps`), and `scene_dir/events.json`. Returns the list of frame PNG paths, in order.

    The page is written once and screenshotted once per frame through
    `render_sheets.screenshot(..., before_capture_js=...)`, which keeps that one page open
    across every call in this loop -- see render_sheets._pw_page -- so Chrome pays
    navigation cost once per scene, not once per frame.
    """
    scene_dir = pathlib.Path(scene_dir)
    scene_dir.mkdir(parents=True, exist_ok=True)
    html_path = scene_dir / "scene.html"
    html_path.write_text(scene_html(scene), encoding="utf-8")
    frames = []
    for i, t in enumerate(frame_times(scene["seconds"], fps)):
        out_png = scene_dir / f"frame_{i:04d}.png"
        R.screenshot(str(html_path), str(out_png), W, H, before_capture_js=f"window.seek({t:.6f})")
        frames.append(out_png)
    (scene_dir / "events.json").write_text(
        json.dumps(scene_events(scene), indent=2) + "\n", encoding="utf-8")
    return frames


def load_spec(spec_path):
    import yaml  # lazy: absent in the stdlib-only test environment, present in .venv-tts
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    validate_spec(spec)
    return spec


def _relink(concat_dir, frames):
    concat_dir = pathlib.Path(concat_dir)
    concat_dir.mkdir(parents=True, exist_ok=True)
    for old in concat_dir.glob("*.png"):
        old.unlink()
    for i, frame in enumerate(frames):
        (concat_dir / f"{i:06d}.png").symlink_to(pathlib.Path(frame).resolve())


def encode_mp4(frames_dir, out_mp4, fps=FPS):
    """A directory of sequentially-numbered `NNNNNN.png` frames -> a silent H.264 mp4."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-r", str(fps),
           "-i", str(pathlib.Path(frames_dir) / "%06d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_mp4)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    return pathlib.Path(out_mp4)


def render_spec(spec_path, out_dir, demo_name="demo.mp4", fps=FPS):
    """Render every scene of a YAML spec into `out_dir/scene_NN/` (its own PNG sequence +
    events.json each), then concatenate every scene's frames, in SCENE ORDER, into one
    silent mp4 at `out_dir/demo_name`. Returns that mp4's path.
    """
    spec = load_spec(spec_path)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_frames = []
    for si, scene in enumerate(spec["scenes"]):
        all_frames.extend(render_scene_frames(scene, out_dir / f"scene_{si:02d}", fps))
    R.close_driver()
    _relink(out_dir / "_concat", all_frames)
    return encode_mp4(out_dir / "_concat", out_dir / demo_name, fps)


def extract_qa_frames(mp4_path, out_dir, seconds):
    """ffmpeg `-ss <t> -frames:v 1` for each mark in `seconds`, written beside the mp4 as
    `frame_<t>s.png`. Returns the list of PNG paths, in the order `seconds` was given."""
    out_dir = pathlib.Path(out_dir)
    paths = []
    for t in seconds:
        out_png = out_dir / f"frame_{t}s.png"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(mp4_path),
               "-frames:v", "1", str(out_png)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        paths.append(out_png)
    return paths


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Render a kind: illustration YAML spec.")
    p.add_argument("--spec", required=True, help="path to a scenes.yaml")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--demo-name", default="demo.mp4")
    p.add_argument("--qa-frames", default="",
                   help="comma-separated second marks to extract after rendering, e.g. 0,1,2,3,4,5")
    a = p.parse_args(argv)
    out_mp4 = render_spec(a.spec, a.out, a.demo_name)
    print(f"wrote {out_mp4}")
    if a.qa_frames:
        seconds = [s.strip() for s in a.qa_frames.split(",") if s.strip() != ""]
        seconds_num = [float(s) if "." in s else int(s) for s in seconds]
        for pth in extract_qa_frames(out_mp4, a.out, seconds_num):
            print(f"wrote {pth}")


if __name__ == "__main__":
    main()
