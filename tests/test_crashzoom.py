"""`motion: crashzoom` and `still_of:` -- the hand-built opening folded into the renderer.

The camera arithmetic is pure and tested in the bare environment. The drawing needs Pillow
and is tested only where it is installed (the render venv); the pixel-level check against
the old hand opener was run once by hand on 2026-11-03 (every sampled frame of both clips
identical, max difference 0) and is not repeated here because it needs the real stills.
"""
import pathlib

import pytest

import crashzoom as CZ
import media

OPEN = {"wide": "media/photos/wide.png", "wide_target": [511, 1040], "wide_width": 116,
        "close": "media/photos/close.png", "close_target": [507, 969]}


def test_every_default_is_the_hand_openers_value():
    cfg = CZ.parse_open(dict(OPEN))
    assert cfg["zoom"] == 4.1 and cfg["impact_s"] == 0.40 and cfg["seconds"] == 3.0
    assert cfg["impact_frame"] == 12 and cfg["frames"] == 90
    assert cfg["ease"] == 2.4 and cfg["shutter"] == 1.6 and cfg["max_samples"] == 24
    assert cfg["pulse"] == 0.07 and cfg["drift"] == 0.05
    assert cfg["flash"] == 0.28 and cfg["flash_frames"] == 4
    assert cfg["shake"] == [[0, -34], [26, 22], [-18, -14], [10, 8], [-5, -3], [2, 1]]
    turn = CZ.parse_turn({"continue": 0})
    assert turn["punch"] == 1.22 and turn["punch_frames"] == 3 and turn["frames"] == 45
    assert turn["shake"] == [[14, -18], [-9, 10], [4, -4]]


@pytest.mark.parametrize("bad,needle", [
    ({"wide": ""}, "wide"),
    ({"wide_width": 0}, "wide_width"),
    ({"zoom": 0.8}, "zoom"),
    ({"impact_s": 0.02}, "impact_s"),
    ({"seconds": 0.3}, "past the impact"),
    ({"xfade": [470, 400]}, "xfade"),
    ({"wobble": 1}, "unknown"),
    ({"lander": {"tip": [0.5, 0.5]}}, "lander needs `src:`"),
])
def test_a_bad_opening_is_refused_by_name(bad, needle):
    with pytest.raises(ValueError) as excinfo:
        CZ.parse_open({**OPEN, **bad})
    assert needle in str(excinfo.value)


def _fingerprint_camera():
    cfg = CZ.parse_open({**OPEN, "close_width": 286, "land_width": 600,
                         "p0": [538.75, 1300], "xfade": [400, 470]})
    return CZ.Camera(cfg, (1024, 1536), (1024, 1536))


def test_the_fingerprint_numbers_come_out_of_the_spec_keys():
    """make_opening.py v2: RS0 145 px (cover by height), P0 (538.75, 1300), RS1 600 px."""
    cam = _fingerprint_camera()
    assert cam.RS0 == pytest.approx(145.0)
    assert cam.P0 == pytest.approx((538.75, 1300.0))
    assert cam.RS1 == 600.0 and cam.close_rw == 286.0 and cam.XFADE == (400, 470)


def test_the_crash_zoom_eases_in_and_lands_on_the_impact_frame():
    cam = _fingerprint_camera()
    widths = [cam.camera1(t)[0] for t in range(13)]
    assert widths[0] == pytest.approx(cam.RS0)
    assert all(b > a for a, b in zip(widths, widths[1:12]))
    # ease-in: the first half of the move covers far less than half the zoom
    assert widths[6] < cam.RS0 * (cam.RS1 / cam.RS0) ** 0.5
    # the hard stop: the 7% pulse on the impact frame, springing back
    assert cam.camera1(12)[0] == pytest.approx(600 * 1.07)
    assert cam.camera1(12)[1] == (540.0, 1180.0)
    assert cam.camera1(30)[0] < cam.camera1(13)[0]


def test_blur_samples_are_many_mid_move_and_one_when_settled():
    cam = _fingerprint_camera()
    rs = lambda t: cam.camera1(t)[0]
    assert len(CZ.Camera.samples(rs, 10, 12, 1.6, 24, 6.0)) > 10
    assert len(CZ.Camera.samples(rs, 10, 12, 1.6, 24, 6.0)) <= 24
    assert CZ.Camera.samples(rs, 0, 12, 1.6, 24, 6.0)[0] >= 0.0


