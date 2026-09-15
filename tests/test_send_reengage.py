"""scripts/sales/send_reengage.py — parse the copy, gate on the veto, send one by one.

Two things this file guards that the plan's original draft did not:

1. **Recipients come from the private store, never the markdown.** The tracked draft under
   marketing/email-sequences/ carries `<redacted:XXXXXXXX>` markers only (CLAUDE.md
   "Privacy"), so `parse()` returns the copy and nothing else, and `load_recipients()` reads
   ~/kdesk-analytics/private/re-engage-2026-09-recipients.json (0600, outside the repo).
2. **No address ever reaches stdout, a queue card or the ledger.** Every one of those three
   sinks is either printed by a scheduled job or tracked by git, so each carries the 8-hex
   salted digest prefix - the same marker the draft's table uses, which keeps a row joinable
   to the private store without naming anyone.

Every address literal below is RFC 2606 reserved (tests/test_no_third_party_emails.py scans
this file too, and a real one would fail that guard).
"""
import base64
import datetime as dt
import email
import email.utils
import json
import pathlib
import stat

import pytest

import ledger
import privacy
from sales import send_reengage as sr

TZ = dt.timezone(dt.timedelta(hours=-7))
BEFORE = dt.datetime(2026, 9, 14, 12, 0, tzinfo=TZ)
AFTER = dt.datetime(2026, 9, 17, 12, 0, tzinfo=TZ)

# Mirrors the real draft: subject, body, and a RECIPIENTS TABLE THAT IS ALREADY REDACTED.
MD = """# Re-engagement email — the 14 downloaders the nurture skipped

**Sender:** KDesk Accounting · santiagokdesk@gmail.com

## Subject
Quick question about the {$product_name} you downloaded

## Body
Hi —

Earlier this year you grabbed the free **{$product_name}** from KDesk.

1. The product page: {$page_url}
2. 20% off with **UPGRADE20**: {$paid_url}/UPGRADE20

— Stephen

## Recipients (2 — MailerLite subscriber id · redaction marker · product)
| id | email | product | domain |
|---|---|---|---|
| 197511900414608737 | <redacted:0d859651> | ASC 842 lease workbook | **accounting firm** |
| 197511899790705978 | <redacted:23736e75> | month-end close checklist | individual |

## Also noted while here
- Nothing relevant to the sender.
"""

ONE = "buyer@northstar.example"
TWO = "kaley@example.net"

STORE = {
    "generated": "2026-09-14",
    "source": "marketing/email-sequences/re-engage-2026-09.md",
    "campaign": "Re-engagement — the downloaders the nurture skipped",
    "note": "fixture",
    "merge_field_keys": list(sr.MERGE_FIELDS),
    "recipients": [
        {"subscriber_id": "197511900414608737", "email": ONE, "redaction_id": "0d859651",
         "product": "ASC 842 lease workbook", "segment": "accounting firm",
         "merge_fields": {"product_name": "ASC 842 lease workbook",
                          "page_url": "https://kdeskaccounting.com/templates/asc842/",
                          "paid_url": "https://kdeskaccounting.gumroad.com/l/phxigq",
                          "price": "$249", "free_cap": "3 leases"}},
        {"subscriber_id": "197511899790705978", "email": TWO, "redaction_id": "23736e75",
         "product": "month-end close checklist", "segment": "individual",
         "merge_fields": {"product_name": "month-end close checklist",
                          "page_url": "https://kdeskaccounting.com/templates/month-end-close/",
                          "paid_url": "https://kdeskaccounting.gumroad.com/l/saas",
                          "price": "$249", "free_cap": "the close scaffolding"}},
    ],
    "excluded": [],
}


@pytest.fixture(autouse=True)
def private_salt(tmp_path, monkeypatch):
    """Never read the real salt in a test: a digest here must not match a live marker."""
    privacy._SALT_CACHE.clear()
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    yield
    privacy._SALT_CACHE.clear()


def store_file(tmp_path, payload=None) -> pathlib.Path:
    path = tmp_path / "re-engage-recipients.json"
    path.write_text(json.dumps(payload if payload is not None else STORE), encoding="utf-8")
    path.chmod(0o600)
    return path


def recipients(tmp_path) -> list:
    return sr.load_recipients(store_file(tmp_path))


# --------------------------------------------------------------------------- parse (copy only)

