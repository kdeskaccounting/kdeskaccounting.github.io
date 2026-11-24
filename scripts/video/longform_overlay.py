"""The v6 Shorts overlay language on the 16:9 long-form path (2026-11-23, Stephen after episode 1:
"I didn't hear many sound effects or see hoot or any other overlay graphics").

A `kind: media` scene on a `landscape:` spec takes make_short's own `callouts:` list (callouts.py:
the same keys, the same validator), so a Shorts callout list works unchanged on a 16:9 scene,
plus the scene's `fx:` verdict washes (grammar.py) and the Shorts' sounds. Everything is drawn
with PIL as PNG layers and composited by ffmpeg overlays (no browser), at 1920x1080.

CALLOUTS (callouts.check validates them; every key make_short reads is read here)

  type     sticker | badge | text | arrow | circle | hoot
  when     a word reference {word, nth?, edge?, offset?} or seconds; `at:` (seconds) is accepted
           as the same thing. Lands `offset_ms` after (default 80 ms after a word, 0 after
           seconds: the one timing deviation from the Shorts, which add 80 ms to seconds too).
  anchor   {x, y} fractions of the 16:9 frame: the element's centre (an arrow's TIP). `track:`
           is accepted and its first point used (no tracking on 16:9). Badge default (0.185, 0.12).
  size     keeps the pixels it has in a Short. Fractions of the Short's WIDTH (hoot, arrow,
           circle) are taken of 1080 px, the 16:9 frame's height; fractions of the Short's HEIGHT
           (badge, text) of 1920 px. So `size: 0.22` is the same 238 px Hoot in both, and a
           0.044 badge the same 84 px cap height. Stickers keep the 16:9 rule from the first
           long-form commit: their LONGER side (after trimming the transparent margin) is
           size x 1080 px, default 0.42.
  hold     next_cut | scene | milliseconds (after the entrance), as in the Shorts. ABSENT, a
           type whose Shorts default is `next_cut` (sticker, badge, text, hoot) stays
           `landscape.callout_s` (3 s), cut short at the next beat cut 1 s or more after it lands:
           a long-form scene can run 15 s with no cut, and next_cut there would mean all of it.
           `seconds:` is accepted as hold in seconds.
  ease     overshoot | pop | slide_in | fade | none | an EASING name, with `in_ms`. The scale
           curves (pop_badge 0.60 -> 1.15 -> 1.0 in 300 ms, pop_arrow from the tip, pop_stamp) are
           drawn as a short PNG sequence; slide_in is an overlay expression from `enter_from`
           (default: the nearest of bottom/left/right).
  out      snap only. `fade` / `slide_out` render as snap (a note is printed): a deviation.
  sfx      pop | chime | hit | whoosh | ding | null, defaulting per type exactly as the Shorts
           (callouts.TYPE_DEFAULTS: sticker whoosh, badge ding, arrow ding, circle pop, text
           pop, hoot pop). Played from `audio.sfx.events.<role>`; a role with no file there
           falls back to `audio.sfx.on_tag`; otherwise skipped with a note.
  text, color, direction, tilt, labels, label (a string or one label mapping): per type, as
           callouts.py documents them.
  hoot     pose, say, bubble, badge_text, point_to, blur_bg, as callouts.HOOT_DOC. The pose set
           is PARKSHEET_HOOT_SET, else the spec's top-level `hoot: {outfit: X}`
           (media/brand/hoot/X/hoot.json in the spec's repo), else media/brand/hoot/hoot.json.
           Default place: lower-left, beside the lower-third captions (lower-right when he
           points left); moved up above any caption box or Earth Studio zone on screen in his
           window. An explicit `anchor` that covers a caption box, the point he points to, an
           Earth zone or the frame edge is refused, as the Shorts refuse it.

  Every callout is refused over an Earth Studio attribution zone.

VERDICTS (`fx:` on the scene, grammar.parse_fx_list: a mapping or a list of up to 4)

  {verdict: good|bad, style: wash, at: {word}, hold?} -- the measured wash (red 0.24 + vignette,
  330 ms; green 0.44 to the cut) -- or the channel grade {verdict, from, to, strength, ramp_ms}.
  Laid on the picture before every graphic. Its sound is `audio.sfx.on_verdict.good|bad` at the
  wash's start.

SOUNDS (`audio.sfx`, the Shorts block)

  events (per role), on_tag, on_verdict, min_gap are read. `on_cut: null`, `opening: null` are
  accepted and mean nothing; a non-null `on_cut` (whoosh on every cut: off for Shorts too),
  `opening`, `cues`, `on_move` or legacy whoosh keys (`src`, `gain_db`, `lead`, `beats`) are
  refused by name. `landscape.chapter_sfx` (default {src: 'bundle:whoosh', gain_db: -16,
  lead: 0.2}, the whoosh of the Shorts' opening sting; null for none) plays as each chapter
  card slides in, starting `lead` before the cut so it peaks on it. All one-shots are thinned
  with grammar.thin (min_gap; verdict before tag before chapter), mixed onto one bus and laid
  over the ducked bed by make_short.audio_steps, never under the duck.

Refused by name: overlay `elements:` (tags, emoji, figures, calendars), `scrim:`, `blur:`,
`crashzoom:`, `still_of:`, `tail_s:` (longform.REFUSED_SCENE_KEYS).
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
W, H, FPS = 1920, 1080, 30
#: The Short's frame: a `size` keeps the pixels it has there.
SHORT_W, SHORT_H = 1080, 1920
FONT_ROUNDED = HERE / "fonts" / "Nunito-Variable.ttf"
FONT_BOLD = HERE / "fonts" / "Carlito-Bold.ttf"
INK = (0x11, 0x11, 0x11)
ARROW_FILL = (0xFF, 0xC8, 0x00)
STAMP_RED = "#E5202A"
CAP_EM = 0.705
#: Default Hoot place, frame fractions: his body's left edge and bottom edge.
HOOT_LEFT, HOOT_BOTTOM = 0.035, 0.93
HOOT_GAP = 0.012
CHAPTER_SFX = {"src": "bundle:whoosh", "gain_db": -16.0, "lead": 0.2}
CHAPTER_SFX_KEYS = ("src", "gain_db", "lead", "start", "end")


# --- normalising + checking ---------------------------------------------------------------------

def normalise(c: dict, tag: str) -> dict:
    """The landscape spellings folded into the Shorts schema: `at` -> `when`, `seconds` -> `hold`
    (ms), `label` -> `labels`. Returns a new dict."""
    c = dict(c)
    if "at" in c:
        if "when" in c:
            raise SystemExit(f"{tag}: give exactly one of `when:` or `at:`")
        c["when"] = c.pop("at")
    if "seconds" in c:
        if "hold" in c:
            raise SystemExit(f"{tag}: give `seconds:` or `hold:`, not both")
        s = c.pop("seconds")
        if isinstance(s, bool) or not isinstance(s, (int, float)) or not 0.3 <= s <= 60:
            raise SystemExit(f"{tag}: `seconds` must be a number of seconds in [0.3, 60]")
        c["hold"] = float(s) * 1000.0
    if "label" in c:
        lab = c.pop("label")
        if isinstance(lab, str):
            lab = {"text": lab, "x": 0.5, "y": 0.80, "size": 0.14}
        c["labels"] = [lab] + list(c.get("labels") or [])
    return c


def load_hoot_set(spec: dict | None, spec_path) -> dict:
    """The pose set: PARKSHEET_HOOT_SET, else the spec's `hoot: {outfit}`, else the default."""
    import callouts
    import make_short
    import media
    outfit = ((spec or {}).get("hoot") or {}).get("outfit") if isinstance(
        (spec or {}).get("hoot"), dict) else None
    if outfit and not os.environ.get("PARKSHEET_HOOT_SET"):
        path = (media.repo_root(spec_path) / "media" / "brand" / "hoot" / str(outfit)
                / "hoot.json").resolve()
        if path in make_short._HOOT_CACHE:
            return make_short._HOOT_CACHE[path]
        if not path.is_file():
            raise SystemExit(f"hoot.outfit {outfit!r}: no pose set at {path}")
        data = callouts.check_hoot_set(json.loads(path.read_text()), str(path))
        for entry in [*data["poses"].values(), data["bubble"]]:
            entry["src"] = str((path.parent / entry["src"]).resolve())
        make_short._HOOT_CACHE[path] = data
        return data
    try:
        return make_short.load_hoot_set(spec_path)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"hoot: {exc}") from None


