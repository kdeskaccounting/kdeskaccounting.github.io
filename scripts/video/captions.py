#!/usr/bin/env python3
"""Word-timed ("karaoke") burned-in captions: the big-type TikTok look.

Why burn them in: YouTube's own caption track is small, at the bottom, and off unless the
viewer turns CC on, and most Shorts are watched muted — so on-screen words are how the hook
lands. The big draggable captions exist only in the mobile Shorts creator, never for an upload.

The rules are ported from kdeskgames/word-chain/video/captions.mjs, which is the look Stephen
asked for:

  * a cue is a PHRASE, not a sentence: at most `MAX_WORDS` words and `MAX_CHARS` characters;
  * a sentence end — or a trailing ":" / ";" — always breaks a cue, and a comma breaks it
    once the phrase has two words (so "so," never shows up as a card of its own);
  * a cue that is already full on words may still absorb ONE more if that next word ends in
    a bare comma and the result is not much longer than the usual cap — a look-ahead grace so
    a list item's trailing comma keeps its number instead of being orphaned as a cue the
    two-word comma rule can never fire on (e.g. "Sat Oct 10," stays one card instead of
    splitting into "Sat Oct" / "10,");
  * a cue stays up until the next one starts, capped at `HOLD_CAP_S` of silence, so the top of
    the frame never flickers between phrases;
  * inside a cue, word k is lit from its own start until the NEXT word's start, and the last
    word stays lit until the cue ends — the phrase is never on screen with nothing lit.

Each window becomes one pre-rendered transparent PNG (this ffmpeg build has no drawtext) that
make_short composites with `overlay` + `enable='between(t,a,b)'`.

An opt-in `short.plate:` block adds ONE more such PNG — the hook plate (`plate_html`), full
frame, over the first `seconds` of the Short, so frame 0 carries the subject and big type.
It rides the same pass as input 1, and every cue starting inside its window is dropped
(`drop_inside`): the plate IS the hook text, not a second line of it.

`caption_box()` is the single place that decides where a caption sits, exactly as
`media.overlay_box` is for a card plate. A spec picks one of `POSITIONS` (`top`, the default
and the original, `center` or `lower`) and one of `SIZES` (`default`, the day-3 geometry, or
`large`). It keeps the band inside the Shorts safe zone
(middle 80% of the width, nothing below 75% of the height), above any card overlay, and
therefore nowhere near the lower-frame zone Google Earth Studio burns its attribution
watermark into (`media.watermark_box`, measured: x >= 0.45, y >= 0.88).

Word timings come from `<scene>.words.json`, written beside each scene WAV by narrate.py:
`[{"text": "Magic", "start": 0.12, "end": 0.41}, ...]` in seconds against the finished WAV
(after the silence trim and the 0.3 s lead-in), or `null` when the provider gave none.

Pure string and arithmetic work, stdlib only, so this imports and tests in the bare
`uv run --with pytest` environment — and so narrate.py can import it without leaving its own
"standard library alone at import time" rule.
"""
from __future__ import annotations

import dataclasses
import html as _html
import json
import math
import os
import pathlib
import re

# --- the phrase rules -------------------------------------------------------------------

#: A cue is a phrase, not a sentence. Both caps come from the reference implementation.
MAX_WORDS = 3
MAX_CHARS = 20

#: How much longer than MAX_CHARS the look-ahead grace (see `_orphans_if_alone`, `build_cues`)
#: may let a cue run when the word that would overflow it is the one closing the phrase —
#: enough for a short trailing item like a date's day number, not enough to defeat the cap.
GRACE_CHARS = 6

#: A cue holds past its last word by this much, ...
HOLD_PAD_S = 0.35
#: ... to at least this long in total, ...
MIN_CUE_S = 0.6
#: ... but never more than this far past the last word it contains. Beyond that the speaker
#: has moved on and a stale phrase at the top of the frame reads as a stuck render.
HOLD_CAP_S = 2.2
#: Left between a cue and the next one, so two cues never overprint on a single frame.
GAP_S = 0.02
#: A cue shorter than this cannot be read at all, so it is dropped rather than flashed.
MIN_VISIBLE_S = 0.15
#: A word window shorter than this is a flash, not a highlight.
MIN_WINDOW_S = 0.03

_SENTENCE_END = (".", "!", "?", "—")
#: Trailing marks that can hide a sentence end: `"Stop."` ends the sentence just as `Stop.` does.
_TRAILING = "\"'”’)]}»"

_TIGHTEN = re.compile(r"\s+([,.!?—])")


# --- the geometry -----------------------------------------------------------------------
#
# Every fraction is of the frame, so the same numbers hold for the 1080x1920 delivered Short
# and the 1296x2304 composite, exactly as in media.py.

#: The Shorts safe zone's side margin: captions live inside the middle 80% of the width.
SAFE_X_FRAC = 0.10

#: Nothing a viewer must read goes below this — the platform's own UI owns the bottom quarter.
SAFE_BOTTOM_FRAC = 0.75

