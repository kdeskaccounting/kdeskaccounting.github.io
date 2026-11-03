"""`motion: crashzoom` -- the hand-built crash-zoom opening, as a scene motion (2026-11-03).

Ported from ParkSheet's `video/hand/crashzoom.py` and `video/hand/fingerprint-scan/
make_opening.py` (v2), which drew this opening OUTSIDE the renderer: a per-slug config of
hand-measured pixel targets, a clip written into the media folder, and a `c2_start` that had
to be re-measured after every narration change because it is the frame scene 0 cuts on. Here
the same camera is a scene motion, every number is a scene key with the old value as its
default, and the continuation frame is read off the render itself.

THE OPENING (a media scene with `motion: crashzoom` and a `crashzoom:` block)

  f 0 .. impact   (0.00-0.40 s) WIDE still -> ~4.1x crash zoom on the key object, ease-in
                  u^2.4; a radial zoom blur of up to 24 sub-frame samples over a 1.6-frame
                  shutter; the wide still cross-fades to a separate close-up inside the blur
                  (a 4x zoom cannot come from one photo).
  f impact        hard stop: a 7% camera pulse springing back, a 6-frame decaying shake, a
                  brightness flash; optional `badge`, `ring` flash, `lander` sticker landing,
                  `scan` line.
  f impact .. n   slow drift 1.00 -> 1.05 so nothing holds still.

  crashzoom:
    wide: media/photos/x-wide.png      # required; repo-relative like any src
    wide_target: [511, 1040]           # key object centre in the wide still, source px
    wide_width: 116                    # key object width in the wide still, source px
    close: media/photos/x-close.png    # required
    close_target: [507, 969]           # the same object's centre in the close-up
    close_width: 286                   # optional; else derived so the close-up sits at
    close_end: 1.6                     #   close_end x its cover scale at the impact
    zoom: 4.1                          # or land_width: <px> for the landed object width
    p0: [540, 1180]  p1: [540, 1180]   # where the object sits on frame 0 / at the impact
    impact_s: 0.40   seconds: 3.0      ease: 2.4   shutter: 1.6   max_samples: 24
    pulse: 0.07      drift: 0.05       flash: 0.28  flash_frames: 4
    shake: [[0, -34], [26, 22], [-18, -14], [10, 8], [-5, -3], [2, 1]]
    xfade: [400, 470]                  # optional; object widths (px) of the cross-fade
    badge:  {text: '36"-56"', at: [540, 1600], size: 96, bg: [40, 150, 80, 230]}
    lander: {src: media/photos/finger.png, tip: [0.163, 0.664], scale: 2.5, ...}
    ring:   {color: [120, 255, 150]}   scan: {color: [90, 255, 140]}

THE TURN (a later media scene with `motion: crashzoom` and `crashzoom: {continue: N}`)
picks up the camera of scene N on the frame scene N's part ends -- read off the encoded part,
so a narration change moves it for free -- then punches 1.22x in 3 frames (blurred) about
`punch_at` with a 3-frame shake, then drifts.

THE LOOP FRAME. A media scene with `still_of: N` shows the opening's settled last frame
(scene N's clip, no flash) as an ordinary still -- `motion: push` or `punch` on it as usual --
so the visual loop needs no exported PNG either.

Pure camera arithmetic is standard library; Pillow is imported only to draw, so this module
imports in the bare test environment. Clips are written to the build's work directory, keyed
by a hash of every input (config, continuation frame, source file sizes and mtimes), and a
re-render with nothing changed reuses them.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import pathlib
import subprocess

MOTION = "crashzoom"
W, H, FPS = 1080, 1920, 30
#: Bumped whenever the drawing changes, so a cached clip from older code is never reused.
ENGINE_VERSION = "1"
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

OPEN_DEFAULTS = {
    "close_end": 1.6, "zoom": 4.1, "p0": [540.0, 1180.0], "p1": [540.0, 1180.0],
    "impact_s": 0.40, "seconds": 3.0, "ease": 2.4, "shutter": 1.6, "max_samples": 24,
    "blur_px": 6.0, "pulse": 0.07, "pulse_decay": 1.5, "drift": 0.05,
    "shake": [[0, -34], [26, 22], [-18, -14], [10, 8], [-5, -3], [2, 1]],
    "flash": 0.28, "flash_frames": 4,
}
OPEN_KEYS = {"wide", "wide_target", "wide_width", "close", "close_target", "close_width",
             "land_width", "s0", "xfade", "badge", "lander", "ring", "scan",
             *OPEN_DEFAULTS}
TURN_DEFAULTS = {"punch": 1.22, "punch_frames": 3, "seconds": 1.5, "drift": 0.04,
                 "shake": [[14, -18], [-9, 10], [4, -4]], "shutter": 1.6, "max_samples": 24,
                 "blur_px": 6.0}
TURN_KEYS = {"continue", "punch_at", "start_frame", "turn_badge", *TURN_DEFAULTS}
LANDER_DEFAULTS = {"tip": [0.5, 0.5], "scale": 1.0, "ref_width": 472.0, "start_s": 0.10,
                   "from": [640.0, -1050.0], "ease": 1.6, "grow": 0.5}
RING_DEFAULTS = {"color": [120, 255, 150], "aspect": 0.57, "frames": 14, "ref_width": 472.0}
SCAN_DEFAULTS = {"color": [90, 255, 140], "core": [200, 255, 210], "from_frame": 1,
                 "to_frame": 19, "ref_width": 472.0}
BADGE_DEFAULTS = {"size": 120, "fg": [255, 255, 255, 255], "bg": [20, 20, 24, 215],
                  "start": 0.0, "outline_only": False, "dotted": None}


def is_crashzoom(scene: dict) -> bool:
    return (scene or {}).get("motion") == MOTION


def is_continuation(scene: dict) -> bool:
    return is_crashzoom(scene) and "continue" in ((scene or {}).get("crashzoom") or {})


def still_of(scene: dict):
    """The scene index a `still_of:` names, or None."""
    value = (scene or {}).get("still_of")
    return None if value is None else int(value)


def generated(scene: dict) -> bool:
    """True when this scene's picture is drawn here rather than read from its `src`."""
    return is_crashzoom(scene) or still_of(scene) is not None


