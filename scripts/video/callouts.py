"""Callouts: subject-anchored overlay graphics with measured easing (ParkSheet PoC v5, 2026-11-04).

The defaults are the measurements in the ParkSheet grammar study (`shmm_grammar_study/SPEC.md`,
three reference Shorts measured frame by frame). The SPEC's defaults ARE the API: a spec names a
type and a word, and gets the measured size, curve, hold and sound unless it says otherwise.

A `kind: media` scene may carry a `callouts:` list. Absent, nothing in the render changes.

    callouts:
    - type: badge                       # sticker | badge | arrow | circle | text
      text: "456 FT"                    # badge / text
      when: {word: "456"}               # the noun it pictures (a word reference, or seconds)
      anchor: {x: 0.62, y: 0.20}        # where it lands, fractions of the 1080x1920 frame
      # anchor: {x: 0.5, y: 0.3, track: [[0.0, 0.5, 0.3], [0.6, 0.38, 0.28]]}
      #   subject-tracked: [seconds after entry, x, y] keyframes, linear between them
      size: 0.044                       # per type, see TYPES
      ease: overshoot                   # overshoot | pop | slide_in | fade | none | an EASING name
      in_ms: 300                        # entrance length (default: the curve's own)
      hold: next_cut                    # next_cut | scene | <milliseconds after the entrance>
      out: snap                         # snap | slide_out | fade
      offset_ms: 80                     # after the word's onset (SPEC: overlays land 0-150 ms after)
      sfx: ding                         # pop | chime | hit | whoosh | ding | null (silent)

Per type (src / direction / enter_from / color / tilt are type-specific):

  sticker  {src: PNG cut-out, size: fraction of frame WIDTH (0.55), enter_from: bottom|left|right
            (default: the nearest frame edge), tilt: degrees}. Slides in, ease-out cubic, 300 ms.
            No outline, no drop shadow, no background blur (SPEC rule 3).
  badge    {text, size: cap height as a fraction of frame HEIGHT (0.044), color}. White heavy
            rounded type, dark outline and soft shadow, no plate. 0.60 -> 1.15 -> 1.0 in 300 ms.
            Default anchor is the SPEC's list-number corner (0.185, 0.12).
  arrow    {size: length as a fraction of frame WIDTH (0.15), direction: down_left (default) |
            down_right | down | left | right | up_left | up_right | up}. Flat yellow with a dark
            outline; the TIP sits on the anchor and it scales out of the tip, 0.18 -> 1.10 -> 1.0
            in 167 ms. Holds 1.2 s by default (SPEC 1.0-1.4 s).
  circle   {size: diameter as a fraction of frame WIDTH (0.30)}. A ring on the subject, same curve
            as the arrow. Not in the SPEC (no reference used one); same palette as the arrow.
  text     {text, size: cap height fraction of HEIGHT (0.06), color (default #E5202A)}. A stamp
            word: 0.90 -> 1.03 -> 1.0 in 100 ms (the SPEC's red X stamp curve).

`compile_callouts()` turns a scene's list into illustrate.py elements (`type: callout`) once the
scene's words and picture cuts are known; `callout_html()` is the element's frame-exact HTML,
built on illustrate's paused-animation `seek()` mechanism. Pure: standard library only.
"""
from __future__ import annotations

import html as _html
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
#: The heavy rounded sans of the SPEC ("Fredoka/Nunito-Black-like"): Nunito, SIL OFL 1.1
#: (fonts/OFL-Nunito.txt), the variable file from github.com/google/fonts, drawn at weight 900.
ROUNDED_FONT = HERE / "fonts" / "Nunito-Variable.ttf"
ROUNDED_FAMILY = "Nunito Bundled"

W, H = 1080, 1920

#: The named easing table (SPEC section 6). `from`/`peak` are scale factors relative to the
#: final size; `peak_ms`/`settle_ms` are when the peak and the rest are reached.
EASING = {
    "pop_badge": {"from": 0.60, "peak": 1.15, "peak_ms": 200, "settle_ms": 300},
    "pop_arrow": {"from": 0.18, "peak": 1.10, "peak_ms": 133, "settle_ms": 167},
    "pop_caption": {"from": 0.94, "peak": 1.05, "peak_ms": 80, "settle_ms": 150},
    "pop_stamp": {"from": 0.90, "peak": 1.03, "peak_ms": 67, "settle_ms": 100},
    "slide_in": {"curve": "ease_out_cubic", "ms": 300},
    "fade": {"ms": 200},
}
EASE_OUT_CUBIC = "cubic-bezier(0.33,1,0.68,1)"
EASE_IN_CUBIC = "cubic-bezier(0.32,0,0.67,0)"

