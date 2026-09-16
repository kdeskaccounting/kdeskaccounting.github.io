"""Burned-in captions against real pixels: Chrome draws them, ffmpeg composites them.

tests/test_make_short_captions.py proves the filter graph make_short ASKS for. This proves
what comes out: that the accent colour is in the caption band while a word is being spoken and
nowhere on the frame when no cue is up. A CSS tweak, a `paint-order` that Chrome stops
honouring, or an `enable=` expression that silently never fires would all pass the unit tests
and fail here.

Cheap on purpose: a 3-second lavfi source and two caption PNGs, not a 53-second Short. The
real media-demo render is checked too, but only when it happens to be on disk — it costs a
minute of Kokoro and a minute of encoding, which does not belong in the suite.
"""
import pathlib
import shutil
import subprocess

import pytest

import captions
import cards
import make_short as M
import media
import render_sheets as R

REPO = pathlib.Path(__file__).resolve().parents[1]
DEMO_SHORT = REPO / "scripts" / "video" / "build" / "media-demo" / "media-demo-short.mp4"

ACCENT = "#ffe234"
ACCENT_RGB = (0xFF, 0xE2, 0x34)
#: Generous enough for h264's 4:2:0 chroma and the glyph antialiasing, tight enough that the
#: brand gold a card uses (#FFD966, blue 0x66) is not mistaken for it.
TOLERANCE = (30, 26, 45)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is absent")
needs_chrome = pytest.mark.skipif(R.headless_shell() is None,
                                  reason="the playwright headless shell is absent")


def _rgb(video, at, box):
    """The RGB bytes of `box` = (left, top, right, bottom) in the frame at `at` seconds."""
    left, top, right, bottom = box
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"crop={right - left}:{bottom - top}:{left}:{top}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stderr.decode()[-2000:]
    assert proc.stdout, f"no pixels came back for t={at}"
    return proc.stdout


def _accent_pixels(px, rgb=ACCENT_RGB, tol=TOLERANCE):
    return sum(1 for i in range(0, len(px), 3)
               if all(abs(px[i + k] - rgb[k]) <= tol[k] for k in range(3)))


def _cue(words):
    return captions.build_cues(words)[0]


# --- the PNG Chrome draws -------------------------------------------------------------------

@needs_chrome
@needs_ffmpeg
def test_the_lit_word_is_drawn_in_the_accent_and_the_rest_are_not(tmp_path):
    box = captions.caption_box(M.OUT_W, M.OUT_H)
    brand = cards.brand_tokens(None)
    cue = _cue([{"text": "Magic", "start": 0.0, "end": 0.4},
                {"text": "Kingdom", "start": 0.5, "end": 0.9}])
    counts = []
    for lit in (0, 1):
        doc = captions.caption_html(cue, lit, ACCENT, brand, M.OUT_W, box)
        hp = tmp_path / f"cap_{lit}.html"; hp.write_text(doc, encoding="utf-8")
        png = tmp_path / f"cap_{lit}.png"
        R.screenshot(hp, png, M.OUT_W, box[3] - box[1], transparent=True)
        counts.append(_accent_pixels(_rgb(png, 0, (0, 0, M.OUT_W, box[3] - box[1]))))
    assert all(c > 500 for c in counts), f"the accent barely appears: {counts}"
    # "Magic" is five letters and "Kingdom" seven, so which word is lit visibly changes how
    # much accent there is — a PNG that ignored `lit` would give two identical counts.
    assert counts[0] != counts[1]


@needs_chrome
@needs_ffmpeg
def test_the_caption_png_is_transparent_everywhere_the_words_are_not(tmp_path):
    """It is laid over footage; an opaque band would be a black bar across the frame."""
    box = captions.caption_box(M.OUT_W, M.OUT_H)
    cue = _cue([{"text": "Hi", "start": 0.0, "end": 0.4}])
    doc = captions.caption_html(cue, 0, ACCENT, cards.brand_tokens(None), M.OUT_W, box)
    hp = tmp_path / "cap.html"; hp.write_text(doc, encoding="utf-8")
    png = tmp_path / "cap.png"
    R.screenshot(hp, png, M.OUT_W, box[3] - box[1], transparent=True)
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-f", "rawvideo",
                           "-pix_fmt", "rgba", "-"], capture_output=True, timeout=120)
    alpha = proc.stdout[3::4]
    assert max(alpha) == 255, "nothing was drawn at all"
    opaque = sum(1 for a in alpha if a)
    assert opaque < len(alpha) * 0.2, (
        f"{opaque} of {len(alpha)} pixels carry ink — a two-letter cue should be nearly all "
        f"transparent")


# --- the composite ffmpeg builds --------------------------------------------------------------

