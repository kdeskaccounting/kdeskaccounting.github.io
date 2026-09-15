"""scripts/sales/crm_sync.py — build and upsert the private KDesk CRM sheet through gws."""
import json
import os
import stat
import sys
import types

import pytest

from sales import crm_sync as cs

COL = {name: i for i, name in enumerate(cs.COLUMNS)}

GUMROAD = [
    {"email": "Buyer@NorthStar.EXAMPLE", "price": 0, "product_name": "ASC 842 — Free",
     "created_at": "2026-08-01T10:00:00Z"},
    {"email": "buyer@northstar.example", "price": 24900, "product_name": "ASC 842",
     "created_at": "2026-09-02T10:00:00Z"},
    {"email": "a@gmail.com", "price": 0, "product_name": "Month-End Close",
     "created_at": "2026-09-05T10:00:00Z"},
]
MAILERLITE = [
    {"email": "a@gmail.com", "subscribed_at": "2026-09-06 12:00:00",
     "fields": {"interest": "rsu-planner"}},
    {"email": "new@acme.example", "subscribed_at": "2026-09-10 12:00:00", "fields": {"interest": None}},
]


def test_columns_and_tabs_match_the_plan_of_record():
    assert cs.COLUMNS == ("email", "first_seen", "source", "domain", "is_business",
                          "interest", "stage", "mrr", "last_touch", "next_action")
    assert cs.TABS == ("People", "Events", "Pipeline", "Scoreboard")


def test_a1_is_one_based_and_spans_every_column():
    assert cs.a1("People", 2) == "People!A2:J2"


def test_from_gumroad_lowercases_the_email_and_keeps_the_earliest_first_seen():
    people = cs.from_gumroad(GUMROAD)
    buyer = people["buyer@northstar.example"]
    assert buyer.first_seen == "2026-08-01"
    assert buyer.last_touch == "2026-09-02"
    assert buyer.domain == "northstar.example"
    assert buyer.is_business == "TRUE"


def test_from_gumroad_marks_a_paid_buyer_and_a_free_downloader_differently():
    people = cs.from_gumroad(GUMROAD)
    assert people["buyer@northstar.example"].source == "gumroad-paid"
    assert people["buyer@northstar.example"].stage == "customer"
    assert people["a@gmail.com"].source == "gumroad-free"
    assert people["a@gmail.com"].stage == "lead"
    assert people["a@gmail.com"].is_business == "FALSE"


def test_from_mailerlite_carries_the_interest_field():
    people = cs.from_mailerlite(MAILERLITE)
    assert people["a@gmail.com"].interest == "rsu-planner"
    assert people["new@acme.example"].interest == ""
    assert people["new@acme.example"].source == "mailerlite"
    assert people["new@acme.example"].first_seen == "2026-09-10"


def test_from_seo_tracking_reads_the_mailerlite_sync_log(tmp_path):
    d = tmp_path / "marketing" / "seo-tracking"
    d.mkdir(parents=True)
    (d / "mailerlite-sync.jsonl").write_text(
        json.dumps({"email": "info@northwind.example", "product": "ASC 842 lease workbook",
                    "gumroad_sale": "2026-09-11T04:25:17Z",
                    "synced_at": "2026-09-11T08:15-07:00"}) + "\n")
    people = cs.from_seo_tracking(tmp_path)
    assert people["info@northwind.example"].first_seen == "2026-09-11"
    assert people["info@northwind.example"].interest == "ASC 842 lease workbook"
    assert people["info@northwind.example"].is_business == "TRUE"


def test_merge_prefers_the_strongest_source_and_the_earliest_first_seen():
    merged = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    assert merged["a@gmail.com"].source == "gumroad-free"       # gumroad outranks mailerlite
    assert merged["a@gmail.com"].interest == "rsu-planner"      # but the interest is filled in
    assert merged["a@gmail.com"].first_seen == "2026-09-05"     # the earlier of the two
    assert merged["a@gmail.com"].last_touch == "2026-09-06"     # the later of the two
    assert set(merged) == {"buyer@northstar.example", "a@gmail.com", "new@acme.example"}


