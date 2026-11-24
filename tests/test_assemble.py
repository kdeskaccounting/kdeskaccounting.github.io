"""scripts/video/assemble.py picks scene stills, not the media layers beside them; and its opt-in
landscape media path (ParkSheet long-form spike) frames, captions and fills without touching the old one."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "video"))
import assemble  # noqa: E402


def test_scene_frames_ignores_media_layers_and_orders_by_index(tmp_path):
    for name in ["scene_00.png", "scene_00-credit.png", "scene_00-overlay.png",
                 "scene_00-poster.png", "scene_02.png", "scene_01.png", "focus.json"]:
        (tmp_path / name).write_bytes(b"")
    assert [f.name for f in assemble.scene_frames(tmp_path)] == [
        "scene_00.png", "scene_01.png", "scene_02.png"]


def test_scene_frames_on_an_empty_directory_is_empty(tmp_path):
    assert assemble.scene_frames(tmp_path) == []


def _words(text, step=0.3):
    return [{"text": t, "start": round(i * step, 3), "end": round(i * step + 0.25, 3)}
            for i, t in enumerate(text.split())]


def test_landscape_is_opt_in():
    assert assemble.landscape_opts(None) is None
    assert assemble.landscape_opts({"scenes": []}) is None
    assert assemble.landscape_opts({"landscape": {"join": "cut"}}) == {"join": "cut"}


def test_landscape_fill_pillarboxes_portrait_and_square_and_always_shows_earth_whole():
    assert assemble.landscape_fill({}, 3840, 2160, earth=False) == "crop"
    assert assemble.landscape_fill({}, 4000, 3000, earth=False) == "crop"     # 4:3 still crops
    assert assemble.landscape_fill({}, 2212, 2160, earth=False) == "blur"     # square-ish
    assert assemble.landscape_fill({}, 1080, 1920, earth=False) == "blur"     # 9:16
    assert assemble.landscape_fill({"fill": "crop"}, 1080, 1920, earth=False) == "crop"
    # cover-cropping a portrait Earth Studio export to 16:9 cuts its burned-in attribution
    assert assemble.landscape_fill({"fill": "crop"}, 1080, 1920, earth=True) == "blur"
    assert assemble.landscape_fill({}, None, None, earth=False) == "crop"


def test_caption_cues_one_per_sentence_and_spans_to_the_next():
    cues = assemble.caption_cues(_words("It's the rulebook. I read the whole thing."), 5.0)
    assert [c[0] for c in cues] == ["It's the rulebook.", "I read the whole thing."]
    assert cues[0][2] == cues[1][1]                       # no gap between cues
    assert cues[1][2] <= 5.0


def test_caption_cues_split_a_long_sentence_at_its_comma():
    text = ("On the way, there's a horse that gets in when your dog doesn't, and a park where "
            "your balloon has to go to daycare.")
    cues = assemble.caption_cues(_words(text), 30.0)
    assert [c[0] for c in cues] == ["On the way, there's a horse that gets in when your dog doesn't,",
                                    "and a park where your balloon has to go to daycare."]


def test_split_without_a_comma_never_strands_a_function_word():
    ws = _words("Every single rule in this very long video comes from the pages Disney itself "
                "publishes for its own guests to read")
    chunks = assemble.split_long(ws, max_chars=60)
    assert len(chunks) >= 2
    for chunk in chunks[:-1]:
        last = chunk[-1]["text"].strip(".,").lower()
        assert last not in assemble.FUNCTION_WORDS


def test_wrap_caption_balances_two_lines():
    lines = assemble.wrap_caption("costumes may not be worn by guests ages fourteen or older.")
    assert len(lines) == 2 and abs(len(lines[0]) - len(lines[1])) <= 12
    assert assemble.wrap_caption("Masks are out at that age too.") == ["Masks are out at that age too."]


def test_caption_png_is_full_frame_transparent_with_ink_only_in_its_band(tmp_path):
    import pytest
    Image = pytest.importorskip("PIL.Image")   # the suite's env is pytest + stdlib; the venv has PIL
    out = assemble.caption_png("It's the rulebook.", tmp_path / "c.png")
    im = Image.open(out)
    assert im.size == (assemble.W, assemble.H) and im.mode == "RGBA"
    box = im.getchannel("A").getbbox()
    assert box[1] > assemble.H * 0.6                      # lower third
    top = assemble.caption_png("It's the rulebook.", tmp_path / "t.png", position="top")
    assert Image.open(top).getchannel("A").getbbox()[3] < assemble.H * 0.4


def test_source_args_loop_a_clip_and_seek_to_its_in_point():
    assert assemble.source_args("clip", 2.5, "/m/a.mp4") == [
        "-stream_loop", "-1", "-ss", "2.500", "-i", "/m/a.mp4"]
    assert assemble.source_args("hold", 1.0, "/m/a.mp4") == ["-ss", "1.000", "-i", "/m/a.mp4"]
    assert assemble.source_args("kenburns", 0.0, "/m/b.jpg") == ["-i", "/m/b.jpg"]


def test_picture_steps_show_earth_whole_on_the_brand_ground_and_blur_fill_a_portrait_clip():
    (earth,) = assemble.picture_steps("2:v", "b2", "clip", 4.0, (1080, 1920), "crop", (0.5, 0.5),
                                      None, True, "#343A46")
    assert earth.startswith("[2:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=")
    assert "color=#343A46" in earth and "boxblur" not in earth and earth.endswith("[b2]")
    portrait = assemble.picture_steps("0:v", "m0", "clip", 4.0, (1080, 1920), None, (0.5, 0.5),
                                      None, False, "#343A46")
    assert any("boxblur" in s for s in portrait) and portrait[-1].endswith("[m0]")
    cropped = assemble.picture_steps("1:v", "b1", "clip", 4.0, (1080, 1920), "crop", (0.5, 0.2),
                                     None, False, "#343A46")
    assert len(cropped) == 1 and "y=(ih-1080)*0.200" in cropped[0]
