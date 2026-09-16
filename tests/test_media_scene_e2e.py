"""End-to-end: the media-demo spec renders through the real pipeline.

Three layers of guard, each skipping on what it actually needs:

  * the demo's committed assets — stdlib only, always runs;
  * the composite — needs ffmpeg and a headless Chrome, and proves against real pixels that
    nothing we draw covers the attribution zone in the bottom-right corner;
  * `build_video.py --frames-only` — needs the render venv (playwright/yaml/openpyxl), so it
    skips in a bare pytest environment and on CI runners, exactly like the card e2e.

The pixel test is the one worth keeping honest. tests/test_media.py proves the BOXES do not
intersect the watermark; this proves the rendered PNGs are actually transparent there, which
is the claim that matters when someone changes the CSS rather than the constants.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

import media
import render_sheets as R

REPO = pathlib.Path(__file__).resolve().parents[1]
VENV_PY = REPO / "scripts" / "video" / ".venv-tts" / "bin" / "python"
BUILD_VIDEO = REPO / "scripts" / "video" / "build_video.py"
MAKE_SHORT = REPO / "scripts" / "video" / "make_short.py"
DEMO = REPO / "marketing" / "video" / "media-demo"
SPEC = DEMO / "scenes.yaml"
ASSETS = DEMO / "assets"

#: Committed placeholders stay small — assets/generate.py enforces the same number.
MAX_ASSET_BYTES = 300_000

needs_venv = pytest.mark.skipif(not VENV_PY.exists(),
                                reason="render venv scripts/video/.venv-tts is absent")
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is absent")
needs_chrome = pytest.mark.skipif(R.headless_shell() is None,
                                  reason="the playwright headless shell is absent")


def _run(args, timeout=900):
    return subprocess.run([str(VENV_PY), *args], capture_output=True, text=True,
                          timeout=timeout, cwd=REPO)


# --- the committed demo assets ----------------------------------------------------------

@pytest.mark.parametrize("name", ["placeholder-still.jpg", "placeholder-clip.mp4"])
def test_the_demo_ships_its_placeholder_asset(name):
    """The demo renders on a clean checkout: no download step, no external imagery."""
    path = ASSETS / name
    assert path.is_file(), f"{path} missing; regenerate with {ASSETS / 'generate.py'}"
    assert path.stat().st_size <= MAX_ASSET_BYTES, (
        f"{name} is {path.stat().st_size:,} bytes, over the {MAX_ASSET_BYTES:,} cap — "
        f"a committed placeholder stays small")


def test_the_demo_assets_are_a_video_and_a_still_the_renderer_knows():
    assert media.media_kind(ASSETS / "placeholder-clip.mp4") == "video"
    assert media.media_kind(ASSETS / "placeholder-still.jpg") == "image"


def test_the_demo_spec_resolves_both_of_its_sources_from_this_repos_root():
    """`src:` is repo-relative to the spec's own repo, which for this spec is this one."""
    text = SPEC.read_text(encoding="utf-8")
    for name in ("placeholder-still.jpg", "placeholder-clip.mp4"):
        src = f"marketing/video/media-demo/assets/{name}"
        assert src in text
        assert media.resolve_src(SPEC, src) == (ASSETS / name).resolve()


def test_the_demo_spec_documents_the_watermark_rule():
    """Someone copying this spec into another repo must be told about the corner."""
    text = SPEC.read_text(encoding="utf-8")
    assert "bottom-right" in text and "attribution" in text


# --- the composite, against real pixels --------------------------------------------------

def _alpha_bytes(png, box):
    """The alpha channel of `box` = (left, top, right, bottom) in `png`, as raw bytes."""
    left, top, right, bottom = box
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(png),
         "-vf", f"crop={right - left}:{bottom - top}:{left}:{top}",
         "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
        capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stderr.decode()[-2000:]
    return proc.stdout[3::4]


@needs_chrome
@needs_ffmpeg
@pytest.mark.parametrize("layer", ["overlay", "credit"])
def test_the_layer_pngs_are_fully_transparent_over_the_attribution_zone(tmp_path, layer):
    """The claim the boxes make, checked against the pixels Chrome actually drew."""
    import cards
    import make_short as M
    scene = {"overlay": {"template": "ranked_list",
                         "data": {"heading": "A card over real imagery",
                                  "subheading": "The same data block, drawn on a plate",
                                  "items": [{"rank": i, "label": "x" * 40, "value": i}
                                            for i in range(1, 9)],
                                  "footer": "kdeskaccounting.com"}},
             "credit": "Imagery: " + "Placeholder Imagery Provider, " * 4}
    only = {layer: scene[layer]}
    pngs = M.media_layers(only, cards.brand_tokens(None), tmp_path, 0)
    assert len(pngs) == 1
    alpha = _alpha_bytes(pngs[0], media.watermark_box(M.RW, M.RH))
    assert alpha, "the crop produced no pixels"
    assert max(alpha) == 0, (
        f"the {layer} layer paints {sum(1 for a in alpha if a)} pixels inside the Earth "
        f"Studio attribution zone — nothing may be drawn there")


@needs_chrome
@needs_ffmpeg
def test_a_layer_png_is_not_simply_blank(tmp_path):
    """Guards the test above from passing because nothing was drawn at all."""
    import cards
    import make_short as M
    pngs = M.media_layers({"credit": "Imagery: placeholder"}, cards.brand_tokens(None),
                          tmp_path, 0)
    alpha = _alpha_bytes(pngs[0], media.credit_box(M.RW, M.RH))
    assert max(alpha) > 0, "the credit plate drew nothing inside its own box"