def test_diff_appends_new_people_and_updates_changed_ones():
    header = list(cs.COLUMNS)
    existing = [header,
                ["a@gmail.com", "2026-09-05", "gumroad-free", "gmail.com", "FALSE", "",
                 "lead", "0", "2026-09-05", ""]]
    wanted = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    updates, appends = cs.diff(existing, wanted)
    assert [row for _i, row in updates] == [wanted["a@gmail.com"]]
    assert updates[0][0] == 2                                   # sheet row number, 1-based
    assert {p.email for p in appends} == {"buyer@northstar.example", "new@acme.example"}


def test_diff_is_a_noop_when_the_sheet_already_matches():
    wanted = cs.from_mailerlite([MAILERLITE[1]])
    person = wanted["new@acme.example"]
    existing = [list(cs.COLUMNS), person.as_row()]
    assert cs.diff(existing, wanted) == ([], [])


def test_diff_tolerates_an_empty_sheet():
    wanted = cs.from_mailerlite([MAILERLITE[1]])
    updates, appends = cs.diff([], wanted)
    assert updates == []
    assert [p.email for p in appends] == ["new@acme.example"]


def test_sync_dry_run_prints_the_diff_and_makes_no_gws_call(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no gws call in --dry-run")))
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    cs.sync(sheet_id="SHEET1", wanted=wanted, existing=[list(cs.COLUMNS)], dry_run=True,
            show_emails=True)
    out = capsys.readouterr().out
    assert "+ buyer@northstar.example" in out
    assert "2 to append" in out


def test_sync_batch_updates_then_appends_through_one_seam(tmp_path, monkeypatch):
    calls = []

    def fake_gws(argv, body=None):
        calls.append((argv, body))
        return {"spreadsheetId": "SHEET1"}

    monkeypatch.setattr(cs, "_gws", fake_gws)
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    header = list(cs.COLUMNS)
    existing = [header, ["a@gmail.com", "2026-01-01", "mailerlite", "gmail.com", "FALSE", "",
                         "lead", "0", "2026-01-01", ""]]
    cs.sync(sheet_id="SHEET1", wanted=wanted, existing=existing, dry_run=False)
    kinds = [argv[3] for argv, _ in calls]
    assert kinds == ["batchUpdate", "append"]
    update_body = calls[0][1]
    assert update_body["valueInputOption"] == "RAW"
    assert update_body["data"][0]["range"] == "People!A2:J2"
    append_body = calls[1][1]
    assert [row[0] for row in append_body["values"]] == ["buyer@northstar.example"]


def test_ensure_sheet_reuses_the_recorded_id(tmp_path, monkeypatch):
    idfile = tmp_path / "crm-sheet-id.txt"
    idfile.write_text("EXISTING-ID\n")
    monkeypatch.setattr(cs, "SHEET_ID_FILE", idfile)
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not create a second sheet")))
    assert cs.ensure_sheet(dry_run=False) == "EXISTING-ID"


def test_ensure_sheet_creates_all_four_tabs_and_records_the_id(tmp_path, monkeypatch):
    idfile = tmp_path / "crm-sheet-id.txt"
    monkeypatch.setattr(cs, "SHEET_ID_FILE", idfile)
    seen = {}

    def fake_gws(argv, body=None):
        seen.update(argv=argv, body=body)
        return {"spreadsheetId": "NEW-ID"}

    monkeypatch.setattr(cs, "_gws", fake_gws)
    assert cs.ensure_sheet(dry_run=False) == "NEW-ID"
    assert idfile.read_text().strip() == "NEW-ID"
    assert seen["body"]["properties"]["title"] == "KDesk CRM"
    assert [s["properties"]["title"] for s in seen["body"]["sheets"]] == list(cs.TABS)


# --- amendments to the brief, each locked by a test -------------------------------------
#
# 1. ensure_sheet() makes exactly ONE gws call: the header row rides along in the create
#    body, so the sheet never exists half-built (the brief's own test asserts the last call
#    seen is the create).
# 2. A self-declared MailerLite interest beats one inferred from a product name, in either
#    merge order (the brief's merge test asserts "rsu-planner" wins over "Month-End Close").
# 3. The sheet id is written 0600; the CLI prints counts, never an address; the Gumroad
#    token travels in an Authorization header, never a query string; a gws failure queues a
#    card and exits non-zero rather than failing silently.


def test_the_created_sheet_carries_the_people_header_in_one_call(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    calls = []

    def fake_gws(argv, body=None):
        calls.append((argv, body))
        return {"spreadsheetId": "NEW-ID"}

    monkeypatch.setattr(cs, "_gws", fake_gws)
    cs.ensure_sheet(dry_run=False)
    assert len(calls) == 1, "creating the sheet must be a single atomic call"
    people = calls[0][1]["sheets"][0]
    assert people["properties"]["title"] == "People"
    header = [cell["userEnteredValue"]["stringValue"]
              for cell in people["data"][0]["rowData"][0]["values"]]
    assert header == list(cs.COLUMNS)


def test_the_recorded_sheet_id_is_private(tmp_path, monkeypatch):
    idfile = tmp_path / "crm-sheet-id.txt"
    monkeypatch.setattr(cs, "SHEET_ID_FILE", idfile)
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: {"spreadsheetId": "NEW-ID"})
    cs.ensure_sheet(dry_run=False)
    assert stat.S_IMODE(idfile.stat().st_mode) == 0o600


def test_ensure_sheet_creates_nothing_in_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no gws call in --dry-run")))
    assert cs.ensure_sheet(dry_run=True) == "(would create a new spreadsheet)"
    assert not (tmp_path / "crm-sheet-id.txt").exists()


def test_a_declared_interest_beats_an_inferred_one_in_either_merge_order():
    forward = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    backward = cs.merge(cs.from_mailerlite(MAILERLITE), cs.from_gumroad(GUMROAD))
    assert forward["a@gmail.com"].interest == "rsu-planner"
    assert backward["a@gmail.com"].interest == "rsu-planner"
    assert backward["a@gmail.com"].source == "gumroad-free"


def test_an_inferred_interest_still_fills_an_empty_one():
    only_gumroad = cs.merge(cs.from_gumroad(GUMROAD))
    assert only_gumroad["a@gmail.com"].interest == "Month-End Close"


def test_sync_without_show_emails_prints_counts_and_no_address(capsys, monkeypatch):
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no gws call in --dry-run")))
    wanted = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    cs.sync(sheet_id="SHEET1", wanted=wanted, existing=[list(cs.COLUMNS)], dry_run=True,
            show_emails=False)
    out = capsys.readouterr().out
    assert "3 to append" in out
    assert "business domains 2/3" in out          # scott + new@acme.example, not a@gmail.com
    for address in ("buyer@northstar.example", "a@gmail.com", "new@acme.example"):
        assert address not in out


def test_the_cli_dry_run_prints_counts_only_and_touches_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "fetch_gumroad", lambda: GUMROAD)
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no gws call in --dry-run")))
    monkeypatch.setattr(cs.ledger, "append", lambda **k: (_ for _ in ()).throw(
        AssertionError("no ledger append in --dry-run")))
    assert cs.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "3 to append" in out
    for address in ("buyer@northstar.example", "a@gmail.com", "new@acme.example"):
        assert address not in out
    assert not (tmp_path / "crm-sheet-id.txt").exists()
    assert not (tmp_path / "marketing").exists()


