"""The edit-grammar layer: blur behind overlays, per-event SFX, verdict tint (2026-11-04).

ParkSheet "route C" adopts three habits of a reference Shorts channel (Super Happy Mega Mouse,
logged in Stephen's vault as the edit-grammar reference): the scene behind an overlay graphic
blurs while the graphic is up, a sound marks nearly every edit event (a hit on each cut, a
pop on each tag, a whoosh on each camera move), and a "good"/"bad" moment tints the picture
green/red with a ding/buzzer. Every key here is OPT-IN; a spec that carries none of them
renders byte for byte what it did before this module existed (tested on a real scene).

PICTURE (per `kind: media` scene, composited in the scene's own encode, on the FOOTAGE only --
before the illustration overlay, the plates and the captions, so the graphics stay sharp and
keep their own colours):

  overlay:
    blur_bg: true | {sigma: 10, in_ms: 150, out_ms: 150, hold: 1.2}
        Blur behind the WHOLE overlay: from the first element's entry (0 for a card
        `template:`) to `hold` seconds later, or to the end of the scene.
    elements:
    - {type: tag, ..., blur_bg: true | {...}}      # blur behind this one element only

  crashzoom: {badge: {..., blur_bg: {...}}}         # blur behind the crash-zoom badge

  fx: {verdict: good|bad, from: <t|word>, to: <t|word>, strength: 1.0, ramp_ms: 100}
        Colour wash (colorchannelmixer) for the span (default: the whole scene), plus the matching sound
        (`audio.sfx.on_verdict`) at the span start. `from`/`to` take the same word references
        an overlay element's `enter.when` does.
  fx: [{verdict: bad, to: <word>}, {verdict: good, from: <word>}]
        A LIST of up to 4 such spans (2026-11-04, PoC v3): the line can turn from bad to good
        mid-sentence. Each span is checked as above, each gets its own sound, and the spans
        may not overlap once their words resolve (refused by scene).

  `sigma` is in DELIVERED pixels (scaled to the 1.2x render size here, as `blur:` is). A blur
  window that runs to the end of its scene has no out-ramp: the cut is the snap back.

  Mechanism: the graded footage is split; each window's copy is blurred (or tinted), given an
  alpha ramp with `fade=...:alpha=1`, and overlaid back with `enable='between(t,a,b)'`. So the
  ramp is a dissolve from sharp to blurred, which at 150 ms reads as the blur arriving.

SOUND (`audio.sfx`, all optional, each `{src, gain_db, start?, end?}`):

  on_cut:  a sound on every PICTURE cut (scene starts after the first, and beat boundaries).
           The legacy string form `on_cut: <file>` is unchanged: the whoosh at the structural
           beat boundaries. Only the MAPPING form is this layer.
  on_tag:  a sound on every overlay/illustration element's entry that has no `sfx:` of its
           own (an element's own sound wins).
  on_move: a sound `lead` seconds before every camera move: a beat or scene whose motion is in
           `motions` (default punch, burst, pan_left, pan_right) and every crash-zoom turn.
  on_verdict: {good: {...}, bad: {...}} -- the ding/buzzer of `fx.verdict`.
  min_gap: the closest two grammar sounds (or a grammar sound and any other) may start.

  `src: bundle:<name>` names a file in scripts/video/sfx/ (see sfx/manifest.json: Mixkit,
  each file's URL, licence and sha256). Sounds before the first word + guard are dropped, as
  the element sounds are; collisions inside `min_gap` keep the higher-priority sound
  (verdict > tag > cut > move). Everything kept is written to cuts.json's `sfx` list with
  roles `cut`, `tag`, `move`, `verdict_good`, `verdict_bad`.

Pure: standard library only (the word-reference resolver is illustrate's, which is too).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib

import illustrate

HERE = pathlib.Path(__file__).resolve().parent
SFX_DIR = HERE / "sfx"
SFX_MANIFEST = SFX_DIR / "manifest.json"
BUNDLE_PREFIX = "bundle:"

BLUR_DEFAULTS = {"sigma": 10.0, "in_ms": 150.0, "out_ms": 150.0, "hold": None}
BLUR_SIGMA_MAX = 30.0
RAMP_MS_MAX = 2000.0

VERDICTS = ("good", "bad")
FX_KEYS = ("verdict", "from", "to", "strength", "ramp_ms", "style", "at", "hold")
FX_STYLES = ("grade", "wash")

#: `fx: {style: wash}` (2026-11-04): the measured verdict WASH of the grammar study (SPEC
#: section 4) -- a normal-blend colour layer, not a channel grade. Red at alpha 0.24 with darker
#: corners, ramping 200 ms from 80 ms before the word, held 330 ms, out 200 ms; green at alpha
#: 0.44, 170 ms in, held to the cut. `hold: cut` / milliseconds overrides the hold.
WASH = {
    "bad": {"color": "0xFF0000", "alpha": 0.24, "vignette": True, "lead_ms": 80.0,
            "in_ms": 200.0, "hold": 330.0, "out_ms": 200.0},
    "good": {"color": "0x009600", "alpha": 0.44, "vignette": False, "lead_ms": 80.0,
             "in_ms": 170.0, "hold": "cut", "out_ms": 200.0},
}
FX_DEFAULT_RAMP_MS = 100.0

#: The verdict grades, at strength 1: an RGB colour WASH (`colorchannelmixer`), each channel
#: pulled toward green (good) or red (bad) from the other two. Chosen over `colorbalance` after
#: looking at real frames (2026-11-04): colorbalance with preserve-lightness posterised a
#: saturated blue sky into grey bands on the green grade and barely moved it at all at a gentler
#: setting, while the wash reads as an unmistakable tint, stays smooth on skies, and keeps faces
#: and sign text legible (each output channel keeps most of its own input). Linear in
#: `strength`: every coefficient moves from the identity toward these.
VERDICT_MIX = {
    "good": {"rr": 0.72, "rg": 0.0, "rb": 0.0, "gr": 0.18, "gg": 0.92, "gb": 0.18,
             "br": 0.0, "bg": 0.0, "bb": 0.66},
    "bad": {"rr": 0.92, "rg": 0.22, "rb": 0.12, "gr": 0.0, "gg": 0.72, "gb": 0.0,
            "br": 0.0, "bg": 0.0, "bb": 0.70},
}
_IDENTITY = {"rr": 1.0, "gg": 1.0, "bb": 1.0}

GRAMMAR_KEYS = ("on_tag", "on_move", "on_verdict", "min_gap")
SOUND_KEYS = ("src", "gain_db", "start", "end")
MOVE_KEYS = (*SOUND_KEYS, "lead", "motions")
DEFAULT_GAIN = {"cut": -10.0, "tag": -14.0, "move": -20.0, "verdict_good": -14.0,
                "verdict_bad": -16.0}
DEFAULT_MOVE_MOTIONS = ("punch", "burst", "pan_left", "pan_right")
DEFAULT_MOVE_LEAD = 0.15
DEFAULT_MIN_GAP = 0.12
#: Lower sorts first: who keeps the slot when two sounds collide inside `min_gap`.
PRIORITY = {"verdict_good": 0, "verdict_bad": 0, "tag": 1, "cut": 2, "move": 3}
END_FADE_S = 0.02


# --- picture ----------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Window:
    """One span of a part that gets a filtered copy of the footage laid over it."""
    kind: str            # "tint" | "blur"
    t0: float
    t1: float
    ramp_in: float
    ramp_out: float
    filter: str


def _num(value, name, where, lo, hi, *, lo_open=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: `{name}` must be a number, got {value!r}")
    v = float(value)
    if (v <= lo if lo_open else v < lo) or v > hi:
        raise ValueError(f"{where}: `{name}: {value}` is outside "
                         f"{'(' if lo_open else '['}{lo:g}, {hi:g}]")
    return v


def parse_blur_bg(value, where="blur_bg"):
    """`blur_bg:` -> a filled-in dict, or None when absent/false. Pure; raises ValueError."""
    if value is None or value is False:
        return None
    if value is True:
        value = {}
    if not isinstance(value, dict):
        raise ValueError(f"{where}: `blur_bg` must be true or a mapping "
                         f"{{sigma, in_ms, out_ms, hold}}, got {value!r}")
    unknown = set(value) - set(BLUR_DEFAULTS)
    if unknown:
        raise ValueError(f"{where}: unknown blur_bg key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(BLUR_DEFAULTS)}")
    cfg = {**BLUR_DEFAULTS, **value}
    cfg["sigma"] = _num(cfg["sigma"], "sigma", where, 0.0, BLUR_SIGMA_MAX, lo_open=True)
    for key in ("in_ms", "out_ms"):
        cfg[key] = _num(cfg[key], key, where, 0.0, RAMP_MS_MAX)
    if cfg["hold"] is not None:
        cfg["hold"] = _num(cfg["hold"], "hold", where, 0.0, 600.0, lo_open=True)
    return cfg


def element_entry(el) -> float:
    """When a RESOLVED element starts to appear, in scene seconds (0 if it has no entry)."""
    if el.get("type") == "figure" and el.get("pose") == "walk":
        return float(el.get("t0", 0.0))
    if el.get("type") == "calendar":
        return float(el.get("t0", 0.0))
    enter = el.get("enter")
    return float(enter["t"]) if isinstance(enter, dict) and "t" in enter else 0.0


def _blur_window(t0, cfg, dur, scale) -> Window | None:
    t1 = float(dur) if cfg["hold"] is None else min(float(dur), t0 + cfg["hold"])
    t0 = max(0.0, float(t0))
    if t1 - t0 < 1.0 / 30:
        return None
    ramp_in = min(cfg["in_ms"] / 1000.0, t1 - t0)
    ends_at_cut = t1 >= float(dur) - 1e-6
    ramp_out = 0.0 if ends_at_cut else min(cfg["out_ms"] / 1000.0, max(0.0, t1 - t0 - ramp_in))
    return Window("blur", round(t0, 4), round(t1, 4), round(ramp_in, 4), round(ramp_out, 4),
                  f"gblur=sigma={cfg['sigma'] * float(scale):.4f}")


def merge_windows(windows) -> list:
    """Overlapping windows of one kind -> one window each (earliest in-ramp, latest out-ramp,
    the strongest filter). Pure."""
    out = []
    for w in sorted(windows, key=lambda w: (w.t0, w.t1)):
        if out and out[-1].kind == w.kind and w.t0 <= out[-1].t1 + 1e-6:
            prev = out[-1]
            keep_out = w if w.t1 >= prev.t1 else prev
            strong = max((prev, w), key=lambda x: _sigma(x.filter))
            out[-1] = Window(w.kind, prev.t0, keep_out.t1, prev.ramp_in, keep_out.ramp_out,
                             strong.filter)
        else:
            out.append(w)
    return out


def _sigma(filter_text: str) -> float:
    try:
        return float(filter_text.split("sigma=")[1].split(":")[0])
    except (IndexError, ValueError):
        return 0.0


def blur_windows(overlay_block, resolved_overlay, dur, scale=1.0, where="overlay") -> list:
    """Every blur window a media scene's `overlay:` asks for. `[]` when it asks for none.

    `resolved_overlay` is the scene's overlay AFTER `illustrate.resolve_times` (its element
    entries are seconds), or None for a card-only overlay.
    """
    block = overlay_block if isinstance(overlay_block, dict) else {}
    elements = list((resolved_overlay or {}).get("elements") or [])
    windows = []
    whole = parse_blur_bg(block.get("blur_bg"), f"{where}.blur_bg")
    if whole is not None:
        starts = [element_entry(el) for el in elements if isinstance(el, dict)]
        t0 = 0.0 if block.get("template") or not starts else min(starts)
        w = _blur_window(t0, whole, dur, scale)
        if w:
            windows.append(w)
    for index, el in enumerate(elements):
        if not isinstance(el, dict):
            continue
        cfg = parse_blur_bg(el.get("blur_bg"), f"{where} element {index}")
        if cfg is not None:
            w = _blur_window(element_entry(el), cfg, dur, scale)
            if w:
                windows.append(w)
    return merge_windows(windows)


def check_overlay(overlay_block, where="overlay") -> None:
    """Preflight the blur keys of an UNRESOLVED overlay block (shape only)."""
    block = overlay_block if isinstance(overlay_block, dict) else {}
    parse_blur_bg(block.get("blur_bg"), f"{where}.blur_bg")
    for index, el in enumerate(block.get("elements") or []):
        if isinstance(el, dict):
            parse_blur_bg(el.get("blur_bg"), f"{where} element {index}")


#: The most verdict spans one scene's `fx:` list may carry.
FX_MAX_SPANS = 4


def parse_fx_list(scene, where="scene") -> list:
    """A scene's `fx:` as a list of checked spans: [] when absent, one for a mapping (the
    original form, unchanged), several for a list. Pure; raises ValueError."""
    fx = (scene or {}).get("fx")
    if fx is None:
        return []
    if isinstance(fx, list):
        if not fx:
            raise ValueError(f"{where}: `fx:` is an empty list; drop it or give a span")
        if len(fx) > FX_MAX_SPANS:
            raise ValueError(f"{where}: `fx:` has {len(fx)} spans; at most {FX_MAX_SPANS}")
        return [parse_fx({"fx": item}, f"{where} fx[{i}]") for i, item in enumerate(fx)]
    return [parse_fx(scene, where)]


def check_no_overlap(spans, where="scene") -> None:
    """Refuse verdict spans [(t0, t1), ...] that overlap on the scene clock."""
    ordered = sorted(spans)
    for (a0, a1), (b0, b1) in zip(ordered, ordered[1:]):
        if b0 < a1 - 1e-6:
            raise ValueError(f"{where}: fx verdict spans overlap ({a0:.3f}-{a1:.3f}s and "
                             f"{b0:.3f}-{b1:.3f}s); give the first a `to:` before the "
                             f"second's `from:`")


def parse_fx(scene, where="scene"):
    """A scene's `fx:` block, checked, or None. Pure; raises ValueError."""
    fx = (scene or {}).get("fx")
    if fx is None:
        return None
    if not isinstance(fx, dict):
        raise ValueError(f"{where}: `fx:` must be a mapping, got {type(fx).__name__}")
    unknown = set(fx) - set(FX_KEYS)
    if unknown:
        raise ValueError(f"{where}: unknown fx key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(FX_KEYS)}")
    if fx.get("verdict") not in VERDICTS:
        raise ValueError(f"{where}: fx.verdict must be one of {', '.join(VERDICTS)}, "
                         f"got {fx.get('verdict')!r}")
    style = fx.get("style", "grade")
    if style not in FX_STYLES:
        raise ValueError(f"{where}: fx.style must be one of {', '.join(FX_STYLES)}")
    if style == "wash":
        bad = sorted(k for k in ("strength", "ramp_ms", "to") if k in fx)
        if bad:
            raise ValueError(f"{where}: fx.style wash takes `at` (or `from`) and `hold`, not "
                             f"{', '.join(bad)}; its colour, alpha and ramps are the measured ones")
        if "at" not in fx and "from" not in fx:
            raise ValueError(f"{where}: fx.style wash needs `at:` -- the verdict word")
        hold = fx.get("hold", WASH[fx["verdict"]]["hold"])
        if hold != "cut":
            _num(hold, "fx.hold", where, 1.0, 60000.0)
        out = {"verdict": fx["verdict"], "style": "wash", "hold": hold}
        for key in ("at", "from"):
            if key in fx:
                illustrate._check_time(fx[key], where, f"fx.{key}")
                out[key] = fx[key]
        return out
    if "at" in fx or "hold" in fx:
        raise ValueError(f"{where}: fx `at`/`hold` belong to `style: wash`")
    out = {"verdict": fx["verdict"],
           "strength": _num(fx.get("strength", 1.0), "fx.strength", where, 0.0, 1.0,
                            lo_open=True),
           "ramp_ms": _num(fx.get("ramp_ms", FX_DEFAULT_RAMP_MS), "fx.ramp_ms", where, 0.0,
                           RAMP_MS_MAX)}
    for key in ("from", "to"):
        if key in fx:
            illustrate._check_time(fx[key], where, f"fx.{key}")
            out[key] = fx[key]
    return out