@needs_chrome
@needs_ffmpeg
def test_a_media_scene_composites_into_a_short_ready_mp4(tmp_path):
    """The real encode: footage + layers + audio -> one part of a Short, at Short specs."""
    import cards
    import make_short as M
    wav = tmp_path / "narration.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=mono", "-t", "2", str(wav)],
                   check=True, capture_output=True, timeout=120)
    scene = {"credit": "Imagery: placeholder",
             "overlay": {"template": "countdown",
                         "data": {"heading": "Composite", "subheading": "", "items":
                                  [{"rank": 1, "label": "One row", "value": 1}],
                                  "footer": "kdeskaccounting.com"}}}
    layers = M.media_layers(scene, cards.brand_tokens(None), tmp_path, 0)
    out = M.encode_media_scene(ASSETS / "placeholder-clip.mp4", "clip", layers, wav,
                               4.0, 30, tmp_path / "scene_0.mp4")
    assert out.exists() and out.stat().st_size > 10_000
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,pix_fmt",
         "-show_entries", "format=duration", "-of", "json", str(out)],
        capture_output=True, text=True, timeout=120)
    info = json.loads(probe.stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (video["width"], video["height"]) == (M.OUT_W, M.OUT_H) == (1080, 1920)
    assert video["r_frame_rate"] == "30/1" and video["codec_name"] == "h264"
    # Limited range like every other scene kind, so `-c:v copy` concat has nothing to jump.
    assert video["pix_fmt"] == "yuv420p"
    assert audio["codec_name"] == "aac" and audio["sample_rate"] == "48000"
    # The 3-second source was looped and trimmed to the 4-second scene, not cut short.
    assert abs(float(info["format"]["duration"]) - 4.0) < 0.15


# --- the driver --------------------------------------------------------------------------

@needs_venv
def test_build_video_frames_only_renders_every_media_scene():
    build = REPO / "scripts" / "video" / "build" / "media-demo"
    # clear everything this run should produce, but keep build/audio: narration is cached by
    # text hash and re-synthesizing it costs a minute of Kokoro for no extra coverage.
    shutil.rmtree(build / "frames", ignore_errors=True)
    shutil.rmtree(build / "recalc", ignore_errors=True)
    (build / "src.xlsx").unlink(missing_ok=True)
    proc = _run([str(BUILD_VIDEO), "--spec", str(SPEC), "--frames-only"])
    assert proc.returncode == 0, proc.stderr[-2000:]
    frames = build / "frames"
    for i in range(2):
        png = frames / f"scene_{i:02d}.png"
        assert png.exists(), f"{png} missing\n{proc.stdout}"
        assert png.stat().st_size > 10_000, f"{png} is suspiciously small"
    focus = json.loads((frames / "focus.json").read_text())
    assert all(focus[str(i)]["static"] is True for i in range(2))
    assert "media" in proc.stdout
    # no workbook was staged or recalculated: the spec has no `source:` key
    assert not (build / "src.xlsx").exists()
    assert not (build / "recalc").exists()
    assert "recalc" not in proc.stdout


@needs_venv
def test_build_video_renders_a_media_spec_that_lives_outside_the_repo(tmp_path):
    """A second venture keeps its spec in its own repo; `src:` resolves against THAT repo."""
    root = tmp_path / "parksheet"
    (root / ".git").mkdir(parents=True)
    (root / "video").mkdir()
    (root / "media").mkdir()
    shutil.copy(ASSETS / "placeholder-still.jpg", root / "media" / "shot.jpg")
    shutil.copy(ASSETS / "placeholder-clip.mp4", root / "media" / "clip.mp4")
    spec = root / "video" / "scenes.yaml"
    # Both srcs are rewritten, not just the one this run renders: the preflight validates
    # every media scene in the spec, which is the point of it being a preflight.
    spec.write_text(
        SPEC.read_text(encoding="utf-8")
        .replace("slug: media-demo", "slug: media-demo-external")
        .replace("marketing/video/media-demo/assets/placeholder-still.jpg", "media/shot.jpg")
        .replace("marketing/video/media-demo/assets/placeholder-clip.mp4", "media/clip.mp4"),
        encoding="utf-8")
    build = REPO / "scripts" / "video" / "build" / "media-demo-external"
    shutil.rmtree(build, ignore_errors=True)
    try:
        proc = _run([str(BUILD_VIDEO), "--spec", str(spec), "--frames-only", "--scenes", "0"])
        assert proc.returncode == 0, proc.stderr[-2000:]
        assert (build / "frames" / "scene_00.png").stat().st_size > 10_000
    finally:
        shutil.rmtree(build, ignore_errors=True)


@needs_venv
def test_a_still_with_no_credit_stops_the_render(tmp_path):
    """The attribution rule is enforced by the pipeline, not only by review."""
    spec = tmp_path / "scenes.yaml"
    spec.write_text(SPEC.read_text(encoding="utf-8")
                    .replace("slug: media-demo", "slug: media-demo-nocredit")
                    .replace('    credit: "Imagery: placeholder, generated with ffmpeg"\n', ""),
                    encoding="utf-8")
    build = REPO / "scripts" / "video" / "build" / "media-demo-nocredit"
    try:
        proc = _run([str(BUILD_VIDEO), "--spec", str(spec), "--frames-only"], timeout=300)
        assert proc.returncode != 0
        assert "credit" in proc.stderr
    finally:
        shutil.rmtree(build, ignore_errors=True)
