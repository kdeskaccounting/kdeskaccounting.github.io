"""Park Detective long-form (16:9): what assemble.py's opt-in `landscape:` path reads (2026-11-23).

Everything here is OPT-IN. A spec without a top-level `landscape:` mapping never reaches this
module, so every Short and every walkthrough renders exactly as it did. make_short.py is not
touched: its constants are portrait and stay that way. Where make_short already owns a rule
(beat_spans' rescale arithmetic, audio_settings' bed/duck/master checks, audio_steps' mix
graph, the bed pool in beds.py) this module calls it or mirrors it rather than inventing a
second one.

THE SPEC KEYS
=============

Top level (assemble.py reads it; build_video.py preflights it before any narration):

    landscape:
      captions: {style: sentence, position: lower-third}   # or {enabled: false}; position: top
      join: cut              # cut | fade (default fade: 0.35 s dip in/out per scene)
      scene_pad: 0.35        # silence after each scene's last word (default 0.7)
      chapter_card_s: 2.5    # how long a `chapter:` card stays up (default 2.5)
      callout_s: 3.0         # default on-screen time of a callout with no `seconds:` (3.0)
      max_picture_s: 12.0    # backstop: no beat may be on screen longer, after rescale (12.0)
      bed_crossfade: 3.0     # seconds of crossfade where the bed loops (default 3.0; 0 = butt)
      bed_loop_in: 0.0       # repeats of the bed start here (skip a long intro); default 0
      chapter_sfx: {src: 'bundle:whoosh', gain_db: -16, lead: 0.2}   # default; null = silent

    Unknown `landscape:` keys are refused by name.

    audio:                   # optional; the music bed, mixed under the narration
      bed: 'pool:<id>'       # or `rotate`, or a mapping {src, lufs, target_lufs, fade_in, fade_out}
      duck: {threshold, ratio, attack, release}            # optional, make_short's defaults
      master: {lufs: -16, tp: -1.5, lra: 11}               # optional; the final loudnorm
      sfx: {events: {...}, on_tag: {...}, on_verdict: {good, bad}, min_gap}   # the Shorts block
    bed_pool: [...]          # top level, as the Shorts template has it (beds.py)

    The audio block is make_short.audio_settings() verbatim (same refusals: a bed needs its
    measured `lufs`, the gain target - lufs must be within +/-30 dB, a missing file refuses,
    duck/master/sfx without a bed refuse). The landscape path reads events, on_tag,
    on_verdict and min_gap under `audio.sfx`, drops null `on_cut`/`opening`, and refuses a
    live whoosh-on-cut, opening sting, cue or camera-move sound (longform_overlay.py).
    The bed is trimmed to its audible span (a silent lead-in or tail would be a dip at every
    seam; the pool's feeling-good starts with 2 s under -50 dBFS, its-playtime and
    ukulele-girls end with 3 s of it), looped to the episode's length with an equal-power
    crossfade at every seam (`bed_crossfade`), repeats starting at `bed_loop_in`, and then
    make_short.audio_steps() mixes it: gain = target_lufs - lufs,
    fade in/out, sidechain-ducked under the voice, alimiter, loudnorm to `audio.master`.
    No `audio:` block: the narration alone, loudnorm I -16 / TP -1.5 / LRA 11 as before.

Per `kind: media` scene (every key optional except `src`, which beats may stand in for):

    - kind: media
      src: <clip or still>   # a scene with `beats:` may omit it (beat 0's src stands in)
      in: 12.0               # clip in-point, seconds into the file (footage only)
      motion: clip | kenburns | hold          # high motions (punch/push/pan/burst) refused
      fill: crop | blur      # default: narrower than 1.3:1 -> blur, else crop
      focus: [fx, fy]        # what a crop keeps
      crop: {zoom, fx, fy}   # re-frame a still before the cover (media.crop_chain)
      beats:                 # 2+ pictures cut inside the scene, over its one narration WAV
      - {src: a.mp4, seconds: 6, in: 3.5, fill: crop, focus: [0.5, 0.4]}
      - {src: b.jpg, seconds: 5, credit: 'Photo: X / CC BY 4.0', motion: hold, crop: {...}}
      chapter: {number: 3, title: "Balloons", kicker: "NUMBER 3"}   # kicker optional
      callouts:
      - {type: sticker, src: media/photos/ai-x.png, when: {word: balloon}, anchor: {x: 0.75,
         y: 0.35}, size: 0.42, seconds: 3, label: "1971", enter_from: right, sfx: pop}

  beats    Each beat: `src`, `seconds` (> 0, <= max_picture_s), and optionally `in`, `fill`,
           `focus`, `motion`, `crop` (stills only; dropped on footage), `credit`, `credit_line`.
           A beat without `fill`/`focus` takes the scene's. The seconds are an estimate: they
           are rescaled to the scene's real narration length exactly as make_short.beat_spans
           does (last span absorbs the rounding), and a rescaled span over `max_picture_s` is
           refused. One beat is refused (one picture IS the scene); `start:` is refused with a
           hint (the landscape path spells the in-point `in:`).
  in       A clip in-point (scene `src` or beat). The clip plays from there; if it runs out
           before the picture's span ends, `clip` loops the file (as the path always did) and
           `hold` freezes its last frame. A still with `in:` is refused.
  chapter  A chapter card at the scene's start for `chapter_card_s`: a brand-ground card
           (brand.bg) with a brand-accent (brand.accent) kicker pill, "NUMBER N" (or `kicker:`)
           over the `title`, Carlito Bold, sliding in from the left and out again. Placed
           where the captions are not: upper-left over lower-third captions; lower-left when
           the captions are at the top (always the case over Earth Studio footage), and then
           never wider than 0.45 of the frame minus a margin, which keeps it clear of the Earth
           Studio attribution zone for ANY source shape (see earth_zones). Each chapter's
           start time is written to build/<slug>/chapters.json for the description's
           timestamps. `number` is optional (no number, no kicker, unless `kicker:` is given).
  callouts make_short's own `callouts:` schema, every type: sticker, badge, text, arrow, circle
           and hoot (Hoot), plus the landscape spellings `at:` (seconds), `seconds:` (hold)
           and `label:`. Timing, sizes, eases, sounds and Hoot's placement are documented in
           scripts/video/longform_overlay.py. A sticker's `size` is its LONGER side (after its
           transparent margin is trimmed) as a fraction of the frame HEIGHT, default 0.42; it
           slides in from the nearest edge. Every callout is refused over an Earth Studio zone.
  fx       The scene's verdict washes/grades (grammar.py `fx:`), on the picture under every
           graphic, with `audio.sfx.on_verdict` sounds (longform_overlay.py).

  Refused on a landscape media scene (each is a Shorts render key this path would silently
  drop): overlay, elements, scrim, blur, tail_s, crashzoom, still_of, steps. `chapter:`,
  `callouts:`, `beats:`, `in:` and `fx:` on a non-media scene are refused too (a card/title/sheet
  scene still renders through assemble's old 2400x1350 still path, fades included).

Not built for 16:9: overlay `elements:` (tags, emoji, figures, calendars), whoosh-on-cut
(off for the Shorts too), payoff cues, the opening sting, camera-move sounds, xfade joins.

Pure string/geometry work and the standard library, except the PNG drawing (`chapter_png`,
`sticker_png`), which imports PIL inside the function, and `render_bed_loop`, which runs
ffmpeg. make_short / illustrate / media are imported inside the functions that use them.
"""
from __future__ import annotations