# --- the spec ------------------------------------------------------------------------------

def _pair(value, name, where):
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError, IndexError, KeyError):
        raise ValueError(f"{where}: crashzoom.{name} must be [x, y], got {value!r}") from None
    return [x, y]


def _block(raw, known, defaults, where, what):
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: `{what}` must be a mapping, got {type(raw).__name__}")
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"{where}: unknown {what} key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(sorted(known))}")
    return {**defaults, **raw}


def _shake(value, name, where):
    if not isinstance(value, list):
        raise ValueError(f"{where}: crashzoom.{name} must be a list of [dx, dy]")
    return [_pair(step, name, where) for step in value]


def parse_open(raw, where="crashzoom") -> dict:
    """An opening block, every default filled in and every number checked. Pure."""
    cfg = _block(raw, OPEN_KEYS, OPEN_DEFAULTS, where, "crashzoom")
    for name in ("wide", "close"):
        if not str(cfg.get(name) or "").strip():
            raise ValueError(f"{where}: crashzoom needs `{name}:` (a still to crop from)")
    for name in ("wide_target", "close_target"):
        if cfg.get(name) is None:
            raise ValueError(f"{where}: crashzoom needs `{name}: [x, y]` in source px")
        cfg[name] = _pair(cfg[name], name, where)
    for name in ("p0", "p1"):
        cfg[name] = _pair(cfg[name], name, where)
    if cfg.get("wide_width") is None or float(cfg["wide_width"]) <= 0:
        raise ValueError(f"{where}: crashzoom needs a positive `wide_width` (source px)")
    cfg["wide_width"] = float(cfg["wide_width"])
    for name in ("close_width", "land_width", "s0"):
        if cfg.get(name) is not None:
            if float(cfg[name]) <= 0:
                raise ValueError(f"{where}: crashzoom.{name} must be positive")
            cfg[name] = float(cfg[name])
    if float(cfg["zoom"]) <= 1.0:
        raise ValueError(f"{where}: crashzoom.zoom must be > 1 (it is a zoom IN)")
    impact = round(float(cfg["impact_s"]) * FPS)
    frames = round(float(cfg["seconds"]) * FPS)
    if impact < 2:
        raise ValueError(f"{where}: crashzoom.impact_s {cfg['impact_s']} is under two frames")
    if frames <= impact:
        raise ValueError(f"{where}: crashzoom.seconds must run past the impact")
    cfg["impact_frame"], cfg["frames"] = impact, frames
    cfg["shake"] = _shake(cfg["shake"], "shake", where)
    if cfg.get("xfade") is not None:
        a, b = _pair(cfg["xfade"], "xfade", where)
        if not 0 < a < b:
            raise ValueError(f"{where}: crashzoom.xfade must be [a, b] with 0 < a < b")
        cfg["xfade"] = [a, b]
    if cfg.get("lander") is not None:
        lander = _block(cfg["lander"], {"src", *LANDER_DEFAULTS}, LANDER_DEFAULTS, where,
                        "crashzoom.lander")
        if not str(lander.get("src") or "").strip():
            raise ValueError(f"{where}: crashzoom.lander needs `src:` (a transparent PNG)")
        lander["tip"] = _pair(lander["tip"], "lander.tip", where)
        lander["from"] = _pair(lander["from"], "lander.from", where)
        cfg["lander"] = lander
    for name, defaults in (("ring", RING_DEFAULTS), ("scan", SCAN_DEFAULTS)):
        if cfg.get(name) is not None:
            cfg[name] = _block(cfg[name] or {}, set(defaults), defaults, where,
                               f"crashzoom.{name}")
    if cfg.get("badge") is not None:
        cfg["badge"] = parse_badge(cfg["badge"], where, "crashzoom.badge")
    return cfg


