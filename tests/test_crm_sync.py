"""scripts/sales/crm_sync.py — build and upsert the private KDesk CRM sheet through gws."""
import json
import stat
import sys
import types

from sales import crm_sync as cs

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
    {"email": "new@acme.io", "subscribed_at": "2026-09-10 12:00:00", "fields": {"interest": None}},
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
    assert people["new@acme.io"].interest == ""
    assert people["new@acme.io"].source == "mailerlite"
    assert people["new@acme.io"].first_seen == "2026-09-10"


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
    assert set(merged) == {"buyer@northstar.example", "a@gmail.com", "new@acme.io"}


def test_diff_appends_new_people_and_updates_changed_ones():
    header = list(cs.COLUMNS)
    existing = [header,
                ["a@gmail.com", "2026-09-05", "gumroad-free", "gmail.com", "FALSE", "",
                 "lead", "0", "2026-09-05", ""]]
    wanted = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    updates, appends = cs.diff(existing, wanted)
    assert [row for _i, row in updates] == [wanted["a@gmail.com"]]
    assert updates[0][0] == 2                                   # sheet row number, 1-based
    assert {p.email for p in appends} == {"buyer@northstar.example", "new@acme.io"}


def test_diff_is_a_noop_when_the_sheet_already_matches():
    wanted = cs.from_mailerlite([MAILERLITE[1]])
    person = wanted["new@acme.io"]
    existing = [list(cs.COLUMNS), person.as_row()]
    assert cs.diff(existing, wanted) == ([], [])


def test_diff_tolerates_an_empty_sheet():
    wanted = cs.from_mailerlite([MAILERLITE[1]])
    updates, appends = cs.diff([], wanted)
    assert updates == []
    assert [p.email for p in appends] == ["new@acme.io"]


def test_sync_dry_run_prints_the_diff_and_makes_no_gws_call(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no gws call in --dry-run")))
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    cs.sync(sheet_id="SHEET1", wanted=wanted, existing=[list(cs.COLUMNS)], dry_run=True)
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
    assert "business domains 2/3" in out          # scott + new@acme.io, not a@gmail.com
    for address in ("buyer@northstar.example", "a@gmail.com", "new@acme.io"):
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
    for address in ("buyer@northstar.example", "a@gmail.com", "new@acme.io"):
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
    for address in ("buyer@northstar.example", "a@gmail.com", "new@acme.io"):
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
            return {"sales": [{"email": "x@y.com"}], "next_page_key": None}

    def fake_get(url, headers=None, params=None, timeout=None):
        seen.update(url=url, headers=headers, params=params)
        return Response()

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setenv("GUMROAD_ACCESS_TOKEN", "FAKE-GUMROAD-TOKEN")
    assert cs.fetch_gumroad() == [{"email": "x@y.com"}]
    assert seen["headers"]["Authorization"] == "Bearer FAKE-GUMROAD-TOKEN"
    assert "access_token" not in (seen["params"] or {})
    assert "FAKE-GUMROAD-TOKEN" not in seen["url"]


def test_fetch_mailerlite_pages_until_the_cursor_stops_moving(tmp_path, monkeypatch):
    tokenfile = tmp_path / "mailerlite-token.txt"
    tokenfile.write_text("FAKE-ML-TOKEN\n")
    monkeypatch.setattr(cs, "MAILERLITE_TOKEN_FILE", tokenfile)
    pages = [{"data": [{"email": "one@acme.io"}], "meta": {"next_cursor": "c2"}},
             {"data": [{"email": "two@acme.io"}], "meta": {"next_cursor": "c2"}}]
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
    assert [s["email"] for s in subscribers] == ["one@acme.io", "two@acme.io"]
    assert len(seen) == 2, "a repeated cursor must stop the loop, not spin"
    assert seen[0][0]["Authorization"] == "Bearer FAKE-ML-TOKEN"
