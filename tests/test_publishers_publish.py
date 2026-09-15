"""scripts/publishers/publish.py — the CLI: exit codes, ledger lines, meta handling."""
import json

import pytest

from publishers import publish
from publishers import upload_post as up

META = {"slug": "asc842-liability", "title": "ASC 842 Lease Liability in Excel",
        "description": "PV of the remaining payments.", "privacy": "public",
        "tags": ["ASC 842", "Excel"], "product": "asc842"}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A tmp repo, an asset, a meta.json, and a ledger that records instead of writing."""
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(META), encoding="utf-8")
    rows = []
    monkeypatch.setattr(publish.ledger, "append",
                        lambda **kw: rows.append(kw) or dict(kw))
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    return {"repo": tmp_path, "asset": asset, "meta": meta_path, "rows": rows}


def _run(rig, platform, *extra):
    return publish.main(["--platform", platform, "--asset", str(rig["asset"]),
                         "--meta", str(rig["meta"]), *extra], repo=rig["repo"])


def test_capabilities_exits_zero_and_prints_one_line_per_publisher(capsys):
    assert publish.main(["--capabilities"]) == 0
    printed = capsys.readouterr().out.strip().splitlines()
    assert len(printed) == len(publish.PUBLISHERS)
    assert all(name in "".join(printed) for name in publish.PUBLISHERS)


def test_a_successful_publish_exits_zero_and_appends_exactly_one_ledger_line(rig):
    rig["meta"].write_text(json.dumps({**META, "video_url": "https://youtu.be/VID"}),
                           encoding="utf-8")
    assert _run(rig, "site") == 0
    assert len(rig["rows"]) == 1
    assert rig["rows"][0]["tier"] == 1
    assert rig["rows"][0]["status"] == "executed"
    assert "site" in rig["rows"][0]["action"]


def test_a_queued_platform_exits_one_and_still_logs_the_card(rig):
    assert _run(rig, "youtube") == 1                       # no UPLOAD_POST_KEY -> queued
    assert len(rig["rows"]) == 1
    assert rig["rows"][0]["files"], "the card must be named in the ledger line"


def test_an_unknown_platform_exits_two(rig, capsys):
    assert _run(rig, "myspace") == 2
    assert "unknown platform" in capsys.readouterr().err


def test_an_unknown_platform_is_not_downgraded_by_a_later_queued_platform(rig):
    # rc started as 2, then a queued youtube set rc = 1 and lost the harder failure.
    assert _run(rig, "myspace,youtube") == 2


def test_dry_run_appends_no_ledger_line_and_writes_nothing(rig):
    assert _run(rig, "youtube,instagram,site", "--dry-run") == 0
    assert rig["rows"] == []
    assert not (rig["repo"] / "marketing").exists()
    assert not (rig["repo"] / "content").exists()


def test_a_video_url_from_a_video_platform_is_threaded_into_the_site_post(rig, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (200, {
        "success": True,
        "results": {"youtube": {"success": True, "url": "https://youtu.be/THREADED"}}}))
    assert _run(rig, "youtube,site") == 0
    posts = list((rig["repo"] / "content" / "shorts").glob("*.md"))
    assert len(posts) == 1
    assert "https://www.youtube.com/embed/THREADED" in posts[0].read_text(encoding="utf-8")


def test_malformed_meta_json_exits_two_without_a_traceback(rig, capsys):
    rig["meta"].write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run(rig, "site")
    assert exc.value.code == 2
    assert "meta" in capsys.readouterr().err.lower()


def test_a_non_dict_meta_is_rejected(rig, capsys):
    rig["meta"].write_text('["a", "list"]', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run(rig, "site")
    assert exc.value.code == 2
    assert "object" in capsys.readouterr().err.lower()


def test_a_missing_asset_exits_two_without_a_traceback(rig, capsys):
    rig["asset"].unlink()
    with pytest.raises(SystemExit) as exc:
        _run(rig, "site")
    assert exc.value.code == 2
    assert "--asset" in capsys.readouterr().err


def test_the_api_key_never_reaches_stdout_or_the_ledger(rig, monkeypatch, capsys):
    key = "up_live_CLISECRET1"
    monkeypatch.setenv("UPLOAD_POST_KEY", key)
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (
        401, {"success": False, "message": f"Invalid credential {key} for profile kdesk"}))
    assert _run(rig, "youtube") == 1
    assert key not in capsys.readouterr().out
    assert key not in rig["rows"][0]["action"]
    card = rig["repo"] / rig["rows"][0]["files"][0]
    assert key not in card.read_text(encoding="utf-8")


# --- --whoami answers "is user=kdesk the right profile?" from the documented profile
# listing, before the first upload burns a slot on a 400 "Username required in form data".

def test_whoami_without_a_key_exits_one_and_calls_nothing(monkeypatch, capsys):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    monkeypatch.setattr(up, "_http_get", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no HTTP call may happen without a key")))
    assert publish.main(["--whoami"]) == 1
    assert "UPLOAD_POST_KEY" in capsys.readouterr().err


def test_whoami_prints_the_profiles_and_never_the_key(monkeypatch, capsys):
    key = "up_live_WHOAMIKEY1"
    monkeypatch.setenv("UPLOAD_POST_KEY", key)
    monkeypatch.setattr(up, "_http_get", lambda url, headers, params: (
        200, {"success": True, "profiles": [{"username": "kdesk", "key_echo": key}]}))
    assert publish.main(["--whoami"]) == 0
    out = capsys.readouterr().out
    assert "kdesk" in out
    assert key not in out