import dataclasses
import json
import math
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
W, H, FPS = 1920, 1080, 30
FONT_BOLD = HERE / "fonts" / "Carlito-Bold.ttf"
FONT_ROUNDED = HERE / "fonts" / "Nunito-Variable.ttf"

# --- landscape: options -----------------------------------------------------------------------

LANDSCAPE_KEYS = ("captions", "join", "scene_pad", "chapter_card_s", "callout_s",
                  "max_picture_s", "bed_crossfade", "bed_loop_in", "chapter_sfx")
CAPTION_KEYS = ("enabled", "style", "position")
CAPTION_POSITIONS = ("lower-third", "top")
JOINS = ("cut", "fade")
DEFAULT_SCENE_PAD = 0.7
CHAPTER_CARD_S = 2.5
CALLOUT_S = 3.0
#: The long-form backstop on one picture. make_short's is 6 s (a Short cuts every 2-3 s); a
#: documentary-paced episode holds a shot longer, but not for a whole list item.
MAX_PICTURE_S = 12.0
BED_CROSSFADE_S = 3.0


@dataclasses.dataclass(frozen=True)
class Options:
    captions: dict
    join: str = "fade"
    scene_pad: float = DEFAULT_SCENE_PAD
    chapter_card_s: float = CHAPTER_CARD_S
    callout_s: float = CALLOUT_S
    max_picture_s: float = MAX_PICTURE_S
    bed_crossfade: float = BED_CROSSFADE_S
    bed_loop_in: float = 0.0

    @property
    def captions_on(self) -> bool:
        return bool(self.captions.get("enabled", True)) and \
            self.captions.get("style", "sentence") == "sentence"

    @property
    def caption_position(self) -> str:
        return str(self.captions.get("position", "lower-third"))