def check(raw, where: str, spec: dict | None = None, spec_path=None) -> list:
    """A scene's `callouts:` -> normalised, callouts.check()ed copies (sticker srcs resolved,
    hoots carrying their pose set under `_hoot`). Raises SystemExit naming the callout."""
    import callouts
    import illustrate
    import media
    if raw is None:
        return []
    if not isinstance(raw, list) or not raw:
        raise SystemExit(f"{where}: `callouts:` must be a non-empty list")
    out = []
    for i, c in enumerate(raw):
        tag = f"{where} callouts[{i}]"
        if not isinstance(c, dict):
            raise SystemExit(f"{tag}: a callout is a mapping, got {c!r}")
        c = normalise(c, tag)
        if c.get("type") == "hoot":
            c["_hoot"] = load_hoot_set(spec, spec_path) if spec_path is not None else None
            if c["_hoot"] is None:
                c.pop("_hoot")
        try:
            callouts.check([c], tag)
        except callouts.CalloutError as exc:
            raise SystemExit(str(exc)) from None
        if c.get("type") == "sticker" and spec_path is not None:
            try:
                c["src"] = str(media.resolve_src(spec_path, c["src"]))
            except (FileNotFoundError, ValueError) as exc:
                raise SystemExit(f"{tag}: {exc}") from None
            if illustrate.png_size(c["src"]) is None:
                raise SystemExit(f"{tag}: {c['src']} is not a PNG; a sticker is a transparent "
                                 f"PNG cut-out")
        out.append(c)
    return out


# --- timing -----------------------------------------------------------------------------------

