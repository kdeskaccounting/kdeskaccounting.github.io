"""End-to-end: the media-demo spec renders through the real pipeline.

Three layers of guard, each skipping on what it actually needs:

  * the demo's committed assets — stdlib only, always runs;
  * the composite — needs ffmpeg and a headless Chrome, and proves against real pixels that
    nothing we draw covers the attribution zone, or the Google Earth mark measured inside
    it;
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


def test_the_demo_is_a_mixed_spec():
    """Card and media in one spec is the case the `-c:v copy` concat has to survive."""
    text = SPEC.read_text(encoding="utf-8")
    assert "- kind: card" in text and "- kind: media" in text


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


_NONZERO = bytes(0 if v == 0 else 1 for v in range(256))


def _alpha_bbox(png, w, h):
    """The tight (left, top, right, bottom) box of everything `png` actually painted.

    The same Chrome -> PNG -> ffmpeg path the transparency tests use, read the other way
    round: instead of "is this region empty", "where did the ink land". None when the page
    drew nothing at all.
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(png), "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
        capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stderr.decode()[-2000:]
    alpha = proc.stdout[3::4]
    assert len(alpha) == w * h, f"expected a {w}x{h} frame, got {len(alpha)} alpha samples"
    top = bottom = left = right = None
    for y in range(h):
        row = alpha[y * w:(y + 1) * w].translate(_NONZERO)
        first = row.find(b"\x01")
        if first < 0:
            continue
        last = row.rfind(b"\x01")
        top = y if top is None else top
        bottom = y
        left = first if left is None else min(left, first)
        right = last if right is None else max(right, last)
    return None if top is None else (left, top, right + 1, bottom + 1)


@needs_chrome
@needs_ffmpeg
@pytest.mark.parametrize("layer", ["overlay", "credit"])
def test_the_layer_pngs_are_fully_transparent_over_the_attribution_zone(tmp_path, layer):
    """The claim the boxes make, checked against the pixels Chrome actually drew.

    Both the zone and the measured mark inside it: the zone is the rule the code enforces,
    the mark is the thing on the real Earth Studio frame that the rule exists for.
    """
    import cards
    import make_short as M
    import test_media as TM
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
    for what, box in (("attribution zone", media.watermark_box(M.RW, M.RH)),
                      ("measured Google Earth mark", TM.mark_box(M.RW, M.RH))):
        alpha = _alpha_bytes(pngs[0], box)
        assert alpha, "the crop produced no pixels"
        assert max(alpha) == 0, (
            f"the {layer} layer paints {sum(1 for a in alpha if a)} pixels inside the "
            f"{what} {box} — nothing may be drawn there")


@needs_chrome
@needs_ffmpeg
@pytest.mark.parametrize("credit", [
    "Imagery: Google Earth, Maxar Technologies",          # the Earth Studio line
    "Photo: Some Photographer Name / CC BY 2.0",          # the longest realistic Commons line
])
def test_the_narrowed_credit_plate_fits_a_real_credit_in_two_lines(tmp_path, credit):
    """The plate lost a third of its width when the zone widened to x >= 0.45. Does it fit?

    media.credit_box says where the plate MAY go; only Chrome knows where the text actually
    went, and a credit that overflows its box or spills toward the mark is a licence problem
    rather than a layout one. So this measures the ink: it must stay inside the box
    horizontally, sit on the box's bottom edge, and wrap to at most two lines — beyond that
    the plate is climbing the frame one word at a time and CREDIT_FS_UNITS is too large.

    Growing UPWARD past the box's nominal top is allowed and tested for separately below:
    the box is a floor and a right edge, not a clip rectangle. Attribution that is cut off
    is not attribution.
    """
    import cards
    import render_sheets as R2
    brand = cards.brand_tokens(None)
    w, h = 1296, 2304
    html = tmp_path / "credit.html"
    html.write_text(media.credit_plate_html(credit, brand, w, h), encoding="utf-8")
    png = tmp_path / "credit.png"
    R2.screenshot(html, png, w, h, transparent=True)

    drawn = _alpha_bbox(png, w, h)
    assert drawn is not None, "the credit plate drew nothing at all"
    box_left, _box_top, box_right, box_bottom = media.credit_box(w, h)
    assert drawn[0] >= box_left, f"the plate {drawn} starts left of its box"
    assert drawn[2] <= box_right, (
        f"the plate {drawn} overflows credit_box's right edge {box_right} and is heading for "
        f"the attribution zone at x={media.watermark_box(w, h)[0]}")
    assert abs(drawn[3] - box_bottom) <= 2, "the plate is anchored to the box's bottom edge"
    assert not media.boxes_overlap(drawn, media.watermark_box(w, h))

    font_px = media.CREDIT_FS_UNITS * h / 100.0
    lines = round((drawn[3] - drawn[1] - 2 * 0.55 * font_px) / (1.24 * font_px))
    assert lines <= 2, (
        f"{credit!r} wraps to {lines} lines in a {box_right - box_left}px plate; widen the "
        f"plate or drop CREDIT_FS_UNITS")