def parse_badge(raw, where, what):
    badge = _block(raw, {"text", "at", "font", *BADGE_DEFAULTS}, BADGE_DEFAULTS, where, what)
    badge["at"] = _pair(badge.get("at"), f"{what}.at", where)
    badge["text"] = str(badge.get("text") or "")
    return badge


def parse_turn(raw, where="crashzoom") -> dict:
    cfg = _block(raw, TURN_KEYS, TURN_DEFAULTS, where, "crashzoom")
    cfg["continue"] = int(cfg["continue"])
    if float(cfg["punch"]) <= 0:
        raise ValueError(f"{where}: crashzoom.punch must be positive")
    if int(cfg["punch_frames"]) < 1:
        raise ValueError(f"{where}: crashzoom.punch_frames must be at least 1")
    cfg["frames"] = round(float(cfg["seconds"]) * FPS)
    if cfg["frames"] <= int(cfg["punch_frames"]):
        raise ValueError(f"{where}: crashzoom.seconds must run past the punch")
    if cfg.get("punch_at") is not None:
        cfg["punch_at"] = _pair(cfg["punch_at"], "punch_at", where)
    cfg["shake"] = _shake(cfg["shake"], "shake", where)
    if cfg.get("turn_badge") is not None:
        cfg["turn_badge"] = parse_badge(cfg["turn_badge"], where, "crashzoom.turn_badge")
    return cfg


def validate_scene(scene: dict, index: int, spec: dict, resolve) -> None:
    """The preflight for a generated scene. `resolve(src) -> path` raises on a missing file.

    Raises ValueError naming the problem; media.validate_spec prefixes the scene.
    """
    scenes = spec.get("scenes") or []

    def opening_at(target, why):
        if not 0 <= target < len(scenes):
            raise ValueError(f"{why} {target}, which is not a scene in this spec")
        other = scenes[target] or {}
        if not is_crashzoom(other) or is_continuation(other):
            raise ValueError(f"{why} {target}, which is not a crash-zoom OPENING "
                             f"(`motion: crashzoom` without `continue:`)")
        return other

    if is_crashzoom(scene):
        if scene.get("beats"):
            raise ValueError("a crashzoom scene carries `beats:`; its picture is the camera, "
                             "and a beat would cut away from it")
        block = scene.get("crashzoom")
        if block is None:
            raise ValueError("`motion: crashzoom` needs a `crashzoom:` block")
        if "continue" in (block or {}):
            cfg = parse_turn(block)
            if cfg["continue"] >= index:
                raise ValueError(f"crashzoom.continue: {cfg['continue']} must name an EARLIER "
                                 f"scene (this is scene {index})")
            opening_at(cfg["continue"], "crashzoom.continue names scene")
            return
        cfg = parse_open(block)
        for name in ("wide", "close"):
            resolve(cfg[name])
        if cfg.get("lander"):
            resolve(cfg["lander"]["src"])
        return
    target = still_of(scene)
    if target is not None:
        if (scene.get("motion") or "kenburns") == MOTION:
            raise ValueError("a `still_of:` scene is a still; give it a still motion")
        opening_at(target, "still_of names scene")


