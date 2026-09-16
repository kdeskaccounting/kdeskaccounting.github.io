#!/usr/bin/env python3
"""The `media` scene kind: real footage or a still frame, under an optional card overlay.

A `card` scene is text on a brand background. A `media` scene is the same text over imagery —
a fly-in from Google Earth Studio, a stock still, a screen capture — which is what makes a
data Short look like a video instead of a slide deck.

  - kind: media
    src: media/earth/magic-kingdom.mp4   # repo-relative to the SPEC's repo root, or absolute
    motion: clip | kenburns | hold       # default: kenburns for a still, clip for footage
    credit: "Imagery: Google Earth, Maxar Technologies"     # REQUIRED for a still
    overlay:                             # optional; the `card` data contract, unchanged
      template: ranked_list | countdown | changed
      data: {heading, subheading, items, footer}
    narration: "..."

Three rules are worth stating out loud, because each one is a licence or a legibility
question rather than a style preference.

**The bottom-right corner is not ours.** Google Earth Studio burns its attribution watermark
("Google · Maxar Technologies") into the bottom-right of every frame it exports, and the terms
require it to stay visible. `WATERMARK_*` fences off that rectangle: the credit plate is
anchored bottom-LEFT and stops short of it horizontally, and the overlay's bottom edge stops
short of it vertically. `boxes_overlap()` plus the tests in tests/test_media.py are what keep
a later layout tweak from sliding a plate over it.

**A still must be credited.** Footage may carry its own on-screen attribution; a still frame
never does, so `check_credit()` refuses an image scene with no `credit:`.

**The overlay is the card renderer, not a copy of it.** `overlay_html()` calls
`cards.card_html()` with a box and a transparent background, so the templates, the row caps,
the escaping and the brand tokens are all the ones `kind: card` already uses. The card sizes
its type to its own canvas, which here is the plate rather than the whole frame — an overlay
row lands between a Short's caption and its URL in size.

Pure string and geometry work, stdlib only (the filesystem is touched only by `resolve_src`),
so this imports and tests in the bare `uv run --with pytest` environment.
"""
from __future__ import annotations

import html as _html
import math
import pathlib

import cards

MOTIONS = ("clip", "kenburns", "hold")

#: Which motions actually work on which kind of source. `clip` needs frames to play and
#: `kenburns` needs a single frame to zoom; the wrong pairing hangs ffmpeg or silently
#: freezes the footage. See check_motion() for the mechanics of each failure.
MOTIONS_FOR = {"image": ("kenburns", "hold"), "video": ("clip", "hold")}

VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")

#: Files that mark the top of a repository, in the order they are looked for. A spec handed
#: to us from another repo resolves its `src:` against whichever of these sits above it.
ROOT_MARKERS = (".git", "pyproject.toml")

FPS = 30

#: Ken Burns end zoom. 8% over the scene reads as motion without ever looking like a shove.
KENBURNS_ZOOM = 1.08

# --- the geometry ---------------------------------------------------------------------
#
# Every fraction below is of the frame, so the same numbers hold for the 1296x2304 composite,
# the 1080x1920 delivered Short and build_video's 2400x1350 still.

#: Earth Studio's attribution watermark. NOTHING may be drawn inside this rectangle.
WATERMARK_W_FRAC = 0.20
WATERMARK_H_FRAC = 0.08

#: Side margin. A 9:16 frame loses its edges to platform chrome; text lives inside this.
SAFE_X_FRAC = 0.055

#: Visible clearance kept between our plates and the watermark zone, so "not overlapping"
#: also looks like "not crowding".
CLEARANCE_FRAC = 0.012

#: The overlay plate starts here and runs to just above the watermark — the lower ~60%.
OVERLAY_TOP_FRAC = 0.40

#: The credit plate's gap from the bottom edge, and its nominal height (it grows upward when
#: a long credit wraps, which is why nothing clips it).
CREDIT_BOTTOM_FRAC = 0.022
CREDIT_PLATE_H_FRAC = 0.032

#: Credit type size, in canvas units (height/100): small, but never below the 24px floor a
#: phone needs — 1.35 units is 31px on the 1296x2304 composite, 26px delivered.
CREDIT_FS_UNITS = 1.35

#: `clip` loops a source shorter than the narration by repeating the demuxer. The `loop`
#: FILTER would buffer raw frames instead — at 1296x2304 that is ~9 MB a frame.
CLIP_INPUT_ARGS = ("-stream_loop", "-1")


def is_media(scene: dict) -> bool:
    return scene.get("kind") == "media"


def default_motion(kind: str) -> str:
    """A still needs manufactured motion; footage already has its own."""
    return "clip" if kind == "video" else "kenburns"


