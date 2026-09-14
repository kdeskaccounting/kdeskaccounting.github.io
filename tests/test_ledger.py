"""scripts/ledger.py — the append-only decision log every autonomous action writes to."""
import datetime as dt
import json

import ledger


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_entries_tolerates_the_repr_string_files_field_used_by_entries_59_to_63(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [
        {"id": 1, "ts": "2026-09-06T09:30:00-0700", "tier": 2, "status": "in_progress",
         "action": "a", "reasoning": "r", "files": "['marketing/outreach/targets.md', 'CLAUDE.md']",
         "veto_window_close": None, "stephen_reviewed": True},
        {"id": 2, "ts": "2026-09-11T09:45:00-0700", "tier": 1, "status": "executed",
         "action": "b", "reasoning": "r", "files": ["CLAUDE.md"],
         "veto_window_close": None, "stephen_reviewed": True},
    ])
    rows = ledger.entries(p)
    assert rows[0]["files"] == ["marketing/outreach/targets.md", "CLAUDE.md"]
    assert rows[1]["files"] == ["CLAUDE.md"]


def test_entries_skips_blank_lines_and_last_id_reads_the_maximum(tmp_path):
    p = tmp_path / "decisions.jsonl"
    p.write_text(json.dumps({"id": 7, "ts": "t", "tier": 0, "status": "executed", "action": "a",
                             "reasoning": "r", "files": [], "veto_window_close": None,
                             "stephen_reviewed": False}) + "\n\n")
    assert len(ledger.entries(p)) == 1
    assert ledger.last_id(p) == 7


def test_last_id_of_a_missing_file_is_zero(tmp_path):
    assert ledger.last_id(tmp_path / "nope.jsonl") == 0


def test_append_allocates_the_next_id_and_writes_one_line_with_the_exact_schema(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [{"id": 68, "ts": "t", "tier": 1, "status": "executed", "action": "a",
                "reasoning": "r", "files": [], "veto_window_close": None, "stephen_reviewed": True}])
    now = dt.datetime(2026, 9, 14, 8, 30, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
    written = ledger.append("Published a Short", 1, "executed", "Because.",
                            ["marketing/video/asc842/shorts.json"], path=p, now=now)
    assert written["id"] == 69
    assert written["ts"] == "2026-09-14T08:30:00-0700"
    lines = p.read_text().splitlines()
    assert len(lines) == 2
    saved = json.loads(lines[1])
    assert saved == {"id": 69, "ts": "2026-09-14T08:30:00-0700", "tier": 1, "status": "executed",
                     "action": "Published a Short", "reasoning": "Because.",
                     "files": ["marketing/video/asc842/shorts.json"],
                     "veto_window_close": None, "stephen_reviewed": False}


def test_append_creates_the_file_and_its_parent_when_missing(tmp_path):
    p = tmp_path / "decisions" / "decisions.jsonl"
    written = ledger.append("First", 0, "executed", "r", [], path=p)
    assert written["id"] == 1
    assert json.loads(p.read_text().splitlines()[0])["action"] == "First"


def test_append_rejects_an_out_of_range_tier(tmp_path):
    p = tmp_path / "decisions.jsonl"
    try:
        ledger.append("x", 4, "executed", "r", [], path=p)
    except ValueError as e:
        assert "tier" in str(e)
    else:
        raise AssertionError("tier 4 must be rejected")
    assert not p.exists()


def test_find_and_veto_close_read_a_specific_entry(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [{"id": 69, "ts": "t", "tier": 2, "status": "in_progress", "action": "T1 loosening",
                "reasoning": "r", "files": [], "veto_window_close": "2026-09-16T09:00:00-0700",
                "stephen_reviewed": False}])
    assert ledger.find(69, p)["action"] == "T1 loosening"
    assert ledger.find(70, p) is None
    assert ledger.veto_close(69, p) == "2026-09-16T09:00:00-0700"
    assert ledger.veto_close(70, p) is None