# --- the camera (pure) ----------------------------------------------------------------------

def lerp(a, b, k):
    return a + (b - a) * k


def cover(size) -> float:
    return max(W / size[0], H / size[1])


class Camera:
    """The virtual camera, defined by the key object's on-screen width `rs` and centre `p`.

    Sizes, not images: the arithmetic is the same whether or not Pillow is installed, which
    is how the tests check it.
    """

    def __init__(self, cfg: dict, wide_size, close_size):
        self.cfg = cfg
        self.wide_size, self.close_size = tuple(wide_size), tuple(close_size)
        s0 = max(cfg.get("s0") or cover(wide_size), cover(wide_size))
        tx, ty = cfg["wide_target"]
        p0 = cfg["p0"]
        left = min(max(0.0, tx - p0[0] / s0), wide_size[0] - W / s0)
        top = min(max(0.0, ty - p0[1] / s0), wide_size[1] - H / s0)
        self.P0 = ((tx - left) * s0, (ty - top) * s0)
        self.RS0 = cfg["wide_width"] * s0
        self.RS1 = cfg.get("land_width") or self.RS0 * float(cfg["zoom"])
        self.close_rw = cfg.get("close_width") or (
            self.RS1 / (float(cfg["close_end"]) * cover(close_size)))
        if cfg.get("xfade"):
            self.XFADE = tuple(cfg["xfade"])
        else:
            close_end = self.RS1 / (self.close_rw * cover(close_size))
            x0 = max(0.62, 1.04 / close_end) * self.RS1
            self.XFADE = (x0, min(0.88 * self.RS1, x0 + 0.12 * self.RS1))
        self.impact = int(cfg["impact_frame"])
        self.n1 = int(cfg["frames"])

    def camera1(self, t: float):
        c = self.cfg
        if t < self.impact:
            e = max(0.0, t / self.impact) ** float(c["ease"])
            rs = self.RS0 * (self.RS1 / self.RS0) ** e
            p = (lerp(self.P0[0], c["p1"][0], e), lerp(self.P0[1], c["p1"][1], e))
        else:
            d = t - self.impact
            rs = (self.RS1 * (1 + float(c["drift"]) * d / (self.n1 - self.impact))
                  * (1 + float(c["pulse"]) * math.exp(-d / float(c["pulse_decay"]))))
            p = tuple(c["p1"])
        return rs, p

    def camera2(self, turn: dict, start: int, g: float):
        rs, p = self.camera1(start + g)
        pf, n2 = int(turn["punch_frames"]), int(turn["frames"])
        k = 1 + (float(turn["punch"]) - 1) * (1 - (1 - min(1.0, max(0.0, g) / pf)) ** 3)
        k *= 1 + float(turn["drift"]) * max(0.0, g - pf) / (n2 - pf)
        pa = turn.get("punch_at") or self.cfg["p1"]
        p = (pa[0] + (p[0] - pa[0]) * k, pa[1] + (p[1] - pa[1]) * k)
        return rs * k, p

    @staticmethod
    def crop_box(size, target, rw, rs, p):
        """(left, top, right, bottom) of the source crop for object width `rs` at `p`."""
        s = max(rs / rw, cover(size))
        vw, vh = W / s, H / s
        left = max(0.0, min(size[0] - vw, target[0] - p[0] / s))
        top = max(0.0, min(size[1] - vh, target[1] - p[1] / s))
        return (left, top, left + vw, top + vh), s

    @staticmethod
    def samples(rs_at, t: float, t_stop: float, shutter: float, max_samples: int,
                blur_px: float) -> list:
        """The sub-frame times a blurred frame averages; [t] when the camera barely moves."""
        a, b = t - shutter / 2, min(t + shutter / 2, t_stop)
        disp = abs(math.log(rs_at(b) / rs_at(max(a, 0.0)))) * 1100
        k = max(1, min(int(max_samples), math.ceil(disp / blur_px)))
        if k == 1:
            return [t]
        return [max(0.0, lerp(a, b, (i + 0.5) / k)) for i in range(k)]


def continuation_frame(part_seconds: float) -> int:
    """The clip-1 frame the next scene picks up on: the frames the opening part showed."""
    return int(round(float(part_seconds) * FPS))


# --- drawing (Pillow) ------------------------------------------------------------------------