#: Vertical centre of the caption band, per position. The band used to be top-only, which
#: on a letterboxed media scene put the words on the blurred bar rather than on the picture;
#: 11 of the 13 reference Shorts measured in the 2026-09-19 teardown use centre or lower
#: third. `top` is unchanged, so every spec that does not ask for a position is unmoved.
BAND_CENTER_FRAC: dict = {"top": 0.22, "center": 0.46, "lower": 0.62}

#: Nominal band height, per `captions.size`. `default` is the day-3 geometry and is what a
#: spec that does not ask for a size still gets, byte for byte. `large` grew it because at
#: FONT_BAND_FRAC 0.347 a two-word cue wraps, and a wrapped two-word cue reads BETTER than
#: one shrunk to fit a single line.
BAND_H_FRAC_DEFAULT = 0.16
BAND_H_FRAC = 0.185

#: Height the band may never fall below; past it the type is too small to read on a phone.
MIN_BAND_H_FRAC = 0.09

#: The band may move up this far — but no further — to clear a card that sits unusually high.
BAND_TOP_MIN_FRAC = 0.05

#: Visible clearance kept between the band and a card overlay, so "not overlapping" also
#: looks like "not crowding". Same idea as media.CLEARANCE_FRAC.
CLEARANCE_FRAC = 0.02


# --- type -------------------------------------------------------------------------------

#: Font size as a fraction of the band's height, per `captions.size`. 0.30 -> 0.347 is about
#: +15% of linear type in a band that also grew, i.e. roughly +28% against the 92.1 px the
#: day-3 build burned in — which is exactly what `default` still produces.
FONT_BAND_FRAC_DEFAULT = 0.30
FONT_BAND_FRAC = 0.347

#: How many lines a cue may wrap to, per `captions.size`. font_size() divides the character
#: count by this before stepping the type down, so a long cue wraps instead of shrinking to
#: nothing. `default` is one line, the model every caption rendered under until v4.
MAX_CUE_LINES_DEFAULT = 1
MAX_CUE_LINES = 2

#: size name -> (band height fraction, font fraction, lines). The whole of what `size` means:
#: `default` is the geometry of every Short rendered before v4 and must stay byte-identical,
#: `large` is the feed-stopper type the 2026-09-19 teardown measured on the reference channels.
SIZE_TABLE = {
    "default": (BAND_H_FRAC_DEFAULT, FONT_BAND_FRAC_DEFAULT, MAX_CUE_LINES_DEFAULT),
    "large": (BAND_H_FRAC, FONT_BAND_FRAC, MAX_CUE_LINES),
}
SIZES = tuple(SIZE_TABLE)

#: Average advance width of a bold sans glyph, in em — the PLATE's width model
#: (`plate_max_word_chars`). Cues stopped using it on 2026-09-23: measured against what the
#: band page actually renders it is an underestimate (see ADVANCE_EM), and a cue sized to it
#: wrapped to three lines in a two-line band, or ran a long word off the frame.
FONT_EM_PER_CHAR = 0.58

#: Advance widths, in em, of the face the captions ACTUALLY render in: system Arial Bold.
#: The brand stack names Carlito first, but caption_html carries no @font-face (only
#: render_sheets.BASE_CSS does, and the band page never includes it), so Chrome falls
#: through to Arial. Measured with FreeType from /System/Library/Fonts/Supplemental/Arial
#: Bold.ttf; the suite re-measures it wherever Pillow and that file exist. The page is
#: `text-transform: uppercase`, so only capitals, digits and punctuation are on screen.
ADVANCE_EM = {
    "A": 0.722, "B": 0.722, "C": 0.722, "D": 0.722, "E": 0.667, "F": 0.611, "G": 0.778,
    "H": 0.722, "I": 0.278, "J": 0.556, "K": 0.722, "L": 0.611, "M": 0.833, "N": 0.722,
    "O": 0.778, "P": 0.667, "Q": 0.778, "R": 0.722, "S": 0.667, "T": 0.611, "U": 0.722,
    "V": 0.667, "W": 0.944, "X": 0.667, "Y": 0.667, "Z": 0.611,
    "0": 0.556, "1": 0.556, "2": 0.556, "3": 0.556, "4": 0.556, "5": 0.556, "6": 0.556,
    "7": 0.556, "8": 0.556, "9": 0.556,
    ".": 0.278, ",": 0.278, ":": 0.333, ";": 0.333, "!": 0.333, "?": 0.611, "'": 0.238,
    '"': 0.474, "-": 0.333, "(": 0.333, ")": 0.333, "$": 0.556, "%": 0.889, "&": 0.722,
    "/": 0.278, " ": 0.278,
}
#: A glyph the table does not list (a curly quote, an accented capital) is assumed as wide
#: as an M: wrong only on the safe side.
DEFAULT_ADVANCE_EM = 0.833
SPACE_EM = ADVANCE_EM[" "]
#: Mirrors `letter-spacing:.01em` in caption_html.
LETTER_SPACING_EM = 0.01
#: The band width a cue is fitted to is this much narrower than the box. Measured in the
#: renderer's own headless Chrome (2026-09-23): a line sized to the box lands at 864.0 px of
#: 864 exactly, and caption_html then writes the size to one decimal place — rounded UP
#: half the time — so an exact fit wrapped "THE OUTSIDE WAS" to three lines. One percent is
#: 8.6 px at 1080 wide: invisible, and more than any rounding this page does.
FIT_SLACK_FRAC = 0.01
#: Floor: below this a caption is unreadable on a phone, so the cue wraps instead.
MIN_FONT_PX = 44.0

