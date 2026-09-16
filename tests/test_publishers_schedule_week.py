"""scripts/publishers/schedule_week.py — the Saturday batch's one command.

The ParkSheet release directory holds day-1.mp4 … day-7.mp4 with a day-N.json beside each.
This maps them onto the week's calendar days at a fixed local time and hands each to the
TikTok Studio driver. What the tests hold still:

* **The day mapping**, including the two things a naive `weekday` arithmetic gets wrong —
  an ISO week number is not a month offset, and 14:00 in Los Angeles is -07:00 in September
  and -08:00 in November.
* **The exit codes**, because the Saturday batch branches on them: 0 all scheduled, 1 at
  least one queued for Stephen, 2 the batch itself is wrong (bad week, missing meta, a veto
  window still open) and nothing was attempted.
* **One ledger line per schedule, carrying no caption past the 40-character key.**

No browser and no Playwright: a fake publisher records what it was asked to do.
"""
import datetime as dt
import json

import pytest

from publishers import schedule_week as sw

PT = dt.timezone(dt.timedelta(hours=-7))
AFTER_VETO = dt.datetime(2026, 9, 17, 8, 0, tzinfo=PT)
BEFORE_VETO = dt.datetime(2026, 9, 15, 8, 0, tzinfo=PT)


class _FakePublisher:
    """Records every publish() call and answers from a scripted list of outcomes."""

    platform = "tiktok_web"

    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = list(outcomes or [])

    def publish(self, asset, meta, dry_run):
        self.calls.append({"asset": asset, "meta": dict(meta), "dry_run": dry_run})
        if self.outcomes:
            ok, detail, url, queued = self.outcomes.pop(0)
        else:
            ok, detail, url, queued = True, "scheduled", "https://www.tiktok.com/x", None
        return sw.PublishResult(platform=self.platform, ok=ok, url=url,
                                queued_path=queued, detail=detail)


@pytest.fixture
def assets(tmp_path):
    """A release dir with three days, the way the render batch leaves it."""
    d = tmp_path / "release"
    d.mkdir()
    for n in (1, 2, 3):
        (d / f"day-{n}.mp4").write_bytes(b"mp4")
        (d / f"day-{n}.json").write_text(json.dumps({
            "slug": f"parksheet-day-{n}",
            "title": f"Day {n} title",
            "description": f"Day {n}: wait times at the parks moved again this week.",
            "tags": ["parks"]}), encoding="utf-8")
    return d


@pytest.fixture
def rows(monkeypatch):
    """Capture ledger writes instead of appending to the real decisions log."""
    captured = []
    monkeypatch.setattr(sw.ledger, "append", lambda **kw: captured.append(kw) or dict(kw))
    monkeypatch.setattr(sw.publish.ledger, "find", lambda entry_id, path=None: {
        "id": 69, "tier": 2, "status": "pending_veto",
        "veto_window_close": "2026-09-16T12:00:00-0700"})
    return captured


def _run(assets, pub, *extra, repo, now=AFTER_VETO, week="2026-W39"):
    """A LIVE run unless the caller says otherwise.

    --go is appended when the caller names neither mode, because these tests are about what
    happens when the batch actually runs. That the default is a dry run is pinned separately,
    by the tests that call sw.main directly.
    """
    if not {"--go", "--dry-run"} & set(extra):
        extra = (*extra, "--go")
    return sw.main(["--week", week, "--assets-dir", str(assets), *extra],
                   repo=repo, publisher=pub, now=now)


# ------------------------------------------------------------------------- the day mapping

def test_the_iso_week_resolves_to_its_monday():
    assert sw.week_start("2026-W39") == dt.date(2026, 9, 21)
    assert sw.week_start("2026-W38") == dt.date(2026, 9, 14)


def test_a_week_number_is_not_a_month_offset():
    """2026-W39 is the week of 21 September, not anything in March."""
    assert sw.week_start("2026-W39").month == 9


