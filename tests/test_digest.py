"""scripts/digest.py — the 07:30 summary: what happened, what is queued, what moved."""
import datetime as dt
import json

import digest

TZ = dt.timezone(dt.timedelta(hours=-7))
NOW = dt.datetime(2026, 9, 14, 7, 30, tzinfo=TZ)
ENTRIES = [
    {"id": 66, "ts": "2026-09-10T10:55:00-0700", "tier": 0, "status": "executed",
     "action": "Old thing", "reasoning": "r", "files": [], "veto_window_close": None,
     "stephen_reviewed": True},
    {"id": 69, "ts": "2026-09-13T20:00:00-0700", "tier": 1, "status": "executed",
     "action": "Published asc842-short-liability.mp4 to youtube: https://youtu.be/NEW",
     "reasoning": "r", "files": [], "veto_window_close": None, "stephen_reviewed": False},
    {"id": 70, "ts": "2026-09-14T06:00:00-0700", "tier": 2, "status": "in_progress",
     "action": "T1 loosening", "reasoning": "r", "files": [],
     "veto_window_close": "2026-09-16T09:00:00-0700", "stephen_reviewed": False},
    {"id": 71, "ts": "2026-09-14T06:05:00-0700", "tier": 2, "status": "executed",
     "action": "Closed window", "reasoning": "r", "files": [],
     "veto_window_close": "2026-09-01T09:00:00-0700", "stephen_reviewed": True},
]


def test_recent_entries_keeps_only_the_last_24_hours():
    recent = digest.recent_entries(ENTRIES, NOW, hours=24)
    assert [e["id"] for e in recent] == [69, 70, 71]


def test_open_veto_windows_lists_only_windows_still_in_the_future():
    assert [e["id"] for e in digest.open_veto_windows(ENTRIES, NOW)] == [70]


def test_queue_cards_lists_every_card_across_every_platform_folder(tmp_path):
    for sub, name in (("manual", "2026-09-14-login-gumroad.md"),
                      ("tiktok", "2026-09-14-asc842-liability.md")):
        d = tmp_path / "marketing" / "publish-queue" / sub
        d.mkdir(parents=True)
        (d / name).write_text("# card\n")
        (d / "asset.mp4").write_bytes(b"v")            # mp4s are not cards
    cards = digest.queue_cards(tmp_path)
    assert sorted(p.name for p in cards) == ["2026-09-14-asc842-liability.md",
                                             "2026-09-14-login-gumroad.md"]


def test_queue_cards_is_empty_when_the_folder_does_not_exist(tmp_path):
    assert digest.queue_cards(tmp_path) == []


def test_snapshot_delta_subtracts_the_previous_row(tmp_path):
    p = tmp_path / "gumroad-snapshots.jsonl"
    p.write_text("\n".join([
        json.dumps({"all_time": {"paid_full_price": 0, "download_events": 15, "revenue_usd": 16.99}}),
        json.dumps({"all_time": {"paid_full_price": 0, "download_events": 17, "revenue_usd": 16.99}}),
    ]) + "\n")
    delta = digest.snapshot_delta(p, ("all_time.paid_full_price", "all_time.download_events",
                                      "all_time.revenue_usd"))
    assert delta == {"all_time.paid_full_price": (0, 0.0),
                     "all_time.download_events": (17, 2.0),
                     "all_time.revenue_usd": (16.99, 0.0)}


def test_snapshot_delta_skips_a_key_absent_from_the_rows(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"a": 1}) + "\n" + json.dumps({"a": 3}) + "\n")
    assert digest.snapshot_delta(p, ("a", "missing.key")) == {"a": (3, 2.0)}


def test_snapshot_delta_of_a_single_row_reports_the_value_with_no_delta(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"a": 5}) + "\n")
    assert digest.snapshot_delta(p, ("a",)) == {"a": (5, None)}


def test_snapshot_delta_of_a_missing_file_is_empty(tmp_path):
    assert digest.snapshot_delta(tmp_path / "nope.jsonl", ("a",)) == {}


def test_compose_has_every_section_and_names_the_open_window(tmp_path):
    md = digest.compose(NOW, digest.recent_entries(ENTRIES, NOW),
                        digest.open_veto_windows(ENTRIES, NOW),
                        [tmp_path / "marketing/publish-queue/tiktok/2026-09-14-x.md"],
                        {"gumroad-snapshots.jsonl": {"all_time.download_events": (17, 2.0)}})
    assert md.startswith("## KDesk digest — 2026-09-14\n")
    for heading in ("### Shipped in the last 24 h", "### Waiting on Stephen",
                    "### Open veto windows", "### Numbers"):
        assert heading in md
    assert "https://youtu.be/NEW" in md
    assert "2026-09-14-x.md" in md
    assert "closes 2026-09-16T09:00:00-0700" in md
    assert "all_time.download_events" in md and "+2" in md


