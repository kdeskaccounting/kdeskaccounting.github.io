"""scripts/publishers/youtube_longform_web.py: the pure parts of the long-form Studio driver.

The browser half (the A/B Testing dialog, tags, category) is proved by its own dry run, which
uploads a draft and deletes it; these tests pin what is decided BEFORE Studio is touched: what
a long-form meta must look like, the tag budget, and which thumbnail goes in which A/B slot.
"""
import pathlib

import pytest

from publishers import publish
from publishers import youtube_longform_web as lf
from publishers import youtube_web as yw


def _thumb(tmp_path, name, size=1000):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xff" * size)
    return p


def _episode(tmp_path):
    """An episode folder shaped like ~/parksheet/video/longform/ep01-banned (cut8 one level down)."""
    ep = tmp_path / "video" / "longform" / "ep01"
    for n in ("thumb-B.png", "thumb-A.png", "thumb-C.png"):
        _thumb(ep / "package", n)
    (ep / "cut8").mkdir(parents=True)
    meta_path = ep / "cut8" / "meta.json"
    meta_path.write_text("{}")
    meta = {"format": "longform", "title": "8 Things That Are BANNED at Disney World",
            "description": "d", "promoted": False, "sponsored": False, "made_for_kids": False,
            "category": "Travel & Events", "tags": ["disney world rules", "magic kingdom"],
            "thumbnail": "video/longform/ep01/package/thumb-B.png",
            "test_and_compare": [{"variant": "B", "thumbnail": "package/thumb-B.png"},
                                 {"variant": "A", "thumbnail": "package/thumb-A.png"},
                                 {"variant": "C", "thumbnail": "package/thumb-C.png"}],
            "_meta_path": str(meta_path)}
    return ep, meta


def test_tag_chars_counts_commas_and_quotes_like_youtube():
    assert lf.tag_chars([]) == 0
    assert lf.tag_chars(["disney"]) == 6
    # "magic kingdom" is quoted (+2), plus one comma between the two tags
    assert lf.tag_chars(["disney", "magic kingdom"]) == 6 + 13 + 2 + 1


def test_tags_of_strips_dedupes_and_drops_commas():
    meta = {"tags": [" Disney  World ", "disney world", "a,b", "", "Magic Kingdom"]}
    assert lf.tags_of(meta) == ["Disney World", "a b", "Magic Kingdom"]


def test_tags_of_refuses_over_youtubes_limit():
    with pytest.raises(lf.LongformMetaError, match="500"):
        lf.tags_of({"tags": [f"tag number {i:03d}" for i in range(40)]})


def test_episode_tags_fit():
    """The ep 1 package's 14 tags (313 chars bare) fit with YouTube's quoting."""
    tags = ["banned at disney world", "disney world rules", "things banned at disney world",
            "disney world park rules", "walt disney world", "magic kingdom",
            "disney world costume rule", "disney selfie stick ban", "disney stroller size",
            "disney world smoking", "disney world age rule", "disney service animals",
            "animal kingdom balloons", "disney world no fly zone"]
    assert lf.tag_chars(lf.tags_of({"tags": tags})) <= lf.TAGS_MAX_CHARS


def test_ab_thumbnails_resolve_from_the_cut_folder_upward_in_slot_order(tmp_path):
    ep, meta = _episode(tmp_path)
    files, mode = lf.thumbnails_of(meta)
    assert mode == "ab"
    assert [f.name for f in files] == ["thumb-B.png", "thumb-A.png", "thumb-C.png"]
    assert all(f.parent == ep / "package" for f in files)


def test_single_thumbnail_resolves_a_repo_relative_path(tmp_path):
    ep, meta = _episode(tmp_path)
    meta.pop("test_and_compare")
    files, mode = lf.thumbnails_of(meta)
    assert mode == "single" and files == [ep / "package" / "thumb-B.png"]


def test_no_thumbnail_is_allowed(tmp_path):
    _, meta = _episode(tmp_path)
    meta.pop("test_and_compare"); meta.pop("thumbnail")
    assert lf.thumbnails_of(meta) == ([], "none")


@pytest.mark.parametrize("variants, match", [
    ([{"thumbnail": "package/thumb-B.png"}], "2 or 3"),
    ([{"thumbnail": "package/thumb-B.png"}, {"thumbnail": "package/thumb-B.png"}], "twice"),
    ([{"thumbnail": "package/missing.png"}, {"thumbnail": "package/thumb-B.png"}], "cannot find"),
])
def test_ab_refusals(tmp_path, variants, match):
    _, meta = _episode(tmp_path)
    meta["test_and_compare"] = variants
    with pytest.raises(lf.LongformMetaError, match=match):
        lf.thumbnails_of(meta)