def window(c: dict, rows, dur: float, cuts, callout_s: float, tag: str) -> tuple:
    """(t0, t1, in_s, ease) on the scene clock."""
    import callouts
    import illustrate
    kind = c["type"]
    d = callouts.TYPE_DEFAULTS[kind]
    try:
        at = float(illustrate.resolve_time(c["when"], rows, tag, "when"))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    word = illustrate.is_wordref(c["when"])
    offset = c.get("offset_ms", callouts.DEFAULT_OFFSET_MS if word else 0.0)
    t0 = max(0.0, at + float(offset) / 1000.0)
    if t0 >= float(dur) - 0.1:
        raise SystemExit(f"{tag}: lands at {t0:.2f}s, at or after its scene ends ({dur:.2f}s)")
    holds_badge = kind == "hoot" and (c.get("pose") == "badge" or
                                      ("badge_text" in c and c.get("pose") is None))
    if kind == "hoot":
        ease = c.get("ease") or ("overshoot" if holds_badge or "badge_text" in c else "slide_in")
    else:
        ease = c.get("ease", d["ease"])
    ease = callouts.ease_of(ease, kind)
    base = callouts.EASING.get(ease, {})
    in_ms = float(c.get("in_ms", base.get("settle_ms") or base.get("ms") or 0.0))
    if ease == "none":
        in_ms = 0.0
    hold = c.get("hold")
    cuts = sorted(float(t) for t in (cuts or ()))
    if hold is None:
        hold = d["hold"]
        if hold == "next_cut":                       # the long-form default (see the docstring)
            t1 = t0 + float(callout_s)
            nxt = next((t for t in cuts if t >= t0 + 1.0), None)
            t1 = min(t1, nxt) if nxt is not None else t1
            return round(t0, 3), round(min(t1, float(dur)), 3), in_ms / 1000.0, ease
    if hold == "next_cut":
        t1 = next((t for t in cuts if t > t0 + 1e-3), float(dur))
    elif hold == "scene":
        t1 = float(dur)
    else:
        t1 = t0 + in_ms / 1000.0 + float(hold) / 1000.0
    return round(t0, 3), round(min(t1, float(dur)), 3), in_ms / 1000.0, ease


# --- drawing (PIL) ----------------------------------------------------------------------------

def _rgb(value, fallback="#FFFFFF") -> tuple:
    s = str(value or fallback).lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _font(px: float):
    from PIL import ImageFont
    font = ImageFont.truetype(str(FONT_ROUNDED), max(8, round(px)))
    try:
        font.set_variation_by_axes([900])
    except (OSError, AttributeError):
        font = ImageFont.truetype(str(FONT_BOLD), max(8, round(px)))
    return font


def text_image(lines, fs: float, color, ink=INK, stroke_k=0.08, shadow=True):
    """Heavy rounded type (Nunito Black), centred lines, dark outline + soft shadow: the badge /
    stamp / label look of callouts.py."""
    from PIL import Image, ImageDraw, ImageFilter
    font = _font(fs)
    stroke = max(1, round(stroke_k * fs))
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    boxes = [probe.textbbox((0, 0), ln, font=font, stroke_width=stroke) for ln in lines]
    lh = round(fs * 1.05)
    w = max(b[2] - b[0] for b in boxes) + 4 * stroke + 16
    h = lh * (len(lines) - 1) + (boxes[-1][3] - boxes[0][1]) + 4 * stroke + 16
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k, (ln, b) in enumerate(zip(lines, boxes)):
        x = (w - (b[2] - b[0])) // 2 - b[0]
        d.text((x, 8 + 2 * stroke - boxes[0][1] + k * lh), ln, font=font,
               fill=(*_rgb(color), 255), stroke_width=stroke, stroke_fill=(*ink, 255))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.putalpha(layer.getchannel("A").point(lambda a: a * 0.5))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(1, fs * 0.05))),
                            (0, max(1, round(fs * 0.04))))
    img.alpha_composite(layer)
    return img


def badge_image(c: dict):
    """`type: badge` / `type: text`: the text at its cap height, kept inside 0.8 of the frame."""
    import callouts
    kind = c["type"]
    cap = float(c.get("size", callouts.TYPE_DEFAULTS[kind]["size"])) * SHORT_H
    fs = cap / CAP_EM
    color = c.get("color", "#FFFFFF" if kind == "badge" else STAMP_RED)
    img = text_image([c["text"]], fs, color, stroke_k=0.08 if kind == "badge" else 0.07)
    if img.size[0] > 0.8 * W:
        img = text_image([c["text"]], fs * 0.8 * W / img.size[0], color)
    return img, (img.size[0] / 2, img.size[1] / 2)


def arrow_image(c: dict):
    """Flat yellow arrow with a dark outline, length size x 1080 px, its TIP the pivot."""
    from PIL import Image, ImageDraw
    import callouts
    length = float(c.get("size", callouts.TYPE_DEFAULTS["arrow"]["size"])) * SHORT_W
    angle = callouts.DIRECTIONS[c.get("direction", "down_left")]
    t = length * 0.22                                     # shaft thickness
    head_l, head_w = length * 0.42, length * 0.62
    pts = [(0, -t / 2), (length - head_l, -t / 2), (length - head_l, -head_w / 2), (length, 0),
           (length - head_l, head_w / 2), (length - head_l, t / 2), (0, t / 2)]
    rad = math.radians(angle)
    rot = [(x * math.cos(rad) - y * math.sin(rad), x * math.sin(rad) + y * math.cos(rad))
           for x, y in pts]
    pad = length * 0.08 + 6
    xs, ys = [p[0] for p in rot], [p[1] for p in rot]
    ox, oy = -min(xs) + pad, -min(ys) + pad
    w, h = math.ceil(max(xs) - min(xs) + 2 * pad), math.ceil(max(ys) - min(ys) + 2 * pad)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    poly = [(x + ox, y + oy) for x, y in rot]
    d = ImageDraw.Draw(img)
    d.polygon(poly, fill=(*ARROW_FILL, 255), outline=(*INK, 255), width=max(3, round(length * 0.035)))
    tip = (rot[3][0] + ox, rot[3][1] + oy)
    return img, tip