def check_motion(kind: str, motion: str) -> None:
    """Refuse a motion that cannot work on this kind of source.

    Not a style rule — each rejected pairing is a concrete failure:

      clip on a still      `clip` plays frames and a still has one. The source is looped at
                           the input (CLIP_INPUT_ARGS), and an image2 input restarts its PTS
                           on every pass, so `trim=duration=` is never reached and `-t` never
                           fires: ffmpeg writes 0 bytes and runs forever.
      kenburns on footage  zoompan's `d=` counts INPUT frames, not output frames, so on a
                           video it consumes frame 0 and holds it — the scene is a freeze
                           frame that looks like a still by mistake.

    `hold` is the one motion both kinds share: on a still it clones the frame, on footage it
    plays the clip through and then freezes the last frame for the rest of the scene.
    """
    if motion not in MOTIONS:
        raise ValueError(f"unknown media motion {motion!r}; known: {', '.join(MOTIONS)}")
    if kind not in MOTIONS_FOR:
        raise ValueError(f"unknown media kind {kind!r}; known: {', '.join(MOTIONS_FOR)}")
    allowed = MOTIONS_FOR[kind]
    if motion in allowed:
        return None
    why = ("`clip` plays frames and a still has only one: looped at the input it never "
           "reaches the trim point, so ffmpeg writes nothing and runs forever"
           if motion == "clip" else
           "zoompan counts INPUT frames, so on footage `kenburns` consumes frame 0 and "
           "holds it — the scene comes out a freeze frame")
    raise ValueError(f"motion {motion!r} cannot be used with a {kind} src: {why}. "
                     f"Use one of: {', '.join(allowed)}")


# --- the source file ------------------------------------------------------------------

def repo_root(spec_path) -> pathlib.Path:
    """The directory a spec's relative `src:` paths are resolved against.

    The nearest ancestor of the spec carrying a `.git` or `pyproject.toml`, so a caller in
    another repo writes `media/earth/x.mp4` the way it would in its own README. With no
    marker anywhere above it (a loose spec in a scratch directory) the spec's own directory
    stands in, which is the only other thing it could sensibly mean.
    """
    spec = pathlib.Path(spec_path).expanduser().resolve()
    start = spec.parent if spec.is_file() or spec.suffix else spec
    for directory in (start, *start.parents):
        if any((directory / marker).exists() for marker in ROOT_MARKERS):
            return directory
    return start


def resolve_src(spec_path, src: str) -> pathlib.Path:
    """`src:` -> an existing absolute path. Absolute as given, else repo-root-relative.

    A spec is data from another repository, so a relative `src:` may not climb out of that
    repository's root — the same reasoning as `short_variants.safe_slug`.
    """
    spec = pathlib.Path(spec_path).expanduser()
    raw = pathlib.Path(str(src)).expanduser()
    if raw.is_absolute():
        resolved = raw.resolve()
        root = None
    else:
        root = repo_root(spec)
        resolved = (root / raw).resolve()
        if root not in resolved.parents:
            raise ValueError(
                f"media src {src!r} resolves to {resolved}, which is outside the spec's "
                f"repository root {root} — a relative src must stay inside the repo that "
                f"ships the spec ({spec})")
    if not resolved.is_file():
        where = f" (root {root})" if root is not None else ""
        raise FileNotFoundError(
            f"media src {src!r} does not exist: looked for {resolved}{where}, "
            f"resolved for spec {spec}")
    return resolved


def media_kind(path) -> str:
    """'image' or 'video', by suffix. Anything else is an error, not a guess."""
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return "video"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    raise ValueError(
        f"media src {path} has suffix {suffix!r}, which this renderer does not handle; "
        f"video: {', '.join(VIDEO_SUFFIXES)} · images: {', '.join(IMAGE_SUFFIXES)}")


def check_credit(kind: str, credit: str | None) -> None:
    """A still is licensed on attribution and cannot credit itself on screen."""
    if kind == "image" and not (credit or "").strip():
        raise ValueError(
            "a `media` scene whose src is a still image must carry a `credit:` line — the "
            "imagery is licensed on attribution and a still cannot credit itself on screen")


# --- boxes ----------------------------------------------------------------------------

def boxes_overlap(a, b) -> bool:
    """True when two (left, top, right, bottom) rectangles share any area. Edges may touch."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def watermark_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Earth Studio's attribution zone: the bottom-right corner. Keep everything out of it."""
    return (round(width * (1 - WATERMARK_W_FRAC)), round(height * (1 - WATERMARK_H_FRAC)),
            int(width), int(height))


def overlay_box(width: int, height: int) -> tuple[int, int, int, int]:
    """The card plate: the lower ~60%, inside the side margins, stopping above the watermark."""
    x = round(width * SAFE_X_FRAC)
    return (x, round(height * OVERLAY_TOP_FRAC), int(width) - x,
            round(height * (1 - WATERMARK_H_FRAC - CLEARANCE_FRAC)))


