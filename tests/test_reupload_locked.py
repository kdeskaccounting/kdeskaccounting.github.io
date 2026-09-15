"""scripts/video/reupload_locked.py — re-publish the 20 locked-private Data-API uploads."""
import json
import pathlib

import reupload_locked as rl


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
    item = rl.scan(_repo(tmp_path))[0]
    meta = rl.meta_for(item)
    assert meta == {"slug": "asc842-liability", "title": "Lease liability #Shorts",
                    "description": "PV of payments.", "privacy": "public", "product": "asc842",
                    "tags": []}