def circle_image(c: dict):
    """A yellow ring with a dark outline, diameter size x 1080 px, centred on the anchor."""
    from PIL import Image, ImageDraw
    import callouts
    dia = float(c.get("size", callouts.TYPE_DEFAULTS["circle"]["size"])) * SHORT_W
    ring = max(6, round(dia * 0.05))
    pad = ring + 4
    n = math.ceil(dia + 2 * pad)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((pad - 3, pad - 3, n - pad + 3, n - pad + 3), outline=(*INK, 255), width=ring + 6)
    d.ellipse((pad, pad, n - pad, n - pad), outline=(*ARROW_FILL, 255), width=ring)
    return img, (n / 2, n / 2)


def sticker_image(c: dict):
    import longform
    out = pathlib.Path(c["_work"])
    out.mkdir(parents=True, exist_ok=True)
    out = out / f"{c.get('_stem', 'sticker')}-src.png"
    longform.sticker_png({"src": c["src"], "size": c.get("size", longform.STICKER_SIZE),
                          "labels": [longform._label(lab, "label") for lab in
                                     (c.get("labels") or [])]}, out)
    from PIL import Image
    img = Image.open(out).convert("RGBA")
    if c.get("tilt"):
        img = img.rotate(-float(c["tilt"]), expand=True, resample=Image.BICUBIC)
    return img, (img.size[0] / 2, img.size[1] / 2)


# --- Hoot -------------------------------------------------------------------------------------

def _pose(c: dict, hs: dict, ax: float, ay: float) -> tuple:
    """(pose, mirrored?) -- callouts._pick_pose with the 16:9 frame's proportions."""
    import callouts
    pose = c.get("pose")
    pt = c.get("point_to")
    if pose is None:
        if "badge_text" in c:
            pose = "badge"
        elif pt is not None:
            dx, dy = (pt["x"] - ax) * W, (pt["y"] - ay) * H
            if abs(dx) >= abs(dy):
                pose = callouts.POINT_POSES["right" if dx > 0 else "left"]
            else:
                pose = callouts.POINT_POSES["down" if dy > 0 else "up"]
        else:
            pose = "neutral"
    mirror = False
    if pt is not None and pose in (callouts.POINT_POSES["left"], callouts.POINT_POSES["right"]):
        mirror = (pt["x"] > ax) != (pose == callouts.POINT_POSES["right"])
    return pose, mirror


def hoot_image(c: dict, hs: dict, ax: float | None, ay: float | None):
    """Hoot (pose, badge text, bubble) as one RGBA image. Returns (img, body_center_in_img,
    body_box_in_img, pose). (ax, ay) only steers the pose choice and bubble side; None for the
    default place (then he faces the frame centre)."""
    from PIL import Image, ImageDraw, ImageOps
    import callouts
    holds_badge = c.get("pose") == "badge" or ("badge_text" in c and c.get("pose") is None)
    size = float(c.get("size", callouts.HOOT_BADGE_SIZE if holds_badge
                       else callouts.TYPE_DEFAULTS["hoot"]["size"]))
    ref = hs["poses"]["neutral"]["body"]
    canvas = max(8, round(size * SHORT_W / (ref[2] - ref[0])))
    gx = ax if ax is not None else (0.8 if (c.get("point_to") or {}).get("x", 1) < 0.5 else 0.15)
    gy = ay if ay is not None else 0.7
    pose, mirror = _pose(c, hs, gx, gy)
    if pose not in hs["poses"]:
        raise SystemExit(f"unknown hoot pose {pose!r}; the set has {', '.join(sorted(hs['poses']))}")
    pdata = hs["poses"][pose]
    img = Image.open(pdata["src"]).convert("RGBA").resize((canvas, canvas), Image.LANCZOS)
    if mirror:
        img = ImageOps.mirror(img)
    body = list(pdata["body"])
    if mirror:
        body = [1 - body[2], body[1], 1 - body[0], body[3]]
    if "badge_text" in c:
        if "badge" not in pdata:
            raise SystemExit(f"hoot pose {pose} holds nothing to write `badge_text` on "
                             f"(poses with a badge: badge, nope)")
        cx, cy, r = pdata["badge"]
        if mirror:
            cx = 1 - cx
        r_px = r * canvas
        text = str(c["badge_text"])
        lines = text.split() if len(text) > 3 else [text]
        if len(lines) > 2:
            lines = [" ".join(lines[:-1]), lines[-1]]
        longest = max(len(ln) for ln in lines)
        fs = min(1.2 * r_px, 2.3 * r_px / max(1.0, longest * 0.62),
                 1.9 * r_px / (1.05 * len(lines)))
        t = text_image(lines, fs, pdata.get("badge_color", "#FFFFFF"), stroke_k=0.09)
        img.alpha_composite(t, (round(cx * canvas - t.size[0] / 2),
                                round(cy * canvas - t.size[1] / 2)))
    bx0, by0, bx1, by1 = (body[0] * canvas, body[1] * canvas, body[2] * canvas, body[3] * canvas)
    if c.get("say"):
        side = c.get("bubble", "auto")
        if side == "auto":
            side = "right" if gx < 0.5 else "left"
        img, (bx0, by0, bx1, by1), shift = _with_bubble(img, (bx0, by0, bx1, by1), hs, c, side)
    else:
        shift = (0, 0)
    center = ((bx0 + bx1) / 2, (by0 + by1) / 2)
    return img, center, (bx0, by0, bx1, by1), pose, shift