def credit_box(width: int, height: int) -> tuple[int, int, int, int]:
    """The credit plate: bottom-LEFT, stopping short of the watermark's left edge."""
    x = round(width * SAFE_X_FRAC)
    right = round(width * (1 - WATERMARK_W_FRAC)) - round(width * CLEARANCE_FRAC)
    bottom = int(height) - round(height * CREDIT_BOTTOM_FRAC)
    return (x, bottom - round(height * CREDIT_PLATE_H_FRAC), right, bottom)


# --- HTML -----------------------------------------------------------------------------

def credit_plate_html(credit: str, brand: dict, width: int = 1296, height: int = 2304) -> str:
    """A transparent full-frame page carrying only the credit plate, bottom-left.

    Bottom-anchored with a max-width and ordinary wrapping, so a long credit grows upward
    into empty frame instead of being clipped: attribution that is cut off is not attribution.
    """
    text = str(credit or "").strip()
    if not text:
        raise ValueError("credit_plate_html needs a non-empty credit line")
    left, _top, right, bottom = credit_box(width, height)
    unit = height / 100.0
    fs = CREDIT_FS_UNITS * unit
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{width}px;height:{height}px;background:transparent;
  font-family:{brand['font']};-webkit-font-smoothing:antialiased}}
.credit{{position:absolute;left:{left}px;bottom:{height - bottom}px;
  max-width:{right - left}px;padding:{0.55 * fs:.0f}px {0.85 * fs:.0f}px;
  border-radius:{0.45 * fs:.0f}px;color:{brand['fg']};font-size:{fs:.1f}px;line-height:1.24;
  font-weight:700;font-variant-caps:all-small-caps;letter-spacing:.06em;
  text-shadow:0 1px 2px rgba(0,0,0,.55)}}
.credit::before{{content:'';position:absolute;inset:0;background:{brand['bg']};opacity:.62;
  border-radius:inherit}}
.credit span{{position:relative}}
</style></head><body>
<div class="credit"><span>{_html.escape(text, quote=True)}</span></div>
</body></html>"""


def overlay_html(overlay: dict, brand: dict, width: int = 1296, height: int = 2304) -> str:
    """The card renderer, boxed into the lower frame over a transparent background."""
    left, top, right, bottom = overlay_box(width, height)
    return cards.card_html(overlay["template"], overlay.get("data") or {}, brand, width, height,
                           transparent=True, box=(left, top, right - left, bottom - top))


def media_frame_html(poster, layers, width: int = 1296, height: int = 2304,
                     bg: str = "#101418") -> str:
    """A still of the finished scene: the poster, covered, with the layer PNGs stacked on it.

    build_video renders its frame this way rather than re-implementing the layout, so the
    still it produces is composed of exactly the PNGs ffmpeg composites in the Short.
    """
    stack = "".join(f'\n<img class="layer" src="file://{pathlib.Path(p).resolve()}">'
                    for p in layers)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{width}px;height:{height}px;overflow:hidden;background:{bg}}}
img{{position:absolute;left:0;top:0;width:{width}px;height:{height}px}}
.bg{{object-fit:cover}}
</style></head><body>
<img class="bg" src="file://{pathlib.Path(poster).resolve()}">{stack}
</body></html>"""


# --- ffmpeg ---------------------------------------------------------------------------

def ffmpeg_video_filter(motion: str, dur: float, w: int, h: int, fps: int = FPS) -> str:
    """The `-vf` chain that turns one media source into `dur` seconds of a `w`x`h` frame.

    Every motion starts by covering the frame — scale up to fill, then crop — because a 16:9
    source in a 9:16 frame must fill it: letterbox bars on a Short read as a mistake.

      clip      trim the footage to the narration (looped at the input, see CLIP_INPUT_ARGS)
      kenburns  zoompan 1.0 -> 1.08 over the scene, centred; the default for a still
      hold      one frame, padded out by cloning it
    """
    if motion not in MOTIONS:
        raise ValueError(f"unknown media motion {motion!r}; known: {', '.join(MOTIONS)}")
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if motion == "clip":
        return f"{cover},fps={fps},trim=duration={dur:.3f},setpts=PTS-STARTPTS"
    if motion == "kenburns":
        n = max(1, math.ceil(dur * fps))
        dz = (KENBURNS_ZOOM - 1.0) / n
        return (f"{cover},zoompan=z='min(zoom+{dz:.7f},{KENBURNS_ZOOM})':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={w}x{h}:fps={fps}")
    return f"{cover},fps={fps},tpad=stop_mode=clone:stop_duration={dur:.3f}"