def test_a_malformed_week_is_refused():
    for bad in ("2026-39", "W39", "2026-W00", "2026-W54", "next week", ""):
        with pytest.raises(sw.PlanError):
            sw.week_start(bad)


def test_day_one_lands_on_monday_and_day_seven_on_sunday():
    monday = sw.week_start("2026-W39")
    assert sw.slot_for(monday, 1, 1, (14, 0)).date() == dt.date(2026, 9, 21)
    assert sw.slot_for(monday, 1, 7, (14, 0)).date() == dt.date(2026, 9, 27)
    assert sw.slot_for(monday, 1, 1, (14, 0)).strftime("%A") == "Monday"
    assert sw.slot_for(monday, 1, 7, (14, 0)).strftime("%A") == "Sunday"


def test_start_day_shifts_the_whole_run_without_reordering_it():
    monday = sw.week_start("2026-W39")
    assert sw.slot_for(monday, 3, 1, (14, 0)).date() == dt.date(2026, 9, 23)   # Wednesday
    assert sw.slot_for(monday, 3, 2, (14, 0)).date() == dt.date(2026, 9, 24)


def test_a_run_that_overflows_the_week_continues_into_the_next_one():
    """Seven days from Wednesday is the following Tuesday — never a wrap back to Monday."""
    monday = sw.week_start("2026-W39")
    assert sw.slot_for(monday, 3, 7, (14, 0)).date() == dt.date(2026, 9, 29)


def test_the_time_is_local_pacific_and_carries_the_right_offset_across_dst():
    september = sw.slot_for(dt.date(2026, 9, 21), 1, 1, (14, 0))
    november = sw.slot_for(dt.date(2026, 11, 2), 1, 4, (14, 0))
    assert september.isoformat() == "2026-09-21T14:00:00-07:00"
    assert november.isoformat() == "2026-11-05T14:00:00-08:00"      # after the fall-back
    assert september.strftime("%H:%M") == november.strftime("%H:%M") == "14:00"


def test_the_hour_is_parsed_as_twenty_four_hour_and_validated():
    assert sw.parse_hour("14:00") == (14, 0)
    assert sw.parse_hour("09:30") == (9, 30)
    for bad in ("2pm", "25:00", "14:60", "14", ""):
        with pytest.raises(sw.PlanError):
            sw.parse_hour(bad)


# ------------------------------------------------------------------------ finding the days

def test_the_days_are_discovered_in_numeric_order_not_lexical(tmp_path):
    d = tmp_path / "r"
    d.mkdir()
    for n in (1, 2, 10):
        (d / f"day-{n}.mp4").write_bytes(b"v")
        (d / f"day-{n}.json").write_text("{}", encoding="utf-8")
    assert [n for n, _mp4, _meta in sw.discover(d)] == [1, 2, 10]


def test_an_mp4_without_its_json_is_a_hard_error_not_a_silent_skip(assets, rows, tmp_path):
    (assets / "day-4.mp4").write_bytes(b"v")
    pub = _FakePublisher()
    assert _run(assets, pub, repo=tmp_path) == 2
    assert pub.calls == [], "a mis-built batch must not half-publish"


def test_a_missing_assets_dir_is_a_hard_error(tmp_path, rows):
    assert sw.main(["--week", "2026-W39", "--assets-dir", str(tmp_path / "nope")],
                   repo=tmp_path, publisher=_FakePublisher(), now=AFTER_VETO) == 2


def test_an_empty_assets_dir_is_a_hard_error(tmp_path, rows):
    (tmp_path / "empty").mkdir()
    assert sw.main(["--week", "2026-W39", "--assets-dir", str(tmp_path / "empty")],
                   repo=tmp_path, publisher=_FakePublisher(), now=AFTER_VETO) == 2


# ----------------------------------------------------------------------------- the run