def _with_bubble(img, body, hs, c, side):
    """Hoot's image grown to carry the `say:` bubble beside his head (callouts._bubble_geometry
    in pixels: the bubble scaled to its text, tail tip a quarter down his head)."""
    from PIL import Image, ImageDraw, ImageOps
    import callouts
    b = hs["bubble"]
    lines = callouts.say_lines(c["say"])
    fs = callouts.HOOT_SAY_CAP * SHORT_H / CAP_EM
    tb, bb, tail = b["text_box"], b["body"], b["tail"]
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    longest = max(len(ln) for ln in lines)
    sx = max(longest, 6) * callouts.HOOT_EM_PER_CHAR * fs / tw
    sy = max(len(lines) * 1.15 * fs / th, sx / callouts.HOOT_BUBBLE_STRETCH)
    bub = Image.open(b["src"]).convert("RGBA").resize((max(8, round(sx)), max(8, round(sy))),
                                                      Image.LANCZOS)
    mirror = side == "left"
    if mirror:
        bub = ImageOps.mirror(bub)
    bx0, by0, bx1, by1 = body
    tip_y = by0 + 0.25 * (by1 - by0)
    tip_x = bx1 - 0.12 * (bx1 - bx0) if side == "right" else bx0 + 0.12 * (bx1 - bx0)
    tx = (1 - tail[0]) if mirror else tail[0]
    left, top = tip_x - tx * bub.size[0], tip_y - tail[1] * bub.size[1]
    # text, centred in the text box
    t_l = (1 - tb[2]) if mirror else tb[0]
    t_r = (1 - tb[0]) if mirror else tb[2]
    timg = text_image(lines, fs, "#111111", stroke_k=0.0, shadow=False)
    cx = (t_l + t_r) / 2 * bub.size[0]
    cy = (tb[1] + tb[3]) / 2 * bub.size[1]
    bub.alpha_composite(timg, (max(0, round(cx - timg.size[0] / 2)),
                               max(0, round(cy - timg.size[1] / 2))))
    x0, y0 = min(0, math.floor(left)), min(0, math.floor(top))
    x1 = max(img.size[0], math.ceil(left + bub.size[0]))
    y1 = max(img.size[1], math.ceil(top + bub.size[1]))
    out = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    out.alpha_composite(img, (-x0, -y0))
    out.alpha_composite(bub, (round(left) - x0, round(top) - y0))
    return out, (bx0 - x0, by0 - y0, bx1 - x0, by1 - y0), (-x0, -y0)


# --- layers ------------------------------------------------------------------------------------

@dataclasses.dataclass
class Layer:
    """One overlay: a PNG (or an entrance PNG sequence ending on it) at (x, y), on [t0, t1]."""
    kind: str                  # "png" (static or slide) | "seq"
    path: str                  # the PNG, or the sequence pattern
    x: int
    y: int
    w: int
    h: int
    t0: float
    t1: float
    slide: str | None = None
    sfx: str | None = None
    callout: str = ""
    blur: dict | None = None

    @property
    def box(self) -> tuple:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


def scale_at(ease: dict, t_ms: float) -> float:
    """The measured overshoot (callouts.scale_keyframes): from -> peak -> 1.0, each leg eased out."""
    f, p, pk, st = ease["from"], ease["peak"], float(ease["peak_ms"]), float(ease["settle_ms"])
    out = lambda u: 1 - (1 - min(1.0, max(0.0, u))) ** 3        # noqa: E731
    if t_ms <= pk:
        return f + (p - f) * out(t_ms / pk)
    if t_ms <= st:
        return p + (1.0 - p) * out((t_ms - pk) / max(1.0, st - pk))
    return 1.0


def entrance(img, pivot, ease: str, in_s: float, work: pathlib.Path, stem: str):
    """`img` -> (kind, path, canvas_w, canvas_h, pivot_in_canvas). Scale eases and `fade` become a
    PNG sequence on a canvas big enough for the peak scale; anything else one PNG."""
    from PIL import Image
    import callouts
    work.mkdir(parents=True, exist_ok=True)
    spec = callouts.EASING.get(ease, {})
    if "peak" in spec or ease == "fade":
        peak = float(spec.get("peak", 1.0))
        cw, ch = math.ceil(img.size[0] * peak) + 2, math.ceil(img.size[1] * peak) + 2
        pc = (pivot[0] * peak + 1, pivot[1] * peak + 1)
        total_ms = in_s * 1000.0 if in_s > 0 else float(spec.get("settle_ms", spec.get("ms", 200)))
        n = max(2, math.ceil(total_ms / 1000.0 * FPS) + 1)
        d = work / stem
        d.mkdir(parents=True, exist_ok=True)
        for k in range(n):
            t_ms = min(total_ms, k * 1000.0 / FPS)
            frame = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            if ease == "fade":
                a = img.copy()
                a.putalpha(a.getchannel("A").point(lambda v, f=t_ms / total_ms: round(v * f)))
                frame.alpha_composite(a, (round(pc[0] - pivot[0]), round(pc[1] - pivot[1])))
            else:
                s = scale_at(spec, t_ms * float(spec["settle_ms"]) / total_ms)
                sw, sh = max(1, round(img.size[0] * s)), max(1, round(img.size[1] * s))
                frame.alpha_composite(img.resize((sw, sh), Image.LANCZOS),
                                      (round(pc[0] - pivot[0] * s), round(pc[1] - pivot[1] * s)))
            frame.save(d / f"f_{k:03d}.png")
        return "seq", str(d / "f_%03d.png"), cw, ch, pc
    path = work / f"{stem}.png"
    img.save(path)
    return "png", str(path), img.size[0], img.size[1], pivot