@needs_chrome
@needs_ffmpeg
def test_a_credit_too_long_for_the_plate_grows_upward_into_free_frame(tmp_path):
    """The escape valve: a three-provider credit wraps further UP, and still clears the card."""
    import cards
    brand = cards.brand_tokens(None)
    import render_sheets as R2
    w, h = 1296, 2304
    credit = "Imagery: Google Earth, Landsat / Copernicus, Maxar Technologies"
    html = tmp_path / "long.html"
    html.write_text(media.credit_plate_html(credit, brand, w, h), encoding="utf-8")
    png = tmp_path / "long.png"
    R2.screenshot(html, png, w, h, transparent=True)

    drawn = _alpha_bbox(png, w, h)
    assert drawn is not None
    assert drawn[1] < media.credit_box(w, h)[1], "a long credit is supposed to grow upward"
    assert drawn[1] > media.overlay_box(w, h)[3], "it grew into the card overlay's box"
    assert drawn[2] <= media.credit_box(w, h)[2]
    assert not media.boxes_overlap(drawn, media.watermark_box(w, h))


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


# --- the joins, on the rendered demo ---------------------------------------------------------

DEMO_BUILD = REPO / "scripts" / "video" / "build" / "media-demo"
DEMO_SHORT = DEMO_BUILD / "media-demo-short.mp4"
DEMO_CONCAT = DEMO_BUILD / "short" / "concat.txt"

#: The silence a viewer may hear at a cut: make_short.SCENE_PAD after the last word of one
#: scene plus narrate.LEAD_IN_S before the first of the next. Anything longer and the
#: narration audibly "cuts out" between clips, which is what this number exists to stop.
MAX_JOIN_GAP = 0.6


def _part_spans():
    """(name, start, end) of every part of the rendered demo, from the concat list it used."""
    import make_short as M
    spans, at = [], 0.0
    for line in DEMO_CONCAT.read_text(encoding="utf-8").splitlines():
        if line.startswith("file "):
            part = pathlib.Path(line[5:].strip().strip("'"))
            seconds = M.dur_of(part)
            spans.append((part.name, at, at + seconds))
            at += seconds
    return spans


def _silences(video, floor="-45dB", minimum=0.15):
    """(start, end) of every stretch silencedetect calls silence, in order."""
    import make_short as M
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(video), "-af",
         f"silencedetect=noise={floor}:d={minimum}", "-f", "null", "-"],
        capture_output=True, text=True, timeout=600)
    out, start = [], None
    for line in proc.stderr.splitlines():
        if "silence_start:" in line:
            start = float(line.split("silence_start:")[1].split()[0])
        elif "silence_end:" in line and start is not None:
            out.append((start, float(line.split("silence_end:")[1].split()[0])))
            start = None
    if start is not None:
        out.append((start, M.dur_of(video)))
    return out


def test_the_pad_and_the_lead_in_add_up_to_the_join_budget():
    """Arithmetic, before any render: this is why the gap fits."""
    import make_short as M
    import narrate
    assert M.SCENE_PAD + narrate.LEAD_IN_S <= MAX_JOIN_GAP


@needs_ffmpeg
@pytest.mark.skipif(not DEMO_CONCAT.exists(),
                    reason=f"{DEMO_SHORT} has not been rendered in this checkout")