def verdict_filter(verdict: str, strength: float = 1.0) -> str:
    """The colour wash for a verdict, at `strength` (0, 1]."""
    k = float(strength)
    parts = []
    for key, target in VERDICT_MIX[verdict].items():
        ident = _IDENTITY.get(key, 0.0)
        parts.append(f"{key}={ident + k * (target - ident):.4f}")
    return "colorchannelmixer=" + ":".join(parts)


def verdict_span(fx, words, dur, where="scene") -> tuple:
    """(t0, t1) of a verdict on its scene's own clock, word references resolved."""
    rows = illustrate.word_rows(words or [])
    t0 = (float(illustrate.resolve_time(fx["from"], rows, where, "fx.from"))
          if "from" in fx else 0.0)
    t1 = (float(illustrate.resolve_time(fx["to"], rows, where, "fx.to"))
          if "to" in fx else float(dur))
    t0, t1 = max(0.0, t0), min(float(dur), t1)
    if t1 - t0 < 1.0 / 30:
        raise ValueError(f"{where}: fx verdict span resolves to {t0:.3f}-{t1:.3f}s, "
                         f"shorter than a frame. `from` must come before `to`.")
    return round(t0, 4), round(t1, 4)


def wash_filter(verdict: str) -> str:
    """A normal-blend colour layer at the measured alpha: out = in * (1 - a) + colour * a, per
    RGB channel (lutrgb; drawbox's own alpha does not blend in YUV -- measured: red @0.24 on
    mid-grey came out (232, 66, 61), not (158, 97, 97))."""
    w = WASH[verdict]
    a = float(w["alpha"])
    rgb = [int(w["color"][2:][i:i + 2], 16) for i in (0, 2, 4)]
    f = "lutrgb=" + ":".join(f"{ch}='val*{1 - a:.4f}+{c * a:.2f}'" for ch, c in zip("rgb", rgb))
    return f + (",vignette=angle=0.8" if w["vignette"] else "")