def _number(value, name, lo, hi, lo_open=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SystemExit(f"{name} must be a number, got {value!r}")
    v = float(value)
    if (v <= lo if lo_open else v < lo) or v > hi:
        raise SystemExit(f"{name}: {value!r} is outside {'(' if lo_open else '['}{lo:g}, {hi:g}]")
    return v


def options(spec: dict) -> Options | None:
    """The spec's `landscape:` block, validated with its defaults. None without one."""
    raw = (spec or {}).get("landscape")
    if not isinstance(raw, dict):
        return None
    unknown = set(raw) - set(LANDSCAPE_KEYS)
    if unknown:
        raise SystemExit(f"unknown landscape key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(LANDSCAPE_KEYS)}")
    cap = raw.get("captions") or {}
    if not isinstance(cap, dict):
        raise SystemExit(f"landscape.captions must be a mapping, got {cap!r}")
    bad = set(cap) - set(CAPTION_KEYS)
    if bad:
        raise SystemExit(f"unknown landscape.captions key(s) {', '.join(sorted(bad))}; "
                         f"known: {', '.join(CAPTION_KEYS)}")
    if cap.get("style", "sentence") != "sentence":
        raise SystemExit(f"landscape.captions.style {cap.get('style')!r}: only `sentence` is "
                         f"built (or `enabled: false` for none)")
    if cap.get("position", "lower-third") not in CAPTION_POSITIONS:
        raise SystemExit(f"landscape.captions.position {cap.get('position')!r}; known: "
                         f"{', '.join(CAPTION_POSITIONS)}")
    join = str(raw.get("join", "fade"))
    if join not in JOINS:
        raise SystemExit(f"landscape.join {join!r}; known: {', '.join(JOINS)}")
    return Options(
        captions=dict(cap), join=join,
        scene_pad=_number(raw.get("scene_pad", DEFAULT_SCENE_PAD), "landscape.scene_pad",
                          0.0, 3.0, lo_open=True),
        chapter_card_s=_number(raw.get("chapter_card_s", CHAPTER_CARD_S),
                               "landscape.chapter_card_s", 0.5, 10.0),
        callout_s=_number(raw.get("callout_s", CALLOUT_S), "landscape.callout_s", 0.3, 60.0),
        max_picture_s=_number(raw.get("max_picture_s", MAX_PICTURE_S),
                              "landscape.max_picture_s", 3.0, 120.0),
        bed_crossfade=_number(raw.get("bed_crossfade", BED_CROSSFADE_S),
                              "landscape.bed_crossfade", 0.0, 10.0),
        bed_loop_in=_number(raw.get("bed_loop_in", 0.0), "landscape.bed_loop_in", 0.0, 600.0))


# --- scenes -----------------------------------------------------------------------------------

#: Shorts render keys the landscape path does not draw. Refused rather than ignored: a key
#: that parses and does nothing reads, in the spec, as applied.
REFUSED_SCENE_KEYS = ("overlay", "elements", "scrim", "blur", "tail_s", "crashzoom",
                      "still_of", "steps")
#: Keys only a `kind: media` scene may carry on a landscape spec.
MEDIA_ONLY_KEYS = ("chapter", "callouts", "beats", "in", "fx")


def normalise_spec(spec: dict) -> dict:
    """Give a beats scene with no `src` its first beat's (and that beat's credit), IN PLACE.

    media.validate_spec asks every media scene for a `src` (and a still for a `credit`), but
    under `beats:` the scene's own src is never rendered. Returns the spec.
    """
    for scene in (spec or {}).get("scenes") or []:
        if not isinstance(scene, dict) or scene.get("kind") != "media" or scene.get("src"):
            continue
        beats = scene.get("beats")
        if isinstance(beats, list) and beats and isinstance(beats[0], dict) and beats[0].get("src"):
            scene["src"] = beats[0]["src"]
            if not scene.get("credit") and beats[0].get("credit"):
                scene["credit"] = beats[0]["credit"]
    return spec


def check_scene_keys(scene: dict, where: str) -> None:
    """Refuse a Shorts-only render key on a landscape media scene, and media-only keys on any
    other kind."""
    scene = scene or {}
    if scene.get("kind") == "media":
        bad = [key for key in REFUSED_SCENE_KEYS if key in scene]
        if bad:
            raise SystemExit(f"{where}: {', '.join(bad)} is not drawn on a landscape (16:9) "
                             f"scene; it would be silently dropped. Take it off (see "
                             f"scripts/video/longform.py for what the 16:9 path reads).")
        return
    bad = [key for key in MEDIA_ONLY_KEYS if key in scene]
    if bad:
        raise SystemExit(f"{where} (kind: {scene.get('kind', 'sheet')}): {', '.join(bad)} is "
                         f"only drawn on a `kind: media` scene in the 16:9 path")


def in_point(value, where: str) -> float:
    """A clip in-point: seconds into the file, >= 0. 0.0 when absent."""
    if value is None:
        return 0.0
    return _number(value, f"{where} `in`", 0.0, 86400.0)


# --- beats ------------------------------------------------------------------------------------

BEAT_KEYS = ("src", "seconds", "in", "fill", "focus", "motion", "crop", "credit", "credit_line")


def scene_beats(scene: dict, where: str = "scene", max_s: float = MAX_PICTURE_S) -> list:
    """A landscape scene's `beats:`, validated and normalised. `[]` when it has none.

    Each comes back as {src, seconds, in, fill, focus, motion, crop, credit}; `fill` and
    `focus` fall back to the scene's. `motion` stays "" when unset (its default depends on the
    file's kind, resolved where the path is). Raises SystemExit naming the beat.
    """
    import media
    raw = (scene or {}).get("beats")
    if not raw:
        return []
    if not isinstance(raw, list):
        raise SystemExit(f"{where}: `beats:` must be a list, got {type(raw).__name__}")
    if len(raw) < 2:
        raise SystemExit(f"{where}: `beats:` has one entry; one picture IS the scene. Drop the "
                         f"key, or give it two.")
    try:
        scene_fill, scene_focus = media.scene_fill(scene)
    except ValueError as exc:
        raise SystemExit(f"{where}: {exc}") from None
    out = []
    for index, beat in enumerate(raw):
        tag = f"{where} beats[{index}]"
        if not isinstance(beat, dict):
            raise SystemExit(f"{tag} is {type(beat).__name__}, expected a mapping")
        if "start" in beat:
            raise SystemExit(f"{tag}: the 16:9 path spells the clip in-point `in:`, not `start:`")
        unknown = set(beat) - set(BEAT_KEYS)
        if unknown:
            raise SystemExit(f"{tag}: unknown key(s) {', '.join(sorted(unknown))}; known: "
                             f"{', '.join(BEAT_KEYS)}")
        src = str(beat.get("src") or "").strip()
        if not src:
            raise SystemExit(f"{tag} has no `src`; a beat is a picture")
        seconds = _number(beat.get("seconds"), f"{tag} `seconds`", 0.0, float(max_s),
                          lo_open=True)
        try:
            fill, focus = media.scene_fill(beat)
        except ValueError as exc:
            raise SystemExit(f"{tag}: {exc}") from None
        crop = beat.get("crop") or {}
        try:
            media.crop_chain(1, 1, crop)
        except ValueError as exc:
            raise SystemExit(f"{tag}: {exc}") from None
        motion = str(beat.get("motion") or "").strip()
        if motion and motion not in media.MOTIONS:
            raise SystemExit(f"{tag}: unknown motion {motion!r}; known: {', '.join(media.MOTIONS)}")
        if motion in media.HIGH_MOTIONS:
            raise SystemExit(f"{tag}: motion {motion!r} is portrait-only; use clip, kenburns or "
                             f"hold on a 16:9 spec")
        out.append({"src": src, "seconds": seconds, "in": in_point(beat.get("in"), tag),
                    "fill": fill if fill is not None else scene_fill,
                    "focus": focus if "focus" in beat else scene_focus,
                    "motion": motion, "crop": dict(crop),
                    "credit": str(beat.get("credit") or "").strip()})
    return out


def beat_spans(beats, dur: float, max_s: float = MAX_PICTURE_S) -> list:
    """The beats' seconds rescaled to the scene's REAL duration, summing exactly to it.

    make_short.beat_spans' arithmetic, unchanged (the last span absorbs the rounding), with the
    long-form backstop `max_s` in place of the Shorts' 6 s.
    """
    nominal = [float(beat["seconds"]) for beat in beats]
    if not nominal:
        return []
    total = sum(nominal) or 1.0
    spans = [round(float(dur) * value / total, 3) for value in nominal]
    spans[-1] = round(float(dur) - sum(spans[:-1]), 3)
    for index, span in enumerate(spans):
        if span > max_s:
            raise SystemExit(
                f"beats[{index}] asks for {nominal[index]:.2f}s of a {sum(nominal):.2f}s "
                f"estimate, which over this scene's real {float(dur):.2f}s is {span:.2f}s on "
                f"screen, past landscape.max_picture_s ({max_s:g}s). Add beats, or lengthen "
                f"the short ones.")
    return spans


def cut_times(spans) -> list:
    """Scene-local seconds where the picture cuts (the beat boundaries)."""
    out, t = [], 0.0
    for span in list(spans)[:-1]:
        t += float(span)
        out.append(round(t, 3))
    return out


# --- Earth Studio ---------------------------------------------------------------------------

def fit_rect(src_w: int | None, src_h: int | None, w: int = W, h: int = H) -> tuple:
    """(x0, y0, dw, dh) of a source shown WHOLE (fit, centred) in a w x h frame."""
    if not src_w or not src_h:
        return 0.0, 0.0, float(w), float(h)
    s = min(w / src_w, h / src_h)
    dw, dh = src_w * s, src_h * s
    return (w - dw) / 2.0, (h - dh) / 2.0, dw, dh


def earth_zones(size, w: int = W, h: int = H) -> list:
    """Every rectangle an Earth Studio attribution can occupy on the 16:9 canvas.

    The landscape path shows Earth footage whole (fit, on the brand ground), so its mark sits
    inside the DISPLAYED picture: media.WATERMARK_* of that rectangle. The full-frame zone is
    added too, so an unprobed source, or one re-exported at another aspect, stays covered.
    For any fitted source the displayed zone starts at x >= 0.45 w (x0 + 0.45 dw, where
    x0 = (w - dw) / 2), which is why a box kept left of 0.45 w is clear of every one of them.
    """
    import media
    full = media.watermark_box(w, h)
    x0, y0, dw, dh = fit_rect(*(size or (None, None)), w, h)
    shown = (round(x0 + dw * (1 - media.WATERMARK_W_FRAC)),
             round(y0 + dh * (1 - media.WATERMARK_H_FRAC)), round(x0 + dw), round(y0 + dh))
    return [full] if shown == full else [full, shown]


def overlaps_any(box, zones) -> bool:
    import media
    return any(media.boxes_overlap(box, zone) for zone in zones)


def windows_overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return a0 < b1 and b0 < a1


# --- chapter cards ------------------------------------------------------------------------------

CHAPTER_KEYS = ("number", "title", "kicker")
CHAPTER_MARGIN_X = 0.05        # of W
CHAPTER_MARGIN_Y = 0.08        # of H, inside title-safe
CHAPTER_CLEARANCE = 0.012      # of W, kept between a lower-left card and the Earth zone
CHAPTER_MAX_W = 0.60           # of W, upper-left card
CHAPTER_TITLE_PX = 76
CHAPTER_TITLE_MIN_PX = 52
CHAPTER_KICKER_PX = 32
CHAPTER_PAD = 30
#: The soft drop shadow's margin around the panel, inside the PNG (and so inside `max_w`).
CHAPTER_SHADOW = 14
CHAPTER_IN_S, CHAPTER_OUT_S = 0.35, 0.30


def chapter_of(scene: dict, where: str = "scene") -> dict | None:
    """The scene's `chapter:` as {number, title, kicker}, or None."""
    raw = (scene or {}).get("chapter")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SystemExit(f"{where}: `chapter:` must be a mapping {{number, title}}, got {raw!r}")
    unknown = set(raw) - set(CHAPTER_KEYS)
    if unknown:
        raise SystemExit(f"{where}: unknown chapter key(s) {', '.join(sorted(unknown))}; known: "
                         f"{', '.join(CHAPTER_KEYS)}")
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SystemExit(f"{where}: `chapter:` needs a `title`")
    number = raw.get("number")
    if number is not None and (isinstance(number, bool) or not isinstance(number, int)
                               or number < 0):
        raise SystemExit(f"{where}: chapter `number` must be a whole number, got {number!r}")
    kicker = raw.get("kicker")
    if kicker is not None and not isinstance(kicker, str):
        raise SystemExit(f"{where}: chapter `kicker` must be a string, got {kicker!r}")
    if kicker is None:
        kicker = f"NUMBER {number}" if number is not None else ""
    return {"number": number, "title": title.strip(), "kicker": kicker.strip()}


def chapter_placement(earth_under: bool, captions_top: bool, w: int = W, h: int = H) -> dict:
    """Where a chapter card goes: {corner, x, y_top | y_bottom, max_w}.

    Upper-left unless the captions are at the top (they always are over Earth footage); then
    lower-left, never wider than the Earth zone's leftmost possible edge (0.45 w) minus a
    clearance, so it cannot touch the attribution whatever the source's shape.
    """
    import media
    x = round(w * CHAPTER_MARGIN_X)
    if earth_under or captions_top:
        right = round(w * (1 - media.WATERMARK_W_FRAC)) - round(w * CHAPTER_CLEARANCE)
        return {"corner": "bottom-left", "x": x, "y_bottom": h - round(h * CHAPTER_MARGIN_Y),
                "max_w": right - x}
    return {"corner": "top-left", "x": x, "y_top": round(h * CHAPTER_MARGIN_Y),
            "max_w": round(w * CHAPTER_MAX_W)}


def _hex_rgb(value: str, fallback: str) -> tuple:
    s = str(value or fallback).lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return _hex_rgb(fallback, "#000000")


def _wrap_two(draw, text: str, font, max_w: int) -> list | None:
    """One line, or the most balanced two-line split that fits `max_w`; None if neither fits."""
    if draw.textlength(text, font=font) <= max_w:
        return [text]
    words = text.split()
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        wa, wb = draw.textlength(a, font=font), draw.textlength(b, font=font)
        if max(wa, wb) <= max_w and (best is None or max(wa, wb) < best[0]):
            best = (max(wa, wb), [a, b])
    return best[1] if best else None


def chapter_png(chapter: dict, brand: dict | None, out: pathlib.Path, max_w: int) -> tuple:
    """Draw the chapter card as a tight transparent PNG. Returns (path, width, height).

    A rounded brand-ground (brand.bg) panel with a brand-accent bar down its left edge, the
    kicker ("NUMBER 3") in a brand-accent pill, and the title under it in white Carlito Bold,
    wrapped to two lines and shrunk (to CHAPTER_TITLE_MIN_PX) before it may exceed `max_w`.
    `max_w` bounds the whole PNG, shadow margin included, so the box the caller places is the
    box every drawn pixel stays inside.
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    brand = brand or {}
    bg = _hex_rgb(brand.get("bg"), "#343A46")
    accent = _hex_rgb(brand.get("accent"), "#1F6F3D")
    fg = _hex_rgb(brand.get("fg"), "#FFFFFF")
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bar, pad, shadow = 12, CHAPTER_PAD, CHAPTER_SHADOW
    inner = max_w - 2 * shadow - bar - 2 * pad
    px, lines = CHAPTER_TITLE_PX, None
    while px >= CHAPTER_TITLE_MIN_PX:
        font = ImageFont.truetype(str(FONT_BOLD), px)
        lines = _wrap_two(probe, chapter["title"], font, inner)
        if lines:
            break
        px -= 4
    if not lines:
        raise SystemExit(f"chapter title {chapter['title']!r} does not fit two lines of "
                         f"{inner}px at {CHAPTER_TITLE_MIN_PX}px; shorten it")
    kfont = ImageFont.truetype(str(FONT_BOLD), CHAPTER_KICKER_PX)
    kick = chapter.get("kicker") or ""
    kw = probe.textlength(kick, font=kfont) if kick else 0
    pill_h = round(CHAPTER_KICKER_PX * 1.45) if kick else 0
    line_h = round(px * 1.12)
    title_w = max(probe.textlength(ln, font=font) for ln in lines)
    body_w = max(title_w, kw + 28 if kick else 0)
    cw = int(bar + 2 * pad + body_w)
    ch = int(pad + (pill_h + 14 if kick else 0) + line_h * len(lines) + pad * 0.8)
    img = Image.new("RGBA", (cw + 2 * shadow, ch + 2 * shadow), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((shadow, shadow + 5, shadow + cw, shadow + ch + 5),
                                         radius=16, fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(img)
    x0, y0 = shadow, shadow
    d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=16, fill=(*bg, 238))
    d.rounded_rectangle((x0, y0, x0 + bar + 6, y0 + ch), radius=16, fill=(*accent, 255))
    d.rectangle((x0 + bar, y0, x0 + bar + 6, y0 + ch), fill=(*bg, 238))
    tx, ty = x0 + bar + pad, y0 + pad
    if kick:
        d.rounded_rectangle((tx, ty, tx + kw + 28, ty + pill_h), radius=pill_h // 2,
                            fill=(*accent, 255))
        d.text((tx + 14, ty + (pill_h - CHAPTER_KICKER_PX) // 2 - 2), kick, font=kfont,
               fill=(*fg, 255))
        ty += pill_h + 14
    for k, ln in enumerate(lines):
        d.text((tx, ty + k * line_h), ln, font=font, fill=(*fg, 255),
               stroke_width=1, stroke_fill=(0, 0, 0, 160))
    img.save(out)
    return out, img.size[0], img.size[1]


def chapter_origin(place: dict, png_w: int, png_h: int) -> tuple:
    """Top-left (x, y) of the card PNG on the frame, from chapter_placement()."""
    y = place["y_top"] if place["corner"] == "top-left" else place["y_bottom"] - png_h
    return int(place["x"]), int(y)


def ease_out(t0: float, d: float) -> str:
    """ffmpeg expression: ease-out cubic 0 -> 1 over [t0, t0 + d] of the overlay's `t`."""
    return f"(1-pow(1-min(1,max(0,(t-{t0:.3f})/{d:.3f})),3))"


def ease_in(t0: float, d: float) -> str:
    """ffmpeg expression: ease-in cubic 0 -> 1 over [t0, t0 + d]."""
    return f"pow(min(1,max(0,(t-{t0:.3f})/{d:.3f})),3)"


def chapter_overlay(x: int, y: int, w: int, t0: float, t1: float) -> str:
    """The overlay filter (no labels) that slides a card in from the left and back out."""
    d_in = min(CHAPTER_IN_S, (t1 - t0) / 3)
    d_out = min(CHAPTER_OUT_S, (t1 - t0) / 3)
    off = f"({x}+{w})"
    xexpr = (f"({x})-{off}*(1-{ease_out(t0, d_in)})-{off}*{ease_in(t1 - d_out, d_out)}")
    return (f"overlay=x='{xexpr}':y={y}:format=auto:"
            f"enable='between(t,{t0:.3f},{t1:.3f})'")


# --- callouts -----------------------------------------------------------------------------

STICKER_SIZE = 0.42
SLIDE_S = 0.30
EDGES = ("bottom", "left", "right", "top")
LABEL_KEYS = ("text", "x", "y", "size", "color", "ink", "rotate")
LABEL_DEFAULT = {"x": 0.5, "y": 0.80, "size": 0.14}
LABEL_SIZE = 0.12


def _label(raw, tag) -> dict:
    if isinstance(raw, str):
        raw = {"text": raw, **LABEL_DEFAULT}
    if not isinstance(raw, dict):
        raise SystemExit(f"{tag}: a label is a string or a mapping {{text, x, y, ...}}")
    unknown = set(raw) - set(LABEL_KEYS)
    if unknown:
        raise SystemExit(f"{tag}: unknown label key(s) {', '.join(sorted(unknown))}; known: "
                         f"{', '.join(LABEL_KEYS)}")
    if not isinstance(raw.get("text"), str) or not raw["text"].strip():
        raise SystemExit(f"{tag}: a label needs `text`")
    lab = {"text": raw["text"], "x": _number(raw.get("x", 0.5), f"{tag} x", -0.5, 1.5),
           "y": _number(raw.get("y", 0.5), f"{tag} y", -0.5, 1.5),
           "size": _number(raw.get("size", LABEL_SIZE), f"{tag} size", 0.01, 1.0),
           "rotate": _number(raw.get("rotate", 0.0), f"{tag} rotate", -90.0, 90.0)}
    for key, default in (("color", "#FFFFFF"), ("ink", "#111111")):
        value = raw.get(key, default)
        if not (isinstance(value, str) and value.startswith("#") and len(value) in (4, 7)):
            raise SystemExit(f"{tag}: `{key}` must be a #rgb or #rrggbb hex colour")
        lab[key] = value
    return lab


def check_callouts(scene: dict, where: str = "scene", spec: dict | None = None,
                   spec_path=None) -> list:
    """A landscape scene's `callouts:`, in make_short's own schema (callouts.check), with the
    landscape spellings `at`, `seconds`, `label` folded in (longform_overlay.check)."""
    import longform_overlay
    return longform_overlay.check((scene or {}).get("callouts"), where, spec, spec_path)


def _sticker_image(src, size: float, h: int = H):
    """(the PNG cropped to its visible pixels, (w, h) it is drawn at on the frame)."""
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box is None:
        raise SystemExit(f"sticker {src} is fully transparent")
    im = im.crop(box)
    scale = max(1, round(float(size) * h)) / max(im.size)
    return im, (max(1, round(im.size[0] * scale)), max(1, round(im.size[1] * scale)))


def sticker_dims(src, size: float, h: int = H) -> tuple:
    """The (w, h) a sticker is drawn at, without drawing it (for the preflight)."""
    return _sticker_image(src, size, h)[1]


def sticker_png(c: dict, out: pathlib.Path, h: int = H) -> tuple:
    """The sticker trimmed to its visible pixels, fitted so its LONGER side is `size` x frame
    height, with its labels drawn on (heavy rounded Nunito, white over a dark outline, as the
    Shorts draw them). Returns (path, width, height)."""
    from PIL import Image, ImageDraw, ImageFont
    im, (w_, h_) = _sticker_image(c["src"], c["size"], h)
    im = im.resize((w_, h_), Image.LANCZOS)
    for lab in c.get("labels") or ():
        fs = max(8, round(float(lab["size"]) * w_ / 0.705))
        font = ImageFont.truetype(str(FONT_ROUNDED), fs)
        try:
            font.set_variation_by_axes([900])
        except (OSError, AttributeError):
            font = ImageFont.truetype(str(FONT_BOLD), fs)
        stroke = max(1, round(0.08 * fs))
        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        l, t, r, b = probe.textbbox((0, 0), lab["text"], font=font, stroke_width=stroke)
        layer = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((4 - l, 4 - t), lab["text"], font=font,
                                   fill=(*_hex_rgb(lab["color"], "#FFFFFF"), 255),
                                   stroke_width=stroke,
                                   stroke_fill=(*_hex_rgb(lab["ink"], "#111111"), 255))
        if lab.get("rotate"):
            layer = layer.rotate(-float(lab["rotate"]), expand=True, resample=Image.BICUBIC)
        cx, cy = float(lab["x"]) * w_, float(lab["y"]) * h_
        im.alpha_composite(layer, (round(cx - layer.size[0] / 2), round(cy - layer.size[1] / 2)))
    im.save(out)
    return out, w_, h_


def sticker_box(anchor, w_: int, h_: int, w: int = W, h: int = H) -> tuple:
    """(left, top, right, bottom) of a sticker centred on `anchor` (frame fractions)."""
    cx, cy = anchor[0] * w, anchor[1] * h
    left, top = round(cx - w_ / 2), round(cy - h_ / 2)
    return left, top, left + w_, top + h_


def sticker_overlay(box, edge: str, t0: float, t1: float, w: int = W, h: int = H) -> str:
    """The overlay filter (no labels): slide in from `edge` over SLIDE_S, snap off at t1."""
    left, top, right, bottom = box
    e = ease_out(t0, min(SLIDE_S, max(0.05, (t1 - t0) / 3)))
    x, y = f"({left})", f"({top})"
    if edge == "bottom":
        y = f"({top})+({h}-({top}))*(1-{e})"
    elif edge == "top":
        y = f"({top})-({bottom})*(1-{e})"
    elif edge == "left":
        x = f"({left})-({right})*(1-{e})"
    else:
        x = f"({left})+({w}-({left}))*(1-{e})"
    return f"overlay=x='{x}':y='{y}':format=auto:enable='between(t,{t0:.3f},{t1:.3f})'"


# --- sound ------------------------------------------------------------------------------------

def audio_mix(spec: dict, spec_path):
    """make_short.audio_settings() for a landscape spec, or None with no `audio:` block.

    `audio.sfx` is the Shorts block: events, on_tag, on_verdict and min_gap are read; a null
    `on_cut` / `opening` (as the v6 template writes them) is dropped; a non-null whoosh-on-cut,
    opening sting, cue, camera-move sound or legacy whoosh key is refused by name
    (longform_overlay.REFUSED_SFX), because accepting it would read as applied.
    """
    import longform_overlay
    import make_short
    if (spec or {}).get("audio") is None:
        return None
    longform_overlay.check_sfx_block(spec)
    return make_short.audio_settings(longform_overlay.strip_nulls(spec), spec_path)


def bed_copies(first_s: float, runtime: float, xfade: float, loop_s: float | None = None) -> int:
    """How many copies cover `runtime`: the first `first_s` long, each repeat `loop_s` long
    (default the same) and overlapping the one before it by `xfade`."""
    first_s, runtime, xfade = float(first_s), float(runtime), float(xfade)
    loop_s = first_s if loop_s is None else float(loop_s)
    for length in (first_s, loop_s):
        if length <= 2 * xfade or length <= 0:
            raise SystemExit(f"the bed is {length:.1f}s long, too short to loop with a "
                             f"{xfade:g}s crossfade; lower landscape.bed_crossfade (or "
                             f"landscape.bed_loop_in)")
    if runtime <= first_s:
        return 1
    return 1 + math.ceil((runtime - first_s) / (loop_s - xfade))


def bed_loop_steps(copies: int, runtime: float, xfade: float, span=None,
                   loop_in: float = 0.0) -> list:
    """The graph that joins `copies` inputs (the same file, 0..copies-1) into one `runtime`-long
    bed `[bed]`: equal-power (qsin) acrossfades at each seam, or a plain concat at xfade 0.

    `span` (start, end) is the bed's audible part (audible_span): every copy is trimmed to it,
    so a silent lead-in or tail never becomes a dip at a seam. Repeats (copies 1..) start at
    `loop_in` instead when that is later, which skips a long intro on every repeat."""
    fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
    steps = []
    for k in range(copies):
        trim = ""
        if span is not None:
            a = float(span[0]) if k == 0 else max(float(span[0]), float(loop_in))
            trim = f"atrim={a:.3f}:{float(span[1]):.3f},asetpts=PTS-STARTPTS,"
        elif k and loop_in:
            trim = f"atrim=start={float(loop_in):.3f},asetpts=PTS-STARTPTS,"
        steps.append(f"[{k}:a]{trim}{fmt}[a{k}]")
    if copies == 1:
        last = "a0"
    elif xfade > 0:
        last = "a0"
        for k in range(1, copies):
            steps.append(f"[{last}][a{k}]acrossfade=d={xfade:g}:c1=qsin:c2=qsin[x{k}]")
            last = f"x{k}"
    else:
        steps.append("".join(f"[a{k}]" for k in range(copies)) + f"concat=n={copies}:v=0:a=1[xc]")
        last = "xc"
    steps.append(f"[{last}]atrim=0:{float(runtime):.3f},asetpts=PTS-STARTPTS[bed]")
    return steps


#: Below this a bed's lead-in or tail counts as silence (audible_span). The pool beds measure
#: -24 to -30 dBFS per second in their bodies and -44 to -92 in their silent ends.
BED_SILENCE_DB = -50.0
BED_SILENCE_WINDOW_S = 0.02


def audible_span(pcm, rate: int, threshold_db: float = BED_SILENCE_DB,
                 window_s: float = BED_SILENCE_WINDOW_S) -> tuple:
    """(start, end) seconds of the audible part of mono samples `pcm` (ints, full scale 32768):
    from the first to the last `window_s` window whose RMS is above `threshold_db`. The whole
    clip when nothing is above it."""
    win = max(1, int(rate * window_s))
    floor = (32768.0 * 10 ** (threshold_db / 20.0)) ** 2 * win
    loud = [k for k in range(0, len(pcm), win)
            if sum(v * v for v in pcm[k:k + win]) > floor]
    if not loud:
        return 0.0, len(pcm) / float(rate)
    return loud[0] / float(rate), min(len(pcm), loud[-1] + win) / float(rate)


def bed_span(src, rate: int = 8000) -> tuple:
    """audible_span() of a bed file, decoded to mono 16-bit at `rate` by ffmpeg."""
    import array
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-f", "s16le", "-ac", "1",
                          "-ar", str(rate), "-"], capture_output=True).stdout
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) // 2 * 2])
    return audible_span(pcm, rate)