def test_parse_reads_the_subject_line():
    subject, _body = sr.parse(MD)
    assert subject == "Quick question about the {$product_name} you downloaded"


def test_parse_reads_the_body_and_stops_at_the_next_heading():
    _s, body = sr.parse(MD)
    assert body.startswith("Hi —")
    assert "UPGRADE20" in body
    assert body.rstrip().endswith("— Stephen")
    assert "Recipients" not in body


def test_parse_returns_the_copy_only_and_never_harvests_recipients():
    """The ruling: recipients live in the private store, so parse() returns (subject, body)."""
    parsed = sr.parse(MD)
    assert len(parsed) == 2
    assert not any("@" in part for part in parsed)


def test_parse_rejects_a_file_missing_the_subject_or_the_body():
    with pytest.raises(ValueError) as e:
        sr.parse("## Body\ny\n")
    assert "Subject" in str(e.value)
    with pytest.raises(ValueError):
        sr.parse("## Subject\nx\n")


def test_parse_reads_the_real_tracked_draft_and_finds_no_address_in_it():
    text = sr.SOURCE.read_text(encoding="utf-8")
    subject, body = sr.parse(text)
    assert "{$product_name}" in subject
    assert "UPGRADE20" in body
    assert "@" not in body, "the tracked draft must stay address-free"


# ------------------------------------------------------------------- load_recipients (private)

def test_load_recipients_reads_the_private_store(tmp_path):
    people = recipients(tmp_path)
    assert [p.email for p in people] == [ONE, TWO]
    assert people[0].subscriber_id == "197511900414608737"
    assert people[0].product == "ASC 842 lease workbook"
    assert people[0].merge_fields["price"] == "$249"


def test_load_recipients_defaults_to_the_private_path_outside_the_repo():
    assert sr.RECIPIENTS_PATH.name == "re-engage-2026-09-recipients.json"
    assert "kdesk-analytics" in str(sr.RECIPIENTS_PATH)
    assert str(sr.REPO) not in str(sr.RECIPIENTS_PATH), "personal data never lives in the repo"


def test_load_recipients_raises_a_clear_error_when_the_file_is_missing(tmp_path):
    with pytest.raises(sr.RecipientsError) as e:
        sr.load_recipients(tmp_path / "nope.json")
    assert "nope.json" in str(e.value)


def test_load_recipients_raises_on_unreadable_or_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(sr.RecipientsError):
        sr.load_recipients(bad)


def test_load_recipients_rejects_a_row_with_no_address(tmp_path):
    payload = json.loads(json.dumps(STORE))
    payload["recipients"][1]["email"] = ""
    with pytest.raises(sr.RecipientsError) as e:
        sr.load_recipients(store_file(tmp_path, payload))
    assert "email" in str(e.value)


def test_load_recipients_rejects_an_empty_recipient_list(tmp_path):
    payload = json.loads(json.dumps(STORE))
    payload["recipients"] = []
    with pytest.raises(sr.RecipientsError):
        sr.load_recipients(store_file(tmp_path, payload))


def test_load_recipients_warns_when_the_private_file_is_not_0600(tmp_path, capsys):
    path = store_file(tmp_path)
    path.chmod(0o644)
    sr.load_recipients(path)
    err = capsys.readouterr().err
    assert "0600" in err
    assert stat.S_IMODE(path.stat().st_mode) == 0o644, "warn, do not silently chmod"


# --------------------------------------------------------------------------------- merge fields

def test_render_substitutes_every_merge_field():
    out = sr.render("Hi, the {$product_name} at {$page_url}",
                    {"product_name": "ASC 842 workbook", "page_url": "https://x/"})
    assert out == "Hi, the ASC 842 workbook at https://x/"


def test_render_names_every_field_it_could_not_fill():
    with pytest.raises(KeyError) as e:
        sr.render("{$product_name} {$paid_url} {$price}", {"product_name": "x"})
    message = str(e.value)
    assert "paid_url" in message and "price" in message
    assert "product_name" not in message


def test_merge_fields_for_reads_the_recipients_own_stored_fields(tmp_path):
    one = recipients(tmp_path)[0]
    fields = sr.merge_fields_for(one)
    assert set(fields) == set(sr.MERGE_FIELDS)
    assert fields["product_name"] == "ASC 842 lease workbook"


# ---------------------------------------------------------------------------------- the digest