#: The reference's yellow. Overridable per spec.
DEFAULT_ACCENT = "#ffe234"

POSITIONS = ("top", "center", "lower")

#: The first seconds of a Short read faster than the rest of it, so the cue caps tighten
#: there: 1-2 words a card instead of 3. Off (0.0) unless a spec asks — HOOK_S is the v4
#: value a spec writer (and the ParkSheet spec builder) puts in `captions.hook_seconds`;
#: nothing in this module reads it, because the window always comes off the spec.
HOOK_S = 3.0
HOOK_MAX_WORDS = 2
HOOK_MAX_CHARS = 14

#: The word pop. 1.0 means no transform at all and NO extra CSS, so a spec that does not ask
#: for it renders the byte-identical PNG it rendered before this existed.
DEFAULT_POP = 1.0
#: REQUIRED whenever the pop is on: transform:scale() needs display:inline-block, and an
#: inline-block span's scaled glyphs overflow its layout box, so the word gap has to be a
#: margin. Without it "WHICH DISNEY" renders as "WHICHDISNEY".
SPAN_MARGIN_EM = 0.07
#: Scale from slightly below the optical centre, so the lit word grows into the line rather
#: than lifting off it.
POP_ORIGIN = "50% 62%"

_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


def size_rules(size: str = "default") -> tuple:
    """(band height fraction, font fraction, lines) for a `captions.size`, refused by name.

    The one place a size name turns into numbers, so `default` cannot drift away from the
    geometry every Short rendered before v4.
    """
    try:
        return SIZE_TABLE[size]
    except (KeyError, TypeError):
        raise ValueError(f"unknown caption size {size!r}; "
                         f"known: {', '.join(SIZES)}") from None


# --- the data ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Word:
    """One spoken word, on the FINAL timeline (scene offset already added)."""
    text: str
    start: float
    end: float


@dataclasses.dataclass(frozen=True)
class Cue:
    """One phrase on screen, with the words it is made of."""
    text: str
    start: float
    end: float
    words: tuple


@dataclasses.dataclass(frozen=True)
class Window:
    """One pre-rendered PNG's time window: cue `cue` with word `word` lit."""
    cue: int
    word: int
    start: float
    end: float


@dataclasses.dataclass(frozen=True)
class CaptionConfig:
    enabled: bool = False
    accent: str = DEFAULT_ACCENT
    position: str = "top"
    size: str = "default"
    pop: float = DEFAULT_POP
    hook_seconds: float = 0.0


# --- the words file -----------------------------------------------------------------------

def words_path(wav_path) -> pathlib.Path:
    """`…/scene_03.wav` -> `…/scene_03.words.json`."""
    wav = pathlib.Path(wav_path)
    return wav.with_name(f"{wav.stem}.words.json")


def write_words(wav_path, words) -> pathlib.Path:
    """Write a scene's word timings beside its WAV. `None` is written as JSON `null`.

    Through a temp file, for the reason write_wav uses one: a crash must never leave half a
    JSON array in the cache beside a good WAV, because the next run would read it as truth.
    """
    path = words_path(wav_path)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(words, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_words(wav_path):
    """A scene's word timings, or None when there are none / the file is unusable."""
    try:
        raw = words_path(wav_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, list) else None


# --- cues ---------------------------------------------------------------------------------

def _word(raw, offset: float):
    """One entry of a words.json array -> a Word on the final timeline, or None if unusable."""
    if isinstance(raw, Word):
        text, start, end = raw.text, raw.start, raw.end
    elif isinstance(raw, dict):
        text, start, end = raw.get("text"), raw.get("start"), raw.get("end")
    else:
        return None
    text = str(text or "").strip()
    if not text:
        return None
    try:
        start = float(start)
        end = float(end)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(start) and math.isfinite(end)):
        return None
    start = max(0.0, start) + offset
    return Word(text=text, start=start, end=max(start, end + offset))


#: Marks that break a cue on their own, independent of how many words are already in it —
#: a sentence end, or a trailing ":" / ";" (a list lead-in reads exactly like a sentence end:
#: what follows is a new phrase, so it must not glue to the word before the colon).
_HARD_BREAK = _SENTENCE_END + (":", ";")


def _breaks_after(text: str, count: int) -> bool:
    """Does a cue end after this word? The reference's rule, quote marks seen through."""
    bare = text.rstrip(_TRAILING)
    if bare.endswith(_HARD_BREAK):
        return True
    return bare.endswith(",") and count >= 2