def test_the_rendered_demo_has_no_dead_air_at_a_scene_join():
    """The defect: ~1.2 s of silence at every cut, because each part was narration + 0.6 s."""
    spans = _part_spans()
    assert len(spans) >= 2, "a one-part Short has no joins to measure"
    quiet = _silences(DEMO_SHORT)
    measured = 0
    for (name, _lo, boundary), (next_name, _nlo, _nhi) in zip(spans, spans[1:]):
        if next_name == "end.mp4":
            continue                    # the closing plate is 1.5 s of deliberate silence
        covering = [(s, e) for s, e in quiet if s <= boundary <= e]
        measured += 1
        if not covering:
            continue                    # no silence detected across the cut at all: ideal
        start, end = covering[0]
        gap = end - start
        assert gap <= MAX_JOIN_GAP + 0.05, (
            f"{gap:.2f}s of silence across the join at {boundary:.2f}s "
            f"({name} -> {next_name}); the budget is {MAX_JOIN_GAP}s — make_short.SCENE_PAD "
            f"plus narrate.LEAD_IN_S")
    assert measured, "every join was the end-card plate; nothing was actually checked"


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
    for i in range(3):
        png = frames / f"scene_{i:02d}.png"
        assert png.exists(), f"{png} missing\n{proc.stdout}"
        assert png.stat().st_size > 10_000, f"{png} is suspiciously small"
    focus = json.loads((frames / "focus.json").read_text())
    assert all(focus[str(i)]["static"] is True for i in range(3))
    assert "media" in proc.stdout
    assert "card" in proc.stdout, "the demo is a MIXED spec; scene 1 is a plain card"
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


# --- the concat claim, against a real mixed render ----------------------------------------

@needs_chrome
@needs_ffmpeg
def test_a_card_part_and_a_media_part_concatenate_into_one_continuous_stream(tmp_path):
    """The load-bearing claim: parts are joined with `-c:v copy`, so a media scene has to
    encode to exactly the stream a card scene does. If it does not, the concat either fails
    or produces a file whose second half is a different stream — which is why this asserts
    the JOINED file, not the two parts."""
    import cards
    import make_short as M
    wav = tmp_path / "narration.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=mono", "-t", "3", str(wav)],
                   check=True, capture_output=True, timeout=120)
    brand = cards.brand_tokens(None)
    data = {"heading": "A card scene", "subheading": "Text on a brand background",
            "items": [{"rank": 1, "label": "Row", "value": 1}], "footer": "kdeskaccounting.com"}

    card_png = tmp_path / "scene_0.png"
    R.render_card_scene(card_png, "ranked_list", data, None, M.RW, M.RH, html_dir=tmp_path)
    card_part = M.encode_scene(card_png, wav, 3.0, 30)

    layers = M.media_layers({"credit": "Imagery: placeholder"}, brand, tmp_path, 1)
    media_part = M.encode_media_scene(ASSETS / "placeholder-clip.mp4", "clip", layers, wav,
                                      3.0, 30, tmp_path / "scene_1.mp4")

    lst = tmp_path / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in (card_part, media_part)))
    joined = tmp_path / "mixed.mp4"
    M.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           str(joined)])

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,color_range",
         "-show_entries", "format=duration,nb_streams", "-of", "json", str(joined)],
        capture_output=True, text=True, timeout=120)
    info = json.loads(probe.stdout)
    # One video stream and one audio stream — not two of each, which is what a stream the
    # concat demuxer refused to join would look like.
    assert int(info["format"]["nb_streams"]) == 2
    videos = [s for s in info["streams"] if s["codec_type"] == "video"]
    assert len(videos) == 1
    assert (videos[0]["width"], videos[0]["height"]) == (M.OUT_W, M.OUT_H)
    assert videos[0]["r_frame_rate"] == "30/1" and videos[0]["pix_fmt"] == "yuv420p"
    assert videos[0]["color_range"] == "tv"
    assert abs(float(info["format"]["duration"]) - 6.0) < 0.3, "both parts must be present"

    # And the two parts really did agree, which is what let `-c:v copy` work.
    def stream_of(path):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name,profile,width,height,r_frame_rate,pix_fmt,color_range",
             "-of", "json", str(path)], capture_output=True, text=True, timeout=120)
        return json.loads(out.stdout)["streams"][0]

    assert stream_of(card_part) == stream_of(media_part)
