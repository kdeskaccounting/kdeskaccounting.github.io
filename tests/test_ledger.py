"""scripts/ledger.py — the append-only decision log every autonomous action writes to."""
import datetime as dt
import fcntl
import json
import threading

import pytest

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


def test_append_accepts_pending_veto_status_and_round_trips_it(tmp_path):
    p = tmp_path / "decisions.jsonl"
    written = ledger.append("T2 loosening", 2, "pending_veto", "r", [],
                            veto_window_close="2026-09-16T12:00:00-0700", path=p)
    assert written["status"] == "pending_veto"
    assert written["veto_window_close"] == "2026-09-16T12:00:00-0700"
    saved = json.loads(p.read_text().splitlines()[0])
    assert saved["status"] == "pending_veto"
    assert saved["veto_window_close"] == "2026-09-16T12:00:00-0700"
    assert ledger.entries(p)[0]["status"] == "pending_veto"


# --- approves / vetoes: how a LATER entry answers an earlier T2 window -------------------
#
# The ledger is append-only, so Stephen approving #69 early cannot edit #69. It has to be a
# new row that names the ids it answers for, in a field the gate can read - which is what
# `approves` (and its symmetric `vetoes`) is. Entry #81 said the same thing in prose and the
# gate could not see it.

def test_append_writes_approves_only_when_it_is_given(tmp_path):
    p = tmp_path / "decisions.jsonl"
    plain = ledger.append("no ids answered", 0, "executed", "r", [], path=p)
    assert "approves" not in plain, "the field is absent, not null, on an ordinary row"
    assert "vetoes" not in plain
    assert "approves" not in json.loads(p.read_text().splitlines()[0])


def test_append_records_approves_as_a_list_of_ints_and_round_trips_it(tmp_path):
    p = tmp_path / "decisions.jsonl"
    written = ledger.append("Stephen approved 69 and 70", 0, "executed", "r", [],
                            approves=[69, 70], path=p)
    assert written["approves"] == [69, 70]
    saved = json.loads(p.read_text().splitlines()[0])
    assert saved["approves"] == [69, 70]
    assert ledger.entries(p)[0]["approves"] == [69, 70]


def test_append_records_vetoes_symmetrically(tmp_path):
    p = tmp_path / "decisions.jsonl"
    written = ledger.append("Stephen VETOED 69", 0, "executed", "r", [],
                            vetoes=[69], path=p)
    assert written["vetoes"] == [69]
    assert ledger.entries(p)[0]["vetoes"] == [69]
    assert "approves" not in written


def test_append_accepts_the_approved_status(tmp_path):
    p = tmp_path / "decisions.jsonl"
    written = ledger.append("Approved", 0, "approved", "r", [], approves=[69], path=p)
    assert written["status"] == "approved"
    assert ledger.entries(p)[0]["status"] == "approved"


def test_append_refuses_approves_on_a_row_that_did_not_happen(tmp_path):
    """`approves` is a record of Stephen saying yes, not of intending to ask him."""
    p = tmp_path / "decisions.jsonl"
    with pytest.raises(ValueError, match="approves"):
        ledger.append("planning to ask", 0, "planned", "r", [], approves=[69], path=p)
    assert not p.exists(), "a rejected append writes nothing"


def test_append_refuses_an_approves_value_that_is_not_a_list_of_ints(tmp_path):
    p = tmp_path / "decisions.jsonl"
    for bad in ("69", 69, [69, "70"], [69.5]):
        with pytest.raises(ValueError, match="approves"):
            ledger.append("x", 0, "executed", "r", [], approves=bad, path=p)
    with pytest.raises(ValueError, match="vetoes"):
        ledger.append("x", 0, "executed", "r", [], vetoes="69", path=p)
    assert not p.exists()


def test_entries_and_append_raise_ledger_error_naming_the_bad_line(tmp_path):
    p = tmp_path / "decisions.jsonl"
    good = {"id": 1, "ts": "t", "tier": 0, "status": "executed", "action": "a",
            "reasoning": "r", "files": [], "veto_window_close": None, "stephen_reviewed": False}
    p.write_text(
        json.dumps(good) + "\n"
        + json.dumps({**good, "id": 2}) + "\n"
        + "not valid json\n"
    )
    with pytest.raises(ledger.LedgerError) as exc_info:
        ledger.entries(p)
    assert str(p) in str(exc_info.value)
    assert ":3:" in str(exc_info.value)

    with pytest.raises(ledger.LedgerError) as exc_info2:
        ledger.append("x", 0, "executed", "r", [], path=p)
    assert ":3:" in str(exc_info2.value)


def test_append_blocks_while_the_sidecar_lock_is_held_by_another_fd(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [{"id": 5, "ts": "t", "tier": 0, "status": "executed", "action": "a",
                "reasoning": "r", "files": [], "veto_window_close": None,
                "stephen_reviewed": False}])
    lock_path = p.with_name(p.name + ".lock")
    lock_fh = open(lock_path, "a+")
    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)

    result: dict = {}

    def do_append():
        result["row"] = ledger.append("blocked until unlocked", 0, "executed", "r", [], path=p)

    t = threading.Thread(target=do_append)
    t.start()
    t.join(timeout=0.3)
    assert t.is_alive(), "append() must block while the sidecar lock is held elsewhere"

    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
    lock_fh.close()
    t.join(timeout=2)
    assert not t.is_alive(), "append() must complete once the lock is released"
    assert result["row"]["id"] == 6


