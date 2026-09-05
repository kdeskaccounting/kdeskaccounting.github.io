"""Named Short variants for make_short.py: keep the legacy single `short:` block working, add `shorts: {name: block}`."""
import pathlib
import pytest
import short_variants as sv

SPEC = {
    "short": {"hook": "legacy", "scenes": [6, 10], "cta": "c"},
    "shorts": {"je": {"hook": "the entry", "scenes": [6, 7], "cta": "c"},
               "recon": {"hook": "ties to zero", "scenes": [10], "cta": "c"}},
}


def test_select_short_defaults_to_legacy_block():
    assert sv.select_short(SPEC, None) is SPEC["short"]


def test_select_short_returns_named_variant():
    assert sv.select_short(SPEC, "je")["hook"] == "the entry"


def test_select_short_missing_variant_lists_available_names():
    with pytest.raises(KeyError) as e:
        sv.select_short(SPEC, "nope")
    assert "je" in str(e.value) and "recon" in str(e.value)


def test_select_short_without_any_short_block_is_a_clear_error():
    with pytest.raises(KeyError):
        sv.select_short({"scenes": []}, None)


def test_all_variants_yields_legacy_first_then_named_in_order():
    assert [name for name, _ in sv.all_variants(SPEC)] == [None, "je", "recon"]
    assert [name for name, _ in sv.all_variants({"shorts": {"a": {}}})] == ["a"]


def test_short_paths_keep_legacy_filenames_and_suffix_named_variants():
    b = pathlib.Path("/b/asc842")
    legacy = sv.short_paths(b, "asc842", None)
    assert legacy.final == b / "asc842-short.mp4"
    assert legacy.work == b / "short"
    assert legacy.review == b / "short-review"
    named = sv.short_paths(b, "asc842", "je")
    assert named.final == b / "asc842-short-je.mp4"
    assert named.work == b / "short-je"
    assert named.review == b / "short-review-je"