def test_compose_says_so_plainly_when_nothing_happened():
    md = digest.compose(NOW, [], [], [], {})
    assert "Nothing logged in the last 24 h." in md
    assert "Queue is empty." in md
    assert "No open veto windows." in md


def test_compose_redacts_any_email_address_even_a_recognized_kdesk_one(tmp_path, monkeypatch):
    monkeypatch.setattr(digest.privacy, "SALT_FILE", tmp_path / "salt.txt")
    hot = [{"id": 90, "ts": "2026-09-14T06:10:00-0700", "tier": 1, "status": "executed",
            "action": "Emailed santiagokdesk@gmail.com and third.party@example.com "
                      "about the launch",
            "reasoning": "r", "files": [], "veto_window_close": None,
            "stephen_reviewed": False}]
    md = digest.compose(NOW, hot, [], [], {})
    assert "santiagokdesk@gmail.com" not in md
    assert "third.party@example.com" not in md
    assert "@" not in md
    assert "<redacted:" in md


def test_compose_redacts_known_secrets_through_the_session_seam(monkeypatch):
    monkeypatch.setattr(digest.session, "redact_secrets",
                        lambda text, **k: str(text).replace("shh", "***"))
    hot = [{"id": 91, "ts": "2026-09-14T06:10:00-0700", "tier": 1, "status": "executed",
            "action": "token=shh in the log", "reasoning": "r", "files": [],
            "veto_window_close": None, "stephen_reviewed": False}]
    md = digest.compose(NOW, hot, [], [], {})
    assert "shh" not in md and "***" in md


def test_vault_path_is_todays_daily_note(tmp_path):
    assert digest.vault_path(NOW, root=tmp_path) == tmp_path / "01-Daily" / "2026-09-14.md"


def test_append_to_vault_creates_the_note_when_it_is_missing(tmp_path):
    p = digest.append_to_vault("## KDesk digest — 2026-09-14\n\nbody\n", NOW, root=tmp_path)
    assert p.read_text().startswith("## KDesk digest — 2026-09-14")


def test_append_to_vault_creates_the_note_from_the_daily_template_when_missing(tmp_path):
    templates = tmp_path / "_Templates"
    templates.mkdir()
    (templates / "Daily.md").write_text(
        "---\ntype: daily\ndate: {{date:YYYY-MM-DD}}\n---\n\n"
        "# {{date:dddd, MMMM D, YYYY}}\n\n## \U0001f4dd Log\n\n\n")
    p = digest.append_to_vault("## KDesk digest — 2026-09-14\n\nbody\n", NOW, root=tmp_path)
    text = p.read_text()
    assert "date: 2026-09-14" in text
    assert "# Monday, September 14, 2026" in text
    assert "## \U0001f4dd Log" in text
    assert text.count("## KDesk digest") == 1
    assert "## KDesk digest — 2026-09-14\n\nbody" in text


def test_append_to_vault_replaces_an_earlier_digest_rather_than_stacking(tmp_path):
    note = tmp_path / "01-Daily" / "2026-09-14.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Tuesday\n\nMorning pages.\n\n## KDesk digest — 2026-09-14\n\nold\n\n## Later\n\nkeep me\n")
    digest.append_to_vault("## KDesk digest — 2026-09-14\n\nnew\n", NOW, root=tmp_path)
    text = note.read_text()
    assert text.count("## KDesk digest") == 1
    assert "new" in text and "old" not in text
    assert "Morning pages." in text and "keep me" in text


def test_send_builds_a_gmail_to_stephen_through_the_seam(monkeypatch):
    calls = []
    monkeypatch.setattr(digest, "_gws", lambda argv, body=None: calls.append((argv, body)) or {"id": "m"})
    digest.send("## KDesk digest — 2026-09-14\n\nbody\n", NOW)
    argv, body = calls[0]
    assert argv[:4] == ["gmail", "users", "messages", "send"]
    assert "raw" in body


def test_main_dry_run_prints_and_neither_sends_nor_writes(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(digest, "REPO", tmp_path)
    monkeypatch.setattr(digest, "_gws", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    monkeypatch.setattr(digest.ledger, "entries", lambda path=None: ENTRIES)
    monkeypatch.setattr("sys.argv", ["digest.py", "--dry-run", "--send", "--vault"])
    assert digest.main() == 0
    assert "## KDesk digest" in capsys.readouterr().out