def wash_window(fx, words, dur, where="scene") -> Window:
    """The measured verdict wash: ramps in `lead_ms` before the word so it peaks on it."""
    w = WASH[fx["verdict"]]
    rows = illustrate.word_rows(words or [])
    key = "at" if "at" in fx else "from"
    word_t = float(illustrate.resolve_time(fx[key], rows, where, f"fx.{key}"))
    t0 = max(0.0, word_t - (w["lead_ms"] / 1000.0 if key == "at" else 0.0))
    ramp_in = w["in_ms"] / 1000.0
    if fx["hold"] == "cut":
        t1, ramp_out = float(dur), 0.0
    else:
        ramp_out = w["out_ms"] / 1000.0
        t1 = t0 + ramp_in + float(fx["hold"]) / 1000.0 + ramp_out
        if t1 >= float(dur) - 1e-6:
            t1, ramp_out = float(dur), 0.0
    if t0 >= float(dur) - 1.0 / 30:
        raise ValueError(f"{where}: fx wash starts at {t0:.3f}s, at its scene's end")
    ramp_in = min(ramp_in, t1 - t0)
    return Window("tint", round(t0, 4), round(t1, 4), 0.0 if t0 <= 1e-6 else round(ramp_in, 4),
                  round(min(ramp_out, max(0.0, t1 - t0 - ramp_in)), 4), wash_filter(fx["verdict"]))