def test_each_day_is_handed_to_the_publisher_with_its_own_schedule(assets, rows, tmp_path):
    pub = _FakePublisher()
    assert _run(assets, pub, repo=tmp_path) == 0
    assert [c["asset"].name for c in pub.calls] == ["day-1.mp4", "day-2.mp4", "day-3.mp4"]
    assert [c["meta"]["schedule_at"] for c in pub.calls] == [
        "2026-09-21T14:00:00-07:00",
        "2026-09-22T14:00:00-07:00",
        "2026-09-23T14:00:00-07:00"]


def test_the_meta_reaches_the_publisher_intact(assets, rows, tmp_path):
    pub = _FakePublisher()
    _run(assets, pub, repo=tmp_path)
    assert pub.calls[0]["meta"]["slug"] == "parksheet-day-1"
    assert pub.calls[0]["meta"]["tags"] == ["parks"]


def test_the_hour_flag_moves_every_day(assets, rows, tmp_path):
    pub = _FakePublisher()
    _run(assets, pub, "--hour", "09:30", repo=tmp_path)
    assert all(c["meta"]["schedule_at"].endswith("T09:30:00-07:00") for c in pub.calls)


def test_a_summary_table_names_every_day_its_weekday_and_its_outcome(assets, rows, tmp_path,
                                                                     capsys):
    pub = _FakePublisher([(True, "scheduled", "https://t/1", None),
                          (True, "already scheduled — nothing uploaded", "https://t/2", None),
                          (False, "Timeout", None, "marketing/publish-queue/manual/c.md")])
    assert _run(assets, pub, repo=tmp_path) == 1
    out = capsys.readouterr().out
    for fragment in ("day-1", "day-2", "day-3", "Mon", "Tue", "Wed",
                     "2026-09-21 14:00", "ok", "skip", "QUEUED"):
        assert fragment in out, fragment


# -------------------------------------------------------------------------- exit codes

def test_everything_scheduled_exits_zero(assets, rows, tmp_path):
    assert _run(assets, _FakePublisher(), repo=tmp_path) == 0


def test_one_queued_day_exits_one_and_the_rest_still_run(assets, rows, tmp_path):
    pub = _FakePublisher([(False, "Timeout", None, "marketing/publish-queue/manual/c.md"),
                          (True, "scheduled", "https://t/2", None),
                          (True, "scheduled", "https://t/3", None)])
    assert _run(assets, pub, repo=tmp_path) == 1
    assert len(pub.calls) == 3, "one bad day must not abandon the week"


def test_a_publisher_that_raises_is_a_hard_error_not_a_queue(assets, rows, tmp_path):
    class _Boom(_FakePublisher):
        def publish(self, asset, meta, dry_run):
            raise RuntimeError("the browser went away")

    assert _run(assets, _Boom(), repo=tmp_path) == 2


def test_the_still_open_veto_window_refuses_the_whole_batch(assets, rows, tmp_path, capsys):
    pub = _FakePublisher()
    assert _run(assets, pub, repo=tmp_path, now=BEFORE_VETO) == 2
    assert "REFUSING" in capsys.readouterr().err
    assert pub.calls == []
    assert rows == []


def test_dry_run_is_never_gated_and_writes_nothing(assets, rows, tmp_path, capsys):
    pub = _FakePublisher()
    assert _run(assets, pub, "--dry-run", repo=tmp_path, now=BEFORE_VETO) == 0
    assert all(c["dry_run"] is True for c in pub.calls)
    assert rows == []
    assert not (tmp_path / "marketing").exists()


# ------------------------------------------------------------------------------ ledger

def test_one_ledger_line_per_successful_schedule(assets, rows, tmp_path):
    _run(assets, _FakePublisher(), repo=tmp_path)
    assert len(rows) == 3
    assert all(r["tier"] == 1 and r["status"] == "executed" for r in rows)


