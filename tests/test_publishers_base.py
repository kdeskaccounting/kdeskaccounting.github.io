"""scripts/publishers/base.py — the queue-card fallback every publisher shares."""
import datetime as dt
import pathlib

import pytest

from publishers import base

NOW = dt.datetime(2026, 9, 14, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
META = {"slug": "asc842-liability", "title": "ASC 842 Lease Liability in Excel #Shorts",
        "description": "PV of the remaining payments.\nFree: https://kdeskaccounting.com/",
        "privacy": "public", "tags": ["ASC 842", "Excel"]}


def test_publish_result_carries_either_a_url_or_a_queued_path():
    ok = base.PublishResult(platform="youtube", ok=True, url="https://youtu.be/x",
                            queued_path=None, detail="uploaded")
    queued = base.PublishResult(platform="tiktok", ok=False, url=None,
                                queued_path="marketing/publish-queue/tiktok/x.md", detail="403")
    assert ok.url and ok.queued_path is None
    assert queued.queued_path and queued.url is None


def test_queue_card_body_is_paste_ready_with_title_description_and_the_asset():
    body = base.queue_card_body("tiktok", META, "HTTP 403 TikTok uploads not available on Free plan.",
                                "asc842-short-liability.mp4", NOW)
    assert body.startswith("# tiktok — ASC 842 Lease Liability in Excel #Shorts\n")
    assert "2026-09-14 07:00 -0700" in body
    assert "HTTP 403 TikTok uploads not available on Free plan." in body
    assert "asc842-short-liability.mp4" in body
    assert "PV of the remaining payments." in body
    assert "## Caption (copy this)" in body


def test_link_or_copy_symlinks_when_it_can(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video")
    dest = tmp_path / "queue" / "a.mp4"
    dest.parent.mkdir()
    how = base.link_or_copy(src, dest)
    assert how == "symlink"
    assert dest.read_bytes() == b"video"


def test_link_or_copy_falls_back_to_a_real_copy(tmp_path, monkeypatch):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video")
    dest = tmp_path / "a-copy.mp4"

    def boom(self, target, target_is_directory=False):
        raise OSError("cross-device link")

    monkeypatch.setattr(pathlib.Path, "symlink_to", boom)
    assert base.link_or_copy(src, dest) == "copy"
    assert dest.read_bytes() == b"video"
    assert not dest.is_symlink()


class _Stub(base.Publisher):
    platform = "stub"

    def capabilities(self):
        return {"video": True}

    def _do_publish(self, asset, meta):
        raise RuntimeError("upstream exploded")


def test_queue_writes_the_card_and_the_asset_and_returns_a_not_ok_result(tmp_path):
    asset = tmp_path / "asc842-short-liability.mp4"
    asset.write_bytes(b"video")
    pub = _Stub(repo=tmp_path)
    res = pub.queue(asset, META, "upstream exploded")
    assert res.ok is False
    assert res.platform == "stub"
    assert res.url is None
    card = tmp_path / res.queued_path
    assert card.exists()
    assert "upstream exploded" in card.read_text()
    assert (card.parent / asset.name).exists()


def test_publish_dry_run_touches_nothing_and_reports_the_plan(tmp_path, capsys):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"video")
    pub = _Stub(repo=tmp_path)
    res = pub.publish(asset, META, dry_run=True)
    assert res.ok is True
    assert res.url is None and res.queued_path is None
    assert "dry-run" in res.detail
    assert not (tmp_path / "marketing").exists()


def test_publish_falls_back_to_the_queue_when_the_platform_call_raises(tmp_path):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"video")
    res = _Stub(repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is False
    assert res.queued_path is not None
    assert "upstream exploded" in res.detail


def test_publish_refuses_a_missing_asset_without_touching_the_network(tmp_path):
    with pytest.raises(FileNotFoundError):
        _Stub(repo=tmp_path).publish(tmp_path / "gone.mp4", META, dry_run=False)


# ============================ fix round 1 ============================

# --- queue_card_body redacted the WHOLE card, so ordinary accounting copy was corrupted:
# a title like "The secret: a faster close" tripped the `secret:` pattern and reached
# Stephen as "The secret: *** faster close". Only `detail` is machine text.

def test_queue_card_body_masks_the_machine_detail_but_not_the_authors_copy():
    meta = {**META, "title": "The secret: a faster month-end close",
            "description": "Your key: the PV formula. Password: none needed."}
    body = base.queue_card_body("tiktok", meta, "rejected Bearer abc123def456", "x.mp4", NOW)
    assert "Bearer ***" in body                                   # machine text: masked
    assert "abc123def456" not in body
    assert "The secret: a faster month-end close" in body         # author copy: verbatim
    assert "Your key: the PV formula. Password: none needed." in body
