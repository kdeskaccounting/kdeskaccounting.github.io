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

**The lower-right half of the bottom strip is not ours.** Google Earth Studio burns its
attribution watermark ("Google Earth", with a data-provider line under it) into every frame it
exports, and the terms require it to stay visible. It is anchored bottom-right but it is not
in the corner: measured on a real 1080x1920 portrait render it occupies x 0.495-0.815,
y 0.909-0.955. `WATERMARK_*` fences off x >= 0.45, y >= 0.88, which contains that with room on
every side. The credit plate is anchored bottom-LEFT and stops short of the zone horizontally,
and the overlay's bottom edge stops short of it vertically. `boxes_overlap()` plus the tests in
tests/test_media.py are what keep a later layout tweak from sliding a plate over it.

**A still must be credited.** Footage may carry its own on-screen attribution; a still frame
never does, so `check_credit()` refuses an image scene with no `credit:`.

**A landscape source is never cropped to 9:16 unless the scene asks.** Scaling a 16:9
photograph up until it fills a 9:16 frame and cropping the overflow keeps under a third of its
width, so the subject is whatever happened to sit in the middle column. Above
`BLUR_FILL_RATIO` the source is fitted INSIDE the frame and composited over a blurred,
darkened copy of itself — the whole picture stays visible, the frame is still full. Portrait
sources keep the cover-and-crop fill, which only costs them their edges. A scene that knows
better says so: `fill: crop | blur` overrides that ratio test and `focus: [fx, fy]` says which
part of the picture the crop keeps, which is how a 1.60:1 hero fills the frame instead of
letterboxing at 35% of its height. See `ffmpeg_video_steps()` and `scene_fill()`.

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

#: Width/height at which a source stops being cropped to fill the 9:16 frame and starts being
#: letterboxed over a blurred copy of itself.
#:
#: Cropping a 16:9 photograph (1.78) to 9:16 keeps 32% of its width and throws the rest away —
#: whatever the subject was, it is now whatever happened to be in the middle column. Above
#: this ratio the whole picture stays on screen over a blurred backdrop (the look every
#: vertical feed uses for landscape material); at or below it the crop takes only the edges
#: and stays. 0.8 is deliberately below 1.0: a mildly portrait 3:4 source (0.75) still crops
#: cleanly, a square one (1.0) does not.
BLUR_FILL_RATIO = 0.8

#: How a source fills the frame, when a scene says rather than letting the ratio decide.
#: `crop` covers and crops — the whole frame is picture. `blur` letterboxes over a blurred
#: copy — the whole PICTURE survives. Absent, wants_blur_fill() decides from the ratio, which
#: is what every existing spec gets.
FILLS = ("crop", "blur")

#: The backdrop: boxblur radius:power, then a slight darken. 20:2 is soft enough that no edge
#: of the original survives it, and -0.10 brightness keeps the sharp middle the brightest
#: thing on the frame without turning the sides into a black bar.
BLUR_RADIUS, BLUR_POWER = 20, 2
BLUR_DARKEN = "0.10"

# --- the geometry ---------------------------------------------------------------------
#
# Every fraction below is of the frame, so the same numbers hold for the 1296x2304 composite,
# the 1080x1920 delivered Short and build_video's 2400x1350 still.

#: Earth Studio's attribution watermark. NOTHING may be drawn inside this rectangle.
#:
#: MEASURED off the first real Earth Studio portrait render (1080x1920, cloud video,
#: Attribution Position bottom-right at its maximum offsets), not guessed from the corner it
#: is nominally anchored to: the "Google Earth" wordmark occupies x 0.495-0.815 and
#: y 0.909-0.933 of the frame, and the smaller data-provider line beneath it reaches about
#: y 0.955. Earth Studio will not place the mark further right or lower than that on a
#: portrait canvas, so those are its extremes.
#:
#: The mark is therefore NOT in the bottom-right corner — it starts at the middle of the
#: width and stops a clear 4.5% of the height above the bottom edge. The zone that preceded
#: this one (0.20 x 0.08: x >= 0.80, y >= 0.92) covered the corner the mark is anchored to
#: and almost none of the mark itself. 0.55 x 0.12 (x >= 0.45, y >= 0.88) contains all of it
#: with room either side, and every box below is derived from these two numbers, so this is
#: the only place to edit if a future Earth Studio release moves the mark again.
WATERMARK_W_FRAC = 0.55
WATERMARK_H_FRAC = 0.12