TYPES = ("sticker", "badge", "arrow", "circle", "text")
#: Per-type defaults. `size` units differ per type (see the module docstring).
TYPE_DEFAULTS = {
    "sticker": {"ease": "slide_in", "size": 0.55, "hold": "next_cut", "sfx": "whoosh"},
    "badge": {"ease": "pop_badge", "size": 0.044, "hold": "next_cut", "sfx": "ding"},
    "arrow": {"ease": "pop_arrow", "size": 0.15, "hold": 1200, "sfx": "ding"},
    "circle": {"ease": "pop_arrow", "size": 0.30, "hold": 1200, "sfx": "pop"},
    "text": {"ease": "pop_stamp", "size": 0.06, "hold": "next_cut", "sfx": "pop"},
}
#: `ease: overshoot` means the type's own measured overshoot curve; `pop` the gentle stamp.
OVERSHOOT = {"sticker": "pop_badge", "badge": "pop_badge", "arrow": "pop_arrow",
             "circle": "pop_arrow", "text": "pop_badge"}
EASE_NAMES = ("overshoot", "pop", "slide_in", "fade", "none", *EASING)
HOLDS = ("next_cut", "scene")
OUTS = ("snap", "slide_out", "fade")
EDGES = ("bottom", "left", "right", "top")
DIRECTIONS = {"right": 0, "down_right": 45, "down": 90, "down_left": 135, "left": 180,
              "up_left": 225, "up": 270, "up_right": 315}
SFX = ("pop", "chime", "hit", "whoosh", "ding")
DEFAULT_OFFSET_MS = 80.0
DEFAULT_OUT_MS = 200.0
BADGE_ANCHOR = (0.185, 0.12)
ARROW_FILL = "#FFC800"
INK = "#111111"
STAMP_RED = "#E5202A"
#: Nunito's cap height is ~0.705 em; a `size` given as cap height converts to font-size by it.
CAP_EM = 0.705
KEYS = ("type", "text", "src", "when", "anchor", "size", "ease", "in_ms", "hold", "out",
        "out_ms", "offset_ms", "sfx", "enter_from", "direction", "color", "tilt")


class CalloutError(ValueError):
    pass