def test_thumbnail_over_2mb_or_wrong_type_is_refused(tmp_path):
    big = _thumb(tmp_path, "big.png", size=lf.THUMB_MAX_BYTES + 1)
    with pytest.raises(lf.LongformMetaError, match="2 MB"):
        lf.check_thumbnail(big)
    with pytest.raises(lf.LongformMetaError, match="JPG or PNG"):
        lf.check_thumbnail(_thumb(tmp_path, "t.webp"))


@pytest.mark.parametrize("change, match", [
    ({"format": "v6"}, "not 'longform'"),
    ({"promoted": True}, "never promoted"),
    ({"sponsored": True}, "never promoted"),
    ({"made_for_kids": True}, "made_for_kids"),
    ({"category": "Travel and Events"}, "not one of Studio's"),
])
def test_check_longform_meta_refuses(tmp_path, change, match):
    _, meta = _episode(tmp_path)
    meta.update(change)
    with pytest.raises(lf.LongformMetaError, match=match):
        lf.check_longform_meta(meta)


def test_check_longform_meta_passes_the_episode_shape(tmp_path):
    _, meta = _episode(tmp_path)
    lf.check_longform_meta(meta)


def test_publish_refuses_before_touching_studio(tmp_path):
    """A refused meta returns a result; the page is never opened (no session, no upload)."""
    _, meta = _episode(tmp_path)
    meta["promoted"] = True
    pub = lf.YouTubeLongformWebPublisher(repo=tmp_path, check_fn=lambda: None)
    res = pub.publish(tmp_path / "x.mp4", meta, dry_run=True)
    assert not res.ok and "REFUSED before touching Studio" in res.detail


def test_chips_missing_and_ab_state():
    assert lf.chips_missing("Tags\ndisney world rules\nMagic Kingdom\n0/500", ["disney world rules", "magic kingdom"]) == []
    assert lf.chips_missing("Tags\nmagic kingdom", ["disney world rules", "magic kingdom"]) == ["disney world rules"]
    assert lf.ab_state("A/B Testing\nThumbnail 1 (required)\nAdd thumbnail\nThumbnail 3\nThumbnails ready") == "loading"
    assert lf.ab_state("A/B Testing\nThumbnail 1 (required)\nThumbnail 3\nThumbnails ready") == "ready"


def test_watch_url_and_row_url_are_long_form():
    assert lf.watch_url("abc") == "https://www.youtube.com/watch?v=abc"
    pub = lf.YouTubeLongformWebPublisher(repo=pathlib.Path("."), check_fn=lambda: None)
    assert pub.row_url({"href": "/video/AbCdEfGhIjK/edit"}) == "https://www.youtube.com/watch?v=AbCdEfGhIjK"


def test_longer_checks_wait_and_shorts_unchanged():
    assert lf.YouTubeLongformWebPublisher.checks_wait_ms == 45 * 60_000
    assert yw.YouTubeWebPublisher.checks_wait_ms == yw.S.CHECKS_WAIT_TIMEOUT_MS


def test_registered_in_publish_py():
    assert publish.PUBLISHERS["youtube_longform_web"] is lf.YouTubeLongformWebPublisher
    assert "youtube_longform_web" in publish.VIDEO_PLATFORMS
    assert lf.YouTubeLongformWebPublisher.dry_run_writes is True   # publish.py --dry-run refuses it


class _Loc:
    def __init__(self): self.calls = []
    def set_input_files(self, path): self.calls.append(("set_input_files", path))
    def evaluate(self, js): self.calls.append(("evaluate", js))


class _Cdp:
    def __init__(self): self.sent = []; self.detached = False
    def send(self, method, params=None):
        self.sent.append((method, params))
        return {"result": {"objectId": "obj-1"}} if method == "Runtime.evaluate" else {}
    def detach(self): self.detached = True


class _Page:
    def __init__(self):
        self.cdp = _Cdp()
        page = self
        class _Ctx:
            def new_cdp_session(self, p): assert p is page; return page.cdp
        self.context = _Ctx()
        self.evals = []
    def evaluate(self, js): self.evals.append(js)


def test_small_file_goes_through_playwright(tmp_path):
    f = tmp_path / "small.mp4"; f.write_bytes(b"0" * 1000)
    page, loc = _Page(), _Loc()
    assert lf.set_local_file(page, loc, f) == "playwright"
    assert loc.calls == [("set_input_files", str(f.resolve()))] and not page.cdp.sent


def test_large_file_goes_by_path_over_cdp(tmp_path, monkeypatch):
    monkeypatch.setattr(lf, "PLAYWRIGHT_FILE_LIMIT", 10)
    f = tmp_path / "episode.mp4"; f.write_bytes(b"0" * 100)
    page, loc = _Page(), _Loc()
    assert lf.set_local_file(page, loc, f) == "cdp"
    assert not any(c[0] == "set_input_files" for c in loc.calls)
    assert ("DOM.setFileInputFiles", {"files": [str(f.resolve())], "objectId": "obj-1"}) in page.cdp.sent
    assert page.cdp.detached
