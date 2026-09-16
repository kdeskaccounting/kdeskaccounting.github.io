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


# --- safe_slug: a spec from outside this repo names its own build directory -------------

def test_safe_slug_accepts_the_slugs_this_repo_already_uses():
    for slug in ("asc842", "asc606-kit", "month-end-close", "rsu-planner", "card-demo",
                 "park.sheet_v2"):
        assert sv.safe_slug(slug) == slug


@pytest.mark.parametrize("slug", ["../../etc", "a/b", "..", ".", "", "has space",
                                  "semi;colon", "quote'", None])
def test_safe_slug_rejects_anything_that_is_not_one_path_segment(slug):
    """slug becomes scripts/video/build/<slug>; an external spec must not steer that elsewhere."""
    with pytest.raises(SystemExit) as e:
        sv.safe_slug(slug)
    assert "slug" in str(e.value)


# --- needs_workbook ----------------------------------------------------------------------

def test_the_workbook_free_kinds_are_the_ones_that_carry_their_own_content():
    """A spreadsheet is only needed by a scene that shows a spreadsheet."""
    assert sv.WORKBOOK_FREE_KINDS == ("title", "outro", "card", "media")


@pytest.mark.parametrize("kind", ["title", "outro", "card", "media"])
def test_a_spec_of_only_workbook_free_scenes_needs_no_workbook(kind):
    assert sv.needs_workbook({"scenes": [{"kind": kind}, {"kind": kind}]}) is False


def test_a_media_only_spec_needs_no_workbook_the_same_way_a_card_only_spec_does():
    spec = {"scenes": [{"kind": "media", "src": "a.mp4"}, {"kind": "card"}]}
    assert sv.needs_workbook(spec) is False


def test_a_sheet_scene_anywhere_in_the_spec_needs_the_workbook():
    assert sv.needs_workbook({"scenes": [{"kind": "media"}, {"sheet": "Inputs"}]}) is True


def test_a_scene_with_no_kind_is_a_sheet_scene():
    """`kind:` is optional in every existing spec; its absence has always meant `sheet`."""
    assert sv.needs_workbook({"scenes": [{"sheet": "Inputs", "range": "A1:D9"}]}) is True


def test_a_spec_with_no_scenes_needs_no_workbook():
    assert sv.needs_workbook({"scenes": []}) is False
    assert sv.needs_workbook({}) is False