class Painter:
    """Pillow half: the stills, the layers, the composites. One per opening."""

    def __init__(self, cfg: dict, resolve):
        from PIL import Image
        self.cfg = cfg
        self.wide = Image.open(resolve(cfg["wide"])).convert("RGB")
        self.close = Image.open(resolve(cfg["close"])).convert("RGB")
        self.cam = Camera(cfg, self.wide.size, self.close.size)
        lander = cfg.get("lander")
        self.fg = Image.open(resolve(lander["src"])).convert("RGBA") if lander else None

    def _crop(self, img, target, rw, rs, p, fast):
        from PIL import Image, ImageFilter
        box, s = Camera.crop_box(img.size, target, rw, rs, p)
        out = img.resize((W, H), Image.BILINEAR if fast else Image.LANCZOS, box=box)
        if not fast and s > 1.6:
            out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
        return out

    def background(self, rs, p, fast):
        from PIL import Image
        c, cam = self.cfg, self.cam
        a, b = cam.XFADE
        wide = lambda: self._crop(self.wide, c["wide_target"], c["wide_width"], rs, p, fast)
        close = lambda: self._crop(self.close, c["close_target"], cam.close_rw, rs, p, fast)
        if rs <= a:
            return wide()
        if rs >= b:
            return close()
        return Image.blend(wide(), close(), (rs - a) / (b - a))

    def draw_lander(self, frame, rs, p, t, fast=False):
        from PIL import Image
        lc = self.cfg.get("lander")
        if not lc:
            return
        impact = self.cam.impact
        k_scale = float(lc["scale"]) / float(lc["ref_width"])
        start = round(float(lc["start_s"]) * FPS)
        if t < start:
            return
        if t < impact:
            q = ((t - start) / (impact - start)) ** float(lc["ease"])
            scale = k_scale * self.cam.RS1 * (1 + float(lc["grow"]) - float(lc["grow"]) * q)
            tx = p[0] + (1 - q) * lc["from"][0]
            ty = p[1] + (1 - q) * lc["from"][1]
        else:
            scale = k_scale * rs
            tx, ty = p
        f = self.fg.resize((max(1, int(self.fg.width * scale)), max(1, int(self.fg.height * scale))),
                           Image.BILINEAR if fast else Image.LANCZOS)
        fx, fy = tx - lc["tip"][0] * f.width, ty - lc["tip"][1] * f.height
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(f, (int(fx), int(fy)), f)
        frame.alpha_composite(layer)

    def ring_flash(self, frame, rs, p, d):
        from PIL import Image, ImageDraw, ImageFilter
        rc = self.cfg["ring"]
        k = max(0.0, 1 - d / float(rc["frames"]))
        u = rs / float(rc["ref_width"])
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lw = int((14 + 30 * k) * u)
        rx, ry = 0.50 * rs + lw / 2, 0.50 * rs * float(rc["aspect"]) + lw / 2
        cx, cy = p
        r, g, b = (int(v) for v in rc["color"][:3])
        ImageDraw.Draw(glow).ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                                     outline=(r, g, b, int(255 * (0.25 + 0.75 * k))), width=lw)
        frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur((6 + 10 * k) * u)))

    def scan_line(self, frame, rs, p, d):
        from PIL import Image, ImageDraw, ImageFilter
        sc = self.cfg["scan"]
        u = rs / float(sc["ref_width"])
        span = float(sc["to_frame"]) - float(sc["from_frame"])
        q = (d - float(sc["from_frame"])) / span
        cx, cy = p
        y = cy + (-170 + 260 * q) * u
        hw = 330 * u
        scan = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        r, g, b = (int(v) for v in sc["color"][:3])
        ImageDraw.Draw(scan).rectangle([cx - hw, y - 16 * u, cx + hw, y + 16 * u],
                                       fill=(r, g, b, 120))
        scan = scan.filter(ImageFilter.GaussianBlur(10 * u))
        r, g, b = (int(v) for v in sc["core"][:3])
        ImageDraw.Draw(scan).rectangle([cx - hw + 10, y - 4 * u, cx + hw - 10, y + 4 * u],
                                       fill=(r, g, b, 255))
        frame.alpha_composite(scan)

    def composite1(self, t, fast=False):
        from PIL import ImageEnhance
        c, cam = self.cfg, self.cam
        rs, p = cam.camera1(t)
        d = t - cam.impact
        if 0 <= d < len(c["shake"]):
            dx, dy = c["shake"][int(d)]
            p = (p[0] + dx, p[1] + dy)
        frame = self.background(rs, p, fast).convert("RGBA")
        if d >= 0 and c.get("ring"):
            self.ring_flash(frame, rs, p, d)
        if d >= 0 and c.get("badge"):
            draw_badge(frame, c["badge"], d)
        self.draw_lander(frame, rs, p, t, fast)
        if c.get("scan") and c["scan"]["from_frame"] <= d <= c["scan"]["to_frame"]:
            self.scan_line(frame, rs, p, d)
        out = frame.convert("RGB")
        nf = int(c["flash_frames"])
        if 0 <= d < nf:
            out = ImageEnhance.Brightness(out).enhance(1 + float(c["flash"]) * (1 - d / nf))
        return out

    def composite2(self, turn, start, g, fast=False):
        c, cam = self.cfg, self.cam
        rs, p = cam.camera2(turn, start, g)
        d = g - int(turn["punch_frames"])
        if 0 <= d < len(turn["shake"]):
            dx, dy = turn["shake"][int(d)]
            p = (p[0] + dx, p[1] + dy)
        frame = self.background(rs, p, fast).convert("RGBA")
        if c.get("badge"):
            draw_badge(frame, c["badge"], start + g - cam.impact)
        if turn.get("turn_badge"):
            draw_badge(frame, turn["turn_badge"], g)
        if c.get("lander"):
            self.draw_lander(frame, rs, p, cam.n1 + 100, fast)
        return frame.convert("RGB")

    def blurred(self, fn, t, t_stop, rs_at, shutter, max_samples, blur_px):
        from PIL import Image
        ts = Camera.samples(rs_at, t, t_stop, shutter, max_samples, blur_px)
        if len(ts) == 1:
            return fn(t)
        img = fn(ts[0], True)
        for i, ti in enumerate(ts[1:], start=2):
            img = Image.blend(img, fn(ti, True), 1 / i)
        return img

    def open_frames(self):
        c, cam = self.cfg, self.cam
        rs1 = lambda t: cam.camera1(t)[0]
        for i in range(cam.n1):
            if i < cam.impact:
                yield self.blurred(self.composite1, i, cam.impact, rs1, float(c["shutter"]),
                                   int(c["max_samples"]), float(c["blur_px"]))
            else:
                yield self.composite1(i)

    def turn_frames(self, turn, start):
        cam, pf = self.cam, int(turn["punch_frames"])
        rs2 = lambda g: cam.camera2(turn, start, g)[0]
        fn = lambda g, fast=False: self.composite2(turn, start, g, fast)
        for g in range(int(turn["frames"])):
            if g < pf:
                yield self.blurred(fn, g, pf, rs2, float(turn["shutter"]),
                                   int(turn["max_samples"]), float(turn["blur_px"]))
            else:
                yield fn(g)


