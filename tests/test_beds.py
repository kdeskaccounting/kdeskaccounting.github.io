"""beds.py: `audio.bed: rotate` picks one bed from `bed_pool` by slug hash (2026-11-09)."""
import hashlib
import pathlib

import pytest

import beds
import make_short as M

POOL = [
    {"id": "a", "src": "media/audio/a.mp3", "lufs": -24.0, "target_lufs": -24, "fade_in": 0.3,
     "fade_out": 1.2},
    {"id": "b", "src": "media/audio/b.mp3", "lufs": -24.1, "target_lufs": -24, "fade_in": 0.3,
     "fade_out": 1.2},
    {"id": "c", "src": "media/audio/c.mp3", "lufs": -23.9, "target_lufs": -24, "fade_in": 0.3,
     "fade_out": 1.2},
]


def _spec(bed="rotate", slug="parksheet-hand-x", pool=POOL):
    spec = {"slug": slug, "audio": {"bed": bed, "duck": {"ratio": 8}}}
    if pool is not None:
        spec["bed_pool"] = [dict(e) for e in pool]
    return spec


def test_the_slot_is_sha256_of_the_slug_mod_the_pool_size():
    want = int(hashlib.sha256(b"parksheet-hand-x").hexdigest(), 16) % 3
    assert beds.slot("parksheet-hand-x", 3) == want


def test_rotate_is_deterministic_and_spreads_over_the_pool():
    picks = {beds.pick(_spec(slug=f"parksheet-hand-s{i}"))["id"] for i in range(40)}
    assert picks == {"a", "b", "c"}
    assert beds.pick(_spec())["id"] == beds.pick(_spec())["id"]


def test_pool_id_names_one_entry():
    assert beds.pick(_spec(bed="pool:b"))["src"] == "media/audio/b.mp3"
    with pytest.raises(ValueError, match="no bed_pool entry with id 'z'"):
        beds.pick(_spec(bed="pool:z"))


def test_resolve_drops_the_id_and_keeps_the_rest_of_the_block():
    block = beds.resolve_audio(_spec(bed="pool:a"))
    assert block["bed"] == {k: v for k, v in POOL[0].items() if k != "id"}
    assert block["duck"] == {"ratio": 8}


def test_a_mapping_bed_comes_back_as_the_same_object():
    """Every spec written before rotation: untouched, so its render is byte-identical."""
    spec = {"slug": "s", "audio": {"bed": {"src": "x.mp3", "lufs": -11.6}}}
    assert beds.resolve_audio(spec) is spec["audio"]
    assert beds.resolve_audio({}) is None


@pytest.mark.parametrize("pool, match", [
    (None, "missing"), ([], "empty"), ([{"id": "a"}], "needs an `id` and a `src`"),
    ([{"id": "a", "src": "x", "gain": 1}], "unknown key"),
    ([{"id": "a", "src": "x"}, {"id": "a", "src": "y"}], "twice"),
])
def test_a_bad_pool_is_refused_by_name(pool, match):
    with pytest.raises(ValueError, match=match):
        beds.pick(_spec(pool=pool))


def test_an_unknown_string_bed_is_refused():
    with pytest.raises(ValueError, match="must be 'rotate'"):
        beds.pick(_spec(bed="shuffle"))


def test_rotate_without_a_slug_is_refused():
    with pytest.raises(ValueError, match="needs the spec's `slug`"):
        beds.pick(_spec(slug=None))


def test_audio_settings_mixes_the_picked_bed(tmp_path):
    (tmp_path / "media" / "audio").mkdir(parents=True)
    for entry in POOL:
        (tmp_path / entry["src"]).write_bytes(b"x")
    (tmp_path / "pyproject.toml").write_text("")
    spec = _spec(bed="pool:c")
    mix = M.audio_settings(spec, tmp_path / "video" / "scenes.yaml")
    assert mix.bed.src.endswith("media/audio/c.mp3")
    assert mix.bed.lufs == -23.9 and mix.bed.target_lufs == -24
    assert mix.bed.fade_in == 0.3


def test_audio_settings_turns_a_pool_error_into_a_refusal():
    with pytest.raises(SystemExit, match="audio.bed: .*bed_pool"):
        M.audio_settings(_spec(pool=None), pathlib.Path("/x/scenes.yaml"))