def _orphans_if_alone(text: str) -> bool:
    """Would this word, flushed as the first word of a new cue, be unable to break on its
    own right after? Only a trailing comma has that problem: `_breaks_after` needs the phrase
    to already have two words before a comma fires. Every hard-break mark (`_HARD_BREAK`)
    flushes at count 1, so a word ending in one of those is a perfectly fine one-word cue and
    does not need the look-ahead grace in `build_cues` below.
    """
    return text.rstrip(_TRAILING).endswith(",")


def _cue_text(words) -> str:
    return _TIGHTEN.sub(r"\1", " ".join(w.text for w in words))


def caps_at(start: float, hook_seconds: float) -> tuple:
    """(words, characters) for a cue starting at `start`. The hook reads faster."""
    if hook_seconds and float(start) < float(hook_seconds):
        return HOOK_MAX_WORDS, HOOK_MAX_CHARS
    return MAX_WORDS, MAX_CHARS


def build_cues(words, scene_offset: float = 0.0, limit: float | None = None,
               hook_seconds: float = 0.0) -> list:
    """One scene's words -> the cues that appear on the FINAL timeline.

    `scene_offset` is where the scene's audio starts in the concatenated Short; `limit` is the
    absolute time its captions must not outlive (the scene's own end), so a held phrase never
    bleeds over the cut into the next scene. `hook_seconds` tightens the caps for the cues
    that start inside the opening window (`caps_at`); 0.0 — the default — is the caps this
    has always used, everywhere.
    """
    items = [w for w in (_word(raw, float(scene_offset)) for raw in (words or []))
             if w is not None]

    groups: list[list] = []
    current: list = []
    for word in items:
        max_words, max_chars = caps_at(current[0].start if current else word.start,
                                       hook_seconds)
        nxt = current + [word]
        if current and (len(nxt) > max_words or len(_cue_text(nxt)) > max_chars):
            # Look-ahead grace: a cue already full on words would normally flush right here,
            # orphaning `word` as the start of the next cue. That is fine for a hard-break
            # word (it flushes itself right back off, a valid one-word cue) but not for a
            # word ending in a bare comma: `_breaks_after` needs two words before a comma
            # fires, so the orphan would sit stuck as the start of a longer cue, splitting a
            # list item's number from its neighbour — "Sat Oct" / "10," instead of one card.
            # Letting it join instead, when that does not blow the cap by much, keeps
            # "Sat Oct 10," together. Bounded to MAX_WORDS + 1 words and MAX_CHARS +
            # GRACE_CHARS characters, and only ever taken once per cue (the append+flush
            # below empties `current`, so the next word starts a fresh cue like normal).
            # The same grace covers a cue that filled on CHARACTERS rather than words
            # ("Saturday, October" is two words and 17 characters) and a short closing
            # token that ends the phrase ("10," "26." "3,"): a numeral alone on a card
            # reads as scrambled whatever mark it carries. A long closer ("card.") is not
            # rescued, so ordinary prose keeps its 3-word rhythm.
            closer = word.text.strip()
            short_closer = len(closer) <= 4 and closer.endswith(("," ,) + _HARD_BREAK)
            if (len(current) >= 2 and len(nxt) <= max_words + 1
                    and (_orphans_if_alone(word.text) or short_closer)
                    and len(_cue_text(nxt)) <= max_chars + GRACE_CHARS):
                current.append(word)
                groups.append(current)
                current = []
                continue
            groups.append(current)
            current = []
        current.append(word)
        if _breaks_after(word.text, len(current)):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    cues = [Cue(text=_cue_text(g), start=g[0].start, end=g[-1].end, words=tuple(g))
            for g in groups]

    held = []
    for i, cue in enumerate(cues):
        # A cue owns the screen until the next one claims it — the gap between two phrases
        # belongs to the one already up, or the top of the frame blinks between every card.
        # Two things bound that: HOLD_CAP_S of silence (past it the speaker has moved on and a
        # stale phrase reads as a stuck render) and, on the last cue, nothing to hold for.
        floor = max(cue.end + HOLD_PAD_S, cue.start + MIN_CUE_S)
        if i + 1 < len(cues):
            end = min(cues[i + 1].start - GAP_S, max(floor, cue.end + HOLD_CAP_S))
        else:
            end = floor
        if limit is not None:
            end = min(end, float(limit))
        held.append(dataclasses.replace(cue, end=end))
    return [c for c in held if c.end - c.start > MIN_VISIBLE_S]


def word_windows(cues, min_window: float = MIN_WINDOW_S) -> list:
    """The karaoke timing: one window per spoken word, tiling its cue end to end."""
    out = []
    for ci, cue in enumerate(cues):
        last = len(cue.words) - 1
        for wi, word in enumerate(cue.words):
            start = cue.start if wi == 0 else max(cue.start, word.start)
            end = cue.end if wi == last else min(cue.end, cue.words[wi + 1].start)
            if end - start < min_window:
                continue
            out.append(Window(cue=ci, word=wi, start=start, end=end))
    return out


