"""scripts/gws.py — the one `gws` subprocess seam and the one scrubber.

Three scripts shelled out to `gws` with three private `_gws` copies, and only one of them
(send_reengage) had learned the rule that matters: gws echoes the request it choked on,
including the `--json` body, so a multi-line stderr tail is "here is the request that
failed, addresses and all". crm_sync's copy carried `stderr[:400]` into a queue card that
this PUBLIC repo tracks. The rule lives here now, once.
"""
import json

import pytest

import gws
import privacy


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run(monkeypatch, proc, seen=None):
    def fake(cmd, **kw):
        if seen is not None:
            seen.update(cmd=cmd, kw=kw)
        return proc

    monkeypatch.setattr(gws.subprocess, "run", fake)


# ------------------------------------------------------------------------------------- run()

def test_run_returns_stdout_unchanged(monkeypatch):
    _run(monkeypatch, FakeProc(stdout='{"ok": true}\n'))
    assert gws.run(["sheets", "spreadsheets", "get"], timeout=30) == '{"ok": true}\n'


def test_run_passes_the_body_as_a_json_flag(monkeypatch):
    seen = {}
    _run(monkeypatch, FakeProc(stdout="{}"), seen)
    gws.run(["gmail", "users", "messages", "send"], {"raw": "abc"}, timeout=12)
    assert seen["cmd"][-2] == "--json"
    assert json.loads(seen["cmd"][-1]) == {"raw": "abc"}
    assert seen["kw"]["timeout"] == 12
    assert seen["kw"]["capture_output"] is True


def test_run_sends_no_json_flag_without_a_body(monkeypatch):
    seen = {}
    _run(monkeypatch, FakeProc(stdout="{}"), seen)
    gws.run(["gmail", "users", "getProfile"], timeout=5)
    assert "--json" not in seen["cmd"]


def test_run_keeps_only_the_first_line_of_stderr(monkeypatch):
    """The whole point. gws stderr on a failure can echo the --json body it was handed."""
    at = "@"
    leaked = f"someone{at}northstar.example"
    _run(monkeypatch, FakeProc(returncode=1, stderr=(
        f"quota exceeded\nfull request echoed back: --json "
        f'{{"values": [["{leaked}"]]}}\nand a third line\n')))
    with pytest.raises(RuntimeError) as exc:
        gws.run(["sheets", "spreadsheets", "values", "append"], {"values": []}, timeout=30)
    message = str(exc.value)
    assert "quota exceeded" in message
    assert leaked not in message
    assert "northstar" not in message
    assert "\n" not in message


def test_run_says_so_when_a_failure_produced_no_stderr(monkeypatch):
    _run(monkeypatch, FakeProc(returncode=2, stderr="  \n "))
    with pytest.raises(RuntimeError) as exc:
        gws.run(["sheets", "spreadsheets", "create"], timeout=30)
    assert "no stderr" in str(exc.value)


def test_run_names_the_subcommand_that_failed(monkeypatch):
    _run(monkeypatch, FakeProc(returncode=1, stderr="nope"))
    with pytest.raises(RuntimeError) as exc:
        gws.run(["sheets", "spreadsheets", "values", "batchUpdate", "--params", "{}"],
                timeout=30)
    message = str(exc.value)
    assert "sheets spreadsheets values batchUpdate" in message
    assert "--params" not in message, "the argv tail can carry ids; only the verb is named"


def test_run_requires_an_explicit_timeout(monkeypatch):
    _run(monkeypatch, FakeProc(stdout="{}"))
    with pytest.raises(TypeError):
        gws.run(["gmail", "users", "getProfile"])


# ----------------------------------------------------------------------------------- scrub()

def test_scrub_swaps_an_address_for_its_salted_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    at = "@"
    address = f"buyer{at}northstar.example"
    out = gws.scrub(f"gws failed on row for {address} — retry")
    assert address not in out
    assert f"<redacted:{privacy.email_hash(address)[:8]}>" in out
    assert "retry" in out


def test_scrub_elides_a_long_base64_run_so_a_leaked_body_cannot_be_decoded():
    import base64
    at = "@"
    blob = base64.urlsafe_b64encode(
        f"To: someone{at}northstar.example\n\nbody".encode()).decode().rstrip("=")
    assert len(blob) >= 40
    out = gws.scrub(f'failed request --json {{"raw": "{blob}"}}')
    assert blob not in out
    assert gws.B64_PLACEHOLDER in out
    import re
    assert not re.search(r"[A-Za-z0-9_-]{40,}", out)


def test_scrub_elides_a_google_sheet_id(tmp_path, monkeypatch):
    """A spreadsheet id is a 44-character base64url-shaped token: a private handle to a
    sheet full of customer addresses, and it must not reach a public CI step summary."""
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    fake_id = "1A" + "bQ7z_x-9" * 5 + "2yK"          # 45 chars, id-shaped, not a real id
    out = gws.scrub(f"KDesk CRM ({fake_id}) — 22 people")
    assert fake_id not in out
    assert gws.B64_PLACEHOLDER in out


def test_scrub_masks_a_token_the_caller_names(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    out = gws.scrub("boom with tok=hunter2-hunter2", extra_secrets=("hunter2-hunter2",))
    assert "hunter2-hunter2" not in out


def test_scrub_masks_a_bearer_header_through_redact_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    out = gws.scrub("Authorization: Bearer sekrit-token-value")
    assert "sekrit-token-value" not in out


def test_scrub_keeps_only_the_addresses_the_caller_names(tmp_path, monkeypatch):
    """send_reengage's cards name KDesk's own sender so a human can check the account;
    digest and crm_sync name nothing, which is the strict default."""
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    at = "@"
    own = f"santiagokdesk{at}gmail.com"
    other = f"buyer{at}northstar.example"
    kept = gws.scrub(f"from {own} to {other}", keep=(own,))
    assert own in kept and other not in kept
    strict = gws.scrub(f"from {own} to {other}")
    assert own not in strict and other not in strict


def test_scrub_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    at = "@"
    once = gws.scrub(f"row for buyer{at}northstar.example")
    assert gws.scrub(once) == once


def test_scrub_handles_none_and_non_strings(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    assert gws.scrub(None) == ""
    assert gws.scrub(12) == "12"
