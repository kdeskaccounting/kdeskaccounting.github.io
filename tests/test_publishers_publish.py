"""scripts/publishers/publish.py — the CLI: exit codes, the veto gate, ledger lines, meta."""
import datetime as dt
import json

import pytest

from publishers import publish
from publishers import upload_post as up

TZ = dt.timezone(dt.timedelta(hours=-7))
# Entry 69's real window closes 2026-09-16 12:00 PT. Both stamps are fixtures: the tests
# must not change their answer on the day it actually closes, or the day Stephen vetoes it.
BEFORE = dt.datetime(2026, 9, 15, 8, 0, tzinfo=TZ)
AFTER = dt.datetime(2026, 9, 17, 8, 0, tzinfo=TZ)


def autonomy_entry(**over) -> dict:
    row = {"id": publish.VETO_ENTRY, "ts": "2026-09-14T14:40:00-0700", "tier": 2,
           "status": "pending_veto", "action": "T1 auto-publish for five surfaces",
           "reasoning": "r", "files": [],
           "veto_window_close": "2026-09-16T12:00:00-0700", "stephen_reviewed": False}
    row.update(over)
    return row

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
    # The gate reads the live ledger otherwise. Every test below that is not about the gate
    # runs at AFTER against a closed, un-vetoed window - the world in which publishing is
    # authorised at all.
    monkeypatch.setattr(publish.ledger, "find",
                        lambda entry_id, path=None: autonomy_entry())
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    return {"repo": tmp_path, "asset": asset, "meta": meta_path, "rows": rows}


def _run(rig, platform, *extra, now=AFTER):
    return publish.main(["--platform", platform, "--asset", str(rig["asset"]),
                         "--meta", str(rig["meta"]), *extra], repo=rig["repo"], now=now)


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


# --- the veto gate -----------------------------------------------------------------------
#
# publish.py wrote tier-1 ledger rows citing "the 2026-09-14 autonomy decision" while that
# decision (#69) was still pending_veto. The rows were true about what happened and false
# about what authorised it: until the window closes unvetoed the rule is still "queues, not
# auto-posters". Nothing bypasses this - there is deliberately no --i-accept-veto-risk.

def test_a_live_publish_refuses_while_the_autonomy_window_is_still_open(rig, capsys):
    rig["meta"].write_text(json.dumps({**META, "video_url": "https://youtu.be/VID"}),
                           encoding="utf-8")
    assert _run(rig, "site", now=BEFORE) == 2
    err = capsys.readouterr().err
    assert f"entry {publish.VETO_ENTRY}" in err
    assert "2026-09-16" in err
    assert "--dry-run" in err, "say what the caller can do instead"
    assert rig["rows"] == [], "a refused run logs nothing"
    assert not (rig["repo"] / "content").exists(), "and publishes nothing"


def test_a_live_publish_refuses_when_stephen_actually_vetoed_the_decision(rig, monkeypatch,
                                                                          capsys):
    """An elapsed window does not turn a veto into permission."""
    monkeypatch.setattr(publish.ledger, "find",
                        lambda entry_id, path=None: autonomy_entry(status="vetoed"))
    rig["meta"].write_text(json.dumps({**META, "video_url": "https://youtu.be/VID"}),
                           encoding="utf-8")
    assert _run(rig, "site", now=AFTER) == 2
    assert "VETOED" in capsys.readouterr().err
    assert rig["rows"] == []


def test_a_live_publish_refuses_when_the_decision_does_not_exist_yet(rig, monkeypatch,
                                                                    capsys):
    monkeypatch.setattr(publish.ledger, "find", lambda entry_id, path=None: None)
    assert _run(rig, "site", now=AFTER) == 2
    assert "does not exist" in capsys.readouterr().err


def test_a_live_publish_proceeds_once_the_window_has_closed_unvetoed(rig):
    rig["meta"].write_text(json.dumps({**META, "video_url": "https://youtu.be/VID"}),
                           encoding="utf-8")
    assert _run(rig, "site", now=AFTER) == 0
    assert len(rig["rows"]) == 1


def test_dry_run_is_never_gated(rig, capsys):
    """--dry-run performs zero writes, so there is nothing for a veto to protect against -
    and it is the one thing a refused caller is told to run."""
    assert _run(rig, "youtube,site", "--dry-run", now=BEFORE) == 0
    assert rig["rows"] == []


def test_capabilities_and_whoami_are_not_gated(monkeypatch):
    """Read-only probes. Gating them would make diagnosing the gate itself harder."""
    monkeypatch.setattr(publish.ledger, "find", lambda entry_id, path=None: None)
    assert publish.main(["--capabilities"]) == 0


def test_the_gate_runs_before_the_meta_file_is_even_read(rig, capsys):
    """A refused run must not reach the work. Invalid JSON would exit 2 with a parse error;
    the refusal has to come first, with the refusal's own message."""
    rig["meta"].write_text("{not json", encoding="utf-8")
    assert _run(rig, "site", now=BEFORE) == 2
    assert "REFUSING" in capsys.readouterr().err


def test_there_is_no_flag_to_bypass_the_veto_gate(capsys):
    """Deliberate: an override flag is the thing that gets typed at 2 a.m. and committed to
    a workflow file. If the window has not closed, the answer is --dry-run or wait."""
    with pytest.raises(SystemExit):
        publish.main(["--help"])
    help_text = capsys.readouterr().out
    assert "veto" not in help_text.lower() or "--i-accept-veto-risk" not in help_text
    assert "--i-accept-veto-risk" not in help_text