def build_layers(calls: list, rows, dur: float, cuts, callout_s: float, work: pathlib.Path,
                 where: str, avoid_in, earth_in) -> list:
    """Compiled callouts -> Layers, in list order. `avoid_in(t0, t1)` -> caption boxes (px) on
    screen in that window; `earth_in(t0, t1)` -> Earth Studio zones (px) in it."""
    import callouts
    work.mkdir(parents=True, exist_ok=True)
    layers = []
    for k, c in enumerate(calls):
        tag = f"{where} callouts[{k}]"
        t0, t1, in_s, ease = window(c, rows, dur, cuts, callout_s, tag)
        kind = c["type"]
        stem = f"c{k:02d}"
        if c.get("out", "snap") != "snap":
            print(f"note: {tag}: out {c['out']!r} renders as snap on 16:9", flush=True)
        if kind == "hoot":
            layer = _hoot_layer(c, tag, t0, t1, in_s, ease, work, stem, avoid_in, earth_in)
        else:
            ax, ay = _anchor_xy(c, kind)
            c2 = {**c, "_work": str(work), "_stem": stem}
            img, pivot = {"sticker": sticker_image, "badge": badge_image, "text": badge_image,
                          "arrow": arrow_image, "circle": circle_image}[kind](c2)
            mode, path, cw, ch, pc = entrance(img, pivot, ease, in_s, work, stem)
            x, y = round(ax * W - pc[0]), round(ay * H - pc[1])
            edge = None
            if ease == "slide_in":
                edge = c.get("enter_from") or callouts.nearest_edge(ax, ay)
            layer = Layer(mode, path, x, y, cw, ch, t0, t1, slide=edge, callout=kind)
        if any(_hits(layer.box, z) for z in earth_in(t0, t1)):
            raise SystemExit(f"{tag}: the {kind} at {layer.box} would cover the Earth Studio "
                             f"attribution zone; move its anchor up or left, or make it smaller")
        sfx = c.get("sfx", callouts.TYPE_DEFAULTS[kind]["sfx"])
        layer.sfx = sfx or None
        layers.append(layer)
    return layers


def _anchor_xy(c: dict, kind: str) -> tuple:
    import callouts
    a = c.get("anchor")
    if a is None:
        return callouts.BADGE_ANCHOR
    if a.get("track"):
        return float(a["track"][0][1]), float(a["track"][0][2])
    return float(a["x"]), float(a["y"])


def _hits(a, b, pad: float = 0.0) -> bool:
    return a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


def _hoot_layer(c, tag, t0, t1, in_s, ease, work, stem, avoid_in, earth_in) -> Layer:
    import callouts
    hs = c.get("_hoot")
    if hs is None:
        raise SystemExit(f"{tag}: a hoot needs the pose set")
    explicit = c.get("anchor") is not None
    ax, ay = _anchor_xy(c, "hoot") if explicit else (None, None)
    img, center, body, pose, _shift = hoot_image(c, hs, ax, ay)
    bw, bh = body[2] - body[0], body[3] - body[1]
    blocked = list(avoid_in(t0, t1)) + list(earth_in(t0, t1))
    if explicit:
        cx, cy = ax * W, ay * H
    else:
        left_side = not ((c.get("point_to") or {}).get("x", 1.0) < 0.5)
        cx = HOOT_LEFT * W + bw / 2 if left_side else W - HOOT_LEFT * W - bw / 2
        cy = HOOT_BOTTOM * H - bh / 2
    x, y = round(cx - center[0]), round(cy - center[1])
    full = (x, y, x + img.size[0], y + img.size[1])
    if not explicit:
        # Up and out of the way of whatever is on screen with him.
        for _ in range(8):
            hit = [b for b in blocked if _hits(full, b, HOOT_GAP * H)]
            if not hit:
                break
            dy = full[3] - (min(b[1] for b in hit) - HOOT_GAP * H)
            y -= math.ceil(dy)
            full = (x, y, x + img.size[0], y + img.size[1])
    else:
        hit = [b for b in blocked if _hits(full, b)]
        if hit:
            raise SystemExit(f"{tag}: Hoot at {full} would cover a caption box or an Earth "
                             f"Studio zone {hit[0]}; move `anchor` (or drop it for the default)")
    pt = c.get("point_to")
    if pt is not None:
        px, py = pt["x"] * W, pt["y"] * H
        pad = callouts.HOOT_POINT_CLEAR * W
        if full[0] - pad < px < full[2] + pad and full[1] - pad < py < full[3] + pad:
            raise SystemExit(f"{tag}: Hoot at {full} would cover the point he points to "
                             f"({pt['x']:g}, {pt['y']:g}); move `anchor`")
    if full[0] < -2 or full[1] < -2 or full[2] > W + 2 or full[3] > H + 2:
        raise SystemExit(f"{tag}: Hoot at {full} runs off the 16:9 frame; move `anchor`")
    mode, path, cw, ch, pc = entrance(img, center, ease, in_s, work, stem)
    lx, ly = round(x + center[0] - pc[0]), round(y + center[1] - pc[1])
    edge = None
    if ease == "slide_in":
        edge = c.get("enter_from") or callouts.nearest_edge((x + center[0]) / W,
                                                            (y + center[1]) / H)
    blur = None
    if c.get("blur_bg"):
        import grammar
        blur = grammar.parse_blur_bg(c["blur_bg"], f"{tag} blur_bg")
        if blur is not None and blur.get("hold") is None:
            blur["hold"] = round(max(1.0 / FPS, t1 - t0), 4)
    return Layer(mode, path, lx, ly, cw, ch, t0, t1, slide=edge, callout="hoot", blur=blur)