def verdict_window(fx, words, dur, where="scene") -> Window:
    if fx.get("style") == "wash":
        return wash_window(fx, words, dur, where)
    t0, t1 = verdict_span(fx, words, dur, where)
    ramp = min(fx["ramp_ms"] / 1000.0, (t1 - t0) / 2)
    ends_at_cut = t1 >= float(dur) - 1e-6
    starts_at_cut = t0 <= 1e-6
    return Window("tint", t0, t1, 0.0 if starts_at_cut else round(ramp, 4),
                  0.0 if ends_at_cut else round(ramp, 4),
                  verdict_filter(fx["verdict"], fx["strength"]))


def window_steps(stage: str, windows, tag: str = "w") -> tuple:
    """ffmpeg filter steps laying each window's filtered copy over `stage`.

    Returns (steps, new_stage). `([], stage)` for no windows, so a spec without the keys
    gets exactly the graph it always got.
    """
    windows = list(windows or ())
    if not windows:
        return [], stage
    n = len(windows)
    labels = [f"{tag}b0"] + [f"{tag}s{i}" for i in range(n)]
    steps = [f"[{stage}]split={n + 1}" + "".join(f"[{label}]" for label in labels)]
    base = f"{tag}b0"
    for i, w in enumerate(windows):
        chain = [w.filter, "format=yuva420p"]
        if w.ramp_in > 0:
            chain.append(f"fade=t=in:st={w.t0:.4f}:d={w.ramp_in:.4f}:alpha=1")
        if w.ramp_out > 0:
            chain.append(f"fade=t=out:st={w.t1 - w.ramp_out:.4f}:d={w.ramp_out:.4f}:alpha=1")
        steps.append(f"[{tag}s{i}]{','.join(chain)}[{tag}f{i}]")
        steps.append(f"[{base}][{tag}f{i}]overlay=x=0:y=0:format=auto:"
                     f"enable='between(t,{w.t0:.4f},{w.t1:.4f})'[{tag}b{i + 1}]")
        base = f"{tag}b{i + 1}"
    return steps, base