def test_a_gws_failure_queues_a_card_and_exits_non_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "fetch_gumroad", lambda: GUMROAD)
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("gws sheets spreadsheets create failed: insufficient authentication scopes")))
    assert cs.main([]) == 1
    cards = sorted((tmp_path / "marketing" / "publish-queue" / "manual").glob("crm-sync-*.md"))
    assert len(cards) == 1
    body = cards[0].read_text()
    assert "gws auth login" in body
    assert "insufficient authentication scopes" in body
    for address in ("buyer@northstar.example", "a@gmail.com", "new@acme.example"):
        assert address not in body


def test_the_queue_card_masks_a_token_that_leaked_into_the_error(tmp_path, monkeypatch):
    monkeypatch.setenv("GUMROAD_ACCESS_TOKEN", "sekrit-token-value")
    card = cs.queue_card("gws failed with Authorization: Bearer sekrit-token-value", repo=tmp_path)
    assert "sekrit-token-value" not in card.read_text()


def test_fetch_gumroad_sends_a_bearer_header_not_a_query_param(monkeypatch):
    seen = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"sales": [{"email": "x@y.example"}], "next_page_key": None}

    def fake_get(url, headers=None, params=None, timeout=None):
        seen.update(url=url, headers=headers, params=params)
        return Response()

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setenv("GUMROAD_ACCESS_TOKEN", "FAKE-GUMROAD-TOKEN")
    assert cs.fetch_gumroad() == [{"email": "x@y.example"}]
    assert seen["headers"]["Authorization"] == "Bearer FAKE-GUMROAD-TOKEN"
    assert "access_token" not in (seen["params"] or {})
    assert "FAKE-GUMROAD-TOKEN" not in seen["url"]