def layer_steps(layers, stage: str, n_in: int, tag: str = "o") -> tuple:
    """(ffmpeg input args, filter steps, last stage, next input index) for `layers` over `stage`."""
    import longform
    args, steps = [], []
    for k, L in enumerate(layers):
        out = f"{tag}{k}"
        if L.kind == "seq":
            args += ["-framerate", str(FPS), "-i", L.path]
            steps.append(f"[{n_in}:v]setpts=PTS+{L.t0:.3f}/TB[{out}s]")
            steps.append(f"[{stage}][{out}s]overlay=x={L.x}:y={L.y}:eof_action=repeat:"
                         f"format=auto:enable='between(t,{L.t0:.3f},{L.t1:.3f})'[{out}]")
        elif L.slide:
            args += ["-i", L.path]
            steps.append(f"[{stage}][{n_in}:v]"
                         f"{longform.sticker_overlay(L.box, L.slide, L.t0, L.t1)}[{out}]")
        else:
            args += ["-i", L.path]
            steps.append(f"[{stage}][{n_in}:v]overlay=x={L.x}:y={L.y}:format=auto:"
                         f"enable='between(t,{L.t0:.3f},{L.t1:.3f})'[{out}]")
        stage = out
        n_in += 1
    return args, steps, stage, n_in


def blur_windows(layers, dur: float) -> list:
    """grammar Windows for every layer with `blur_bg` (the footage blurs while he is up)."""
    import grammar
    out = []
    for L in layers:
        if L.blur:
            w = grammar._blur_window(L.t0, L.blur, dur, W / SHORT_W)
            if w is not None:
                out.append(w)
    return grammar.merge_windows(out)


def verdict_windows(scene: dict, words, dur: float, where: str) -> list:
    """The scene's `fx:` spans as grammar Windows (wash or grade), checked not to overlap."""
    import grammar
    try:
        spans = grammar.parse_fx_list(scene, where)
        wins = [grammar.verdict_window(fx, words, dur, where) for fx in spans]
        grammar.check_no_overlap([(w.t0, w.t1) for w in wins], where)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    return [(fx["verdict"], w) for fx, w in zip(spans, wins)]


# --- sound ------------------------------------------------------------------------------------

#: `audio.sfx` keys the 16:9 path refuses (non-null), and why.
REFUSED_SFX = {"on_cut": "the whoosh on every cut is off (as it is for the Shorts)",
               "opening": "there is no frame-0 sting on a long-form episode",
               "cues": "payoff cues key off a Short's last scene",
               "on_move": "the 16:9 path has no camera moves (high motions are refused)",
               "src": "the legacy whoosh-at-beat-boundaries", "lead": "the legacy whoosh",
               "beats": "the legacy whoosh", "gain_db": "the legacy whoosh"}


def check_sfx_block(spec: dict) -> None:
    block = ((spec or {}).get("audio") or {}).get("sfx") if isinstance(
        (spec or {}).get("audio"), dict) else None
    if not isinstance(block, dict):
        return
    for key, why in REFUSED_SFX.items():
        if block.get(key) is not None:
            raise SystemExit(f"audio.sfx.{key} is not mixed on a 16:9 spec: {why}. Set it to "
                             f"null or drop it (events, on_tag, on_verdict, min_gap are read)")


def strip_nulls(spec: dict) -> dict:
    """The spec with `audio.sfx` keys set to null removed (make_short.audio_settings would build
    an empty Sfx out of `on_cut: null`). Returns a shallow copy when it changes anything."""
    audio = (spec or {}).get("audio")
    if not isinstance(audio, dict) or not isinstance(audio.get("sfx"), dict):
        return spec
    sfx = {k: v for k, v in audio["sfx"].items() if v is not None}
    return {**spec, "audio": {**audio, "sfx": sfx}}


def chapter_sound(opts_raw, resolve) -> dict | None:
    """`landscape.chapter_sfx` -> {src, gain_db, lead, start, end} resolved, or None."""
    raw = (opts_raw or {}).get("chapter_sfx", CHAPTER_SFX) if isinstance(opts_raw, dict) \
        else CHAPTER_SFX
    if raw is None or raw is False:
        return None
    if isinstance(raw, str):
        raw = {"src": raw}
    if not isinstance(raw, dict) or not raw.get("src"):
        raise SystemExit("landscape.chapter_sfx must be null, a src, or {src, gain_db, lead}")
    unknown = set(raw) - set(CHAPTER_SFX_KEYS)
    if unknown:
        raise SystemExit(f"unknown landscape.chapter_sfx key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(CHAPTER_SFX_KEYS)}")
    out = {**{k: v for k, v in CHAPTER_SFX.items() if k != "src"}, **raw}
    out["src"] = resolve(out["src"])
    out["gain_db"] = float(out["gain_db"])
    out["lead"] = float(out.get("lead", 0.2))
    return out