def blur_strength(cfg, d: float, end: float | None = None) -> float:
    """0..1 ramp of a blur that starts at d=0 (seconds since it began). For crashzoom frames."""
    if d < 0:
        return 0.0
    hold = cfg.get("hold")
    if hold is not None and d > hold:
        return 0.0
    k = 1.0 if cfg["in_ms"] <= 0 else min(1.0, d / (cfg["in_ms"] / 1000.0))
    if hold is not None and cfg["out_ms"] > 0:
        k = min(k, max(0.0, (hold - d) / (cfg["out_ms"] / 1000.0)))
    return k


# --- sound ------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Sound:
    role: str
    src: str
    gain_db: float
    start: float = 0.0
    end: float | None = None


@dataclasses.dataclass(frozen=True)
class Grammar:
    """The per-event sounds of `audio.sfx`. Every field None/empty = nothing fires."""
    cut: Sound | None = None
    tag: Sound | None = None
    move: Sound | None = None
    good: Sound | None = None
    bad: Sound | None = None
    move_lead: float = DEFAULT_MOVE_LEAD
    move_motions: tuple = DEFAULT_MOVE_MOTIONS
    min_gap: float = DEFAULT_MIN_GAP

    def sound(self, role: str) -> Sound | None:
        return {"cut": self.cut, "tag": self.tag, "move": self.move,
                "verdict_good": self.good, "verdict_bad": self.bad}.get(role)

    def any(self) -> bool:
        return any(s is not None for s in (self.cut, self.tag, self.move, self.good, self.bad))