def render_bed_loop(src, runtime: float, xfade: float, out: pathlib.Path,
                    loop_in: float = 0.0) -> pathlib.Path:
    """The bed, trimmed to its audible span, looped and crossfaded to exactly `runtime` seconds,
    as a 48 kHz stereo WAV."""
    a, b = bed_span(src)
    if loop_in and loop_in >= b - 2 * xfade:
        raise SystemExit(f"landscape.bed_loop_in {loop_in:g}s leaves no bed to loop (its audible "
                         f"part ends at {b:.1f}s)")
    copies = bed_copies(b - a, runtime, xfade, b - max(a, loop_in))
    args = []
    for _ in range(copies):
        args += ["-i", str(src)]
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex",
                        ";".join(bed_loop_steps(copies, runtime, xfade, (a, b), loop_in)),
                        "-map", "[bed]", "-c:a", "pcm_s16le", "-ar", "48000", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"bed loop failed:\n{r.stderr[-1500:]}")
    return out


# --- preflight (build_video, before any narration) ----------------------------------------------

def probe_size(path):
    """(width, height) of a media file's first video stream, or None."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
                         capture_output=True, text=True).stdout
    for line in (out or "").splitlines():
        parts = line.strip().split("x")
        if len(parts) == 2 and all(q.isdigit() and int(q) for q in parts):
            return int(parts[0]), int(parts[1])
    return None


def scene_pictures(scene: dict, spec_path, max_s: float = MAX_PICTURE_S,
                   where: str = "scene") -> list:
    """Every picture a landscape media scene shows, resolved: [{src, kind, motion, in, fill,
    focus, crop, earth, beat}] (one entry, beat None, for a scene without beats).

    Refuses (SystemExit, naming the scene and beat): a high motion, a motion that cannot work on
    that kind of file (media.check_motion), `in:` on a still, `in:` on the scene of a beats
    scene (it belongs on the beat).
    """
    import media
    beats = scene_beats(scene, where, max_s)
    if beats:
        if scene.get("in") is not None:
            raise SystemExit(f"{where}: `in:` on a scene with `beats:` points into a file that is "
                             f"never shown; put it on the beat")
        entries = [(beat, f"{where} beats[{k}]") for k, beat in enumerate(beats)]
    else:
        try:
            fill, focus = media.scene_fill(scene)
        except ValueError as exc:
            raise SystemExit(f"{where}: {exc}") from None
        entries = [({"src": scene.get("src"), "in": in_point(scene.get("in"), where),
                     "fill": fill, "focus": focus, "motion": str(scene.get("motion") or ""),
                     "crop": dict(scene.get("crop") or {}), "credit": scene.get("credit")},
                    where)]
    out = []
    for beat, tag in entries:
        try:
            src = media.resolve_src(spec_path, beat["src"])
            kind = media.media_kind(src)
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(f"{tag}: {exc}") from None
        motion = beat["motion"] or media.default_motion(kind)
        if motion in media.HIGH_MOTIONS:
            raise SystemExit(f"{tag}: motion {motion!r} is portrait-only (ZOOMPAN_W x ZOOMPAN_H); "
                             f"use clip, kenburns or hold on a landscape spec")
        try:
            media.check_motion(kind, motion)
        except ValueError as exc:
            raise SystemExit(f"{tag}: {exc}") from None
        if beat["in"] and kind != "video":
            raise SystemExit(f"{tag}: `in: {beat['in']:g}` is an in-point into footage, and a "
                             f"still has none")
        credit = beat.get("credit") or scene.get("credit")
        out.append({"src": src, "kind": kind, "motion": motion, "in": beat["in"],
                    "fill": beat["fill"], "focus": beat["focus"],
                    "crop": beat["crop"] if kind == "image" else {},
                    "earth": media.is_earth_studio({"src": beat["src"], "credit": credit}),
                    "beat": beat if beats else None})
    return out


def preflight(spec: dict, spec_path) -> Options | None:
    """Everything the 16:9 path can refuse, checked before a frame or a word is rendered.

    None (and nothing checked) without a `landscape:` block. Run AFTER normalise_spec() and
    media.validate_spec(), which build_video does in that order.
    """
    import grammar
    import longform_overlay
    opts = options(spec)
    if opts is None:
        return None
    for index, scene in enumerate((spec or {}).get("scenes") or []):
        where = f"scene {index}"
        check_scene_keys(scene or {}, where)
        if (scene or {}).get("kind") != "media":
            continue
        pictures = scene_pictures(scene, spec_path, opts.max_picture_s, where)
        chapter_of(scene, where)
        try:
            grammar.parse_fx_list(scene, where)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        calls = longform_overlay.check(scene.get("callouts"), where, spec, spec_path)
        earth = [p for p in pictures if p["earth"]]
        if calls and earth:
            zones = [z for p in earth for z in earth_zones(probe_size(p["src"]))]
            for k, c in enumerate(calls):
                if c["type"] != "sticker" or c.get("anchor") is None:
                    continue                    # the rest are checked where they are drawn
                try:
                    dims = sticker_dims(c["src"], c.get("size", STICKER_SIZE))
                except ImportError:
                    break                       # no PIL here; assemble checks it at render
                anchor = (c["anchor"].get("x"), c["anchor"].get("y"))
                if overlaps_any(sticker_box(anchor, *dims), zones):
                    raise SystemExit(
                        f"{where} callouts[{k}]: the sticker at {anchor} would cover the "
                        f"Earth Studio attribution zone of this scene's Earth footage. Move its "
                        f"anchor up or left, or make it smaller.")
    audio_mix(spec, spec_path)
    longform_overlay.chapter_sound((spec or {}).get("landscape"),
                                   lambda src: longform_overlay.resolve_sound(src, spec_path))
    return opts


def poster(out_png, scene: dict, spec_path, w: int = W, h: int = H) -> dict:
    """The scene still build_video writes for a landscape media scene: the first picture's frame
    at its in-point, fitted onto a w x h black frame by ffmpeg (no browser). Same focus shape as
    render_sheets.render_media_scene's."""
    import media
    beats = (scene or {}).get("beats") or []
    pick = beats[0] if beats and isinstance(beats[0], dict) and beats[0].get("src") else scene
    src = media.resolve_src(spec_path, pick["src"])
    at = float(pick.get("in") or 0.0)
    seek = ["-ss", f"{at:.3f}"] if at and media.media_kind(src) == "video" else []
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *seek, "-i", str(src),
                        "-frames:v", "1", "-vf",
                        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black", str(out_png)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"poster for {src} failed:\n{r.stderr[-800:]}")
    return {"fx": 0.5, "fy": 0.5, "static": True}


# --- chapters.json ----------------------------------------------------------------------------

def timestamp(seconds: float) -> str:
    s = int(math.floor(float(seconds)))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def write_chapters(path: pathlib.Path, marks: list) -> pathlib.Path:
    """[{scene, start, number, title, kicker, timestamp}] -> chapters.json (for the description;
    YouTube wants the first chapter at 0:00, three or more, each 10 s or longer)."""
    rows = [{**m, "start": round(float(m["start"]), 3), "timestamp": timestamp(m["start"])}
            for m in marks]
    path.write_text(json.dumps(rows, indent=1) + "\n")
    return path