def test_the_gate_is_the_shared_ledger_helper_not_a_second_copy():
    assert publish.ledger.t2_window_open is not None
    assert publish.VETO_ENTRY == 69


# --- tiktok_web: the Chrome-driven TikTok scheduler (2026-09-15). Upload-Post's TikTok
# needs the paid plan Stephen declined, so the week's Shorts are scheduled through TikTok
# Studio instead. It reaches this CLI like any other publisher, plus one flag: --schedule.

from publishers import tiktok_web as tw  # noqa: E402


def _logged_out(monkeypatch):
    """Make the tiktok preflight fail, so no test here can ever open a browser."""
    monkeypatch.setattr(tw.session, "check", lambda *_a, **_k: tw.session.SiteStatus(
        "tiktok", False, tw.S.STUDIO_URL, "https://www.tiktok.com/login", "not logged in"))


def test_tiktok_web_is_a_known_platform():
    assert "tiktok_web" in publish.PUBLISHERS
    assert publish.PUBLISHERS["tiktok_web"] is tw.TikTokWebPublisher


def test_the_upload_post_tiktok_publisher_is_still_there_under_its_own_name():
    """Two transports for one platform; the paid one stays, unused, until the plan changes."""
    assert "tiktok" in publish.PUBLISHERS
    assert publish.PUBLISHERS["tiktok"] is not publish.PUBLISHERS["tiktok_web"]


def test_schedule_is_threaded_into_the_meta_the_publisher_sees(rig, monkeypatch):
    seen = {}
    monkeypatch.setattr(tw.TikTokWebPublisher, "publish",
                        lambda self, asset, meta, dry_run: seen.update(meta) or
                        tw.PublishResult(platform="tiktok_web", ok=True, url="u",
                                         queued_path=None, detail="d"))
    assert _run(rig, "tiktok_web", "--schedule", "2026-09-21T14:00:00-07:00") == 0
    assert seen["schedule_at"] == "2026-09-21T14:00:00-07:00"


def test_without_the_flag_no_schedule_at_is_invented(rig, monkeypatch):
    seen = {}
    monkeypatch.setattr(tw.TikTokWebPublisher, "publish",
                        lambda self, asset, meta, dry_run: seen.update(meta) or
                        tw.PublishResult(platform="tiktok_web", ok=True, url="u",
                                         queued_path=None, detail="d"))
    assert _run(rig, "tiktok_web") == 0
    assert "schedule_at" not in seen


def test_an_unparseable_schedule_exits_two_before_any_publisher_runs(rig, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(rig, "tiktok_web", "--schedule", "next tuesday")
    assert exc.value.code == 2
    assert "--schedule" in capsys.readouterr().err


def test_a_schedule_without_an_offset_exits_two(rig, capsys):
    """'14:00' is a different instant in Los Angeles and in London — refuse, never guess."""
    with pytest.raises(SystemExit) as exc:
        _run(rig, "tiktok_web", "--schedule", "2026-09-21T14:00:00")
    assert exc.value.code == 2
    assert "offset" in capsys.readouterr().err.lower()


def test_a_dry_run_prints_the_schedule_and_writes_nothing(rig, capsys, monkeypatch):
    monkeypatch.setattr(tw.session, "open_page", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("--dry-run must not open a browser")))
    assert _run(rig, "tiktok_web", "--schedule", "2026-09-21T14:00:00-07:00", "--dry-run") == 0
    assert "2026-09-21 14:00" in capsys.readouterr().out
    assert rig["rows"] == []
    assert not (rig["repo"] / "marketing").exists()


def test_a_logged_out_profile_queues_a_card_and_exits_one(rig, monkeypatch):
    _logged_out(monkeypatch)
    assert _run(rig, "tiktok_web") == 1
    assert len(rig["rows"]) == 1
    assert rig["rows"][0]["files"], "the card must be named in the ledger line"
    assert (rig["repo"] / rig["rows"][0]["files"][0]).exists()


def test_the_studio_url_is_not_threaded_into_the_site_post_as_a_video_url(rig, monkeypatch):
    """tiktok_web returns a Studio URL, not a public permalink — embedding it would 404."""
    assert "tiktok_web" not in publish.VIDEO_PLATFORMS
    monkeypatch.setattr(tw.TikTokWebPublisher, "publish",
                        lambda self, asset, meta, dry_run: tw.PublishResult(
                            platform="tiktok_web", ok=True, url=tw.S.CONTENT_URL,
                            queued_path=None, detail="scheduled"))
    seen = {}
    monkeypatch.setattr(publish.SitePublisher, "publish",
                        lambda self, asset, meta, dry_run: seen.update(meta) or
                        tw.PublishResult(platform="site", ok=True, url="/s/", queued_path=None,
                                         detail="d"))
    assert _run(rig, "tiktok_web,site") == 0
    assert "tiktokstudio" not in str(seen.get("video_url", ""))


def test_a_live_tiktok_web_publish_is_gated_by_the_same_veto_entry(rig, monkeypatch, capsys):
    _logged_out(monkeypatch)
    assert _run(rig, "tiktok_web", now=BEFORE) == 2
    assert "REFUSING" in capsys.readouterr().err
    assert rig["rows"] == []
