"""scripts/video/reupload_locked.py — re-publish the 20 locked-private Data-API uploads."""
import json
import pathlib

import pytest

import reupload_locked as rl
import youtube_publish as yp
from publishers.base import PublishResult


@pytest.fixture(autouse=True)
def _never_touch_the_real_ledger(monkeypatch):
    """live_run() always calls ledger.append(); every test here uses a throwaway tmp_path
    repo but ledger.append's default path is the REAL decisions/decisions.jsonl (Task 1's
    ledger.append(path=...) parameter is optional and live_run() never passes one). Without
    this, any test that reaches live_run() would silently append a real row to the repo's
    actual audit log. Autouse so a future test that calls live_run() is protected by default;
    a test that wants to inspect the call overrides this with its own
    monkeypatch.setattr(rl.ledger, "append", ...), which simply wins for that test.
    """
    monkeypatch.setattr(rl.ledger, "append",
                        lambda **kw: {"id": 0, "ts": "1970-01-01T00:00:00+0000"})


def _repo(tmp_path):
    mv = tmp_path / "marketing" / "video"
    (mv / "asc842").mkdir(parents=True)
    (mv / "rsu-planner").mkdir(parents=True)
    (mv / "asc842" / "shorts.json").write_text(json.dumps({
        "liability": {"title": "Lease liability #Shorts", "description": "PV of payments.",
                      "url": "https://youtube.com/shorts/n1BlUeme0k4", "video_id": "n1BlUeme0k4",
                      "uploaded": "2026-09-04 22:21", "via": "data-api"},
        "rollforward": {"title": "Rollforward #Shorts", "description": "Opening + additions.",
                        "url": "https://youtube.com/shorts/nHSki3m6fRI", "video_id": "nHSki3m6fRI",
                        "uploaded": "2026-09-04 22:21", "via": "upload-post"}}))
    (mv / "asc842" / "short.json").write_text(json.dumps({
        "title": "Legacy short", "description": "d", "url": "https://youtube.com/shorts/OrgGKSkFHoY",
        "video_id": "OrgGKSkFHoY"}))                                   # no "via" -> Chrome-era, skip
    (mv / "rsu-planner" / "youtube.json").write_text(json.dumps({
        "title": "RSU walkthrough", "description": "d", "url": "https://youtu.be/-rfZDelJQMY",
        "video_id": "-rfZDelJQMY", "uploaded": "2026-09-05 09:11", "via": "data-api"}))
    return tmp_path


def test_scan_finds_only_the_data_api_records(tmp_path):
    items = rl.scan(_repo(tmp_path))
    assert [(i.slug, i.kind, i.key) for i in items] == [
        ("asc842", "shorts", "liability"), ("rsu-planner", "youtube", None)]


def test_scan_carries_the_original_title_description_and_old_url(tmp_path):
    item = rl.scan(_repo(tmp_path))[0]
    assert item.title == "Lease liability #Shorts"
    assert item.description == "PV of payments."
    assert item.old_url == "https://youtube.com/shorts/n1BlUeme0k4"
    assert item.video_id == "n1BlUeme0k4"


def test_resolve_mp4_prefers_the_named_short_variant_in_the_build_dir(tmp_path):
    repo = _repo(tmp_path)
    build = repo / "scripts" / "video" / "build" / "asc842"
    build.mkdir(parents=True)
    (build / "asc842-short-liability.mp4").write_bytes(b"v")
    item = rl.scan(repo)[0]
    assert rl.resolve_mp4(repo, item) == build / "asc842-short-liability.mp4"


def test_resolve_mp4_finds_the_walkthrough_by_slug(tmp_path):
    repo = _repo(tmp_path)
    build = repo / "scripts" / "video" / "build" / "rsu-planner"
    build.mkdir(parents=True)
    (build / "rsu-planner.mp4").write_bytes(b"v")
    item = rl.scan(repo)[1]
    assert rl.resolve_mp4(repo, item) == build / "rsu-planner.mp4"