# --- geometry -------------------------------------------------------------------------------

def caption_box(width: int, height: int, card_top: int | None = None,
                position: str = "top", size: str = "default"):
    """The caption band as (left, top, right, bottom). The one place captions are placed.

    `position` picks the band's centre out of BAND_CENTER_FRAC and `size` its height out of
    SIZE_TABLE; a band that would reach into the platform's own bottom quarter is lifted whole.

    `card_top` is the top edge of whatever a scene draws below the captions — in practice
    `media.overlay_box(...)[1]`, the card plate on a media scene. The band shrinks from the
    BOTTOM to clear it (the band's top is the more valuable edge: it is what keeps captions
    off the platform's own chrome), and only once the band would drop below a readable height
    does it move up instead. A card that owns the whole top of the frame is refused rather
    than overlapped — a caption drawn over a card is unreadable and so is the card.
    """
    if position not in POSITIONS:
        raise ValueError(f"unknown caption position {position!r}; "
                         f"known: {', '.join(POSITIONS)}")
    centre = BAND_CENTER_FRAC[position]
    band_h_frac = size_rules(size)[0]
    x = round(width * SAFE_X_FRAC)
    top = round(height * (centre - band_h_frac / 2))
    bottom = round(height * (centre + band_h_frac / 2))
    floor = round(height * SAFE_BOTTOM_FRAC)
    if bottom > floor:
        # The platform's own UI owns the bottom quarter. A band that would reach into it is
        # lifted whole rather than shrunk: it is a position, not a collision.
        top -= bottom - floor
        bottom = floor
    min_h = round(height * MIN_BAND_H_FRAC)
    if card_top is not None:
        ceiling = round(card_top) - round(height * CLEARANCE_FRAC)
        if bottom > ceiling:
            bottom = ceiling
            if bottom - top < min_h:
                top = max(round(height * BAND_TOP_MIN_FRAC), bottom - min_h)
    if bottom - top < min_h:
        raise ValueError(
            f"no room for a caption band in a {width}x{height} frame: a card whose top edge "
            f"is at y={card_top} leaves {max(0, bottom - top)}px, under the {min_h}px a "
            f"caption needs to stay readable on a phone. Move the card down, or turn "
            f"captions off for this spec.")
    return (x, top, int(width) - x, bottom)


# --- type -------------------------------------------------------------------------------------

def word_em(word: str, pop: float = DEFAULT_POP) -> float:
    """The layout width of one word, in em, as the band page sets it: its glyph advances in
    capitals, the letter-spacing on each, and — when the pop is on — the inline-block
    margin on both sides of its span."""
    text = str(word).upper()
    em = sum(ADVANCE_EM.get(ch, DEFAULT_ADVANCE_EM) for ch in text)
    em += len(text) * LETTER_SPACING_EM
    if float(pop) > DEFAULT_POP:
        em += 2 * SPAN_MARGIN_EM
    return em


def line_em(words, pop: float = DEFAULT_POP) -> float:
    """The layout width of one line of words, in em: the words and the spaces between."""
    words = list(words)
    gaps = max(0, len(words) - 1) * (SPACE_EM + LETTER_SPACING_EM)
    return sum(word_em(w, pop) for w in words) + gaps


def tightest_lines_em(words, rows: int, pop: float = DEFAULT_POP) -> float:
    """The narrowest the WIDEST line can be, over every split of `words` into at most `rows`
    consecutive lines. Chrome wraps greedily, and greedy first-fit wraps into the fewest
    lines any split can, so type sized to this width wraps to `rows` lines or fewer — which
    is the whole question, because the band holds exactly `rows` lines of it."""
    words = list(words)
    if not words:
        return 0.0
    whole = line_em(words, pop)
    if rows <= 1 or len(words) == 1:
        return whole
    best = whole
    for k in range(1, len(words)):
        best = min(best, max(line_em(words[:k], pop), tightest_lines_em(words[k:], rows - 1, pop)))
    return best