def load_bundle(manifest=SFX_MANIFEST) -> dict:
    with open(manifest, encoding="utf-8") as fh:
        return json.load(fh)


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_bundle(src: str, manifest=SFX_MANIFEST) -> str:
    """`bundle:<name>` -> the absolute path of that bundled sound, sha256-checked.

    The files are NOT in git (the repo is public, and the Mixkit licence does not allow
    redistributing the sounds as stand-alone files): `sfx/fetch.py` downloads them by hand.
    """
    name = str(src)[len(BUNDLE_PREFIX):]
    sounds = load_bundle(manifest)["sounds"]
    if name not in sounds:
        raise ValueError(f"`{src}` names no bundled sound; known: {', '.join(sorted(sounds))}")
    row = sounds[name]
    path = pathlib.Path(manifest).parent / row["file"]
    if not path.is_file():
        raise FileNotFoundError(
            f"bundled sound {name!r} is not downloaded ({path}). Fetch the set by hand: "
            f"scripts/video/.venv-tts/bin/python scripts/video/sfx/fetch.py")
    got = sha256(path)
    if got != row["sha256"]:
        raise ValueError(f"bundled sound {name!r} ({path}) has sha256 {got}, not the "
                         f"manifest's {row['sha256']}: re-fetch it with sfx/fetch.py")
    return str(path)