def test_find_and_veto_close_read_a_specific_entry(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [{"id": 69, "ts": "t", "tier": 2, "status": "in_progress", "action": "T1 loosening",
                "reasoning": "r", "files": [], "veto_window_close": "2026-09-16T09:00:00-0700",
                "stephen_reviewed": False}])
    assert ledger.find(69, p)["action"] == "T1 loosening"
    assert ledger.find(70, p) is None
    assert ledger.veto_close(69, p) == "2026-09-16T09:00:00-0700"
    assert ledger.veto_close(70, p) is None


# --------------------------------------------------------------------------- parse_ts
# Was two private `_parse_iso` copies (scripts/digest.py, scripts/sales/send_reengage.py),
# each written to fix the same bug independently: datetime.fromisoformat only learned to
# read the ledger's colon-free `-0700` offset in Python 3.11, and this repo's scripts run
# under both the system python3 (3.9.6 on this Mac) and `uv run`'s newer interpreter.

def test_parse_ts_reads_the_colon_free_offset_ledger_append_actually_writes():
    parsed = ledger.parse_ts("2026-09-16T12:00:00-0700")
    assert parsed == dt.datetime(2026, 9, 16, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))


def test_parse_ts_reads_every_shape_the_ledger_or_a_human_writes():
    colon = ledger.parse_ts("2026-09-16T12:00:00-07:00")
    z = ledger.parse_ts("2026-09-16T19:00:00Z")
    naive = ledger.parse_ts("2026-09-16T12:00:00")
    assert colon == dt.datetime(2026, 9, 16, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
    assert z == dt.datetime(2026, 9, 16, 19, 0, tzinfo=dt.timezone.utc)
    assert naive == dt.datetime(2026, 9, 16, 12, 0)
    assert naive.tzinfo is None


def test_parse_ts_raises_value_error_on_garbage():
    with pytest.raises(ValueError, match="unparseable"):
        ledger.parse_ts("not a timestamp")


# --- the T2 act-with-veto-window gate ----------------------------------------------------
#
# Lived in send_reengage.py, where it was written for one caller. publish.py cites the same
# decision (#69) to justify its T1 ledger rows, so the gate has to live where both can reach
# it - and a second copy would be a second place to get "vetoed but elapsed" wrong.

TZ = dt.timezone(dt.timedelta(hours=-7))
BEFORE = dt.datetime(2026, 9, 15, 8, 0, tzinfo=TZ)
AFTER = dt.datetime(2026, 9, 17, 8, 0, tzinfo=TZ)


def _entry(**over) -> dict:
    row = {"id": 69, "ts": "2026-09-14T14:40:00-0700", "tier": 2, "status": "pending_veto",
           "action": "T1 loosening", "reasoning": "r", "files": [],
           "veto_window_close": "2026-09-16T12:00:00-0700", "stephen_reviewed": False}
    row.update(over)
    return row


def _ledger_with(tmp_path, *rows):
    p = tmp_path / "decisions.jsonl"
    _write(p, list(rows))
    return p


def test_t2_window_open_is_false_before_the_window_closes(tmp_path):
    ok, why = ledger.t2_window_open(69, BEFORE, path=_ledger_with(tmp_path, _entry()))
    assert ok is False
    assert "2026-09-16" in why


def test_t2_window_open_is_true_once_the_window_has_closed(tmp_path):
    ok, why = ledger.t2_window_open(69, AFTER, path=_ledger_with(tmp_path, _entry()))
    assert ok is True
    assert "closed" in why


def test_t2_window_open_refuses_an_entry_that_does_not_exist_yet(tmp_path):
    ok, why = ledger.t2_window_open(69, AFTER, path=_ledger_with(tmp_path))
    assert ok is False
    assert "does not exist" in why


def test_t2_window_open_refuses_an_entry_of_the_wrong_tier(tmp_path):
    """A T0 note authorises nothing, however old it is."""
    ok, why = ledger.t2_window_open(69, AFTER,
                                    path=_ledger_with(tmp_path, _entry(tier=0)))
    assert ok is False
    assert "tier 0" in why


def test_t2_window_open_refuses_an_entry_stephen_actually_vetoed(tmp_path):
    """The check that matters most: an elapsed window does not turn a veto into permission."""
    ok, why = ledger.t2_window_open(69, AFTER,
                                    path=_ledger_with(tmp_path, _entry(status="vetoed")))
    assert ok is False
    assert "VETOED" in why


def test_t2_window_open_refuses_an_entry_with_no_window_at_all(tmp_path):
    ok, why = ledger.t2_window_open(69, AFTER,
                                    path=_ledger_with(tmp_path, _entry(veto_window_close=None)))
    assert ok is False
    assert "no veto_window_close" in why


def test_veto_ok_refuses_a_naive_now_rather_than_guessing_an_offset():
    ok, why = ledger.veto_ok("2026-09-16T12:00:00-0700",
                             dt.datetime(2026, 9, 17, 8, 0))
    assert ok is False
    assert "naive" in why


def test_veto_ok_refuses_an_unparseable_window_rather_than_assuming_it_closed():
    ok, why = ledger.veto_ok("not a timestamp", AFTER)
    assert ok is False
    assert "unparseable" in why