def test_the_digest_is_eight_hex_and_carries_no_address():
    digest = sr.digest(ONE)
    assert len(digest) == 8 and all(c in "0123456789abcdef" for c in digest)
    assert "@" not in digest and "northstar" not in digest
    assert sr.digest(ONE) != sr.digest(TWO)


def test_the_digest_is_the_marker_shape_used_in_the_tracked_draft():
    assert sr.marker(ONE) == f"<redacted:{sr.digest(ONE)}>"


# --------------------------------------------------------------- scrub: the one choke point

def test_scrub_elides_long_base64_runs_so_a_leaked_mime_body_cannot_be_decoded():
    """A raw MIME body (what rfc822() produces) never contains '@', so ADDRESS_RE alone lets
    it straight through undecoded but perfectly decodable. scrub() must catch it too."""
    leaked = sr.rfc822(ONE, "Subject", "Body line", sr.SENDER)
    assert len(leaked) >= 40
    out = sr.scrub(f"gws failed on request with raw={leaked}")
    assert "<b64 elided>" in out
    assert leaked not in out
    assert ONE not in out
    # Not merely truncated - no run long enough to still be a decodable fragment remains.
    import re as _re
    assert not _re.search(r"[A-Za-z0-9_-]{40,}", out)


def test_scrub_composes_address_masking_with_base64_elision():
    """Both transformations must fire on the same string without one hiding the other."""
    leaked = sr.rfc822(ONE, "Subject", "Body", sr.SENDER)
    out = sr.scrub(f"contact {ONE} about the failed request raw={leaked}")
    assert ONE not in out
    assert sr.marker(ONE) in out
    assert leaked not in out
    assert "<b64 elided>" in out


def test_gws_failure_message_keeps_only_the_first_line_of_stderr(monkeypatch):
    """gws stderr on a failure can echo the request it choked on - for a send, that request
    is the --json body containing the base64url MIME envelope, address and all. Only the
    first line of stderr may ever leave _gws()."""
    leaked = sr.rfc822(ONE, "Subject", "Body", sr.SENDER)

    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = f"quota exceeded\nfull request echoed back: --json {{\"raw\": \"{leaked}\"}}\n"

    # The seam moved to scripts/gws.py; the rule it enforces is the same one.
    monkeypatch.setattr(sr.gws.subprocess, "run", lambda *a, **k: FakeProc())
    with pytest.raises(RuntimeError) as e:
        sr._gws(["gmail", "users", "messages", "send"], {"raw": "x"})
    message = str(e.value)
    assert "quota exceeded" in message
    assert leaked not in message
    assert ONE not in message


def test_a_gws_send_failure_queues_a_card_with_no_decodable_address(monkeypatch, tmp_path):
    """Belt and suspenders: even if a leaked base64 fragment reached send_all() some other
    way, the card it writes must still come out clean - that's scrub()'s job, not _gws()'s
    alone."""
    leaked = sr.rfc822(ONE, "Subject", "Body", sr.SENDER)

    def boom(argv, body=None):
        raise RuntimeError(f"gws send failed: raw={leaked}")

    monkeypatch.setattr(sr, "_gws", boom)
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path, limit=1)
    assert (sent, failed) == (0, 1)
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 1
    text = cards[0].read_text(encoding="utf-8")
    assert leaked not in text
    assert ONE not in text
    import re as _re
    assert not _re.search(r"[A-Za-z0-9_-]{40,}", text)


# ------------------------------------------------------------------------------------ the gate

def test_veto_ok_is_false_before_the_window_closes():
    ok, why = sr.veto_ok("2026-09-16T09:00:00-0700", BEFORE)
    assert ok is False
    assert "2026-09-16" in why
    assert "closes" in why, "refuse because the window is open, not because it was unreadable"


def test_veto_ok_is_true_after_the_window_closes():
    ok, _why = sr.veto_ok("2026-09-16T09:00:00-0700", AFTER)
    assert ok is True


@pytest.mark.parametrize("stamp", ["2026-09-16T12:00:00-0700",     # what ledger.py writes
                                   "2026-09-16T12:00:00-07:00",
                                   "2026-09-16T19:00:00Z",
                                   "2026-09-16T12:00:00"])         # hand-edited, no offset
def test_the_window_is_read_in_every_shape_the_ledger_or_a_human_writes(stamp):
    """%z renders as -0700, which fromisoformat could not read before 3.11 - and the runbook
    drives this script with the system python3 (3.9 on this Mac)."""
    assert sr.veto_ok(stamp, BEFORE)[0] is False
    assert sr.veto_ok(stamp, AFTER)[0] is True


