"""scripts/video/assemble.py picks scene stills, not the media layers beside them."""
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