def test_the_turn_continues_the_same_camera_then_punches():
    cam = _fingerprint_camera()
    turn = CZ.parse_turn({"continue": 0, "punch_at": [600, 1080]})
    rs0, p0 = cam.camera2(turn, 72, 0)
    assert rs0 == pytest.approx(cam.camera1(72)[0])
    assert cam.camera2(turn, 72, 3)[0] == pytest.approx(cam.camera1(75)[0] * 1.22)


def test_the_continuation_frame_is_the_frames_the_opening_part_showed():
    """The number make_opening.py's `c2_start` had to be re-measured as after every TTS run."""
    assert CZ.continuation_frame(2.4) == 72
    assert CZ.continuation_frame(2.7) == 81


def _spec(*scenes):
    return {"scenes": list(scenes)}


def _scene(**kw):
    return {"kind": "media", "credit": "Illustrations: generated", "narration": "x", **kw}


@pytest.fixture
def stills(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    photos = tmp_path / "media" / "photos"
    photos.mkdir(parents=True)
    for name in ("wide.png", "close.png", "finger.png"):
        (photos / name).write_bytes(b"\0")
    return tmp_path / "scenes.yaml"


def test_a_crashzoom_spec_passes_the_media_preflight_without_a_src(stills):
    spec = _spec(_scene(motion="crashzoom", crashzoom=dict(OPEN)),
                 _scene(motion="crashzoom", crashzoom={"continue": 0}),
                 _scene(still_of=0, motion="push"))
    media.validate_spec(spec, stills)


@pytest.mark.parametrize("scenes,needle", [
    ([_scene(motion="crashzoom")], "needs a `crashzoom:` block"),
    ([_scene(motion="crashzoom", crashzoom={**OPEN, "close": "media/photos/nope.png"})],
     "does not exist"),
    ([_scene(motion="crashzoom", src="media/photos/wide.png", crashzoom=dict(OPEN))],
     "would be ignored"),
    ([_scene(motion="crashzoom", crashzoom={"continue": 0})], "EARLIER"),
    ([_scene(motion="punch", src="media/photos/wide.png"),
      _scene(motion="crashzoom", crashzoom={"continue": 0})], "not a crash-zoom OPENING"),
    ([_scene(still_of=3)], "not a scene"),
    ([_scene(motion="crashzoom", crashzoom=dict(OPEN)), _scene(still_of=0, motion="clip")],
     "cannot be used"),
    ([_scene(motion="crashzoom", crashzoom=dict(OPEN), credit="")], "credit"),
])
def test_a_broken_generated_scene_is_refused_in_the_preflight(stills, scenes, needle):
    with pytest.raises((ValueError, FileNotFoundError)) as excinfo:
        media.validate_spec(_spec(*scenes), stills)
    assert needle in str(excinfo.value)


def test_a_spec_with_no_crashzoom_is_validated_exactly_as_before(stills):
    """Backward compatibility: an ordinary media scene still needs its src."""
    with pytest.raises(ValueError) as excinfo:
        media.validate_spec(_spec(_scene(motion="punch")), stills)
    assert "has no `src:`" in str(excinfo.value)


def test_the_clip_key_moves_with_the_config_and_the_continuation_frame(stills):
    root = stills.parent
    resolve = lambda src: root / src
    cfg = CZ.parse_open(dict(OPEN))
    assert CZ.clip_key(cfg, resolve) == CZ.clip_key(CZ.parse_open(dict(OPEN)), resolve)
    assert CZ.clip_key(cfg, resolve) != CZ.clip_key(CZ.parse_open({**OPEN, "zoom": 4.0}),
                                                    resolve)
    assert CZ.clip_key(cfg, resolve, {"start": 71}) != CZ.clip_key(cfg, resolve, {"start": 72})


# --- drawing: render venv only ----------------------------------------------------------

def test_the_painter_draws_the_impact_brighter_than_the_settled_frame(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    photos = tmp_path / "media" / "photos"
    photos.mkdir(parents=True)
    Image.new("RGB", (1024, 1536), (90, 110, 130)).save(photos / "wide.png")
    Image.new("RGB", (1024, 1536), (100, 120, 140)).save(photos / "close.png")
    painter = CZ.Painter(CZ.parse_open({**OPEN, "ring": {}}), lambda src: tmp_path / src)
    impact, settled = painter.composite1(12), painter.composite1(60)
    assert impact.size == settled.size == (1080, 1920)
    mean = lambda im: sum(im.convert("L").getdata()) / (1080 * 1920)
    assert mean(impact) > mean(settled)