def test_fetch_mailerlite_pages_until_the_cursor_stops_moving(tmp_path, monkeypatch):
    tokenfile = tmp_path / "mailerlite-token.txt"
    tokenfile.write_text("FAKE-ML-TOKEN\n")
    monkeypatch.setattr(cs, "MAILERLITE_TOKEN_FILE", tokenfile)
    pages = [{"data": [{"email": "one@acme.example"}], "meta": {"next_cursor": "c2"}},
             {"data": [{"email": "two@acme.example"}], "meta": {"next_cursor": "c2"}}]
    seen = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, headers=None, params=None, timeout=None):
        seen.append((headers, params))
        return Response(pages[min(len(seen) - 1, len(pages) - 1)])

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=fake_get))
    subscribers = cs.fetch_mailerlite()
    assert [s["email"] for s in subscribers] == ["one@acme.example", "two@acme.example"]
    assert len(seen) == 2, "a repeated cursor must stop the loop, not spin"
    assert seen[0][0]["Authorization"] == "Bearer FAKE-ML-TOKEN"


def test_read_people_returns_the_rows_below_the_cap(monkeypatch):
    rows = [list(cs.COLUMNS)] + [["p%d@acme.example" % i] for i in range(5)]
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: {"values": rows})
    assert cs.read_people("SHEET1") == rows


def test_read_people_refuses_to_silently_duplicate_past_the_row_cap(monkeypatch):
    full = [["p%d@acme.example" % i] for i in range(cs.ROW_CAP)]
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: {"values": full})
    try:
        cs.read_people("SHEET1")
    except RuntimeError as exc:
        assert "row read cap" in str(exc)
    else:
        raise AssertionError("a full People tab must stop the sync, not duplicate it")


# --- containment: the tracker is pseudonymised, and humans own some columns ---------------


def _sanitised_tracker(tmp_path, digest, product="ASC 842 lease workbook"):
    d = tmp_path / "marketing" / "seo-tracking"
    d.mkdir(parents=True, exist_ok=True)
    (d / "mailerlite-sync.jsonl").write_text(
        json.dumps({"email_sha256": digest, "product": product,
                    "gumroad_sale": "2026-09-11T04:25:17Z",
                    "synced_at": "2026-09-11T08:15-07:00"}) + "\n")
    return tmp_path