@needs_chrome
@needs_ffmpeg
def test_the_accent_is_on_screen_during_a_word_window_and_gone_outside_every_cue(tmp_path):
    """The whole claim, end to end, on a source with no yellow of its own."""
    box = captions.caption_box(M.OUT_W, M.OUT_H)
    brand = cards.brand_tokens(None)
    # Two cues, 0.4-1.4 s and 2.0-2.8 s, leaving 0-0.4 and 1.5-2.0 and 2.9-3.0 uncaptioned.
    cues = [captions.Cue(text="Magic Kingdom", start=0.4, end=1.4,
                         words=(captions.Word("Magic", 0.4, 0.9),
                                captions.Word("Kingdom", 0.9, 1.4))),
            captions.Cue(text="five minutes.", start=2.0, end=2.8,
                         words=(captions.Word("five", 2.0, 2.4),
                                captions.Word("minutes.", 2.4, 2.8)))]
    overlays = M.render_captions(cues, captions.CaptionConfig(True, ACCENT, "top"),
                                 brand, tmp_path, box)
    assert len(overlays) == 4

    base = tmp_path / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c=0x203040:s={M.OUT_W}x{M.OUT_H}:r={M.FPS}:d=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(base)],
                   check=True, capture_output=True, timeout=180)

    out = tmp_path / "captioned.mp4"
    args = ["-i", str(base)]
    for png, _s, _e in overlays:
        args += ["-i", str(png)]
    steps = M.caption_filter(overlays, box[1])
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", ";".join(steps),
                    "-map", "[vout]", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-r", str(M.FPS), str(out)],
                   check=True, capture_output=True, timeout=300)

    frame = (0, 0, M.OUT_W, M.OUT_H)
    for at in (0.6, 1.1, 2.2, 2.6):
        assert _accent_pixels(_rgb(out, at, box)) > 300, \
            f"no accent in the band at t={at}, inside a word window"
    for at in (0.1, 1.7, 2.95):
        assert _accent_pixels(_rgb(out, at, frame)) == 0, \
            f"accent pixels somewhere on the frame at t={at}, outside every cue"


@needs_chrome
@needs_ffmpeg
def test_nothing_is_ever_drawn_below_the_safe_zone_or_in_the_attribution_corner(tmp_path):
    """The band's own claim, against the pixels — not just against the constants."""
    box = captions.caption_box(M.OUT_W, M.OUT_H)
    cue = _cue([{"text": "Tomorrowland", "start": 0.0, "end": 0.6},
                {"text": "waits.", "start": 0.7, "end": 1.2}])
    doc = captions.caption_html(cue, 0, ACCENT, cards.brand_tokens(None), M.OUT_W, box)
    hp = tmp_path / "cap.html"; hp.write_text(doc, encoding="utf-8")
    png = tmp_path / "cap.png"
    R.screenshot(hp, png, M.OUT_W, box[3] - box[1], transparent=True)
    # The PNG IS the band, so "inside the band" is the whole claim; the band in turn is proved
    # to clear the safe zone and the watermark by tests/test_captions.py's geometry.
    assert box[3] <= round(M.OUT_H * captions.SAFE_BOTTOM_FRAC)
    assert not media.boxes_overlap(box, media.watermark_box(M.OUT_W, M.OUT_H))
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-f", "rawvideo",
                           "-pix_fmt", "rgba", "-"], capture_output=True, timeout=120)
    row = M.OUT_W * 4
    for edge, name in ((proc.stdout[:row], "top"), (proc.stdout[-row:], "bottom")):
        assert max(edge[3::4]) == 0, f"the caption touches the {name} edge of its own band"


# --- the real demo render, when it is on disk ---------------------------------------------------

@needs_ffmpeg
@pytest.mark.skipif(not DEMO_SHORT.exists(),
                    reason=f"{DEMO_SHORT} has not been rendered in this checkout")
def test_the_rendered_demo_short_carries_the_highlight_only_while_a_cue_is_up():
    """marketing/video/media-demo/scenes.yaml is the one spec in this repo with captions on."""
    import json
    yaml = pytest.importorskip("yaml", reason="the bare pytest environment has no yaml")
    spec = yaml.safe_load((REPO / "marketing/video/media-demo/scenes.yaml").read_text())
    assert captions.settings(spec).enabled is True
    build = DEMO_SHORT.parent
    work = build / "short"
    box, skipped = M.caption_plan(spec, spec["short"])
    scenes, at = [], 0.0
    for k, idx in enumerate(spec["short"]["scenes"]):
        seconds = M.dur_of(work / f"scene_{k}.mp4")
        scenes.append((idx, at, at + seconds))
        at += seconds
    total = at + M.dur_of(work / "end.mp4")
    cues = M.caption_cues(scenes, build / "audio", skipped)
    windows = captions.word_windows(cues)
    assert windows, "the demo rendered no caption windows at all"
    for window in windows[:: max(1, len(windows) // 5)]:
        mid = (window.start + window.end) / 2
        assert _accent_pixels(_rgb(DEMO_SHORT, mid, box)) > 300, \
            f"no highlight at t={mid:.2f}, mid-window on {cues[window.cue].text!r}"
    covered = [(w.start, w.end) for w in windows]
    for at in (0.1, total - 0.5):
        assert not any(s <= at <= e for s, e in covered)
        assert _accent_pixels(_rgb(DEMO_SHORT, at, (0, 0, M.OUT_W, M.OUT_H))) == 0, \
            f"accent pixels at t={at:.2f}, which no cue covers"
    assert json.loads((build / "audio" / "scene_00.words.json").read_text()), \
        "the demo's word timings went missing"