#: Side margin. A 9:16 frame loses its edges to platform chrome; text lives inside this.
SAFE_X_FRAC = 0.055

#: Visible clearance kept between our plates and the watermark zone, so "not overlapping"
#: also looks like "not crowding".
CLEARANCE_FRAC = 0.012

#: The overlay plate starts here and runs to just above the watermark zone. That leaves it
#: 0.40 -> 0.868 of the height, ~47% of the frame: the zone taking 12% of the height instead
#: of 8% comes straight off the bottom of the card, and 40% is the floor below which a
#: ranked_list stops being a card and becomes a strip (tests/test_media.py asserts it).
OVERLAY_TOP_FRAC = 0.40

#: The credit plate's gap from the bottom edge, and its nominal height (it grows upward when
#: a long credit wraps, which is why nothing clips it).
#:
#: The plate STAYS bottom-left rather than moving above the zone, even though the zone's left
#: edge at 0.45w now cuts its width to ~0.38w. Above the zone there is nowhere to put it: the
#: overlay's bottom edge is already at 0.868 and the zone starts at 0.88, a 0.012 gap, so the
#: plate would have to push the card up and spend card height on a credit line. Below and to
#: the left of the mark is empty frame that costs nothing, and a realistic credit fits there
#: in two lines — measured, in tests/test_media_scene_e2e.py.
CREDIT_BOTTOM_FRAC = 0.022
CREDIT_PLATE_H_FRAC = 0.032