def test_from_seo_tracking_joins_a_hash_only_row_to_an_address_we_already_hold(
        tmp_path, monkeypatch):
    """The tracked file carries no address; the live API pull does. Hashing what we know is
    how a pseudonymised row still enriches its person."""
    monkeypatch.setattr(cs.privacy, "SALT_FILE", tmp_path / "salt.txt")
    repo = _sanitised_tracker(tmp_path, cs.privacy.email_hash("info@northwind.example"))
    people = cs.from_seo_tracking(repo, known_emails=["INFO@northwind.example", "x@y.example"])
    assert set(people) == {"info@northwind.example"}
    assert people["info@northwind.example"].interest == "ASC 842 lease workbook"
    assert people["info@northwind.example"].first_seen == "2026-09-11"
    assert people["info@northwind.example"].is_business == "TRUE"


def test_from_seo_tracking_skips_a_hash_it_cannot_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(cs.privacy, "SALT_FILE", tmp_path / "salt.txt")
    repo = _sanitised_tracker(tmp_path, cs.privacy.email_hash("gone@northwind.example"))
    assert cs.from_seo_tracking(repo, known_emails=["someone@else.example"]) == {}
    assert cs.from_seo_tracking(repo) == {}


def test_from_seo_tracking_needs_no_known_emails_for_a_legacy_plaintext_row(tmp_path):
    d = tmp_path / "marketing" / "seo-tracking"
    d.mkdir(parents=True)
    (d / "mailerlite-sync.jsonl").write_text(
        json.dumps({"email": "info@northwind.example", "product": "runway calculator",
                    "gumroad_sale": "2026-09-11T04:25:17Z"}) + "\n")
    assert set(cs.from_seo_tracking(tmp_path)) == {"info@northwind.example"}


def test_the_column_ownership_split_covers_every_column():
    assert set(cs.MACHINE_COLUMNS) | set(cs.HUMAN_COLUMNS) | {"email", "first_seen"} == set(cs.COLUMNS)
    assert cs.HUMAN_COLUMNS == ("next_action",)
    assert "next_action" not in cs.MACHINE_COLUMNS


def test_diff_never_overwrites_a_next_action_a_human_typed():
    wanted = cs.from_mailerlite([MAILERLITE[1]])                  # next_action == ""
    person = wanted["new@acme.example"]
    row = person.as_row()
    row[COL["next_action"]] = "call them Tuesday"
    row[COL["stage"]] = "lead"
    existing = [list(cs.COLUMNS), row]
    updates, appends = cs.diff(existing, wanted)
    assert appends == []
    assert updates == [], "nothing machine-owned changed, so there is nothing to write"


def test_diff_updates_machine_columns_while_keeping_the_human_one():
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    person = wanted["buyer@northstar.example"]                    # stage customer, paid
    stale = person.as_row()
    stale[COL["stage"]] = "lead"                                  # machine-owned, out of date
    stale[COL["interest"]] = ""                                   # machine-owned, out of date
    stale[COL["next_action"]] = "send the case study"             # human-owned, keep it
    existing = [list(cs.COLUMNS), stale]
    updates, _appends = cs.diff(existing, wanted)
    assert len(updates) == 1
    row, updated = updates[0]
    assert row == 2
    assert updated.stage == "customer"                            # machine column refreshed
    assert updated.interest == person.interest
    assert updated.next_action == "send the case study"           # human column preserved
    assert updated.as_row()[COL["next_action"]] == "send the case study"


def test_diff_keeps_the_earliest_first_seen_the_sheet_has_ever_held():
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    person = wanted["buyer@northstar.example"]                    # first_seen 2026-08-01
    older = person.as_row()
    older[COL["first_seen"]] = "2025-01-01"
    older[COL["stage"]] = "lead"                                  # force an update
    existing = [list(cs.COLUMNS), older]
    updates, _appends = cs.diff(existing, wanted)
    assert updates[0][1].first_seen == "2025-01-01", "first_seen must never move forward"


