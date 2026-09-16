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


def test_the_three_motions_are_the_ones_the_contract_names():
    assert media.MOTIONS == ("clip", "kenburns", "hold")


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
    assert media.MOTIONS_FOR == {"image": ("kenburns", "hold"), "video": ("clip", "hold")}


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