def test_resolve_mp4_returns_none_when_nothing_is_on_disk(tmp_path):
    repo = _repo(tmp_path)
    assert rl.resolve_mp4(repo, rl.scan(repo)[0]) is None


def test_expected_mp4_names_cover_both_legacy_and_named_shorts():
    assert rl.expected_mp4_name("asc842", "shorts", "liability") == "asc842-short-liability.mp4"
    assert rl.expected_mp4_name("asc842", "short", None) == "asc842-short.mp4"
    assert rl.expected_mp4_name("asc842", "youtube", None) == "asc842.mp4"


def test_update_record_rewrites_the_url_and_flips_via_for_a_named_variant(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[0]
    rl.update_record(item, "https://youtube.com/shorts/NEW111")
    saved = json.loads((repo / "marketing/video/asc842/shorts.json").read_text())
    assert saved["liability"]["url"] == "https://youtube.com/shorts/NEW111"
    assert saved["liability"]["via"] == "upload-post"
    assert saved["liability"]["replaced_url"] == "https://youtube.com/shorts/n1BlUeme0k4"
    assert saved["rollforward"]["url"] == "https://youtube.com/shorts/nHSki3m6fRI"   # untouched


def test_update_record_rewrites_a_flat_record(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[1]
    rl.update_record(item, "https://youtu.be/NEW222")
    saved = json.loads((repo / "marketing/video/rsu-planner/youtube.json").read_text())
    assert saved["url"] == "https://youtu.be/NEW222"
    assert saved["via"] == "upload-post"
    assert saved["replaced_url"] == "https://youtu.be/-rfZDelJQMY"


def test_meta_for_builds_the_publisher_payload(tmp_path):
    """Brief defect, fixed here: the original brief's expected payload used the raw
    description verbatim and tags=[], which silently dropped short_description()'s TAIL
    (disclaimer + site link) and TAGS[slug] + ["Shorts"] that youtube_publish.py's short_job()
    actually put on every Short it uploaded. meta_for() must reproduce those, not omit them."""
    item = rl.scan(_repo(tmp_path))[0]
    meta = rl.meta_for(item)
    assert meta["slug"] == "asc842-liability"
    assert meta["title"] == "Lease liability #Shorts"
    assert meta["description"] == yp.short_description("PV of payments.")
    assert meta["privacy"] == "public"
    assert meta["product"] == "asc842"
    assert meta["tags"] == yp.TAGS["asc842"] + ["Shorts"]


def test_meta_for_keeps_the_full_walkthrough_description_and_tags_for_a_youtube_kind_item(tmp_path):
    """A walkthrough's description is already the finished text (verbatim off the record, or
    already run through walkthrough_description() in scan()'s META fallback) — meta_for must
    not wrap it again, and its tags come from TAGS[slug] alone, without "Shorts" appended."""
    item = rl.scan(_repo(tmp_path))[1]   # rsu-planner / youtube — title/description already on the record
    meta = rl.meta_for(item)
    assert meta["slug"] == "rsu-planner"
    assert meta["description"] == "d"
    assert meta["tags"] == yp.TAGS["rsu-planner"]
    assert "Shorts" not in meta["tags"]


def test_scan_fills_a_missing_walkthrough_title_from_youtube_publish_meta(tmp_path):
    """youtube.json never stored title/description; scan() must rebuild them the same way
    youtube_publish.walkthrough_job() did, from its META dict, rather than leaving them blank."""
    mv = tmp_path / "marketing" / "video" / "asc842"
    mv.mkdir(parents=True)
    (mv / "youtube.json").write_text(json.dumps({
        "url": "https://youtu.be/5lkrHbWlb4c", "video_id": "5lkrHbWlb4c",
        "uploaded": "2026-09-04 22:21", "via": "data-api"}))          # no title, no description
    item = rl.scan(tmp_path)[0]
    expected_title, expected_blurb = yp.META["asc842"]
    assert item.title == expected_title
    # no scenes.yaml / durations.json in this tmp repo -> the chapters-based description isn't
    # buildable, so the fallback degrades to the blurb alone rather than failing outright.
    assert item.description == expected_blurb


def test_scan_flags_a_walkthrough_with_no_title_and_no_meta_fallback(tmp_path):
    """A slug outside youtube_publish.META has no fallback at all; scan() must not invent one,
    so main() can refuse to upload it live instead of publishing a blank title."""
    mv = tmp_path / "marketing" / "video" / "unknown-product"
    mv.mkdir(parents=True)
    (mv / "youtube.json").write_text(json.dumps({
        "url": "https://youtu.be/ZZZ999", "video_id": "ZZZ999",
        "uploaded": "2026-09-04 22:21", "via": "data-api"}))
    item = rl.scan(tmp_path)[0]
    assert item.title == ""


def test_scan_returns_empty_list_when_marketing_video_is_absent(tmp_path):
    assert rl.scan(tmp_path) == []


# ---------- Fix 1: video_id must survive a watch?v= url, not just a path-segment one ----------

def test_update_record_derives_video_id_from_a_watch_query_param(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[1]   # rsu-planner / youtube
    rl.update_record(item, "https://www.youtube.com/watch?v=ABC123")
    saved = json.loads((repo / "marketing/video/rsu-planner/youtube.json").read_text())
    assert saved["video_id"] == "ABC123"          # not "watch" (rsplit("/")[-1] on this url)


def test_update_record_derives_video_id_from_the_shorts_path_segment(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[0]   # asc842 / shorts / liability
    rl.update_record(item, "https://youtube.com/shorts/XYZ789")
    saved = json.loads((repo / "marketing/video/asc842/shorts.json").read_text())
    assert saved["liability"]["video_id"] == "XYZ789"


# ---------- Fix 2: an async accept that times out must never be silently re-attempted ----------

def test_pending_request_id_from_detail_extracts_the_id_from_an_async_timeout_and_ignores_ordinary_failures():
    timeout_detail = ("Upload-Post accepted the upload (request_id abc-123) but it was still not "
                       "ready after 5 checks: still pending. DO NOT RE-UPLOAD — it may already be "
                       "live, and each attempt burns one of the monthly upload slots.")
    assert rl.pending_request_id_from_detail(timeout_detail) == "abc-123"
    assert rl.pending_request_id_from_detail("Upload-Post HTTP 500: server error") is None


def test_mark_pending_persists_the_request_id_without_touching_url_or_via(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[0]
    rl.mark_pending(item, "req-abc")
    saved = json.loads((repo / "marketing/video/asc842/shorts.json").read_text())
    assert saved["liability"]["pending_request_id"] == "req-abc"
    assert saved["liability"]["url"] == "https://youtube.com/shorts/n1BlUeme0k4"
    assert saved["liability"]["via"] == "data-api"


def test_live_run_skips_a_record_with_a_pending_request_id_and_never_calls_publish_again(tmp_path):
    """Resume behaviour: a record a previous run already marked pending must not be
    re-submitted to Upload-Post on the next run — that would risk double-posting a video that
    may already be live."""
    mv = tmp_path / "marketing" / "video" / "prod-p"
    mv.mkdir(parents=True)
    (mv / "short.json").write_text(json.dumps({
        "title": "P title", "description": "P desc.",
        "url": "https://youtube.com/shorts/PPP000", "video_id": "PPP000",
        "uploaded": "2026-09-04 22:21", "via": "data-api",
        "pending_request_id": "req-already-pending"}))
    build = tmp_path / "scripts" / "video" / "build" / "prod-p"
    build.mkdir(parents=True)
    (build / "prod-p-short.mp4").write_bytes(b"v")
    items = rl.scan(tmp_path)
    assert items[0].pending_request_id == "req-already-pending"

    class _BoomPublisher:
        def publish(self, asset, meta, dry_run):
            raise AssertionError("a pending item must never be re-submitted to Upload-Post")

    result = rl.live_run(items, tmp_path, _BoomPublisher())
    assert result == {"done": 0, "failed": 1, "rewritten": set()}
    saved = json.loads((mv / "short.json").read_text())
    assert saved["pending_request_id"] == "req-already-pending"   # untouched
    assert saved["via"] == "data-api"                              # a skip never rewrites anything


# ---------- Fix 4: NO METADATA / missing-mp4 must queue a manual card, never just print ----------

def test_live_run_queues_a_manual_card_for_a_no_metadata_item_and_never_calls_publish(tmp_path):
    mv = tmp_path / "marketing" / "video" / "unknown-product"
    mv.mkdir(parents=True)
    (mv / "youtube.json").write_text(json.dumps({
        "url": "https://youtu.be/ZZZ999", "video_id": "ZZZ999",
        "uploaded": "2026-09-04 22:21", "via": "data-api"}))
    items = rl.scan(tmp_path)
    assert items[0].title == ""

    class _BoomPublisher:
        def publish(self, asset, meta, dry_run):
            raise AssertionError("a title-less item must never reach publish()")

    result = rl.live_run(items, tmp_path, _BoomPublisher())
    assert result["failed"] == 1
    assert result["rewritten"] == set()
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 1
    assert "no stored title" in cards[0].read_text()


def test_live_run_queues_a_manual_card_for_a_missing_mp4_and_names_the_regen_command(tmp_path):
    repo = _repo(tmp_path)   # asc842/shorts/liability has no mp4 anywhere in this repo
    items = rl.scan(repo)

    class _BoomPublisher:
        def publish(self, asset, meta, dry_run):
            raise AssertionError("an item with no local mp4 must never reach publish()")

    result = rl.live_run([items[0]], repo, _BoomPublisher())
    assert result["failed"] == 1
    assert result["rewritten"] == set()
    cards = list((repo / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 1
    body = cards[0].read_text()
    assert "make_short.py --slug asc842 --variant liability" in body
    assert "gh release download" in body


# ---------- Fix 5: a record write must never leave a half-written file behind ----------

def test_update_record_write_is_atomic_and_leaves_the_original_file_intact_if_replace_fails(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[0]
    path = repo / "marketing" / "video" / "asc842" / "shorts.json"
    original = path.read_text()

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(rl.os, "replace", boom)
    with pytest.raises(OSError):
        rl.update_record(item, "https://youtube.com/shorts/NEW111")
    assert path.read_text() == original
    assert not any(p.name.startswith("shorts.json.tmp") for p in path.parent.iterdir())


# ---------- Fix 6: the live loop end to end, with a stub publisher ----------

def test_live_run_stub_publisher_covers_success_queued_pending_and_scopes_the_ledger(tmp_path, monkeypatch):
    mv = tmp_path / "marketing" / "video"
    for slug in ("prod-a", "prod-b", "prod-c"):
        (mv / slug).mkdir(parents=True)
        build = tmp_path / "scripts" / "video" / "build" / slug
        build.mkdir(parents=True)
        (build / f"{slug}-short.mp4").write_bytes(b"v")
    (mv / "prod-a" / "short.json").write_text(json.dumps({
        "title": "A title", "description": "A desc.",
        "url": "https://youtube.com/shorts/AAA111", "video_id": "AAA111",
        "uploaded": "2026-09-04 22:21", "via": "data-api"}))
    (mv / "prod-b" / "short.json").write_text(json.dumps({
        "title": "B title", "description": "B desc.",
        "url": "https://youtube.com/shorts/BBB222", "video_id": "BBB222",
        "uploaded": "2026-09-04 22:21", "via": "data-api"}))
    (mv / "prod-c" / "short.json").write_text(json.dumps({
        "title": "C title", "description": "C desc.",
        "url": "https://youtube.com/shorts/CCC333", "video_id": "CCC333",
        "uploaded": "2026-09-04 22:21", "via": "data-api"}))
    items = rl.scan(tmp_path)
    assert [i.slug for i in items] == ["prod-a", "prod-b", "prod-c"]

    results = {
        "prod-a": PublishResult(platform="youtube", ok=True, url="https://youtube.com/shorts/NEWAAA",
                                queued_path=None, detail="published via Upload-Post"),
        "prod-b": PublishResult(platform="youtube", ok=False, url=None,
                                queued_path="marketing/publish-queue/youtube/2026-09-14-prod-b.md",
                                detail="Upload-Post HTTP 500: server error"),
        "prod-c": PublishResult(platform="youtube", ok=False, url=None, queued_path=None,
                                detail=("Upload-Post accepted the upload (request_id req-999) but "
                                        "it was still not ready after 5 checks: still pending. DO "
                                        "NOT RE-UPLOAD — it may already be live, and each attempt "
                                        "burns one of the monthly upload slots.")),
    }

    class _StubPublisher:
        def __init__(self):
            self.calls = []

        def publish(self, asset, meta, dry_run):
            self.calls.append(meta["slug"])
            return results[meta["slug"]]

    stub = _StubPublisher()
    captured = {}
    monkeypatch.setattr(rl.ledger, "append",
                        lambda **kw: captured.update(kw) or {"id": 999, "ts": "x"})

    result = rl.live_run(items, tmp_path, stub)

    assert stub.calls == ["prod-a", "prod-b", "prod-c"]
    assert result["done"] == 1
    assert result["failed"] == 2
    assert result["rewritten"] == {"marketing/video/prod-a/short.json",
                                   "marketing/video/prod-c/short.json"}

    a_saved = json.loads((mv / "prod-a" / "short.json").read_text())
    assert a_saved["url"] == "https://youtube.com/shorts/NEWAAA"
    assert a_saved["via"] == "upload-post"
    assert a_saved["replaced_url"] == "https://youtube.com/shorts/AAA111"

    b_saved = json.loads((mv / "prod-b" / "short.json").read_text())
    assert b_saved["url"] == "https://youtube.com/shorts/BBB222"   # untouched
    assert b_saved["via"] == "data-api"
    assert "replaced_url" not in b_saved

    c_saved = json.loads((mv / "prod-c" / "short.json").read_text())
    assert c_saved["pending_request_id"] == "req-999"
    assert c_saved["via"] == "data-api"          # not re-uploaded, just marked pending
    assert c_saved["url"] == "https://youtube.com/shorts/CCC333"

    assert captured["files"] == sorted(result["rewritten"])
    assert captured["tier"] == 1
    assert captured["status"] == "executed"


def test_live_run_with_nothing_to_do_writes_no_ledger_row(tmp_path, monkeypatch):
    """"Ledger entry on every live side effect" - and only on one. A --slug that matches
    nothing, or a second run after everything has been re-uploaded, produced
    "Re-uploaded 0 of 0 locked-private YouTube videos" in the audit log: a row recording
    that nothing happened, which the digest then reports as activity."""
    rows = []
    monkeypatch.setattr(rl.ledger, "append", lambda **kw: rows.append(kw) or {"id": 0})
    result = rl.live_run([], tmp_path, pub=None)
    assert rows == [], "no side effect, no ledger line"
    assert result == {"done": 0, "failed": 0, "rewritten": set()}


def test_live_run_still_logs_when_every_item_only_queued(tmp_path, monkeypatch):
    """The other side of the same line: items that all failed IS a side effect worth a row -
    queue cards were written and a human has work to do. Only an empty run is silent."""
    rows = []
    monkeypatch.setattr(rl.ledger, "append", lambda **kw: rows.append(kw) or {"id": 0})
    repo = _repo(tmp_path)
    items = [i for i in rl.scan(repo) if not i.title][:1] or rl.scan(repo)[:1]
    monkeypatch.setattr(rl, "resolve_mp4", lambda repo, item: None)
    rl.live_run(items, repo, pub=None)
    assert len(rows) == 1