def _sound(role, raw, resolve, where, known=SOUND_KEYS) -> Sound:
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be a mapping {{src, gain_db}}, got {raw!r}")
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"unknown {where} key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(known)}")
    if not raw.get("src"):
        raise ValueError(f"{where} has no `src`, so there is no file to mix")
    start = _num(raw.get("start", 0.0), "start", where, 0.0, 60.0)
    end = raw.get("end")
    if end is not None:
        end = _num(end, "end", where, 0.0, 60.0)
        if end <= start:
            raise ValueError(f"{where}: `end` ({end:g}) must be after `start` ({start:g})")
    gain = _num(raw.get("gain_db", DEFAULT_GAIN[role]), "gain_db", where, -60.0, 12.0)
    return Sound(role=role, src=resolve(where, raw), gain_db=gain, start=start, end=end)


def parse_grammar(raw_sfx: dict, resolve) -> Grammar | None:
    """The grammar half of `audio.sfx`, or None when it asks for none of it.

    `resolve(name, raw) -> absolute path` is audio_settings' own resolver (it knows
    `bundle:`), so a missing file refuses the render the way a missing bed does.
    """
    raw_sfx = raw_sfx or {}
    on_cut = raw_sfx.get("on_cut")
    if not any(k in raw_sfx for k in GRAMMAR_KEYS) and not isinstance(on_cut, dict):
        return None
    kw = {}
    if isinstance(on_cut, dict):
        kw["cut"] = _sound("cut", on_cut, resolve, "audio.sfx.on_cut")
    if raw_sfx.get("on_tag") is not None:
        kw["tag"] = _sound("tag", raw_sfx["on_tag"], resolve, "audio.sfx.on_tag")
    move = raw_sfx.get("on_move")
    if move is not None:
        kw["move"] = _sound("move", move, resolve, "audio.sfx.on_move", MOVE_KEYS)
        kw["move_lead"] = _num(move.get("lead", DEFAULT_MOVE_LEAD), "lead",
                               "audio.sfx.on_move", 0.0, 1.0)
        motions = move.get("motions", list(DEFAULT_MOVE_MOTIONS))
        if not isinstance(motions, list) or not all(isinstance(m, str) for m in motions):
            raise ValueError("audio.sfx.on_move.motions must be a list of motion names")
        kw["move_motions"] = tuple(motions)
    verdict = raw_sfx.get("on_verdict")
    if verdict is not None:
        if not isinstance(verdict, dict) or set(verdict) - set(VERDICTS):
            raise ValueError("audio.sfx.on_verdict must be a mapping with `good:` and/or "
                             "`bad:`, each {src, gain_db}")
        for name in VERDICTS:
            if verdict.get(name) is not None:
                kw[name] = _sound(f"verdict_{name}", verdict[name], resolve,
                                  f"audio.sfx.on_verdict.{name}")
    if "min_gap" in raw_sfx:
        kw["min_gap"] = _num(raw_sfx["min_gap"], "min_gap", "audio.sfx", 0.0, 2.0)
    return Grammar(**kw)


def cut_events(rows, picture_cuts) -> list:
    """`{at, role: cut}` at every PICTURE cut: each scene start after the first, and every
    beat boundary inside a scene. `picture_cuts` is {scene index: [scene-local boundaries]}.
    Overlay element entries are NOT cuts here (they are tags)."""
    out = []
    for n, row in enumerate(rows or ()):
        start = float(row["start"])
        if n > 0:
            out.append(start)
        for local in picture_cuts.get(row["scene"], ()):
            out.append(start + float(local))
    return [{"at": round(at, 3), "role": "cut"} for at in sorted(set(round(a, 3) for a in out))]


def tag_events(illustrated, rows) -> list:
    """`{at, role: tag}` for every element entry that has no `sfx:` of its own."""
    starts = {row["scene"]: float(row["start"]) for row in rows or ()}
    out = []
    for index, scene in illustrated or ():
        if index not in starts:
            continue
        for el in scene.get("elements") or ():
            if not isinstance(el, dict) or el.get("sfx"):
                continue
            enter = el.get("enter")
            if not isinstance(enter, dict) or "t" not in enter:
                continue      # on screen from frame 0: it arrives WITH the cut
            at = float(enter["t"]) + illustrate.EVENT_OFFSET.get(enter.get("how"), 0.0)
            out.append({"at": round(starts[index] + at, 3), "role": "tag"})
    return sorted(out, key=lambda r: r["at"])