def test_a_human_edit_survives_a_second_sync(tmp_path, monkeypatch):
    """The regression that matters: edit the sheet, re-run, edit still there, zero writes."""
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a no-op sync must make no gws call")))
    wanted = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    rows = [list(cs.COLUMNS)] + [p.as_row() for p in wanted.values()]
    rows[1][COL["next_action"]] = "intro call booked"
    assert cs.sync(sheet_id="S", wanted=wanted, existing=rows, dry_run=False,
                   show_emails=False) == (0, 0)
    assert rows[1][COL["next_action"]] == "intro call booked"


# --- fix round: failure handling, dry-run purity, and the counts-only default -------------


def test_sync_defaults_to_counts_only():
    """The CLI is the common caller; the safe default is the one that cannot leak."""
    import inspect
    assert inspect.signature(cs.sync).parameters["show_emails"].default is False


def _fail(exc):
    def boom(*_a, **_k):
        raise exc
    return boom


def test_a_dry_run_failure_prints_the_card_to_stderr_and_writes_nothing(
        tmp_path, monkeypatch, capsys):
    """--dry-run performs zero writes - including the queue card. On Actions, where the
    tokens are absent, writing one would dirty the checkout on every scheduled run."""
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "fetch_gumroad", _fail(RuntimeError("no gumroad token on this box")))
    assert cs.main(["--dry-run"]) == 1
    err = capsys.readouterr().err
    assert "no gumroad token on this box" in err
    assert "gws auth login" in err, "the card body itself goes to stderr"
    assert not (tmp_path / "marketing").exists(), "--dry-run must not write a queue card"


def test_a_live_failure_still_writes_the_card(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "fetch_gumroad", _fail(RuntimeError("boom")))
    assert cs.main([]) == 1
    assert len(list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))) == 1


@pytest.mark.parametrize("exc", [
    json.JSONDecodeError("Expecting value", "", 0),          # gws printed something odd
    KeyError("spreadsheetId"),                               # gws printed a different shape
    OSError("connection reset"),
])
def test_any_unexpected_failure_queues_a_card_rather_than_crashing(exc, tmp_path, monkeypatch):
    """A traceback out of a scheduled job is a silent failure: nobody reads it."""
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "fetch_gumroad", lambda: GUMROAD)
    monkeypatch.setattr(cs, "_gws", _fail(exc))
    assert cs.main([]) == 1
    assert len(list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))) == 1


def test_a_ledger_failure_is_never_swallowed_into_a_card(tmp_path, monkeypatch):
    """The ledger is the audit trail; a lost entry must be loud, not queued."""
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "SHEET_ID_FILE", tmp_path / "crm-sheet-id.txt")
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "fetch_gumroad", lambda: GUMROAD)
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: {"spreadsheetId": "SHEET1"})
    monkeypatch.setattr(cs.ledger, "append", _fail(RuntimeError("ledger disk full")))
    with pytest.raises(RuntimeError, match="ledger disk full"):
        cs.main([])
    assert not (tmp_path / "marketing").exists(), "a ledger failure is not a queue-card case"


def test_an_empty_sheet_id_file_counts_as_absent(tmp_path, monkeypatch):
    """ensure_sheet() and main() must agree, or a blank file makes main call gws on a
    placeholder id during --dry-run."""
    idfile = tmp_path / "crm-sheet-id.txt"
    idfile.write_text("   \n")
    monkeypatch.setattr(cs, "SHEET_ID_FILE", idfile)
    monkeypatch.setattr(cs, "REPO", tmp_path)
    monkeypatch.setattr(cs, "fetch_mailerlite", lambda: MAILERLITE)
    monkeypatch.setattr(cs, "fetch_gumroad", lambda: GUMROAD)
    monkeypatch.setattr(cs, "_gws", _fail(AssertionError("no gws call for a blank id file")))
    assert cs.recorded_sheet_id() is None
    assert cs.ensure_sheet(dry_run=True) == "(would create a new spreadsheet)"
    assert cs.main(["--dry-run"]) == 0