def pop_scale(d: float) -> float:
    """0 -> 1.15 -> 1.0 over ~5 frames after the impact."""
    if d < 0:
        return 0.0
    if d < 3:
        return 1.15 * (d + 1) / 3
    return 1.0 + 0.15 * math.exp(-(d - 3) / 1.5)


def draw_badge(frame, badge: dict, d: float) -> None:
    """A self-drawn text badge popping in `badge.start` frames after the impact."""
    from PIL import Image, ImageDraw, ImageFont
    k = pop_scale(d - float(badge["start"]))
    if k <= 0:
        return
    size, at = float(badge["size"]), badge["at"]
    fg, bg = tuple(int(v) for v in badge["fg"]), tuple(int(v) for v in badge["bg"])
    f = ImageFont.truetype(badge.get("font") or FONT, max(8, int(size * k)))
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    if badge.get("dotted"):
        bw, bh = int(badge["dotted"][0] * k), int(badge["dotted"][1] * k)
        x0, y0 = at[0] - bw / 2, at[1] - bh / 2
        dash = 26
        for x in range(int(x0), int(x0 + bw), dash * 2):
            dr.line([(x, y0), (min(x + dash, x0 + bw), y0)], fill=fg, width=9)
            dr.line([(x, y0 + bh), (min(x + dash, x0 + bw), y0 + bh)], fill=fg, width=9)
        for y in range(int(y0), int(y0 + bh), dash * 2):
            dr.line([(x0, y), (x0, min(y + dash, y0 + bh))], fill=fg, width=9)
            dr.line([(x0 + bw, y), (x0 + bw, min(y + dash, y0 + bh))], fill=fg, width=9)
    text = badge["text"]
    if text:
        box = dr.textbbox((0, 0), text, font=f)
        tw, th = box[2] - box[0], box[3] - box[1]
        x, y = at[0] - tw / 2 - box[0], at[1] - th / 2 - box[1]
        if not badge.get("outline_only"):
            pad = int(0.28 * size * k)
            dr.rounded_rectangle([at[0] - tw / 2 - pad, at[1] - th / 2 - pad,
                                  at[0] + tw / 2 + pad, at[1] + th / 2 + pad],
                                 radius=pad, fill=bg)
        dr.text((x, y), text, font=f, fill=fg, stroke_width=max(2, int(size * k / 14)),
                stroke_fill=(0, 0, 0, 255))
    frame.alpha_composite(layer)