def move_events(rows, moves, lead: float) -> list:
    """`{at, role: move}` `lead` s before every camera move. `moves` is
    {scene index: [scene-local move starts]}."""
    out = []
    for row in rows or ():
        for local in moves.get(row["scene"], ()):
            out.append({"at": round(max(0.0, float(row["start"]) + float(local) - lead), 3),
                        "role": "move"})
    return sorted(out, key=lambda r: r["at"])


def verdict_events(rows, verdicts) -> list:
    """`{at, role: verdict_good|bad}` at each verdict span start. `verdicts` is
    {scene index: (verdict, local t0)} or, for a scene with an `fx:` list,
    {scene index: [(verdict, local t0), ...]}."""
    starts = {row["scene"]: float(row["start"]) for row in rows or ()}
    out = []
    for index, value in (verdicts or {}).items():
        pairs = value if isinstance(value, list) else [value]
        if index in starts:
            for verdict, t0 in pairs:
                out.append({"at": round(starts[index] + float(t0), 3),
                            "role": f"verdict_{verdict}"})
    return sorted(out, key=lambda r: r["at"])


def thin(candidates, *, first_speech_s, guard: float, min_gap: float, seed=()) -> tuple:
    """Keep the grammar sounds that fit. Returns (kept, dropped-with-why). Pure.

    Nothing before `first_speech_s + guard` (gate S16: a sound over the first word is a
    swipe); then, in PRIORITY order, a sound is kept only if nothing already kept (or in
    `seed`, the sounds the render places anyway) starts within `min_gap` of it.
    """
    floor = (float(first_speech_s) + float(guard)) if first_speech_s is not None else float(guard)
    taken = [float(r["at"]) for r in seed or ()]
    kept, dropped = [], []
    order = sorted(candidates or (), key=lambda r: (PRIORITY.get(r["role"], 9), r["at"]))
    for row in order:
        at = float(row["at"])
        if at < floor:
            dropped.append({**row, "why": f"before the first word + {guard:g}s ({floor:.2f}s)"})
            continue
        near = [t for t in taken if abs(t - at) < float(min_gap) - 1e-9]
        if near:
            dropped.append({**row, "why": f"within {min_gap:g}s of a sound at {near[0]:.2f}s"})
            continue
        taken.append(at)
        kept.append(dict(row))
    return sorted(kept, key=lambda r: (r["at"], r["role"])), dropped


def sound_steps(grammar: Grammar, rows, indexes, runtime: float) -> tuple:
    """One clause per kept grammar sound (same shape as an element sound's, plus the
    optional in-file trim). Returns (steps, labels)."""
    steps, labels = [], []
    for n, (index, row) in enumerate(zip(indexes, rows), start=1):
        sound = grammar.sound(row["role"])
        delay = max(0, round(float(row["at"]) * 1000))
        trim = ""
        if sound.start or sound.end is not None:
            trim = (f"atrim=start={sound.start:g}" + (f":end={sound.end:g}" if sound.end is not None
                                                      else "") + ",asetpts=PTS-STARTPTS,")
            if sound.end is not None:
                length = sound.end - sound.start
                trim += f"afade=t=out:st={max(0.0, length - END_FADE_S):.3f}:d={END_FADE_S:g},"
        steps.append(f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,{trim}"
                     f"volume={sound.gain_db:g}dB,adelay={delay}|{delay},"
                     f"atrim=0:{float(runtime):.3f},"
                     f"apad=whole_dur={float(runtime):.3f}[g{n}]")
        labels.append(f"g{n}")
    return steps, labels


def sound_inputs(grammar: Grammar, rows, next_index: int) -> tuple:
    """The `-i` args for the kept grammar sounds (one per event) and their input indexes."""
    args, indexes = [], []
    count = int(next_index)
    for row in rows or ():
        sound = grammar.sound(row["role"])
        if sound is None:
            raise ValueError(f"no file for grammar sound {row['role']!r}")
        indexes.append(count)
        args += ["-i", sound.src]
        count += 1
    return args, indexes