def test_veto_ok_refuses_an_unreadable_window_rather_than_assuming_it_closed():
    ok, why = sr.veto_ok("not a timestamp", AFTER)
    assert ok is False
    assert "unparseable" in why


def test_veto_ok_refuses_when_the_entry_has_no_window():
    ok, why = sr.veto_ok(None, AFTER)
    assert ok is False
    assert "no veto_window_close" in why


def test_veto_ok_refuses_a_timezone_naive_now_instead_of_raising():
    """now.tzinfo is None but the window has an offset - comparing them directly raises
    TypeError. The gate must refuse with a reason, not crash the whole run."""
    naive_now = dt.datetime(2026, 9, 17, 8, 0)          # no tzinfo
    ok, why = sr.veto_ok("2026-09-16T09:00:00-0700", naive_now)
    assert ok is False
    assert "naive" in why or "timezone" in why


def entry(**over) -> dict:
    row = {"id": 69, "ts": "t", "tier": 2, "status": "pending_veto", "action": "T1 loosening",
           "reasoning": "r", "files": [], "veto_window_close": "2026-09-16T12:00:00-0700",
           "stephen_reviewed": True}
    row.update(over)
    return row


def test_veto_gate_refuses_a_missing_entry():
    ok, why = sr.veto_gate(None, AFTER)
    assert ok is False
    assert "does not exist" in why


def test_veto_gate_refuses_an_entry_that_is_not_tier_2():
    ok, why = sr.veto_gate(entry(tier=1), AFTER)
    assert ok is False
    assert "tier 1" in why


def test_veto_gate_refuses_an_entry_stephen_actually_vetoed():
    ok, why = sr.veto_gate(entry(status="vetoed"), AFTER)
    assert ok is False
    assert "VETOED" in why


def test_veto_gate_allows_a_tier_2_entry_whose_window_has_closed():
    ok, why = sr.veto_gate(entry(), AFTER)
    assert ok is True
    assert "closed" in why


def test_veto_gate_matches_entry_69s_shape_using_a_fixture_not_the_live_ledger():
    """entry 69's known tier and window, exercised through the `entry()` fixture.

    A previous version of this test read `ledger.find(69, sr.LEDGER_PATH)` from the real,
    live decisions.jsonl and asserted `veto_gate(row, AFTER)[0] is True`. That goes red the
    moment Stephen actually vetoes #69 (status becomes "vetoed") - a correct refusal would
    fail this test. The property this script depends on - a T2 entry whose window has
    closed authorises the send - belongs in a fixture, never in an assertion about the live
    ledger's current, mutable status.
    """
    row = entry(tier=2, veto_window_close="2026-09-16T12:00:00-0700", status="pending_veto")
    assert sr.veto_gate(row, BEFORE)[0] is False, "before the window closes, refuse"
    assert sr.veto_gate(row, AFTER)[0] is True


# ------------------------------------------------------------------------------------- rfc822

def test_rfc822_round_trips_to_and_subject_and_body():
    raw = sr.rfc822("a@example.com", "Subject line", "Body line\nSecond",
                    "santiagokdesk@gmail.com")
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    assert msg["To"] == "a@example.com"
    name, addr = email.utils.parseaddr(msg["From"])
    assert addr == "santiagokdesk@gmail.com"
    assert name == "KDesk Accounting"
    assert msg["Subject"] == "Subject line"
    assert "Second" in msg.get_payload(decode=True).decode()


# ------------------------------------------------------------------------------------ dry run

def no_send(*a, **k):
    raise AssertionError("a dry run must not send")


def test_dry_run_renders_every_email_and_makes_no_gws_call_and_no_sleep(
        capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr(sr, "_sleep", no_send)
    monkeypatch.setattr(sr.ledger, "append", no_send)
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=True, repo=None)
    out = capsys.readouterr().out
    assert (sent, failed) == (2, 0)
    assert "Quick question about the ASC 842 lease workbook you downloaded" in out
    assert "197511900414608737" in out