def resolve_sound(src: str, spec_path) -> str:
    import grammar
    import media
    try:
        if str(src).startswith(grammar.BUNDLE_PREFIX):
            return grammar.resolve_bundle(src)
        return str(media.resolve_src(spec_path, src))
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"sound {src}: {exc}") from None


def placements(mix, callout_rows, verdict_rows, chapter_rows, chapter_snd) -> tuple:
    """Every one-shot sound -> ([{at, role, src, gain_db, start, end}], notes). Callout rows are
    {at, role: <sfx name>}; verdict rows {at, role: verdict_good|bad}; chapter rows {at}."""
    import grammar
    gram = mix.sfx.grammar if mix is not None and mix.sfx is not None else None
    events = {e.role: e for e in (mix.sfx.events if mix is not None and mix.sfx is not None
                                  else ())}
    cand, notes, files = [], [], {}
    for row in callout_rows:
        ev = events.get(row["role"])
        tag = gram.tag if gram is not None else None
        if ev is not None:
            src, gain, a, b = ev.src, ev.gain_db, 0.0, None
        elif tag is not None:
            src, gain, a, b = tag.src, tag.gain_db, tag.start, tag.end
        else:
            notes.append(f"callout sfx {row['role']} at {row['at']:.2f}s skipped: no "
                         f"audio.sfx.events.{row['role']} and no on_tag")
            continue
        cand.append({"at": row["at"], "role": "tag", "src": src, "gain_db": gain, "start": a,
                     "end": b})
    for row in verdict_rows:
        snd = gram.sound(row["role"]) if gram is not None else None
        if snd is None:
            notes.append(f"{row['role']} at {row['at']:.2f}s is silent: no audio.sfx.on_verdict")
            continue
        cand.append({"at": row["at"], "role": row["role"], "src": snd.src,
                     "gain_db": snd.gain_db, "start": snd.start, "end": snd.end})
    if chapter_snd is not None:
        for row in chapter_rows:
            cand.append({"at": max(0.0, row["at"] - chapter_snd["lead"]), "role": "cut",
                         "src": chapter_snd["src"], "gain_db": chapter_snd["gain_db"],
                         "start": float(chapter_snd.get("start") or 0.0),
                         "end": chapter_snd.get("end")})
    gap = gram.min_gap if gram is not None else grammar.DEFAULT_MIN_GAP
    kept, dropped = grammar.thin(cand, first_speech_s=None, guard=0.0, min_gap=gap)
    notes += [f"sfx {r['role']} at {r['at']:.2f}s dropped ({r['why']})" for r in dropped]
    return kept, notes


def bus_steps(rows, runtime: float) -> tuple:
    """(input files in order, filter steps ending [bus]): one input per distinct file, split per
    use, each trimmed/gained/delayed, mixed with normalize=0 and padded to `runtime`."""
    files = []
    for r in rows:
        if r["src"] not in files:
            files.append(r["src"])
    uses = {f: [r for r in rows if r["src"] == f] for f in files}
    steps, labels = [], []
    for i, f in enumerate(files):
        n = len(uses[f])
        fmt = f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo"
        if n == 1:
            steps.append(f"{fmt}[u{i}_0]")
        else:
            steps.append(f"{fmt},asplit={n}" + "".join(f"[u{i}_{j}]" for j in range(n)))
        for j, r in enumerate(uses[f]):
            trim = ""
            if r.get("start") or r.get("end") is not None:
                trim = (f"atrim=start={float(r.get('start') or 0):g}"
                        + (f":end={float(r['end']):g}" if r.get("end") is not None else "")
                        + ",asetpts=PTS-STARTPTS,")
            delay = max(0, round(float(r["at"]) * 1000))
            lab = f"s{i}_{j}"
            # Padded per use, as make_short pads each event: an apad AFTER the amix of an
            # asplit leaves the bus at its last sound (measured: 3.3 s of a 6 s runtime).
            steps.append(f"[u{i}_{j}]{trim}volume={float(r['gain_db']):g}dB,"
                         f"adelay={delay}|{delay},atrim=0:{float(runtime):.3f},"
                         f"apad=whole_dur={float(runtime):.3f}[{lab}]")
            labels.append(lab)
    steps.append("".join(f"[{lab}]" for lab in labels)
                 + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
                 f"atrim=0:{float(runtime):.3f}[bus]")
    return files, steps


def render_bus(rows, runtime: float, out: pathlib.Path) -> pathlib.Path | None:
    """Every kept one-shot on one `runtime`-long 48 kHz stereo WAV, or None for no sounds."""
    if not rows:
        return None
    files, steps = bus_steps(rows, runtime)
    args = []
    for f in files:
        args += ["-i", str(f)]
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex",
                        ";".join(steps), "-map", "[bus]", "-c:a", "pcm_s16le", "-ar", "48000",
                        str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"sfx bus failed:\n{r.stderr[-1500:]}")
    return out
