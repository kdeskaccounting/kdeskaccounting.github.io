#!/usr/bin/env python3
"""Word-timed ("karaoke") burned-in captions: the top-of-frame TikTok look.

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

`caption_box()` is the single place that decides where a caption sits, exactly as
`media.overlay_box` is for a card plate. It keeps the band inside the Shorts safe zone
(middle 80% of the width, nothing below 75% of the height), above any card overlay, and
therefore nowhere near the bottom-right corner Google Earth Studio burns its attribution
watermark into.

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

#: Vertical centre of the caption band: the top of the frame, clear of the notch and clear of
#: everything the renderer draws.
BAND_CENTER_FRAC = 0.22

#: Nominal band height. Two lines of the largest type still fit inside it.
BAND_H_FRAC = 0.16

#: Height the band may never fall below; past it the type is too small to read on a phone.
MIN_BAND_H_FRAC = 0.09

#: The band may move up this far — but no further — to clear a card that sits unusually high.
BAND_TOP_MIN_FRAC = 0.05

#: Visible clearance kept between the band and a card overlay, so "not overlapping" also
#: looks like "not crowding". Same idea as media.CLEARANCE_FRAC.
CLEARANCE_FRAC = 0.02


# --- type -------------------------------------------------------------------------------

#: Font size as a fraction of the band's height, for a cue short enough not to need shrinking.
FONT_BAND_FRAC = 0.30
#: Average advance width of a bold sans glyph, in em. Used to step a long cue down so it stays
#: on one line — the same trick cards._heading_size uses on a card headline.
FONT_EM_PER_CHAR = 0.58
#: Floor: below this a caption is unreadable on a phone, so the cue wraps instead.
MIN_FONT_PX = 44.0

#: The reference's yellow. Overridable per spec.
DEFAULT_ACCENT = "#ffe234"

POSITIONS = ("top",)

_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


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


def build_cues(words, scene_offset: float = 0.0, limit: float | None = None) -> list:
    """One scene's words -> the cues that appear on the FINAL timeline.

    `scene_offset` is where the scene's audio starts in the concatenated Short; `limit` is the
    absolute time its captions must not outlive (the scene's own end), so a held phrase never
    bleeds over the cut into the next scene.
    """
    items = [w for w in (_word(raw, float(scene_offset)) for raw in (words or []))
             if w is not None]

    groups: list[list] = []
    current: list = []
    for word in items:
        nxt = current + [word]
        if current and (len(nxt) > MAX_WORDS or len(_cue_text(nxt)) > MAX_CHARS):
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
            if (len(current) == MAX_WORDS and _orphans_if_alone(word.text)
                    and len(_cue_text(nxt)) <= MAX_CHARS + GRACE_CHARS):
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

def caption_box(width: int, height: int, card_top: int | None = None):
    """The caption band as (left, top, right, bottom). The one place captions are placed.

    `card_top` is the top edge of whatever a scene draws below the captions — in practice
    `media.overlay_box(...)[1]`, the card plate on a media scene. The band shrinks from the
    BOTTOM to clear it (the band's top is the more valuable edge: it is what keeps captions
    off the platform's own chrome), and only once the band would drop below a readable height
    does it move up instead. A card that owns the whole top of the frame is refused rather
    than overlapped — a caption drawn over a card is unreadable and so is the card.
    """
    x = round(width * SAFE_X_FRAC)
    top = round(height * (BAND_CENTER_FRAC - BAND_H_FRAC / 2))
    bottom = round(height * (BAND_CENTER_FRAC + BAND_H_FRAC / 2))
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

def font_size(text: str, box) -> float:
    """Type size for one cue: as big as the band allows, stepped down so a long cue fits.

    A cue is capped at MAX_CHARS, so the worst case is bounded; the floor is what keeps a
    caption readable on a phone if that cap is ever raised (past it the cue wraps instead).
    """
    left, top, right, bottom = box
    band_h, usable = bottom - top, right - left
    chars = max(len(str(text or "")), 1)
    return max(MIN_FONT_PX, min(FONT_BAND_FRAC * band_h,
                                usable / (chars * FONT_EM_PER_CHAR)))


def _checked_accent(value: object) -> str:
    """The accent lands in a <style> block unescaped, so it is validated as a hex literal."""
    text = str(value)
    if not _HEX.match(text):
        raise ValueError(f"caption accent must be a hex colour like '#ffe234', got {text!r}")
    return text


def caption_html(cue: Cue, lit: int, accent: str, brand: dict, width: int, box) -> str:
    """One frame of one cue: every word of the phrase, with word `lit` in the accent colour.

    The page is the BAND, not the whole frame — make_short overlays it at the band's own y —
    because a full-frame RGBA PNG per spoken word is six times the memory for nothing. The
    side padding is the safe-zone margin, so the geometry still comes from `caption_box`
    alone.

    White on a thick dark stroke, `paint-order: stroke fill` so the outline sits behind the
    glyph instead of eating into it: the captions have to stay legible over bright footage as
    well as over a dark card.
    """
    colour = _checked_accent(accent)
    left, top, _right, bottom = box
    band_h = bottom - top
    fs = font_size(cue.text, box)
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
  letter-spacing:-.01em;color:#FFFFFF;
  -webkit-text-stroke:{0.085 * fs:.1f}px #0A0E14;paint-order:stroke fill;
  text-shadow:0 {0.07 * fs:.1f}px {0.11 * fs:.1f}px rgba(0,0,0,.72)}}
.lit{{color:{colour}}}
</style></head><body>
<div class="band"><div class="line">{" ".join(spans)}</div></div>
</body></html>"""


# --- the spec surface ------------------------------------------------------------------------

def settings(spec: dict, override: bool | None = None) -> CaptionConfig:
    """The spec's top-level `captions:` block, with `--captions/--no-captions` on top.

    Default OFF. Every walkthrough Short in marketing/video/ predates captions and must render
    byte-identically until its spec opts in, which is also what keeps the goldens honest.

      captions:
        enabled: true
        accent: "#ffe234"     # hex only: it is interpolated into CSS unescaped
        position: top
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
    enabled = bool(block.get("enabled", False))
    if override is not None:
        enabled = bool(override)
    return CaptionConfig(enabled=enabled,
                         accent=_checked_accent(block.get("accent", DEFAULT_ACCENT)),
                         position=position)