def test_dry_run_prints_the_digest_and_never_the_address(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr(sr, "_sleep", no_send)
    sr.send_all(MD, recipients(tmp_path), dry_run=True, repo=None)
    out = capsys.readouterr().out
    assert ONE not in out and TWO not in out
    assert "northstar" not in out
    assert sr.marker(ONE) in out and sr.marker(TWO) in out


def test_dry_run_writes_nothing_at_all(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr(sr, "_sleep", no_send)
    monkeypatch.setattr(sr, "merge_fields_for", lambda r: {})      # every field fails
    repo = tmp_path / "repo"
    repo.mkdir()
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=True, repo=repo)
    assert (sent, failed) == (0, 2)
    assert not list(repo.rglob("*.md")), "--dry-run performs zero writes, cards included"


def test_limit_stops_after_n_recipients(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr(sr, "_sleep", no_send)
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=True, repo=None, limit=1)
    assert (sent, failed) == (1, 0)
    assert sr.marker(TWO) not in capsys.readouterr().out


# ---------------------------------------------------------------------------------- live send

def test_live_send_waits_between_recipients_but_not_after_the_last_one(monkeypatch, tmp_path):
    """There is nothing left to pace against once the last recipient is done."""
    calls, sleeps = [], []
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: calls.append(body) or {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", sleeps.append)
    logged = []
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: logged.append(kw) or {"id": 1})
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    assert (sent, failed) == (2, 0)
    assert len(calls) == 2
    assert sleeps == [sr.GAP_SECONDS], "one gap between the two recipients, none trailing"
    assert len(logged) == 2                                  # one ledger line per send


def test_the_live_send_addresses_the_real_recipient(monkeypatch, tmp_path):
    """The address goes into the MIME envelope - and nowhere else."""
    calls = []
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: calls.append(body) or {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path, limit=1)
    raw = calls[0]["raw"]
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    assert msg["To"] == ONE
    assert "ASC 842 lease workbook" in msg["Subject"]


def test_the_ledger_line_carries_the_digest_and_never_the_address(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path, limit=1)
    rows = ledger.entries(path)
    assert len(rows) == 1
    written = path.read_text(encoding="utf-8")
    assert ONE not in written and "northstar" not in written
    assert sr.marker(ONE) in rows[0]["action"]
    assert rows[0]["tier"] == 1 and rows[0]["status"] == "executed"


def test_the_ledger_line_says_recipient_not_mailerlite_subscriber(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path, limit=1)
    rows = ledger.entries(path)
    assert "MailerLite" not in rows[0]["action"]
    assert "recipient" in rows[0]["action"]


def test_a_ledger_append_failure_after_a_successful_send_queues_a_loud_card_and_keeps_going(
        monkeypatch, tmp_path, capsys):
    """A lock/permission error on ledger.append must not swallow that the email already went
    out, and must not silently let a resumed run send it again."""
    calls = []
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: calls.append(body) or {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append",
                        lambda **kw: (_ for _ in ()).throw(OSError("ledger is locked")))
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    assert sent == 2, "both emails genuinely went out"
    assert failed == 2, "both need manual attention: sent but not recorded"
    assert len(calls) == 2, "one bad ledger write must not stop the rest of the campaign"
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*UNLOGGED*.md"))
    assert len(cards) == 2
    text = cards[0].read_text(encoding="utf-8")
    assert "SENT but NOT LOGGED" in text
    assert ONE not in text and TWO not in text and "northstar" not in text
    err = capsys.readouterr().err
    assert "SENT but NOT LOGGED" in err


def test_three_consecutive_gws_failures_stop_the_run_with_one_systemic_card(
        monkeypatch, tmp_path):
    """Three broken sends in a row means gws is down, not that three (or four, or fourteen)
    recipients are broken - one card, not one per person."""
    fields = {"product_name": "x", "page_url": "u", "paid_url": "p", "price": "$1",
             "free_cap": "c"}
    people = [sr.Recipient(subscriber_id=str(i), email=f"r{i}@example.net", product="x",
                           merge_fields=dict(fields)) for i in range(4)]
    calls = []

    def boom(argv, body=None):
        calls.append(1)
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(sr, "_gws", boom)
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    sent, failed = sr.send_all(MD, people, dry_run=False, repo=tmp_path)
    assert sent == 0
    assert len(calls) == 3, "must stop calling gws after the third consecutive failure"
    assert failed == 4, "all four never got the email"
    manual_dir = tmp_path / "marketing" / "publish-queue" / "manual"
    cards = list(manual_dir.glob("*.md"))
    assert len(cards) == 1, "one consolidated card, not one per recipient"
    text = cards[0].read_text(encoding="utf-8")
    assert "3 consecutive" in text
    assert "quota exceeded" in text
    for person in people:
        assert person.email not in text


def test_fewer_than_three_consecutive_gws_failures_still_queue_individually(
        monkeypatch, tmp_path):
    """An isolated blip that self-resolves is not a systemic outage: no early stop, and each
    failure still gets its own card."""
    calls = []

    def flaky(argv, body=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("temporary blip")
        return {"id": "m"}

    monkeypatch.setattr(sr, "_gws", flaky)
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    assert (sent, failed) == (1, 1)
    assert len(calls) == 2, "the second recipient must still be attempted"
    manual_dir = tmp_path / "marketing" / "publish-queue" / "manual"
    cards = list(manual_dir.glob("*.md"))
    assert len(cards) == 1
    assert "SYSTEMIC" not in cards[0].name


def test_live_stdout_never_prints_an_address(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    captured = capsys.readouterr()
    assert ONE not in captured.out + captured.err
    assert sr.marker(ONE) in captured.out


# ------------------------------------------------------------------ never send the same twice

def sent_row(address: str) -> str:
    return json.dumps({"id": 1, "ts": "t", "tier": 1, "status": "executed",
                       "action": f"{sr.SENT_PREFIX}{sr.marker(address)} (MailerLite "
                                 f"subscriber 1, took the free x) from {sr.SENDER}.",
                       "reasoning": "r", "files": [], "veto_window_close": None,
                       "stephen_reviewed": False}) + "\n"


def test_a_recipient_the_ledger_already_records_is_not_emailed_twice(
        monkeypatch, tmp_path, capsys):
    """The normal failure is a run that dies half way; the retry must resume, not restart."""
    path = tmp_path / "decisions.jsonl"
    path.write_text(sent_row(ONE), encoding="utf-8")
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    calls = []
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: calls.append(body) or {"id": "m"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    assert (sent, failed) == (1, 0), "only the recipient with no ledger line"
    assert len(calls) == 1
    assert "already records this send" in capsys.readouterr().out


def test_resend_deliberately_overrides_the_duplicate_guard(monkeypatch, tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(sent_row(ONE), encoding="utf-8")
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    calls = []
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: calls.append(body) or {"id": "m"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    sent, _failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path,
                                resend=True)
    assert sent == 2 and len(calls) == 2


def test_the_guard_matches_this_campaigns_sent_line_and_not_prose_about_it(
        monkeypatch, tmp_path):
    """A planning entry that merely mentions the campaign is not evidence anyone was emailed."""
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(
        {"id": 1, "ts": "t", "tier": 0, "status": "planned", "files": [], "reasoning": "r",
         "action": f"Drafted the {sr.CAMPAIGN} email for {sr.marker(ONE)}; NOT sent.",
         "veto_window_close": None, "stephen_reviewed": False}) + "\n", encoding="utf-8")
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    assert sr.already_sent() == set()
    path.write_text(sent_row(ONE), encoding="utf-8")
    assert sr.already_sent() == {sr.marker(ONE)}


def test_already_sent_reads_the_path_it_is_given_not_the_live_ledger(tmp_path):
    """A fixture ledger, passed explicitly - never ~/…/decisions.jsonl.

    A previous version of this test pointed sr.LEDGER_PATH at the real, live
    decisions.jsonl and asserted already_sent() == set(). That goes red the moment this
    campaign's first real send is logged - a correctly-working duplicate guard would fail
    this test. The property worth locking in - an empty ledger means nobody, a matching row
    means somebody - belongs entirely in fixture space.
    """
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert sr.already_sent(empty) == set()
    populated = tmp_path / "decisions.jsonl"
    populated.write_text(sent_row(ONE), encoding="utf-8")
    assert sr.already_sent(populated) == {sr.marker(ONE)}


# --------------------------------------------------------------------------- queues, not fails

def test_a_missing_merge_field_queues_a_card_instead_of_sending(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    monkeypatch.setattr(sr, "merge_fields_for",
                        lambda r: {} if r.email == TWO else dict(r.merge_fields))
    sent, failed = sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    assert (sent, failed) == (1, 1)
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 1
    text = cards[0].read_text(encoding="utf-8")
    assert sr.digest(TWO) in text
    assert "paid_url" in text, "the card names the fields that could not be filled"


def test_the_queue_card_carries_no_address(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    monkeypatch.setattr(sr, "merge_fields_for", lambda r: {})
    sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path)
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 2
    for card in cards:
        text = card.read_text(encoding="utf-8")
        assert ONE not in text and TWO not in text and "northstar" not in text
        assert "@" not in text.replace(sr.SENDER, ""), "only KDesk's own address may appear"


def test_the_queue_card_says_recipient_not_mailerlite_subscriber(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    monkeypatch.setattr(sr, "merge_fields_for", lambda r: {})
    sr.send_all(MD, recipients(tmp_path), dry_run=False, repo=tmp_path, limit=1)
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    text = cards[0].read_text(encoding="utf-8")
    assert "MailerLite" not in text


# ---------------------------------------------------------------------------------------- main

def test_main_refuses_when_the_veto_entry_is_missing(monkeypatch, capsys, tmp_path):
    empty = tmp_path / "decisions.jsonl"
    empty.write_text("")
    monkeypatch.setattr(sr, "LEDGER_PATH", empty)
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr("sys.argv", ["send_reengage.py"])
    assert sr.main() == 2
    assert "entry 69" in capsys.readouterr().err


def test_main_refuses_before_the_window_closes(monkeypatch, capsys, tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(entry(veto_window_close="2099-01-01T00:00:00-0800")) + "\n")
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr("sys.argv", ["send_reengage.py"])
    assert sr.main() == 2
    assert "2099-01-01" in capsys.readouterr().err


def test_main_refuses_without_reading_the_private_store(monkeypatch, capsys, tmp_path):
    """The gate comes first: a refused run must not even open the recipients file."""
    empty = tmp_path / "decisions.jsonl"
    empty.write_text("")
    monkeypatch.setattr(sr, "LEDGER_PATH", empty)
    monkeypatch.setattr(sr, "load_recipients", no_send)
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr("sys.argv", ["send_reengage.py"])
    assert sr.main() == 2


def test_main_exits_2_when_the_recipients_file_is_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr("sys.argv", ["send_reengage.py", "--dry-run",
                                     "--recipients", str(tmp_path / "gone.json")])
    assert sr.main() == 2
    err = capsys.readouterr().err
    assert "gone.json" in err and "nothing sent" in err


def test_main_dry_run_renders_the_real_copy_and_sends_nothing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr(sr, "_sleep", no_send)
    monkeypatch.setattr(sr.ledger, "append", no_send)
    monkeypatch.setattr("sys.argv", ["send_reengage.py", "--dry-run",
                                     "--recipients", str(store_file(tmp_path))])
    assert sr.main() == 0
    out = capsys.readouterr().out
    assert "UPGRADE20" in out, "the real tracked copy was rendered"
    assert ONE not in out and TWO not in out
    assert "(dry-run)" in out


def test_main_honours_a_custom_veto_entry(monkeypatch, capsys, tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(entry(id=70)) + "\n")
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    monkeypatch.setattr(sr, "_gws", no_send)
    monkeypatch.setattr("sys.argv", ["send_reengage.py", "--veto-entry", "71"])
    assert sr.main() == 2
    assert "entry 71" in capsys.readouterr().err


def test_veto_ok_uses_the_shared_ledger_parse_ts_not_a_private_copy():
    """_parse_iso used to be duplicated here; it now lives once in ledger.py."""
    assert sr.ledger is ledger
    assert not hasattr(sr, "_parse_iso"), "the old private copy must be gone, not just unused"


def test_send_reengage_uses_the_one_shared_gws_seam_and_scrubber():
    """_gws and scrub were duplicated in three scripts and only this one had the
    first-stderr-line rule. The implementation lives in scripts/gws.py now."""
    import gws as gws_module
    assert sr.gws is gws_module
    assert "subprocess" not in dir(sr), "send_reengage must not shell out on its own any more"


def test_scrub_still_keeps_kdesks_own_sender_and_nothing_else(tmp_path, monkeypatch):
    """The shared scrubber is strict by default; this caller names the one address a human
    needs to see in a card (which account failed to send)."""
    monkeypatch.setattr(sr.privacy, "SALT_FILE", tmp_path / "salt.txt")
    out = sr.scrub(f"send from {sr.SENDER} to {ONE} failed")
    assert sr.SENDER in out
    assert ONE not in out and sr.marker(ONE) in out