#: Credit type size, in canvas units (height/100): small, but never below the 24px floor a
#: phone needs — 1.35 units is 31px on the 1296x2304 composite, 26px delivered. Held at 1.35
#: when the plate narrowed: shrinking the type to keep the credit on one line would have put
#: it under that floor, and an illegible credit is not attribution. It wraps instead.
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
    article = "an" if kind[0] in "aeiou" else "a"
    raise ValueError(f"motion {motion!r} cannot be used with {article} {kind} src: {why}. "
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


def validate_spec(spec: dict, spec_path) -> None:
    """Check every `media` scene in a spec before anything at all is rendered.

    Validating inside the render loop means scene 3's typo surfaces after scenes 0-2 have been
    narrated, screenshotted and encoded — minutes of work thrown away, and on a bad pairing
    (see check_motion) a wedged ffmpeg rather than an error. This is the preflight: one pass
    over the whole spec, failing on the first bad scene and naming its index.

    It checks every media scene, including ones no `short:` block selects — the spec is the
    contract, and a scene that is broken today is broken for the variant that picks it up
    tomorrow.
    """
    for index, scene in enumerate(spec.get("scenes") or []):
        if not is_media(scene or {}):
            continue
        where = f"scene {index} (kind: media)"
        src = scene.get("src")
        if not src:
            raise ValueError(f"{where} has no `src:` — a media scene needs a file to show")
        try:
            path = resolve_src(spec_path, src)
            kind = media_kind(path)
            check_credit(kind, scene.get("credit"))
            check_motion(kind, scene.get("motion") or default_motion(kind))
            scene_fill(scene)
        except (ValueError, FileNotFoundError) as exc:
            raise type(exc)(f"{where}: {exc}") from exc


def check_credit(kind: str, credit: str | None) -> None:
    """A still is licensed on attribution and cannot credit itself on screen."""
    if kind == "image" and not (credit or "").strip():
        raise ValueError(
            "a `media` scene whose src is a still image must carry a `credit:` line — the "
            "imagery is licensed on attribution and a still cannot credit itself on screen")


def scene_fill(scene: dict) -> tuple:
    """(`fill` or None, (fx, fy)) off one media scene. Validates both.

    Both keys are optional and both are read here rather than in the render loop, so
    validate_spec() refuses a bad one in the preflight. A misspelling (`fill: strech`, a
    `focus` outside the frame) that is silently ignored is worse than one that stops the run:
    the Short renders, looks plausible, and is not the framing the spec asked for.
    """
    scene = scene or {}
    fill = scene.get("fill")
    if fill is not None:
        fill = str(fill)
        if fill not in FILLS:
            raise ValueError(f"unknown media fill {fill!r}; known: {', '.join(FILLS)}")
    focus = scene.get("focus") or (0.5, 0.5)
    try:
        fx, fy = (float(focus[0]), float(focus[1]))
    except (TypeError, ValueError, IndexError, KeyError):
        raise ValueError(f"media focus must be [fx, fy], got {scene.get('focus')!r}") from None
    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
        raise ValueError(f"media focus must be two fractions in [0, 1]; got [{fx}, {fy}]")
    return fill, (fx, fy)


# --- boxes ----------------------------------------------------------------------------

def boxes_overlap(a, b) -> bool:
    """True when two (left, top, right, bottom) rectangles share any area. Edges may touch."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def watermark_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Earth Studio's attribution zone. Keep everything out of it.

    Anchored to the bottom-right corner but far larger than one: the mark itself starts at
    mid-width and 0.909 of the height, so the zone reaches x >= 0.45, y >= 0.88.
    """
    return (round(width * (1 - WATERMARK_W_FRAC)), round(height * (1 - WATERMARK_H_FRAC)),
            int(width), int(height))


def overlay_box(width: int, height: int) -> tuple[int, int, int, int]:
    """The card plate: OVERLAY_TOP_FRAC down, inside the side margins, stopping a visible
    CLEARANCE_FRAC above the watermark zone."""
    x = round(width * SAFE_X_FRAC)
    return (x, round(height * OVERLAY_TOP_FRAC), int(width) - x,
            round(height * (1 - WATERMARK_H_FRAC - CLEARANCE_FRAC)))


def credit_box(width: int, height: int) -> tuple[int, int, int, int]:
    """The credit plate: bottom-LEFT, stopping short of the watermark zone's left edge.

    The bottom and right edges are the load-bearing ones. The nominal top is where a
    single-line plate starts; a wrapped credit grows upward past it into empty frame, which
    is deliberate — see credit_plate_html.
    """
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

def cover_chain(w: int, h: int, fx: float = 0.5, fy: float = 0.5) -> str:
    """Scale up until the frame is covered, then crop the overflow away.

    `fx`/`fy` say WHAT to keep: 0.5/0.5 is the implicit centre crop ffmpeg does anyway, and
    is emitted as the bare `crop=w:h` it always was so no existing render moves. Day 3's
    hero is 1.60:1 and its subject sits slightly above centre, hence focus [0.50, 0.42].
    """
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase"
    if (float(fx), float(fy)) == (0.5, 0.5):
        return f"{cover},crop={w}:{h}"
    return f"{cover},crop={w}:{h}:x=(iw-{w})*{float(fx):.3f}:y=(ih-{h})*{float(fy):.3f}"


def motion_chain(motion: str, dur: float, w: int, h: int, fps: int = FPS) -> str:
    """The motion half of the chain, on a source that already fills the `w`x`h` frame.

      clip      trim the footage to the narration (looped at the input, see CLIP_INPUT_ARGS)
      kenburns  zoompan 1.0 -> 1.08 over the scene, centred; the default for a still
      hold      one frame, padded out by cloning it
    """
    if motion not in MOTIONS:
        raise ValueError(f"unknown media motion {motion!r}; known: {', '.join(MOTIONS)}")
    if motion == "clip":
        return f"fps={fps},trim=duration={dur:.3f},setpts=PTS-STARTPTS"
    if motion == "kenburns":
        n = max(1, math.ceil(dur * fps))
        dz = (KENBURNS_ZOOM - 1.0) / n
        return (f"zoompan=z='min(zoom+{dz:.7f},{KENBURNS_ZOOM})':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={w}x{h}:fps={fps}")
    return f"fps={fps},tpad=stop_mode=clone:stop_duration={dur:.3f}"


def ffmpeg_video_filter(motion: str, dur: float, w: int, h: int, fps: int = FPS,
                        focus: tuple = (0.5, 0.5)) -> str:
    """The `-vf` chain that turns one PORTRAIT media source into `dur` seconds of `w`x`h`.

    Cover, not contain: a source that is already taller than it is wide loses only its edges
    to the crop, and letterbox bars on a Short read as a mistake. A landscape source would
    lose most of itself here, so by default it goes through blur_fill_steps() instead — see
    ffmpeg_video_steps(), which is what the renderer actually calls. A scene that asks for
    `fill: crop` comes back here whatever its shape, and `focus` says which part it keeps.
    """
    return f"{cover_chain(w, h, focus[0], focus[1])},{motion_chain(motion, dur, w, h, fps)}"


def wants_blur_fill(src_w: int | None, src_h: int | None) -> bool:
    """Is this source too wide to crop to 9:16 — i.e. does it need the blurred backdrop?

    True for anything WIDER than BLUR_FILL_RATIO; the ratio itself, and everything more
    portrait than it, still crops. False too when the size is unknown (probing failed),
    which keeps the old cover-and-crop as the fallback rather than changing the picture on
    a guess.
    """
    if not src_w or not src_h:
        return False
    return src_w / src_h > BLUR_FILL_RATIO


def blur_fill_steps(src_label: str, out_label: str, w: int, h: int) -> list[str]:
    """The TikTok fill: the whole source letterboxed over a blurred, darkened copy of itself.

    Two chains off one `split`, so a clip's backdrop is that same clip rather than a still of
    it, and a Ken Burns backdrop drifts with the photograph. The foreground is
    `force_original_aspect_ratio=decrease` — the entire frame of the source, nothing cropped —
    centred over a background built the way the portrait path builds its whole picture
    (cover + crop), then blurred and dimmed so the eye lands on the sharp middle.

    Output is exactly `w`x`h`, so every layer laid over it afterwards — the card overlay, the
    credit plate, the caption band — keeps the geometry media.overlay_box / credit_box and
    the Earth Studio watermark zone already agreed on.
    """
    bg, fg = f"{out_label}_bg", f"{out_label}_fg"
    return [
        f"[{src_label}]split=2[{bg}_s][{fg}_s]",
        f"[{bg}_s]{cover_chain(w, h)},boxblur={BLUR_RADIUS}:{BLUR_POWER},"
        f"eq=brightness=-{BLUR_DARKEN}[{bg}]",
        f"[{fg}_s]scale={w}:{h}:force_original_aspect_ratio=decrease[{fg}]",
        f"[{bg}][{fg}]overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2:"
        f"format=auto[{out_label}]",
    ]


def ffmpeg_video_steps(motion: str, dur: float, w: int, h: int, fps: int = FPS,
                       src_w: int | None = None, src_h: int | None = None,
                       src_label: str = "0:v", out_label: str = "m0",
                       fill: str | None = None, focus: tuple = (0.5, 0.5)) -> list[str]:
    """The filter-graph chains that turn one media source into `dur` seconds of `w`x`h`.

    A list of chains rather than one string because the blur fill needs a `split`, which
    cannot live inside a single linear chain. Portrait sources come back as the one chain
    they always were, so nothing about an existing portrait render moves.

    `fill` is the scene's opt-in override (see FILLS and scene_fill): given, it decides
    instead of the source's ratio, so a landscape hero can cover-crop on `focus` rather than
    sit at 35% of frame height over blur. Absent — which is every existing spec —
    wants_blur_fill() decides exactly as before.
    """
    if motion not in MOTIONS:
        raise ValueError(f"unknown media motion {motion!r}; known: {', '.join(MOTIONS)}")
    blur = wants_blur_fill(src_w, src_h) if fill is None else (fill == "blur")
    if not blur:
        return [f"[{src_label}]"
                f"{ffmpeg_video_filter(motion, dur, w, h, fps, focus)}[{out_label}]"]
    fill_label = f"{out_label}_fill"
    return [*blur_fill_steps(src_label, fill_label, w, h),
            f"[{fill_label}]{motion_chain(motion, dur, w, h, fps)}[{out_label}]"]