def wrap(words, px: float, usable: float, pop: float = DEFAULT_POP) -> list:
    """How the band page wraps `words` at `px` of type into `usable` px: greedy first-fit
    at word boundaries. (A hyphen is one more place Chrome MAY break, which can only pack a
    line fuller, never produce more lines than this.)"""
    lines, current = [], []
    for w in words:
        trial = current + [w]
        if current and line_em(trial, pop) * px > usable:
            lines.append(current)
            current = [w]
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def font_size(text: str, box, lines: int | None = None, size: str = "default",
              pop: float = DEFAULT_POP) -> float:
    """Type size for one cue: as big as the band allows, wrapped over at most `lines`.

    `size` picks the font fraction and the default line count out of SIZE_TABLE; `lines`
    overrides the line count alone. Measuring over more than one line is what lets the type
    stay big: a two-word cue that wraps reads better than the same cue shrunk onto one line.

    The width model is the band page's own layout (`tightest_lines_em`): Arial Bold capitals
    at their real advances, the letter-spacing, the pop's span margins when `pop` is on, and
    a greedy wrap at word boundaries into at most `lines` lines. It is sized to the split
    whose widest line is narrowest — since CSS cannot break inside a word and the page is
    overflow:hidden, the longest word is a line of its own in that measure, never halved.

    Before 2026-09-23 this was `chars / lines` at a flat 0.58 em a glyph. Arial Bold
    capitals average 0.66-0.75 em, so a cue measured as fitting two lines wrapped to three
    (3 x 1.06 x 123 px in a 355 px band: the top of "119" and the bottom of "FIGURES," gone)
    and a 13-character word sized to the 864 px box ran past both edges of the 1080 px
    frame. MIN_FONT_PX is the floor below which the cue is unreadable anyway. The fit
    leaves FIT_SLACK_FRAC of the box unused, because the page rounds the size it is given.
    """
    left, top, right, bottom = box
    band_h, usable = bottom - top, right - left
    band_frac, size_lines = size_rules(size)[1:]
    rows = max(1, int(size_lines if lines is None else lines))
    words = str(text or "").split()
    widest = tightest_lines_em(words, rows, pop)
    room = usable * (1 - FIT_SLACK_FRAC)
    fit = room / widest if widest > 0 else band_frac * band_h
    return max(MIN_FONT_PX, min(band_frac * band_h, fit))


def _checked_accent(value: object) -> str:
    """The accent lands in a <style> block unescaped, so it is validated as a hex literal."""
    text = str(value)
    if not _HEX.match(text):
        raise ValueError(f"caption accent must be a hex colour like '#ffe234', got {text!r}")
    return text


def caption_html(cue: Cue, lit: int, accent: str, brand: dict, width: int, box,
                 pop: float = DEFAULT_POP, size: str = "default") -> str:
    """One frame of one cue: every word of the phrase, with word `lit` in the accent colour.

    The page is the BAND, not the whole frame — make_short overlays it at the band's own y —
    because a full-frame RGBA PNG per spoken word is six times the memory for nothing. The
    side padding is the safe-zone margin, so the geometry still comes from `caption_box`
    alone.

    ALL CAPS (Stephen's call, 2026-09-16: `text-transform: uppercase`, so words.json and the
    cue text stay as spoken while the frame reads in capitals). White on a thick dark stroke,
    `paint-order: stroke fill` so the outline sits behind the
    glyph instead of eating into it: the captions have to stay legible over bright footage as
    well as over a dark card.

    `pop` scales the lit word. At DEFAULT_POP (1.0) it emits no CSS at all, and `size`
    defaults to the day-3 type, so a spec that asks for neither renders the byte-identical
    PNG it rendered before either existed.
    """
    colour = _checked_accent(accent)
    left, top, _right, bottom = box
    band_h = bottom - top
    fs = font_size(cue.text, box, size=size, pop=pop)
    pop_css = "" if float(pop) <= DEFAULT_POP else (
        f"\n.line span{{display:inline-block;margin:0 {SPAN_MARGIN_EM}em}}"
        f"\n.lit{{transform:scale({float(pop):.2f});transform-origin:{POP_ORIGIN};"
        f"text-shadow:0 {0.08 * fs:.1f}px {0.13 * fs:.1f}px rgba(0,0,0,.72), "
        f"0 0 {0.24 * fs:.0f}px {colour}66}}")
    spans = []
    for i, word in enumerate(cue.words):
        text = _html.escape(word.text, quote=True)
        spans.append(f'<span class="lit">{text}</span>' if i == lit else f"<span>{text}</span>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{int(width)}px;height:{band_h}px;overflow:hidden;background:transparent;
  font-family:{brand['font']};-webkit-font-smoothing:antialiased}}
.band{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  padding:0 {left}px}}
.line{{text-align:center;font-weight:700;font-size:{fs:.1f}px;line-height:1.06;
  letter-spacing:.01em;text-transform:uppercase;color:#FFFFFF;
  -webkit-text-stroke:{0.085 * fs:.1f}px #0A0E14;paint-order:stroke fill;
  text-shadow:0 {0.07 * fs:.1f}px {0.11 * fs:.1f}px rgba(0,0,0,.72)}}