# --- encoding and the clip cache -----------------------------------------------------------

def encode(path: pathlib.Path, frames, crf: int = 14):
    """Raw RGB frames -> libx264, exactly as the hand openers did (slow, crf 14)."""
    path = pathlib.Path(path)
    tmp = path.with_name(path.stem + ".part.mp4")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
         "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)],
        stdin=subprocess.PIPE)
    last = None
    try:
        for img in frames:
            proc.stdin.write(img.tobytes())
            last = img
    finally:
        proc.stdin.close()
    if proc.wait():
        raise SystemExit(f"crashzoom: ffmpeg failed writing {path}")
    os.replace(tmp, path)
    return last


def clip_key(cfg: dict, resolve, extra=None) -> str:
    """A hash of everything the clip depends on: config, sources' size+mtime, code version."""
    files = [cfg["wide"], cfg["close"]] + ([cfg["lander"]["src"]] if cfg.get("lander") else [])
    stamps = []
    for src in files:
        path = pathlib.Path(resolve(src))
        st = path.stat()
        stamps.append([str(path), st.st_size, int(st.st_mtime)])
    blob = json.dumps({"v": ENGINE_VERSION, "cfg": cfg, "files": stamps, "extra": extra},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclasses.dataclass
class Opening:
    """The rendered opening of one scene: its clip, its settled loop frame, its painter."""
    clip: pathlib.Path
    last: pathlib.Path
    cfg: dict
    resolve: object
    _painter: object = None

    def painter(self):
        if self._painter is None:
            self._painter = Painter(self.cfg, self.resolve)
        return self._painter


def render_opening(scene: dict, work: pathlib.Path, resolve) -> Opening:
    """Draw (or reuse) the opening clip and its loop frame under `work/crashzoom/`."""
    cfg = parse_open(scene["crashzoom"])
    key = clip_key(cfg, resolve)
    out_dir = pathlib.Path(work) / "crashzoom"
    out_dir.mkdir(parents=True, exist_ok=True)
    clip, last = out_dir / f"open-{key}.mp4", out_dir / f"open-{key}-last.png"
    opening = Opening(clip=clip, last=last, cfg=cfg, resolve=resolve)
    if clip.exists() and last.exists():
        print(f"crashzoom: reusing {clip.name}", flush=True)
        return opening
    cam = opening.painter().cam
    print(f"crashzoom: object {cam.RS0:.0f}px -> {cam.RS1:.0f}px "
          f"({cam.RS1 / cam.RS0:.2f}x) in {cam.impact} frames, xfade "
          f"{cam.XFADE[0]:.0f}-{cam.XFADE[1]:.0f}px, {cam.n1} frames", flush=True)
    frame = encode(clip, opening.painter().open_frames())
    frame.save(last)
    return opening


def render_turn(scene: dict, opening: Opening, start_frame: int, work: pathlib.Path) -> pathlib.Path:
    """Draw (or reuse) a continuation clip picking up `opening` on `start_frame`."""
    turn = parse_turn(scene["crashzoom"])
    start = int(turn["start_frame"]) if turn.get("start_frame") is not None else int(start_frame)
    key = clip_key(opening.cfg, opening.resolve, {"turn": turn, "start": start})
    clip = pathlib.Path(work) / "crashzoom" / f"turn-{key}.mp4"
    if clip.exists():
        print(f"crashzoom: reusing {clip.name}", flush=True)
        return clip
    print(f"crashzoom: turn picks up on frame {start}, punch {turn['punch']}x in "
          f"{turn['punch_frames']} frames", flush=True)
    encode(clip, opening.painter().turn_frames(turn, start))
    return clip