def _num(value, name, where, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalloutError(f"{where}: `{name}` must be a number, got {value!r}")
    if not lo <= float(value) <= hi:
        raise CalloutError(f"{where}: `{name}: {value}` is outside [{lo:g}, {hi:g}]")
    return float(value)


def _is_wordref(value) -> bool:
    return isinstance(value, dict) and "word" in value


def _anchor(raw, where, kind):
    """(x, y, track) with track = [(dt, x, y), ...] or None."""
    if raw is None:
        if kind == "badge":
            return BADGE_ANCHOR[0], BADGE_ANCHOR[1], None
        raise CalloutError(f"{where}: a {kind} needs `anchor: {{x, y}}` (fractions of the frame)")
    if not isinstance(raw, dict):
        raise CalloutError(f"{where}: `anchor` must be a mapping {{x, y, track?}}, got {raw!r}")
    unknown = set(raw) - {"x", "y", "track"}
    if unknown:
        raise CalloutError(f"{where}: unknown anchor key(s) {', '.join(sorted(unknown))}")
    track = raw.get("track")
    if track is not None:
        if not isinstance(track, list) or len(track) < 2:
            raise CalloutError(f"{where}: `anchor.track` needs two or more [dt, x, y] points")
        points = []
        for i, point in enumerate(track):
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                raise CalloutError(f"{where}: anchor.track[{i}] must be [dt, x, y]")
            dt = _num(point[0], f"track[{i}].dt", where, 0.0, 60.0)
            x = _num(point[1], f"track[{i}].x", where, -0.2, 1.2)
            y = _num(point[2], f"track[{i}].y", where, -0.2, 1.2)
            if points and dt <= points[-1][0]:
                raise CalloutError(f"{where}: anchor.track times must increase")
            points.append((dt, x, y))
        if points[0][0] != 0.0:
            raise CalloutError(f"{where}: anchor.track starts at dt 0 (the entry)")
        return points[0][1], points[0][2], points
    x = _num(raw.get("x"), "anchor.x", where, -0.2, 1.2)
    y = _num(raw.get("y"), "anchor.y", where, -0.2, 1.2)
    return x, y, None


def ease_of(name: str, kind: str) -> str:
    """A spec `ease:` -> the EASING table name it means for this type ("none" stays "none")."""
    if name == "overshoot":
        return OVERSHOOT[kind]
    if name == "pop":
        return "pop_stamp"
    return name


def check(raw_list, where: str = "callouts") -> list:
    """Validate a scene's UNRESOLVED `callouts:` list. Returns it; raises CalloutError."""
    if raw_list is None:
        return []
    if not isinstance(raw_list, list) or not raw_list:
        raise CalloutError(f"{where}: `callouts:` must be a non-empty list")
    for i, c in enumerate(raw_list):
        tag = f"{where}[{i}]"
        if not isinstance(c, dict):
            raise CalloutError(f"{tag}: a callout is a mapping, got {c!r}")
        unknown = set(c) - set(KEYS)
        if unknown:
            raise CalloutError(f"{tag}: unknown key(s) {', '.join(sorted(unknown))}; "
                               f"known: {', '.join(KEYS)}")
        kind = c.get("type")
        if kind not in TYPES:
            raise CalloutError(f"{tag}: `type` must be one of {', '.join(TYPES)}, got {kind!r}")
        if kind in ("badge", "text") and not (isinstance(c.get("text"), str) and c["text"]):
            raise CalloutError(f"{tag}: a {kind} needs `text`")
        if kind == "sticker" and not (isinstance(c.get("src"), str) and c["src"].strip()):
            raise CalloutError(f"{tag}: a sticker needs `src` (a transparent PNG cut-out)")
        when = c.get("when")
        if when is None:
            raise CalloutError(f"{tag}: needs `when:` -- the word it pictures, or seconds")
        if not _is_wordref(when):
            _num(when, "when", tag, 0.0, 600.0)
        _anchor(c.get("anchor"), tag, kind)
        size = c.get("size", TYPE_DEFAULTS[kind]["size"])
        _num(size, "size", tag, 0.005, 1.2)
        ease = c.get("ease", TYPE_DEFAULTS[kind]["ease"])
        if ease not in EASE_NAMES:
            raise CalloutError(f"{tag}: `ease` must be one of {', '.join(EASE_NAMES)}")
        if "in_ms" in c:
            _num(c["in_ms"], "in_ms", tag, 1.0, 2000.0)
        hold = c.get("hold", TYPE_DEFAULTS[kind]["hold"])
        if hold not in HOLDS:
            _num(hold, "hold", tag, 1.0, 60000.0)
        if c.get("out", "snap") not in OUTS:
            raise CalloutError(f"{tag}: `out` must be one of {', '.join(OUTS)}")
        if "out_ms" in c:
            _num(c["out_ms"], "out_ms", tag, 1.0, 2000.0)
        if "offset_ms" in c:
            _num(c["offset_ms"], "offset_ms", tag, -1000.0, 1000.0)
        sfx = c.get("sfx", TYPE_DEFAULTS[kind]["sfx"])
        if sfx is not None and sfx not in SFX:
            raise CalloutError(f"{tag}: `sfx` must be one of {', '.join(SFX)} or null")
        if "enter_from" in c and c["enter_from"] not in EDGES:
            raise CalloutError(f"{tag}: `enter_from` must be one of {', '.join(EDGES)}")
        if "direction" in c and c["direction"] not in DIRECTIONS:
            raise CalloutError(f"{tag}: `direction` must be one of {', '.join(DIRECTIONS)}")
        if "color" in c and not (isinstance(c["color"], str) and c["color"].startswith("#")
                                 and len(c["color"]) in (4, 7)):
            raise CalloutError(f"{tag}: `color` must be a #rgb or #rrggbb hex colour")
        if "tilt" in c:
            _num(c["tilt"], "tilt", tag, -45.0, 45.0)
    return raw_list


def nearest_edge(x: float, y: float) -> str:
    """The SPEC's sticker rule: enter from the nearest frame edge (bottom rise or side peek)."""
    return min((("bottom", 1.0 - y), ("left", x), ("right", 1.0 - x)), key=lambda kv: kv[1])[0]


def compile_callouts(raw_list, resolve_time, local_cuts, dur: float, where="callouts") -> list:
    """A scene's `callouts:` -> illustrate elements (`type: callout`), times resolved.

    `resolve_time(value) -> seconds` resolves a word reference against the scene's own words
    (make_short passes illustrate.resolve_time bound to the scene's rows). `local_cuts` are the
    scene's picture cuts (beat boundaries), scene-local seconds; `dur` is the scene's length.
    """
    check(raw_list, where)
    cuts = sorted(float(t) for t in (local_cuts or ()))
    out = []
    for i, c in enumerate(raw_list or ()):
        tag = f"{where}[{i}]"
        kind = c["type"]
        d = TYPE_DEFAULTS[kind]
        x, y, track = _anchor(c.get("anchor"), tag, kind)
        offset = float(c.get("offset_ms", DEFAULT_OFFSET_MS)) / 1000.0
        t0 = max(0.0, float(resolve_time(c["when"])) + offset)
        if t0 >= float(dur):
            raise CalloutError(f"{tag}: enters at {t0:.3f}s, after its scene ends ({dur:.3f}s)")
        ease = ease_of(c.get("ease", d["ease"]), kind)
        base_ms = (EASING[ease].get("settle_ms") or EASING[ease].get("ms")) if ease in EASING else 0
        in_ms = float(c.get("in_ms", base_ms or 0.0))
        hold = c.get("hold", d["hold"])
        if hold == "next_cut":
            t1 = next((t for t in cuts if t > t0 + 1e-3), None)
        elif hold == "scene":
            t1 = None
        else:
            t1 = t0 + in_ms / 1000.0 + float(hold) / 1000.0
        if t1 is not None and t1 >= float(dur) - 1e-3:
            t1 = None          # the part's own end is the cut
        el = {"type": "callout", "callout": kind, "at": [x, y], "size": float(c.get("size", d["size"])),
              "ease": ease, "in_ms": in_ms, "enter": {"t": round(t0, 4), "how": "callout"},
              "out": c.get("out", "snap"), "out_ms": float(c.get("out_ms", DEFAULT_OUT_MS)),
              "sticker": False}
        if track:
            el["track"] = [[round(dt, 4), px, py] for dt, px, py in track]
        if t1 is not None:
            el["exit"] = {"t": round(t1, 4)}
        sfx = c.get("sfx", d["sfx"])
        if sfx:
            el["sfx"] = sfx
        for key in ("text", "src", "direction", "color", "tilt"):
            if key in c:
                el[key] = c[key]
        if kind == "sticker":
            el["enter_from"] = c.get("enter_from") or nearest_edge(x, y)
        out.append(el)
    return out


# --- HTML -------------------------------------------------------------------------------------

def font_face_css() -> str:
    return (f"@font-face{{font-family:'{ROUNDED_FAMILY}';font-weight:200 1000;"
            f"src:url('{ROUNDED_FONT.as_uri()}') format('truetype')}}\n")


def scale_keyframes(name: str, ease: dict, fade_in: bool = True) -> str:
    """@keyframes for a measured overshoot: from -> peak -> 1.0, each leg eased out.

    The 0% keyframe is invisible and 0.01% is not, so with `fill-mode: both` the element is
    hidden before its entry and appears AT the `from` scale (no fade), as measured."""
    p = 100.0 * float(ease["peak_ms"]) / float(ease["settle_ms"])
    tf = f"animation-timing-function:{EASE_OUT_CUBIC}"
    return (f"@keyframes {name}{{0%{{opacity:0;transform:scale({ease['from']})}}"
            f"0.01%{{opacity:1;transform:scale({ease['from']});{tf}}}"
            f"{p:.3f}%{{opacity:1;transform:scale({ease['peak']});{tf}}}"
            f"100%{{opacity:1;transform:scale(1)}}}}")


def slide_keyframes(name: str, dx: float, dy: float) -> str:
    return (f"@keyframes {name}{{0%{{opacity:0;transform:translate({dx:.1f}px,{dy:.1f}px)}}"
            f"0.01%{{opacity:1;transform:translate({dx:.1f}px,{dy:.1f}px);"
            f"animation-timing-function:{EASE_OUT_CUBIC}}}"
            f"100%{{opacity:1;transform:translate(0,0)}}}}")


def appear_keyframes(name: str, fade: bool) -> str:
    if fade:
        return f"@keyframes {name}{{0%{{opacity:0}}100%{{opacity:1}}}}"
    return f"@keyframes {name}{{0%{{opacity:0}}0.01%{{opacity:1}}100%{{opacity:1}}}}"


def track_keyframes(name: str, track, x0: float, y0: float) -> tuple:
    """(css, seconds) translating the callout along its subject's keyframes, linearly."""
    total = float(track[-1][0])
    stops = []
    for dt, x, y in track:
        stops.append(f"{100.0 * float(dt) / total:.3f}%{{transform:translate("
                     f"{(x - x0) * W:.1f}px,{(y - y0) * H:.1f}px)}}")
    return f"@keyframes {name}{{{''.join(stops)}}}", total


def sticker_offset(el, aspect: float) -> tuple:
    """(dx, dy) px that put the sticker wholly off the frame edge it enters from."""
    x, y = el["at"]
    w = float(el["size"]) * W
    h = w * aspect
    edge = el.get("enter_from") or nearest_edge(x, y)
    if edge == "bottom":
        return 0.0, H - (y * H - h / 2) + 8
    if edge == "top":
        return 0.0, -(y * H + h / 2) - 8
    if edge == "left":
        return -(x * W + w / 2) - 8, 0.0
    return W - (x * W - w / 2) + 8, 0.0


def _arrow_svg(length: float) -> str:
    L, T = length, length * 0.62
    pts = [(0, 0.36), (0.52, 0.36), (0.52, 0.06), (1.0, 0.5), (0.52, 0.94), (0.52, 0.64), (0, 0.64)]
    poly = " ".join(f"{px * L:.1f},{py * T:.1f}" for px, py in pts)
    sw = max(3.0, 0.035 * L)
    return (f'<svg width="{L:.1f}" height="{T:.1f}" style="position:absolute;left:{-L:.1f}px;'
            f'top:{-T / 2:.1f}px;overflow:visible"><polygon points="{poly}" fill="{ARROW_FILL}" '
            f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linejoin="round"/></svg>')


def _text_body(text: str, cap_frac: float, color: str) -> str:
    fs = cap_frac * H / CAP_EM
    return (f'<div style="position:absolute;left:0;top:0;transform:translate(-50%,-50%);'
            f"white-space:nowrap;font-family:'{ROUNDED_FAMILY}',Arial Rounded MT Bold,sans-serif;"
            f"font-weight:900;font-size:{fs:.1f}px;line-height:1;color:{color};"
            f"-webkit-text-stroke:{0.07 * fs:.1f}px {INK};paint-order:stroke fill;"
            f'text-shadow:0 {0.04 * fs:.1f}px {0.08 * fs:.1f}px rgba(0,0,0,.6)">'
            f"{_html.escape(text)}</div>")


def callout_html(el, idx, *, image_uri=None, png_size=None) -> tuple:
    """-> (html, css) for one compiled callout element. Frame-exact under illustrate's seek().

    Nodes, outside in: a zero-size root on the anchor (carries `id` and the exit's data-t1),
    the tracking translate, the out animation, the entrance, and the body positioned so the
    anchor is its centre (the arrow: its tip). Every animated node carries `data-t0`.
    """
    kind = el["callout"]
    nid = f"el{idx}"
    x, y = el["at"]
    t0 = float(el["enter"]["t"])
    ease = el["ease"]
    in_s = max(0.001, float(el.get("in_ms") or 0.0) / 1000.0)
    css = []
    # entrance
    if ease in ("pop_badge", "pop_arrow", "pop_caption", "pop_stamp"):
        css.append(scale_keyframes(f"kf-{nid}-in", EASING[ease]))
    elif ease == "slide_in":
        aspect = 1.0
        if kind == "sticker" and png_size is not None:
            dims = png_size(el.get("src") or "")
            aspect = (dims[1] / dims[0]) if dims else 1.0
        dx, dy = sticker_offset(el, aspect)
        css.append(slide_keyframes(f"kf-{nid}-in", dx, dy))
    else:  # fade | none
        css.append(appear_keyframes(f"kf-{nid}-in", ease == "fade"))
        if ease == "none":
            in_s = 0.001
    entrance = (f'<div class="anim" data-t0="{t0:.4f}" style="position:absolute;left:0;top:0;'
                f"transform-origin:0 0;animation:kf-{nid}-in {in_s:.4f}s linear both paused;"
                f'animation-delay:{t0:.4f}s">')
    # body
    if kind == "sticker":
        if image_uri is None:
            raise ValueError("a sticker callout needs the caller's image_uri (illustrate)")
        w = float(el["size"]) * W
        tilt = float(el.get("tilt", 0.0))
        body = (f'<img alt="" src="{image_uri(el["src"])}" style="position:absolute;left:0;top:0;'
                f'width:{w:.1f}px;height:auto;transform:translate(-50%,-50%) rotate({tilt:g}deg)">')
    elif kind == "badge":
        body = _text_body(el["text"], float(el["size"]), el.get("color", "#FFFFFF"))
    elif kind == "text":
        body = _text_body(el["text"], float(el["size"]), el.get("color", STAMP_RED))
    elif kind == "arrow":
        angle = DIRECTIONS[el.get("direction", "down_left")]
        body = (f'<div style="position:absolute;left:0;top:0;transform:rotate({angle}deg);'
                f'transform-origin:0 0">{_arrow_svg(float(el["size"]) * W)}</div>')
    else:  # circle
        d = float(el["size"]) * W
        sw = max(6.0, 0.05 * d)
        body = (f'<svg width="{d + 2 * sw:.1f}" height="{d + 2 * sw:.1f}" style="position:absolute;'
                f'left:{-(d / 2 + sw):.1f}px;top:{-(d / 2 + sw):.1f}px;overflow:visible">'
                f'<circle cx="{d / 2 + sw:.1f}" cy="{d / 2 + sw:.1f}" r="{d / 2:.1f}" fill="none" '
                f'stroke="{INK}" stroke-width="{sw * 1.6:.1f}"/>'
                f'<circle cx="{d / 2 + sw:.1f}" cy="{d / 2 + sw:.1f}" r="{d / 2:.1f}" fill="none" '
                f'stroke="{ARROW_FILL}" stroke-width="{sw:.1f}"/></svg>')
    inner = f"{entrance}{body}</div>"
    # out animation (slide_out / fade) ending on the exit instant; snap needs none
    exit_ = el.get("exit")
    if exit_ and el.get("out", "snap") != "snap":
        t_exit = float(exit_["t"])
        o = min(float(el.get("out_ms", DEFAULT_OUT_MS)) / 1000.0, max(0.001, t_exit - t0 - in_s))
        ts = t_exit - o
        if el["out"] == "fade":
            css.append(f"@keyframes kf-{nid}-out{{0%{{opacity:1}}100%{{opacity:0}}}}")
        else:
            aspect = 1.0
            if kind == "sticker" and png_size is not None:
                dims = png_size(el.get("src") or "")
                aspect = (dims[1] / dims[0]) if dims else 1.0
            dx, dy = sticker_offset(el, aspect) if kind == "sticker" else (0.0, H * 0.6)
            css.append(f"@keyframes kf-{nid}-out{{0%{{transform:translate(0,0);"
                       f"animation-timing-function:{EASE_IN_CUBIC}}}"
                       f"100%{{transform:translate({dx:.1f}px,{dy:.1f}px)}}}}")
        inner = (f'<div class="anim" data-t0="{ts:.4f}" style="position:absolute;left:0;top:0;'
                 f"animation:kf-{nid}-out {o:.4f}s linear both paused;animation-delay:{ts:.4f}s\">"
                 f"{inner}</div>")
    track = el.get("track")
    if track:
        tcss, total = track_keyframes(f"kf-{nid}-tr", track, x, y)
        css.append(tcss)
        inner = (f'<div class="anim" data-t0="{t0:.4f}" style="position:absolute;left:0;top:0;'
                 f"animation:kf-{nid}-tr {total:.4f}s linear both paused;animation-delay:{t0:.4f}s\">"
                 f"{inner}</div>")
    root = (f'<div id="{nid}" class="callout callout-{kind}" style="position:absolute;'
            f'left:{x * 100:.4f}%;top:{y * 100:.4f}%;width:0;height:0">{inner}</div>')
    return root, "\n".join([font_face_css() if kind in ("badge", "text") else "", *css])


def bbox(el) -> tuple:
    """(left, top, right, bottom) fractions a compiled callout can paint, erring wide (the
    watermark guard's question). Tracking widens it to the whole path."""
    kind = el["callout"]
    s = float(el["size"])
    if kind == "sticker":
        hw, hh = s / 2, s * W / H     # a square-ish worst case for the height
    elif kind in ("badge", "text"):
        fs = s / CAP_EM
        hw, hh = len(el.get("text", "")) * 0.65 * fs * H / W / 2, fs * 0.8
    elif kind == "arrow":
        hw, hh = s, s * W / H
    else:
        hw, hh = s / 2 + 0.02, (s / 2 + 0.02) * W / H
    xs = [p[1] for p in el.get("track") or []] or [el["at"][0]]
    ys = [p[2] for p in el.get("track") or []] or [el["at"][1]]
    return (round(min(xs) - hw, 6), round(min(ys) - hh, 6),
            round(max(xs) + hw, 6), round(max(ys) + hh, 6))


def entries(elements) -> list:
    """[(t0, kind)] of compiled callouts, for logs and the review table."""
    return [(float(el["enter"]["t"]), el["callout"]) for el in elements
            if el.get("type") == "callout"]



# --- the opening: frame-0 radial zoom-blur + ding (SPEC section 5) ---------------------------

#: Measured in all three references: frame 0 is a heavily radial-zoom-blurred version of the first
#: shot that resolves to sharp in 150-200 ms, with the first word by ~0.07 s and a ding by 0.3 s.
OPEN_DEFAULTS = {"frame0": "radial_zoom_blur", "ms": 180.0, "strength": 0.35,
                 "center": [0.5, 0.5], "samples": 12, "sfx": "ding"}
OPEN_SFX = {"ding": {"src": "bundle:ding", "gain_db": -10.0, "end": 0.9}}


def parse_open(spec) -> dict | None:
    """The spec's top-level `open:` block, filled in, or None when absent.

        open: {frame0: radial_zoom_blur, ms: 180, strength: 0.35, center: [0.5, 0.5], sfx: ding}

    `strength` is the extra zoom of the outermost blur sample at frame 0 (0.35 = 1.35x); it
    decays to 0 over `ms` on an ease-out (heavy on frame 0, sharp by the end). `sfx: ding` puts
    the ding on frame 0 as the opening sting (impact 0.0), so the gate's opening rules judge
    the first word against it; `sfx: null` leaves the audio alone."""
    raw = (spec or {}).get("open")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CalloutError(f"`open:` must be a mapping, got {raw!r}")
    unknown = set(raw) - set(OPEN_DEFAULTS)
    if unknown:
        raise CalloutError(f"unknown open key(s) {', '.join(sorted(unknown))}; "
                           f"known: {', '.join(OPEN_DEFAULTS)}")
    cfg = {**OPEN_DEFAULTS, **raw}
    if cfg["frame0"] != "radial_zoom_blur":
        raise CalloutError("open.frame0: only `radial_zoom_blur` is measured")
    cfg["ms"] = _num(cfg["ms"], "open.ms", "open", 34.0, 600.0)
    cfg["strength"] = _num(cfg["strength"], "open.strength", "open", 0.01, 1.0)
    cfg["samples"] = int(_num(cfg["samples"], "open.samples", "open", 2, 32))
    c = cfg["center"]
    if not (isinstance(c, (list, tuple)) and len(c) == 2):
        raise CalloutError("open.center must be [x, y]")
    cfg["center"] = [_num(c[0], "center.x", "open", 0.0, 1.0), _num(c[1], "center.y", "open", 0.0, 1.0)]
    if cfg["sfx"] is not None and cfg["sfx"] not in OPEN_SFX:
        raise CalloutError(f"open.sfx must be one of {', '.join(OPEN_SFX)} or null")
    return cfg


def open_strengths(cfg, fps: int = 30) -> list:
    """Per-frame blur strength for the opening frames: ease-out decay to 0 over `ms`."""
    n = max(1, round(float(cfg["ms"]) / 1000.0 * fps))
    return [round(float(cfg["strength"]) * (1.0 - i / n) ** 2, 5) for i in range(n)]


def open_sting(cfg) -> dict | None:
    """The `audio.sfx.opening` block `open.sfx` stands for (impact 0.0), or None."""
    if not cfg or not cfg.get("sfx"):
        return None
    s = OPEN_SFX[cfg["sfx"]]
    return {"impact": 0.0, "layers": [{"src": s["src"], "at": 0.0, "end": s["end"],
                                        "fade_out": 0.08, "gain_db": s["gain_db"]}]}