def test_a_skipped_day_writes_no_ledger_line(assets, rows, tmp_path):
    pub = _FakePublisher([(True, "already scheduled — nothing uploaded", "https://t/1", None),
                          (True, "scheduled", "https://t/2", None),
                          (True, "scheduled", "https://t/3", None)])
    _run(assets, pub, repo=tmp_path)
    assert len(rows) == 2, "a skip changed nothing, so it records nothing"


def test_a_queued_day_writes_one_line_naming_the_card(assets, rows, tmp_path):
    pub = _FakePublisher([(False, "Timeout", None, "marketing/publish-queue/manual/c.md"),
                          (True, "scheduled", "https://t/2", None),
                          (True, "scheduled", "https://t/3", None)])
    _run(assets, pub, repo=tmp_path)
    queued = [r for r in rows if r["files"]]
    assert len(queued) == 1
    assert queued[0]["files"] == ["marketing/publish-queue/manual/c.md"]


def test_the_ledger_line_carries_the_key_and_no_more_of_the_caption(assets, rows, tmp_path):
    long = "A" * 300
    (assets / "day-1.json").write_text(json.dumps({"slug": "s", "description": long}),
                                       encoding="utf-8")
    _run(assets, _FakePublisher(), repo=tmp_path)
    action = rows[0]["action"].lower()               # the key is case-normalised
    assert "a" * 40 in action
    assert "a" * 41 not in action, "the ledger is public output; the key is all it gets"


def test_the_ledger_line_names_the_platform_the_file_and_the_instant(assets, rows, tmp_path):
    _run(assets, _FakePublisher(), repo=tmp_path)
    action = rows[0]["action"]
    assert "tiktok_web" in action
    assert "day-1.mp4" in action
    assert "2026-09-21T14:00:00-07:00" in action


# ======================================================================== fix round 1
#
# IMPORTANT 4. A command that schedules a week of posts to a live account must not do that
# because someone forgot a flag. Dry run is the default; --go is the deliberate act.

def test_a_bare_invocation_is_a_dry_run(assets, rows, tmp_path):
    pub = _FakePublisher()
    rc = sw.main(["--week", "2026-W39", "--assets-dir", str(assets)],
                 repo=tmp_path, publisher=pub, now=AFTER_VETO)
    assert rc == 0
    assert all(c["dry_run"] is True for c in pub.calls)
    assert rows == [], "a dry run records nothing"


def test_a_bare_invocation_is_not_gated_because_it_writes_nothing(assets, rows, tmp_path):
    pub = _FakePublisher()
    assert sw.main(["--week", "2026-W39", "--assets-dir", str(assets)],
                   repo=tmp_path, publisher=pub, now=BEFORE_VETO) == 0
    assert all(c["dry_run"] is True for c in pub.calls)


def test_go_is_what_makes_it_live(assets, rows, tmp_path):
    pub = _FakePublisher()
    assert _run(assets, pub, "--go", repo=tmp_path) == 0
    assert all(c["dry_run"] is False for c in pub.calls)
    assert len(rows) == 3


def test_dry_run_and_go_together_are_refused_rather_than_ranked(assets, rows, tmp_path):
    with pytest.raises(SystemExit) as exc:
        _run(assets, _FakePublisher(), "--dry-run", "--go", repo=tmp_path)
    assert exc.value.code == 2


def test_the_dry_run_flag_still_works_for_anyone_who_types_it(assets, rows, tmp_path):
    pub = _FakePublisher()
    assert _run(assets, pub, "--dry-run", repo=tmp_path) == 0
    assert all(c["dry_run"] is True for c in pub.calls)


def test_the_plan_is_printed_either_way(assets, rows, tmp_path, capsys):
    sw.main(["--week", "2026-W39", "--assets-dir", str(assets)],
            repo=tmp_path, publisher=_FakePublisher(), now=AFTER_VETO)
    assert "day-1" in capsys.readouterr().out