.lit{{color:{colour}}}{pop_css}
</style></head><body>
<div class="band"><div class="line">{" ".join(spans)}</div></div>
</body></html>"""


# --- the hook plate ---------------------------------------------------------------------------

#: The hook plate: one transparent full-frame PNG over the first seconds of the Short, so
#: frame 0 carries the subject AND big text — which is what the feed's thumbnail and the
#: first 400 ms both need. Type sizes as fractions of the frame height, from the verified
#: plate.png: a 52 px letter-spaced kicker in the accent over a 186 px white headline at
#: 1080x1920, on a 15 px dark stroke with `paint-order: stroke fill` so the outline sits
#: behind the glyph instead of eating into it.
PLATE_KICKER_PX_FRAC = 0.027
PLATE_HEADLINE_PX_FRAC = 0.097
PLATE_STROKE_FRAC = 0.08
DEFAULT_PLATE_S = 1.4

#: Every frame in this pipeline is 9:16 (1080x1920 delivered, 1296x2304 composite), so a
#: width measured against a height is a constant of the pipeline — which is what lets the
#: plate's box be checked at PREFLIGHT, from the fractions alone, before a frame size exists.
PLATE_ASPECT = 9 / 16

#: The smallest headline a plate may ask for, as a fraction of the frame height. Below
#: this the "headline" is no longer the biggest type in the Short — it is a caption in the
#: middle of the frame — and the plate stops doing the one job it has on frame 0. The
#: ceiling is PLATE_HEADLINE_PX_FRAC itself: everything about the layout above (the
#: safe-zone box, the watermark clearance, two lines inside the band) was verified at that
#: size, and a larger one would overflow a geometry nothing has measured.
PLATE_HEADLINE_FRAC_MIN = 0.05


def plate_max_word_chars(headline_frac: float = PLATE_HEADLINE_PX_FRAC) -> int:
    """The longest WORD a plate headline may carry AT THIS TYPE SIZE.

    Unlike a cue, the plate has no step-down: `plate_html` burns one fixed fraction of the
    frame height on an `overflow:hidden` page with no `overflow-wrap`, so a word too wide
    for the safe-zone box is not shrunk and not broken — it is clipped at the frame edge,
    silently, in a render nobody watches frame by frame. Hence the refusal in
    `plate_settings`, and hence `short.plate.headline_frac`: a subject with a longer word
    rides a smaller headline rather than no plate at all.

    The same width model as `font_size`: the longest word, at FONT_EM_PER_CHAR per glyph.
    It FLOORS, so the cap it returns always fits.
    """
    return int((PLATE_ASPECT * (1 - 2 * SAFE_X_FRAC))
               / (float(headline_frac) * FONT_EM_PER_CHAR))


#: The cap of the DEFAULT fraction — what a plate that asks for no `headline_frac` gets:
#:
#:   0.5625 * (1 - 2*0.10) / (0.097 * 0.58) = 8.0 characters
#:
#: i.e. 7, with "MICKEYS" of the verified plate.png clearing it by exactly one character.
#: Quoted by name in CLAUDE.md and mirrored by ParkSheet, so it stays the default's cap
#: rather than becoming whatever a given plate asked for.
PLATE_MAX_WORD_CHARS = plate_max_word_chars(PLATE_HEADLINE_PX_FRAC)


@dataclasses.dataclass(frozen=True)
class Plate:
    text: str
    kicker: str = ""
    seconds: float = DEFAULT_PLATE_S
    position: str = "center"
    headline_frac: float = PLATE_HEADLINE_PX_FRAC


def plate_settings(short: dict):
    """The `short.plate:` block, or None. Absent means no plate and no extra input."""
    block = (short or {}).get("plate")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise TypeError(f"short.plate must be a mapping, got {type(block).__name__}")
    known = {f.name for f in dataclasses.fields(Plate)}
    unknown = set(block) - known
    if unknown:
        raise KeyError(f"unknown plate key(s) {', '.join(sorted(unknown))}; "
                       f"known: {', '.join(sorted(known))}")
    text = str(block.get("text") or "").strip()
    if not text:
        raise ValueError("short.plate.text is empty; a plate with no text is a blank frame "
                         "over the hook. Drop the block, or name the subject.")
    headline_frac = float(block.get("headline_frac", PLATE_HEADLINE_PX_FRAC))
    if not PLATE_HEADLINE_FRAC_MIN <= headline_frac <= PLATE_HEADLINE_PX_FRAC:
        raise ValueError(
            f"short.plate.headline_frac must be in "
            f"[{PLATE_HEADLINE_FRAC_MIN}, {PLATE_HEADLINE_PX_FRAC}]; got {headline_frac!r}. "
            f"Smaller than {PLATE_HEADLINE_FRAC_MIN} of the frame is not a headline, and "
            f"larger than {PLATE_HEADLINE_PX_FRAC} overflows the layout that was verified.")
    max_chars = plate_max_word_chars(headline_frac)
    wide = [word for word in text.split() if len(word) > max_chars]
    if wide:
        raise ValueError(
            f"short.plate.text word(s) too wide for the frame: {', '.join(wide)}. The plate "
            f"burns one fixed type size on a page that cannot wrap inside a word, so a word "
            f"over {max_chars} characters is CLIPPED at the frame edge rather "
            f"than shrunk. Shorten the headline, move the long word to the kicker (which is "
            f"a fifth of the size), or set short.plate.headline_frac (>= "
            f"{PLATE_HEADLINE_FRAC_MIN}) to buy the word the width it needs.")
    position = str(block.get("position", "center"))
    if position not in POSITIONS:
        raise ValueError(f"unknown plate position {position!r}; "
                         f"known: {', '.join(POSITIONS)}")
    seconds = float(block.get("seconds", DEFAULT_PLATE_S))
    if not 0.0 < seconds <= 4.0:
        raise ValueError(f"short.plate.seconds must be in (0, 4.0]; got {seconds!r}")
    return Plate(text=text, kicker=str(block.get("kicker") or "").strip(),
                 seconds=seconds, position=position, headline_frac=headline_frac)


def plate_html(plate: Plate, accent: str, brand: dict, width: int, height: int) -> str:
    """The plate as a full-frame transparent page. ALL CAPS, like every caption.

    The headline is `plate.headline_frac` of the frame height — PLATE_HEADLINE_PX_FRAC
    unless the spec asked for less — and the stroke stays proportional to it, so a plate
    that shrinks to fit a long word shrinks as one piece. Nothing else about the layout
    moves: the kicker, the safe-zone padding and the band centre are what they were.
    """
    colour = _checked_accent(accent)
    kicker_px = height * PLATE_KICKER_PX_FRAC
    head_px = height * plate.headline_frac
    centre = BAND_CENTER_FRAC[plate.position]
    kicker = (f'<div class="kicker">{_html.escape(plate.kicker, quote=True)}</div>'
              if plate.kicker else "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{int(width)}px;height:{int(height)}px;overflow:hidden;
  background:transparent;font-family:{brand['font']};-webkit-font-smoothing:antialiased}}
.plate{{position:absolute;left:0;top:{round(height * centre)}px;width:{int(width)}px;
  transform:translateY(-50%);text-align:center;padding:0 {round(width * SAFE_X_FRAC)}px}}
.kicker{{font-size:{kicker_px:.0f}px;font-weight:700;letter-spacing:.22em;
  text-transform:uppercase;color:{colour};margin-bottom:{0.4 * kicker_px:.0f}px;
  -webkit-text-stroke:{PLATE_STROKE_FRAC * kicker_px:.1f}px #0A0E14;paint-order:stroke fill}}
.head{{font-size:{head_px:.0f}px;font-weight:700;line-height:1.02;letter-spacing:-.01em;
  text-transform:uppercase;color:#FFFFFF;
  -webkit-text-stroke:{PLATE_STROKE_FRAC * head_px:.1f}px #0A0E14;paint-order:stroke fill;
  text-shadow:0 {0.06 * head_px:.1f}px {0.10 * head_px:.1f}px rgba(0,0,0,.72)}}
</style></head><body>
<div class="plate">{kicker}<div class="head">{_html.escape(plate.text, quote=True)}</div></div>
</body></html>"""


