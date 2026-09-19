"""scripts/video/media.py — the `media` scene kind: real footage or a still, under a card.

A `media` scene points at a file (`src:`), says how it should move (`motion:`), names where
the imagery came from (`credit:`) and may carry a card `overlay:` on the lower part of the
frame. Everything here is pure string/geometry work — no ffmpeg, no Chrome, no filesystem
except the tmp_path files the resolver tests create — so it runs in the bare
`uv run --with pytest` environment.

The geometry tests are the load-bearing ones. Earth Studio burns its attribution watermark
into the BOTTOM-RIGHT of every frame it exports; anything we draw there covers an attribution
we are contractually required to leave visible. The exclusion zone is a constant, and these
tests are what stop a later layout tweak from sliding a plate into it.
"""
import os
import pathlib
import re

import pytest

import captions
import cards
import media

GOLDEN = pathlib.Path(__file__).parent / "golden"

BRAND = {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"}
CREDIT = "Imagery: Google Earth, Maxar Technologies"
OVERLAY = {
    "template": "ranked_list",
    "data": {
        "heading": "Shortest waits right now",
        "subheading": "Magic Kingdom · minutes",
        "items": [
            {"rank": 1, "label": "Tomorrowland Speedway", "value": 5},
            {"rank": 2, "label": "The Barnstormer", "value": 10},
            {"rank": 3, "label": "Dumbo the Flying Elephant", "value": 15},
        ],
        "footer": "Powered by Queue-Times.com",
    },
}
CHANGED_OVERLAY = {
    "template": "changed",
    "data": {
        "heading": "What changed this week",
        "subheading": "Walt Disney World",
        "items": [
            {"label": "Test Track",
             "value": "Reopened on Tuesday after a long refurbishment, and it is already "
                      "the busiest ride at EPCOT."},
            {"label": "Space Mountain",
             "value": "Goes down for refurbishment on Monday and stays closed until early "
                      "spring next year."},
        ],
        "footer": "Powered by Queue-Times.com",
    },
}

#: The canvases the pipeline actually renders at: the Short composite, the delivered Short,
#: and build_video's landscape frame. Geometry must hold on every one of them.
CANVASES = [(1296, 2304), (1080, 1920), (2400, 1350)]


# --- module surface -------------------------------------------------------------------

def test_is_media_detects_the_kind():
    assert media.is_media({"kind": "media"}) is True
    assert media.is_media({"kind": "card"}) is False
    assert media.is_media({"kind": "sheet", "sheet": "Inputs"}) is False
    assert media.is_media({}) is False


def test_the_motions_are_the_ones_the_contract_names():
    assert media.MOTIONS == ("clip", "kenburns", "hold",
                             "punch", "push", "pan_left", "pan_right", "burst")


def test_a_still_defaults_to_kenburns_and_footage_to_clip():
    assert media.default_motion("image") == "kenburns"
    assert media.default_motion("video") == "clip"


# --- resolve_src ----------------------------------------------------------------------

def _repo(tmp_path, marker=".git"):
    """A spec inside a repo: <root>/<marker>, <root>/video/scenes.yaml, <root>/media/…"""
    root = tmp_path / "parksheet"
    root.mkdir(parents=True)
    if marker == ".git":
        (root / marker).mkdir()
    else:
        (root / marker).write_text("[project]\n")
    (root / "video").mkdir()
    spec = root / "video" / "scenes.yaml"
    spec.write_text("slug: x\n")
    (root / "media" / "earth").mkdir(parents=True)
    asset = root / "media" / "earth" / "magic-kingdom.mp4"
    asset.write_bytes(b"\0")
    return root, spec, asset


def test_resolve_src_is_relative_to_the_spec_repos_root_not_the_spec_directory(tmp_path):
    """The contract says repo-relative: `media/earth/x.mp4` from a spec in `video/`."""
    root, spec, asset = _repo(tmp_path)
    assert media.resolve_src(spec, "media/earth/magic-kingdom.mp4") == asset.resolve()


def test_resolve_src_finds_the_root_by_pyproject_when_there_is_no_git_dir(tmp_path):
    root, spec, asset = _repo(tmp_path, marker="pyproject.toml")
    assert media.resolve_src(spec, "media/earth/magic-kingdom.mp4") == asset.resolve()


def test_resolve_src_takes_an_absolute_path_as_given(tmp_path):
    _root, spec, asset = _repo(tmp_path)
    assert media.resolve_src(spec, str(asset)) == asset.resolve()


def test_resolve_src_falls_back_to_the_spec_directory_when_no_repo_marker_exists(tmp_path):
    """A loose spec in a scratch directory still renders; it just has no repo above it."""
    spec = tmp_path / "scenes.yaml"
    spec.write_text("slug: x\n")
    asset = tmp_path / "shot.png"
    asset.write_bytes(b"\0")
    assert media.resolve_src(spec, "shot.png") == asset.resolve()


def test_resolve_src_names_the_spec_the_root_and_the_path_it_tried(tmp_path):
    """The error a caller in another repo sees must say which root it was resolved against."""
    root, spec, _asset = _repo(tmp_path)
    with pytest.raises(FileNotFoundError) as e:
        media.resolve_src(spec, "media/earth/missing.mp4")
    text = str(e.value)
    assert "media/earth/missing.mp4" in text
    assert str(root.resolve()) in text
    assert str(spec) in text


@pytest.mark.parametrize("src", ["../../etc/passwd", "media/../../../etc/passwd"])
def test_resolve_src_refuses_a_path_that_climbs_out_of_the_spec_repo(tmp_path, src):
    """A spec is data from another repo: it must not be able to name a file outside it."""
    _root, spec, _asset = _repo(tmp_path)
    with pytest.raises(ValueError) as e:
        media.resolve_src(spec, src)
    assert "outside" in str(e.value)


# --- media_kind -----------------------------------------------------------------------

@pytest.mark.parametrize("name,kind", [
    ("a.mp4", "video"), ("a.MP4", "video"), ("a.mov", "video"), ("a.m4v", "video"),
    ("a.jpg", "image"), ("a.JPEG", "image"), ("a.png", "image"),
])
def test_media_kind_reads_the_suffix(name, kind):
    assert media.media_kind(pathlib.Path("/tmp") / name) == kind


def test_media_kind_rejects_a_suffix_it_cannot_render_and_lists_the_ones_it_can():
    with pytest.raises(ValueError) as e:
        media.media_kind(pathlib.Path("/tmp/a.gif"))
    assert ".mp4" in str(e.value) and ".png" in str(e.value)


# --- the credit rule ------------------------------------------------------------------

def test_a_still_must_carry_a_credit():
    """Stock/Earth stills are licensed on attribution; a video may credit itself on screen."""
    with pytest.raises(ValueError) as e:
        media.check_credit("image", None)
    assert "credit" in str(e.value)


def test_a_video_may_omit_the_credit():
    assert media.check_credit("video", None) is None
    assert media.check_credit("image", CREDIT) is None


# --- motion vs kind -------------------------------------------------------------------
#
# The wrong pairing is not a style choice. `clip` on a still hangs ffmpeg forever (the input
# is looped, an image2 input restarts PTS every pass, so `trim=duration=` is never reached and
# `-t` never fires: 0 bytes out, still spinning at two minutes). `kenburns` on footage
# silently freezes frame 0, because zoompan's `d=` counts INPUT frames, not output ones.

def test_the_motions_allowed_for_each_kind():
    assert media.MOTIONS_FOR == {
        "image": ("kenburns", "hold", "punch", "push", "pan_left", "pan_right", "burst"),
        "video": ("clip", "hold"),
    }


@pytest.mark.parametrize("kind,motion", [
    ("image", "kenburns"), ("image", "hold"), ("video", "clip"), ("video", "hold"),
])
def test_check_motion_allows_every_sensible_pairing(kind, motion):
    assert media.check_motion(kind, motion) is None


def test_clip_on_a_still_is_refused_because_it_hangs_ffmpeg():
    with pytest.raises(ValueError) as e:
        media.check_motion("image", "clip")
    text = str(e.value)
    assert "clip" in text and "image" in text
    assert "kenburns" in text and "hold" in text     # names the way out
    assert "never" in text or "forever" in text      # says why, not just no


def test_kenburns_on_footage_is_refused_because_it_freezes_frame_zero():
    with pytest.raises(ValueError) as e:
        media.check_motion("video", "kenburns")
    text = str(e.value)
    assert "kenburns" in text and "video" in text
    assert "clip" in text and "hold" in text
    assert "freeze" in text or "frozen" in text


def test_check_motion_is_also_the_gate_on_an_unknown_motion():
    """One call validates the motion, so no caller can check the pair but not the name."""
    with pytest.raises(ValueError) as e:
        media.check_motion("image", "wiggle")
    assert "wiggle" in str(e.value)


def test_the_default_motion_is_always_an_allowed_pairing():
    for kind in ("image", "video"):
        assert media.check_motion(kind, media.default_motion(kind)) is None


# --- validate_spec (the preflight) ----------------------------------------------------

def _media_spec(tmp_path, **overrides):
    root = tmp_path / "parksheet"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir(exist_ok=True)
    (root / "media").mkdir(exist_ok=True)
    (root / "media" / "shot.png").write_bytes(b"\0")
    (root / "media" / "clip.mp4").write_bytes(b"\0")
    spec_path = root / "scenes.yaml"
    spec_path.write_text("slug: x\n")
    scene = {"kind": "media", "src": "media/shot.png", "credit": CREDIT}
    scene.update(overrides)
    spec = {"scenes": [{"kind": "card", "template": "ranked_list"},
                       {"kind": "media", "src": "media/clip.mp4"},
                       scene]}
    return spec, spec_path


def test_validate_spec_passes_a_good_spec(tmp_path):
    spec, spec_path = _media_spec(tmp_path)
    assert media.validate_spec(spec, spec_path) is None


def test_validate_spec_ignores_scenes_that_are_not_media(tmp_path):
    """A card or sheet scene has no src, credit or motion to check."""
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("slug: x\n")
    assert media.validate_spec({"scenes": [{"kind": "card"}, {"sheet": "Inputs"}]},
                               spec_path) is None
    assert media.validate_spec({}, spec_path) is None


@pytest.mark.parametrize("override,needle", [
    ({"motion": "wiggle"}, "wiggle"),
    ({"motion": "clip"}, "clip"),                       # clip on a still
    ({"credit": None}, "credit"),                       # a still with no credit
    ({"src": "media/gone.png"}, "gone.png"),
    ({"src": "media/notes.txt"}, ".txt"),
    ({"fill": "stretch"}, "stretch"),                   # the fill keys are preflighted too,
    ({"focus": [0.5, 1.4]}, "focus"),                   # so a typo is not silently ignored
])
def test_validate_spec_catches_every_per_scene_error(tmp_path, override, needle):
    spec, spec_path = _media_spec(tmp_path, **override)
    with pytest.raises((ValueError, FileNotFoundError)) as e:
        media.validate_spec(spec, spec_path)
    assert needle in str(e.value)


def test_validate_spec_names_the_scene_index_that_is_wrong(tmp_path):
    """The bad scene is the third one; the message has to say so, not just what is wrong."""
    spec, spec_path = _media_spec(tmp_path, motion="wiggle")
    with pytest.raises(ValueError) as e:
        media.validate_spec(spec, spec_path)
    assert "scene 2" in str(e.value)


def test_validate_spec_rejects_a_media_scene_with_no_src(tmp_path):
    spec, spec_path = _media_spec(tmp_path)
    spec["scenes"][2].pop("src")
    with pytest.raises(ValueError) as e:
        media.validate_spec(spec, spec_path)
    assert "src" in str(e.value) and "scene 2" in str(e.value)


def test_validate_spec_checks_a_kenburns_video_too(tmp_path):
    spec, spec_path = _media_spec(tmp_path)
    spec["scenes"][1]["motion"] = "kenburns"
    with pytest.raises(ValueError) as e:
        media.validate_spec(spec, spec_path)
    assert "scene 1" in str(e.value) and "kenburns" in str(e.value)


def test_validate_spec_checks_scenes_the_short_does_not_even_use(tmp_path):
    """The spec is the contract; a scene nobody selected is still a scene that must be valid."""
    spec, spec_path = _media_spec(tmp_path, motion="wiggle")
    spec["short"] = {"hook": "h", "scenes": [0], "cta": "c"}
    with pytest.raises(ValueError):
        media.validate_spec(spec, spec_path)


# --- the attribution exclusion zone ---------------------------------------------------
#
# The zone is MEASURED, not guessed, and it is not really a corner. On the first real Earth
# Studio portrait render (1080x1920, cloud video, Attribution Position bottom-right at its
# maximum offsets) the "Google Earth" wordmark lands at x 0.495-0.815 and y 0.909-0.933 of
# the frame, with the smaller data-provider line under it reaching about y 0.955. Earth
# Studio will not push it further right or lower on a portrait canvas, so that rectangle is
# the worst case the zone has to contain — and it sits well left of, and well above, the
# bottom-right corner, which is why the old 20% x 8% corner zone missed the mark completely.
#
# EARTH_MARK_FRAC rounds that measurement outward. Every test below is written against it or
# against the boxes, never against the constants, so re-measuring is a one-line change here.
EARTH_MARK_FRAC = (0.49, 0.90, 0.82, 0.96)


def mark_box(w, h):
    """The measured Google Earth mark as (left, top, right, bottom) pixels on a w x h frame."""
    left, top, right, bottom = EARTH_MARK_FRAC
    return (round(w * left), round(h * top), round(w * right), round(h * bottom))


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_exclusion_zone_contains_the_measured_google_earth_mark(w, h):
    """This is what pins the constants: the zone is sized FROM the render, not from a guess."""
    zone_left, zone_top, zone_right, zone_bottom = media.watermark_box(w, h)
    left, top, right, bottom = mark_box(w, h)
    assert zone_left <= left, "the mark starts left of the zone; widen WATERMARK_W_FRAC"
    assert zone_top <= top, "the mark starts above the zone; grow WATERMARK_H_FRAC"
    assert zone_right >= right and zone_bottom >= bottom


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_watermark_box_is_anchored_to_the_bottom_right_corner(w, h):
    left, top, right, bottom = media.watermark_box(w, h)
    assert (right, bottom) == (w, h)
    assert left == round(w * (1 - media.WATERMARK_W_FRAC))
    assert top == round(h * (1 - media.WATERMARK_H_FRAC))


@pytest.mark.parametrize("w,h", CANVASES)
def test_nothing_the_renderer_draws_touches_the_measured_mark(w, h):
    """The whole rule in one assertion, against the measurement rather than the constants.

    Three plates can reach the lower frame: the card overlay, the credit plate, and the
    caption band (which is placed by captions.py but fenced by this zone). None of them may
    put a pixel where Earth Studio printed its attribution.
    """
    mark = mark_box(w, h)
    band = captions.caption_box(w, h)
    squeezed = captions.caption_box(w, h, card_top=media.overlay_box(w, h)[1])
    for name, box in (("overlay", media.overlay_box(w, h)),
                      ("credit", media.credit_box(w, h)),
                      ("caption band", band), ("squeezed band", squeezed)):
        assert not media.boxes_overlap(box, mark), f"the {name} box covers the Earth mark"


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_credit_plate_never_reaches_the_attribution_watermark(w, h):
    assert not media.boxes_overlap(media.credit_box(w, h), media.watermark_box(w, h))


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_credit_plate_sits_in_the_lower_left(w, h):
    left, top, right, bottom = media.credit_box(w, h)
    assert left < w / 2                    # left-anchored
    assert right <= media.watermark_box(w, h)[0]   # stops at the zone's left edge
    assert top > h / 2                     # lower half


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_credit_plate_is_still_wide_enough_to_read(w, h):
    """The zone's left edge moved in to 45% of the width, so the plate lost a third of it.

    A plate narrower than a handful of em is one word a line, which is the point at which
    "the credit wraps" stops being acceptable attribution. The Chrome-measured check that it
    really does fit a full credit in two lines is in tests/test_media_scene_e2e.py.
    """
    left, _top, right, _bottom = media.credit_box(w, h)
    font_px = media.CREDIT_FS_UNITS * h / 100.0
    assert (right - left) / font_px >= 10


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_overlay_bottom_edge_stays_above_the_attribution_watermark(w, h):
    assert media.overlay_box(w, h)[3] < media.watermark_box(w, h)[1]
    assert not media.boxes_overlap(media.overlay_box(w, h), media.watermark_box(w, h))


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_overlay_keeps_at_least_forty_percent_of_the_frame_for_the_card(w, h):
    """The zone got 4 points taller, which comes straight off the bottom of the card plate.

    Below roughly 40% of the frame a ranked_list stops being a card and becomes a strip, so
    this is the floor that says whether CLEARANCE_FRAC or OVERLAY_TOP_FRAC has to give.
    """
    left, top, right, bottom = media.overlay_box(w, h)
    assert (bottom - top) / h >= 0.40
    assert left > 0 and right < w          # inside the side safe margins
    assert top > captions.caption_box(w, h)[3]     # and clear below the caption band


@pytest.mark.parametrize("w,h", CANVASES)
def test_the_credit_plate_and_the_overlay_do_not_collide(w, h):
    assert not media.boxes_overlap(media.credit_box(w, h), media.overlay_box(w, h))


@pytest.mark.parametrize("w,h", CANVASES)
def test_every_box_stays_inside_the_frame(w, h):
    for box in (media.credit_box(w, h), media.overlay_box(w, h), media.watermark_box(w, h)):
        left, top, right, bottom = box
        assert 0 <= left < right <= w
        assert 0 <= top < bottom <= h


def test_boxes_overlap_is_a_real_rectangle_intersection():
    assert media.boxes_overlap((0, 0, 10, 10), (5, 5, 15, 15)) is True
    assert media.boxes_overlap((0, 0, 10, 10), (10, 0, 20, 10)) is False   # edge-to-edge
    assert media.boxes_overlap((0, 0, 10, 10), (0, 10, 10, 20)) is False


# --- credit_plate_html ----------------------------------------------------------------

def test_credit_plate_html_is_a_transparent_page_at_the_requested_canvas():
    html = media.credit_plate_html(CREDIT, cards.brand_tokens(BRAND), 1296, 2304)
    assert "width:1296px" in html and "height:2304px" in html
    assert "background:transparent" in html


def test_credit_plate_html_places_the_plate_in_the_lower_left_by_the_box():
    left, top, right, bottom = media.credit_box(1296, 2304)
    html = media.credit_plate_html(CREDIT, cards.brand_tokens(BRAND), 1296, 2304)
    assert f"left:{left}px" in html
    assert f"bottom:{2304 - bottom}px" in html
    assert f"max-width:{right - left}px" in html


def test_credit_plate_html_lets_a_long_credit_wrap_rather_than_crop_it():
    """Nothing may clip the credit: no line clamp, no nowrap, no overflow:hidden on it."""
    long_credit = CREDIT + " and a very long list of further imagery providers indeed"
    html = media.credit_plate_html(long_credit, cards.brand_tokens(BRAND), 1296, 2304)
    plate = html.split(".credit{")[1].split("}")[0]
    assert "line-clamp" not in plate
    assert "nowrap" not in plate
    assert "overflow:hidden" not in plate
    assert long_credit in html


def test_credit_plate_html_escapes_the_credit():
    html = media.credit_plate_html('Imagery: <script>x</script> & "co"',
                                   cards.brand_tokens(BRAND), 1296, 2304)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html


def test_credit_plate_html_uses_the_brand_tokens():
    tokens = cards.brand_tokens({"bg": "#123456", "fg": "#ABCDEF"})
    html = media.credit_plate_html(CREDIT, tokens, 1296, 2304)
    assert "#123456" in html and "#ABCDEF" in html


def test_credit_plate_html_renders_the_credit_in_small_caps():
    html = media.credit_plate_html(CREDIT, cards.brand_tokens(BRAND), 1296, 2304)
    assert "small-caps" in html


def test_credit_plate_html_refuses_an_empty_credit():
    with pytest.raises(ValueError):
        media.credit_plate_html("  ", cards.brand_tokens(BRAND), 1296, 2304)


# --- overlay_html ---------------------------------------------------------------------

def test_overlay_html_is_the_card_renderer_boxed_into_the_lower_frame():
    left, top, right, bottom = media.overlay_box(1296, 2304)
    html = media.overlay_html(OVERLAY, cards.brand_tokens(BRAND), 1296, 2304)
    expected = cards.card_html(OVERLAY["template"], OVERLAY["data"], cards.brand_tokens(BRAND),
                               1296, 2304, transparent=True,
                               box=(left, top, right - left, bottom - top))
    assert html == expected


def test_overlay_html_carries_the_card_data_through():
    html = media.overlay_html(OVERLAY, cards.brand_tokens(BRAND), 1296, 2304)
    assert "Tomorrowland Speedway" in html and "Shortest waits right now" in html


def test_overlay_html_is_transparent_so_the_footage_shows_through():
    html = media.overlay_html(OVERLAY, cards.brand_tokens(BRAND), 1296, 2304)
    assert "background:transparent" in html
    assert "radial-gradient" not in html


def test_overlay_html_honours_every_card_template():
    for overlay in (OVERLAY, CHANGED_OVERLAY,
                    dict(OVERLAY, template="countdown")):
        assert media.overlay_html(overlay, cards.brand_tokens(BRAND), 1296, 2304)


def test_overlay_html_rejects_an_unknown_template_through_cards():
    with pytest.raises(ValueError):
        media.overlay_html({"template": "carousel", "data": {}},
                           cards.brand_tokens(BRAND), 1296, 2304)


# --- ffmpeg_video_filter --------------------------------------------------------------

def test_ffmpeg_video_filter_rejects_an_unknown_motion():
    with pytest.raises(ValueError) as e:
        media.ffmpeg_video_filter("pan", 5.0, 1296, 2304)
    assert "clip" in str(e.value) and "kenburns" in str(e.value)


@pytest.mark.parametrize("motion", ["clip", "kenburns", "hold"])
def test_every_motion_covers_the_nine_by_sixteen_frame_before_anything_else(motion):
    """Cover, not contain: a 16:9 source must fill 9:16 with no letterbox bars."""
    chain = media.ffmpeg_video_filter(motion, 5.0, 1296, 2304)
    assert chain.startswith("scale=1296:2304:force_original_aspect_ratio=increase,"
                            "crop=1296:2304")


def test_clip_trims_to_the_narrated_duration():
    chain = media.ffmpeg_video_filter("clip", 7.25, 1296, 2304)
    assert "trim=duration=7.250" in chain
    assert "setpts=PTS-STARTPTS" in chain
    assert "zoompan" not in chain


def test_clip_is_looped_at_the_input_so_a_short_source_still_fills_the_scene():
    """`loop` as a filter buffers raw frames; -stream_loop repeats the demuxer instead."""
    assert media.CLIP_INPUT_ARGS == ("-stream_loop", "-1")


def test_kenburns_zooms_from_one_to_one_point_zero_eight_over_the_scene():
    dur, fps = 6.0, 30
    n = 180
    chain = media.ffmpeg_video_filter("kenburns", dur, 1296, 2304)
    dz = (1.08 - 1.0) / n
    assert f"zoompan=z='min(zoom+{dz:.7f},1.08)'" in chain
    assert f":d={n}:" in chain
    assert f"s=1296x2304:fps={fps}" in chain
    assert "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" in chain


def test_kenburns_frame_count_is_the_ceiling_of_duration_times_thirty():
    assert ":d=181:" in media.ffmpeg_video_filter("kenburns", 6.01, 1296, 2304)
    assert ":d=180:" in media.ffmpeg_video_filter("kenburns", 6.0, 1296, 2304)


def test_hold_is_static_and_pads_the_frame_out_to_the_duration():
    chain = media.ffmpeg_video_filter("hold", 4.5, 1296, 2304)
    assert "tpad=stop_mode=clone:stop_duration=4.500" in chain
    assert "zoompan" not in chain and "trim" not in chain


@pytest.mark.parametrize("motion", ["clip", "kenburns", "hold"])
def test_every_chain_ends_at_the_requested_canvas_size(motion):
    chain = media.ffmpeg_video_filter(motion, 3.0, 1080, 1920)
    assert "scale=1080:1920" in chain and "crop=1080:1920" in chain


# --- the fill: crop a portrait source, blur behind a landscape one ---------------------
#
# Cropping a 16:9 photograph to 9:16 keeps under a third of its width. These say which
# sources get that and which get the whole picture over a blurred backdrop instead.

PORTRAIT = (1080, 1920)          # a phone video: 0.5625
LANDSCAPE = (1920, 1080)         # 16:9, the Earth Studio / stock-photo case: 1.78


def _graph(steps):
    return ";".join(steps)


@pytest.mark.parametrize("motion", ["clip", "kenburns", "hold"])
def test_a_portrait_source_is_the_single_cover_and_crop_chain_it_always_was(motion):
    """Nothing about an existing portrait render may move: same one chain, same labels."""
    steps = media.ffmpeg_video_steps(motion, 5.0, 1296, 2304, 30, *PORTRAIT)
    assert steps == [f"[0:v]{media.ffmpeg_video_filter(motion, 5.0, 1296, 2304, 30)}[m0]"]


def test_a_source_that_could_not_be_measured_keeps_the_crop():
    """probe_size returns None for anything ffprobe cannot read; that must not reframe it."""
    assert media.ffmpeg_video_steps("kenburns", 5.0, 1296, 2304, 30, None, None) == \
        [f"[0:v]{media.ffmpeg_video_filter('kenburns', 5.0, 1296, 2304, 30)}[m0]"]
    assert media.wants_blur_fill(None, None) is False
    assert media.wants_blur_fill(0, 0) is False


@pytest.mark.parametrize("src_w,src_h,blurred", [
    (1920, 1080, True),           # 16:9
    (4000, 3000, True),           # 4:3
    (1000, 1000, True),           # square
    (801, 1000, True),            # 0.801 — a hair past the line
    (1000, 1250, False),          # 0.80 exactly: the line itself still crops
    (1080, 1440, False),          # 3:4, 0.75: crops to 9:16 without losing the subject
    (1080, 1920, False),          # 9:16
])
def test_the_fill_branches_on_the_sources_aspect_ratio(src_w, src_h, blurred):
    assert media.wants_blur_fill(src_w, src_h) is blurred
    graph = _graph(media.ffmpeg_video_steps("hold", 3.0, 1080, 1920, 30, src_w, src_h))
    assert ("boxblur" in graph) is blurred
    assert (f"crop=1080:1920" in graph) is True   # the backdrop is still built by covering


def test_a_landscape_source_keeps_its_whole_frame_over_a_blurred_copy_of_itself():
    steps = media.ffmpeg_video_steps("kenburns", 5.0, 1080, 1920, 30, *LANDSCAPE)
    graph = _graph(steps)
    # one source, split in two: the backdrop is the SAME footage, not a still of it
    assert "[0:v]split=2[" in graph
    # the foreground is fitted INSIDE the frame — nothing is cropped off it
    assert "scale=1080:1920:force_original_aspect_ratio=decrease" in graph
    # the backdrop covers, blurs and dims
    assert f"boxblur={media.BLUR_RADIUS}:{media.BLUR_POWER}" in graph
    assert f"eq=brightness=-{media.BLUR_DARKEN}" in graph
    # and the sharp copy lands in the middle of it
    assert "overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2" in graph


def test_the_foreground_of_a_blur_fill_is_never_cropped():
    """`increase,crop` on the foreground would throw away exactly what this fix keeps."""
    steps = media.ffmpeg_video_steps("hold", 3.0, 1080, 1920, 30, *LANDSCAPE)
    fg = [s for s in steps if "force_original_aspect_ratio=decrease" in s]
    assert len(fg) == 1
    assert "crop=" not in fg[0] and "increase" not in fg[0]


@pytest.mark.parametrize("motion", ["clip", "kenburns", "hold"])
def test_the_motion_is_applied_to_the_finished_composite(motion):
    """Ken Burns drifts the photograph AND its backdrop; a clip is trimmed after compositing."""
    steps = media.ffmpeg_video_steps(motion, 5.0, 1296, 2304, 30, *LANDSCAPE)
    assert steps[-1].endswith(f"{media.motion_chain(motion, 5.0, 1296, 2304, 30)}[m0]")
    assert steps[-1].startswith("[m0_fill]")


@pytest.mark.parametrize("src", [PORTRAIT, LANDSCAPE])
@pytest.mark.parametrize("motion", ["clip", "kenburns", "hold"])
def test_every_graph_is_wired_from_the_named_input_to_the_named_output(motion, src):
    """Whichever branch runs, it reads [0:v] and writes [m0] — encode_media_scene's contract."""
    steps = media.ffmpeg_video_steps(motion, 4.0, 1296, 2304, 30, *src)
    assert steps[0].startswith("[0:v]")
    assert steps[-1].endswith("[m0]")
    produced, consumed = [], []
    for step in steps:
        head = re.match(r"^(?:\[([A-Za-z0-9_:]+)\])+", step)
        consumed += re.findall(r"\[([A-Za-z0-9_:]+)\]", head.group(0))
        tail = re.search(r"(?:\[([A-Za-z0-9_:]+)\])+$", step)
        produced += re.findall(r"\[([A-Za-z0-9_:]+)\]", tail.group(0))
    # every label a chain reads was either the input or produced by an earlier chain
    for label in consumed:
        assert label == "0:v" or label in produced, f"{label} is never produced"
    assert len(produced) == len(set(produced)), "a label is written twice"


def test_ffmpeg_video_steps_rejects_an_unknown_motion():
    with pytest.raises(ValueError) as e:
        media.ffmpeg_video_steps("pan", 5.0, 1296, 2304, 30, *LANDSCAPE)
    assert "clip" in str(e.value) and "kenburns" in str(e.value)


def test_the_blur_fill_still_hands_the_layers_the_frame_they_expect():
    """The credit plate, the card overlay and the caption band are laid at 0,0 on this."""
    steps = media.ffmpeg_video_steps("hold", 3.0, 1296, 2304, 30, *LANDSCAPE)
    graph = _graph(steps)
    assert "scale=1296:2304" in graph and "crop=1296:2304" in graph
    assert "1080" not in graph, "the fill is built at render scale, not delivery scale"


# --- media_frame_html (the still build_video renders) ---------------------------------

def test_media_frame_html_stacks_the_layers_over_a_cover_poster(tmp_path):
    """build_video's still is the same layers ffmpeg composites, stacked by Chrome instead."""
    poster, over, cred = (tmp_path / n for n in ("poster.png", "overlay.png", "credit.png"))
    html = media.media_frame_html(poster, [over, cred], 1296, 2304, "#101418")
    assert html.index(f"file://{poster}") < html.index(f"file://{over}") \
        < html.index(f"file://{cred}")
    assert "object-fit:cover" in html
    assert "width:1296px" in html and "height:2304px" in html
    assert "#101418" in html


def test_media_frame_html_renders_a_bare_poster_when_there_is_nothing_to_overlay(tmp_path):
    poster = tmp_path / "poster.png"
    html = media.media_frame_html(poster, [], 1296, 2304, "#101418")
    assert f"file://{poster}" in html
    assert html.count("<img") == 1


# --- goldens --------------------------------------------------------------------------

GOLDEN_CASES = [
    ("credit_plate", lambda: media.credit_plate_html(CREDIT, cards.brand_tokens(BRAND),
                                                     1296, 2304)),
    ("overlay_ranked_list", lambda: media.overlay_html(OVERLAY, cards.brand_tokens(BRAND),
                                                       1296, 2304)),
    ("overlay_changed", lambda: media.overlay_html(CHANGED_OVERLAY, cards.brand_tokens(BRAND),
                                                   1296, 2304)),
]


@pytest.mark.parametrize("name,build", GOLDEN_CASES, ids=[c[0] for c in GOLDEN_CASES])
def test_media_html_matches_its_golden_file(name, build):
    """Regenerate after an intentional design change:
       KDESK_UPDATE_GOLDEN=1 uv run --with pytest pytest tests/test_media.py -q
    then open the rendered PNG before committing."""
    html = build()
    path = GOLDEN / f"media_{name}.html"
    if os.environ.get("KDESK_UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    assert path.exists(), f"missing golden {path}; regenerate with KDESK_UPDATE_GOLDEN=1"
    assert html == path.read_text(encoding="utf-8")


# --- fill: crop ---------------------------------------------------------------------------

HERO_LANDSCAPE = (6161, 3862)     # day 3's Spaceship Earth still, 1.60:1


def test_a_landscape_source_is_still_blur_filled_by_default():
    steps = media.ffmpeg_video_steps("kenburns", 4.0, 1296, 2304,
                                     src_w=HERO_LANDSCAPE[0], src_h=HERO_LANDSCAPE[1])
    assert any("boxblur" in step for step in steps)


def test_fill_crop_takes_the_cover_path_whatever_the_source_shape_is():
    steps = media.ffmpeg_video_steps("kenburns", 4.0, 1296, 2304,
                                     src_w=HERO_LANDSCAPE[0], src_h=HERO_LANDSCAPE[1],
                                     fill="crop")
    assert not any("boxblur" in step for step in steps)
    assert len(steps) == 1
    assert "force_original_aspect_ratio=increase" in steps[0]
    assert "crop=1296:2304" in steps[0]


def test_fill_blur_letterboxes_a_portrait_source_that_would_otherwise_crop():
    steps = media.ffmpeg_video_steps("kenburns", 4.0, 1296, 2304,
                                     src_w=1080, src_h=1920, fill="blur")
    assert any("boxblur" in step for step in steps)


def test_focus_moves_the_crop_off_centre_by_the_fraction_it_was_given():
    assert media.cover_chain(1296, 2304) == (
        "scale=1296:2304:force_original_aspect_ratio=increase,crop=1296:2304")
    assert media.cover_chain(1296, 2304, 0.50, 0.42) == (
        "scale=1296:2304:force_original_aspect_ratio=increase,"
        "crop=1296:2304:x=(iw-1296)*0.500:y=(ih-2304)*0.420")


def test_a_centred_focus_emits_the_chain_it_always_emitted():
    """Golden guard: 0.5/0.5 is the implicit centre crop, so it writes no offset at all."""
    assert "x=(iw-" not in media.cover_chain(1296, 2304, 0.5, 0.5)


def test_a_focus_outside_the_frame_is_refused_by_name():
    with pytest.raises(ValueError) as excinfo:
        media.scene_fill({"kind": "media", "src": "x.jpg", "focus": [0.5, 1.4]})
    assert "focus" in str(excinfo.value)


def test_an_unknown_fill_is_refused_by_name():
    with pytest.raises(ValueError) as excinfo:
        media.scene_fill({"kind": "media", "src": "x.jpg", "fill": "stretch"})
    assert "stretch" in str(excinfo.value)


def test_a_scene_with_neither_key_asks_for_nothing():
    assert media.scene_fill({"kind": "media", "src": "x.jpg"}) == (None, (0.5, 0.5))


def test_fill_blur_leaves_the_backdrop_centred_whatever_the_focus_says():
    """`focus` aims the CROP. The blur backdrop is a full-bleed wash and must stay centred.

    blur_fill_steps() builds it with a bare cover_chain(w, h); this is the guard that a later
    change threading focus through that chain — Task 9 adds a parameter to it — cannot leak
    an offset into the backdrop without turning a test red.
    """
    steps = media.ffmpeg_video_steps("kenburns", 4.0, 1296, 2304,
                                     src_w=HERO_LANDSCAPE[0], src_h=HERO_LANDSCAPE[1],
                                     fill="blur", focus=(0.5, 0.42))
    bg = [s for s in steps if "boxblur" in s]
    assert len(bg) == 1
    assert "crop=1296:2304," in bg[0]
    assert "x=(iw-" not in bg[0] and "y=(ih-" not in bg[0]


def test_ffmpeg_video_steps_refuses_an_unknown_fill_the_way_it_refuses_a_motion():
    """The renderer's own gate, so a caller that skipped scene_fill() still cannot silently
    fall through to the ratio default."""
    with pytest.raises(ValueError) as excinfo:
        media.ffmpeg_video_steps("kenburns", 4.0, 1296, 2304, fill="stretch")
    assert "stretch" in str(excinfo.value)
    assert "crop" in str(excinfo.value) and "blur" in str(excinfo.value)


# --- the new motions ---------------------------------------------------------------------

def _zoom_at(expr: str, on: int, frames: int) -> float:
    """Evaluate a zoompan `z` expression in Python. ffmpeg's `if`/`lt`/`min`/`pow` map 1:1."""
    scope = {"on": on, "n": frames, "min": min, "max": max, "pow": pow,
             "lt": lambda a, b: 1 if a < b else 0}
    body = expr.replace("if(", "_if(")
    scope["_if"] = lambda cond, a, b=0.0: a if cond else b
    return float(eval(body, {"__builtins__": {}}, scope))


@pytest.mark.parametrize("motion", media.HIGH_MOTIONS)
def test_every_motion_chain_sets_both_the_size_and_the_fps_zoompan_defaults_wrong(motion):
    """zoompan defaults to s=hd720 and fps=25. Both are wrong for a 1080x1920 30 fps Short."""
    chain = media.motion_chain(motion, 3.0, 1296, 2304)
    assert f"s={media.ZOOMPAN_W}x{media.ZOOMPAN_H}" in chain
    assert "fps=30" in chain
    assert chain.endswith("scale=1296:2304:flags=lanczos")


@pytest.mark.parametrize("motion", media.HIGH_MOTIONS)
def test_every_high_motion_pre_scales_to_twice_the_render_size(motion):
    steps = media.ffmpeg_video_steps(motion, 3.0, 1296, 2304, src_w=4000, src_h=6000)
    assert "scale=2592:4608" in steps[0]


def test_the_punch_hits_its_full_zoom_in_the_ramp_and_then_keeps_creeping():
    """A punch that HELD was measured at 0.00 per-frame motion for most of a 3 s beat and
    was the whole of a 17.4% still_frame_fraction. This replaces the assertion that it
    "holds dead still" after the ramp: the hit still lands in PUNCH_FRAMES, and a slow push
    runs under it from there so no frame is ever a repeat of the one before it.
    """
    expr = media.zoom_expr("punch", 90).strip("'")
    start = _zoom_at(expr, 0, 90)
    ramped = _zoom_at(expr, media.PUNCH_FRAMES, 90)
    last = _zoom_at(expr, 89, 90)
    assert start == pytest.approx(1.0, abs=1e-6)
    assert ramped == pytest.approx(1.0 + media.PUNCH_ZOOM, abs=1e-3), "the hit still lands"
    assert last == pytest.approx(1.0 + media.PUNCH_ZOOM + media.PUNCH_DRIFT, abs=1e-3), \
        "and the drift arrives on the LAST RENDERED frame, on = n-1"
    # the ramp still decelerates: the first frame moves further than the last of the ramp
    assert (_zoom_at(expr, 1, 90) - start) > (ramped - _zoom_at(expr, 8, 90))
    # and the drift is far slower than the ramp — a creep, not a second move
    assert (last - ramped) / (90 - media.PUNCH_FRAMES) < (ramped - start) / media.PUNCH_FRAMES
    zs = [_zoom_at(expr, on, 90) for on in range(90)]
    assert all(b > a for a, b in zip(zs, zs[1:])), "a punch never decreases, and never holds"


def test_a_push_climbs_all_the_way_through_the_beat():
    """And ARRIVES: zoompan's `on` runs 0..n-1, so a push that divided by `n` would stop a
    frame short of PUSH_ZOOM and never reach the zoom the beat was written for."""
    expr = media.zoom_expr("push", 90).strip("'")
    assert _zoom_at(expr, 0, 90) == pytest.approx(1.0)
    assert _zoom_at(expr, 89, 90) == pytest.approx(1.0 + media.PUSH_ZOOM, abs=1e-3)


def test_a_pan_starts_at_one_edge_and_ends_at_the_other():
    right = media.motion_chain("pan_right", 3.0, 1296, 2304)
    left = media.motion_chain("pan_left", 3.0, 1296, 2304)
    assert f"z='{media.PAN_ZOOM}'" in right and f"z='{media.PAN_ZOOM}'" in left
    assert "x='(iw-iw/zoom)*(on/89)'" in right
    assert "x='(iw-iw/zoom)*(1-on/89)'" in left


def test_the_burst_hits_settles_and_then_creeps_back_out():
    """Replaces the assertion that the burst sits at BURST_SETTLE to the end of the beat:
    holding is what the punch was measured doing wrong, and the burst held the same way.
    The settle is the only place it goes DOWN, and after it nothing holds."""
    expr = media.zoom_expr("burst", 90).strip("'")
    assert _zoom_at(expr, 4, 90) == pytest.approx(media.BURST_PEAK, abs=1e-3)
    assert _zoom_at(expr, 12, 90) == pytest.approx(media.BURST_SETTLE, abs=1e-3)
    assert _zoom_at(expr, 89, 90) == pytest.approx(media.BURST_SETTLE + media.PUNCH_DRIFT,
                                                   abs=1e-3)
    after = [_zoom_at(expr, on, 90) for on in range(media.BURST_SETTLE_FRAMES, 90)]
    assert all(b > a for a, b in zip(after, after[1:])), "and it climbs the whole way back"


@pytest.mark.parametrize("motion", ["punch", "push", "burst"])
def test_no_zooming_motion_ever_renders_the_same_frame_twice(motion):
    """The guard behind the ruling: still_frame_fraction is measured on the OUTPUT, and two
    frames at the same `z` with the same `x` are the same frame. The pans are not here
    because their `z` is constant by design — their motion is in `x`, which travels every
    frame (see test_a_pan_starts_at_one_edge_and_ends_at_the_other)."""
    expr = media.zoom_expr(motion, 90).strip("'")
    zs = [_zoom_at(expr, on, 90) for on in range(90)]
    assert all(b != a for a, b in zip(zs, zs[1:]))


@pytest.mark.parametrize("motion", media.HIGH_MOTIONS)
def test_a_beat_shorter_than_its_own_ramp_is_still_a_valid_expression(motion):
    """A one-frame beat has no room to drift and must not divide by zero."""
    for frames in (1, 2, 9, 13):
        expr = media.zoom_expr(motion, frames).strip("'")
        assert "/0" not in expr.replace("/0.", "@")
        assert _zoom_at(expr, frames - 1, frames) >= 1.0


def test_kenburns_is_untouched_so_every_existing_render_is_untouched():
    assert media.KENBURNS_ZOOM == 1.08
    chain = media.motion_chain("kenburns", 4.0, 1296, 2304)
    assert "min(zoom+" in chain
    assert f"s=1296x2304" in chain
    assert "scale=" not in chain


def test_the_new_motions_are_image_only():
    for motion in media.HIGH_MOTIONS:
        assert motion in media.MOTIONS_FOR["image"]
        assert motion not in media.MOTIONS_FOR["video"]


# --- the crop table ----------------------------------------------------------------------

CROP = {"zoom": 1.45, "fx": 0.62, "fy": 0.70}

#: `kenburns` and `hold` are image motions too, so a beat re-frames them as well. Only the
#: five high ones pre-scale.
IMAGE_MOTIONS = ("kenburns", "hold", *media.HIGH_MOTIONS)


def test_a_crop_reframes_the_source_before_anything_resamples_it():
    """The crop is of the SOURCE, in iw/ih terms, and comes first.

    Cropping the covered frame would be scale-down, crop, scale-up: three resamples, and the
    detail the first one threw away is gone. Cropping the source keeps its own pixels, so a
    1.45x re-frame of a 3376 px-wide still is 2328 real px.
    """
    steps = media.ffmpeg_video_steps("punch", 3.0, 1296, 2304, src_w=3376, src_h=6000,
                                     crop=CROP)
    assert steps[0].startswith(
        "[0:v]crop=iw/1.450:ih/1.450:x=(iw-iw/1.450)*0.620:y=(ih-ih/1.450)*0.700,")
    assert steps[0].index("crop=iw/") < steps[0].index("scale=2592:4608")
    assert steps[0].index("crop=iw/") < steps[0].index("zoompan")
    assert "scale=2592:4608" in steps[0]      # and the 2x cover still happens, after it


@pytest.mark.parametrize("motion", IMAGE_MOTIONS)
def test_every_image_motion_is_re_framed_not_just_the_high_ones(motion):
    """`kenburns` and `hold` are stills too. A beat that re-frames them is the cheapest way
    to get three shots out of one photograph without a zoompan on every one."""
    steps = media.ffmpeg_video_steps(motion, 3.0, 1296, 2304, src_w=3376, src_h=6000,
                                     crop=CROP)
    assert steps[0].startswith("[0:v]crop=iw/1.450:")


@pytest.mark.parametrize("motion", IMAGE_MOTIONS)
def test_the_widest_crop_is_a_no_op(motion):
    """zoom 1.00 is the whole picture, so it must emit the chain no crop at all emits —
    not a crop of the full frame, which is a resample for nothing."""
    assert media.ffmpeg_video_steps(motion, 3.0, 1296, 2304, src_w=3376, src_h=6000,
                                    crop={"zoom": 1.00, "fx": 0.5, "fy": 0.5}) == \
        media.ffmpeg_video_steps(motion, 3.0, 1296, 2304, src_w=3376, src_h=6000)


@pytest.mark.parametrize("motion", IMAGE_MOTIONS)
def test_no_crop_is_the_chain_a_scene_without_beats_gets(motion):
    assert media.ffmpeg_video_steps(motion, 3.0, 1296, 2304, src_w=3376, src_h=6000) == \
        media.ffmpeg_video_steps(motion, 3.0, 1296, 2304, src_w=3376, src_h=6000, crop=None)


@pytest.mark.parametrize("motion", ["kenburns", "hold"])
def test_an_uncropped_kenburns_or_hold_is_byte_for_byte_the_chain_it_always_was(motion):
    """The whole of Task 9 rests on this: every spec rendered before today re-renders
    identically."""
    assert media.ffmpeg_video_steps(motion, 5.0, 1296, 2304, 30, 1080, 1920) == \
        [f"[0:v]{media.ffmpeg_video_filter(motion, 5.0, 1296, 2304, 30)}[m0]"]


def test_a_crop_under_a_blur_fill_is_ignored_rather_than_refused():
    """The blur fill's whole point is that the WHOLE picture stays on screen; re-framing it
    would throw away the thing it exists to keep."""
    assert media.ffmpeg_video_steps("kenburns", 3.0, 1296, 2304, src_w=4000, src_h=2250,
                                    crop=CROP) == \
        media.ffmpeg_video_steps("kenburns", 3.0, 1296, 2304, src_w=4000, src_h=2250)


@pytest.mark.parametrize("crop,bad", [
    ({"zoom": 0.8}, "0.8"),                                  # wider than the picture
    ({"zoom": 1.4, "fx": 1.4, "fy": 0.5}, "1.4"),            # off the frame
    ({"zoom": 1.4, "fx": 0.5, "fy": -0.1}, "-0.1"),
    ({"zoom": "wide"}, "wide"),                              # not a number
    ([1.4, 0.5, 0.5], "1.4"),                                # not a mapping
])
def test_a_bad_crop_is_refused_by_name(crop, bad):
    """Task 10 feeds this straight from the spec, so a typo has to stop the render rather
    than hand ffmpeg an expression that quietly evaluates to nonsense."""
    with pytest.raises(ValueError) as e:
        media.crop_chain(2592, 4608, crop)
    assert "crop" in str(e.value) and bad in str(e.value)


def test_a_crop_on_a_clip_beat_is_ignored_rather_than_refused():
    """ParkSheet writes one `crop` per beat for a uniform shape; a footage beat carries it
    too. `crop` re-frames a still, so on `clip` it is a no-op, not an error."""
    crop = {"zoom": 1.45, "fx": 0.62, "fy": 0.70}
    assert media.ffmpeg_video_steps("clip", 3.0, 1296, 2304, src_w=1080, src_h=1920,
                                    crop=crop) == \
        media.ffmpeg_video_steps("clip", 3.0, 1296, 2304, src_w=1080, src_h=1920)


def test_a_high_motion_on_footage_is_refused_by_name_in_the_preflight():
    for motion in media.HIGH_MOTIONS:
        with pytest.raises(ValueError) as e:
            media.check_motion("video", motion)
        text = str(e.value)
        assert motion in text and "video" in text
        assert "clip" in text and "hold" in text