def drop_inside(cues, seconds: float):
    """Cues that start strictly AFTER `seconds`. The plate IS the hook text, so the
    word-by-word captions do not also run underneath it — two texts on one frame is too much
    to read.

    Strictly after, not at: ffmpeg's `between(t,a,b)` is inclusive at BOTH ends, so a cue
    starting on the plate's own last instant would overprint it for a frame.
    """
    if not seconds:
        return list(cues)
    return [cue for cue in cues if cue.start > float(seconds)]


# --- the spec surface ------------------------------------------------------------------------

def settings(spec: dict, override: bool | None = None) -> CaptionConfig:
    """The spec's top-level `captions:` block, with `--captions/--no-captions` on top.

    Default OFF. Every walkthrough Short in marketing/video/ predates captions and must render
    byte-identically until its spec opts in, which is also what keeps the goldens honest.

      captions:
        enabled: true
        accent: "#ffe234"     # hex only: it is interpolated into CSS unescaped
        position: top         # top | center | lower
        size: large           # default (the day-3 band and type) | large
        pop: 1.14             # scale the lit word; 1.0 emits no extra CSS at all
        hook_seconds: 3.0     # cues starting before this take the tighter hook caps
    """
    block = (spec or {}).get("captions")
    if block is None:
        block = {}
    if not isinstance(block, dict):
        raise TypeError(f"spec `captions:` must be a mapping, got {type(block).__name__}")
    known = {f.name for f in dataclasses.fields(CaptionConfig)}
    unknown = set(block) - known
    if unknown:
        raise KeyError(f"unknown captions key(s) {', '.join(sorted(unknown))}; "
                       f"known: {', '.join(sorted(known))}")
    position = str(block.get("position", "top"))
    if position not in POSITIONS:
        raise ValueError(f"unknown caption position {position!r}; "
                         f"known: {', '.join(POSITIONS)}")
    size = str(block.get("size", "default"))
    size_rules(size)          # refused by name, exactly as `position` is
    enabled = bool(block.get("enabled", False))
    if override is not None:
        enabled = bool(override)
    pop = float(block.get("pop", DEFAULT_POP))
    if not DEFAULT_POP <= pop <= 1.5:
        raise ValueError(f"captions.pop must be in [1.0, 1.5]; got {pop!r}")
    hook_seconds = float(block.get("hook_seconds", 0.0))
    if not 0.0 <= hook_seconds <= 10.0:
        raise ValueError(f"captions.hook_seconds must be in [0, 10]; got {hook_seconds!r}")
    return CaptionConfig(enabled=enabled,
                         accent=_checked_accent(block.get("accent", DEFAULT_ACCENT)),
                         position=position, size=size, pop=pop,
                         hook_seconds=hook_seconds)
